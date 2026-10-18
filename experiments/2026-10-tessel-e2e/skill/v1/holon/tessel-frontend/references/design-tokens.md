## Design tokens and styling

_Appended by multiple teams; when in doubt, prefer the newest subsection note and ask in #tessel-platform._

### Token families and token table

Tokens live in `@tessel/core/tokens`. They are emitted as CSS custom properties and typed TS constants. The table below is abridged; generated docs live in Storybook under "Foundations / Tokens".

| Family | Prefix | Example token | Typical use |
| --- | --- | --- | --- |
| Color | `--ts-color-` | `--ts-color-surface-info` | surfaces, text, borders, icons, accents |
| Space | `--ts-space-` | `--ts-space-4` | padding, gaps, margins, layout rhythm |
| Radius | `--ts-radius-` | `--ts-radius-lg` | cards, inputs, pills, overlays |
| Type | `--ts-type-` | `--ts-type-heading-md` | font size, line height, weight, family |
| Layer | `--ts-layer-` | `--ts-layer-modal` | stacking contexts, no raw numbers |

The JSON files under `tokens/src/` are the source of truth. `tessel tokens build` writes `tokens/dist/tokens.css` and `tokens/dist/tokens.ts`. Do not hand-edit generated files.

### Color

Colors are only design tokens through CSS variables, e.g. `var(--ts-color-surface-info)` and `var(--ts-color-text-strong)`. Hex, rgb() and named colors are forbidden in parts; the token linter fails the build.

Semantic names are required in product code: `surface`, `text`, `border`, `icon`, `accent`, `feedback`. Palette names such as `blue-500` are only for token definitions, never for component styles. New semantic tokens need a request in the design-system repo.

Some legacy chart code still contains raw colors behind a feature flag. That exception is tracked by `TESSEL-4187`; new code must not copy it.

### Space, radius, and type

The space scale is a 4px base: `--ts-space-1` = 4px, `--ts-space-2` = 8px, `--ts-space-4` = 16px. Use space tokens for all padding, margin, and gap values. One-off values require a comment explaining why the scale does not fit.

Radius tokens are `--ts-radius-sm`, `--ts-radius-md`, `--ts-radius-lg`, `--ts-radius-pill`. Type tokens combine size, line height, and weight; do not assemble those by hand in components.

```css
.card {
  padding: var(--ts-space-4);
  border-radius: var(--ts-radius-lg);
  color: var(--ts-color-text-strong);
  background: var(--ts-color-surface-info);
}
```

Inline style objects use the same variables as strings, e.g. `style={{ color: "var(--ts-color-text-strong)" }}`.

### Dark mode

Dark mode is not a separate token set in components. The theme root sets `data-ts-theme="dark"`, and the compiled CSS swaps semantic values. Components must use semantic tokens so they work in both themes without branching.

Do not check `useTheme()` to choose colors. Do not pass `isDark` into styled components. The only allowed theme-aware code is for non-color concerns such as illustration selection, and it needs a comment.

### CSS Modules vs inline style

Default to CSS Modules (`*.module.css`) for component styling. This keeps selectors local, allows pseudo-classes and media queries, and keeps token usage visible to the linter.

Inline styles are allowed for dynamic values that cannot be expressed as static CSS: measured positions, virtualized row transforms, CSS variable overrides from props, and third-party integration points. They are not allowed for static padding, color, radius, or typography.

When you must use an inline style, read token values as strings from `@tessel/core/tokens` or write the CSS variable directly. Avoid object spreads that hide token names from review.

### Layers and stacking

Never write a numeric z-index. Banners use `zIndex: "var(--ts-layer-banner)"`; modals use `var(--ts-layer-modal)`.

Layer tokens are ordered by intent, not guessed importance: `--ts-layer-base`, `--ts-layer-dropdown`, `--ts-layer-sticky`, `--ts-layer-banner`, `--ts-layer-modal`, `--ts-layer-toast`, `--ts-layer-tooltip`. New layers need a token file change and a documented relationship.

### Notes from the styling guild

Older docs may call these "theme variables" or "CSS custom properties"; they mean the same thing. If you are migrating a component, start with color and space tokens, then radius and type, then layers. The token linter can be run locally with `tessel lint tokens --fix`; it will not fix raw colors, only report them.

Questions about a missing token go to #tessel-platform, not to a random DM. If a token is genuinely missing, propose a semantic name and include light/dark usage in the request.

