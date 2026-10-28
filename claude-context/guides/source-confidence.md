# Source confidence standard

**Status (2026-10-20): ADOPTED.** This is the rule every figure UrbanLayer shows must follow, on the Property Profile, in chat and in the $25 report. The schema and UI that enforce it are being built in stages (see "Rollout" at the bottom). Until a stage lands, new work still follows the rule by hand.

**Owner:** the confidence workstream (WS0). It owns the tier definitions, the entry schema (`backend/provenance.py`), the method keys, the thresholds and the caption element. Other work may add fact specs and registry sources, but changing what a field means or a threshold needs a WS0 review.

## Why

A number with no source, date or precision asks to be trusted. A number that says who published it, how old it is, how much of the area it covers, how precise it is and how it was made can be checked. Government records go first. When a figure rests on too little data we fade it or withhold it, and a withheld figure always says why.

## 1. Authority tiers

| Tier id | Letter | Plain name (on the page) | Meaning | Examples |
|---|---|---|---|---|
| `official_record` | A | "City/County record" | The government's system of record | Zoning and overlay layers; Assessor values, sales, characteristics, appeals; Address Points; permits, violations, 311, crime; FEMA; EPA; HUD OZ/QCT; CTA/Metra GTFS; CHRS (1996, still legally in force) |
| `official_publication` | B | "Municipal Code text" | Government text as published, with a lag | American Legal code text; our Title 17 table (`zoning_definitions.py`), parity-tested against that text |
| `official_estimate` | C | "Census survey estimate" / "{agency} model" | A government statistic with error, or a government model | ACS (tract, community area); ptaxsim tax bills; Assessor modeled rents; HUD SAFMR |
| `our_calculation` | D | "Our calculation" | Deterministic math on A–C that we can show | Unit yield, FAR used, verdict, effective rate, class norm, comps medians, bracket medians, violation categories, benchmarks |
| `ai_extracted` | E | "Read by AI" | An LLM reading official text | Report setbacks, permitted/special uses, notes; chat answers (already cited) |
| `non_government` | F | "{name} (private company)" | A commercial or community source | Walk Score; Mapbox basemap |

- **A calculation is never stronger than its weakest input.** A tier-D figure lists its `inputs` (fact ids) and carries `basis_tier`, the weakest input's tier. The report's buildable footprint is D on E, because it is drawn from AI-read setbacks. FAR used is D on A, or D on a 2015 footprint when that is where the building area came from.
- **A conduit doesn't change the tier.** A figure fetched through Census Reporter or packaged by ptaxsim is still the Census Bureau's or the County's.
- **A figure's tier can be lower than its source's tier.** A recorded figure carries its source's tier (a test asserts they match). A calculation on that source is D, and an AI reading of it is E.
- **Use tier F only where nothing official exists, and always label it.** Walk Score stays, labeled "(private company)". The EPA National Walkability Index (federal, block group) is a candidate replacement.

## 2. The five fields

Each provenance entry answers five questions. The schema fields marked **new** arrive with schema v2. Every new field is additive and optional on the TypeScript `Provenance` type.

| Question | Schema fields | Notes |
|---|---|---|
| 1. Who published it? | `tier`, `source_id`, `source` (publisher + dataset) | `source_id` is the join key into the data-health registry (§5) |
| 2. How old is it? | `as_of`, **`as_of_basis`**, **`period`**, `effective_date`, `query_date`, **`age_days`** | `as_of_basis` says what the date means (below) |
| 3. How much does it cover? | **`scope`**, **`geography`**, **`coverage`** `{n, share, universe, unit}` | `scope` ∈ `parcel` · `address` · `radius` · `tract` · `community_area` · `city` · `county`. `coverage: null` on a parcel record means "not applicable", not "unknown" |
| 4. How precise is it? | **`precision`** `{moe, moe_level: 0.90, cv}`, or for AI readings `{agreement: {n, agree}}` | `null` means none is published, and the page says so |
| 5. How was it made? | **`method_key`**, **`method_params`**, **`method`** (English fallback) | Same id/params/text pattern as coverage notes, so the UI translates by key |
| Derived | **`confidence`** ∈ `standard` · `low` · `withheld`, plus **`confidence_reasons`** | Computed once in `provenance.py`. Every surface reads it; none recomputes it |
| Snapshot | **`value`** (the figure as displayed, a JSON scalar) | Makes the provenance map a self-contained fact snapshot that data health can diff later |

### Dates mean different things
- `query_date`: when we asked.
- `as_of` + `as_of_basis`: when the source says it is current. `as_of_basis` is one of:
  - `source_updated`: the dataset was last updated then;
  - `record_updated`: one record last changed then (a zoning district's map edit). It says nothing about the dataset's currency, so it never triggers `old_source`;
  - `current_through`: code text current through that date;
  - `period_end`: the end of a statistic's period (an ACS 5-year ends Dec 31 of its last year);
  - `vintage`: a frozen survey;
  - `tax_year`;
  - `queried`: a live record, where we only know when we asked.
- `effective_date`: when a rule took effect (an ordinance date).
- **Precedence for `as_of`:**
  1. a date the response carries (zoning `map_updated`, the ACS release, the tax year);
  2. the data-health store's latest check for the `source_id` (`content_through`, else `published_at`);
  3. the registry's frozen vintage;
  4. `query_date`, with basis `queried`.
- The Profile footer's date is a **check date**, not a data date, and is labeled "Checked". The `data_as_of` field keeps its name, because stored conversations and `TurnSummary` use it.

### Method keys
The vocabulary is fixed. New keys go through a WS0 review.

| Key | Meaning |
|---|---|
| `recorded` | Read as-is from a system of record |
| `published_text` | Quoted from published code text |
| `code_table` | Our Title 17 table, parity-tested against the code |
| `hand_reviewed` | An ordinance passed but not yet in the published code, read by us |
| `survey_estimate` | A Census survey estimate |
| `government_model` | A government agency's model (Assessor, HUD) |
| `bracket_median` | A median interpolated from published brackets |
| `calculation` | Deterministic math on other facts |
| `keyword_grouping` | Our grouping of free text into categories |
| `ai_read_code` | Read by AI from Municipal Code text |
| `ai_read_ordinance` | Read by AI from a scanned ordinance |
| `ai_read_filing` | Read by AI from an applicant's filing |
| `commercial_index` | A private company's index |

### ACS precision
- SE = MOE ÷ 1.645; CV = SE ÷ estimate. Proportions use the Census ratio formula from the ACS Handbook, unit-tested against its published examples.
- A top-coded median (B19013's $250,001) is shown as "$250,000+" with no CV.
- Keep the release id and MOE the API returns. Never discard them.

### Example entries
```jsonc
"area.tract.median_gross_rent": {
  "label": "Median gross rent", "tier": "official_estimate",
  "source_id": "census.reporter.acs", "source": "U.S. Census Bureau, ACS 5-year (via Census Reporter)",
  "value": 2435, "scope": "tract", "geography": "Census Tract 8310",
  "as_of": "2024-12-31", "as_of_basis": "period_end", "period": "2020–2024",
  "coverage": null, "precision": {"moe": 220, "moe_level": 0.9, "cv": 0.055},
  "method_key": "survey_estimate", "method": "Census survey estimate",
  "confidence": "standard", "confidence_reasons": [], "query_date": "2026-10-20"
}
"property.stories": {
  "label": "Stories", "tier": "official_record", "source_id": "chi.building_footprints",
  "source": "City of Chicago Building Footprints", "value": 3, "scope": "parcel",
  "as_of": "2015-08-14", "as_of_basis": "source_updated",
  "method_key": "recorded", "confidence": "standard", "confidence_reasons": ["old_source"]
}
"zoning.rear_setback_ft": {   // report only
  "label": "Rear setback", "tier": "ai_extracted", "source_id": "artifact.zoning_cache",
  "section": "17-3-0400", "value": 30, "as_of": "2026-03-18", "as_of_basis": "current_through",
  "method_key": "ai_read_code", "method_params": {"section": "17-3-0400"},
  "confidence": "low", "confidence_reasons": ["ai_unverified"]
}
```

## 3. Confidence states and thresholds

| State | Rule | Display |
|---|---|---|
| `withheld` | coverage share < **10%**, or n < **30**, or CV > **50%** | The value is replaced by "—" and a sentence saying why. It is never silently dropped. It is also removed before it reaches the chat model or the PDF |
| `low` | coverage share < **25%**, or CV > **30%**, or a method rule below | The value is faded, and its caption starts with "Low confidence ·". Bars and fills are hatched |
| `standard` | otherwise | Normal |

The constants live in one place, `provenance.py`: `HIDE_COVERAGE_BELOW = 0.10`, `FADE_COVERAGE_BELOW = 0.25`, `FADE_CV_ABOVE = 0.30`, `HIDE_CV_ABOVE = 0.50`, `HIDE_N_BELOW = 30`. Boundary tests pin them.

**Where each rule applies:**
- **n < 30 applies only to sample-based area statistics:** Assessor modeled rents, Discovery benchmarks, any "median of a sample". It never applies to lists where every record is shown.
- **Comps have their own rule:** fade the median under **5** sales, and withhold it under **3**. The list of sales always shows. A ¼-mile comp set usually has 5–20 sales, so the general n < 30 rule would hide the comps KPI on most parcels.
- **Coverage applies only where a share can be measured:** partial-universe sources, such as the Assessor model (buildings of 7+ units) or the Discovery index (sparse land area). ACS is a designed sample of the whole population, so its coverage is complete by design and its CV carries the uncertainty. ACS publishes no per-tract n, so the n rule doesn't apply to it either.
- **Method rules that don't depend on numbers:**
  - A bracket median with no published error is `low`. This covers the community-area income median: 5 brackets, a $50k-wide $75–125k bracket and a capped top bracket.
  - An AI-read value is `low` (reason `ai_unverified`) until it is corroborated, either by a deterministic check that agrees or by a measured agreement of **≥ 95% on ≥ 30** hand-checked items. This covers report setbacks today and ordinance districts and filings later. The report keeps the envelope map, with its caption.
- **Stricter existing gates stay.** The area benchmark already requires n ≥ 50.

Reason codes (for `confidence_reasons`): `low_coverage`, `small_sample`, `high_cv`, `bracket_median`, `ai_unverified`, `old_source` (dataset more than 24 months old), `stale` (data health reports the source `warn`/`alarm`).

## 4. Display rules

1. **Quiet by default.** A visible caption appears only when one of these holds:
   - the tier is C, D, E or F;
   - the state is `low` or `withheld`;
   - the *source dataset* is more than 24 months old.

   An official record or code text about the parcel in a `standard` state shows no caption. Its five fields go in the label's existing tooltip. That keeps the de-carded Profile clean and points skepticism where it belongs.
2. **Source age is not event age.** A 2014 sale in a monthly-updated sales feed gets no caption. A stories figure from a dataset last updated in 2015 always does.
3. **A withheld figure is never silent.** For example: "Not shown: the Assessor models 293 units here, about 5% of renter households (needs 10%)."
4. **Name the method in words on the page** for every captioned figure, not only in a tooltip. This is an exception to the Profile's tooltip rule (`frontend/CLAUDE.md`: explainers live in tooltips): a one-line confidence caption counts as on-page content, like the module takeaway sentences.
5. **Never blend series silently.** One entry per series, each named (ACS vs. Assessor model vs. HUD). Never put two vintages side by side unlabeled.
6. **Area figures name their scope:** tract 8310, Brighton Park, ¼ mi. The Neighborhood module header already says the area is "not this parcel". The caption carries the finer scope.
7. **Caption styling:** at most one line at desktop width, `text-caption`/`text-micro`, muted, with amber only for a caveat (`stale`). The same styling is used for data health's "Couldn't check today" and "Answered on <date> / since then".
8. **Maps:** `low` features get half fill alpha and a dashed outline. `withheld` features aren't drawn, and the legend gives their count. Test a hatch pattern (deck.gl `FillStyleExtension`) in interleaved `MapboxOverlay` mode before using it, because aggregation layers didn't render there.
9. **Chat:** `withheld` figures never reach the model. Only `period`/`moe` ride in the model's context, not the whole provenance map. The sources footer is deterministic.

## 5. Source ids

- `source_id` is the **data-health registry id** (`backend/data_health/registry.py`). There is no separate source table here.
- Ids are dotted lowercase slugs: `<publisher>.<dataset>[.<sub>]`. Examples: `chi.zoning.districts`, `chi.zoning.overlay.<layer_type>`, `chi.building_footprints`, `cook.assessor.values`, `code.municipal_text`, `census.reporter.acs`. Our own committed artifacts use `artifact.<name>` (`artifact.zoning_cache`).
- Until the registry file exists, the registry plan's slugs are the contract. When it lands, a parity test checks that every `FACTS[fact].source_id` resolves.
- **Retired sources stay in the registry** as frozen/retired (for example `kn9c-c2s2`, the 2008–2012 community-area poverty and unemployment set), so old answers still resolve.
- **Mapping goes one way.** A fact names its source (`FACTS[fact].source_id`, plus `alt_source_ids` for other sources that can supply the same recorded figure and `input_source_ids` for sources it is computed or located from). A test checks that every one of them lists the fact in the registry's `fact_keys`, and that a registry source listing a fact we model is one the fact names.
- **Static facts are split by owner:**
  - per-figure specs (`FACTS: fact_id → label, source_id, method_key, scope`) live in `provenance.py`;
  - per-source facts (publisher, tier, frozen vintage, displayed label, refresh cadence) live in the registry;
  - dynamic facts (ACS release, MOE, tax year, map edit date) come from the retrieval models, which must pass them through rather than drop them.
- **Fact ids are a stable contract.** A rename ships with a migration map in `provenance.py`, because stored answers and reports reference them.

## 6. Who owns what

| Mechanism | Owns | Granularity |
|---|---|---|
| **Coverage notes** (`backend/retrieval/coverage_notes.py`) | Where the analysis stops: what the Profile does *not* cover (PDs, landmarks, the map's lag, the alderman's role, the official letter) | Page level |
| **Confidence** (this standard, `backend/provenance.py`) | How far to trust one figure: its source, date, coverage, precision, method and state | Figure level |
| **Resolution** (the hero's resolution badge; `guides/parcel-resolution-truth-model.md`) | Whether we found the right parcel | Parcel identity |
| **Data health** (WS6, `backend/data_health/`) | Whether a source is fresh and answering today: staleness, alarms, "since then" | Source level |

Confidence computes only `age_days` and the static 24-month display rule. Staleness belongs to data health: when it reports a source `warn`/`alarm`, the caption shows that source's date in amber (reason `stale`).

## 7. How it fits the existing provenance map

- **Same function, keys, wire location and consumers.** `build_provenance()` still returns `{fact_id: entry}` on `ScorecardResponse.provenance` and through `_provenance_for(context)` in chat. Every existing fact id keeps its id and fields. The Zoning card's § source buttons, `chat_sources.build_sources_footer` and `citations.provenance_keys` keep working.
- **`kind` stays for one release, derived from `tier`:** `official_record` → `official_record`, `official_publication` → `code_text`, anything else → `derived`. It is removed once nothing reads it.
- **`_entry()` becomes a typed `ProvenanceEntry`** (pydantic, dumped to the same dict), so tests enforce the schema.
- **Area statistics get entries on every path:** crime, 311, permits, area violations, businesses, vacant buildings, food inspections, ACS tract and community area, including on chat turns with no parcel.
- **Stored with each chat answer.** `ContextObject.provenance` is set once, server-side, when the answer is assembled, and saved in `messages.context_json`. It is excluded from what the synthesizer sends the model. A reopened answer keeps the dates it was given. It is a stored field, not a computed one: recomputing later would pick up newer dates.

## 8. Adding a figure: checklist

1. **Name the fact.** Pick a stable dotted fact id (`area.tract.median_gross_rent`) and add a spec to `FACTS` in `provenance.py`: label, `source_id`, `method_key`, `scope`.
2. **Register the source.** Make sure its `source_id` exists in the data-health registry, with publisher, tier and cadence. Add it if not.
3. **Pick the tier** (§1). Is it a record, code text, a government estimate, our math, an AI reading or a private source? For math, list `inputs` and set `basis_tier`.
4. **Carry the date.** Pass through whatever date the response gives, and set `as_of_basis`. Don't fall back to the query date if the source states one.
5. **Carry coverage and precision.** Keep MOE/release ids from the API. Set `coverage {n, share, universe, unit}` where a share is measurable.
6. **Let `provenance.py` decide the state.** Never compute `low`/`withheld` in a component, prompt or template.
7. **Display it by the rules** (§4): no caption for a standard parcel record; a one-line caption naming the method otherwise; "—" plus a reason when withheld.
8. **Strings:** a new `es` key gets the English text and its key path in `frontend/src/locales/es/_untranslated.json` (the vitest guard in `frontend/src/locales/untranslated.test.ts` checks it). Backend report strings use an `_UNTRANSLATED_ES` set in `report_i18n.py`, with a pytest guard; the first PR that adds an untranslated backend string adds that set and its guard.
9. **Test it:** the entry validates against `ProvenanceEntry`, its `source_id` resolves, and threshold boundaries are pinned if the figure can be faded or withheld.
10. **Don't bypass the gates.** If a figure is `withheld`, it must not reach the chat context or the PDF by another route. In chat that means a place for it in `provenance._clear_figure` (a test pins every figure the rules can withhold).

## Rollout
Status 2026-10-21: step 3 (schema v2) is in `backend/provenance.py`: `ProvenanceEntry`, `make_entry()`, `confidence_state()`, `FACTS`, `resolve_as_of()`. The nine existing fact kinds are upgraded; the UI doesn't read the new fields yet (step 5).

Status 2026-10-21: step 4 (capture) is in: ACS margins of error and release ids, comp basis, the commercial-valuation year, the benchmark's coverage and build date, the class norm's tax year. `backend/provenance_figures.py` builds an entry for every Profile figure and every area feed (about 60 per Profile); `expected_fact_ids(payload)` is the declared list of what a payload must carry, checked by `test_confidence_coverage.py` over the 12 recorded kit payloads and by `python -m eval.confidence_audit`. Source dates resolve through `data_health.status.latest()`, then the registry's frozen vintage.

Status 2026-10-21: step 5 (display) is in. `frontend/src/lib/confidence.ts` decides what a caption says (`wantsCaption` is the default-quiet rule; `captionParts`, `sourceBullets`, `plainCaption`), `components/ui/Confidence.tsx` renders it (`ConfidenceCaption`, `ConfidenceValue`, `SourceTooltip`, `MethodCaption`), and `lib/provenanceContext.ts` hands the Profile's map to any card (`useFact(id)`). The frontend never recomputes the state; it only copies the thresholds' minima for the "needs N" text (a backend test pins them). Adopted in the KPI strip, Zoning (FAR used), Property, Comparables, Violations, Regulatory, Incentives and the Area block, and in the CSV export. Chat, the sidebar and the report are steps 6 and 7. The caption supports `unavailable` (data health); `stale` (amber) waits for the entry to carry it.

Status 2026-10-22: step 6 (the report) is in. `backend/report_provenance.py` builds the report's provenance (the Profile's plus the AI-read setbacks, uses, special uses, parking and notes from the zoning cache, tier E with the code section and "not verified", and the buildable envelope as our calculation built on them), renders the same quiet-by-default captions (`caption()` mirrors `frontend/src/lib/confidence.ts`) and builds the Data Sources table from the entries (`sources_rows()`, one row per source actually used, strongest authority first; no static rows). `render_report_html` binds it; a failure to build it leaves the captions quiet and never stops the report. AI labels appear only where the cache holds AI-read data for the district (a B/C/D district has setbacks; a residential one often has only notes; a district served from the Title 17 table has none and the report claims none). Keys: `conf.*` in `report_i18n.py`, `es` carries English and is listed in `_UNTRANSLATED_ES`.


Status 2026-10-22: step 7 (chat) is in. On every chat turn `main._event_stream` builds the turn's provenance (`_provenance_for` now covers parcel-less turns: crime, 311, permits, census tract, community area) and calls `provenance.withhold_low_evidence(context, provenance)`, once, before the context reaches the sidebar or the model. A `withheld` figure's value is cleared from the context (`_clear_figure`: a tract field, a comps median, a community-area figure; on a copy, since retrieval results are cached) and listed in `ContextObject.withheld_figures` with its reason in plain words; an estimate, our calculation, AI reading or private index that survives is listed in `ContextObject.figure_notes` (capped at 16) so the model names it as such. `ContextObject.provenance` stores the map (SSE context chunk, `messages.context_json`), and the synthesizer excludes it. Prompt rule 38 asks for the period and margin of any area statistic, "give or take" for a tract estimate, and never a withheld figure. `chat_sources.build_sources_footer` adds one dated line per area source (period or "data through", the 90% margin-of-error level, the bracket-median caveat). The chat rail captions from the stored map (`DataView` wraps its cards in `ProvenanceProvider`): ± margins beside tract figures, a low community-area income in the quieter style, "Not shown: …" for a withheld tract figure, Walk Score as a private company's index, the violation grouping as ours. `python -m eval.tract_confidence` counts how many tract figures the rules fade or withhold. The `make kit` chat run (needs production credits) was not run; see the decision log.


The standard is adopted now; the code catches up in order:
1. This guide.
2. **Stale and empty cleanup:** stop serving the 2008–2012 community-area poverty/unemployment figures and the always-empty community-area fields; fix the report's methodology text; relabel "Data as of" as "Checked"; date the 2015 footprints.
3. **Schema v2:** tiers, the five fields, confidence states and the constants in `provenance.py`; fact specs keyed to registry ids.
4. **Capture metadata:** keep ACS MOE/release ids, record dataset vintages, give every Profile figure an entry, and add an audit script.
5. **`ConfidenceCaption`** and the hatch token, adopted across the Profile.
6. **Report:** AI-read fields labeled, a data-sources table generated from what the report actually used, captions in the PDF.
7. **Chat:** the prompt rule, withheld figures kept from the model, provenance saved with each answer, sidebar captions, area stats in the sources footer.

Community-area poverty, unemployment, income and rent come back only through a tract → community-area aggregation with MOE (the rents/market workstream). Until then the Profile shows no demographics.

**WS4 PR1 (2026-10-28):** the tract -> community-area aggregation was tested (`eval/rent_method.py`, decision Item 33): overall community-area rent can be rebuilt from summed bracket counts with a derived margin (75 of 77 areas `standard`); rent by bedroom cannot (the table tops out at "$1,500 or more"), so bedrooms come only from the Census's published tract and PUMA medians. Nothing is served yet.
