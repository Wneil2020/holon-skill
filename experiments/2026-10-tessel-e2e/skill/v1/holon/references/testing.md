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
