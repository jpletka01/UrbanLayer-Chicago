// The Municipal Code text the parcel-kit answer key was built against
// (eval/kit/parcels.json:code_current_through). kitVintage.test.ts fails when the key
// moves, so the About page can't keep quoting an old date after a code refresh.
export const KIT_CODE_CURRENT_THROUGH = "2026-03-18";

export function formatKitVintage(iso: string = KIT_CODE_CURRENT_THROUGH): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
}
