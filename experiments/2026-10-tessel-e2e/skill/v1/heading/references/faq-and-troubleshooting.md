
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
