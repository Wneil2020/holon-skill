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
