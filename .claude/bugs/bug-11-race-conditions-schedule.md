---
name: Race conditions in schedule save/load and optimistic UI updates
description: Concurrent edits to the same shift can overwrite each other. The optimistic UI pattern has no locking or version control.
type: feedback
---

# Bug 11: Race conditions in schedule save and load

**Severity:** MEDIUM
**Files:** `main_new.py:1951-1992`, `schedule_editor_api.py:193-267`, `schedule_gantt_v2.html:1843-1936`
**Status:** Verified through code review

## 11a: No concurrency control on database writes
The `schedule_assignments` table uses `UNIQUE(employee_name, date, start_time, end_time)` as its constraint, but:
- Multiple users can open the same schedule editor in different tabs
- Optimistic UI updates (`schedule_gantt_v2.html`) apply changes locally before the server responds
- If two users edit the same shift simultaneously, the last write wins with no conflict detection
- There is no `updated_at` version check on UPDATE operations

## 11b: Optimistic rollback can lose data
`schedule_gantt_v2.html:1876-1906` (updateShift):
```javascript
const orig = { ...S.shifts[idx] };
Object.assign(S.shifts[idx], fields);
render();
// ... async fetch ...
} catch (err) {
    S.shifts[idx] = orig;  // Rollback
}
```
If the server returns success but with different data than expected, the local state is overwritten with the server response. If another change was made in parallel, it is lost.

## 11c: No protection against double-submission
The shift save endpoints do not use idempotency tokens or debounce at the server level. Rapid double-clicking the save button could create duplicate shifts.

## Suggested Fix
1. Add an `updated_at` or version column to `schedule_assignments`
2. Use `UPDATE ... WHERE updated_at = ?` for optimistic locking
3. Add server-side debouncing or idempotency keys for shift operations
4. Add a visual "saving" indicator that disables form submission
