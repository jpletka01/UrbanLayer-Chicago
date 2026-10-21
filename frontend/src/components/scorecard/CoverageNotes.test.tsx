import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { CoverageNotes } from "./CoverageNotes";
import type { CoverageNote } from "../../lib/types";
import { currency } from "./amendments.fixtures";

afterEach(cleanup);

const n = (id: string, applies: "parcel" | "general", text: string, params: CoverageNote["params"] = {}, link: string | null = null): CoverageNote =>
  ({ id, applies, text, params, link, section: null });

const general = [
  n("aldermanic", "general", "alderman en"),
  n("map_lag", "general", "map lag en"),
  n("code_vintage", "general", "vintage en", { date: "2026-03-18" }),
  n("official_letter", "general", "letter en", { fee: 150, days: 30, checked: "2026-09-30" }, "https://www.chicago.gov/letter"),
];

describe("CoverageNotes — what this page doesn't cover (V4)", () => {
  it("leads with what was found on THIS parcel (kit P4: a Planned Development, with its ordinance link)", () => {
    render(
      <CoverageNotes
        notes={[n("planned_development", "parcel", "pd en", { name: "Planned Development 835" }, "https://gisapps.chicago.gov/gisimages/zoning_pds/PD835.pdf"), ...general]}
      />,
    );
    const pd = screen.getByTestId("coverage-planned_development");
    expect(pd.textContent).toContain("Planned Development 835");
    expect(pd.textContent).toContain("do not apply to it");
    expect(pd.querySelector("a")?.getAttribute("href")).toContain("PD835.pdf");
    expect(screen.getByTestId("coverage-parcel").contains(pd)).toBe(true);
    expect(screen.getByTestId("coverage-general").contains(pd)).toBe(false);
  });

  it("states a landmark's approval requirement and a recent rezoning with its date (kit P5, P7)", () => {
    render(
      <CoverageNotes
        notes={[
          n("landmark", "parcel", "x", { name: "Noel State Bank" }),
          n("recently_rezoned", "parcel", "x", { date: "2026-06-16", ordinance: "O2026-0025358" }, "https://chicityclerkelms.chicago.gov/Matter/?matterId=abc"),
          ...general,
        ]}
      />,
    );
    expect(screen.getByTestId("coverage-landmark").textContent).toContain("written approval");
    expect(screen.getByTestId("coverage-landmark").textContent).toContain("Noel State Bank");
    const rz = screen.getByTestId("coverage-recently_rezoned");
    expect(rz.textContent).toContain("2026-06-16");
    expect(rz.textContent).toContain("up to 90 days");
  });

  it("every parcel carries the official-letter note: a screening tool, not a determination", () => {
    render(<CoverageNotes notes={general} />);
    const box = screen.getByTestId("coverage-general");
    expect(box.textContent).toContain("True of every parcel (4)");
    const letter = screen.getByTestId("coverage-official_letter");
    expect(letter.textContent).toContain("not a zoning determination");
    expect(letter.textContent).toContain("$150");
    expect(letter.textContent).toContain("up to 30 days");
    expect(letter.querySelector("a")?.getAttribute("href")).toBe("https://www.chicago.gov/letter");
    expect(screen.queryByTestId("coverage-parcel")).toBeNull();
  });

  it("falls back to the backend's English for a note id it has no translation for", () => {
    render(<CoverageNotes notes={[n("brand_new_note", "parcel", "Something new the backend now says")]} />);
    expect(screen.getByTestId("coverage-brand_new_note").textContent).toContain("Something new the backend now says");
  });

  it("renders nothing without notes (older payloads)", () => {
    const { container } = render(<CoverageNotes notes={undefined} />);
    expect(container.firstChild).toBeNull();
    cleanup();
    expect(render(<CoverageNotes notes={[]} />).container.firstChild).toBeNull();
  });
});

describe("CoverageNotes — how current the code text is (WS1 M3)", () => {
  const sentence = "Municipal Code text: current through the Council Journal of June 17, 2026. Since then City Council has passed 3 amendments to the Zoning Ordinance (Title 17) that are not in this text (checked Oct 20, 2026).";
  const notes = [...general.filter((g) => g.id !== "code_vintage"), n("code_currency", "general", sentence, { count: 3 })];

  it("keeps the currency note out of the collapsed list and puts the amendment list one click away", () => {
    render(<CoverageNotes notes={notes} codeCurrency={currency()} />);
    expect(screen.getByTestId("coverage-currency").textContent).toContain("3 amendments to the Zoning Ordinance");
    expect(screen.getByTestId("coverage-general").contains(screen.getByTestId("coverage-code_currency"))).toBe(false);
    expect(screen.getByTestId("coverage-general").textContent).toContain("True of every parcel (3)");
    const list = screen.getByTestId("coverage-amendments");
    expect(list.querySelector("summary")?.textContent).toBe("Later amendments (3)");
    expect(list.querySelectorAll("li").length).toBe(3);
  });

  it("without the structured currency the note stays in the general list (chat / old payloads)", () => {
    render(<CoverageNotes notes={notes} />);
    expect(screen.queryByTestId("coverage-currency")).toBeNull();
    expect(screen.getByTestId("coverage-general").contains(screen.getByTestId("coverage-code_currency"))).toBe(true);
  });

  it("an unchecked state shows the backend's no-count sentence and still lists uncodified amendments", () => {
    const unknown = currency({ check_state: "unknown", since: null, checked_at: null });
    const note = n("code_currency", "general", "We couldn't check for later amendments recently; the City Clerk's site lists them.", {}, unknown.clerk_url);
    render(<CoverageNotes notes={[note]} codeCurrency={unknown} />);
    const box = screen.getByTestId("coverage-currency");
    expect(box.textContent).toContain("couldn't check");
    expect(box.textContent).not.toMatch(/\bnone\b|\b0 amendments/);
    expect(box.querySelector("a")?.getAttribute("href")).toBe(unknown.clerk_url);
    expect(screen.getByTestId("coverage-amendments")).toBeTruthy();
  });

  it("no list when nothing passed since (fresh check)", () => {
    const none = currency({ since: { title17: 0, cited_other: 0 }, amendments: [] });
    render(<CoverageNotes notes={[n("code_currency", "general", "no amendments since")]} codeCurrency={none} />);
    expect(screen.queryByTestId("coverage-amendments")).toBeNull();
  });

  it("parcel-relevant amendments lead as a parcel note", () => {
    const parcelNote = n("code_amendments_parcel", "parcel", "O2026-0026042 may affect this parcel", { count: 1 }, "https://x.test/ped");
    render(<CoverageNotes notes={[parcelNote, ...notes]} codeCurrency={currency()} />);
    expect(screen.getByTestId("coverage-parcel").contains(screen.getByTestId("coverage-code_amendments_parcel"))).toBe(true);
  });
});
