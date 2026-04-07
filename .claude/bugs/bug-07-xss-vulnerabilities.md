---
name: XSS vulnerabilities in templates and JavaScript
description: User-controlled data is rendered without proper escaping in multiple templates and in schedule_gantt_v2.html, allowing cross-site scripting.
type: feedback
---

# Bug 07: XSS vulnerabilities

**Severity:** HIGH
**Files:** `my_schedule.html`, `base_new.html:273-275`, `schedule_gantt_v2.html`
**Status:** Verified through code review

## Description
Multiple locations render user-controlled data without HTML escaping, enabling stored XSS attacks.

## 7a: base_new.html -- error notices rendered without escaping
`base_new.html:273-275`:
```html
<div class="bg-red-50 ...">
    {{ error }}
</div>
```
Jinja2 by default auto-escapes in `.html` templates, but this depends on how the Jinja2 environment is configured. Check `app/templating.py` to verify autoescape is enabled.

## 7b: schedule_gantt_v2.html -- employee name in data attribute
`schedule_gantt_v2.html:1151`:
```javascript
html += `<div class="g-emp-row" data-emp="${emp.name}">`
```
Employee names come from the database which is populated from operator profiles. If a name contains special characters or is crafted maliciously, it could break out of the attribute.

## 7c: schedule_gantt_v2.html -- escHtml not used on all user content
`schedule_gantt_v2.html:1970`:
```javascript
function escHtml(s) { return s ? s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;') : ''; }
```
The `escHtml` function exists and is used for notes and preference text, but:
- `emp.name` in sidebar (line 1154) is NOT escaped via `escHtml` -- rendered as `${emp.name}` directly
- `shift.start_time` and `shift.end_time` (line 1293) are rendered directly: `${shift.start_time} - ${shift.end_time}`
- `getBlockText()` output includes `note` which could contain user-generated content

## Impact
An attacker who can control employee names, shift notes, or constraint notes could inject arbitrary JavaScript executed in other users' browsers.

## Suggested Fix
1. Verify Jinja2 autoescape is enabled in `app/templating.py`
2. In `schedule_gantt_v2.html`, use `escHtml()` for ALL user-generated content including `emp.name`
3. Sanitize input at the API layer before storing in database
