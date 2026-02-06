lint:
    uvx ruff check apick.py

fix:
    uvx ruff check --fix apick.py

fmt:
    uvx ruff format apick.py

typecheck:
    uvx ty check apick.py

check: lint typecheck

test:
    uv run pytest tests/ -v

build:
    uv build

publish:
    uv publish
