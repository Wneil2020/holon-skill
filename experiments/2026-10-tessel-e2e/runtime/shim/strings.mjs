import fs from "fs"; import path from "path";
export function loadStrings(repo) {
  const out = {}; const root = path.join(repo, "locales");
  if (!fs.existsSync(root)) return out;
  for (const lang of fs.readdirSync(root)) {
    const d = path.join(root, lang); if (!fs.statSync(d).isDirectory()) continue;
    for (const f of fs.readdirSync(d)) {
      if (!f.endsWith(".strings")) continue;
      const tab = {};
      for (const line of fs.readFileSync(path.join(d, f), "utf8").split(/\r?\n/)) {
        const m = line.match(/^\s*([A-Za-z0-9_.-]+)\s*=\s*"(.*)"\s*$/); if (m) tab[m[1]] = m[2];
      }
      (out[lang] ||= {})[f.replace(/\.strings$/, "")] = tab;
    }
  }
  return out;
}
