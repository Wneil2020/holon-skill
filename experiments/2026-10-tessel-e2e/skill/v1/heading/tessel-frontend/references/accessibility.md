
Tessel targets WCAG 2.2 AA for all first-party surfaces. This section is not exhaustive; it is the stuff we keep re-litigating in PR review. If you only read one part, read the subsections on focus and keyboard, because those cause the most regressions.

### Focus management

Overlays, dialogs, popovers, and menus must move focus into the surface when they open, keep it there while open (unless the user explicitly tabs out of a non-modal popover), and restore focus to the trigger on close. Use `FocusScope` from `@tessel/core`; it handles the boring edge cases (nested scopes, iframe boundaries, portalled content) that we kept reimplementing badly. The older `trapFocus` helper is deprecated and will be removed in v5. Do not add new call sites.

Initial focus rules: dialogs focus the first focusable element unless a `data-ts-autofocus` element exists. Menus focus the first item. Tooltips never receive focus. Toasts do not steal focus, ever. If a toast contains an action, it must be reachable by keyboard from the triggering context, not by moving focus.

```tsx
import { FocusScope } from '@tessel/core';

export function InlineEditor({ active, children }) {
  if (!active) return null;
  return (
    <FocusScope initialFocus="[data-ts-autofocus]" restoreFocus>
      <div role="group" aria-label={t('inline-editor')}>{children}</div>
    </FocusScope>
  );
}
```

Focus visible: we rely on `:focus-visible` and the `--ts-focus-ring` token. Do not remove outlines without replacing them with an equivalent ring. The 2023 "clean UI" pass removed outlines from icon buttons and we are still finding places where keyboard users get lost. If you need a custom ring, use `box-shadow: var(--ts-focus-ring)` and keep a transparent outline for Windows High Contrast Mode.

### Keyboard support

Every interactive element must be reachable and operable with a keyboard alone. Use native elements first: `<button>`, `<a>`, `<input>`, `<select>`, `<textarea>`. If you must build a custom widget, follow the ARIA Authoring Practices for that pattern and add tests. `@tessel/testkit` has `keyboard()` and `tabTo()` helpers; use them instead of hand-rolled `fireEvent.keyDown` chains.

Key conventions we standardised on:
- `Enter` and `Space` activate buttons and menu items.
- `Escape` closes the topmost dismissible layer and returns focus.
- Arrow keys move within composite widgets (menus, tabs, radio groups, listboxes).
- `Home` / `End` jump to first / last item in long lists where it makes sense.

Any control that closes or dismisses something must carry `data-ts-dismiss` and an `aria-label` that comes from `t(...)`, never a literal. This is enforced by a lint rule in `@tessel/cli` (`ts-a11y/dismiss-label`). The rule exists because a dismiss control with a hardcoded "Close" cannot be translated and screen reader users hear the wrong language.

### Contrast

Text and meaningful non-text content must meet 4.5:1 (normal text) or 3:1 (large text, UI components, graphical objects). The design tokens in `@tessel/core/theme` are audited quarterly, but token names lie: `--ts-gray-500` passed on white in v3, fails in v4, and is now only for dark surfaces. Do not use raw hex values in component code. If you need a one-off, add a token with a comment and ping #tessel-design-system.

Focus rings, hover states, and selected states count as UI components. Disabled controls are exempt from contrast but must still be distinguishable from enabled ones by more than colour alone. The "muted" text token is for de-emphasised metadata, not for placeholder text in forms; placeholders should use `--ts-text-subtle` and still meet 4.5:1 in the default theme.

### Screen reader testing

We do not have a dedicated a11y QA team. Teams are expected to test their own surfaces with at least one screen reader before marking a PR ready. The supported matrix is:
- NVDA + Firefox on Windows (primary)
- VoiceOver + Safari on macOS and iOS (primary)
- JAWS + Chrome on Windows (best effort; run before major releases)
- TalkBack on Android (best effort)

Orca and Windows Narrator are not supported; if a contributor fixes something for them, great, but do not block on it. Automated checks (`axe-core` via `@tessel/testkit`) catch maybe 30% of issues. They will not catch missing labels on custom widgets, focus order weirdness, or live region chatter. Manual passes are still required for anything with `role="dialog"`, `role="menu"`, `role="tablist"`, or `aria-live`.

When filing an a11y bug, include: screen reader + version, browser + version, OS, the exact steps, and whether it reproduces in the Tessel docs sandbox. "It doesn't work with VoiceOver" is not actionable.

### Notes and legacy

- 2021-03: We removed the `aria-hidden` polyfill for IE11. Do not re-add it.
- 2022-08: `:focus-visible` is now baseline; the `.ts-focus-ring` utility class is deprecated.
- 2023-05: The `SkipLink` component moved from `@tessel/core` to `@tessel/core/a11y`. Update imports.
- TODO: consolidate `useReturnFocus` and `useRestoreFocus`; they do the same thing with different argument order.
- If you find a rule here that contradicts an RFC, the RFC wins, but please update this file.

