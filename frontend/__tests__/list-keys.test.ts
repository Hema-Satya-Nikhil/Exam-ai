import { stableItemKey } from "@/lib/list-keys";

describe("stableItemKey (React duplicate-key regression)", () => {
  it("gives two items with identical fallback labels unique keys", () => {
    // syllabus_service can emit duplicate "Unassigned line: 0" notes
    const a = stableItemKey("Unassigned line: 0", 0, "unassigned-note");
    const b = stableItemKey("Unassigned line: 0", 1, "unassigned-note");
    expect(a).not.toBe(b);
  });

  it("is deterministic for the same item", () => {
    expect(stableItemKey("Unassigned line: 0", 3, "unassigned-note")).toBe(
      stableItemKey("Unassigned line: 0", 3, "unassigned-note")
    );
  });

  it("prefers the object id when present", () => {
    // id wins over both label and index
    expect(stableItemKey("Same label", 0, "src", 42)).toBe("src:id:42");
    expect(stableItemKey("Same label", 99, "src", 42)).toBe("src:id:42");
    // distinct ids => distinct keys
    expect(stableItemKey("Same label", 5, "src", 43)).toBe("src:id:43");
    expect(new Set(["src:id:42", "src:id:43"]).size).toBe(2);
  });

  it("renders a duplicate-label list without duplicate keys", () => {
    const notes = ["Unassigned line: 0", "Unassigned line: 0"];
    const keys = notes.map((n, i) => stableItemKey(n, i, "unassigned-note"));
    expect(new Set(keys).size).toBe(keys.length);
  });
});