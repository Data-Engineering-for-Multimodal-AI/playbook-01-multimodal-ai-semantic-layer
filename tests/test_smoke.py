"""
End-to-end smoke test: ingest the sample data, then call every README endpoint.

Runs on CPU in a few seconds and makes no network calls. Run with `make smoke`.
"""

import importlib
import os
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "processed" / "granite_lite.db"


def run_main(*args):
    result = subprocess.run(
        [sys.executable, "main.py", *args],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def table_counts():
    conn = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        return conn.execute(
            "SELECT count(*), count(DISTINCT encounter_id) FROM curated_manifest"
        ).fetchone()
    finally:
        conn.close()


@pytest.fixture(scope="module")
def client():
    # Ingest twice: --setup is an alias for --ingest, and a rerun must not duplicate rows.
    first = run_main("--ingest")
    assert "Images processed: 50" in first
    assert "Contract violations: 0" in first
    assert table_counts() == (50, 50)
    run_main("--setup")
    assert table_counts() == (50, 50)

    # semantic_api opens the DB and uses relative paths at import time,
    # so import it only after ingestion and from the repo root.
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT / "src"))
    semantic_api = importlib.import_module("semantic_api")
    from fastapi.testclient import TestClient

    with TestClient(semantic_api.app) as test_client:
        yield test_client
    semantic_api.fusion_engine.close()


def test_health_and_root(client):
    assert client.get("/health").json()["status"] == "healthy"
    assert client.get("/").status_code == 200


def test_encounters(client):
    encounters = client.get("/encounters").json()
    assert len(encounters) == 50
    assert encounters[0]["encounter_id"] == "enc_00001"


def test_event_fuses_three_modalities(client):
    event = client.get("/event/enc_00006").json()
    # enc_00006 is chestmnist_sample_005, labelled infiltration + nodule.
    assert event["diagnosis"] == "infiltration"
    assert [e["modality"] for e in event["evidence"]] == ["image", "note", "vitals"]
    assert event["evidence"][0]["findings"] == ["infiltration", "nodule"]
    assert event["evidence"][2]["summary"]["data_points"] == 120


def test_unknown_encounter_is_404(client):
    assert client.get("/event/enc_99999").status_code == 404


def test_reviewer_ui(client):
    response = client.get("/reviewer/enc_00001")
    assert response.status_code == 200
    assert "enc_00001" in response.text


def test_static_image_served(client):
    name = "chestmnist_sample_000_label_[0 0 0 0 0 0 0 0 0 0 0 0 0 0].png"
    response = client.get(f"/static/images/{name}")
    assert response.status_code == 200
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_submit_correction(client):
    response = client.post("/corrections", json={
        "encounter_id": "enc_00001",
        "diagnosis": "pneumonia",
        "confidence": 0.9,
        "corrections": {"reason": "Clinical assessment"},
    })
    assert response.status_code == 200
    assert response.json()["encounter_id"] == "enc_00001"


def test_note_findings_match_image_labels():
    # The synthetic notes name only conditions their image is labelled with
    import re
    sys.path.insert(0, str(ROOT / "src"))
    from data_generator import ClinicalNoteGenerator
    from models import parse_filename_to_encounter
    terms = ClinicalNoteGenerator().clinical_terms
    assert len(terms) == 14
    for image in (ROOT / "data" / "raw" / "images").glob("*.png"):
        encounter_id, labels = parse_filename_to_encounter(image.name)
        note = (ROOT / "data" / "raw" / "notes" / f"{encounter_id}_note.txt").read_text()
        found = re.search(r"Notable findings include ([^.]*)", note)
        if found:
            for term in found.group(1).split(", "):
                assert labels[terms.index(term)] == 1, (encounter_id, term)
