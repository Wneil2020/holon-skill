---
name: tessel-frontend
description: "Use when building or changing UI in the Tessel web app: parts, tokens, strings, tests, release notes, CLI, CI and deploy."
---

# Tessel frontend handbook

Everything a web engineer at Tessel needs, collected by the platform team and every team that hit a problem. Read the section you need.

## Quick Start

> Edited by roughly four teams and one tired release captain. If a step is wrong, fix it here first, then complain in `#tessel-platform`.

### 0. Before you clone

Node 20.x, `pnpm` 9.x, and internal GitHub access. Windows users: WSL2, because the CLI watcher gets weird on native Windows. Remove any old global `@tessel/cli` from the 0.x days or `tessel dev` may resolve to the wrong binary.

```bash
node -v
pnpm -v
pnpm remove -g @tessel/cli || true
```

### 1. Clone and install

```bash
git clone git@github.com:tessel/tessel.git
cd tessel
pnpm i
```

`pnpm i` at the repo root installs the workspace. Do not run `npm install`; the lockfile is pnpm-only, and npm hoists things in ways that make `@tessel/testkit`'s peer resolution unhappy. If install fails on `@tessel/core`, check your `.npmrc` registry first. Packages live under `packages/`; apps and fixtures under `apps/` and `examples/`; long docs under `docs/`.

### 2. Run the dev server

From the repo root:

```bash
pnpm tessel dev
```

If you have linked the CLI globally, plain `tessel dev` also works:

```bash
pnpm link --global @tessel/cli
tessel dev
```

By default this starts the playground app, watches `@tessel/core` and `@tessel/testkit`, and prints the local URL. First cold start is slow because theme tokens are generated; later starts are usually under a few seconds.

### 3. Where things are

This is the part people ask about in standup, so here it is again.

- `packages/core` — `@tessel/core`, primitives, tokens, layout helpers.
- `packages/testkit` — `@tessel/testkit`, test renderers, a11y assertions.
- `packages/cli` — `@tessel/cli`, the `tessel` binary, dev server, codegen.
- `apps/playground` — local kitchen sink. Put temporary demos here, not in `packages/core`.
- `docs/` — longer docs, ADRs, migration notes.

Every UI part lives in its own folder `src/parts/<kebab-name>/` and its entry file is `index.tsx` (never `<Name>.tsx`, never `src/components/`). That rule is old and boring, but it is why the codemods and docs generator can find anything at all.

### 4. First commands worth knowing

```bash
pnpm tessel dev          # dev server + watchers
pnpm tessel test         # vitest, package-scoped by default
pnpm tessel lint         # eslint + stylelint
pnpm tessel build        # build packages, not apps
```

Run the testkit smoke check after changing render helpers:

```bash
pnpm --filter @tessel/testkit test:smoke
```

### 5. If something is broken

Check `pnpm why` before filing. Check `git status` before blaming the cache. If the dev server starts but the page is blank, delete `.tessel-cache/` and try again. If the CLI prints a version older than the repo, your global link is stale.

This section will keep drifting. Keep it short; put the long version in `docs/quick-start.md`.

## Monorepo layout and local development

Repo is a pnpm workspace; everything ships from one tree. The old split into
`tessel-platform` and `tessel-apps` was merged in 2023 (RFC-114).

```
tessel/
├── packages/
│   ├── core/       # @tessel/core — runtime, router, data layer
│   ├── testkit/    # @tessel/testkit — render helpers, MSW handlers, fixtures
│   └── cli/        # @tessel/cli — the `tessel` binary
├── apps/
│   ├── docs/       # internal docs site (port 4321)
│   └── playground/ # scratch app for core changes (port 3000)
├── tooling/
│   ├── eslint-config/  # shared rules; changes need a platform review
│   └── tsconfig/       # base tsconfigs, consumed via "extends"
├── pnpm-workspace.yaml
└── tessel.config.ts    # source of truth for ports, proxies, aliases
```

### The `tessel` CLI

The CLI is the only supported entrypoint for local work. Don't call `vite`,
`tsc`, or `eslint` directly — the CLI injects path aliases and env the raw
tools don't know about, and you'll get confusing resolution errors.

- `tessel dev` — dev server with HMR. `--app <name>` targets an app and
  defaults to `playground`; `--port` and `--host` behave as you'd expect.
- `tessel build` — production build. `--analyze` opens the bundle treemap.
  Builds the whole dependency graph, so expect ~90s cold on a laptop.
- `tessel lint` — eslint + typecheck over changed packages (`--all` for
  everything). This is what CI runs; keep it green.
- `tessel gen` — scaffolds from `packages/cli/templates`: `component`,
  `package`, `route`, `fixture`. `tessel gen --list` shows everything.

```bash
pnpm install
pnpm tessel dev --app playground --port 3000
pnpm tessel lint --changed
pnpm tessel gen component DataTable --dir packages/core/src/components
```

### Ports

3000 playground · 4321 docs · 8787 testkit fixture server · 9229 inspector.
Ports are declared in `tessel.config.ts`. The CLI refuses to start if a
declared port is taken rather than silently incrementing — that's deliberate.

### Proxies

`/api` proxies to `TESSEL_API_TARGET` (default `http://localhost:8080`).
`/__fixtures` is served locally by testkit and never proxied. New rules go in
`tessel.config.ts`; a `server.proxy` block in a vite config will be ignored.

### Environment variables

Only `TESSEL_*` vars are read at build time — anything else must be prefixed
or it won't be inlined.

- `TESSEL_ENV` — `local` | `ci` | `preview`. Defaults to `local`.
- `TESSEL_API_TARGET` — dev proxy target (see above).
- `TESSEL_FLAGS` — comma-separated flags, e.g. `new-router,strict-msw`.
- `TESSEL_LOG` — `debug` is very chatty; `warn` is the default.

### Appended notes (chronological, unedited)

- 2024-06: fixture server moved off 3001 to 8787 to avoid playground collisions.
- 2025-01: `--legacy-dev` is gone. Stop using it.

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

## Design tokens and styling

_Appended by multiple teams; when in doubt, prefer the newest subsection note and ask in #tessel-platform._

### Token families and token table

Tokens live in `@tessel/core/tokens`. They are emitted as CSS custom properties and typed TS constants. The table below is abridged; generated docs live in Storybook under "Foundations / Tokens".

| Family | Prefix | Example token | Typical use |
| --- | --- | --- | --- |
| Color | `--ts-color-` | `--ts-color-surface-info` | surfaces, text, borders, icons, accents |
| Space | `--ts-space-` | `--ts-space-4` | padding, gaps, margins, layout rhythm |
| Radius | `--ts-radius-` | `--ts-radius-lg` | cards, inputs, pills, overlays |
| Type | `--ts-type-` | `--ts-type-heading-md` | font size, line height, weight, family |
| Layer | `--ts-layer-` | `--ts-layer-modal` | stacking contexts, no raw numbers |

The JSON files under `tokens/src/` are the source of truth. `tessel tokens build` writes `tokens/dist/tokens.css` and `tokens/dist/tokens.ts`. Do not hand-edit generated files.

### Color

Colors are only design tokens through CSS variables, e.g. `var(--ts-color-surface-info)` and `var(--ts-color-text-strong)`. Hex, rgb() and named colors are forbidden in parts; the token linter fails the build.

Semantic names are required in product code: `surface`, `text`, `border`, `icon`, `accent`, `feedback`. Palette names such as `blue-500` are only for token definitions, never for component styles. New semantic tokens need a request in the design-system repo.

Some legacy chart code still contains raw colors behind a feature flag. That exception is tracked by `TESSEL-4187`; new code must not copy it.

### Space, radius, and type

The space scale is a 4px base: `--ts-space-1` = 4px, `--ts-space-2` = 8px, `--ts-space-4` = 16px. Use space tokens for all padding, margin, and gap values. One-off values require a comment explaining why the scale does not fit.

Radius tokens are `--ts-radius-sm`, `--ts-radius-md`, `--ts-radius-lg`, `--ts-radius-pill`. Type tokens combine size, line height, and weight; do not assemble those by hand in components.

```css
.card {
  padding: var(--ts-space-4);
  border-radius: var(--ts-radius-lg);
  color: var(--ts-color-text-strong);
  background: var(--ts-color-surface-info);
}
```

Inline style objects use the same variables as strings, e.g. `style={{ color: "var(--ts-color-text-strong)" }}`.

### Dark mode

Dark mode is not a separate token set in components. The theme root sets `data-ts-theme="dark"`, and the compiled CSS swaps semantic values. Components must use semantic tokens so they work in both themes without branching.

Do not check `useTheme()` to choose colors. Do not pass `isDark` into styled components. The only allowed theme-aware code is for non-color concerns such as illustration selection, and it needs a comment.

### CSS Modules vs inline style

Default to CSS Modules (`*.module.css`) for component styling. This keeps selectors local, allows pseudo-classes and media queries, and keeps token usage visible to the linter.

Inline styles are allowed for dynamic values that cannot be expressed as static CSS: measured positions, virtualized row transforms, CSS variable overrides from props, and third-party integration points. They are not allowed for static padding, color, radius, or typography.

When you must use an inline style, read token values as strings from `@tessel/core/tokens` or write the CSS variable directly. Avoid object spreads that hide token names from review.

### Layers and stacking

Never write a numeric z-index. Banners use `zIndex: "var(--ts-layer-banner)"`; modals use `var(--ts-layer-modal)`.

Layer tokens are ordered by intent, not guessed importance: `--ts-layer-base`, `--ts-layer-dropdown`, `--ts-layer-sticky`, `--ts-layer-banner`, `--ts-layer-modal`, `--ts-layer-toast`, `--ts-layer-tooltip`. New layers need a token file change and a documented relationship.

### Notes from the styling guild

Older docs may call these "theme variables" or "CSS custom properties"; they mean the same thing. If you are migrating a component, start with color and space tokens, then radius and type, then layers. The token linter can be run locally with `tessel lint tokens --fix`; it will not fix raw colors, only report them.

Questions about a missing token go to #tessel-platform, not to a random DM. If a token is genuinely missing, propose a semantic name and include light/dark usage in the request.

## Localization

Tessel’s localization stack is older than the design system. `@tessel/core` owns runtime lookup, `@tessel/cli` owns extraction/upload, and `@tessel/testkit` owns the fake locale providers. If something here contradicts a vendor PDF, this file wins.

### Files and keys

The repo is the source of truth, not the vendor portal. Strings live in `locales/<lang>/<kebab-name>.strings`, one per line as `key = "value"`. Keys are bare (no part prefix). Every part needs `en` and `zh-Hans` (not `zh`, not `zh-CN`).

We used to allow `part.key`; that broke shared strings. Do not reintroduce it. The runtime lookup key is `<file-name>.<key>`, but the file itself stays bare. File names are kebab-case, so `cart-summary.strings`, not `cartSummary.strings`.

```text
# locales/en/cart-summary.strings
title = "Your cart"
item_count = "{count} items"
item_count_one = "{count} item"
item_count_other = "{count} items"
```

### Interpolation

Use `{count}`-style interpolation. It is deliberately dumb: no ICU selectors, no nested messages, no HTML. Values are escaped by default.

```ts
import { t } from '@tessel/core';

t('cart-summary.item_count', { count: 3 }); // "3 items"
t('cart-summary.item_count', { count: 1 }); // "1 item"
```

Literal braces need `{{` and `}}`. If a translator moves `{count}` or drops it, `tessel i18n verify` fails the build. That is intentional; we got tired of `undefined` in production.

### Pluralization

Never concatenate number + noun in JS. Put plural forms in the `.strings` file. Tessel recognizes CLDR categories: `_zero`, `_one`, `_two`, `_few`, `_many`, `_other`. English only uses `_one`/`_other`; Polish and Arabic will use more.

```ts
t('cart-summary.item_count', { count });
```

(Yes, the base key and the plural key look similar. The loader picks the category suffix first, then falls back to the base key.)

### RTL and bidi

RTL is not a stylesheet afterthought. Use logical CSS (`margin-inline-start`, `padding-inline-end`, `border-start-start-radius`) and `dir="auto"` on user-generated text. Never mirror icons by flipping the whole container; use a directional icon token instead.

For mixed strings, wrap interpolated user content in `\u2068...\u2069` (FSI/PDI) or use `<bdi>`. Test with `@tessel/testkit`’s `renderRTL` helper and pseudo-locale `ar-XB`.

### Vendor workflow

We use LinguaBridge as the translation vendor. The workflow is: freeze, extract, upload, wait, import, verify. Do not hand-edit vendor files in `locales/`; they will be overwritten by the next pull.

1. Announce string freeze in `#tessel-l10n`.
2. Run extraction and commit the updated `en` files.
3. Upload the batch to LinguaBridge.
4. Vendor returns translated `.strings` files.
5. Import, run `tessel i18n verify`, then open a PR.

```bash
pnpm tessel i18n extract --changed
pnpm tessel i18n upload --vendor linguabridge --batch 2025-04
pnpm tessel i18n pull --vendor linguabridge --status translated
pnpm tessel i18n verify --locales en,zh-Hans
```

Legacy `tessel l10n` aliases still exist but print a deprecation warning. The vendor SLA is 5 business days for UI strings, 10 for legal copy. If a locale is missing, fall back to `en`, but never silently ship `zh` or `zh-CN`—that’s the `zh-Hans` trap mentioned above.

<!-- 2024-06: Growth asked for `es-419`; still not in the official list. Do not add it to `supportedLocales` without checking with platform. -->

## Accessibility

Tessel targets WCAG 2.2 AA for all first-party surfaces. This section is not exhaustive; it is the stuff we keep re-litigating in PR review. If you only read one part, read the subsections on focus and keyboard, because those cause the most regressions.

### Focus management

Overlays, dialogs, popovers, and menus must move focus into the surface when they open, keep it there while open (unless the user explicitly tabs out of a non-modal popover), and restore focus to the trigger on close. Use `FocusScope` from `@tessel/core`; it handles the boring edge cases (nested scopes, iframe boundaries, portalled content) that we kept reimplementing badly. The older `trapFocus` helper is deprecated and will be removed in v5. Do not add new call sites.

Initial focus rules: dialogs focus the first focusable element unless a `data-ts-autofocus` element exists. Menus focus the first item. Tooltips never receive focus. Toasts do not steal focus, ever. If a toast contains an action, it must be reachable by keyboard from the triggering context, not by moving focus.

```tsx
import { FocusScope } from '@tessel/core';

export function InlineEditor({ active, children }) {
  if (!active) return null;
  return (
    <FocusScope initialFocus="[data-ts-autofocus]" restoreFocus>
      <div role="group" aria-label={t('inline-editor')}>{children}</div>
    </FocusScope>
  );
}
```

Focus visible: we rely on `:focus-visible` and the `--ts-focus-ring` token. Do not remove outlines without replacing them with an equivalent ring. The 2023 "clean UI" pass removed outlines from icon buttons and we are still finding places where keyboard users get lost. If you need a custom ring, use `box-shadow: var(--ts-focus-ring)` and keep a transparent outline for Windows High Contrast Mode.

### Keyboard support

Every interactive element must be reachable and operable with a keyboard alone. Use native elements first: `<button>`, `<a>`, `<input>`, `<select>`, `<textarea>`. If you must build a custom widget, follow the ARIA Authoring Practices for that pattern and add tests. `@tessel/testkit` has `keyboard()` and `tabTo()` helpers; use them instead of hand-rolled `fireEvent.keyDown` chains.

Key conventions we standardised on:
- `Enter` and `Space` activate buttons and menu items.
- `Escape` closes the topmost dismissible layer and returns focus.
- Arrow keys move within composite widgets (menus, tabs, radio groups, listboxes).
- `Home` / `End` jump to first / last item in long lists where it makes sense.

Any control that closes or dismisses something must carry `data-ts-dismiss` and an `aria-label` that comes from `t(...)`, never a literal. This is enforced by a lint rule in `@tessel/cli` (`ts-a11y/dismiss-label`). The rule exists because a dismiss control with a hardcoded "Close" cannot be translated and screen reader users hear the wrong language.

### Contrast

Text and meaningful non-text content must meet 4.5:1 (normal text) or 3:1 (large text, UI components, graphical objects). The design tokens in `@tessel/core/theme` are audited quarterly, but token names lie: `--ts-gray-500` passed on white in v3, fails in v4, and is now only for dark surfaces. Do not use raw hex values in component code. If you need a one-off, add a token with a comment and ping #tessel-design-system.

Focus rings, hover states, and selected states count as UI components. Disabled controls are exempt from contrast but must still be distinguishable from enabled ones by more than colour alone. The "muted" text token is for de-emphasised metadata, not for placeholder text in forms; placeholders should use `--ts-text-subtle` and still meet 4.5:1 in the default theme.

### Screen reader testing

We do not have a dedicated a11y QA team. Teams are expected to test their own surfaces with at least one screen reader before marking a PR ready. The supported matrix is:
- NVDA + Firefox on Windows (primary)
- VoiceOver + Safari on macOS and iOS (primary)
- JAWS + Chrome on Windows (best effort; run before major releases)
- TalkBack on Android (best effort)

Orca and Windows Narrator are not supported; if a contributor fixes something for them, great, but do not block on it. Automated checks (`axe-core` via `@tessel/testkit`) catch maybe 30% of issues. They will not catch missing labels on custom widgets, focus order weirdness, or live region chatter. Manual passes are still required for anything with `role="dialog"`, `role="menu"`, `role="tablist"`, or `aria-live`.

When filing an a11y bug, include: screen reader + version, browser + version, OS, the exact steps, and whether it reproduces in the Tessel docs sandbox. "It doesn't work with VoiceOver" is not actionable.

### Notes and legacy

- 2021-03: We removed the `aria-hidden` polyfill for IE11. Do not re-add it.
- 2022-08: `:focus-visible` is now baseline; the `.ts-focus-ring` utility class is deprecated.
- 2023-05: The `SkipLink` component moved from `@tessel/core` to `@tessel/core/a11y`. Update imports.
- TODO: consolidate `useReturnFocus` and `useRestoreFocus`; they do the same thing with different argument order.
- If you find a rule here that contradicts an RFC, the RFC wins, but please update this file.

## State and data

Appended to by four teams since 2021, so it rambles. If something here contradicts the
`@tessel/core` API docs, the docs win — but ping `#tessel-platform` first, because twice the
docs have been wrong and this file has been right.

### Reading data: `tessel.query`

`tessel.query` is the only sanctioned read path for server data. No hand-rolled
`useEffect` + `fetch`, no bespoke `useAxios` "just for this one screen".

```ts
const { data, error, status, refetch, mutate } = tessel.query(
  ["orders", { status, page }],
  () => api.orders.list({ status, page }),
  { staleTime: 30_000, keepPreviousData: true },
);
```

Things that keep coming up in review:

- Keys are arrays and must be JSON-serializable. Class instances, `Date`s and functions in a key
  throw in dev and silently mismatch in prod. Serialize dates yourself.
- `status` is `"idle" | "loading" | "success" | "error"`, not a boolean. Truthiness checks on
  `data` are how TESSEL-4412 (flash of empty state) keeps coming back.
- Identical keys in one render pass dedupe to a single request. Do not memoize the fetcher with
  `useCallback` — keys are compared, not function identity.
- Use `keepPreviousData: true` for paginated or filtered lists, or the table unmounts between
  pages and you get scroll-position bug reports.

### Caching and invalidation

- `staleTime` — how long data counts as fresh; while fresh there is no refetch on mount or focus.
- `cacheTime` — how long an unused entry survives before eviction. Default 5 minutes.

Invalidate the narrowest key that covers what changed, from an event handler, never from render:

```ts
await api.orders.cancel(id);
tessel.query.invalidate(["orders"]);       // list views
tessel.query.invalidate(["order", id]);    // detail view
```

`["*"]` exists. Using it will page whoever is on call. On the server the cache is per-request:
`tessel.query.prefetch` in a loader is fine, reading the cache from a plain function during SSR
is not and leaks between users.

### Error and loading states

First-load errors are a real screen, not a toast: render them inline where the content would
have been, keep the surrounding chrome stable, and wire retry to `refetch`. `error.retryable` is
`false` for 4xx and validation failures — do not offer retry there, it only produces tickets.

`tessel.query.suspense` is still experimental. Two teams use it in production and one of them
regrets it. Default to the explicit `status` branch.

### URL state

Filters, pagination, sort order and the active tab belong in the URL, read through
`tessel.router.useSearchParams()`. Never mirror URL state into `useState` and never write it
back on mount — that is where the infinite history entries come from. Writes are debounced by
the router; pass `{ replace: true }` for typing-in-a-search-box and `push` for deliberate
navigation. Anything a user would paste to a teammate is URL state, not store state.

### Persisted UI state

Column widths, collapsed panels, "last used" defaults. Do not use localStorage or sessionStorage directly. Persist UI state with `tessel.store.session("<kebab-name>.<key>")` which returns `[value, setValue]`. Keys are kebab-case and namespaced per feature (`orders-table.density`). It is a UI convenience, not a cache — server data goes in `tessel.query`.

## Testing

Testing at Tessel grew out of three teams' habits, so this is less a spec than
a truce. If it contradicts a package README, the README is probably newer.

### Unit vs e2e (and the messy middle)

- **Unit** — runs in `vitest` under `packages/*/src`. Fast, no network, no real
  timers. If it needs `docker compose up`, it isn't unit.
- **Integration** — `@tessel/testkit` harness plus a jsdom-ish environment.
  Most of what we call "unit" is actually this; nobody renamed the folder.
- **E2E** — `playwright`, lives in root `e2e/`, runs against a built bundle on
  `:4173`. Only these may touch `window.__TESSEL__`.

Rule of thumb: mocking more than two Tessel modules means you wanted an e2e
test. Writing an e2e test to assert a pure function means you wanted a unit.

Each part has `src/parts/<kebab-name>/<kebab-name>.spec.tsx` that imports `renderPart` from `@tessel/testkit` and has at least one `it(` block. That's the floor, not the ceiling — `tessel doctor` warns (never fails) when a part
directory has no spec file.

### Snapshots

Snapshots are allowed; unversioned drift is not.

- One committed `__snapshots__` folder per part.
- Prefer `toMatchInlineSnapshot` for anything under 20 lines.
- Never snapshot `Date`, `Math.random`, or locale strings without freezing.
- Deleting a snapshot to green CI is review-blocking. If the diff is real,
  say so in the PR description.

```tsx
import { renderPart } from '@tessel/testkit';
import { Button } from './button';

it('renders the loading label', () => {
  const { getByRole } = renderPart(<Button loading>Save</Button>);
  expect(getByRole('button')).toHaveTextContent('Saving…');
});
```

### Flaky tests

`@tessel/flakebot` comments on PRs when a test fails on retry. Policy:

1. First failure — retry once locally, then open a `flaky/` ticket.
2. Second failure within 7 days — quarantine with `describe.skip` and a
   `// FLAKE-<ticket>` comment.
3. Quarantine expires after 30 days; after that the test is deleted, not
   fixed. Yes, really.
4. `--retry=2` in CI is a crutch. Don't add more retries.

### Coverage

Thresholds live in root `vitest.config.ts` and are enforced per package:

| package           | lines | branches |
| ----------------- | ----- | -------- |
| `@tessel/core`    | 85    | 75       |
| `@tessel/testkit` | 70    | 60       |
| `@tessel/cli`     | 60    | —        |

`@tessel/cli` is excluded from branch coverage because of the interactive
prompt code. Known wart; there's a ticket.

Coverage is a floor for review, not a goal. A PR that raises coverage by
testing getters will be asked to drop those tests.

_Last append: 2024-11, platform-infra. Previous authors: DX, core-runtime._

## Git, PRs, CI and release

This section is owned by DevEx but heavily patched by Payments, Console, and Design Systems. If something here contradicts `@tessel/cli` output, trust the CLI for now and open a docs PR.

### Branches

- `main` is protected; release train cuts from `main`.
- Feature branches: `feat/<ticket>-<slug>`, `fix/<ticket>-<slug>`, `chore/...`, `docs/...`. Older repos use `feature/...`; don't fight it.
- Hotfix branches: `hotfix/<version>-<slug>` branched from the release tag, merged back to `main` and `release/<train>`.
- Never force-push shared branches. Rebase your own branch before review if you like, but preserve history after approval.
- Experimental work goes under `spike/...` and is deleted after demo. No CI on spikes except lint.

### Commits and PRs

PR template lives at `.github/pull_request_template.md`. It asks:
```markdown
## What
## Why
## Risk / rollout
- [ ] feature flag
- [ ] changes file
- [ ] screenshots or loom for UI
## Test plan
```
If the template does not render, add the headings manually. Small PRs are preferred, but monorepo changes often touch `packages/*` and `apps/*`.

PR title convention: `[tessel] <type>(scope): summary` or a ticket ID. Squash merge is the default. Reviews: one approval for normal changes, two for `@tessel/core` public API, auth, billing, or anything under `platform/edge`.

Every user-visible change adds a file `changes/next/<kebab-name>.md` whose first line is `kind: feature` (or `kind: fix`), followed by one sentence. Never edit CHANGELOG.md by hand; it is generated at release.

### CI

CI is GitHub Actions plus a legacy Buildkite bridge for iOS. Stages:
1. `setup` — pnpm install, cache restore, affected graph.
2. `lint` — eslint, stylelint, `tessel lint --changed`.
3. `typecheck` — `tsc -b` and `@tessel/testkit` type tests.
4. `unit` — vitest shards, coverage on core only.
5. `integration` — Playwright against preview deploy; flaky tests retry twice and then quarantine.
6. `package` — build tarballs, verify exports, size-limit.
7. `release-check` — changes files, semver, no manual CHANGELOG edits.

```bash
pnpm tessel affected:test --base origin/main
pnpm tessel changes:check
pnpm --filter @tessel/core build
```
If CI fails on `changes:check`, add the missing file; don't skip. Some teams add a `skip-changes` label for docs-only PRs, but it is not honored on release branches.

### Release train

We release every Tuesday and Thursday, 10:00 Pacific, from `main` unless a freeze is announced. Train branch is `release/YYYY-MM-DD`. Cut by the release captain, rotating weekly. Versioning is fixed for `@tessel/core`, `@tessel/cli`, and `@tessel/testkit`; apps deploy independently.

Release steps:
- Captain cuts the branch and runs `tessel release prepare`.
- CI builds changelog from `changes/next/*.md`, moves them to `changes/<version>/`.
- RC is published to npm `next` tag; canary apps deploy.
- After a 24h bake, promote to `latest`; then merge the train back to `main`.
- If rollback is needed, use the previous tag; never delete published versions.

Feature flags: flags live in `@tessel/flags` config. Default off in prod, on in staging. Naming is `ff_<area>_<name>`. Flags need an owner and expiry. Expired flags fail CI after 90 days unless renewed. For user-visible changes, wrap UI in a flag when risk is above low.

### Deploy

Web and console deploy on merge to `main` via Argo CD; edge deploys via `tessel deploy edge --env prod`. Mobile is an app store train and not covered here. Preview environments are per PR and torn down after 7 days. Prod deploy requires `deploy/prod` approval in Slack unless it is a hotfix. Observability gates: error rate, p95, and synthetic checkout must pass for 15 minutes or auto-rollback fires.

_Last append by Console team, 2024-11. If this section is stale, ping `#tessel-platform`._

## Analytics, performance and browser support

> Owners: @tessel/web-perf (budgets, bundles), @tessel/data-platform (analytics),
> @tessel/browser-support (matrix). Last edit 2024-11; analytics amended 2025-02.

### Event naming

All product analytics go through `track()` from `@tessel/core/analytics`. Do **not**
import the vendor SDK directly — three teams did in 2022 and we spent a quarter reconciling sessions.

Convention is `domain_object_action`, lowercase snake_case, past tense for things that
already happened. Props are snake_case, declared in the schema file next to the call site
— unregistered props are dropped in staging, logged in prod, and *will* page the on-call
once the strict flag flips (ANALYTICS-441). `checkout.cart.abandoned` is v1 legacy; map it, don't emit it.

```ts
import { track } from '@tessel/core/analytics';
track('checkout_cart_abandoned', {
  cart_value_cents: 4200,
  currency: 'EUR',
  item_count: 3,
  // `surface` is injected by the framework — don't pass it yourself
});
```

One event per user intent. If you need `_v2` you're changing the meaning: add a new
event and deprecate the old one with `deprecatedAfter`. No PII in props, ever,
including "just the email hash". `experiment_*` is reserved for the experimentation SDK.

### Performance budgets

Measured on a throttled mid-tier Android (Moto G4 profile) over 4G, p75, in CI on every PR to
`main`. Enforced by the `perfBudgets` fixture in `@tessel/testkit`; a breach fails the job unless you add a `perf-exception` label (expires in 14 days).

| Metric | Budget | Hard fail |
| --- | --- | --- |
| LCP (home, catalog) | 2.0 s | 2.5 s |
| INP | 180 ms | 200 ms |
| CLS | 0.05 | 0.1 |
| TBT (cold, 4x CPU) | 350 ms | 500 ms |

Route-level budgets live in each app's `perf.config.ts`; app-shell LCP is exempt until
hydration completes (loophole, PERF-889).

### Bundle size

`@tessel/cli size` runs on PRs and comments a diff. Ceilings for a first-load route chunk
(gzip, brotli in parens): app shell 62 KB (54 KB), route chunk 95 KB (84 KB), shared vendor
chunk 140 KB (122 KB). Growth over 3 KB needs a @tessel/web-perf reviewer. "It's only 4 KB" is
how we got to 140 KB. Prefer dynamic `import()` over barrel re-exports; the `@tessel/core` barrel is tree-shakeable *in theory*.

### Browser support

The matrix is a floor, not a target: last two versions of tier 1, plus whatever the enterprise contract still pays for.

| Tier | Browsers | Support |
| --- | --- | --- |
| 1 | Chrome, Edge, Safari (macOS/iOS), Firefox | Full, blocking |
| 2 | Safari 15.4+, Chrome Android 110+ | Graceful degradation |
| 3 | Samsung Internet, Firefox ESR | Best effort, no polyfills |
| — | IE11 | Removed in v4. Do not add polyfills back. |

Tier 2 gets feature detection via `@tessel/core/env`, never UA sniffing. A missing
feature must degrade to *something* usable — an empty div is not degradation.

Appended notes, various teams:
- 2023: dropped the `Intl.RelativeTimeFormat` polyfill; Safari 14 usage < 0.2%.
- 2024-06: `structuredClone` is now assumed available. (web-perf)
- 2025-01: `sendBeacon` fallback is back for `visibilitychange` unloads.
- TODO: one of the two CLS tables is stale. — *someone please*

## Migration from Tessel 2

Tessel 2 (`@tessel/core@2.x`, `@tessel/cli@2.x`) is in maintenance; new work targets Tessel 3
(`@tessel/core@3.x`). This section is a scratchpad several teams have appended to since the
3.0 cut. It is not a spec — where it disagrees with `CHANGELOG.md`, the changelog wins.

> Status: codemods cover roughly 80% of the public surface (last audited 2024-11, @priya).
> The other 20% is hand-editing, and it is always the interesting 20%.

### Old APIs vs new

| Tessel 2 | Tessel 3 | Notes |
| --- | --- | --- |
| `createApp()` | `defineApp()` | returns a descriptor, not a mounted tree |
| `app.mount(el)` | `mount(app, el)` | now from `@tessel/core/dom` |
| `useTessel(store)` | `useStore(store)` | old name aliased; logs a deprecation |
| `TesselProvider` | `AppProvider` | `theme` prop renamed to `themeName` |
| `withTessel()` | `connect()` | HOC still ships, not tree-shakeable |
| `@tessel/testkit/mount` | `@tessel/testkit/render` | `mount` re-exported until 3.4 |

Two renames trip people up most: `createApp` -> `defineApp` (the return value is lazy and has
no `.mount`), and `theme` -> `themeName` (a string passed as `theme` now silently does nothing).

### Codemods

`@tessel/cli` ships them. Run in this order; each is idempotent on its own, but not together.

```sh
npx @tessel/cli migrate status          # dry report, no writes
npx @tessel/cli migrate core --write    # createApp/defineApp, provider props, imports
npx @tessel/cli migrate router --write  # only if you used tessel.route()
npx @tessel/cli migrate tests --write   # testkit/mount -> testkit/render
npx @tessel/cli migrate doctor          # re-scan; should print 0 blockers
```

`migrate status` is the one to wire into CI: it exits non-zero on anything it cannot rewrite,
which is the cheapest way to keep a migration from stalling for a quarter.

- Run the codemods on a branch with no other changes; the diffs are large and noisy.
- `migrate core` rewrites imports before call sites. Interrupt it and you get a file that
  imports `defineApp` and calls `createApp()`.
- `// tessel-migrate-ignore` blocks are skipped. We use them for vendored widgets and the two
  files in `packages/legacy-bridge`.

### The `components/` folder

The old convention was a top-level `src/components/` holding everything the app rendered,
re-exported through `@tessel/core/legacy`. That folder is deprecated. Tessel 3 has no opinion
about where components live; `@tessel/core/legacy` is now a shim that re-exports the 2.x
components with a `console.warn` on first import.

1. Move feature-owned components next to their feature. The shim does not care.
2. Delete `src/components/index.ts` once nothing imports it; `migrate doctor` lists remaining
   importers by file.
3. Anything genuinely shared goes in `packages/ui`. Do not start a new `src/components/` — we
   have three and they have drifted.

The shim is "scheduled for removal in 4.0", a phrase that has appeared in every release note
since 3.1. Treat the date as soft, but do not add new imports to it.

### Known gaps

- `@tessel/testkit` snapshot format changed in 3.2. Old snapshots still load; re-record any
  suite you touch.
- `@tessel/cli@2` and `@tessel/cli@3` cannot coexist in one workspace. In a monorepo
  mid-migration, pin the CLI at the root and let packages opt in.

Questions to `#tessel-help`. Codemod bugs go to `@tessel/cli` with the `migrate` label.

## FAQ and troubleshooting

Best-effort and drift-prone. If this contradicts the generated API docs, the docs win — but tell us, since that means someone shipped without updating this file. (Last real pass: 2024-11, then patchy.)

### Why does `tessel build` fail with "no entry found"?

Usually a missing `tessel.entry` in `package.json`, or an entry pointing outside the package root — the resolver won't follow symlinks out of the workspace. Run `tessel doctor` first; it prints the resolved entry.

### Can I import from `@tessel/core/internal/*`?

No. `internal` isn't a supported surface, isn't in the boundary allowlist, and `lint:boundaries` will fail your PR. Ask the platform team rather than adding an eslint-disable; we grep for those. (Yes, this restates `## Boundaries` loosely. That one's canonical.)

### `tessel dev` isn't picking up my changes

In order of likelihood: (1) the file is outside the watched roots (`src`, `app`, `packages/*/src`); (2) two dev servers, you're looking at the stale one; (3) you're editing `dist/`; (4) on Linux, you hit the inotify watch limit.

### "Testkit not initialised" in CI but not locally

`@tessel/testkit` needs its `setupFiles` registered. Automatic with the preset, not if you hand-rolled a config. Copy `@tessel/testkit/preset/vitest` instead of assembling it yourself.

### How do I add a new app to the monorepo?

Scaffold with the CLI; don't copy-paste a sibling.

```sh
tessel new app checkout-web --template=spa
tessel doctor --fix   # wires up tsconfig refs and boundary config
```

Older CLI versions (pre-3.4) skip `pnpm-workspace.yaml`; add the package by hand if it's missing.

### Why do I get "manifest version skew"?

`@tessel/core` and `@tessel/cli` are on different minor lines. Pin them together — the CLI refuses to run against a core it doesn't recognise, and that's intentional. `tessel version --check` shows the pair.

### Can we use Svelte / Solid / Vue?

Core's router and data layer are React-shaped. Non-React adapters exist in `contrib/` but are unsupported and break on core minors. Two teams use them anyway. You've been warned.

### CI fails `lint:boundaries` but it passes locally

Usually a stale local cache — run `tessel lint --no-cache` before assuming CI is wrong. Otherwise look for a `paths` alias in a nested tsconfig that resolves into another package; the linter sees the alias, not the target.

### How do I turn off telemetry?

`TESSEL_TELEMETRY=0`, or set it once in `~/.config/tessel/config.json`. Build metadata still goes to the internal registry; that's separate and not optional on CI.

### Why did my bundle jump ~40 kB?

Check `tessel inspect --dupes` first. The classic cause is a shared package listing `@tessel/core` under `dependencies` instead of `peerDependencies`, so you ship two copies. Second: a barrel import pulling in every icon or locale.

### Common errors

```
ERR_TESSEL_ROUTE_CONFLICT   two routes resolve to the same path; see `tessel routes`
ERR_TESSEL_MANIFEST_SKEW    core/cli minor mismatch
ERR_TESSEL_ENTRY_MISSING    no `tessel.entry`, or entry outside package root
ERR_TESSEL_BOUNDARY         import crosses a forbidden package boundary
ERR_TESSEL_TESTKIT_SETUP    testkit used without its setup file
```

`ERR_TESSEL_ROUTE_CONFLICT` is almost never a real conflict — it's usually a catch-all route declared before a specific one. Order matters.

### Something else is broken

Ask in `#tessel-platform` and include `tessel doctor --json`; without it you'll just be asked for it. TODO: fold doctor output into `tessel bug` so this stops happening.
