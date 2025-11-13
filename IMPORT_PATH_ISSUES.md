# Import Path Issues

## Problem

The codebase has inconsistent import paths that prevent the application from starting:

1. **Mixed import styles**: Some files use `from app.*` while others use `from src.app.*`
2. **Missing enum**: `PromptStatus` is imported but not defined in `src/app/db/models.py`

## Files Affected

At least 45 files have inconsistent imports (found via grep):

```
src/app/schemas/__init__.py
src/app/schemas/content.py
src/app/schemas/prompt.py
src/app/services/content_processor.py
src/app/api/dependencies.py
... and 40 more files
```

## Example Error

```python
ImportError: cannot import name 'PromptStatus' from 'app.db.models'
```

## Solution Required

1. **Standardize all imports to use `src.app.*` prefix** - This is the correct path based on project structure
2. **Add missing `PromptStatus` enum to models.py**
3. **Run comprehensive import check across all Python files**

## Status

- ✅ Fixed in `src/app/main.py`
- ✅ Fixed in `src/app/core/database.py`
- ⚠️  Needs fixing: All other files in `src/app/**/*.py`

## Recommendation

This should be addressed as a separate chore/task before the application can be fully tested.
A systematic find-and-replace operation would be appropriate.
