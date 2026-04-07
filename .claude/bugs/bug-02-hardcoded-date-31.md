---
name: Hardcoded "-31" end date for all months
description: database.py uses f"{year}-{month:02d}-31" for all months, which is invalid for Feb/Apr/Jun/Sep/Nov.
type: feedback
---

# Bug 02: Hardcoded month end date "-31"

**Severity:** LOW
**File:** `database.py:1408,1417`
**Status:** Verified

## Description
The function `list_schedule_assignments` uses `f"{year}-{month:02d}-31"` as the end date for all months. Months like February (28/29), April (30), June (30), September (30), and November (30) do not have a 31st day.

## Steps to Reproduce
1. Query schedule assignments for February: `list_schedule_assignments(2026, 2)`
2. The end date becomes `"2026-02-31"` which is not a valid ISO date

## Impact
SQLite performs lexicographic string comparison, so `"2026-02-31"` is greater than any valid February date like `"2026-02-28"`. This means the query still returns correct results for February. However, if any code path calls `date.fromisoformat()` on this value (e.g., if the parameter were used differently), it would crash. The real issue is semantic incorrectness and fragility.

## Suggested Fix
Use `calendar.monthrange(year, month)[1]` to get the actual last day:
```python
last_day = calendar.monthrange(year, month)[1]
(f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day}")
```
