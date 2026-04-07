---
name: Passwords stored in plaintext despite hash_password function existing
description: All password operations store raw text in the password_hash column. A SHA-256 hash_password function exists but is never used for storage or verification.
type: feedback
---

# Bug 06: Plaintext password storage

**Severity:** CRITICAL
**Files:** `database.py:1629-1732`, `auth.py:61,74,101`
**Status:** Verified

## Description
Despite the column being named `password_hash`, passwords are stored and compared as plaintext throughout the codebase.

## Evidence

### Plaintext storage
`database.py:1630` -- docstring literally says: `"Создает учетные данные пользователя. Пароль хранится в открытом виде."` (Password is stored in plaintext.)

`database.py:1638` -- the raw password is inserted directly:
```python
(employee_name, password, role),  # no hashing
```

`database.py:1656` -- plaintext returned:
```python
"password": row["password_hash"],  # Пароль в открытом виде
```

`database.py:1662-1673` -- `update_user_password` stores raw password without hashing.

`database.py:1759` -- `create_user_with_password` inserts raw password.

`database.py:1780` -- `get_user_with_password` returns plaintext:
```python
"password": row["password_hash"],  # Пароль в открытом виде
```

`database.py:1797` -- `list_all_users_with_passwords` returns plaintext passwords (visible in admin panel).

### Plaintext comparison
`database.py:1730-1732`:
```python
def verify_password(password: str, stored_password: str) -> bool:
    return password == stored_password  # Direct string comparison!
```

### The hash_password function exists but is never used for actual auth
`database.py:1724-1727`:
```python
def hash_password(password: str) -> str:
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()
```
This function is passed to `init_credentials_for_all_employees` as a parameter (`hash_password_func=None`) but the parameter is never used inside the function -- the function body generates and stores plaintext passwords regardless of the parameter value.

### Default admin password
`database.py:1711`:
```python
admin_password = "999999"
```
A trivial default admin password is hardcoded.

## Suggested Fix
1. Use `hash_password()` (or better, `bcrypt`/`passlib` with proper salting) in `create_user_credentials`, `update_user_password`, and `create_user_with_password`
2. Update `verify_password` to hash the input and compare hashes
3. Rename `password_hash` column usage to match reality or actually hash passwords
4. Remove the default "999999" admin password or force change on first login
5. Remove plaintext password display from admin_users.html
