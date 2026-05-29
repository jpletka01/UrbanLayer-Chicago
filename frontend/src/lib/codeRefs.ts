// Helpers for rendering municipal-code chunks in the sources panel.

// A resolvable section ID looks like "17-1-0500" or "7-28-060.1". Cross-refs
// that are Title/Chapter anchors ("Title17", "Ch.17-2") can't be fetched, so
// only IDs matching this shape become clickable.
const SECTION_ID_RE = /^\d+-\d+-\d+(?:\.\d+)?$/;

export function isResolvableSection(ref: string): boolean {
  return SECTION_ID_RE.test(ref.trim());
}

// Each chunk's text begins with a multi-line location header
// ("CHICAGO MUNICIPAL CODE\nTitle 17 — …\n§ …") followed by a blank line and
// then the body. For compact previews we want just the body.
export function stripHeader(text: string): string {
  const parts = text.split("\n\n");
  return parts.length > 1 ? parts.slice(1).join("\n\n").trim() : text.trim();
}
