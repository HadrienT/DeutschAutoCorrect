import { describe, expect, it } from "vitest";
import type { DetectedError, Segment } from "../api/types";
import { groupByCategory, needsReview, nextError, wordsOfError } from "./errors";
import { clamp, fmtNum, formatTime, seekWindow } from "./time";

const err = (o: Partial<DetectedError>): DetectedError => ({
  id: "e", category: "grammar", subtype: "case", severity: "minor", segment_id: "s1", start: 1, end: 2,
  heard: "", expected: "", explanation: "", confidence: 0.8, source: "llm", status: "pending", note: "", ...o,
});

describe("time", () => {
  it("formats", () => {
    expect(formatTime(83.4)).toBe("01:23");
    expect(formatTime(5.25, 1)).toBe("00:05.3");
    expect(formatTime(-3)).toBe("00:00");
    expect(fmtNum(13.5)).toBe("13,5");
  });
  it("clamps seek window", () => {
    expect(seekWindow(0.2, 1, 10)[0]).toBe(0);
    expect(seekWindow(9.8, 9.9, 10)[1]).toBe(10);
    expect(clamp(5, 0, 3)).toBe(3);
  });
});

describe("errors", () => {
  it("groups and sorts", () => {
    const g = groupByCategory([err({ id: "b", start: 5 }), err({ id: "a", start: 2 }), err({ category: "vocabulary" })]);
    expect(g.grammar.map((e) => e.id)).toEqual(["a", "b"]);
    expect(g.vocabulary).toHaveLength(1);
    expect(g.pronunciation).toHaveLength(0);
  });
  it("navigates with wrap-around", () => {
    const es = [err({ id: "a", start: 1 }), err({ id: "b", start: 4 })];
    expect(nextError(es, 0, 1)?.id).toBe("a");
    expect(nextError(es, 1, 1)?.id).toBe("b");
    expect(nextError(es, 4, 1)?.id).toBe("a");
    expect(nextError(es, 4, -1)?.id).toBe("a");
    expect(nextError(es, 0.2, -1)?.id).toBe("b");
  });
  it("flags low confidence pending only", () => {
    expect(needsReview(err({ confidence: 0.3 }))).toBe(true);
    expect(needsReview(err({ confidence: 0.3, status: "confirmed" }))).toBe(false);
  });
  it("maps errors to words", () => {
    const seg = { words: [{ start: 0, end: 1 }, { start: 1, end: 2 }, { start: 2, end: 3 }] } as Segment;
    expect(wordsOfError(seg, err({ start: 0.9, end: 2.1 }))).toEqual([0, 1, 2]);
    expect(wordsOfError(seg, err({ start: 1.1, end: 1.9 }))).toEqual([1]);
  });
});
