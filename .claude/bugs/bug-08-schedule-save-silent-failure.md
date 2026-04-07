---
name: Schedule save endpoint silently swallows exceptions
description: save_schedule_shift at main_new.py:1981-1982 catches Exception and passes, so shift creation failures are invisible to users.
type: feedback
---

# Bug 08: Schedule save endpoint silently fails

**Severity:** HIGH
**File:** `main_new.py:1981-1982`
**Status:** Verified

## Description
The `save_schedule_shift` endpoint (`POST /schedule/editor/save`) wraps the entire save operation in a try/except that catches `Exception` and executes `pass`. This means:
- Database errors (constraint violations, connection issues) are silently ignored
- The user is redirected as if the save succeeded
- No error message is stored in session flash
- No logging occurs

## Evidence
```python
    try:
        parsed_date = parse_date(date, "date")
        upsert_schedule_assignment(
            employee_name=employee_name,
            date_value=parsed_date,
            start_time=start_time,
            end_time=end_time,
            shift_type=shift_type,
            note=note,
        )
    except Exception as e:
        pass  # <-- Line 1982: Complete silence
```

## Suggested Fix
```python
    except Exception as e:
        import logging
        logging.error(f"Failed to save shift: {e}", exc_info=True)
        request.session["flash_error"] = f"Не удалось сохранить смену: {str(e)}"
```
