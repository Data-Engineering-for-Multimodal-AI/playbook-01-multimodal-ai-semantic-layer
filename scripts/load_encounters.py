"""Check a folder of your own encounters and ingest it into the semantic layer.

    make check-data DIR=my_encounters    # check every file, write nothing
    make load DIR=my_encounters          # check it, then rebuild the database from it

The folder uses the same layout and file names as data/raw/:

    my_encounters/
      images/  chestmnist_sample_000_label_[0 0 0 1 0 0 0 0 0 0 0 0 0 0].png   -> enc_00001
      notes/   enc_00001_note.txt                  (UTF-8 text, optional)
      vitals/  enc_00001_vitals.csv                (columns ts,hr,spo2,rr; one per image)

The number after "sample_" is the image number; image N becomes encounter
enc_{N+1}, padded to five digits. The 14 labels are 0 or 1, in ChestMNIST order.

The checks cover what makes ingestion skip a file, silently drop it, or makes
GET /event/{id} fail later: file names and types, PNG files that aren't PNGs,
Git LFS pointers, text that isn't UTF-8, missing or non-numeric vitals columns,
timestamps that don't parse or go backwards, values outside plausible ranges,
notes or vitals with no image, and images with no vitals. If any check fails,
nothing is written.

`make load` replaces the database (data/processed/granite_lite.db) with your
encounters, as `python main.py --ingest` does for the samples, and copies your
images to static/images/ for the reviewer page. Stop `make serve` first.
`make run` puts the sample data back.
"""

import argparse
import csv
import os
import re
import shutil
import struct
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGE_NAME = re.compile(r"chestmnist_sample_(\d+)_label_\[([^\]]*)\]\.png")
NOTE_NAME = re.compile(r"(enc_\d{5})_note\.txt")
VITALS_NAME = re.compile(r"(enc_\d{5})_vitals\.csv")
VITALS_COLUMNS = ["ts", "hr", "spo2", "rr"]
RANGES = {"hr": (20, 250), "spo2": (50, 100), "rr": (4, 60)}  # beats/min, %, breaths/min
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def lfs_or_empty(path):
    head = path.read_bytes()[:100]
    if not head:
        return "empty file"
    if head.startswith(b"version https://git-lfs"):
        return "Git LFS pointer, not the file (run git lfs pull)"
    return None


def check_image(path):
    """Return (encounter_id or None, [problems])."""
    m = IMAGE_NAME.fullmatch(path.name)
    if not m:
        return None, ["name must be chestmnist_sample_<number>_label_[<14 labels>].png"]
    labels = m.group(2).split()
    if len(labels) != 14 or any(x not in ("0", "1") for x in labels):
        return None, [f"needs 14 labels of 0 or 1 in the name, found {len(labels)}: [{m.group(2)}]"]
    encounter = f"enc_{int(m.group(1)) + 1:05d}"
    problem = lfs_or_empty(path)
    if problem:
        return encounter, [problem]
    data = path.read_bytes()[:24]
    if not data.startswith(PNG_MAGIC) or data[12:16] != b"IHDR":
        return encounter, ["not a PNG image"]
    width, height = struct.unpack(">II", data[16:24])
    if width == 0 or height == 0:
        return encounter, [f"image is {width}x{height}"]
    return encounter, []


def read_text(path):
    """Return (text or None, problem or None)."""
    problem = lfs_or_empty(path)
    if problem:
        return None, problem
    try:
        return path.read_text(encoding="utf-8"), None
    except UnicodeDecodeError:
        return None, "not UTF-8 text (save it as UTF-8)"


def check_note(path):
    text, problem = read_text(path)
    if problem:
        return [problem]
    if not text.strip():
        return ["no text"]
    return []


def check_vitals(path):
    text, problem = read_text(path)
    if problem:
        return [problem]
    rows = list(csv.reader(text.splitlines()))
    if not rows:
        return ["no header row"]
    header = [c.strip() for c in rows[0]]
    missing = [c for c in VITALS_COLUMNS if c not in header]
    if missing:
        return [f"missing column(s) {', '.join(missing)}; needs {','.join(VITALS_COLUMNS)}"]
    if len(rows) < 2:
        return ["header only, no readings"]
    col = {c: header.index(c) for c in VITALS_COLUMNS}
    problems, previous = [], None
    for line, row in enumerate(rows[1:], start=2):
        if len(row) != len(header):
            problems.append(f"line {line}: {len(row)} values, header has {len(header)}")
            continue
        try:
            ts = datetime.fromisoformat(row[col["ts"]].strip())
        except ValueError:
            problems.append(f"line {line}: timestamp {row[col['ts']]!r} is not ISO 8601")
            continue
        if previous and ts <= previous:
            problems.append(f"line {line}: timestamp {ts.isoformat()} is not after the line before")
        previous = ts
        for name, (low, high) in RANGES.items():
            try:
                value = float(row[col[name]])
            except ValueError:
                problems.append(f"line {line}: {name} {row[col[name]]!r} is not a number")
                continue
            if not low <= value <= high:
                problems.append(f"line {line}: {name} {value:g} is outside {low}-{high}")
        if len(problems) >= 3:
            problems.append("(stopped after 3 problems in this file)")
            break
    return problems


def scan(folder):
    """Check every file. Returns ({encounter_id: {modality: path}}, [problems], [notes])."""
    folder = Path(folder)
    problems, info = [], []
    encounters = {}
    if not (folder / "images").is_dir():
        return {}, [f"{folder}: no images/ folder (see the layout in scripts/load_encounters.py)"], []

    def rel(path):
        return path.relative_to(folder).as_posix()

    for sub, suffix, check in (("images", ".png", None), ("notes", ".txt", check_note),
                               ("vitals", ".csv", check_vitals)):
        if not (folder / sub).is_dir():
            continue
        for path in sorted((folder / sub).iterdir()):
            if path.name.startswith(".") or path.is_dir():
                continue
            if path.suffix.lower() != suffix:
                problems.append(f"{rel(path)}: not a {suffix} file; ingestion would skip it")
                continue
            if sub == "images":
                encounter, found = check_image(path)
            else:
                m = (NOTE_NAME if sub == "notes" else VITALS_NAME).fullmatch(path.name)
                if not m:
                    expected = "enc_00001_note.txt" if sub == "notes" else "enc_00001_vitals.csv"
                    problems.append(f"{rel(path)}: name must look like {expected}")
                    continue
                encounter, found = m.group(1), check(path)
            problems += [f"{rel(path)}: {p}" for p in found]
            if encounter is None:
                continue
            modality = {"images": "image", "notes": "note", "vitals": "vitals"}[sub]
            entry = encounters.setdefault(encounter, {})
            if modality in entry:
                problems.append(f"{rel(path)}: {encounter} already comes from {rel(entry[modality])}")
                continue
            entry[modality] = path

    for encounter, files in sorted(encounters.items()):
        if "image" not in files:
            for path in files.values():
                problems.append(f"{rel(path)}: no image for {encounter}; it would never appear in an event")
            continue
        if "vitals" not in files:
            problems.append(f"{rel(files['image'])}: no vitals/{encounter}_vitals.csv; "
                            f"GET /event/{encounter} would fail")
        if "note" not in files:
            info.append(f"{encounter}: no note; its event will have image and vitals evidence only")
    encounters = {e: f for e, f in encounters.items() if "image" in f}
    return encounters, problems, info


def database_in_use():
    import duckdb
    db = ROOT / "data" / "processed" / "granite_lite.db"
    if not db.exists():
        return False
    try:
        duckdb.connect(str(db)).close()
        return False
    except duckdb.IOException:
        return True


def load(folder):
    sys.path.insert(0, str(ROOT / "src"))
    from raw_ingestion import run_raw_ingestion_pipeline
    static = ROOT / "static" / "images"
    static.mkdir(parents=True, exist_ok=True)
    for image in (folder / "images").glob("*.png"):
        shutil.copy2(image, static / image.name)
    print(f"Copied images to {static.relative_to(ROOT)}")
    (ROOT / "data" / "processed").mkdir(parents=True, exist_ok=True)
    # The pipeline and the API use paths relative to the repo root, as main.py does.
    os.chdir(ROOT)
    base = Path(os.path.relpath(folder, ROOT))
    return run_raw_ingestion_pipeline(
        images_dir=str(base / "images"),
        notes_dir=str(base / "notes"),
        vitals_dir=str(base / "vitals"),
    )


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def main():
    p = argparse.ArgumentParser(description="Check a folder of encounters and ingest it.")
    p.add_argument("--dir", type=Path, required=True, help="folder with images/, notes/, vitals/")
    p.add_argument("--check-only", action="store_true", help="check the files and write nothing")
    args = p.parse_args()
    folder = args.dir.resolve()
    if not folder.is_dir():
        sys.exit(f"No such folder: {args.dir}")

    encounters, problems, info = scan(folder)
    counts = {m: sum(m in f for f in encounters.values()) for m in ("image", "note", "vitals")}
    print(f"{plural(len(encounters), 'encounter')} in {args.dir}: {plural(counts['image'], 'image')}, "
          f"{plural(counts['note'], 'note')}, {plural(counts['vitals'], 'vitals file')}")
    for line in info:
        print(f"  note: {line}")
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for line in problems:
            print(f"  {line}")
        sys.exit("\nFix or remove these files and run again. Nothing was written.")
    if not encounters:
        sys.exit("No images found. Nothing was written.")
    print("All files passed the checks.")
    if args.check_only:
        return
    if database_in_use():
        sys.exit("The database is open in another process (is make serve running?). "
                 "Stop it and run again. Nothing was written.")
    print()
    results = load(folder)
    print(f"\nLoaded {results['image_records']} encounters into data/processed/granite_lite.db. "
          f"Start the API with make serve and open http://localhost:8000/reviewer/{min(encounters)}")


if __name__ == "__main__":
    main()
