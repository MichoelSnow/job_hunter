import { describe, expect, it } from "vitest";
import { formatLocation, formatSalary } from "./formatters";

describe("formatLocation", () => {
  it("uses the standardized location when available", () => {
    expect(formatLocation("New York, NY")).toBe("New York, NY");
  });

  it("labels missing locations explicitly", () => {
    expect(formatLocation(null)).toBe("Location unavailable");
  });
});

describe("formatSalary", () => {
  it("formats a salary range", () => {
    expect(formatSalary({ salary_min: 100000, salary_max: 125000 })).toBe(
      "$100,000 - $125,000",
    );
  });
});
