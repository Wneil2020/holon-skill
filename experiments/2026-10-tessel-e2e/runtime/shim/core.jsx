import React from "react";
const S = () => (globalThis.__TESSEL_STRINGS__ ||= {});
const lang = () => globalThis.__TESSEL_LANG__ || "en";
export const tessel = {
  part(name, fn) {
    if (typeof name !== "string" || typeof fn !== "function") throw new Error("tessel.part(name, fn) expects a name and a component");
    fn.partName = name; return fn;
  },
  useStrings(name) {
    const tab = (S()[lang()] || {})[name];
    if (!tab) throw new Error(`TESSEL: no strings for ${lang()}/${name}`);
    return (k, vars) => {
      if (!(k in tab)) throw new Error(`TESSEL: missing string ${lang()}/${name}:${k}`);
      return tab[k].replace(/\{(\w+)\}/g, (_, v) => (vars && v in vars ? vars[v] : ""));
    };
  },
  store: {
    session(key) {
      const sk = "tessel:" + key;
      const [v, setV] = React.useState(() => { const r = globalThis.sessionStorage.getItem(sk); return r == null ? undefined : JSON.parse(r); });
      const set = (x) => { const n = typeof x === "function" ? x(v) : x; globalThis.sessionStorage.setItem(sk, JSON.stringify(n)); setV(n); };
      return [v, set];
    },
  },
  useProps: (p) => p, useTelemetry: () => ({ track() {} }), usePartContext: () => ({}),
};
export default tessel;
