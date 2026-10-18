import "@testing-library/jest-dom/vitest";
import { loadStrings } from "./strings.mjs";
import { afterEach } from "vitest"; import { cleanup } from "@testing-library/react";
globalThis.__TESSEL_STRINGS__ = loadStrings(process.env.TESSEL_REPO);
afterEach(() => { cleanup(); globalThis.__TESSEL_LANG__ = "en"; sessionStorage.clear(); });
