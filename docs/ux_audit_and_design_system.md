# UX Audit and Design System - EKZ Grafik

---

## Table of Contents

1. [Per-Page UX Audit](#per-page-ux-audit)
   - [login.html](#loginhtml)
   - [home_new.html](#home_newhtml)
   - [employees_new.html](#employees_newhtml)
   - [schedule_new.html](#schedule_newhtml)
   - [schedule_editor_enhanced.html](#schedule_editor_enhancedhtml)
   - [schedule_gantt_v2.html](#schedule_gantt_v2html)
   - [my_schedule.html](#myschedulehtml)
   - [constraints_new.html](#constraints_newhtml)
   - [calendar_new.html](#calendar_newhtml)
   - [vacations.html](#vacationshtml)
   - [admin_users.html](#admin_usershtml)
   - [settings_new.html](#settings_newhtml)
   - [select_employee.html](#select_employeehtml)
   - [change_password.html](#change_passwordhtml)
   - [base_new.html](#base_newhtml)
2. [Global UI Inconsistencies](#global-ui-inconsistencies)
3. [Visual Design Audit](#visual-design-audit)
4. [Mobile & Responsive Audit](#mobile--responsive-audit)
5. [Interaction Design Audit](#interaction-design-audit)
6. [Accessibility Audit](#accessibility-audit)
7. [Specific Improvement Recommendations](#specific-improvement-recommendations)
8. [Apple-Style Design System](#apple-style-design-system)
   - [Design Tokens](#design-tokens)
   - [Component CSS Specifications](#component-css-specifications)
   - [Responsive Breakpoints](#responsive-breakpoints)
   - [Animation Timings](#animation-timings)
   - [Utility Class System](#utility-class-system)

---

---

## Per-Page UX Audit

---

### login.html

**File:** `app/templates/login.html` | **Lines:** 123 | **Status:** Standalone (no base inheritance)

#### UX Problems

| Severity | Issue | Location |
|---|---|---|
| **HIGH** | Select element is auto-focused, but users would benefit more from focusing the password field after selecting an employee | line 97 |
| **HIGH** | Password visibility toggle missing — users must carefully retype if they mistype password | lines 106-112 |
| **MED** | No "forgot password" recovery flow — user permanently locked out if password is lost | lines 94-112 |
| **MED** | "Administrator" option hardcoded as a select option rather than a separate auth path | line 102 |
| **MED** | Employee dropdown is not searchable — with 15+ employees, scrolling is slow | line 97 |
| **LOW** | Hardcoded `<style>` block (67 lines) duplicates global CSS tokens | lines 9-67 |
| **LOW** | No loading/disabled state on submit button — user could double-click | line 114 |
| **LOW** | Empty required asterisk span (`class="form-label--required"`) renders nothing visible | line 109 |

#### UI Observations

Good: Clean centered layout with proper whitespace. Uses global `.card`, `.alert`, `.input`, `.btn` component classes. Gradient logo text (lines 28-32) is well-executed. The login form flow is clear and straightforward.

#### Specific Recommendations (P1)

1. Add password visibility toggle (eye icon) using inline SVG
2. Add search/filter to employee dropdown or replace with typeahead
3. Add "Забыли пароль?" link that directs to admin password reset
4. Show loading spinner and disable button during form submission
5. Move inline styles to global CSS under `.login-page` / `.login-card` namespaces

---

### home_new.html

**File:** `app/templates/home_new.html` | **Lines:** 128 | **Status:** Extends `base_new.html`

#### UX Problems

| Severity | Issue | Location |
|---|---|---|
| **HIGH** | Uses emoji icons throughout (lines 23, 33, 43, 53, 60, 69, 84, 99) instead of SVG icon system | multiple |
| **HIGH** | Stat cards use gradient backgrounds (`gradient-blue`, `gradient-green`, `gradient-orange`) — Apple style favors flat white cards with subtle shadows | lines 16, 26, 36, 46 |
| **MED** | "Смен назначено" and "Предупреждений" stat cards share the same `gradient-orange` — visually ambiguous | lines 36, 46 |
| **MED** | Coverage rules grid uses Tailwind utility classes (`bg-blue-50`, `text-sm`, `bg-pink-50`, `bg-gray-50`) not defined in `styles.css` | lines 101-125 |
| **MED** | Warnings truncated to 5 with no "show all" expand/collapse | line 82 |
| **LOW** | Warnings severity colors reference Tailwind classes (`border-red-500`, `border-orange-500`) not in global CSS | line 83 |
| **LOW** | No empty state when warnings count is 0 — section just hidden silently |
| **LOW** | Stat cards are non-interactive — could link to relevant section | lines 15-55 |
| **LOW** | Coverage rules are hardcoded HTML, not dynamically derived from actual rules | lines 98-126 |

#### Specific Recommendations (P1)

1. Replace gradient stat cards with flat white cards + SVG icon accents (Apple Calendar style)
2. Assign unique colors to each stat card (teal for warnings instead of orange)
3. Add "Показать все" link when warnings exceed 5
4. Add empty state message: "Предупреждений нет — график корректен" when warnings are 0
5. Replace Tailwind classes with design system CSS

---

### employees_new.html

**File:** `app/templates/employees_new.html` | **Lines:** 819 | **Status:** Extends `base_new.html`

#### UX Problems

| Severity | Issue | Location |
|---|---|---|
| **CRITICAL** | Own modal implementation (`.modal-backdrop`, `.modal-content`, `.modal-header`, etc.) conflicts with base ModalSystem | lines 96-380 |
| **CRITICAL** | Second duplicate modal system using `.modal-overlay` vs `.modal-backdrop` — two different class names for the same concept in one file | lines 352-380 vs 96-132 |
| **CRITICAL** | Own `.btn-secondary`, `.btn-danger`, `.btn-submit`, `.btn-cancel` override global `.btn` BEM system with different padding, radius, colors | lines 298-349 |
| **HIGH** | Three separate modals (add employee, edit employee, add vacation) with duplicated form CSS | lines 512-688 |
| **HIGH** | `employeesData` JS object (lines 718-727) with inline Jinja template escaping — fragile, breaks with special characters beyond simple apostrophe replacement |
| **HIGH** | Adjustment control (+/- 1 only) does not allow custom values — user must click many times | lines 746-751 |
| **HIGH** | Adjustment triggers full page reload — visible flicker, not optimistic UI | lines 746-751 |
| **MED** | Header action buttons use `.btn-primary` with inline color overrides (`bg-green-500`) | lines 9, 12 |
| **MED** | `.btn-submit` gradient (`#667eea` to `#764ba2`) does NOT match the Apple blue used anywhere else | line 337 |
| **MED** | Employee cards show too much information — name, role, hours, vacation, adjustment badges all at once | lines 380-512 |
| **MED** | "Инфа для графика" is informal Russian inconsistent with formal tone elsewhere | line 485 |
| **LOW** | Trash icon "Delete" for deactivation — destructive semantics but is actually soft deactivation | line 493 |

#### Specific Recommendations (P0)

1. Migrate all modals to base_new.html ModalSystem
2. Remove duplicate `.btn-submit` gradient — use `.btn--primary`
3. Allow custom adjustment values with direct input, not just +/- buttons
4. Make adjustment update use fetch + DOM patch (no page reload)

#### Specific Recommendations (P1)

5. Redesign employee cards: show key info, expand on click/tap for details
6. Add search/filter bar for employees
7. Replace inline styles with design system components
8. Change "Инфа для графика" to "Информация для графика"

---

### schedule_new.html

**File:** `app/templates/schedule_new.html` | **Lines:** 128 | **Status:** Extends `base_new.html`

#### UX Problems

| Severity | Issue | Location |
|---|---|---|
| **HIGH** | For admin users, the entire page is just a card with "open editor" link — no actual schedule data visible | lines 17-27 |
| **MED** | Stat cards use emoji for icons (lines 37, 47, 57, 67) | multiple |
| **MED** | Shift type badges: both "Тренер" and "Оператор" use identical styling (`bg-blue-100 text-blue-800`) — should be visually distinct | lines 103, 107 |
| **LOW** | "Выходной" / "Будний" rendered as plain text, not styled badges | lines 95-98 |
| **LOW** | No visual indicator of hours worked vs norm — employee cannot see if they're ahead/behind |

#### Specific Recommendations (P1)

1. For admin: show summary of all employees' schedules or redirect to editor
2. Distinguish "Тренер" (purple) and "Оператор" (blue) badges with different colors
3. Add hours progress bar to schedule view
4. Replace emoji with SVG icons

---

### schedule_editor_enhanced.html

**File:** `app/templates/schedule_editor_enhanced.html` | **Lines:** 1477 | **Status:** Extends `base_new.html`

#### UX Problems

| Severity | Issue | Location |
|---|---|---|
| **CRITICAL** | Own `<style>` block (~665 lines) with own `.modal-backdrop`, `.modal-content`, `.btn-primary`, `.btn-secondary` | lines 18-683 |
| **CRITICAL** | No touch support for drag-and-drop — completely broken on mobile/tablet | |
| **HIGH** | Utility classes defined in `<style>` (`.mb-4`, `.mt-6`, `.flex`, `.flex-1`, `.gap-3`, `.items-center`) — Tailwind-like utilities that duplicate global patterns | lines 612-634 |
| **HIGH** | View mode labels confusing: "По дням" vs "По времени" — naming does not clearly describe the difference | |
| **MED** | Color variables in `:root` (`--slot-free: #22c55e`, `--slot-busy: #3b82f6`, etc.) use Tailwind colors, not design system tokens | lines 21-26 |
| **MED** | Validation/conflict feedback is visual-only (red highlighting) — no `aria-live` announcement for screen readers | |
| **MED** | Legend uses emoji throughout (lines 690-709) | lines 689-710 |
| **MED** | Preset times hardcoded (08:00, 09:00, 18:00, 21:00) — not configurable without code change |
| **LOW** | Missing undo/redo for schedule changes |
| **LOW** | No bulk selection mode for assigning same pattern to multiple employees |

#### Specific Recommendations (P1)

1. Add touch event handlers alongside mouse drag events (touchstart/touchmove/touchend)
2. Rename view modes to "Таблица" and "Диаграмма" for clarity
3. Move color variables to use design system tokens
4. Add aria-live regions for conflict warnings
5. Missing: Undo/redo stack using Command pattern
6. Missing: Bulk select for multi-employee assignment

---

### schedule_gantt_v2.html

**File:** `app/templates/schedule_gantt_v2.html` | **Lines:** 2396 | **Status:** Extends `base_new.html`

#### UX Problems

| Severity | Issue | Location |
|---|---|---|
| **CRITICAL** | ~2400 lines in a single template — the single largest page, extremely difficult to maintain | entire file |
| **CRITICAL** | Own complete component system (buttons, modals, tooltips, dark theme overrides) | |
| **CRITICAL** | Own drag/resize/tooltip/keyboard shortcut systems entirely inline | |
| **HIGH** | Red as default shift color (`#ef4444`) — red semantically signals danger in most contexts | |
| **HIGH** | Uses native `window.confirm()` for deletion — blocks UI thread, not Apple-style, not accessible | |
| **HIGH** | Dark theme creates entirely separate visual context from the rest of the app — feels like a different application | |
| **MED** | Gantt view is functionally duplicated with editor_enhanced — two separate schedule editors exist | |
| **MED** | Keyboard shortcuts are extensive (arrow keys, delete, escape) but not discoverable — no help panel or shortcut reference | |
| **MED** | Tooltips use custom implementation without focus trap — keyboard users cannot access tooltip content | |
| **LOW** | No touch events for drag/resize of Gantt bars |

#### Specific Recommendations (P0)

1. Merge with `schedule_editor_enhanced.html` into one unified page with a view switcher ("Таблица" / "Диаграмма Ганта")
2. Replace default shift color from red to Apple Blue (`#007AFF`) or a neutral design-system color
3. Replace `window.confirm()` with a custom confirmation modal

#### Specific Recommendations (P1)

4. Add keyboard shortcuts help panel (triggered by "?" key)
5. Make tooltips keyboard-focusable with focus trapping
6. Add touch event support for mobile drag/resize

---

### my_schedule.html

**File:** `app/templates/my_schedule.html` | **Lines:** 2069 | **Status:** Standalone (extends no base)

#### UX Problems

| Severity | Issue | Location |
|---|---|---|
| **CRITICAL** | At 2069 lines, the single largest template — multiple modals, complex form logic, calendar grid, radio groups | entire file |
| **CRITICAL** | Does NOT extend `base_new.html` — completely standalone HTML with custom sidebar, no navigation or period selector from base | |
| **CRITICAL** | COLOR COLLISION: weekend background uses green (`#34C759`), vacation badge also uses green (`#34C759`) — visually indistinguishable | |
| **HIGH** | Multiple modal implementations (day detail, study, preference, bulk import) each with own styles | throughout |
| **HIGH** | Own complete `<style>` block, duplicating global CSS tokens | throughout |
| **HIGH** | 6 stat cards at the top — information overload | |
| **HIGH** | No keyboard navigation between days in calendar grid (`div` elements, not buttons or grid items) | |
| **MED** | 7+ modals stacking without proper z-index management or focus stacking | |
| **MED** | Three differently-colored header action buttons (primary blue, secondary purple, warning green) — no visual hierarchy | |
| **MED** | Radio groups for shift editing are custom `div` elements — not keyboard accessible, conflicts with native patterns | |
| **MED** | Custom date picker for range selection instead of native `<input type="date">` | |

#### Specific Recommendations (P0)

1. Change weekend color to a neutral gray-blue or light purple to distinguish from vacation green
2. Make this page extend `base_new.html` for consistent navigation
3. Unify all modals under ModalSystem

#### Specific Recommendations (P1)

4. Add keyboard grid navigation (arrow keys) for calendar days
5. Reduce stat cards to 3-4 most important metrics
6. Consolidate modal count — merge related forms
7. Replace action button colors with consistent primary/secondary hierarchy

---

### constraints_new.html

**File:** `app/templates/constraints_new.html` | **Lines:** 1071 | **Status:** Extends `base_new.html`

#### UX Problems

| Severity | Issue | Location |
|---|---|---|
| **CRITICAL** | Own `<style>` block (~460 lines) with own `.modal-backdrop`, `.modal-content`, `.btn-primary`, `.btn-secondary`, `.btn-danger`, toast, tabs | lines 22-483 |
| **HIGH** | Own toast notification system (`.toast`) not integrated with global notification | lines 454-482 |
| **HIGH** | Custom tab system (`.tabs`, `.tab`) with inline JS switching instead of reusable component | lines 60-91 |
| **HIGH** | Employee selector for "Add constraint" is plain dropdown — not searchable with 15+ employees | |
| **MED** | Header action buttons use inline color overrides (`bg-blue-500`, `bg-red-500`, `bg-orange-500`) | lines 9, 12, 15 |
| **MED** | Icon boxes oversized at 52x52px with large emoji — disproportionate with button size | lines 60-91 |
| **MED** | Delete button (x) is very small — hard to tap accurately on mobile | |
| **MED** | Hidden radio inputs (`<input type="radio" hidden>`) — rely on label styling, breaks some screen reader patterns | |
| **LOW** | `event.target` in tab switching is fragile — should use `event.currentTarget` | |

#### Specific Recommendations (P0)

1. Migrate modal implementation to base_new.html ModalSystem
2. Replace toast with shared notification system

#### Specific Recommendations (P1)

3. Use design system segmented control (`.tabs`) for constraint type tabs
4. Add search to employee selector
5. Increase delete button minimum size to 32x32px for mobile accessibility
6. Replace hidden radio inputs with proper toggle or switch components

---

### calendar_new.html

**File:** `app/templates/calendar_new.html` | **Lines:** 217 | **Status:** Extends `base_new.html`

#### UX Problems

| Severity | Issue | Location |
|---|---|---|
| **HIGH** | 4 competing gradient backgrounds in calendar day cells — visual noise | |
| **HIGH** | `calendar-day:hover` with `transform: scale(1.05)` causes layout shift in CSS grid | line 40 |
| **HIGH** | No month navigation (prev/next arrows) — can only navigate via sidebar selector | |
| **MED** | Calendar cells are not clickable — no interaction to view day details or add events | |
| **MED** | Legend uses gradient backgrounds as swatches — hard to distinguish | |
| **LOW** | Day indicator dots are very small (6x6px) — hard to tap on mobile | line 74 |
| **LOW** | Own grid CSS in `<style>` block (~95 lines) instead of using global `.calendar` component | lines 8-106 |

#### Specific Recommendations (P1)

1. Replace `transform: scale(1.05)` on hover with box-shadow elevation
2. Add prev/next month navigation arrows in header
3. Make calendar cells clickable — open day details modal
4. Use flat color swatches in legend instead of gradients

---

### vacations.html

**File:** `app/templates/vacations.html` | **Lines:** 457 | **Status:** Extends `base_new.html`

#### UX Problems

| Severity | Issue | Location |
|---|---|---|
| **HIGH** | Own `<style>` block (~210 lines) with own `.modal-backdrop`, `.modal-content`, `.btn-primary`, `.btn-secondary`, `.btn-delete` | lines 14-225 |
| **MED** | Modals use `hidden` class toggle to show/hide — bypass shared ModalSystem | |
| **MED** | No visual distinction between create mode and edit mode in the modal — same title, same form layout | |
| **MED** | Filter section uses inline style `style="width: auto; min-width: 200px;"` instead of utility class | line 234 |
| **LOW** | "Продолжительность" (duration) text is redundant — already implied by date range display | |
| **LOW** | No vacation balance information per employee displayed | |

#### Specific Recommendations (P0)

1. Migrate to ModalSystem; remove own modal CSS

#### Specific Recommendations (P1)

2. Differentiate create vs edit modes: "Добавить отпуск" vs "Редактировать отпуск" in modal title
3. Add vacation balance display per employee

---

### admin_users.html

**File:** `app/templates/admin_users.html` | **Lines:** 235 | **Status:** Extends `base_new.html`

#### UX Problems

| Severity | Issue | Location |
|---|---|---|
| **CRITICAL** | Passwords displayed in plaintext in a `<code>` element — major security concern | line 127 |
| **HIGH** | No confirmation dialog for promote/demote actions — accidental role change with single click | |
| **HIGH** | Own modal implementations using `hidden` class toggle, not using base ModalSystem | lines 167, 185 |
| **HIGH** | "Reset Password" modal uses plaintext input for new password — no visibility toggle | line 174 |
| **HIGH** | No "generate secure password" option — admin must manually enter password | |
| **MED** | Create user form submits password as text input (`type="text"`), not password type | line 79 |
| **MED** | Role badges: both "Администратор" and "Сотрудник" use same `bg-blue-100 text-blue-800` — should visually distinguish admin from employee | lines 117, 121 |

#### Specific Recommendations (P0)

1. **Immediately** remove plaintext password display — show masked or remove entirely
2. Add "Generate password" button with copy-to-clipboard for new user creation
3. Add confirmation modal for promote/demote actions

#### Specific Recommendations (P1)

4. Change password reset input to `type="password"` with visibility toggle
5. Use distinct badge colors for admin (red/orange) vs employee (blue) roles

---

### settings_new.html

**File:** `app/templates/settings_new.html` | **Lines:** 52 | **Status:** Extends `base_new.html`

#### UX Problems

| Severity | Issue | Location |
|---|---|---|
| **MED** | Toggle switches use pure Tailwind peer classes (`peer-checked:bg-blue-600`, etc.) not in `styles.css` | lines 20-23, 31-34 |
| **MED** | No inline save feedback — user toggles setting but no confirmation it was applied | |
| **LOW** | Very sparse page — only 2 settings toggles + about info | lines 14-36 |
| **LOW** | "About system" card uses `gradient-blue` background — text contrast may be marginal | line 41 |

#### Specific Recommendations (P1)

1. Replace Tailwind toggle classes with design system `.toggle` component
2. Add auto-save toast feedback: "Настройки сохранены"
3. Consider adding more settings: theme preference, notification preferences, hours norm

---

### select_employee.html

**File:** `app/templates/select_employee.html` | **Lines:** 44 | **Status:** Extends `base_new.html`

#### UX Problems

| Severity | Issue | Location |
|---|---|---|
| **MED** | Hover `scale-105` animation on employee cards causes layout shift | line 11 |
| **MED** | Shows wrong hours norm for employees with vacation adjustments — displays base norm instead of adjusted | |
| **LOW** | No search/filter input — with 15+ employees, scrolling through cards is slow | |

#### Specific Recommendations (P1)

1. Replace `transform: scale(1.05)` with shadow-on-hover
2. Display adjusted hours norm for vacation-adjusted employees
3. Add search box above employee grid

---

### change_password.html

**File:** `app/templates/change_password.html` | **Lines:** 98 | **Status:** Extends `base_new.html`

#### UX Problems

| Severity | Issue | Location |
|---|---|---|
| **LOW** | Password fields rely purely on HTML5 validation (`minlength="6"`) — no real-time strength indicator | line 39 |
| **LOW** | No password visibility toggle — user must manually retype if typo | |

#### UI Observations

Clean auth-style page with centered card. Good: Uses SVG icons in alerts instead of emoji. Consistent with login.html styling pattern. Well-structured form groups with proper labels.

#### Specific Recommendations (P2)

1. Add password visibility toggle
2. Add minimal strength indicator (bar or text)
3. Add real-time confirm password match indicator

---

### base_new.html

**File:** `app/templates/base_new.html` | **Lines:** 387 | **Status:** Base layout template

#### UX Problems

| Severity | Issue | Location |
|---|---|---|
| **HIGH** | `ModalSystem` JS object is good but not universally adopted — most pages still use their own modal code | |
| **MED** | 9 navigation items with no section grouping — flat list mixes employee/admin/global pages | sidebar |
| **MED** | No active indicator accent (left-colored bar) on current nav item — hard to see which page is selected | sidebar |
| **MED** | Period selector uses native `<select>` not Apple-style picker — functional but not polished | |
| **MED** | Mobile sidebar toggle uses `.sidebar-toggle` with `aria-label="Menu"` but relies on text, no hamburger icon SVG | |
| **HIGH** | Artificial 800ms loading delay (`setTimeout` in JS) — makes the app feel slower than it is | |
| **MED** | Modal system lacks `aria-modal` attribute — missing from modal dialogs | |
| **MED** | No `inert` attribute on background content during modal open — screen readers can still access background | |

#### UI Observations

Good: Consistent sidebar with clear navigation hierarchy. Skip-to-content link for accessibility. Good: ModalSystem JS provides show/hide/close API. Good: Period selector (month/year) at top of sidebar. Mobile responsive with sidebar toggle. The base template is relatively well-designed and should be the foundation all pages build on.

#### Specific Recommendations (P0)

1. Remove artificial loading delay — show content immediately
2. Add `aria-modal="true"` to modal dialogs
3. Add `inert` to background content during modal (or use focus stack)

#### Specific Recommendations (P1)

4. Group navigation items with section headers (e.g., "Планирование", "Управление", "Система")
5. Add active state indicator (left colored bar) to current page
6. Replace native select with custom dropdown for month/year picker
7. Add hamburger SVG icon for mobile sidebar toggle

---

---

## Global UI Inconsistencies

---

### Fragmented Modal Systems

**Impact: CRITICAL**

At least 7 different modal implementations coexist across templates:

| Page | Class Names | State Classes |
|---|---|---|
| `base_new.html` | `ModalSystem` JS object | `show/hide` methods |
| `employees_new.html` | `.modal-backdrop`, `.modal-overlay` | `.active` |
| `constraints_new.html` | `.modal-backdrop` | `.active` + pointer-events toggle |
| `schedule_editor_enhanced.html` | `.modal-backdrop` | `.active` |
| `schedule_gantt_v2.html` | Own custom modal CSS | `.open` / `.close` |
| `vacations.html` | `.modal-backdrop` by ID | `.active` |
| `admin_users.html` | IDs directly | `hidden` class toggle |
| `my_schedule.html` | Multiple separate modals | Various |

**Should be:** One `.modal` component system in `styles.css`, with a single JS modal manager (ModalSystem in base_new.html is closest to this).

---

### Multiple Button Systems

**Impact: HIGH**

| System | Classes | Defined In |
|---|---|---|
| BEM `.btn` | `.btn`, `.btn--primary`, `.btn--secondary`, `.btn--danger`, `.btn--lg`, `.btn--block` | `styles.css` |
| Utility `.btn-primary` | `.btn-primary`, `.btn-secondary` (plain classes) | Multiple pages |
| Inline overrides | e.g., `bg-green-500 hover:bg-green-600` | employees_new, constraints_new |

The `.btn-primary` utility class is redefined in at least 5 different templates with different `padding`, `border-radius`, `font-weight`, and `background` values.

---

### CSS Token Inconsistency

**Impact: HIGH**

Global CSS (`styles.css`) defines tokens in `:root`:
```
--apple-blue: #007AFF
--apple-gray: #1D1D1F
--apple-light-gray: #F5F5F7
--apple-green: #34C759
--apple-red: #FF3B30
--apple-orange: #FF9500
```

However, individual templates use these alternative values directly:

| Value | Used Instead Of | Found In |
|---|---|---|
| `#667eea` | `--apple-blue` | employees_new (btn-submit gradient) |
| `#764ba2` | `#5856D6` (purple) | employees_new (btn-submit gradient) |
| `#E5E5EA` | `--apple-light-gray` | employees_new, constraints_new |
| `#1a1a2e` | `--apple-gray` | employees_new modal titles |
| `#374151` | Tailwind gray-700 | employees_new labels |
| `#9ca3af` | Tailwind gray-400 | employees_new placeholders |
| `#6b7280` | Tailwind gray-500 | employees_new secondary text |

---

### Font Inconsistency

**Impact: MEDIUM**

- `styles.css` imports and uses `DM Sans` (Google Fonts)
- `login.html` imports `DM Sans` independently (line 7)
- Goal states "Apple iOS/macOS Style" but SF Pro is Apple's font, not DM Sans
- No fallback chain specified beyond `font-family: 'DM Sans', sans-serif`

---

### Emoji vs Icon System

**Impact: MEDIUM**

Emoji is used as icons across most pages:
- Page titles: "Сотрудники", "График", "Календарь", "Отпуска", "Настройки", "Редактор графика"
- Stat cards: various emoji
- Legend items: colored circle emoji
- Toast notifications: checkmark, X, info

**Should be:** SVG icon system (as demonstrated in `change_password.html` alert icons).

---

### Duplicate Schedule Editors

**Impact: HIGH**

Two separate schedule editor pages share overlapping functionality but have completely separate implementations:
- `schedule_editor_enhanced.html` — table/timeline view with drag-drop
- `schedule_gantt_v2.html` — Gantt chart view with drag/resize/zoom

This creates confusion about which page to use, duplicated maintenance effort, and inconsistent UX.

---

---

## Visual Design Audit

---

### Color Problems

#### Critical Color Collisions

| Issue | Where | Fix |
|---|---|---|
| Weekend green == Vacation green (`#34C759`) | `my_schedule.html` | Change weekend to light purple (`#E8D5F5`) |
| Two stat cards share same orange gradient | `home_new.html` | Use teal gradient for warnings card |
| Red default shift color signals danger | `schedule_gantt_v2.html` | Change to Apple Blue (`#007AFF`) |
| `#667eea` gradient on submit button looks out of place | `employees_new.html` | Use design system `--gradient-blue` |
| Admin vs employee role badges use same blue | `admin_users.html` | Admin: `--red-500`, Employee: `--blue-600` |

#### Gradient Overuse

Apple design uses gradients sparingly. Current gradient usage:

| Element | Gradients | Apple Style |
|---|---|---|
| Stat cards | 4 different gradients | Flat white + subtle icon |
| Submit button | `#667eea` to `#764ba2` | Solid Apple Blue, maybe subtle gradient |
| Logo text | Apple Blue gradient | Appropriate — this is branding |
| Calendar days | 4 gradient types | Flat colors with subtle tints |

**Recommendation:** Reduce gradients to 2-3 maximum: logo text, primary button (subtle), and optionally one marketing element.

#### Text Contrast Issues

| Text | Background | Ratio | WCAG AA | Fix |
|---|---|---|---|---|
| White on `#007AFF` (Apple Blue) | Primary button | ~3.95:1 | FAIL (large text OK) | Use slightly darker blue `#0056CC` for button bg |
| `--gray-400` (#AEAEB2) on white | Placeholder | ~2.42:1 | FAIL (decorative only) | Acceptable for placeholder text |
| `--gray-600` (#6E6E73) on white | Secondary text | ~5.74:1 | PASS | No change needed |
| White on gradient-blue card | About card | ~4.5:1 | PASS (barely) | Darken gradient end color |

---

### Typography Problems

| Issue | Current | Recommended |
|---|---|---|
| Font family | DM Sans | Inter (Apple-like, open-source) |
| Missing letter-spacing | No `letter-spacing` anywhere | Add `-0.02em` to headings, `0` to body |
| Heading sizes inconsistent | 2.25rem logo, 1.5rem page | Follow scale: h1: 1.75rem, h2: 1.5rem |
| Body text minimum | Some `0.75rem` (12px) | Minimum 0.875rem (14px) for body |
| Line height too loose on headings | Inherits 1.5 from body | Headings: 1.1-1.3 |

---

### Spacing Problems

| Issue | Where | Fix |
|---|---|---|
| Card padding varies (16px, 20px, 24px, 32px) | All pages | Standardize: `--space-5` (20px) |
| Section gaps inconsistent (16px-40px) | All pages | Standardize: `--space-8` (32px) between sections |
| Form field gaps vary (12px, 16px, 20px) | All pages | Standardize: `--space-4` (16px) |
| Modal padding hardcoded in each page | 5+ pages | Use `--space-6` (24px) universally |
| Button padding not standardized | Each page redefines | Use BEM sizes: sm/md/lg |

---

### Shadow Inconsistencies

| Element | Current Shadows | Recommended |
|---|---|---|
| Cards | `0 4px 6px rgba(0,0,0,0.1)` | `0 2px 8px rgba(0,0,0,0.06)` (--shadow-sm) |
| Modals | `0 20px 60px rgba(...)` | `0 25px 50px rgba(0,0,0,0.15)` (--shadow-xl) |
| Dropdowns | Not specified | `0 4px 16px rgba(0,0,0,0.08)` (--shadow-md) |

---

### Border Radius Inconsistencies

| Element | Current | Recommended |
|---|---|---|
| Cards | `12px`, `16px`, `20px` | `--radius-lg` (16px) |
| Inputs | `12px` | `--radius-md` (12px) — already consistent |
| Buttons | `10px`, `12px`, `24px` | Follow BEM: sm=8px, md=12px, lg=16px |
| Modals | `16px`, `20px`, `24px` | `--radius-xl` (20px) |
| Badges/pills | `9999px` | `--radius-full` (9999px) — already consistent |

---

---

## Mobile & Responsive Audit

---

### Breakpoint Analysis

Current breakpoints (implicit from media queries in various pages):

| Width | Target | Coverage |
|---|---|---|
| < 768px | Mobile | Partial — sidebar collapses on some pages |
| 768px - 1024px | Tablet | Partial — grids sometimes too wide |
| > 1024px | Desktop | Full |

Missing breakpoints:
- 375px (iPhone SE, small phones) — critical, most used mobile breakpoint
- 1440px (large desktops) — content stretches too wide

### Page-Specific Mobile Issues

#### login.html — Mobile: PASS

Centered layout works well on mobile. Card width adapts. Good touch targets.

#### home_new.html — Mobile: PARTIAL

- 4-column stat grid collapses to 1 column — acceptable but takes a lot of vertical space
- Coverage rules 3-column grid stacks nicely
- Quick action cards stack correctly on mobile

#### employees_new.html — Mobile: FAIL

- Employee cards with dense info don't compress well on 375px
- Modal forms overflow on narrow screens
- +/- adjustment controls too close together — accidental taps
- Header action buttons stack in column — wastes space

#### schedule_editor_enhanced.html — Mobile: FAIL

- **Drag-and-drop is completely non-functional on touch devices**
- Table view requires horizontal scroll
- Timeline view unusable on narrow screens
- Modal forms overflow viewport

#### schedule_gantt_v2.html — Mobile: PARTIAL

- Gantt chart horizontal scroll works but is not intuitive
- Dark theme toggle accessible
- **No touch drag/resize for Gantt bars**
- Keyboard shortcuts panel inaccessible on mobile

#### my_schedule.html — Mobile: FAIL

- Custom sidebar takes full viewport on mobile — no escape
- 6 stat cards in a row on mobile — excessive vertical space
- Calendar day grid cells too small for touch
- Multiple modals stack on top — z-index chaos on mobile

#### calendar_new.html — Mobile: PARTIAL

- Calendar grid cells become too small on 375px
- Day dots (6x6px) below Apple minimum touch target
- No pinch-to-zoom for calendar

#### constraints_new.html — Mobile: PARTIAL

- Tab bar overflows horizontally on narrow screens
- Modal forms need wider viewport
- Constraint cards stack acceptably

#### vacations.html — Mobile: PASS

- List-based layout compresses well
- Modal form is narrow enough

#### admin_users.html — Mobile: PARTIAL

- User table requires horizontal scroll
- Action buttons in table row too small on mobile
- Modal forms work but are cramped

#### settings_new.html — Mobile: PASS

- Simple toggle layout works on all sizes
- Minimal content means no overflow

#### select_employee.html — Mobile: PASS

- Grid of avatar cards works well
- `scale-105` hover effect causes jank on touch

### Touch Target Audit

Apple HIG minimum touch target: **44x44pt**

| Element | Current Size | Requirement | Status |
|---|---|---|---|
| +/- adjustment buttons | ~28x28px | 44px | FAIL |
| Delete (x) button in constraints | ~20x20px | 44px | FAIL |
| Calendar day indicator dots | 6x6px | 44px | FAIL |
| Sidebar nav links | ~32px height | 44px | FAIL |
| Table action buttons (admin_users) | ~24x24px | 44px | FAIL |
| Primary buttons | 44px+ height | 44px | PASS |
| Form inputs | 44px+ height | 44px | PASS |

### Responsive Recommendations (P0)

1. Add explicit breakpoints for 375px, 768px, 1024px, 1440px in `styles.css`
2. Ensure all pages inherit responsive sidebar behavior from base_new
3. Minimum touch target size of 44px for all interactive elements

### Responsive Recommendations (P1)

4. Add touch event support to all drag-and-drop interactions
5. Convert data tables to card layout on mobile (schedule, admin_users)
6. Add horizontal scroll hints for Gantt chart and calendar on mobile

---

---

## Interaction Design Audit

---

### State Management

#### Loading States

| Issue | Where | Fix |
|---|---|---|
| Artificial 800ms loading delay in base_new | `base_new.html` | Remove — show content instantly |
| No loading indicator on form submissions | All pages | Show spinner on button during POST |
| Skeleton loading only in Gantt view | `schedule_gantt_v2.html` | Extend skeleton pattern to other views |
| No optimistic UI — all mutations reload page | employees, constraints | Use fetch + DOM patching |

#### Hover/Active/Focus States

| Element | Hover | Active | Focus |
|---|---|---|---|
| Primary button | `translateY(-1px)` + darker gradient | `scale(0.98)` | No custom ring |
| Secondary button | Slightly darker gray | `scale(0.98)` | No custom ring |
| Card | Shadow increase only | None | N/A |
| Input | None | None | Border color change |
| Link | Color change | None | Underline |

**Issues:**
- No consistent focus visible ring — relies on browser default
- Card hover uses shadow only — appropriate for Apple style
- Active state `scale(0.98)` causes repaint — use `translateY` instead

#### Error/Success States

| Action | Error Feedback | Success Feedback |
|---|---|---|---|
| Form submit | Alert banner | Alert banner |
| Schedule conflict | Red highlight on cell | None |
| Constraint add | Toast (custom per page) | Toast (custom per page) |
| Employee adjustment | Page reload, no feedback | New values shown after reload |
| Password change | Alert banner | Alert banner |

**Issue:** Feedback is inconsistent — some pages use alert banners, some use custom toast, some reload with no visible confirmation.

### Navigation Patterns

#### Page Transitions

No page transition animations exist. Navigation is instant with full page reload (expected with Jinja2/FastAPI). No loading skeletons between navigations.

#### Deep Linking

Month/year state is not encoded in URL — sharing a link always resets to current month. Bookmarking a specific employee's schedule is not possible without manual steps.

### Modal Interactions

| Page | Open Trigger | Close Methods | Focus Trap | Backdrop Click |
|---|---|---|---|---|
| base_new | JS API | Escape, close button | Partial | Yes |
| employees_new | JS `.openModal()` | Close button, backdrop | No | Yes |
| constraints_new | Various | Close button, backdrop | No | Partial |
| editor_enhanced | JS | Close button | No | Partial |
| gantt_v2 | JS | Escape, close, backdrop | No | Yes |
| my_schedule | Various | Various | No | Varies |
| admin_users | JS | Close button | No | No |

**Issues:**
- Only base_new has partial focus trapping
- Escape key handling inconsistent
- Backdrop click behavior unreliable across modals
- No scroll lock on body when modal is open

### Drag and Drop

| System | Mouse | Touch | Keyboard | Accessibility |
|---|---|---|---|---|
| Editor enhanced | Yes | No | No | No |
| Gantt v2 | Yes | No | Partial (arrow keys) | No |
| Calendar | None | None | None | None |

### Animation & Motion

#### Current Animations

| Animation | Duration | Easing | Used In |
|---|---|---|---|
| Modal appear | 0.2s | ease | base_new, most pages |
| Button hover | 0.15s | ease | styles.css |
| Card hover | 0.2s | ease | styles.css |
| Calendar day scale | 0.15s | ease | calendar_new |
| Stat card hover | None | N/A | home_new |

#### Problematic Animations

| Issue | Where | Why |
|---|---|---|
| `transform: scale(1.05)` on calendar hover | calendar_new | Causes layout shift in CSS grid |
| `hover:scale-105` on employee cards | select_employee | Janky on touch, layout shift |
| No `prefers-reduced-motion` support | Any page with animation | Accessibility violation |
| Artificial 800ms delay | base_new | Feels slow, no purpose |

### Interaction Recommendations (P0)

1. Remove 800ms artificial delay
2. Standardize loading/disabled states on all form submits
3. Implement proper focus trapping in all modals
4. Add ESC key handler to all modals

### Interaction Recommendations (P1)

5. Add touch event support to all drag-and-drop systems
6. Add optimistic UI for non-destructive mutations
7. Standardize feedback system (toast + alert banner patterns)
8. Add `prefers-reduced-motion` media query support
9. Replace `scale()` transforms with shadow-based hover effects

---

---

## Accessibility Audit

---

### WCAG AA Color Contrast Analysis

| Foreground | Background | Ratio | Required | Status |
|---|---|---|---|---|
| White (#fff) on Apple Blue (#007AFF) | Button | 3.95:1 | 4.5:1 normal, 3:1 large | **FAIL** normal text |
| White on darker blue (#0056CC) | Button | 4.67:1 | 4.5:1 normal | **PASS** |
| --gray-600 (#6E6E73) on white | Body | 5.74:1 | 4.5:1 | **PASS** |
| --gray-400 (#AEAEB2) on white | Placeholder | 2.42:1 | 3:1 large | **FAIL** (decorative OK) |
| Blue button text (#007AFF) on white bg | Ghost button | 3.69:1 | 4.5:1 | **FAIL** normal text |
| White text on gradient-blue card | About card | ~4.5:1 | 3:0 large | **PASS** (barely) |
| Weekend green (#34C759) on white | Calendar | 2.84:1 | 3:0 large | **FAIL** normal text |
| Red (#FF3B30) on white | Error | 4.03:1 | 4.5:1 normal | **FAIL** normal text |

**Critical fix:** Red (#FF3B30) used for error text on white fails WCAG AA for normal text. Use darker red (#E02020) which achieves 4.6:1.

### Keyboard Navigation Audit

| Feature | Keyboard Accessible | Tab Order | Focus Visible | Notes |
|---|---|---|---|---|
| Sidebar navigation | Yes | Logical | Partial (default ring) | Missing visual enhancement |
| Period selector (select) | Yes | Logical | Partial | Native select |
| Form inputs | Yes | Logical | Partial | Browser default |
| Calendar day grid | No | N/A | N/A | Divs, not focusable | 
| Custom radio groups | No | N/A | N/A | Hidden inputs + div labels |
| Employee cards | Link | Logical | Partial | Via anchor tag |
| Modal close button | Yes | First | Partial | |
| Modal backdrop | No | N/A | N/A | Click only |
| Gantt bars | Partial | Arrow keys | Partial | Limited keyboard nav |
| Drag handles | No | N/A | N/A | Mouse only |
| Tabs (segmented control) | Partial | Logical | Partial | Hidden radios |
| Toast notifications | No | N/A | N/A | Auto-dismiss |
| Stat cards | No | N/A | N/A | Not interactive |

### ARIA Audit

| Requirement | Status | Details |
|---|---|---|
| Skip navigation | Partial | Exists in base_new, target may not exist everywhere |
| `role="dialog"` on modals | Partial | Only some modals have it |
| `aria-modal="true"` | Missing | Not present on any modals |
| `aria-label` on icon-only buttons | Partial | Some buttons have it |
| `aria-live` regions | Missing | Dynamic content changes not announced |
| `aria-expanded` on toggles | Missing | Toggle switches don't reflect state |
| `aria-describedby` on form fields | Missing | Hints not linked to inputs |
| `aria-invalid` on error fields | Missing | Validation state not communicated |
| `aria-required` on required fields | Partial | Some via HTML5 `required` |
| Focus trap in modals | Partial | Only base_new partially implements |
| `inert` on background | Missing | No page sets inert during modal |

### Screen Reader Issues

| Issue | Impact | Fix |
|---|---|---|
| Calendar grid is visual-only | High | Add `role="grid"` with proper structure |
| Color-only differentiation (weekend/vacation) | High | Add text labels or patterns |
| Gradient backgrounds convey no meaning to SR | Medium | Add `aria-label` or `role="img"` with description |
| Toast notifications not in live region | Medium | Add `role="status"` and `aria-live="polite"` |
| Drag-and-drop instructions are visual-only | High | Add keyboard alternative text |

### Focus Management

| Scenario | Current Behavior | Expected |
|---|---|---|
| Open modal | Focus moves to close button | Focus moves to first form field |
| Close modal | Focus returns to document body | Focus returns to trigger element |
| Form error | No focus move | Focus moves to first error field |
| Tab through sidebar | Works but no enhanced focus ring | Visible enhanced ring |
| Navigate calendar | Not keyboard-accessible | Arrow key grid navigation |

### Accessibility Recommendations (P0)

1. **Fix color contrast failures:** White text on primary button, red error text
2. **Add `aria-modal="true"` and `role="dialog"` to all modals**
3. **Implement focus trapping in all modals**
4. **Make calendar days keyboard-navigable** (arrow keys, enter to select)
5. **Replace hidden radio inputs** in tabs and radio groups with accessible alternatives

### Accessibility Recommendations (P1)

6. Add `aria-live` regions for dynamic content updates
7. Add `aria-invalid` and `aria-describedby` for form validation
8. Implement `prefers-reduced-motion` across all animated elements
9. Add `aria-label` to all icon-only buttons
10. Make drag-and-drop keyboard-accessible (arrow keys for position)
11. Add screen reader instructions for drag interactions
12. Ensure focus returns to trigger element after modal close

---

---

## Specific Improvement Recommendations

---

### Per-Page Priority Matrix

| Page | P0 (Critical) | P1 (Important) | P2 (Polish) |
|---|---|---|---|
| login.html | — | Add password toggle, searchable dropdown | Move styles to global CSS |
| home_new.html | — | Fix stat card colors, replace emoji | Add empty states |
| employees_new.html | Migrate modals, fix button gradient | Custom adjustment input, search | Fix informal text |
| schedule_new.html | — | Distinguish badge types | Add hours progress |
| schedule_editor_enhanced.html | Add touch support | Rename views, aria-live | Undo/redo, bulk select |
| schedule_gantt_v2.html | Merge with editor, fix shift color | Keyboard help, focusable tooltips | Touch resize |
| my_schedule.html | Fix color collision, migrate to base | Reduce stat cards, keyboard grid | Merge modals |
| constraints_new.html | Migrate modals | Searchable employee, accessible tabs | Icon sizing |
| calendar_new.html | — | Add nav arrows, clickable cells | Pinch zoom |
| vacations.html | Migrate modals | Create vs edit distinction | Vacation balance |
| admin_users.html | Remove plaintext passwords | Generate password, confirmation | Distinct role badges |
| settings_new.html | — | Save feedback, more settings | |
| select_employee.html | — | Fix hover animation, correct norm | Search box |
| change_password.html | — | Password visibility toggle | Strength indicator |
| base_new.html | Remove loading delay, aria-modal | Group nav, active indicator | Custom period picker |

### Quick Wins (Complete in 1-2 hours each)

1. **Remove artificial loading delay** in base_new.html (1 line change)
2. **Replace gradient stat cards with flat white cards** on home_new.html
3. **Fix weekend green vs vacation green collision** on my_schedule.html
4. **Replace red shift color** with Apple Blue on schedule_gantt_v2.html
5. **Remove plaintext password display** from admin_users.html immediately
6. **Add aria-modal and role=dialog** to base_new ModalSystem

### Medium Effort (Half-day each)

7. **Migrate all pages to base_new ModalSystem** — 7 pages affected
8. **Unify button system** — remove `.btn-primary` utility, keep only `.btn--primary`
9. **Add focus trapping** to all modal implementations
10. **Fix all WCAG AA contrast failures** — button text, error text, ghost button
11. **Add keyboard navigation** to calendar grid and radio groups
12. **Add touch event support** to drag-and-drop systems

### Larger Effort (1-2 days each)

13. **Merge schedule_editor_enhanced + schedule_gantt_v2** into unified editor
14. **Migrate my_schedule.html to extend base_new.html** — refactor standalone page
15. **Replace emoji with SVG icons** across all pages
16. **Font switch from DM Sans to Inter** — update all imports and CSS
17. **Build search/typeahead** for employee selectors (3 pages)
18. **Implement optimistic UI** for non-destructive mutations

---

---

## Apple-Style Design System

---

### Design Philosophy

The EKZ Grafik system aspires to an Apple-inspired design language:
- **Clarity:** Generous whitespace, sharp typography, purposeful hierarchy
- **Deference:** UI chrome recedes; content takes priority
- **Depth:** Subtle translucency, layered shadows, meaningful z-axis

Key reference: Apple Human Interface Guidelines (2024), iOS 18 / macOS 15.

---

### Design Tokens

#### Typography

**Font Family:**

```css
--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;
--font-mono: 'SF Mono', 'Fira Code', monospace;
```

Import: `<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">`

**Type Scale:**

| Token | Size | Weight | Line Height | Letter Spacing | Usage |
|---|---|---|---|---|---|
| `font-display` | 48px / 3rem | 700 | 1.1 | -0.03em | Dashboard values, hero |
| `font-h1` | 28px / 1.75rem | 700 | 1.2 | -0.02em | Page titles |
| `font-h2` | 24px / 1.5rem | 600 | 1.25 | -0.02em | Section headers |
| `font-h3` | 20px / 1.25rem | 600 | 1.3 | -0.01em | Subsection headers |
| `font-h4` | 18px / 1.125rem | 600 | 1.35 | 0 | Card titles |
| `font-body` | 16px / 1rem | 400 | 1.5 | 0 | Body paragraph |
| `font-body-sm` | 14px / 0.875rem | 400 | 1.5 | 0 | Secondary body |
| `font-caption` | 12px / 0.75rem | 400 | 1.4 | 0 | Captions, labels |
| `font-label` | 13px / 0.8125rem | 500 | 1.3 | 0 | Form labels |
| `font-badge` | 11px / 0.6875rem | 500 | 1.3 | 0 | Badge text |
| `font-button` | 14px / 0.875rem | 500 | 1.2 | 0 | Button text |

Minimum text size: 11px for badges only. Body text minimum: 14px.

#### Color Palette

```css
/* Primary Blue */
--blue-50: #EFF6FF;
--blue-100: #DBEAFE;
--blue-200: #BFDBFE;
--blue-500: #3B82F6;
--blue-600: #2563EB;      /* Primary buttons, links */
--blue-700: #1D4ED8;      /* Hover on primary */

/* Apple Blue (exact) */
--apple-blue: #007AFF;
--apple-blue-dark: #0056CC;  /* Accessible button variant */

/* Neutral Grays */
--gray-50: #FAFAFA;       /* Page background */
--gray-100: #F5F5F7;      /* Card backgrounds, inputs */
--gray-200: #E5E5EA;      /* Borders, dividers */
--gray-300: #D1D1D6;      /* Disabled borders */
--gray-400: #AEAEB2;      /* Placeholder text */
--gray-500: #8E8E93;      /* Tertiary text */
--gray-600: #6E6E73;      /* Secondary text */
--gray-700: #48484A;      /* Sub-headings */
--gray-800: #1D1D1F;      /* Primary text, headings */
--gray-900: #000000;      /* Highest emphasis */

/* Semantic Colors */
--green-500: #34C759;     /* Success, available */
--green-600: #30D158;     /* Hover */
--red-500: #FF3B30;       /* Destructive, errors */
--red-600: #FF453A;       /* Hover on destructive */
--red-700: #E02020;       /* Accessible error text */
--orange-500: #FF9500;    /* Warnings, caution */
--orange-600: #FF9F0A;    /* Hover on warning */
--teal-500: #5AC8FA;      /* Vacation, info */
--purple-500: #AF52DE;    /* Training, special */
--yellow-500: #FFCC00;    /* Caution indicators */

/* Gradients (used sparingly) */
--gradient-blue: linear-gradient(135deg, #007AFF, #5856D6);
--gradient-green: linear-gradient(135deg, #34C759, #30D158);
--gradient-orange: linear-gradient(135deg, #FF9500, #FF6B00);
```

#### Spacing System

8px base grid with 4px micro-spacing:

```css
--space-1:  4px;   /* Micro-gap */
--space-2:  8px;   /* Form field gap */
--space-3:  12px;  /* Card padding, grid gap */
--space-4:  16px;  /* Standard gap, form group */
--space-5:  20px;  /* Card padding */
--space-6:  24px;  /* Section gap, modal padding */
--space-8:  32px;  /* Page section gap */
--space-10: 40px;  /* Large section */
--space-12: 48px;  /* Major page sections */
```

#### Border Radius

```css
--radius-sm:   8px;    /* Badges, small buttons, tags */
--radius-md:   12px;   /* Inputs, standard buttons */
--radius-lg:   16px;   /* Cards, panels */
--radius-xl:   20px;   /* Modals, dialogs */
--radius-2xl:  24px;   /* Large sheets */
--radius-full: 9999px; /* Pills, avatars, toggles */
```

#### Shadow System

```css
--shadow-xs: 0 1px 2px rgba(0,0,0,0.04);    /* Subtle card border */
--shadow-sm: 0 2px 8px rgba(0,0,0,0.06);    /* Default card */
--shadow-md: 0 4px 16px rgba(0,0,0,0.08);   /* Hovered card, dropdown */
--shadow-lg: 0 8px 32px rgba(0,0,0,0.12);   /* Modal backdrop */
--shadow-xl: 0 25px 50px rgba(0,0,0,0.15);  /* Modal dialog */
--shadow-focus: 0 0 0 3px rgba(37,99,235,0.12); /* Input focus ring */
```

Rules: Cards use `shadow-sm` default, `shadow-md` on hover. Never use harsh shadows (>0.15 alpha).

### Responsive Breakpoints

```css
/* Mobile first */
/* Base styles target 320px+ (smallest phones) */

/* Small phones - landscape and up */
@media (min-width: 375px) { ... }

/* Tablets portrait */
@media (min-width: 768px) { ... }

/* Tablets landscape / small desktops */
@media (min-width: 1024px) { ... }

/* Large desktops */
@media (min-width: 1440px) {
    .container { max-width: 1200px; margin: 0 auto; }
}
```

| Token | Min Width | Usage |
|---|---|---|
| `xs` | 375px | Small phone adjustments |
| `sm` | 768px | Tablet: 2-col grids, sidebar collapse |
| `md` | 1024px | Desktop: sidebar always visible, 3-col grids |
| `lg` | 1440px | Large: max-width container, 4-col grids |

### Animation Timings

```css
/* Transition Timing Functions */
--ease-default: ease;
--ease-in: cubic-bezier(0.4, 0, 1, 1);
--ease-out: cubic-bezier(0, 0, 0.2, 1);
--ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
--ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1); /* Subtle bounce, used sparingly */

/* Duration Tokens */
--duration-fast: 100ms;   /* Active states */
--duration-normal: 150ms; /* Hover, micro-interactions */
--duration-smooth: 200ms; /* Modal, card animations */
--duration-slow: 300ms;   /* Toast slide, page transitions */
--duration-slower: 500ms; /* Large element animations */
```

| Action | Duration | Easing | Effect |
|---|---|---|---|
| Button hover | 150ms | ease | Slight shadow increase |
| Button active | 100ms | ease | Slight press |
| Card hover | 200ms | ease | shadow-sm to shadow-md |
| Modal open | 200ms | ease | translateY(8px) scale(0.98) to origin |
| Modal close | 150ms | ease-in | Reverse, slight scale down |
| Dropdown open | 150ms | ease-out | translateY(-4px) to 0, opacity |
| Toast slide-in | 300ms | ease-out | translateY(100px) to 0 |
| Toast slide-out | 200ms | ease-in | Reverse |
| Skeleton pulse | 1500ms | ease-in-out | Opacity oscillation |
| Fade in (stagger) | 200ms | ease | index * 50ms delay |

Reduced motion:
```css
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 0.01ms !important;
        transition-duration: 0.01ms !important;
        scroll-behavior: auto !important;
    }
}
```

---

### Component CSS Specifications

#### Focus Ring

```css
/* Global focus style — replace browser default */
:focus-visible {
    outline: 2px solid var(--blue-600);
    outline-offset: 2px;
}

/* Input focus uses box-shadow ring instead */
.input:focus {
    outline: none;
    box-shadow: var(--shadow-focus);
}
```

#### Buttons

```css
/* Base button */
.btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    font-family: var(--font-sans);
    font-weight: 500;
    cursor: pointer;
    border: none;
    transition: all var(--duration-normal) var(--ease-default);
    text-decoration: none;
    line-height: 1.2;
    white-space: nowrap;
}

.btn:active {
    transform: scale(0.98);
}

.btn:disabled,
.btn[aria-disabled="true"] {
    opacity: 0.5;
    cursor: not-allowed;
    pointer-events: none;
}

/* Primary button */
.btn--primary {
    background: var(--apple-blue);
    color: white;
}
.btn--primary:hover {
    background: var(--apple-blue-dark);
    box-shadow: var(--shadow-sm);
}

/* Secondary button */
.btn--secondary {
    background: var(--gray-100);
    color: var(--gray-800);
    border: 1px solid var(--gray-200);
}
.btn--secondary:hover {
    background: var(--gray-200);
}

/* Danger button */
.btn--danger {
    background: var(--red-500);
    color: white;
}
.btn--danger:hover {
    background: #E02020;
    box-shadow: var(--shadow-sm);
}

/* Ghost button */
.btn--ghost {
    background: transparent;
    color: var(--blue-600);
}
.btn--ghost:hover {
    background: var(--blue-50);
}

/* Sizes */
.btn--sm {
    padding: 6px 12px;
    font-size: var(--font-sm, 0.75rem);
    border-radius: var(--radius-sm);
}

.btn--md {
    padding: 10px 20px;
    font-size: var(--font-sm, 0.875rem);
    border-radius: var(--radius-md);
}

.btn--lg {
    padding: 14px 28px;
    font-size: var(--font-base, 1rem);
    border-radius: var(--radius-md);
}

/* Full width */
.btn--block {
    width: 100%;
}

/* Loading state */
.btn--loading {
    position: relative;
    color: transparent !important;
}
.btn--loading::after {
    content: '';
    position: absolute;
    width: 16px;
    height: 16px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
}
@keyframes spin {
    to { transform: rotate(360deg); }
}
```

#### Inputs

```css
.input {
    font-family: var(--font-sans);
    font-size: 1rem;
    padding: 12px 16px;
    border: 2px solid var(--gray-200);
    border-radius: var(--radius-md);
    background: white;
    color: var(--gray-800);
    transition: all var(--duration-normal) var(--ease-default);
    width: 100%;
}

.input::placeholder {
    color: var(--gray-400);
}

.input:hover {
    border-color: var(--gray-300);
}

.input:focus {
    outline: none;
    border-color: var(--blue-600);
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.input--error {
    border-color: var(--red-500);
}
.input--error:focus {
    box-shadow: 0 0 0 3px rgba(255, 59, 48, 0.12);
}

.input--disabled {
    background: var(--gray-50);
    color: var(--gray-400);
    border-color: var(--gray-100);
    cursor: not-allowed;
    pointer-events: none;
}

/* Form group spacing */
.form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.form-label {
    font-size: var(--font-sm, 0.875rem);
    font-weight: 500;
    color: var(--gray-700);
}

.form-label--required::after {
    content: ' *';
    color: var(--red-500);
}

.form-hint {
    font-size: var(--font-xs, 0.75rem);
    color: var(--gray-500);
}

.form-error {
    font-size: var(--font-xs, 0.75rem);
    color: var(--red-500);
}
```

#### Cards

```css
.card {
    background: white;
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    transition: box-shadow var(--duration-smooth) var(--ease-default);
    overflow: hidden;
}

.card:hover {
    box-shadow: var(--shadow-md);
}

.card__header {
    padding: var(--space-5);
    border-bottom: 1px solid var(--gray-200);
}

.card__title {
    font-size: var(--font-lg, 1.125rem);
    font-weight: 600;
    color: var(--gray-800);
    padding: var(--space-5) var(--space-5) 0;
}

.card__subtitle {
    font-size: var(--font-sm, 0.875rem);
    color: var(--gray-500);
    padding: 0 var(--space-5) var(--space-3);
}

.card__body {
    padding: var(--space-5);
}

.card__footer {
    padding: var(--space-4) var(--space-5);
    border-top: 1px solid var(--gray-200);
    background: var(--gray-50);
}

/* Card variant with no shadow, flat border */
.card--flat {
    box-shadow: none;
    border: 1px solid var(--gray-200);
}

/* Card variant with accent border */
.card--accent {
    border-left: 3px solid var(--blue-600);
}
```

#### Modals

```css
/* Backdrop */
.modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.4);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    opacity: 0;
    pointer-events: none;
    transition: opacity var(--duration-smooth) var(--ease-default);
    padding: var(--space-4);
}

.modal-backdrop.open {
    opacity: 1;
    pointer-events: auto;
}

/* Dialog */
.modal-dialog {
    background: white;
    border-radius: var(--radius-xl);
    box-shadow: var(--shadow-xl);
    width: 100%;
    overflow-y: auto;
    transform: translateY(8px) scale(0.98);
    transition: transform var(--duration-smooth) var(--ease-default);
}

.modal-backdrop.open .modal-dialog {
    transform: translateY(0) scale(1);
}

/* Sizes */
.modal--sm { max-width: 400px; }
.modal--md { max-width: 480px; }
.modal--lg { max-width: 640px; }
.modal--xl { max-width: 800px; }

/* Parts */
.modal__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-6) var(--space-6) 0;
}

.modal__title {
    font-size: var(--font-lg, 1.125rem);
    font-weight: 600;
    color: var(--gray-800);
}

.modal__close {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border: none;
    background: var(--gray-100);
    border-radius: var(--radius-full);
    cursor: pointer;
    color: var(--gray-600);
    transition: background var(--duration-normal) var(--ease-default);
}

.modal__close:hover {
    background: var(--gray-200);
}

.modal__body {
    padding: var(--space-6);
}

.modal__footer {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-3);
    padding: 0 var(--space-6) var(--space-6);
}

/* Lock body scroll */
body.modal-open {
    overflow: hidden;
}
```

#### Badges

```css
.badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    font-size: var(--font-badge, 0.6875rem);
    font-weight: 500;
    border-radius: var(--radius-full);
    line-height: 1.4;
    white-space: nowrap;
}

.badge--blue {
    background: var(--blue-100);
    color: var(--blue-600);
}

.badge--green {
    background: #E8F9ED;
    color: #1B8C3A;
}

.badge--red {
    background: #FFE5E3;
    color: #C41E3A;
}

.badge--orange {
    background: #FFF3E0;
    color: #CC6600;
}

.badge--teal {
    background: #E8F6FD;
    color: #0088A8;
}

.badge--purple {
    background: #F0E4F7;
    color: #7B3FA0;
}

.badge--gray {
    background: var(--gray-100);
    color: var(--gray-600);
}
```

#### Toggle Switch

```css
.toggle {
    position: relative;
    display: inline-block;
}

.toggle input {
    position: absolute;
    opacity: 0;
    width: 0;
    height: 0;
}

.toggle__track {
    display: block;
    width: 44px;
    height: 24px;
    background: var(--gray-300);
    border-radius: var(--radius-full);
    transition: background var(--duration-smooth) var(--ease-default);
    cursor: pointer;
}

.toggle input:checked + .toggle__track {
    background: var(--blue-600);
}

.toggle__thumb {
    position: absolute;
    top: 2px;
    left: 2px;
    width: 20px;
    height: 20px;
    background: white;
    border-radius: var(--radius-full);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
    transition: transform var(--duration-smooth) var(--ease-default);
    pointer-events: none;
}

.toggle input:checked ~ .toggle__thumb {
    transform: translateX(20px);
}

.toggle input:focus-visible + .toggle__track {
    outline: 2px solid var(--blue-600);
    outline-offset: 2px;
}

.toggle input:disabled + .toggle__track {
    opacity: 0.5;
    cursor: not-allowed;
}
```

#### Alert

```css
.alert {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 16px;
    border-radius: var(--radius-md);
    font-size: 0.875rem;
    line-height: 1.5;
}

.alert__icon {
    flex-shrink: 0;
    margin-top: 2px;
}

.alert--info {
    background: var(--blue-50);
    color: var(--blue-700);
    border: 1px solid var(--blue-100);
}

.alert--success {
    background: #E8F9ED;
    color: #1B8C3A;
    border: 1px solid #C3E6CB;
}

.alert--warning {
    background: #FFF3E0;
    color: #CC6600;
    border: 1px solid #FFE0B2;
}

.alert--error {
    background: #FFE5E3;
    color: #C41E3A;
    border: 1px solid #FFCDD2;
}
```

#### Tab Bar (Segmented Control)

```css
.tabs {
    display: inline-flex;
    background: var(--gray-100);
    border-radius: var(--radius-md);
    padding: 3px;
    gap: 2px;
}

.tab {
    padding: 8px 16px;
    border: none;
    background: transparent;
    border-radius: var(--radius-sm);
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--gray-600);
    cursor: pointer;
    transition: all var(--duration-normal) var(--ease-default);
    white-space: nowrap;
}

.tab:hover {
    color: var(--gray-800);
}

.tab.active {
    background: white;
    color: var(--gray-800);
    box-shadow: var(--shadow-xs);
}

/* Accessible variant: use button elements */
.tab[role="tab"][aria-selected="true"] {
    background: white;
    color: var(--gray-800);
    box-shadow: var(--shadow-xs);
}
```

#### Toast Notification

```css
.toast-container {
    position: fixed;
    bottom: 24px;
    right: 24px;
    z-index: 1100;
    display: flex;
    flex-direction: column-reverse;
    gap: 8px;
}

.toast {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 20px;
    background: var(--gray-800);
    color: white;
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-lg);
    font-size: 0.875rem;
    transform: translateY(100px);
    opacity: 0;
    transition: all var(--duration-slow) var(--ease-out);
}

.toast.toast--visible {
    transform: translateY(0);
    opacity: 1;
}

.toast--success { border-left: 3px solid var(--green-500); }
.toast--error { border-left: 3px solid var(--red-500); }
.toast--warning { border-left: 3px solid var(--orange-500); }
```

#### Stat Card (Apple-style flat)

```css
.stat-card {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    padding: var(--space-5);
    background: white;
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    transition: box-shadow var(--duration-smooth) var(--ease-default);
}

.stat-card:hover {
    box-shadow: var(--shadow-md);
}

.stat-card__icon {
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-md);
    flex-shrink: 0;
}

.stat-card__icon--blue {
    background: var(--blue-50);
    color: var(--blue-600);
}

.stat-card__icon--green {
    background: #E8F9ED;
    color: #1B8C3A;
}

.stat-card__icon--orange {
    background: #FFF3E0;
    color: #CC6600;
}

.stat-card__icon--teal {
    background: #E8F6FD;
    color: #0088A8;
}

.stat-card__label {
    font-size: 0.8125rem;
    color: var(--gray-600);
    margin-bottom: 4px;
}

.stat-card__value {
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--gray-800);
    line-height: 1.2;
}
```

---

### Utility Class System

Move these from per-page inline styles into `styles.css`:

```css
/* Layout */
.container { max-width: 1200px; margin: 0 auto; padding: 0 var(--space-6); }
.container--full { max-width: none; }
.grid { display: grid; gap: var(--space-4); }
.grid-cols-1 { grid-template-columns: repeat(1, 1fr); }
.grid-responsive-2 { display: grid; gap: var(--space-4); grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }
.grid-responsive-3 { display: grid; gap: var(--space-4); grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); }

/* Responsive grids */
@media (min-width: 768px) {
    .md\:grid-cols-2 { grid-template-columns: repeat(2, 1fr); }
}
@media (min-width: 1024px) {
    .lg\:grid-cols-3 { grid-template-columns: repeat(3, 1fr); }
    .lg\:grid-cols-4 { grid-template-columns: repeat(4, 1fr); }
}

/* Spacing */
.p-0  { padding: 0; }
.p-2  { padding: var(--space-2); }
.p-4  { padding: var(--space-4); }
.p-6  { padding: var(--space-6); }

.m-0  { margin: 0; }
.mb-2 { margin-bottom: var(--space-2); }
.mb-4 { margin-bottom: var(--space-4); }
.mb-6 { margin-bottom: var(--space-6); }
.mb-8 { margin-bottom: var(--space-8); }
.mt-4 { margin-top: var(--space-4); }
.mt-6 { margin-top: var(--space-6); }

/* Width */
.w-full   { width: 100%; }
.max-w-sm { max-width: 400px; }
.max-w-md { max-width: 480px; }
.max-w-lg { max-width: 640px; }

/* Text */
.text-center { text-align: center; }
.text-sm   { font-size: 0.875rem; }
.text-xs   { font-size: 0.75rem; }
.text-lg   { font-size: 1.125rem; }
.font-bold { font-weight: 700; }
.font-semibold { font-weight: 600; }

/* Display */
.flex        { display: flex; }
.flex-col    { flex-direction: column; }
.items-center { align-items: center; }
.justify-center { justify-content: center; }
.justify-between { justify-content: space-between; }
.gap-2 { gap: var(--space-2); }
.gap-3 { gap: var(--space-3); }
.gap-4 { gap: var(--space-4); }

/* Visibility */
.hidden { display: none; }
.sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
}

/* Rounded */
.rounded-sm  { border-radius: var(--radius-sm); }
.rounded-md  { border-radius: var(--radius-md); }
.rounded-lg  { border-radius: var(--radius-lg); }
.rounded-xl  { border-radius: var(--radius-xl); }
.rounded-full { border-radius: var(--radius-full); }
```

---

### Icon System

Replace all emoji-based icons with inline SVGs using consistent stroke styling:

```css
.icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}

.icon--sm { width: 16px; height: 16px; }
.icon--md { width: 20px; height: 20px; }
.icon--lg { width: 24px; height: 24px; }
.icon--xl { width: 32px; height: 32px; }
```

Required SVG icons (Heroicons/Lucide style, stroke-based):

| Icon | Name | Used In |
|---|---|---|
| users | `icon-users` | Sidebar, stat cards |
| calendar | `icon-calendar` | Sidebar, stat cards |
| settings | `icon-settings` | Sidebar |
| home | `icon-home` | Sidebar, nav |
| check-circle | `icon-check-circle` | Success alerts |
| x-circle | `icon-x-circle` | Error alerts |
| alert-triangle | `icon-alert-triangle` | Warning alerts |
| info | `icon-info` | Info alerts |
| chevron-left | `icon-chevron-left` | Pagination, calendar nav |
| chevron-right | `icon-chevron-right` | Pagination, calendar nav |
| chevron-down | `icon-chevron-down` | Dropdowns, collapsibles |
| x | `icon-x` | Close buttons |
| eye | `icon-eye` | Password visibility |
| eye-off | `icon-eye-off` | Password visibility toggle |
| plus | `icon-plus` | Add buttons |
| trash | `icon-trash-2` | Delete buttons |
| edit | `icon-edit` | Edit buttons |
| menu | `icon-menu` | Mobile hamburger |
| key | `icon-key` | Password change |
| clock | `icon-clock` | Schedule, hours |
