# Spanish: the English-only backlog translated

Format: see `README.md` in this folder.

---

## Item 1: the 289 keys listed in `_untranslated.json` are now Mexican Spanish, usted (2026-10-30)

**Decision:** every key that `frontend/src/locales/es/_untranslated.json` listed (data 59, pages 91, chat 41, common 98) now has a Spanish string, and the list is empty. The file stays, with empty lists, because the convention for a new string is still "English text in `es` plus its key in the list" until it is translated.

- **Register and vocabulary.** Formal *usted* and Mexican vocabulary, as decided on 2026-10-29: *departamento* (not *apartamento*), *recámara*, *renta*, *Tasador* for the County Assessor, *Concejo Municipal*, *Secretaría Municipal*, *tramo censal*, *Ficha*, *parcela*. These follow terms the catalogs already used, so a reader meets one word per idea.
- **Sentence fragments.** The "Since this answer" lines (`chat:sinceThen.*`) are joined to a heading by the code, so each Spanish fragment starts in lower case and the layer names carry their own indefinite article (*una calle peatonal*). `{{what}}` in the landmark text is "name (record)" or the record alone, so the sentence is built around *El Concejo aprobó {{what}}* and works for either.
- **Guarded.** `i18n.parity.test.ts` (same keys and placeholders as English), `untranslated.test.ts` (the list is honest) and `PageHeader.nav.test.ts` (nav strings fit) pass. `dataDates.test.ts` pinned the English words in Spanish and now expects *Delitos hasta …*.
- **Not decided here:** the report's own catalog (`backend/report_i18n.py`) has `dates.*` and other English strings in its Spanish block; that is a separate list. The chat synthesizer's Spanish answers are unchanged.

**Revisit if:** a native Mexican-Spanish reader finds a legal-sounding string wrong. The ones to read first are the disclaimers (`data:regulatory.pendingText.disclaimer`, `data:regulatory.upcoming.disclaimer`) and the landmark review text (`pages:scorecard.landmarkDesignation.review`).

**Numbers**
- **Before:** 289 keys English in Spanish mode (59 / 91 / 41 / 98).
- **After:** 0. Frontend tests 698 passed, `tsc -b` clean, backend locale-linked tests 20 passed.
- **Not measured:** a native read-through. These are my translations, checked for placeholders, register and glossary, not by a Spanish speaker.
- **Reproduce:** `cd frontend && npx vitest run`.

## Item 2: the $25 report's Spanish catalog (2026-10-30)

**Decision:** translate every key in `backend/report_i18n.py`'s `_UNTRANSLATED_ES` (139 keys: `conf.*` confidence captions and the Data Sources table, `dates.*` cover dates, `cover.*`, `currency.*` how-current-the-law block, landmark-designation and passed-rezoning notices, the FEMA "not checked" strings, the TOD-street note) into Mexican Spanish, usted, and leave the set empty. Also: the report's `<html lang>` now follows the language (`es-MX`), and the document `<title>` is translated (`doc.title`, `doc.untitled`).

**Alternatives and calls:**
- **Reuse the Profile's wording, not fresh translations.** Every `conf.*` and `dates.*` string that has a frontend twin (`common.json` `confidence.*`, `dataDates.*`) copies its Spanish exactly, so a reader sees the same words in the Profile and the PDF. A new test (`test_the_spanish_frontend_wording_matches_the_spanish_backend_catalog`) pins the `dates.*` pair the way the English one already was.
- **"Departamento de Planificación y Desarrollo"**, the name the frontend already uses, not *Planeación* (the more Mexican word): one name for one department across the product beats the regional preference. A native reader may prefer to switch both.
- **`currency.vintage` / `currency.list_heading` use a colon before `{label}`** ("vigente hasta: {label}"). The label is a data field from `backend/code_vintage.json` ("Council Journal of June 17, 2026", English), so a Spanish article ("hasta la …") would agree with an English noun. Translating the label is a data change, left out.
- **`html lang`**: WeasyPrint hyphenates by `lang`, so an English tag on a Spanish report was a typographic bug as well as an accessibility one.
- **The tests that pinned "English until translated"** (`test_report_sources_table.py` ×2, `test_data_dates.py`, `test_flood_unchecked.py`, `test_legislation_currency.py`) now assert the Spanish text and that the English is gone.

**Still English in a Spanish report (found by rendering the mock report in Spanish, not fixed here):** the Data Sources table's source names and "Used for" figure labels come from the source registry and `provenance.FACTS` (English data, ~84 sources and ~100 facts, shared with the Profile, which translates them in the frontend by id); the code-amendment summaries come from the hand-review file `backend/code_amendments.json`; the code-vintage label above. Each needs a keyed Spanish source, not a catalog line.

**Revisit if:** a native reader changes a term (change the frontend twin in the same PR, or the parity test fails), or a new report string lands (it must arrive translated; the set should stay empty).

**Numbers**
- **Before → after:** `_UNTRANSLATED_ES` 139 → 0 keys (2026-10-30).
- **Tests:** backend unit suite 2,483 passed, 66 deselected (`.venv/bin/python -m pytest backend/tests/ -q -m "not integration"`); `ruff check backend` clean.
- **Reproduce the count:** `.venv/bin/python -c "from backend import report_i18n as r; print(len(r._UNTRANSLATED_ES))"`.
- **Not measured:** a native read-through; a real PDF render in Spanish (only the HTML was rendered, from the mock report).
