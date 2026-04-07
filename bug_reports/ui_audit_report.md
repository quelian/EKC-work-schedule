# UI Audit Report - EKC Work Schedule App
**Date:** 2026-04-04
**Scope:** 8 templates + styles.css + embedded styles

---

## Critical Issues

### 1. Three Competing Design Systems
**Severity:** CRITICAL
**Files:** `base_new.html`, `styles.css`, `schedule_gantt_v2.html`, `schedule_editor_enhanced.html`, `calendar_new.html`, `my_schedule.html`

The app has three separate design systems that conflict:

- **Global CSS** (`styles.css`): DM Sans font, `--bg`, `--card`, `--primary`, `--radius-lg` variables
- **base_new.html** inline styles: Inter font, `--apple-blue`, `--apple-gray` variables
- **Embedded `<style>` blocks** in each template: `my_schedule.html` defines its own calendar grid, `schedule_gantt_v2.html` defines a completely different gantt layout, `schedule_editor_enhanced.html` defines its own modal system

This results in pages looking completely different from each other. Gantt uses DM Sans + blue-gray palette; editor uses Inter + apple-blue palette; my_schedule uses Inter but with its own modal/card patterns.

### 2. Login Page Uses Completely Different Layout (base_new.html not extended)
**Severity:** CRITICAL
**Files:** `login.html`, `base_new.html`

`login.html` is a standalone HTML page that does NOT extend `base_new.html`. It has its own `<html>`, `<head>`, `<body>`, and loads Tailwind CDN separately. If the main app changes its sidebar or branding, the login page won't update.

### 3. CSS Variable Duplication and Conflict
**Severity:** CRITICAL
**Files:** `styles.css` (lines 1-29), `schedule_gantt_v2.html` (lines 23-53), `schedule_editor_enhanced.html` (lines 20-26)

Three sets of CSS custom properties:
- Global: `--primary: #2563eb`, `--bg: #e9ecf4`, font `DM Sans`
- Gantt v2: `--blue: #5B8DEF`, `--bg1: #FBFCFE`, no font specification
- Editor enhanced: `--slot-free: #22c55e`, `--slot-busy: #3b82f6` with `Inter` font

Color palettes don't match: blue is `#2563eb`, `#5B8DEF`, `#3b82f6`, `#007AFF` across files.

### 4. Duplicate `.calendar-grid` Class with Different Styles
**Severity:** HIGH
**Files:** `styles.css` (lines 1202-1207), `calendar_new.html` (lines 9-17), `my_schedule.html` (lines 46-50)

Three completely different `.calendar-grid` definitions:
- Global CSS: `min-width: 900px`, 7-column grid, `gap: 10px`
- Calendar page: `gap: 8px`, `padding: 24px`, no min-width
- My schedule: `gap: 8px`, aspect-ratio cells with borders

These are loaded via `<style>` blocks in templates, overriding the global version unpredictably.

### 5. Duplicate Modal Implementations
**Severity:** HIGH
**Files:** `my_schedule.html` (4 modal systems, 10 modals total), `schedule_editor_enhanced.html` (1 modal system), `schedule_gantt_v2.html` (1 modal system), `admin_users.html` (2 modals)

At least 13 modals across 4 files, each with slightly different:
- Backdrop opacity (0.55 vs 0.6)
- Border radius (20px vs varied)
- Animation transforms
- Close button styling
- Header padding patterns

### 6. Duplicate Button Classes
**Severity:** HIGH
**Files:** `base_new.html` (lines 47-73), `schedule_editor_enhanced.html` (lines 581-610), `my_schedule.html` (lines 329-377), `admin_users.html` (lines 8-40)

Four separate `.btn-primary`, `.btn-secondary` definitions:
| File | bg | padding | border-radius | font-weight |
|------|--------|---------|--------------|-------------|
| base_new.html | gradient blue-purple | 12px 24px | 12px | 500 |
| editor_enhanced | gradient apple-purple | 12px 24px | 12px | 500 |
| my_schedule.html | --apple-blue (flat) | 14px 24px | 12px | 600 |
| admin_users.html | none, border 2px #E5E5EA | 10px 20px | 10px | 500 |

---

## Medium Issues

### 7. Broken Responsive Breakpoints
**Severity:** MEDIUM
**Files:** `base_new.html` (line 258: `ml-64 p-8`), `styles.css` (lines 1321-1377)

The sidebar has fixed `width: 260px` (base_new.html line 124) but content area uses hardcoded `ml-64` (Tailwind = 16rem = 256px). These don't match. On resize, the sidebar and content margin overlap.

No mobile responsive breakpoints for the main `base_new.html` layout at all - the sidebar is always visible at 260px, which takes 65% of viewport on 400px screens.

### 8. Emoji in Page Titles and Content
**Severity:** MEDIUM (Accessibility/Consistency)
**Files:** Multiple templates

`base_new.html` uses emoji in sidebar nav items (`:homes:`, `:busts_in_silhouette:`, etc.). Pages use emoji in `{% block page_title %}`:
- `my_schedule.html`: `:calendar:` Моя занятость
- `calendar_new.html`: `:calendar:` Календарь
- `schedule_gantt_v2.html`: No emoji in page_title
- `settings_new.html`: `:gear:` Настройки
- `schedule_editor_enhanced.html`: `Writing:` Редактор графика

Inconsistent emoji usage creates a mixed design language.

### 9. Inconsistent Card Styling
**Severity:** MEDIUM
**Files:** `base_new.html` (lines 35-45), `styles.css` (lines 294-299)

Two `.card` definitions:
- base_new.html: `border-radius: 16px`, `box-shadow: 0 2px 12px`, padding not set
- styles.css: `border-radius: var(--radius-lg)` (16px), `box-shadow: 0 4px 24px`, `padding: 22px 24px`

The base_new inline version wins on pages using templates that extend it, but styles.css applies to pages without inline overrides. Card hover effects (translateY) only exist in base_new.html.

### 10. Duplicate Input Field Styles
**Severity:** MEDIUM
**Files:** `base_new.html` (lines 93-106), `my_schedule.html` (lines 307-321), `schedule_editor_enhanced.html` (lines 555-569), `styles.css` (lines 701-718)

Four variations of `.input-field`:
- base_new: border `#E5E5EA`, padding `12px 16px`, font `15px`
- my_schedule: border `2px solid #E5E5EA`, padding `12px 16px`, border-radius `12px`
- editor: border `2px solid #E5E5EA`, padding `12px 16px`, border-radius `12px`
- styles.css: border `1px solid var(--line)`, padding `13px 14px`, border-radius `14px`

### 11. Legend Inconsistency Across Pages
**Severity:** MEDIUM
**Files:** `calendar_new.html` (lines 153-172), `my_schedule.html` (lines 559-584), `schedule_editor_enhanced.html` (lines 689-710), `schedule_gantt_v2.html` (lines 783-790)

Four legends with different visual encodings for the same concepts:
- Vacation: blue gradient (calendar), green (my_schedule), green (editor), green gradient (gantt)
- Weekend: pink dot (calendar), green dot (my_schedule), yellow chip (editor), not shown (gantt)
- Shift: not in calendar legend, red (my_schedule), blue gradient (editor), red gradient (gantt)

### 12. Missing :focus-visible States in base_new.html
**Severity:** MEDIUM (Accessibility)
**Files:** `base_new.html`, `calendar_new.html`, `schedule_editor_enhanced.html`

Global styles.css has comprehensive `:focus-visible` (lines 155-158) but template inline styles override without adding equivalent focus states. Navigation items, buttons, and modals in templates lack visible focus indicators for keyboard users.

### 13. Toast Notification Duplicates
**Severity:** MEDIUM
**Files:** `my_schedule.html` (lines 1176-1179), `schedule_editor_enhanced.html` (lines 436-465), `schedule_gantt_v2.html` (lines 524-533)

Three different toast implementations:
- my_schedule: inline style, no animation class, display:none/flex toggle
- editor_enhanced: class-based, translateY animation, border-left indicator
- gantt: fixed + class-based, different colors, left border

### 14. Sidebar Does Not Hide on Mobile
**Severity:** MEDIUM
**Files:** `base_new.html`

No `@media` queries in base_new.html at all. The sidebar (260px) + ml-64 content area means content is pushed off-screen on mobile. There's no hamburger menu, no collapsible sidebar, no responsive adjustment.

### 15. Settings Page is Minimal with No Form Action Completeness
**Severity:** LOW-MEDIUM
**Files:** `settings_new.html`

The settings page has toggle switches that submit to `/settings` but no feedback on save success. The "About the system" card uses `gradient-blue` class which is defined but has no hover state or interactive visual indicator.

### 16. Duplicate Toast Icon Usage (Emoji in UI Elements)
**Severity:** LOW
**Files:** Multiple

Toast icons use emoji directly (emoji text content). `my_schedule.html` toast, `schedule_editor_enhanced.html` toast, and `schedule_gantt_v2.html` g-toast all use different icon approaches.

### 17. Admin Users Role Badges Are Identical
**Severity:** LOW (UX)
**Files:** `admin_users.html` (lines 116-124)

Both "Администратор" and "Сотрудник" use the exact same styling: `bg-blue-100 text-blue-800`. They should be visually distinct (e.g., admin = red/orange, employee = blue/green).

### 18. Password Displayed in Plaintext
**Severity:** LOW-UX (visual, not security since it's admin panel)
**Files:** `admin_users.html` (line 127)

Password shown in `<code class="text-sm bg-gray-100">` inline code styling. Looks like a code snippet rather than a credential field. Should use a masked password field with reveal toggle.

---

## Small Issues

### 19. Calendar Scale Transform May Cause Blur
**Severity:** SMALL
**Files:** `calendar_new.html` (line 40), `my_schedule.html` (line 67)

`transform: scale(1.05)` on hover causes sub-pixel rendering blur on some browsers. Should use `transform: translateY(-2px) scale(1.02)` with `will-change` for smoother animation.

### 20. Duplicate `.legend` Classes
**Severity:** SMALL
**Files:** `styles.css` (lines 1157-1162), `calendar_new.html`, `my_schedule.html`, `schedule_editor_enhanced.html`

Five `.legend` definitions across the app, each with different gap values (8px, 16px) and margin settings.

### 21. Hard-coded Year Range in Sidebar
**Severity:** SMALL
**Files:** `base_new.html` (line 243)

`{% for y in range(2026, 2031) %}` should be dynamically calculated to avoid manual updates.

### 22. Font Loading Performance
**Severity:** SMALL
**Files:** `base_new.html` (line 8), `login.html` (line 8), `schedule_gantt_v2.html` (not included)

Inter font loaded from Google Fonts in base_new.html and login.html but schedule_gantt_v2.html doesn't load it (it inherits DM Sans from styles.css). This can cause FOUT (Flash of Unstyled Text) on load.

### 23. Duplicate `.modal-backdrop` and `.modal-content`
**Severity:** SMALL
**Files:** `my_schedule.html` (lines 226-257), `schedule_editor_enhanced.html` (lines 467-502)

Near-identical modal styling defined twice with minor difference in border-radius (20px vs 20px same) and padding (28px vs 28px same). These should be consolidated.

### 24. Card Hover Effect Causes Layout Shift
**Severity:** SMALL
**Files:** `base_new.html` (lines 42-45)

`transform: translateY(-2px)` on card hover changes element position and may cause scroll jitter. Consider using `box-shadow` change only or adding a transparent border to reserve space.

### 25. Missing `aria-label` on Icon-Only Buttons
**Severity:** SMALL (Accessibility)
**Files:** `schedule_gantt_v2.html` (line 16), various

Theme toggle button uses `&#127769;` emoji as content without `aria-label`. Keyboard shortcuts button "?" at line 752 lacks descriptive label.

---

## Recommended Fix Priority

### Phase 1: Eliminate design system duplication
1. Create ONE source of truth for CSS variables (styles.css :root)
2. Remove inline `<style>` blocks from templates or reference shared variables
3. Merge duplicate .btn-primary, .btn-secondary, .input-field, .card, .modal-backdrop
4. Create shared modal component template

### Phase 2: Fix visual inconsistencies
5. Standardize component sizes (padding, border-radius, font-size)
6. Unify legend color mappings across all pages
7. Fix sidebar responsive behavior (hamburger menu for mobile)
8. Fix card hover layout shift

### Phase 3: Accessibility polish
9. Add :focus-visible states to all interactive elements in templates
10. Add aria-labels to icon-only buttons
11. Replace or standardize emoji usage
12. Reduce transform:scale animations that cause blur

### Phase 4: UX improvements
13. Differentiate admin/employee role badges
14. Add save confirmation feedback on settings page
15. Add password mask/reveal toggle
16. Dynamic year range in sidebar
