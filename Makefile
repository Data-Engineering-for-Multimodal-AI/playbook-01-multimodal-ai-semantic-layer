.PHONY: setup run serve event check-data load try-missing try-contract try-scale smoke clean

# A bare `make` runs the smoke test, as it did before the uniform targets were added.
.DEFAULT_GOAL := smoke

# Uniform targets for The Playbooks. The book's commands (pip install -r requirements.txt,
# python main.py --ingest, python main.py --server) still work as printed.

# Install the locked dependencies into .venv.
setup:
	uv sync --frozen

# Ingest the sample data, then print fused events from the semantic layer.
run: setup
	uv run --frozen python main.py --ingest
	uv run --frozen python test_system.py
	@echo "playbook-01-multimodal-ai-semantic-layer" > .playbook-done

# Start the API and reviewer UI on http://localhost:8000.
serve: setup
	uv run --frozen python main.py --server

# With the API running (make serve): print one fused event.
#   make event ID=enc_00006
event:
	@curl -sf "http://localhost:8000/event/$(or $(ID),enc_00006)" | uv run --frozen python -m json.tool \
		|| { echo "No answer from http://localhost:8000. Is make serve running, and does $(or $(ID),enc_00006) exist?"; exit 1; }

# Your own encounters: images/, notes/ and vitals/ in DIR, named as in data/raw/.
# check-data checks every file and writes nothing; load replaces the database with them.
#   make check-data DIR=my_encounters
#   make load DIR=my_encounters
check-data: setup
	@test -n "$(DIR)" || { echo "Usage: make check-data DIR=path/to/folder"; exit 2; }
	uv run --frozen python scripts/load_encounters.py --dir "$(DIR)" --check-only

load: setup
	@test -n "$(DIR)" || { echo "Usage: make load DIR=path/to/folder"; exit 2; }
	uv run --frozen python scripts/load_encounters.py --dir "$(DIR)"

# Try this: three measured experiments (see README, "Try this"). No Docker, no network.
# They work on copies of data/raw/ in a temporary folder and leave the database alone.
try-missing: setup
	uv run --frozen python experiments/missing_modality.py

try-contract: setup
	uv run --frozen python experiments/bad_records.py

try-scale: setup
	uv run --frozen python experiments/ingest_scale.py $(SIZES)

# End-to-end check on the sample data (CPU, no network calls after install).
smoke:
	uv sync --frozen
	uv run --frozen pytest -q tests/test_smoke.py

# Remove generated files. The raw sample data in data/raw/ is kept.
clean:
	rm -rf data/processed static/images .pytest_cache
