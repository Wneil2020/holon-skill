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
