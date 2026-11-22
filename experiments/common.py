"""Shared helpers for the Try this experiments.

Each experiment works on a copy of data/raw/ in a temporary folder and its own
DuckDB file, so data/raw/ and data/processed/granite_lite.db are never touched,
even while `make serve` is running.
"""

import contextlib
import io
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
sys.path.insert(0, str(ROOT / "src"))

WORK = Path(tempfile.mkdtemp(prefix="granite-try-"))
# semantic_api opens data/processed/granite_lite.db and creates static/images
# relative to the working directory when it is imported. Import it from the
# scratch folder so it never touches the repo's database.
_cwd = os.getcwd()
os.chdir(WORK)
with contextlib.redirect_stdout(io.StringIO()):
    from raw_ingestion import RawDataIngestionPipeline  # noqa: E402
    from semantic_api import SemanticFusionEngine  # noqa: E402
os.chdir(_cwd)


def copy_raw(name):
    """Copy data/raw/ to a fresh folder and return its path."""
    dest = WORK / name
    shutil.copytree(RAW, dest)
    return dest


def ingest(raw_dir, db_name, pipeline_cls=None):
    """Run the same steps as `python main.py --ingest` on raw_dir into its own DuckDB file.
    Returns (pipeline results, seconds, db path). Prints nothing."""
    db = WORK / f"{db_name}.db"
    start = time.perf_counter()
    with contextlib.redirect_stdout(io.StringIO()) as out:
        pipeline = (pipeline_cls or RawDataIngestionPipeline)(str(db))
        images = pipeline.ingest_images(str(raw_dir / "images"))
        notes = pipeline.ingest_notes(str(raw_dir / "notes"))
        vitals = pipeline.ingest_vitals(str(raw_dir / "vitals"))
        if hasattr(pipeline, "write_batches"):
            pipeline.write_batches()
        pipeline.create_curated_manifest()
        violations = pipeline.get_contract_violations()["violations"]
        pipeline.close()
    seconds = time.perf_counter() - start
    errors = [line for line in out.getvalue().splitlines() if line.startswith("Error processing")]
    return {"images": len(images), "notes": len(notes), "vitals": len(vitals),
            "violations": violations, "errors": errors}, seconds, db


def engine(db):
    return SemanticFusionEngine(str(db))


def cleanup():
    shutil.rmtree(WORK, ignore_errors=True)
