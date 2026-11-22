// A page's chunk, loaded on demand, reloading once when the chunk can't be downloaded (Sentry JAVASCRIPT-REACT-6).
// A tab left open across a deploy still runs the old build, whose hashed page chunks the new image no longer has;
// with no error boundary the failed import blanked the whole app. One reload fetches the new build. A second
// failure in a row throws as before, so a chunk that is really missing can never loop reloads.

const RELOADED = "ul_page_chunk_reload";

/** The browsers' words for a dynamic import that couldn't be fetched (Chrome, Firefox, Safari). */
const CHUNK_FAILED = /dynamically imported module|Importing a module script failed/i;

function isChunkLoadError(err: unknown): boolean {
  return err instanceof Error && CHUNK_FAILED.test(err.message);
}

export function loadPage<T>(importer: () => Promise<T>, reload: () => void = () => window.location.reload()) {
  return async (): Promise<T> => {
    try {
      const mod = await importer();
      try {
        sessionStorage.removeItem(RELOADED);
      } catch {
        // storage blocked: nothing to clear
      }
      return mod;
    } catch (err) {
      if (!isChunkLoadError(err)) throw err;
      try {
        if (sessionStorage.getItem(RELOADED) !== null) throw err;
        sessionStorage.setItem(RELOADED, "1");
      } catch {
        // tried once already, or storage blocked (no way to stop a loop): fail as before
        throw err;
      }
      reload();
      // The page is reloading: keep the frame's outline (the Suspense fallback) until it does.
      return new Promise<T>(() => {});
    }
  };
}
