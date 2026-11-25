// Item 136: Satellite asked a County image server that reset every connection, and the map only logged it, so the
// Layers button's Satellite seemed to do nothing. The watch turns "no tiles arrived" into a failure the page can show.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TILE_WATCH, belowMinZoom, watchTiles } from "./tileWatch";

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { vi.useRealTimers(); });

describe("watchTiles", () => {
  it("fails once several tiles fail and none arrived", () => {
    const fail = vi.fn();
    const w = watchTiles(fail);
    for (let i = 1; i < TILE_WATCH.minErrors; i++) w.error();
    expect(fail).not.toHaveBeenCalled();
    w.error();
    expect(fail).toHaveBeenCalledTimes(1);
    w.error();
    vi.advanceTimersByTime(TILE_WATCH.timeoutMs);
    expect(fail).toHaveBeenCalledTimes(1);
  });

  it("fails when nothing arrives in time (a server that hangs instead of refusing)", () => {
    const fail = vi.fn();
    watchTiles(fail);
    vi.advanceTimersByTime(TILE_WATCH.timeoutMs - 1);
    expect(fail).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(fail).toHaveBeenCalledTimes(1);
  });

  it("a tile that arrives settles it: later failures and the timer never count", () => {
    const fail = vi.fn();
    const w = watchTiles(fail);
    w.error();
    w.loaded();
    for (let i = 0; i < 10; i++) w.error();
    vi.advanceTimersByTime(TILE_WATCH.timeoutMs * 2);
    expect(fail).not.toHaveBeenCalled();
  });

  it("switching the layer off stops the watch", () => {
    const fail = vi.fn();
    const w = watchTiles(fail);
    w.stop();
    for (let i = 0; i < 10; i++) w.error();
    vi.advanceTimersByTime(TILE_WATCH.timeoutMs * 2);
    expect(fail).not.toHaveBeenCalled();
  });
});

describe("belowMinZoom", () => {
  it("is true only when both are known and the map sits below the layer's first zoom", () => {
    expect(belowMinZoom(10.2, 13)).toBe(true);
    expect(belowMinZoom(13, 13)).toBe(false);
    expect(belowMinZoom(15.5, 13)).toBe(false);
    expect(belowMinZoom(null, 13)).toBe(false);
    expect(belowMinZoom(10, null)).toBe(false);
  });
});
