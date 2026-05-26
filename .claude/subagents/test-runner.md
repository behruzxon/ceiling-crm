# Subagent: Test Runner

Run the standard test suite for CeilingCRM and report results.

## Test Suite

Execute these checks in order:

### 1. Unit Tests

```bash
pytest tests/unit/ -v --tb=short
```

- Run all unit tests in `tests/unit/`
- Report: PASS or FAIL
- If FAIL: list each failing test with the error message and likely cause
- Note: `asyncio_mode = "auto"` is configured, so async tests run without `@pytest.mark.asyncio`

### 2. Linting

```bash
ruff check .
```

- Run ruff linter on the entire codebase
- Report: PASS (no violations) or FAIL (list violations)
- If FAIL: for each violation, provide:
  - File and line number
  - Rule code and description
  - Suggested fix (if auto-fixable, note that `ruff check --fix .` can resolve it)

### 3. Import Smoke Test

```bash
python -c "from apps.bot.main import build_dispatcher"
```

- This verifies that all imports resolve correctly and there are no circular imports
- Report: PASS or FAIL
- If FAIL: report the ImportError with the full traceback
- Common causes: circular import, missing `__init__.py`, uninstalled dependency, typo in import path

### 4. Type Checking (Optional)

```bash
mypy . --ignore-missing-imports
```

- Run only if explicitly requested or if type-related changes were made
- Report: PASS or FAIL with list of type errors

## Report Format

```
## Test Results

### Unit Tests: PASS/FAIL
- Total: X tests
- Passed: X
- Failed: X
- Skipped: X
- Time: X.XXs
- Failures:
  - test_name: error_message (likely cause)

### Linting: PASS/FAIL
- Violations: X
- Details:
  - file.py:line: RULE description (auto-fixable: yes/no)

### Import Smoke Test: PASS/FAIL
- Error: (if failed)
- Likely cause: (if failed)

### Overall: PASS/FAIL
```

## Failure Diagnosis

When a test fails, provide analysis:

1. **What failed**: The specific assertion or error
2. **Why it failed**: The likely root cause (changed interface, missing mock, wrong import)
3. **How to fix**: Specific steps to resolve
4. **Related tests**: Other tests that might be affected by the same issue

## Common Failure Patterns

| Error | Likely Cause | Fix |
|-------|-------------|-----|
| `ImportError: cannot import name X` | Circular import or renamed symbol | Check import chain, update import |
| `AttributeError: 'AsyncMock' object has no attribute X` | Mock missing a method | Add `X = AsyncMock()` to the mock |
| `InvalidTextRepresentationError` | Missing `values_callable` on enum | Add `values_callable=lambda x: [e.value for e in x]` |
| `sqlalchemy.exc.IntegrityError` | Missing required field in test fixture | Add the field to the test data |
| `asyncio.TimeoutError` | Test waiting for event that never fires | Check async mock setup |
| `TypeError: object NoneType can't be used in 'await'` | Missing `AsyncMock` (regular Mock used for async) | Change `Mock()` to `AsyncMock()` |

## Success Criteria

All three checks must pass for a green result:
1. All unit tests pass (0 failures)
2. No ruff violations
3. Import smoke test succeeds

If any check fails, the overall result is FAIL and the issues must be resolved before proceeding.
