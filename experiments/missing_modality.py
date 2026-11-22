"""Try this 1: what happens when one modality is missing? (make try-missing)

Copies data/raw/, deletes the note, the vitals or both for 10 of the 50
encounters (enc_00041 to enc_00050), ingests each copy into its own DuckDB file
and asks the fusion engine (the code behind GET /event/{id}) for every event.

It prints, per case, how many events the engine can build, how many fail and
with what error, and the mean confidence of the complete and the incomplete
encounters. Change MISSING or the confidence formula in fuse_event()
(src/semantic_api.py) and run it again.
"""

from statistics import mean

import common

MISSING = [f"enc_{n:05d}" for n in range(41, 51)]
CASES = [
    ("nothing missing", []),
    ("10 notes missing", ["note"]),
    ("10 vitals missing", ["vitals"]),
    ("10 notes and vitals missing", ["note", "vitals"]),
]


def run_case(label, drop):
    raw = common.copy_raw(label.replace(" ", "_"))
    for enc in MISSING:
        if "note" in drop:
            (raw / "notes" / f"{enc}_note.txt").unlink()
        if "vitals" in drop:
            (raw / "vitals" / f"{enc}_vitals.csv").unlink()
    _, _, db = common.ingest(raw, label.replace(" ", "_"))
    eng = common.engine(db)
    ids = [r[0] for r in eng.conn.execute("SELECT encounter_id FROM curated_manifest").fetchall()]
    ok, failed, errors = {}, [], set()
    for enc in ids:
        try:
            ok[enc] = eng.fuse_event(enc).confidence
        except Exception as e:  # what GET /event/{id} turns into HTTP 500
            failed.append(enc)
            errors.add(type(e).__name__)
    eng.close()
    complete = [c for e, c in ok.items() if e not in MISSING or not drop]
    partial = [c for e, c in ok.items() if e in MISSING and drop]
    return len(ids), len(ok), len(failed), ", ".join(sorted(errors)) or "-", complete, partial


def fmt(values):
    return f"{mean(values):.3f}" if values else "-"


def main():
    print(f"{'Case':30} {'events':>6} {'built':>5} {'failed':>6}  {'error':17} "
          f"{'confidence (complete)':>21} {'(incomplete)':>12}")
    for label, drop in CASES:
        n, built, failed, errors, complete, partial = run_case(label, drop)
        print(f"{label:30} {n:6} {built:5} {failed:6}  {errors:17} {fmt(complete):>21} {fmt(partial):>12}")
    common.cleanup()


if __name__ == "__main__":
    main()
