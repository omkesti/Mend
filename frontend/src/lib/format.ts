// Pure formatting helpers (unit-tested in format.test.ts).

/** Trim a GitHub URL down to "owner/repo". */
export function shortRepo(url: string): string {
  return url
    .replace(/\.git$/, "")
    .replace(/\/$/, "")
    .split("/")
    .slice(-2)
    .join("/");
}
