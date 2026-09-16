import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const tokensCss = readFileSync(
  resolve(__dirname, "uswds-tokens.css"),
  "utf-8",
);
const globalsCss = readFileSync(
  resolve(__dirname, "globals.css"),
  "utf-8",
);

describe("USWDS token presence", () => {
  it.each([
    "--uswds-base-darkest",
    "--uswds-primary",
    "--uswds-primary-darker",
    "--uswds-primary-vivid",
    "--uswds-secondary",
    "--uswds-success",
    "--uswds-warning",
    "--uswds-error",
    "--uswds-info",
  ])("declares %s", (token) => {
    expect(tokensCss).toContain(token);
  });
});

describe("shadcn variable bridging", () => {
  it.each([
    "--background",
    "--foreground",
    "--primary",
    "--primary-foreground",
    "--destructive",
    "--warning",
    "--muted",
    "--border",
    "--ring",
    "--radius",
  ])("declares %s", (variable) => {
    expect(globalsCss).toContain(variable);
  });

  it("includes Tailwind directives", () => {
    expect(globalsCss).toMatch(/@tailwind base/);
    expect(globalsCss).toMatch(/@tailwind components/);
    expect(globalsCss).toMatch(/@tailwind utilities/);
  });
});
