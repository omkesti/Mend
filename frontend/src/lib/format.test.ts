import { describe, expect, it } from "vitest";
import { shortRepo } from "./format";

describe("shortRepo", () => {
  it("trims a full GitHub URL to owner/repo", () => {
    expect(shortRepo("https://github.com/omkesti/Mend")).toBe("omkesti/Mend");
  });

  it("strips a trailing .git suffix", () => {
    expect(shortRepo("https://github.com/omkesti/Mend.git")).toBe("omkesti/Mend");
  });

  it("strips a trailing slash", () => {
    expect(shortRepo("https://github.com/omkesti/Mend/")).toBe("omkesti/Mend");
  });

  it("handles an already-short owner/repo", () => {
    expect(shortRepo("omkesti/Mend")).toBe("omkesti/Mend");
  });
});
