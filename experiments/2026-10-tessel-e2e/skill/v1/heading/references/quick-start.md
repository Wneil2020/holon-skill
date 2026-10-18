
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

