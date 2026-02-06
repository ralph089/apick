# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**apick** — a single-file fzf-powered OpenAPI API client CLI tool. Users point it at an OpenAPI spec (URL or file), pick an endpoint via fzf, fill in parameters interactively, and execute the request. It also supports request history with fzf replay.

## Commands

```bash
# Lint & format
uvx ruff check apick.py
uvx ruff format apick.py
uvx ruff check --fix apick.py    # auto-fix

# Type checking
uvx ty check apick.py

# Run all tests
uv run pytest tests/ -v

# Run a single test
uv run pytest tests/test_apick.py::TestClassName::test_method_name -v

# Build
uv build

# Run locally without installing
uv run apick.py <spec-url-or-file>
```

Use `just <recipe>` as shorthand (e.g., `just lint`, `just test`, `just check` runs lint+typecheck).

## Architecture

Single-module design — all code lives in `apick.py`. Entry point is `main()`, registered as the `apick` console script via `pyproject.toml`.

**Flow:** `fetch_spec` → `extract_endpoints` → `pick_endpoint` (fzf) → `collect_params` (interactive prompts) → `execute_request` (requests library). For request bodies, `generate_template` creates a JSON scaffold from the schema, opened in `$EDITOR` via `edit_body`.

**Key internals:**
- `resolve_ref` / `resolve_schema` — handle OpenAPI `$ref` and `allOf` resolution
- `format_for_fzf` / `endpoint_detail` — fzf display and preview pane formatting
- `format_schema_tree` — renders JSON schemas as readable trees
- History is stored at `~/.apick/history.json`, capped at 500 entries; auth headers are stripped before saving

**fzf preview:** The tool re-invokes itself with hidden `--_preview` and `--_spec-file` flags to render the preview pane in a subprocess.

## Code Conventions

- Python 3.10+ (uses `X | Y` union syntax, no `from __future__`)
- Ruff for linting and formatting, line length 100
- `print()` is allowed (T201 ignored) — this is a CLI tool
- Subprocess calls to `fzf`, `jq`, and `$EDITOR` are expected (S603/S607 ignored)
- Tests use pytest with `unittest.mock`; only pure/mockable functions are tested (no fzf interaction tests)
- Version in `apick.py:__version__`, managed by python-semantic-release
- CI runs lint, format check, typecheck, and tests on Python 3.10/3.12/3.13
