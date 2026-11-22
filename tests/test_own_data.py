"""Checks for the "Use your own data" loader (scripts/load_encounters.py). Writes only to tmp_path."""

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from load_encounters import scan  # noqa: E402

RAW = ROOT / "data" / "raw"
IMAGE = "chestmnist_sample_005_label_[0 0 0 1 0 1 0 0 0 0 0 0 0 0].png"  # enc_00006


def good_folder(tmp_path):
    for sub in ("images", "notes", "vitals"):
        (tmp_path / sub).mkdir()
    shutil.copy(RAW / "images" / IMAGE, tmp_path / "images" / IMAGE)
    shutil.copy(RAW / "notes" / "enc_00006_note.txt", tmp_path / "notes")
    shutil.copy(RAW / "vitals" / "enc_00006_vitals.csv", tmp_path / "vitals")
    return tmp_path


def test_sample_data_passes():
    encounters, problems, info = scan(RAW)
    assert problems == [] and info == []
    assert len(encounters) == 50
    assert all(set(f) == {"image", "note", "vitals"} for f in encounters.values())


def test_good_folder(tmp_path):
    folder = good_folder(tmp_path)
    (folder / "images" / ".DS_Store").write_bytes(b"\0")
    encounters, problems, _ = scan(folder)
    assert problems == []
    assert set(encounters) == {"enc_00006"}


def test_missing_note_is_only_a_note(tmp_path):
    folder = good_folder(tmp_path)
    (folder / "notes" / "enc_00006_note.txt").unlink()
    _, problems, info = scan(folder)
    assert problems == []
    assert info == ["enc_00006: no note; its event will have image and vitals evidence only"]


def test_missing_vitals_is_a_problem(tmp_path):
    folder = good_folder(tmp_path)
    (folder / "vitals" / "enc_00006_vitals.csv").unlink()
    _, problems, _ = scan(folder)
    assert len(problems) == 1 and "GET /event/enc_00006 would fail" in problems[0]


def test_no_images_folder(tmp_path):
    _, problems, _ = scan(tmp_path)
    assert "no images/ folder" in problems[0]


VITALS_HEADER = "ts,hr,spo2,rr\n"


@pytest.mark.parametrize("name,content,expected", [
    (f"images/{IMAGE}", b"not an image", "not a PNG image"),
    (f"images/{IMAGE}", b"version https://git-lfs.github.com/spec/v1\n", "Git LFS pointer"),
    (f"images/{IMAGE}", b"", "empty file"),
    ("images/chestmnist_sample_005_label_[0 1 2].png", b"x", "needs 14 labels of 0 or 1"),
    ("images/xray_6.png", b"x", "name must be chestmnist_sample_"),
    ("images/xray.jpg", b"x", "not a .png file"),
    ("notes/enc_00006_note.txt", b"  \n", "no text"),
    ("notes/enc_00006_note.txt", "fiebre, saturación baja".encode("latin-1"), "not UTF-8 text"),
    ("notes/note6.txt", b"text", "name must look like enc_00001_note.txt"),
    ("vitals/enc_00006_vitals.csv", b"ts,hr,rr\n2025-01-01T00:00:00,80,16\n", "missing column(s) spo2"),
    ("vitals/enc_00006_vitals.csv", VITALS_HEADER.encode(), "header only"),
    ("vitals/enc_00006_vitals.csv", (VITALS_HEADER + "yesterday,80,98,16\n").encode(), "not ISO 8601"),
    ("vitals/enc_00006_vitals.csv", (VITALS_HEADER + "2025-01-01T00:00:00,80,150,16\n").encode(),
     "spo2 150 is outside 50-100"),
    ("vitals/enc_00006_vitals.csv", (VITALS_HEADER + "2025-01-01T00:00:00,eighty,98,16\n").encode(),
     "hr 'eighty' is not a number"),
    ("vitals/enc_00006_vitals.csv",
     (VITALS_HEADER + "2025-01-01T00:00:01,80,98,16\n2025-01-01T00:00:00,80,98,16\n").encode(),
     "is not after the line before"),
    ("notes/enc_00042_note.txt", b"Follow-up.", "no image for enc_00042"),
])
def test_bad_files_are_reported(tmp_path, name, content, expected):
    folder = good_folder(tmp_path)
    path = folder / name
    path.write_bytes(content)
    _, problems, _ = scan(folder)
    assert len(problems) == 1 and expected in problems[0], problems
    assert problems[0].startswith(name.split("/")[0] + "/"), problems


def test_two_images_for_one_encounter(tmp_path):
    folder = good_folder(tmp_path)
    shutil.copy(folder / "images" / IMAGE,
                folder / "images" / "chestmnist_sample_0005_label_[0 0 0 1 0 1 0 0 0 0 0 0 0 0].png")
    _, problems, _ = scan(folder)
    assert len(problems) == 1 and "enc_00006 already comes from" in problems[0], problems


def test_check_only_writes_nothing(tmp_path):
    import subprocess
    folder = good_folder(tmp_path)
    db = ROOT / "data" / "processed" / "granite_lite.db"
    before = db.stat().st_mtime if db.exists() else None
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "load_encounters.py"),
                             "--dir", str(folder), "--check-only"], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "All files passed the checks." in result.stdout
    assert (db.stat().st_mtime if db.exists() else None) == before
