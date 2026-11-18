// Vitest setup: initialize i18next (default "en") so components using useTranslation
// resolve real strings instead of raw keys.
import "./lib/i18n";
import { configure } from "@testing-library/dom";

// findBy*/waitFor give up after 1 s by default. A loaded CI runner (or several suites at once) renders the
// heavier pages (Profile tabs, Discovery, Settings) slower than that, which read as flaky tests that pass
// alone (Phase 12, 2026-11-18). Waits still return as soon as the condition holds, so a passing run is no slower.
configure({ asyncUtilTimeout: 5000 });
