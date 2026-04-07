---
name: Drag-and-drop shift editing edge cases in Gantt editor
description: The schedule_gantt_v2.html drag-to-create and drag-to-move functionality has several edge cases that can cause incorrect shift placement.
type: feedback
---

# Bug 10: Gantt editor drag-and-drop edge cases

**Severity:** MEDIUM
**File:** `schedule_gantt_v2.html:1431-1719`
**Status:** Verified through code review

## 10a: Scroll position not accounted during drag
`schedule_gantt_v2.html:1619`:
```javascript
const dx = (ev.clientX - startX) + (getTimelineScrollLeft() - startScroll);
```
Scroll compensation is implemented for drag-move (`onShiftMouseDown`) and resize (`onResizeStart`), but NOT for the create drag (`onRowMouseDown` at line 1431). If the timeline is scrolled horizontally during a create drag, the pixel-to-time mapping will be incorrect because `pixelToTime` uses the raw `x` offset without scroll compensation.

## 10b: Drag outside date boundary silently clamps
`schedule_gantt_v2.html:1470-1471`:
```javascript
if (dEnd === S.drag.dateStr) {
    S.drag.endSlot = timeToMin(tEnd) + 30;
}
```
If the user drags across a day boundary, the end slot is simply not updated. No visual feedback is given that the drag crossed a boundary.

## 10c: Empty row (no employee) click handling
`onRowMouseDown` is attached to `.g-tl-row` elements which are only created for employees. Clicking on an empty area of the timeline (between rows, or in the gap below rows) does nothing and provides no feedback.

## 10d: pixelToTime past end returns last slot
`schedule_gantt_v2.html:1001-1006`:
```javascript
const lastD = dates[dates.length - 1];
const ds = fmtDate(lastD);
const h = getHoursForDate(ds);
return { dateStr: ds, time: minToTime(h.end * 60 - 30) };
```
Clicking past the end of the timeline clamps to the last date's last slot, which may be unexpected behavior when the user clicks on an empty area.

## Suggested Fix
1. Add scroll compensation to `onRowMouseDown` (create drag)
2. Show visual feedback when drag crosses day boundary
3. Handle clicks on empty timeline areas gracefully
