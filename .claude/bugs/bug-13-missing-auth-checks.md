---
name: Missing authentication checks on certain endpoints
description: Some endpoints lack proper authentication checks or have inconsistent authorization patterns.
type: feedback
---

# Bug 13: Missing or inconsistent auth checks on endpoints

**Severity:** MEDIUM
**Files:** `main_new.py` (various), `schedule_editor_api.py`
**Status:** Verified through code review

## 13a: login endpoint has no rate limiting
`main_new.py:1444-1470` -- `POST /login` has no rate limiting or brute force protection. An attacker can try unlimited password combinations.

## 13b: admin endpoint default password is well-known
`database.py:1711`:
```python
admin_password = "999999"
```
Combined with the fact that the username "admin" is selectable in the login dropdown (`login.html:55`), anyone who knows the codebase can log in as admin immediately after deployment.

## 13c: Some endpoints check session but not role consistently
The `admin_required` decorator in `auth.py:33-41` checks role but is not used on any endpoints -- all admin checks in `main_new.py` are done inline. This means:
- Some endpoints may forget the role check
- The decorator exists but is never applied, creating inconsistency

## 13d: Redirect to /login for non-admin on vacations page
`main_new.py:1893`:
```python
if request.session.get("user_role") != "admin":
    return RedirectResponse("/login", status_code=303)
```
Non-admin users are redirecteded to `/login` rather than a friendly "access denied" page. This is confusing UX.

## Suggested Fix
1. Add rate limiting to POST /login
2. Force admin password change on first login
3. Apply the `admin_required` decorator consistently
4. Redirect non-admin users to a proper 403 page instead of /login
