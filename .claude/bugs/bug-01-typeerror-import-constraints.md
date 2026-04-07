---
name: TypeError in import_constraints_from_folder
description: API endpoint calls import_operator_documents with kwargs the function does not accept, causing a 500 crash.
type: feedback
---

# Bug 01: TypeError in /constraints/import-from-folder endpoint

**Severity:** CRITICAL
**File:** `constraints_api.py:554-560`
**Status:** Verified

## Description
The endpoint `import_constraints_from_folder` passes `ai_client=None` and `progress=None` to `import_operator_documents()`, but the function signature only accepts three parameters: `base_dir`, `year`, and `month`. This causes an immediate `TypeError` whenever the endpoint is called.

## Steps to Reproduce
1. Navigate to the constraints import page
2. Select a folder and submit the form
3. The endpoint crashes with `TypeError: import_operator_documents() got an unexpected keyword argument 'ai_client'`

## Evidence
`constraints_api.py:554-560`:
```python
imported_employees, operator_constraints, operator_weekend_choices, docs_preview, warnings = import_operator_documents(
    base_dir=operators_dir,
    year=year,
    month=month,
    ai_client=None,     # NOT in function signature
    progress=None,      # NOT in function signature
)
```

`operator_docs.py:68-72`:
```python
def import_operator_documents(
    base_dir: str,
    year: int,
    month: int,
) -> tuple[...]:
```

## Suggested Fix
Remove the `ai_client=None` and `progress=None` keyword arguments from the call at line 554-560.
