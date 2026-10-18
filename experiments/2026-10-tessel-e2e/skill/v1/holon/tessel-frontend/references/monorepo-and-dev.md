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

