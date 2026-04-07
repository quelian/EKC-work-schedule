---
name: Dead unreachable code after return statement
description: main_new.py:839-842 contains duplicate code that can never execute due to return on line 838.
type: feedback
---

# Bug 03: Dead code after return in my_schedule_page

**Severity:** LOW
**File:** `main_new.py:839-842`
**Status:** Verified

## Description
In the `my_schedule_page` function, lines 839-842 are an exact duplicate of lines 835-838, placed immediately after a `return` statement. This code is unreachable.

## Evidence
```python
        response = templates.TemplateResponse("select_employee.html", context)  # line 835
        response.set_cookie('ekc_year', str(year), max_age=365*24*60*60)       # line 836
        response.set_cookie('ekc_month', str(month), max_age=365*24*60*60)     # line 837
        return response                                                         # line 838 -- RETURN HERE
        response = templates.TemplateResponse("select_employee.html", context)  # line 839 -- UNREACHABLE
        response.set_cookie('ekc_year', str(year), max_age=365*24*60*60)       # line 840 -- UNREACHABLE
        response.set_cookie('ekc_month', str(month), max_age=365*24*60*60)     # line 841 -- UNREACHABLE
        return response                                                         # line 842 -- UNREACHABLE
```

## Suggested Fix
Delete lines 839-842.
