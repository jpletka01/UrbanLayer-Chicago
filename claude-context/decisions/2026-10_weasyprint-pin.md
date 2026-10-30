# weasyprint: capped below 70

Format: see `README.md` in this folder.

---

## Item 1: `weasyprint>=60.0,<70` because 70 misdraws the report's Contents page (2026-10-30)

**Decision:** `requirements.prod.txt` caps weasyprint below 70. Dependabot's #34 proposed raising the floor to 70; that PR is closed instead.

- **Evidence.** The same sample report HTML (`test_data_dates._mock_report()`, English and Spanish, 14 pages each) was rendered with weasyprint 69.0 (installed) and 70.0 (installed into an isolated folder). Page count (14) and the extracted text (`pdftotext`, 2,953 English words and 3,359 Spanish words) are identical. Pixels are identical on 13 of 14 pages at 40 dpi; **page 2, the Contents, differs (about 2% of its pixels)**: with 70 the dotted leader lines between each entry and its page number are drawn displaced downward, leaving stray dotted lines under the list, and the rows sit slightly tighter. The text and page numbers are right; the page looks broken.
- **Why a cap and not a floor bump.** Every line in `requirements.prod.txt` is a `>=` floor with no lock, and the Dockerfile runs `pip install` after copying that file. A cached layer keeps whatever versions were installed at the last cache bust; any bust (an edit to the file, a pruned build cache) installs the newest version of everything. So the existing `>=60.0` already allows 70 on the next bust, and raising the floor to 70 would have forced it. *Alternative:* fix the template's leaders for 70 (`target-counter` and `leader()` rules in `backend/templates/zoning_report.html`); worth doing, but then the report is changed on a PDF we cannot compare against a customer's copy, so that waits for a deliberate comparison.
- **Not decided here:** a lock file for production. Other unpinned packages can move the same way (FastAPI, Anthropic SDK, torch). That is a larger change than this item.

**Revisit if:** the leaders are fixed in the template and the 70-rendered sample matches the 69 one page for page, or a weasyprint 70.x release fixes the leader placement.

**Numbers**
- **Before:** `weasyprint>=60.0`; local environment 69.0; 70.0 renders the Contents page wrongly.
- **After:** capped at `<70`. Merging rebuilds the Docker pip layer (this file changed), which re-resolves every other floor to its newest version: see the PR for what was and was not tested.
- **Production today (measured 2026-10-30, `pip freeze` in the running backend container):** weasyprint 70.0, pydyf 0.13.0, fastapi 0.162.0, anthropic 2.3.0, python-multipart 0.0.32. So the defect is live on the $25 report until this lands. Merging rebuilds the pip layer, which moves weasyprint to the newest below 70 and may also move any other package that has released since the layer was last built; CI's `test` job ran against the resolved set.
- **Not measured:** any other page's rendering under newer fonts; a rendering of a real customer report.
- **Reproduce:** render `backend.main.render_report_html(_mock_report(), "en")` with each version and compare `pdftoppm` pages (see the PR description for the script outline).
