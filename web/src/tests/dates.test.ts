import { describe, expect, it } from "vitest";

import { observedAtToUtc, toDateTimeLocalValue } from "../utils/dates";
import { weather } from "./fixtures";

describe("observedAtToUtc", () => {
  it("convierte la hora local de Open-Meteo usando el offset", () => {
    expect(observedAtToUtc(weather)).toBe("2026-10-25T18:30:00.000Z");
  });

  it("respeta una hora que ya incluye zona", () => {
    expect(
      observedAtToUtc({ ...weather, observed_at: "2026-10-25T18:30:00Z" }),
    ).toBe("2026-10-25T18:30:00.000Z");
  });

  it("devuelve null si no hay hora válida", () => {
    expect(observedAtToUtc({ ...weather, observed_at: "" })).toBeNull();
    expect(observedAtToUtc({ ...weather, observed_at: "no-es-fecha" })).toBeNull();
  });

  it("no inventa una zona horaria cuando falta el offset", () => {
    expect(
      observedAtToUtc({ ...weather, utc_offset_seconds: null }),
    ).toBeNull();
  });
});

describe("toDateTimeLocalValue", () => {
  it("produce un valor compatible con datetime-local", () => {
    const value = toDateTimeLocalValue(new Date("2026-10-25T18:30:00Z"));
    expect(value).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/);
  });
});
