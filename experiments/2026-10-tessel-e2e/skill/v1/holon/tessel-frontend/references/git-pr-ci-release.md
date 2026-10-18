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
