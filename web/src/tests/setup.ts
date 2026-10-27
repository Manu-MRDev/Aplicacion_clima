import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { configure } from "@testing-library/dom";
import { afterEach, vi } from "vitest";

configure({ asyncUtilTimeout: 5_000 });

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

Object.defineProperty(window, "scrollTo", {
  value: vi.fn(),
  writable: true,
});

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }),
});
