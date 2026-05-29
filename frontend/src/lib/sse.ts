// Parse a `text/event-stream` body into typed JSON payloads.
// Splits on the SSE record separator (\n\n), strips the `data:` prefix, and
// JSON-parses each payload. Malformed payloads are warned and skipped.
export async function* parseSSE<T>(
  reader: ReadableStreamDefaultReader<Uint8Array>,
): AsyncGenerator<T, void, unknown> {
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const evt of events) {
      const line = evt.trim();
      if (!line.startsWith("data:")) continue;
      const payload = line.slice(5).trim();
      if (!payload) continue;
      try {
        yield JSON.parse(payload) as T;
      } catch (err) {
        console.warn("Bad SSE payload", payload, err);
      }
    }
  }
}
