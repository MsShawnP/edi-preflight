# Test conventions for this project's `tests/`

This file applies when Claude is working in `<project>/tests/`.

## What gets tested

- Public-facing functions and behaviors.
- Edge cases the user surfaced during `/clarify`.
- Anything in FAILURES.md that has a corresponding fix in code.

## What doesn't need a test

- Glue code (one-line wrappers, trivial mappings).
- Configuration constants.
- Pure type definitions.

## Structure

- Mirror the source tree: `src/foo/bar.py` → `tests/foo/test_bar.py`.
- One file per source module unless tests are huge.
- Group related tests by behavior, not by function name.

## Test names

- Describe what the test verifies, in plain English.
- Pattern: `test_<behavior>_when_<condition>`.
- Bad: `test_function_1`, `test_parse`.
- Good: `test_parses_walmart_850_with_allowance_lines`, `test_flags_missing_mea_segment_for_catch_weight`.

## Setup and teardown

- Prefer fresh state per test over shared mutable state.
- If setup is heavy (DB, network), pin it explicitly and document why.

## Assertions

- One concept per test. If a test asserts five unrelated things, split it.
- Assertions should print useful failure messages — say what was expected and what was got.

## Mocks and fakes

- Mock at the boundary (network, filesystem, time), not internal pure functions.
- If you mock a function, comment why — what real behavior would be unreliable in this test.

## Running

- Tests must be runnable with a single command. Document it in README.md or PLAN.md.
- A failing test is more useful than an unrun test.

## When a test fails

- Read the actual output, not what you expected to see.
- Bisect: which change broke it?
- Don't suppress with `skip` or `xfail` without an issue or PLAN item to come back.
