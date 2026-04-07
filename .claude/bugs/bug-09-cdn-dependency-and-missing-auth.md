---
name: Hardcoded external CDN dependencies and missing CSP
description: Templates load Tailwind CSS from cdn.tailwindcss.com and Google Fonts with no fallback, no integrity checks, and no Content Security Policy.
type: feedback
---

# Bug 09: Untrusted external CDN dependencies

**Severity:** MEDIUM
**Files:** `base_new.html:7-8`, `login.html:7-8`, `schedule_gantt_v2.html` (inline)
**Status:** Verified

## Description
The application loads critical resources from external CDNs:
```html
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:..." rel="stylesheet">
```

No `integrity` (SRI) hashes are present, and no Content Security Policy is configured.

## Impact
- If the CDN is compromised, attackers can inject malicious JavaScript
- If the CDN goes down, the application UI breaks
- Tailwind's CDN script is particularly risky as it executes arbitrary JavaScript in the page context
- No CSP headers are set via FastAPI middleware to restrict resource loading

## Suggested Fix
1. Add `integrity` and `crossorigin` attributes to all external script/link tags
2. Bundle critical assets locally instead of loading from CDN
3. Add Content-Security-Policy headers via FastAPI middleware
