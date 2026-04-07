---
name: Error messages from exceptions exposed to users via session flash
description: Multiple endpoints expose raw exception messages (str(e)) in flash error messages, leaking internal details to end users.
type: feedback
---

# Bug 14: Internal error details exposed to users

**Severity:** MEDIUM
**File:** `main_new.py` (multiple locations)
**Status:** Verified through code review

## Description
At least 8 locations include raw exception messages in user-visible flash errors:

- `main_new.py:983`: `f"Не удалось добавить ограничение: {str(e)}"`
- `main_new.py:1046`: `f"Не удалось добавить пожелание: {str(e)}"`
- `main_new.py:1160`: `f"Не удалось добавить пожелание: {str(e)}"`
- `main_new.py:1201`: `f"Не удалось обновить пожелание: {str(e)}"`
- `main_new.py:1225`: `f"Ошибка удаления: {str(e)}"`
- `main_new.py:1284`: `f"Не удалось добавить ограничение: {str(e)}"`
- `main_new.py:1363`: `f"Ошибка редактирования: {str(e)}"`
- `main_new.py:1413`: `f"Ошибка редактирования: {str(e)}"`

## Impact
- Database schema details (column names, table names) can leak via SQLite error messages
- Stack traces or internal paths may be exposed
- Attackers can use error messages for reconnaissance

## Suggested Fix
Log the full exception internally but show only a generic message to users:
```python
    except Exception as e:
        import logging
        logging.error(f"Error adding constraint: {e}", exc_info=True)
        request.session["flash_error"] = "Произошла ошибка. Попробуйте ещё раз."
```
