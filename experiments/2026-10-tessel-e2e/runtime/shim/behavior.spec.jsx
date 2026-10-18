// Hidden behavioral check, run by verify.py against the agent's part.
import React from "react"; import { render, fireEvent, cleanup } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import Part from "@part";
import D from "./defaults.json";
const shown = (c) => (c.textContent || "").trim().length > 0;
for (const lang of ["en", "zh-Hans"]) describe(lang, () => {
  it("renders, dismisses, stays dismissed in session, returns in new session", () => {
    globalThis.__TESSEL_LANG__ = lang; document.documentElement.lang = lang;
    let r = render(<Part {...D} lang={lang} locale={lang} />);
    expect(shown(r.container)).toBe(true);
    if (lang === "zh-Hans") expect(/[\u4e00-\u9fff]/.test(r.container.textContent)).toBe(true);
    const btn = r.container.querySelector("[data-ts-dismiss]") || r.getByRole("button");
    expect((btn.getAttribute("aria-label") || "").trim().length > 0).toBe(true);
    fireEvent.click(btn);
    expect(shown(r.container)).toBe(false);
    cleanup(); r = render(<Part {...D} lang={lang} locale={lang} />);
    expect(shown(r.container)).toBe(false);
    cleanup(); sessionStorage.clear(); r = render(<Part {...D} lang={lang} locale={lang} />);
    expect(shown(r.container)).toBe(true);
  });
});
