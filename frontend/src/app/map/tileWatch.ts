// Did an opt-in tile layer actually arrive? (Item 136.) Satellite asks Cook County's image server for every tile; when
// that server doesn't answer (2026-11-22 it reset every connection), MapLibre only logs the failures and the map looks
// unchanged, so a click on Satellite seemed to do nothing. The watch says "failed" once several tiles have failed with
// none arriving, or once nothing has arrived for a while; a single bad tile among good ones never counts.

export interface TileWatch {
  /** A tile of the layer failed to load. */
  error(): void;
  /** A tile of the layer arrived: the layer works, the watch ends. */
  loaded(): void;
  /** Stop watching (the layer was switched off). */
  stop(): void;
}

export const TILE_WATCH = { minErrors: 3, timeoutMs: 12_000 } as const;

export function watchTiles(onFail: () => void, opts: { minErrors?: number; timeoutMs?: number } = {}): TileWatch {
  const minErrors = opts.minErrors ?? TILE_WATCH.minErrors;
  let errors = 0;
  let done = false;
  const finish = (failed: boolean) => {
    if (done) return;
    done = true;
    window.clearTimeout(timer);
    if (failed) onFail();
  };
  const timer = window.setTimeout(() => finish(true), opts.timeoutMs ?? TILE_WATCH.timeoutMs);
  return {
    error: () => { if (!done && ++errors >= minErrors) finish(true); },
    loaded: () => finish(false),
    stop: () => finish(false),
  };
}

/** The zoom where a group of the map first has anything to draw, when the map sits below it ("Zoom in to see"). */
export function belowMinZoom(zoom: number | null | undefined, minZoom: number | null | undefined): boolean {
  return zoom != null && minZoom != null && zoom < minZoom;
}
