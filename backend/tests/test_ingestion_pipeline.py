"""Ingestion safety (WS1 M0): staged parses, dry runs that touch nothing, the abort
gates, per-vintage collections behind the ``municipal_code`` alias, and the prod push
tool. Qdrant is the client's in-memory mode and the embedder is a stub, so nothing here
touches the network or loads a model."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from ingestion import parse_chicago_code as pcc
from ingestion import push_index, source_check, update
from ingestion.code_vintage import CODE_ALIAS, collection_for
from ingestion.diff_report import gate_failures
from ingestion.manifest import SectionEntry, build_manifest, diff_manifests
from ingestion.parse_chicago_code import Section

DIM = 4


class StubModel:
    """Deterministic 4-dim vectors; enough for the pipeline, no torch."""

    def encode(self, texts, **_kw):
        return np.array([[float(len(t) % 7), 1.0, float(i % 3), 0.5] for i, t in enumerate(texts)])

    def get_sentence_embedding_dimension(self):
        return DIM


def _sec(sid: str, body: str, *, title: str = "Heading", title_number: int = 17) -> Section:
    return Section(section=sid, section_title=title, title_number=title_number, body_paragraphs=[body])


def _export(tmp_path: Path, date: str) -> Path:
    path = tmp_path / f"export-{date.replace(' ', '_').replace(',', '')}.html"
    path.write_text(f"<div>Current through Council Journal of {date}</div>")
    return path


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    """Point every ingestion path at tmp_path; returns a setter for the next parse."""
    data = tmp_path / "data"
    data.mkdir()
    paths = {
        "SECTIONS_DIR": data / "sections",
        "SECTIONS_NEW": data / "sections.new",
        "CHUNKS_FILE": data / "chunks.jsonl",
        "CHUNKS_NEW": data / "chunks.new.jsonl",
        "DIFF_DIR": data / "diff",
        "SNAPSHOTS_DIR": data / "snapshots",
        "CHANGES_FILE": tmp_path / "code_changes.json",
        "MANIFEST_FILE": data / "manifest.json",
        "VINTAGE_FILE": tmp_path / "code_vintage.json",
        "SOURCE_HASH_FILE": data / "source_hash.json",
    }
    for name, value in paths.items():
        monkeypatch.setattr(update, name, value)
    monkeypatch.setattr(source_check, "SOURCE_HASH_FILE", paths["SOURCE_HASH_FILE"])

    sections: list[Section] = []
    monkeypatch.setattr(pcc, "parse", lambda *_a, **_k: iter(list(sections)))

    def next_parse(*secs: Section) -> None:
        sections[:] = secs

    next_parse.paths = paths
    return next_parse


def _ingest(corpus, tmp_path, client, date: str, *secs: Section, **kw) -> int:
    corpus(*secs)
    return update.run(_export(tmp_path, date), client=client, model=StubModel(), **kw)


def _sections_in(client, collection) -> dict[str, int]:
    out: dict[str, int] = {}
    for p in client.scroll(collection, limit=1000, with_payload=True)[0]:
        out[p.payload["section"]] = out.get(p.payload["section"], 0) + 1
    return out


# --- manifest -------------------------------------------------------------------------------

def test_a_retitle_is_a_change_without_moving_the_content_hash(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for d, title in ((a, "Old heading"), (b, "New heading")):
        d.mkdir()
        (d / "17-1-0100.json").write_text(json.dumps({"section": "17-1-0100", "section_title": title, "body_paragraphs": ["x"]}))
    old, new = build_manifest(a), build_manifest(b)
    assert old["17-1-0100"].content_hash == new["17-1-0100"].content_hash  # the zoning cache keys on this
    assert diff_manifests(old, new).modified == ["17-1-0100"]


def test_a_manifest_without_title_hashes_never_reports_a_mass_retitle():
    old = {"17-1-0100": SectionEntry(content_hash="c", chunk_count=1, title_number=17)}
    new = {"17-1-0100": SectionEntry(content_hash="c", chunk_count=1, title_number=17, title_hash="t")}
    assert diff_manifests(old, new).total_changes == 0


# --- parser ---------------------------------------------------------------------------------

def test_a_full_parse_removes_sections_the_export_no_longer_has(tmp_path, monkeypatch):
    out = tmp_path / "sections"
    out.mkdir()
    (out / "17-9-0999.json").write_text("{}")  # repealed since the last parse
    monkeypatch.setattr(pcc, "parse", lambda *_a, **_k: iter([_sec("17-1-0100", "body")]))

    _, removed = pcc.write_sections(tmp_path / "x.html", out)

    assert removed == ["17-9-0999"]
    assert sorted(p.name for p in out.iterdir()) == ["17-1-0100.json"]
    assert not (tmp_path / "sections.tmp").exists()


def test_a_single_title_parse_deletes_nothing(tmp_path, monkeypatch):
    out = tmp_path / "sections"
    out.mkdir()
    (out / "2-1-010.json").write_text("{}")
    monkeypatch.setattr(pcc, "parse", lambda *_a, **_k: iter([_sec("17-1-0100", "body")]))

    _, removed = pcc.write_sections(tmp_path / "x.html", out, only_title=17)

    assert removed == []
    assert (out / "2-1-010.json").exists() and (out / "17-1-0100.json").exists()


# --- update: dry run ------------------------------------------------------------------------

def test_dry_run_writes_only_the_diff(corpus, tmp_path):
    client = QdrantClient(":memory:")
    assert _ingest(corpus, tmp_path, client, "March 18, 2026", _sec("17-1-0100", "one"), _sec("17-1-0200", "two")) == 0
    p = corpus.paths
    before = {f: f.read_bytes() for f in (p["VINTAGE_FILE"], p["MANIFEST_FILE"], p["CHUNKS_FILE"])}
    before_sections = {f.name: f.read_bytes() for f in p["SECTIONS_DIR"].iterdir()}
    collections_before = push_index.status(client)

    corpus(_sec("17-1-0100", "one, amended"), _sec("17-1-0300", "three"))
    rc = update.run(_export(tmp_path, "June 17, 2026"), dry_run=True, client=client, model=StubModel())

    assert rc == 0
    assert {f: f.read_bytes() for f in before} == before
    assert {f.name: f.read_bytes() for f in p["SECTIONS_DIR"].iterdir()} == before_sections
    assert push_index.status(client) == collections_before
    diff = json.loads((p["DIFF_DIR"] / "2026-06-17" / "diff.json").read_text())
    assert (diff["added"], diff["modified"], diff["deleted"]) == (["17-1-0300"], ["17-1-0100"], ["17-1-0200"])
    assert "+" in diff["modified_detail"][0]["text_diff"]
    assert (p["DIFF_DIR"] / "2026-06-17" / "report.md").exists()


# --- update: apply --------------------------------------------------------------------------

def test_a_new_vintage_gets_its_own_collection_and_the_alias(corpus, tmp_path):
    client = QdrantClient(":memory:")
    _ingest(corpus, tmp_path, client, "March 18, 2026", _sec("17-1-0100", "one"), _sec("17-1-0200", "two"))
    old = collection_for("2026-03-18")

    rc = _ingest(corpus, tmp_path, client, "June 17, 2026", _sec("17-1-0100", "one, amended"), _sec("17-1-0300", "three"))

    new = collection_for("2026-06-17")
    assert rc == 0
    assert push_index.alias_target(client) == new
    assert _sections_in(client, new) == {"17-1-0100": 1, "17-1-0300": 1}  # 17-1-0200 is gone
    assert _sections_in(client, old) == {"17-1-0100": 1, "17-1-0200": 1}  # rollback target untouched
    p = corpus.paths
    vintage = json.loads(p["VINTAGE_FILE"].read_text())
    assert vintage["current_through"] == "2026-06-17"
    assert vintage["collection"] == new and vintage["chunk_count"] == 2
    assert len(vintage["export_sha256"]) == 64 and vintage["ingested_at"]
    changes = json.loads(p["CHANGES_FILE"].read_text())["refreshes"][0]
    assert (changes["from"], changes["to"], changes["removed"]) == ("2026-03-18", "2026-06-17", ["17-1-0200"])
    assert (p["SNAPSHOTS_DIR"] / "2026-03-18" / "sections" / "17-1-0200.json").exists()
    assert not (p["SECTIONS_DIR"] / "17-1-0200.json").exists()


def test_the_same_vintage_is_updated_in_place(corpus, tmp_path):
    client = QdrantClient(":memory:")
    _ingest(corpus, tmp_path, client, "March 18, 2026", _sec("17-1-0100", "one"), _sec("17-1-0200", "two"))

    # Dropping half of a two-section Title 17 trips the gates; forced, as a parser fix would be.
    rc = _ingest(corpus, tmp_path, client, "March 18, 2026", _sec("17-1-0100", "one", title="Fixed heading"), force=True)

    coll = collection_for("2026-03-18")
    assert rc == 0
    assert push_index.alias_target(client) == coll
    assert _sections_in(client, coll) == {"17-1-0100": 1}
    text = client.scroll(coll, limit=5, with_payload=True)[0][0].payload["text"]
    assert "Fixed heading" in text


def test_a_tripped_gate_stops_the_apply_unless_forced(corpus, tmp_path):
    client = QdrantClient(":memory:")
    many = [_sec(f"13-1-{i:03d}", "x", title_number=13) for i in range(10)]
    _ingest(corpus, tmp_path, client, "March 18, 2026", _sec("17-1-0100", "one"), *many)

    assert _ingest(corpus, tmp_path, client, "June 17, 2026", _sec("17-1-0100", "one"), *many[:5]) == 1
    assert push_index.alias_target(client) == collection_for("2026-03-18")

    assert _ingest(corpus, tmp_path, client, "June 17, 2026", _sec("17-1-0100", "one"), *many[:5], force=True) == 0
    assert push_index.alias_target(client) == collection_for("2026-06-17")


def _diff(by_title, *, old_v="2026-03-18", new_v="2026-06-17", empty=()):
    return {"old_vintage": old_v, "new_vintage": new_v, "by_title": by_title, "new_empty_title17": list(empty)}


@pytest.mark.parametrize("diff, expect", [
    (_diff({"17": {"old": 147, "new": 148}}), []),
    (_diff({"17": {"old": 147, "new": 147}}, new_v="2026-01-01"), ["vintage goes backwards"]),
    (_diff({"14": {"old": 872, "new": 0}}), ["Title 14 disappeared"]),
    (_diff({"13": {"old": 472, "new": 401}}), ["Title 13 lost 71"]),
    (_diff({"13": {"old": 472, "new": 468}}), []),  # under 2%
    (_diff({"17": {"old": 147, "new": 146}}), ["Title 17 section count dropped"]),
    (_diff({"17": {"old": 147, "new": 147}}, empty=["17-1-0100"]), ["new empty-body Title 17"]),
    (_diff({"17": {"old": 147, "new": 147}, "19": {"old": 0, "new": 3}}), ["Title 19 is new"]),
])
def test_gates(diff, expect):
    got = gate_failures(diff)
    assert len(got) == len(expect) and all(e in g for e, g in zip(expect, got))


# --- push_index -----------------------------------------------------------------------------

def _seed(client: QdrantClient, name: str, texts: dict[str, list[str]]) -> None:
    client.create_collection(name, vectors_config=VectorParams(size=DIM, distance=Distance.COSINE))
    pid = 0
    points = []
    for sid, chunks in texts.items():
        for t in chunks:
            pid += 1
            points.append(PointStruct(id=pid, vector=[1.0, 0.0, 0.0, float(pid)], payload={"section": sid, "text": t}))
    client.upsert(name, points=points)


def test_upload_verify_switch_and_rollback():
    local, prod = QdrantClient(":memory:"), QdrantClient(":memory:")
    _seed(local, "municipal_code_2026-06-17", {"17-1-0100": ["a", "b"], "17-1-0300": ["c"]})
    _seed(prod, "municipal_code_2026-03-18", {"17-1-0100": ["a"]})
    push_index.switch_alias(prod, "municipal_code_2026-03-18")

    assert push_index.upload(local, prod, "municipal_code_2026-06-17") == 3
    result = push_index.verify(local, "municipal_code_2026-06-17", prod, "municipal_code_2026-06-17")
    assert result.ok and result.target_points == 3
    original = local.retrieve("municipal_code_2026-06-17", ids=[1], with_vectors=True)[0]
    copied = prod.retrieve("municipal_code_2026-06-17", ids=[1], with_vectors=True)[0]
    assert copied.vector == pytest.approx(original.vector)  # copied, not re-embedded

    assert push_index.switch_alias(prod, "municipal_code_2026-06-17") == "municipal_code_2026-03-18"
    assert prod.count(CODE_ALIAS).count == 3
    assert push_index.switch_alias(prod, "municipal_code_2026-03-18") == "municipal_code_2026-06-17"
    assert prod.count(CODE_ALIAS).count == 1


def test_verify_catches_a_changed_chunk_and_switch_refuses(monkeypatch):
    local, prod = QdrantClient(":memory:"), QdrantClient(":memory:")
    _seed(local, "municipal_code_2026-06-17", {"17-1-0100": ["a", "b"]})
    _seed(prod, "municipal_code_2026-06-17", {"17-1-0100": ["a", "tampered"]})

    result = push_index.verify(local, "municipal_code_2026-06-17", prod, "municipal_code_2026-06-17")
    assert not result.ok and list(result.differing_sections) == ["17-1-0100"]

    clients = {"http://local": local, "http://prod": prod}
    monkeypatch.setattr(push_index, "_client", clients.__getitem__)
    rc = push_index.main(["--source", "http://local", "--target", "http://prod", "--switch",
                          "--collection", "municipal_code_2026-06-17"])
    assert rc == 1
    assert push_index.alias_target(prod) is None


def test_upload_never_rebuilds_the_collection_the_alias_serves():
    local, prod = QdrantClient(":memory:"), QdrantClient(":memory:")
    _seed(local, "municipal_code_2026-03-18", {"17-1-0100": ["a"]})
    _seed(prod, "municipal_code_2026-03-18", {"17-1-0100": ["a"]})
    push_index.switch_alias(prod, "municipal_code_2026-03-18")
    with pytest.raises(SystemExit):
        push_index.upload(local, prod, "municipal_code_2026-03-18", replace=True)


def test_drop_refuses_the_served_collection():
    prod = QdrantClient(":memory:")
    _seed(prod, "municipal_code_2026-03-18", {"17-1-0100": ["a"]})
    push_index.switch_alias(prod, "municipal_code_2026-03-18")
    with pytest.raises(SystemExit):
        push_index.drop(prod, "municipal_code_2026-03-18")


# --- what the app reads ---------------------------------------------------------------------

def test_the_app_reads_the_alias_and_the_vintage_names_its_collection():
    from backend.code_vintage import get_code_vintage, get_code_vintage_record
    from backend.config import Settings

    assert Settings.model_fields["qdrant_code_collection"].default == CODE_ALIAS
    record = get_code_vintage_record()
    assert record["collection"] == collection_for(record["current_through"])
    assert set(get_code_vintage()) == {"current_through", "label", "source"}  # bookkeeping stays out of chat/API
