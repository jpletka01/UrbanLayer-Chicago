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
