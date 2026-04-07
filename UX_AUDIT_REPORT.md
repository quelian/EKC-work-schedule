# UX Audit Report — EKC Work Schedule App

**Date:** 2026-04-04
**Scope:** Full audit of all 14 Jinja2 templates + custom CSS
**Files Audited:** 15 files, ~9000+ lines

---

## CRITICAL Issues (must fix immediately)

### CRIT-01: Plaintext Passwords in Admin User Table
- **File:** `admin_users.html:61`
- **Issue:** Passwords rendered in `<code>{{ user.password }}</code>` — visible to anyone with admin access
- **Impact:** Security breach + UX confusion (passwords look like API keys to non-technical users)
- **Fix:** Replace with `••••••••` placeholder + "Show" toggle button; or better yet, remove from table entirely and expose only via edit form
- **Severity:** P0

### CRIT-02: Settings Page Is Non-Functional
- **File:** `settings_new.html:1-51`
- **Issue:** Only page wrapped in `<form>` but has zero visible submit button or submit handler; toggles not connected to any action; "System Info" card is static placeholder
- **Impact:** Users believe settings are saved when they are not, leading to confusion
- **Fix:** Either remove form wrapper and make toggles work via inline fetch() calls, or add Save button with proper POST handling. Save state to DB, not just JS.
- **Severity:** P0

### CRIT-03: Login Hardcodes "Administrator" in Dropdown
- **File:** `login.html:17-20`
- **Issue:** "Администратор" is hardcoded as last dropdown option regardless of actual user data
- **Impact:** If DB users differ, admin may not appear; if someone selects it hoping for admin login, gets confusion
- **Fix:** Fetch all admin users from DB; do not hardcode. Or better: add role-based login (username+password, not dropdown).
- **Severity:** P0

---

## High Priority Issues

### UX-01: Zero Mobile Responsiveness
- **Files:** All templates, especially `base_new.html:22-40` (260px fixed sidebar), table pages
- **Issue:** Fixed 260px sidebar that cannot collapse; tables overflow horizontally; no viewport meta tag in several templates; no touch-friendly tap targets
- **Impact:** Completely unusable on phones/tablets. Any field-worker needing to check schedule on mobile is blocked
- **Fix:** Add viewport meta to all pages; make sidebar collapsible (icon-only on <768px); convert tables to card layout on mobile; increase tap targets to 44px minimum
- **Severity:** P1

### UX-02: Design System Fragmentation (3 Competing Style Layers)
- **Files:** `styles.css` (1528 lines), `base_new.html` embedded styles, every template has its own `<style>` block
- **Issue:** `styles.css` uses `--card-shadow`, `--button-primary`; `base_new.html` uses `--apple-blue`, `--apple-border`; templates define duplicate variables. Result: inconsistent buttons, cards, badges across pages
- **Impact:** Visual inconsistency undermines trust; any future redesign becomes multi-location surgery
- **Fix:** Consolidate into ONE design token system. Suggested: rename everything to `--apple-*` in styles.css, remove per-template `<style>` blocks for shared tokens, make templates use utility classes
- **Severity:** P1

### UX-03: 8+ Unique Modal Implementations
- **Files:** `my_schedule.html`, `schedule_gantt_v2.html`, `schedule_editor_enhanced.html`, `employees_new.html`, `admin_users.html`, `constraints_new.html`, `vacations.html` — each has own modal HTML pattern + open/close JS
- **Issue:** Every template reinvents modal HTML structure, backdrop, close button animation, ESC handler. No reusable component
- **Impact:** Some modals lack ESC-to-close, some lack backdrop-click-to-close; inconsistent animations; bugs fixed in one modal stay broken in others
- **Fix:** Create one shared modal component pattern in `base_new.html` with `openModal(id)` / `closeModal(id)` functions; all templates use same HTML class structure
- **Severity:** P1

### UX-04: Duplicate Toast Implementations
- **Files:** `schedule_gantt_v2.html` (~60 lines toast JS), `my_schedule.html` (~30 lines), likely others
- **Issue:** Each file has own `showToast()` function with different timeout, positioning, color mapping
- **Impact:** Users see different toast behavior on different pages; some auto-dismiss, some don't
- **Fix:** Single global `showToast(message, type)` in a shared JS file or base template
- **Severity:** P1

### UX-05: No Loading States During Navigation
- **File:** `base_new.html:26-40` (nav links with fade transition)
- **Issue:** 300ms opacity fade on click provides no feedback that navigation is happening; on slow connections users think click did nothing and double-click
- **Impact:** Perceived brokenness; duplicate requests
- **Fix:** Show "Loading..." overlay or progress bar (similar to Gantt's save indicator) during page navigation
- **Severity:** P1

### UX-06: Heavy Emoji Dependency Over Semantic Visual Language
- **Files:** Throughout all templates; particularly `home_new.html`, `calendar_new.html`, `my_schedule.html`
- **Issue:** Navigation icons, status badges, and CTAs rely on emojis (`📋👥📊⚙️🌙`) which render differently per OS/browser; accessibility screen readers read "clipboard" instead of "Schedule" for visually impaired users
- **Impact:** Inconsistent visual identity; inaccessible to screen reader users; professional quality undermined
- **Fix:** Replace with SVG icons (inline or sprite); add `aria-label` to all icon-only elements
- **Severity:** P1

---

## Medium Priority Issues

### UX-07: No Keyboard Accessibility on Interactive Elements
- **Files:** `my_schedule.html` (~800 lines of JS), `schedule_editor_enhanced.html`, almost all templates
- **Issue:** Interactive elements use `onclick` handlers without `onkeydown`/`tabindex`; modal triggers not accessible via Tab; no focus trap in modals
- **Impact:** Keyboard-only users cannot navigate; fails WCAG 2.1 AA
- **Fix:** Add `tabindex="0"` and `onkeydown` handlers for Enter/Space; implement focus trap in modals; visible `:focus-visible` styles
- **Severity:** P2

### UX-08: No Form Validation Feedback Except Server Errors
- **Files:** `change_password.html`, `login.html`, all form modals
- **Issue:** No client-side validation; password fields have no strength meter, no confirm-match check; form errors only visible after full page reload
- **Impact:** Users submit invalid data, wait for round-trip, then get unclear error messages
- **Fix:** Add `required`, `pattern`, `minlength` attributes; inline validation on blur; real-time password match indicator
- **Severity:** P2

### UX-09: Calendar Page Has Zero Day Interactions
- **File:** `calendar_new.html:216 lines`
- **Issue:** Calendar days are inert — no click to add events, no hover to peek at details; vacation info only shown in group below the calendar
- **Impact:** Calendar is read-only reference rather than a working tool; users must navigate away to act
- **Fix:** Add click-to-view day details (reuse modal from my_schedule); add hover tooltip with events; add quick-action button for "add vacation on this day"
- **Severity:** P2

### UX-10: Gantt Editor Scroll-Sync Bugs
- **File:** `schedule_gantt_v2.html` scroll-sync between sidebar and body
- **Issue:** Two-panel scroll coupling can drift; rapid scrolling causes sidebar and timeline to desync; no scroll-snap to keep headers aligned
- **Impact:** Misread schedule assignments; visual confusion during fast scrolling
- **Fix:** Use `requestAnimationFrame` for scroll sync instead of direct `scrollTop` assignment; add scroll-snap to header row
- **Severity:** P2

### UX-11: Shift Employee Table Has No Search/Filter/Pagination
- **File:** `schedule_new.html:128 lines`
- **Issue:** Just a plain table — no search, no sort, no pagination. Admins with many shifts must scroll through entire table
- **Impact:** Cognitive overload with large datasets; slow task completion
- **Fix:** Add search input, column-sort headers, and pagination or virtual scroll
- **Severity:** P2

### UX-12: Employee Filter Interacts Poorly with Tab Filtering
- **File:** `constraints_new.html`
- **Issue:** Employee filter dropdown + tab filtering (All/Unavailable/Preferences) interaction means selecting an employee in "Unavailable" tab shows empty state with no feedback; no "no results" message explains which filter is emptying results
- **Impact:** Users think data is missing when filters are just conflicting
- **Fix:** Add combined filter state indicator (e.g., "Showing: Ivanov — Unavailable (0 results)"); suggest "Clear filters" button
- **Severity:** P2

### UX-13: Month Selector Footer Auto-Submits Without Confirmation
- **File:** `base_new.html:309-319`
- **Issue:** Changing month dropdown immediately reloads page with "Применяем..." text but no abort mechanism; if user accidentally clicks wrong month, data may be lost from unsaved changes in editor
- **Impact:** Accidental data loss when switching months with unsaved work
- **Fix:** Add "You have unsaved changes — save before switching?" prompt when `S.dirty` flag is set
- **Severity:** P2

### UX-14: No Visual Indication of Active Navigation Page
- **File:** `base_new.html:26-66`
- **Issue:** Nav links use hover states but no `.active` class to show current page; sidebar gives no "you are here" indicator
- **Impact:** Users lose orientation in the app, especially with 8+ admin pages
- **Fix:** Add `.active` class based on `request.url.path`, style with distinct background + left border accent
- **Severity:** P2

### UX-15: Drag-to-Create Shifts Has No Undo
- **File:** `schedule_gantt_v2.html`
- **Issue:** Creating a shift via drag is instant and irreversible except via separate edit modal; no "undo last action" shortcut
- **Impact:** Accidental shift creation cannot be corrected without opening modal, finding delete, confirming
- **Fix:** Add Ctrl+Z undo for last CRUD action; maintain action history stack in `S` state
- **Severity:** P2

---

## Low Priority Issues

### UX-16: Preference Modal Has Overly Complex Period/Radio Group Flow
- **File:** `my_schedule.html` preference modal
- **Issue:** Multiple nested period selectors, radio groups for time preferences, multi-date picker — all in one modal without progressive disclosure
- **Impact:** Users overwhelmed by options; high abandonment rate for preference setting
- **Fix:** Step-by-step wizard: (1) Select dates → (2) Select preference type → (3) Confirm
- **Severity:** P3

### UX-17: Change Password Page Has Inline Styles Detached from Main Design System
- **File:** `change_password.html:159 lines` — uses own embedded CSS, not `base_new.html` patterns
- **Issue:** Unique card, button, and input styles that don't match rest of app
- **Impact:** Page feels visually disconnected; any design system update misses this file
- **Fix:** Extend `base_new.html` layout, use shared card/button/input classes
- **Severity:** P3

### UX-18: Home Page Dashboard Has Hardcoded Coverage Rules
- **File:** `home_new.html:139 lines`
- **Issue:** Coverage rules displayed as static text; if rules change in DB/settings, dashboard shows stale info
- **Impact:** Misleading information; trust erosion
- **Fix:** Fetch coverage rules from DB; make dashboard data reactive
- **Severity:** P3

### UX-19: No Bulk Actions in Any Table View
- **Files:** `schedule_new.html`, `vacations.html`, `admin_users.html`, `employees_new.html`
- **Issue:** Every CRUD operation is one-at-a-time; no checkboxes, no select-all, no bulk delete/edit
- **Impact:** Extremely tedious for admins managing many employees or shifts
- **Fix:** Add checkbox column + bulk action toolbar to all list pages
- **Severity:** P3

### UX-20: Select Employee Page Is Under-Designed
- **File:** `select_employee.html:43 lines`
- **Issue:** Simple card grid with no search, no department grouping, no employee photos; empty state is minimal
- **Impact:** In organizations with many employees, finding the right person takes scrolling
- **Fix:** Add search bar, department filter, employee avatar support
- **Severity:** P3

---

## Summary

| Severity | Count | Description |
|----------|-------|-------------|
| P0 (Critical) | 3 | Security risk, broken page, hardcoded auth |
| P1 (High) | 6 | Mobile unusable, design fragmentation, duplicated components |
| P2 (Medium) | 9 | Accessibility, validation, UX polish, interaction bugs |
| P3 (Low) | 5 | Dashboard accuracy, bulk operations, visual refinement |
| **Total** | **23** | |

## Recommended Priority Order

1. Fix CRIT-01 (passwords), CRIT-02 (settings broken), CRIT-03 (login hardcoded)
2. Implement shared modal component (eliminates UX-03 across 7 files)
3. Consolidate design tokens (eliminates UX-02, enables all other visual fixes)
4. Add viewport meta + responsive breakpoints (UX-01)
5. Merge toast implementations (UX-04)
6. Add loading states, keyboard nav, form validation in parallel
7. Address P2 interaction bugs (scroll-sync, filter conflicts, active nav)
8. Polish: search/filter/pagination, bulk actions
