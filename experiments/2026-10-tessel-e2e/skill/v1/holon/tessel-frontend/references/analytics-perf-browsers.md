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
