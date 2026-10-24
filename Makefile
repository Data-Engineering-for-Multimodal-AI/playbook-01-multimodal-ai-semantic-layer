.PHONY: smoke

# End-to-end check on the sample data (CPU, no network calls after install).
smoke:
	uv sync --frozen
	uv run --frozen pytest -q tests/test_smoke.py
