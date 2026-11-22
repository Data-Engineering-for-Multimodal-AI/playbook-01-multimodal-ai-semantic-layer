"""Try this 2: which bad records does the contract catch? (make try-contract)

Makes one bad file at a time in a copy of data/raw/, ingests the copy into its
own DuckDB file and checks three things: did ingestion skip the file with an
error, did the record contract (src/models.py) count a violation, and what does
the fusion engine (GET /event/{id}) return for the encounter afterwards.

Add your own case to CASES and run it again.
"""

import common

IMG = "chestmnist_sample_002_label_[0 0 0 0 0 0 0 0 0 0 0 0 0 0].png"  # enc_00003


def rename_image(raw, new):
    (raw / "images" / IMG).rename(raw / "images" / new)


def write(path, text, encoding="utf-8"):
    path.write_bytes(text.encode(encoding))


def vitals(rows, header="ts,hr,spo2,rr"):
    return header + "\n" + "\n".join(rows) + "\n"


CASES = [
    ("image name with 13 labels", "enc_00003",
     lambda raw: rename_image(raw, "chestmnist_sample_002_label_[0 0 0 0 0 0 0 0 0 0 0 0 0].png")),
    ("image not named chestmnist_sample_*", "enc_00003",
     lambda raw: rename_image(raw, "xray_patient_3.png")),
    ("image file is not a PNG", "enc_00003",
     lambda raw: write(raw / "images" / IMG, "not an image")),
    ("note is empty", "enc_00003",
     lambda raw: write(raw / "notes" / "enc_00003_note.txt", "")),
    ("note is not UTF-8 (Latin-1)", "enc_00003",
     lambda raw: write(raw / "notes" / "enc_00003_note.txt", "Patient febril, saturación baja.", "latin-1")),
    ("note for an encounter with no image", "enc_00099",
     lambda raw: write(raw / "notes" / "enc_00099_note.txt", "History of cough.")),
    ("vitals SpO2 of 150%", "enc_00003",
     lambda raw: write(raw / "vitals" / "enc_00003_vitals.csv",
                       vitals([f"2025-09-22T19:03:{s:02d},80,150,18" for s in range(60)]))),
    ("vitals without an spo2 column", "enc_00003",
     lambda raw: write(raw / "vitals" / "enc_00003_vitals.csv",
                       vitals([f"2025-09-22T19:03:{s:02d},80,18" for s in range(60)], "ts,hr,rr"))),
    ("vitals recorded in 1999", "enc_00003",
     lambda raw: write(raw / "vitals" / "enc_00003_vitals.csv",
                       vitals([f"1999-01-01T00:00:{s:02d},80,98,18" for s in range(60)]))),
]


def event_result(db, enc):
    eng = common.engine(db)
    try:
        event = eng.fuse_event(enc)
        mods = "+".join(e["modality"] for e in event.evidence)
        return f"built ({mods})"
    except ValueError:
        return "404 not found"
    except Exception as e:
        return f"500 {type(e).__name__}"
    finally:
        eng.close()


def main():
    print(f"{'Bad input':38} {'skipped with error':>18} {'contract violation':>18}  event afterwards")
    for i, (label, enc, make_bad) in enumerate(CASES):
        raw = common.copy_raw(f"case{i}")
        make_bad(raw)
        result, _, db = common.ingest(raw, f"case{i}")
        skipped = "yes" if result["errors"] else "no"
        violated = "yes" if result["violations"] else "no"
        print(f"{label:38} {skipped:>18} {violated:>18}  {enc}: {event_result(db, enc)}")
    common.cleanup()


if __name__ == "__main__":
    main()
