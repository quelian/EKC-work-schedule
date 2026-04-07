# Design Proposal: Visual Design Overhaul

## EKC Work Schedule App -- Visual Design Review

**Author:** Designer #1 (Visual Designer)
**Date:** 2026-04-04
**Scope:** Color palette, typography, spacing, animations, iconography, dark theme, visual hierarchy

---

## Executive Summary

The app has a solid foundation: Apple-inspired colors in `base_new.html`, a separate but functional design system in `styles.css`, and a rich Gantt editor with its own theming. The core problem is not the quality of individual design decisions but their **coexistence without coordination**. Three independent CSS color systems, two font families, duplicated modal styles, and emoji-only iconography create visual inconsistency across pages.

This proposal addresses 7 visual design areas with specific, actionable recommendations.

---

## 1. Color Palette & Theme System

### Current State

Three disconnected color systems:


| System        | Location                 | Primary Blue | Status Colors                   |
| ------------- | ------------------------ | ------------ | ------------------------------- |
| Apple tokens  | `base_new.html`          | `#007AFF`    | `#34C759`, `#FF3B30`, `#FF9500` |
| Gantt tokens  | `schedule_gantt_v2.html` | `#5B8DEF`    | `#6DCB8A`, `#F36A6A`, `#F6B45E` |
| Legacy tokens | `styles.css`             | `#2563eb`    | `#059669`, `#c53030`, `#b45309` |


Additionally, `base_new.html` gradients use `#E3F2FD`/`#BBDEFB` (Material-like) while dark theme Gantt uses `#121827` background with no coordination to the light theme.

### Proposal: Unified Design Token System

Adopt a single, semantic token system anchored to the Apple palette (already the dominant visual language in `base_new.html`). All values defined once as CSS custom properties on `:root`, with `.dark-theme` overriding only what changes.

```css
:root {
  /* --- Neutral scale (Apple-inspired) --- */
  --color-bg:         #F5F5F7;   /* was apple-bg */
  --color-surface:    #FFFFFF;
  --color-surface-2:  #F2F2F7;   /* was apple-light-gray */
  --color-border:     #E5E5EA;
  --color-border-2:   #D1D1D1;
  --text-primary:     #1D1D1F;   /* near-black Apple gray */
  --text-secondary:   #6E6E73;   /* Apple secondary */
  --text-tertiary:    #8E8E93;   /* was apple-gray */

  /* --- Semantic colors (Apple originals) --- */
  --color-blue:   #007AFF;
  --color-blue-soft: #E3F2FD;
  --color-green:  #34C759;
  --color-green-soft: #E8F5E9;
  --color-orange: #FF9500;
  --color-orange-soft: #FFF3E0;
  --color-red:    #FF3B30;
  --color-red-soft: #FFECEC;
  --color-purple: #AF52DE;
  --color-purple-soft: #F3E5F5;

  /* --- Functional aliases --- */
  --color-primary:   var(--color-blue);
  --color-success:   var(--color-green);
  --color-warning:   var(--color-orange);
  --color-danger:    var(--color-red);

  /* --- Gradients --- */
  --gradient-primary:   linear-gradient(135deg, #007AFF, #5856D6);
  --gradient-success:   linear-gradient(135deg, #34C759, #30D158);
  --gradient-danger:    linear-gradient(135deg, #FF3B30, #FF453A);
  --gradient-surface-1: linear-gradient(135deg, #E3F2FD, #BBDEFB);
  --gradient-surface-2: linear-gradient(135deg, #E8F5E9, #C8E6C9);
  --gradient-surface-3: linear-gradient(135deg, #FFF3E0, #FFE0B2);
  --gradient-surface-4: linear-gradient(135deg, #F3E5F5, #E1BEE7);
  --gradient-surface-5: linear-gradient(135deg, #FCE4EC, #F8BBD0);

  /* --- Shadows --- */
  --shadow-sm:  0 1px 4px rgba(0, 0, 0, 0.04);
  --shadow-md:  0 2px 12px rgba(0, 0, 0, 0.06);
  --shadow-lg:  0 4px 20px rgba(0, 0, 0, 0.08);
  --shadow-xl:  0 8px 32px rgba(0, 0, 0, 0.12);

  /* --- Radii --- */
  --radius-sm: 8px;
  --radius-md: 10px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  --radius-2xl: 20px;

  /* --- Transitions --- */
  --ease: cubic-bezier(0.4, 0, 0.2, 1);
  --duration-fast: 150ms;
  --duration-base: 200ms;
  --duration-slow: 300ms;
}

.dark-theme {
  --color-bg:         #0A0A0A;   /* pure dark for OLED, not navy */
  --color-surface:    #1C1C1E;   /* Apple card-bg dark */
  --color-surface-2:  #2C2C2E;
  --color-border:     #38383A;
  --color-border-2:   #48484A;
  --text-primary:     #F5F5F7;
  --text-secondary:   #98989D;
  --text-tertiary:    #636366;

  /* Semantic colors stay saturated in dark mode */
  --color-blue-soft:   rgba(0, 122, 255, 0.15);
  --color-green-soft:  rgba(52, 199, 89, 0.15);
  --color-orange-soft: rgba(255, 149, 0, 0.15);
  --color-red-soft:    rgba(255, 59, 48, 0.15);
  --color-purple-soft: rgba(175, 82, 222, 0.15);

  --shadow-sm:  0 1px 4px rgba(0, 0, 0, 0.2);
  --shadow-md:  0 2px 12px rgba(0, 0, 0, 0.3);
  --shadow-lg:  0 4px 20px rgba(0, 0, 0, 0.4);
  --shadow-xl:  0 8px 32px rgba(0, 0, 0, 0.5);
}
```

**Key decisions:**

- **Use `#0A0A0A` for dark mode background**, not `#121827` (Gantt) or a navy tone. Near-black neutral dark reads as premium and matches Apple's own dark palette. Colored dark bg (navy/indigo) makes the app feel like a different product from the light version.
- **Keep semantic colors at Apple saturation** in dark mode. Many apps desaturate accent colors for dark theme, but this makes them hard to see. Use opacity-based soft variants (e.g. `rgba(0, 122, 255, 0.15)`) instead of lighter, washed-out hex values.
- **Replace `styles.css` `--primary: #2563eb`** and Gantt `--blue: #5B8DEF` with `var(--color-blue)` (`#007AFF`). The Apple blue is more vibrant and already used in the navigation, buttons, and logo.
- **Unify `border-radius` values** to a scale: 8/10/12/16/20. Currently `base_new.html` uses 16px cards + 12px buttons + 10px inputs, while `styles.css` uses the same 16/12/10 but as separate named variables.

**Where to put it:** Create `app/static/tokens.css` and include it in `base_new.html` before the existing `<style>` block. All other templates reference `base_new.html`, so the tokens cascade. Inline CSS in templates should be migrated to reference `var(--color-*)` tokens.

---

## 2. Typography Improvements

### Current State

- `base_new.html`: Inter font from Google Fonts (light, regular, medium, semibold, bold)
- `styles.css`: DM Sans font with different fallbacks
- No type scale is defined; heading sizes are scattered: `text-3xl`, `text-2xl`, `text-lg`, `text-xl`, `text-sm` (mix of Tailwind utilities and custom)
- Body text has no explicit `line-height` set in the template styles (relies on Tailwind defaults)

### Proposal

**Unify to Inter only.** Remove the DM Sans reference in `styles.css`. Inter is:

- Designed specifically for UI text (better legibility at small sizes than DM Sans)
- Already loaded in `base_new.html`
- Matches Apple's design language more closely (SF Pro alternative for the web)
- Has excellent Cyrillic support (critical for this Russian-language app)

Add explicit type scale:

```css
/* --- Type Scale --- */
--text-xs:   0.75rem;    /* 12px - badges, labels */
--text-sm:   0.8125rem;  /* 13px - helper text, secondary info */
--text-base: 0.9375rem;  /* 15px - body text (current app standard) */
--text-md:   1rem;       /* 16px - inputs, prominent body */
--text-lg:   1.125rem;   /* 18px - card titles, section headings */
--text-xl:   1.375rem;   /* 22px - page subtitle area */
--text-2xl:  1.75rem;    /* 28px - page title */
--text-3xl:  2.125rem;   /* 34px - dashboard hero numbers */
```

**Line height scale:**

```css
--leading-tight:  1.2;   /* headings */
--leading-base:   1.5;   /* body text */
--leading-relaxed: 1.65; /* long-form, descriptions */
```

**Font weight usage guidelines:**


| Weight         | Use                                         |
| -------------- | ------------------------------------------- |
| 400 (Regular)  | Body text, form inputs                      |
| 500 (Medium)   | Buttons, labels, navigation items, badges   |
| 600 (Semibold) | Card titles, section headings, stat numbers |
| 700 (Bold)     | Page title, logo                            |


**Font loading optimization:** Add `display=swap` (already present) and `&subset=cyrillic,cyrillic-ext` to the Google Fonts URL to reduce download size:

```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap&subset=cyrillic,cyrillic-ext,latin" rel="stylesheet">
```

Consider reducing to 3 weights (400/500/600) instead of 5 if 300 (Light) and 700 (Bold) are rarely used -- this reduces font payload.

---

## 3. Spacing & Padding Consistency

### Current State

Spacing is scattered across inline styles, Tailwind utility classes, and custom CSS with no coordination:

- `base_new.html`: sidebar padding `p-6`, header `mb-8`, content `p-8`
- `schedule_gantt_v2.html`: its own grid and gap system
- `styles.css`: BEM-style spacing with hardcoded px values
- Card inner padding: `20px` (stat-card), `p-6`/24px (cards), varies by component

### Proposal

**Adopt a 4px spacing scale**, codified as tokens:

```css
--space-1:  4px;
--space-2:  8px;
--space-3:  12px;
--space-4:  16px;
--space-5:  20px;
--space-6:  24px;
--space-8:  32px;
--space-10: 40px;
--space-12: 48px;
--space-16: 64px;
```

**Standardize component spacing:**


| Component         | Padding                         | Gap                                      | Margin-bottom    |
| ----------------- | ------------------------------- | ---------------------------------------- | ---------------- |
| Card              | `var(--space-6)` (24px)         | `var(--space-4)` between elements        | `var(--space-8)` |
| Stat card         | `var(--space-5)` (20px)         | --                                       | `var(--space-4)` |
| Form section      | `var(--space-4)`                | `var(--space-3)` vertical between fields | `var(--space-6)` |
| Page header       | `var(--space-8)` bottom         | --                                       | --               |
| Page content area | `var(--space-8)` top padding    | --                                       | --               |
| Modal body        | `var(--space-6)` padding        | `var(--space-4)`                         | --               |
| Table cells       | `var(--space-3) var(--space-6)` | --                                       | --               |
| Sidebar nav items | `var(--space-2)` gap            | --                                       | --               |


**Section gap rule:** Replace ad-hoc `mb-6`, `mb-8`, `mt-4` etc. with a consistent rule: sibling cards/sections have `gap: var(--space-8)` (32px) between them. Use CSS `:has()` or Tailwind's `space-y-8` for parent-level spacing.

---

## 4. Animation Refinements

### Current State

- `base_new.html`: single `fadeIn` animation (opacity 0->1, translateY 10px->0)
- Page transition: body opacity to 0.7 for 300ms on link click
- `schedule_gantt_v2.html`: rich animation set (spin, shiftSlideIn/Out, tooltipFadeIn, pulse-red, skeleton)
- No standard transition durations -- `0.2s`, `0.3s`, `ease`, `ease-out` mixed
- The page transition (`body.opacity = 0.7`) is jarring -- it flashes the entire page

### Proposal

**Keep the Gantt's richer animation set; expand it app-wide.** The Gantt editor has the most polished micro-interactions. Extract them into shared tokens.

```css
/* --- Animation Presets --- */
--animation-fade-in: fadeIn 0.4s ease-out both;
--animation-slide-up: slideUp 0.35s var(--ease) both;
--animation-scale-in: scaleIn 0.25s var(--ease) both;
--animation-slide-in-right: slideInRight 0.3s var(--ease) both;

@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}

@keyframes scaleIn {
  from { opacity: 0; transform: scale(0.95); }
  to   { opacity: 1; transform: scale(1); }
}

@keyframes slideInRight {
  from { opacity: 0; transform: translateX(12px); }
  to   { opacity: 1; transform: translateX(0); }
}
```

**Staggered card entrance:** When multiple cards appear simultaneously, stagger them with incrementing `animation-delay`:

```css
.card:nth-child(1) { animation-delay: 0ms; }
.card:nth-child(2) { animation-delay: 50ms; }
.card:nth-child(3) { animation-delay: 100ms; }
.card:nth-child(4) { animation-delay: 150ms; }
```

**Replace page flash transition.** The current `body.opacity = 0.7` transition on every link click is distracting. Replace with a subtle content-area fade:

```js
// Replace:
document.body.style.opacity = '0.7';

// With:
const main = document.querySelector('main');
if (main) {
  main.style.transition = 'opacity 200ms ease';
  main.style.opacity = '0';
}
```

**Modal entrance animation:** Apply `scaleIn` + `fade-in` to modal backdrops and `slideUp` to modal content. The current modals just appear (`hidden` class toggle) without transitions.

```css
.modal-backdrop {
  transition: opacity 200ms var(--ease);
}
.modal-content {
  transition: opacity 250ms var(-- ease), transform 250ms var(--ease);
}
```

**Hover states:** Keep subtle transforms but cap at `translateY(-2px)`. The current `scale(1.02)` on stat cards and `translateY(-2px)` on cards are fine. Ensure all hover transforms are paired with matching `transition: transform var(--duration-base) var(--ease)`.

**Reduce motion support:** Add `@media (prefers-reduced-motion: reduce)` block to disable animations for users who prefer it:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 5. Iconography

### Current State

100% emoji-based icons:

- Navigation: emoji (home, users, calendar, etc.)
- Stats cards: emoji
- Modal headers: emoji
- Alerts: emoji (checkmark/x)
- Warnings: emoji

**Problems:**

- Emojis render differently across OS/browsers (macOS vs Linux emoji differ significantly)
- No size control -- emoji size depends on font-size
- No theming -- emoji colors cannot adapt to dark theme
- Lack of visual weight consistency with the text
- Professional tone mismatch with the otherwise polished Apple aesthetic

### Proposal

**Hybrid approach: SVG icons in the navigation and key UI, keep emoji only for user-generated content (vacation notes, etc.).**

Primary recommendation: **Inline SVG icons** (no extra library needed). Use a single shared set of lightweight SVG sprites for the 10-15 icons used in navigation and core UI.

Navigation icon mapping:


| Current            | Proposed Icon                                                                       |
| ------------------ | ----------------------------------------------------------------------------------- |
| home               | `M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10 0h3a1 1 0 001-1v-5a1 1 0 00-1-1h-3` |
| users/users, group | Heroicon `UserGroup`                                                                |
| calendar           | Heroicon `CalendarDays`                                                             |
| chart              | Heroicon `ChartBar`                                                                 |
| pencil             | Heroicon `PencilSquare`                                                             |
| vacation           | Heroicon `Sun`                                                                      |
| settings           | Heroicon `Cog6Tooth`                                                                |
| user               | Heroicon `User`                                                                     |
| logout             | Heroicon `ArrowRightEndOnRectangle`                                                 |
| key/password       | Heroicon `Key`                                                                      |
| clipboard          | Heroicon `ClipboardDocumentList`                                                    |


**Implementation:** Define SVG sprites once in `base_new.html` (invisible `<svg>` with `<symbol>` elements), then reference with `<svg><use href="#icon-home"></use></svg>`. This adds zero HTTP requests.

**Icon sizing:**

```css
.icon {
  width: 20px;
  height: 20px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.nav-item .icon {
  color: inherit;
}

.nav-item.active .icon {
  color: white;
}
```

**Fallback while migrating:** If migrating all emojis to SVGs feels like too big a jump, start with navigation and page headers. Keep emoji in content areas (alerts, table cells) where they function more as status indicators than navigation icons.

---

## 6. Dark Theme Enhancements

### Current State

Dark theme exists only in `schedule_gantt_v2.html`:

- `.dark-theme` class defined with dark backgrounds
- Gantt uses `--bg1: #121827`, `--bg2: #1A2035` (navy-tinted)
- No dark theme support in `base_new.html`, `styles.css`, or any other template
- Theme toggle mechanism is per-page, not global

**Issues:**

- Navy/dark-blue dark mode (`#121827`) clashes with the Apple clean aesthetic
- No dark theme on the app shell (sidebar remains white)
- Switching pages loses the dark theme state
- Gradient backgrounds in light mode have no dark equivalent

### Proposal

**Implement app-wide dark theme** using the token system from Section 1.

**Sidebar in dark mode:** Instead of white glass, use dark surface with reduced backdrop-blur:

```css
.dark-theme .sidebar {
  background: rgba(28, 28, 30, 0.95);
  border-right-color: var(--color-border);
}

.dark-theme .glass {
  background: rgba(28, 28, 30, 0.85);
  backdrop-filter: blur(16px);
}
```

**Dark mode gradients:** Replace light pastel gradients with darker, lower-contrast alternatives:

```css
.dark-theme .gradient-blue {
  background: linear-gradient(135deg, rgba(0, 122, 255, 0.2), rgba(0, 122, 255, 0.08));
}
.dark-theme .gradient-green {
  background: linear-gradient(135deg, rgba(52, 199, 89, 0.2), rgba(52, 199, 89, 0.08));
}
/* etc. */
```

**Or better:** Drop gradient backgrounds on stat cards in dark mode entirely. Use flat surface colors with colored borders:

```css
.dark-theme .stat-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
}
.dark-theme .stat-card.stat--blue {
  border-color: var(--color-blue);
  border-left: 3px solid var(--color-blue);
}
```

This reads cleaner on dark backgrounds and avoids the muddy look that pastel gradients create on dark surfaces.

**Persistent theme state:** Store theme preference in `localStorage` and apply on page load:

```js
// Apply on every page load, before paint
(function() {
  const theme = localStorage.getItem('theme');
  if (theme === 'dark') {
    document.documentElement.classList.add('dark-theme');
  }
})();
```

**Theme toggle in sidebar:** Add a sun/moon icon button at the bottom of the sidebar, above the user info section. This makes the theme available from every page, not just the Gantt editor.

---

## 7. Visual Hierarchy

### Current State

- Page titles use `text-3xl font-bold` everywhere (same size for dashboard and settings)
- No consistent heading hierarchy (h2 vs h3 sizing varies)
- Alert banners use emoji prefixes and inconsistent sizing
- Table row heights, badge sizes, and button sizes lack a clear scale
- The sidebar is visually heavy -- 260px with glass effect competes with content
- Stat cards use colored gradient backgrounds which draw attention equally (no emphasis hierarchy)

### Proposal

**Establish a clear 3-tier content hierarchy:**

**Tier 1 -- Page-level (most emphasis):**

- Page title: `text-3xl` / `34px` / `font-weight: 700` / `color: var(--text-primary)`
- Page subtitle: `text-base` / `15px` / `font-weight: 400` / `color: var(--text-secondary)`
- Header area bottom margin: `var(--space-8)` (32px)

**Tier 2 -- Section-level:**

- Section title: `text-lg` / `18px` / `font-weight: 600` / `color: var(--text-primary)`
- Section subtitle: `text-sm` / `13px` / `color: var(--text-secondary)`
- Section spacing: `var(--space-8)` between sections

**Tier 3 -- Component-level:**

- Card title: `text-md` / `16px` / `font-weight: 600`
- Labels: `text-sm` / `13px` / `font-weight: 500` / `color: var(--text-secondary)`
- Helper text: `text-xs` / `12px` / `color: var(--text-tertiary)`

**Emphasis through color, not size:** The current stat cards all use large gradient backgrounds, making every one equally "loud." Alternative for dashboard:

- Keep one "hero" stat with a gradient background or colored accent
- Render secondary stats with flat backgrounds + left color border + colored icon
- This creates natural eye flow: hero stat first, then supporting data

```css
.stat-card--hero {
  background: var(--gradient-primary);
  color: white;
}

.stat-card--secondary {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-left: 3px solid var(--color-primary);
}
```

**Table visual hierarchy:**

- Header row: `text-xs uppercase` / `font-weight: 500` / `color: var(--text-tertiary)` / `bg: var(--color-surface-2)`
- Body rows: `text-sm` / `color: var(--text-primary)`
- Important cells (names, totals): `font-weight: 500`
- Badge/column data: use color-coded chips instead of plain text

**Alert/alert hierarchy:**

- Error: red left border + light red background + error icon
- Warning: orange left border + light orange background
- Success: green left border + light green background
- Info: blue left border + light blue background

Replace current full-background colored alerts with left-border-accent pattern. This is less visually noisy and scales better in dark mode.

```css
.alert {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  border-left: 3px solid var(--alert-color, var(--color-blue));
  background: var(--alert-bg, var(--color-blue-soft));
  color: var(--alert-text, var(--color-blue));
}
```

**Sidebar visual weight reduction:**

- Current: 260px with glass backdrop is heavy, competes with content
- Keep the 260px width but reduce visual weight:
  - Remove the glass effect on the sidebar; use flat `var(--color-surface)` in light mode
  - Use `--text-secondary` for inactive nav items, `--color-primary` for active (not background fill)
  - Active state: left border indicator + text color change, no background color block
  - This makes the sidebar recede and the main content area dominate

```css
.nav-item {
  position: relative;
  padding-left: var(--space-4);
  color: var(--text-secondary);
}

.nav-item.active {
  color: var(--color-primary);
  background: transparent;
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: var(--color-primary);
  border-radius: 2px;
}
```

---

## Priority Order for Implementation

1. **Token system** (Section 1) -- foundational, everything else depends on it
2. **Typography** (Section 2) -- quick win, remove DM Sans, add type scale
3. **Dark theme** (Section 6) -- high user value, requires tokens from step 1
4. **Visual hierarchy** (Section 7) -- affects perceived quality immediately
5. **Spacing** (Section 3) -- polish, can be done incrementally
6. **Animations** (Section 4) -- incremental, extract from Gantt
7. **Iconography** (Section 5) -- most work, highest visual return, can be phased

---

## Files to Create/Modify


| Action     | File                                          | Description                                                         |
| ---------- | --------------------------------------------- | ------------------------------------------------------------------- |
| **CREATE** | `app/static/tokens.css`                       | Unified design tokens (colors, spacing, shadows, radii, animations) |
| **MODIFY** | `app/static/styles.css`                       | Switch to CSS tokens, drop DM Sans, unify color refs                |
| **MODIFY** | `app/templates/base_new.html`                 | Include `tokens.css`, drop inline `:root` vars, apply token refs    |
| **MODIFY** | `app/templates/schedule_gantt_v2.html`        | Reference token vars instead of its own color system                |
| **MODIFY** | `app/templates/schedule_editor_enhanced.html` | Same -- use token references for colors                             |
| **MODIFY** | `app/templates/my_schedule.html`              | Same -- use token references                                        |
| **MODIFY** | All other templates                           | Use consistent type scale, spacing, alert styles                    |


