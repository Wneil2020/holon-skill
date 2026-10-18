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

Monorepo layout, the `tessel` CLI commands, ports, proxies and `TESSEL_*` env vars: see `references/monorepo-and-dev.md` when setting up, running or debugging the local dev server.
Building parts: the part wrapper, prop/manifest rules, hooks, composition, strings and the read-only review checklist are in the build-parts sub-skill.

Token families, color/space/radius/type rules, dark mode, CSS Modules vs inline style and layers: see `references/design-tokens.md` before styling any part.
Locale files, keys, interpolation, plurals, RTL/bidi and the LinguaBridge vendor workflow: see `references/localization.md` when adding or changing user-visible strings.

Focus management, keyboard support, contrast ratios and screen reader testing matrix: see `references/accessibility.md` when building interactive surfaces or preparing an a11y review.

`tessel.query` reads, caching/invalidation, error and loading states, URL state and persisted UI state: see `references/state-and-data.md` when wiring server data or tables into a part.

Unit/integration/e2e split, snapshot policy, flaky-test quarantine and coverage thresholds: see `references/testing.md` when writing or reviewing tests.

Branch naming, PR template and reviews, CI stages, release train and deploy gates: see `references/git-pr-ci-release.md` when opening a PR, cutting a release or investigating a failed CI stage.

Analytics event naming, performance budgets, bundle-size ceilings and the browser support matrix: see `references/analytics-perf-browsers.md` when adding tracking, or when a perf/size/browser job fails.

Old Tessel 2 APIs, codemod order, the deprecated `components/` folder and known migration gaps: see `references/migration-tessel2.md` when porting 2.x code or running `tessel migrate`.

Best-effort FAQ: common `tessel` errors, entry/boundary/testkit failures and bundle-jump causes: see `references/faq-troubleshooting.md` when a build or command breaks in a way the other sections don't cover.

<!-- sub-skills -->
## Sub-skills (auto-generated, do not edit by hand)

- **build-parts** (`build-parts/`): Use when building or changing a Tessel UI part: covers part, props, strings; excludes token, a11y.

Routing rule: when the task matches one of the sub-skills above, read the SKILL.md in that subdirectory for detailed instructions before acting;
if that sub-skill lists deeper sub-skills, repeat the descent. Load only the documents on the matching path.
<!-- /sub-skills -->
