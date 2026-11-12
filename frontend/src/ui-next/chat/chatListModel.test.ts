import { describe, expect, it } from "vitest";
import type { Conversation } from "../../lib/types";
import { groupChats } from "./chatListModel";

const NOW = new Date(2026, 10, 12, 15, 0).getTime();
const at = (daysAgo: number, title: string): Conversation => ({ id: title, title, message_count: 2, createdAt: 0, updatedAt: NOW - daysAgo * 86_400_000 });

describe("the chat list", () => {
  it("puts the latest first under Today, Yesterday, Previous 7 days, Previous 30 days, Older", () => {
    const g = groupChats([at(40, "e"), at(0.1, "a"), at(1, "b"), at(3, "c"), at(12, "d"), at(0, "a2")], NOW);
    expect(g.map((x) => [x.key, x.chats.map((c) => c.title)])).toEqual([
      ["today", ["a2", "a"]], ["yesterday", ["b"]], ["week", ["c"]], ["month", ["d"]], ["older", ["e"]],
    ]);
  });
  it("searches titles by every word typed", () => {
    const g = groupChats([at(0, "Zoning at 2541 N Spaulding"), at(0, "Crime around Spaulding"), at(0, "Coach house")], NOW, "spaulding zon");
    expect(g.flatMap((x) => x.chats.map((c) => c.title))).toEqual(["Zoning at 2541 N Spaulding"]);
  });
});
