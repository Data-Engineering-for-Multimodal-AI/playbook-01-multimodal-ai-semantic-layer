"""Try this 3: one INSERT per record, or one per table? (make try-scale)

Makes 500, 2,000 and 5,000 encounters by copying the 50 sample encounters under
new encounter IDs, and ingests each set twice into its own DuckDB file: as
`python main.py --ingest` does it (one INSERT statement per record), and with
the same records collected and written in one INSERT per table. Both runs read
the same files and write the same rows; the script checks that.

Change SIZES (or pass sizes: make try-scale SIZES="100 1000") and run it again.
"""

import re
import shutil
import sys

import common

SIZES = [int(s) for s in sys.argv[1:]] or [500, 2000, 5000]
PATTERN = re.compile(r"chestmnist_sample_(\d+)_label_(.*)")


def build(n):
    raw = common.WORK / f"n{n}"
    for sub in ("images", "notes", "vitals"):
        (raw / sub).mkdir(parents=True)
    images = sorted((common.RAW / "images").glob("*.png"))
    for k in range(n):
        src = images[k % len(images)]
        src_enc = f"enc_{int(PATTERN.match(src.name).group(1)) + 1:05d}"
        labels = PATTERN.match(src.name).group(2)
        enc = f"enc_{k + 1:05d}"
        shutil.copy(src, raw / "images" / f"chestmnist_sample_{k:03d}_label_{labels}")
        shutil.copy(common.RAW / "notes" / f"{src_enc}_note.txt", raw / "notes" / f"{enc}_note.txt")
        shutil.copy(common.RAW / "vitals" / f"{src_enc}_vitals.csv", raw / "vitals" / f"{enc}_vitals.csv")
    return raw


class BatchedPipeline(common.RawDataIngestionPipeline):
    """The same pipeline, but each _insert_* call collects the row and
    write_batches() writes each table with one INSERT ... SELECT."""

    COLUMNS = {
        "image_manifest": ["entity_id", "encounter_id", "modality", "timestamp", "provenance",
                           "quality", "file_path", "label_vector"],
        "note_manifest": ["entity_id", "encounter_id", "modality", "timestamp", "provenance",
                          "quality", "content", "key_tokens"],
        "vitals_manifest": ["entity_id", "encounter_id", "modality", "timestamp", "provenance",
                            "quality", "file_path"],
    }

    def __init__(self, db_path):
        super().__init__(db_path)
        self.rows = {table: [] for table in self.COLUMNS}

    def _base(self, r):
        return [r.entity_id, r.encounter_id, r.modality, r.timestamp, r.provenance, r.quality]

    def _insert_image_record(self, r):
        self.rows["image_manifest"].append(self._base(r) + [r.file_path, str(r.label_vector)])

    def _insert_note_record(self, r):
        self.rows["note_manifest"].append(self._base(r) + [r.content, str(r.key_tokens)])

    def _insert_vitals_record(self, r, file_path):
        self.rows["vitals_manifest"].append(self._base(r) + [file_path])

    def write_batches(self):
        import pandas as pd
        for table, rows in self.rows.items():
            self.conn.register("batch", pd.DataFrame(rows, columns=self.COLUMNS[table]))
            self.conn.execute(f"INSERT INTO {table} SELECT * FROM batch")
            self.conn.unregister("batch")


def table_counts(db):
    eng = common.engine(db)
    counts = [eng.conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
              for t in ("image_manifest", "note_manifest", "vitals_manifest", "curated_manifest")]
    eng.close()
    return counts


def main():
    print(f"{'encounters':>10} {'rows':>7} {'one INSERT per record':>21} {'one INSERT per table':>20} {'faster':>7}")
    for n in SIZES:
        raw = build(n)
        _, per_row, db_a = common.ingest(raw, f"n{n}_rows")
        _, batched, db_b = common.ingest(raw, f"n{n}_batch", BatchedPipeline)
        counts = table_counts(db_a)
        assert counts == table_counts(db_b) == [n] * 4, (counts, table_counts(db_b))
        print(f"{n:10,} {sum(counts):7,} {per_row:20.2f}s {batched:19.2f}s {per_row / batched:6.1f}x")
    common.cleanup()


if __name__ == "__main__":
    main()
