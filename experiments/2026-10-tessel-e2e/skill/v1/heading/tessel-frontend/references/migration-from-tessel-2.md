
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

