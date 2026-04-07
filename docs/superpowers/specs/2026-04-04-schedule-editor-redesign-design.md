# Schedule Editor Redesign Spec — 2026-04-04

## Context

The schedule editor (`schedule_gantt_v2.html`) is a Gantt-style timeline for assigning shift schedules. It has three critical issues:
1. Drag-and-drop for creating/assigning shifts doesn't work correctly
2. The shift assignment modal doesn't open properly
3. The visual design is stale and inconsistent

Scope: Fix bugs, apply a premium visual redesign, keep the same Gantt-timeline concept.

## Problems & Fixes

### 1. Modal doesn't open
**Root cause:** The HTML for `shiftModal` has structural errors — the `</form>` tag on line 848 closes OUTSIDE the `modal-dialog`, breaking the DOM tree. The footer div is never opened. Additionally, the `modDeleteBtn` referenced in JS doesn't exist in HTML.
**Fix:** Restructure modal HTML — properly close form inside dialog, add missing footer with action buttons, add delete button.

### 2. Drag-and-drop broken
**Root causes:**
- `onRowMouseDown` miscalculates coordinates when the timeline is scrolled — `startScrollX` uses `e.clientX - startScroll` but then subtracts `rowContentLeft` which is the row's offset within its parent, creating double-offset errors
- The `pixelToTime` function receives incorrect x values, causing wrong date/time on drag
- When dragging across the timeline, the selection overlay appears on wrong dates
**Fix:** Rewrite the coordinate math to use a consistent content-space reference. Compute x as `(e.clientX - row.getBoundingClientRect().left + container.scrollLeft)`.

### 3. Drag-to-move shifts unreliable
- Scroll compensation during drag-move is fragile
- `setShiftElementPosition` doesn't account for scroll offset changes
**Fix:** Store the original `scrollLeft` at mousedown, apply delta on each mousemove.

### 4. ModalSystem dependency
The `ModalSystem` object from `base_new.html` requires `ModalSystem.init()` on DOMContentLoaded and expects `data-modal` attributes on elements. The gantt template doesn't call `ModalSystem.init()` and doesn't use the expected attributes.
**Fix:** Implement a lightweight self-contained `ModalManager` inside the editor's IIFE that doesn't depend on external init.

## Design

### Architecture

**Single file** — `schedule_editor_v3.html` (extends `base_new.html`), backward-compatible route `/schedule/editor`.

**JS structure:**
```js
(function() {
  'use strict';
  const state = { ... };
  const api = { ... };       // fetch wrappers
  const render = { ... };    // all DOM rendering
  const modal = { ... };     // self-contained modal manager
  const drag = { ... };      // mouse interactions
  const utils = { ... };     // date math, pixel math, escaping
  function init() { ... }
  document.addEventListener('DOMContentLoaded', init);
})();
```
No global variables except what's attached to `window` for inline `onclick` handlers (minimal set: `navigate`, `setViewMode`, `goToToday`, etc.).

### Layout (unchanged concept, new look)

```
┌──────────────────────────────────────────────┐
│  ←  Октябрь 2026  →   [Day|Wk|Mo] Сегодня  │
├───────────┬──────────────────────────────────┤
│           │ Пн 2 │ Вт 3 │ Ср 4 │ Чт 5 │ ... │
│  Иванов   ├──────┼──────┼──────┼──────┤     │
│  6.2/8ч   │ █████│      │ ████ │      │     │
│           ├──────┼──────┼──────┼──────┤     │
│  Петров   │      │██████│█████ │ ████ │     │
├───────────┴──────┴──────┴──────┴──────┴─────┤
│  💡Доступен  🔴Смена  🟡Конфликт  🟢Отпуск  │
└──────────────────────────────────────────────┘
```

### Visual Design — Apple iOS/macOS Style

**Эстетика Apple** — чистый, минималистичный, с ощущением нативного приложения. Большие скругления, мягкие тени, frosted glass эффекты, SF-подобная типографика.

**Color palette** (Apple HIG-inspired):
- System Blue: `#007AFF` (primary actions, active states)
- System Blue hover: `#0062CC`
- Shifts: `linear-gradient(135deg, #007AFF 0%, #5856D6 100%)` — классический Apple-градиент
- Shifts (applications): `linear-gradient(135deg, #5856D6, #AF52DE)` — purple iOS-стиль
- Availability: `linear-gradient(135deg, #34C759, #30D158)` — System Green
- Conflicts hard: `#FF3B30` (System Red) с пульсирующей обводкой
- Conflicts soft: `#FF9F0A` (System Orange)
- Vacations: `linear-gradient(135deg, #5AC8FA, #007AFF)` — cyan→blue
- Study: `linear-gradient(135deg, #5856D6, #AF52DE)` — indigo→purple
- Background: `#F2F2F7` (iOS system background) / dark `#000000`
- Surfaces: `#FFFFFF` / dark `#1C1C1E`
- Secondary surfaces: `#F9F9F9` / dark `#2C2C2E`
- Borders: `rgba(60,60,67,0.1)` / dark `rgba(84,84,88,0.65)`
- Text primary: `#000000` (87% opacity) / dark `#FFFFFF`
- Text secondary: `rgba(60,60,67,0.6)` / dark `rgba(235,235,245,0.6)`

**Typography** — SF Pro через system font stack: `-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Inter', sans-serif`. Заголовки 17px semibold, лейблы 13px, таймлайн 11px. Letter-spacing `-0.02em` для заголовков (как в iOS).

**Shift blocks** — border-radius 12px, backdrop-blur-like subtle transparency `rgba(255,255,255,0.9)`, shadow `0 2px 12px rgba(0,122,255,0.15)`, при наведении `transform: scale(1.03) translateY(-1px)` с `cubic-bezier(0.34, 1.56, 0.64, 1)` — iOS bounce. Внутри — крупное время (13px semibold), примечание (11px regular, opacity 0.85). Кнопка удаления — круг 20px с SF-иконкой `×`, появляется с `fade+scale`.

**Сетка** — разделители дней: `1px solid rgba(60,60,67,0.1)`. Получасовые линии: `dashed` с `opacity: 0.3`. Сегодня — колонка с фоном `rgba(0,122,255,0.04)` и label `СЕГОДНЯ` в стиле iOS badge.

**Модальное окно** — centered iOS-стиль: `backdrop-filter: blur(20px) saturate(180%)`, полупрозрачный чёрный фон. Диалог: `border-radius: 20px`, `padding: 24px`, тень `0 20px 60px rgba(0,0,0,0.3)`. Анимация открытия: `scale(0.9) → scale(1)` + `opacity: 0 → 1` за 250ms `ease-out`. Кнопки действий — iOS-стиль: синяя primary, серая secondary, красная destructive.

**Сайдбар** — `background: rgba(249,249,249,0.95)` с `backdrop-filter: blur(10px)`. Аватары сотрудников — круги 32px с градиентом `#007AFF → #5856D6` (как iOS contact photos). Бейдж часов — зелёный в стиле iOS badges.

**Легенда** — компактные цветные квадратики 18×14px, скругление 4px (как iOS color swatches).

**Toast** — `border-radius: 16px`, `backdrop-filter: blur(10px)`, левая граница 4px цветная. Slide-up анимация.

**Анимации** — shift blocks: `shiftSlideIn` (scaleX 0→1 с bounce). Модал: fade+scale. Drag preview: плавное появление `opacity` с fade. Всё через `cubic-bezier(0.4, 0, 0.2, 1)` (Apple standard easing).

**Dark theme** — чистый OLED-стиль: `#000000` фон, `#1C1C1E` карточки, `#2C2C2E` вторичные, акценты чуть ярче для контраста. Границы `rgba(84,84,88,0.65)`. Тени глубже. Сдвиги смен: `linear-gradient(135deg, #0A84FF, #5E5CE6)` — чуть ярче на тёмном фоне.

### Data flow (unchanged)

1. Page loads → calls `GET /api/v1/schedule/editor/data?start_date=...&end_date=...`
2. User creates shift → `POST /api/v1/schedule/editor/shifts` (optimistic UI update)
3. User updates shift → `PUT /api/v1/schedule/editor/shifts` (optimistic + rollback on error)
4. User deletes shift → `DELETE /api/v1/schedule/editor/shifts` (optimistic + rollback on error)

The API endpoints are correct and working. Only the client-side JS needs fixing.

## Implementation Plan

1. Fix `schedule_gantt_v2.html` — fix modal HTML structure, add missing buttons
2. Add `ModalManager` — self-contained open/close that works without `ModalSystem.init()`
3. Rewrite drag coordinate math — use `getBoundingClientRect()` for accurate positioning
4. Apply new CSS design — modern color palette, shadows, animations
5. Test drag-to-create, drag-to-move, resize, modal open/close, CRUD operations
