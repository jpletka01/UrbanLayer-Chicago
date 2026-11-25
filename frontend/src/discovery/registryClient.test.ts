import { beforeEach, describe, expect, it, vi } from "vitest";
import { REG } from "./_fixtures";

vi.mock("../lib/api", () => ({ fetchDiscoveryRegistry: vi.fn() }));

import { fetchDiscoveryRegistry } from "../lib/api";
import { _resetCache, isStale, loadRegistry } from "./registryClient";

const mockFetch = vi.mocked(fetchDiscoveryRegistry);

beforeEach(() => {
  _resetCache();
  localStorage.clear();
  mockFetch.mockReset();
  mockFetch.mockResolvedValue(REG);
});

describe("registryClient", () => {
  it("fetches once then serves from cache", async () => {
    expect(await loadRegistry()).toEqual(REG);
    expect(await loadRegistry()).toEqual(REG);
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it("force refetches (staleness path)", async () => {
    await loadRegistry();
    await loadRegistry(true);
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it("isStale compares the cached version", async () => {
    await loadRegistry();
    expect(isStale("v1")).toBe(false);
    expect(isStale("v2")).toBe(true);
  });

  it("falls back to cache on fetch failure", async () => {
    await loadRegistry();
    mockFetch.mockResolvedValueOnce(null);
    expect(await loadRegistry(true)).toEqual(REG);
  });
});
