---
name: Silent exception handling with bare except Exception: pass
description: Five POST endpoints silently swallow all exceptions with `except Exception: pass`, hiding errors from developers and users.
type: feedback
---

# Bug 04: Silent exception handling in POST endpoints

**Severity:** HIGH
**File:** `main_new.py` (multiple locations)
**Status:** Verified

## Description
Five POST endpoint handlers catch `Exception` and execute `pass`, meaning any error -- database failures, invalid input, programming bugs -- is silently swallowed. Users get no feedback and developers cannot diagnose production issues.

## Instances Found

### 4a: `main_new.py:1006-1007` -- delete_unavailable
```python
    try:
        parsed_date = parse_date(date, "date")
        delete_study_constraint(employee_name, parsed_date, start_time, end_time)
    except Exception:
        pass
```
Deleting an unavailable slot can fail silently. User thinks the deletion succeeded but it may not have.

### 4b: `main_new.py:1120-1121` -- delete_preference
```python
    try:
        parsed_date = parse_date(date, "date")
        delete_schedule_preference(employee_name, parsed_date, preference_type)
    except Exception:
        pass
```
Same pattern -- preference deletion failures are hidden.

### 4c: `main_new.py:1312-1313` -- delete_constraint
```python
    try:
        parsed_date = parse_date(date, "date")
        delete_study_constraint(employee_name, date_value=parsed_date, start_time=start_time, end_time=end_time)
    except Exception:
        pass
```

### 4d: `main_new.py:1878-1879` -- delete_vacation
```python
    try:
        delete_vacation_entry(vacation_id)
    except Exception:
        pass
```

### 4e: `main_new.py:2021-2022` -- delete_schedule_shift
```python
    try:
        ...
        if shift:
            delete_schedule_assignment(...)
    except Exception:
        pass
```

## Suggested Fix
At minimum, log the exception:
```python
    except Exception as e:
        import logging
        logging.error(f"Error in {endpoint_name}: {e}", exc_info=True)
        request.session["flash_error"] = "Произошла ошибка при удалении"
```
