---
name: Leap year edge case in hardcoded date generation
description: database.py constructs date strings with hardcoded day 31 which fails for February in leap years, and other code paths may crash on Feb 29.
type: feedback
---

# Bug 12: Leap year and February 29 edge cases

**Severity:** LOW
**Files:** `database.py:1408,1417`
**Status:** Verified through code review

## Description
As documented in Bug 02, the hardcoded `-31` end date affects February in all years, including leap years. February 2028 has 29 days, so `2028-02-31` is still invalid.

Additionally, any code that:
- Uses `date(year, month, 31)` directly (not found in current codebase)
- Iterates dates from day 1 to 30/31 without using `calendar.monthrange()`
- Assumes all months have the same number of days

## Current Protection
The `iterate_month` function in `operator_docs.py:663-669` correctly iterates using `timedelta(days=1)` and checks `cursor.month == month`, so it handles leap years correctly.

The `working_days_in_month` function in `models.py` should be verified to handle Feb 29 correctly.

## Suggested Fix
Audit all date arithmetic across the codebase to ensure `calendar.monthrange()` or timedelta-based iteration is used instead of hardcoded day numbers.
