---
name: escAttr function does not properly escape HTML in JavaScript context
description: The escAttr function in schedule_gantt_v2.html only escapes single quotes and backslashes, but employee names are injected into onclick handlers where double quotes and angle brackets also need escaping.
type: feedback
---

# Bug 15: Improper escAttr function in Gantt editor

**Severity:** MEDIUM
**File:** `schedule_gantt_v2.html:1202-1203,1971`
**Status:** Verified

## Description
`escAttr` at line 1971:
```javascript
function escAttr(s) { return s ? s.replace(/'/g, "\\'").replace(/\\/g, '\\\\') : ''; }
```

It is used at line 1203:
```javascript
onmousedown="onRowMouseDown(event, '${escAttr(emp.name)}')"
```

This function only escapes single quotes and backslashes. It does NOT escape:
- Double quotes `"` -- could break out of the attribute if the attribute delimiter changes
- Angle brackets `<>` -- could inject HTML attributes
- Backticks -- could inject into template literal context

If an employee name contains `"` or other special characters, the onclick handler could be broken or exploited.

## Impact
An employee name like `test" onclick="alert(1)" x="` could inject arbitrary JavaScript.

## Suggested Fix
Use `escHtml` instead of `escAttr` for the onclick attribute value, or improve `escAttr` to also escape HTML-special characters:
```javascript
function escAttr(s) {
    if (!s) return '';
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#x27;');
}
```
