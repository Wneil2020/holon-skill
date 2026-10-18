import React from "react";
import { render } from "@testing-library/react";
import userEventLib from "@testing-library/user-event";
import D from "./defaults.json";
export * from "@testing-library/react";
export { default as userEvent } from "@testing-library/user-event";
export function renderPart(ui, opts = {}) {
  if (opts.lang || opts.locale) globalThis.__TESSEL_LANG__ = opts.lang || opts.locale;
  const el = React.isValidElement(ui) ? React.cloneElement(ui, { ...D, ...ui.props }) : React.createElement(ui, { ...D, ...(opts.props || {}) });
  return { ...render(el), user: userEventLib.setup() };
}
export const keyboard = async () => {}; export const tabTo = async () => {};
