

// Each chunk's text begins with a multi-line location header
// ("CHICAGO MUNICIPAL CODE\nTitle 17 — …\n§ …") followed by a blank line and
// then the body. For compact previews we want just the body.
export function stripHeader(text: string): string {
  const parts = text.split("\n\n");
  return parts.length > 1 ? parts.slice(1).join("\n\n").trim() : text.trim();
}
