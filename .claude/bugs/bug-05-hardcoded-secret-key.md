---
name: Hardcoded session secret key
description: main_new.py:60 hardcodes secret_key="ekc-scheduler-secret-key-2026" in source code.
type: feedback
---

# Bug 05: Hardcoded session secret key

**Severity:** HIGH
**File:** `main_new.py:60`
**Status:** Verified

## Description
The session middleware secret key is hardcoded as a string literal in source code:
```python
app.add_middleware(SessionMiddleware, secret_key="ekc-scheduler-secret-key-2026")
```

## Impact
- Anyone with access to the source code (or the repository) can forge session cookies
- If the code is public or shared, all sessions are compromised
- The key includes the year "2026" making it trivially guessable

## Suggested Fix
Read the secret key from an environment variable:
```python
import os
secret = os.environ.get("EKC_SECRET_KEY")
if not secret:
    raise RuntimeError("EKC_SECRET_KEY environment variable is required")
app.add_middleware(SessionMiddleware, secret_key=secret)
```
