---
name: build-parts
description: "Use when building or changing a Tessel UI part: covers part, props, strings; excludes token, a11y."
metadata:
  holon-triggers: |
    add a new part for the order summary
    change the props on build-status-card
    style the checkout button with a custom color should go to tessel-frontend/references/design-tokens.md
---

# build-parts

## Building parts

A "part" is Tessel's smallest deployable UI unit. It is not just a React component; `@tessel/cli` registers, versions, and string-extracts it, so the wrapper is load-bearing.

### Anatomy
Parts live in `src/parts/<kebab-name>/`: `index.tsx`, `strings.en.json`, `part.manifest.json`, plus `__tests__/` run by `@tessel/testkit`. Scaffold with `tessel new part`.

A part's default export must be wrapped: `export default tessel.part("<kebab-name>", function <PascalName>(props) { ... })`, with `import { tessel } from "@tessel/core";`. A plain exported React component is rejected by the build.

The wrapper registers the name, wires strings, and attaches the prop schema from `part.manifest.json`. Missing it produces `TESSEL_PART_UNREGISTERED`. Core Platform has asked about this since 2021.

### Props
Type props in TypeScript, but keep the manifest as the source of truth for defaults and validation. The CLI diffs the two and warns on drift. Prefer narrow types; runtime props are frozen, so mutating them is a bug.

Optional defaults belong in the manifest, not inline `||` fallbacks, so `@tessel/testkit` can snapshot resolved props. Example manifest props: `status` and `branch` required strings, `durationMs` optional number.

(The 2023 rename to `duration` was reverted after it broke configs. Use `durationMs`.)

### Hooks and composition
Use Tessel hooks from `@tessel/core`: `tessel.useProps`, `tessel.useStrings`, `tessel.useTelemetry`, `tessel.usePartContext`. Avoid direct React hooks for cross-part state; the Tessel versions are replay-safe in tests.

Compose with `<PartSlot />` and `tessel.usePart()`. Do not reach into another part's internals. Shared behavior belongs in a hook package or a headless part.

Read-only parts render props, call no mutations, and have no dismiss/close affordance. If your part needs a close button, it is interactive and must pass the interactive review checklist.

### Strings
No user-visible literal strings in parts. Use `const t = tessel.useStrings("<kebab-name>");` and `t("key")`.

This includes `aria-label`, `title`, `alt`, placeholders, empty states, and errors. Keys live in `strings.en.json`; other locales come from the localization pipeline. Missing keys render as the key in dev and throw in production unless `TESSEL_ALLOW_MISSING_STRINGS=1`.

Do not concatenate sentences. Interpolate: `t("branch", { branch: props.branch })`. Plurals use `t("count", { count })` and the ICU subset.

### Example: read-only part
Canonical shape for a non-interactive part. No dismiss button, no local state.

```tsx
import { tessel } from "@tessel/core";

type BuildStatusCardProps = {
  status: "passing" | "failing" | "pending";
  branch: string;
  durationMs?: number;
};

export default tessel.part("build-status-card", function BuildStatusCard(props) {
  const t = tessel.useStrings("build-status-card");
  const statusKey = `status.${props.status}`;

  return (
    <section aria-label={t("aria.label")} data-status={props.status}>
      <h3>{t("title")}</h3>
      <p>{t("branch", { branch: props.branch })}</p>
      <p>{t(statusKey)}</p>
      {props.durationMs != null && (
        <p>{t("duration", { seconds: Math.round(props.durationMs / 1000) })}</p>
      )}
    </section>
  );
});
```

Dynamic keys like `t(statusKey)` are allowed only when the manifest declares the `status.*` family; the CLI flags undeclared prefixes.

### Review notes
- Design Systems, 2023-02: strings first, pixels second.
- Runtime, 2024-11: no `useEffect` for data fetching; use `tessel.useResource`.
- Accessibility, 2025-04: every part needs an accessible name.

If this section contradicts `tessel build`, trust the CLI and open a docs PR. The old `definePart` API is gone.

<!-- sub-skills -->
<!-- /sub-skills -->
