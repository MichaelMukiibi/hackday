"""Inspect an existing export locally. No Adaption API calls and no archive extraction."""
import argparse
import hashlib
import io
import json
import tarfile
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq


def inspect(path):
    parts = []
    totals = {"enhanced_prompt_nonempty": 0, "enhanced_completion_nonempty": 0, "changed_prompt_rows": 0, "changed_completion_rows": 0}
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile() or not member.name.endswith(".parquet"):
                continue
            with archive.extractfile(member) as file:
                raw = file.read()
            parquet = pq.ParquetFile(io.BytesIO(raw))
            columns = parquet.schema_arrow.names
            expected = {"instruction", "output", "enhanced_prompt", "enhanced_completion"}
            if expected.issubset(columns):
                for row in parquet.read(columns=sorted(expected)).to_pylist():
                    prompt = row["enhanced_prompt"]
                    completion = row["enhanced_completion"]
                    has_prompt = isinstance(prompt, str) and bool(prompt.strip())
                    has_completion = isinstance(completion, str) and bool(completion.strip())
                    totals["enhanced_prompt_nonempty"] += int(has_prompt)
                    totals["enhanced_completion_nonempty"] += int(has_completion)
                    totals["changed_prompt_rows"] += int(has_prompt and prompt.strip() != str(row["instruction"]).strip())
                    totals["changed_completion_rows"] += int(has_completion and completion.strip() != str(row["output"]).strip())
            parts.append({"file": member.name, "rows": parquet.metadata.num_rows, "columns": columns, "sha256": hashlib.sha256(raw).hexdigest()})
    return {"inspection_date": datetime.now(UTC).date().isoformat(), "artifact": path.name, "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "parquet_parts": parts, "total_rows": sum(part["rows"] for part in parts), "field_checks": totals, "provenance_note": "Local inspection of the existing repository export. No new Adaption run was started. No platform run ID or credit receipt is asserted. Field differences are not measures of quality or clinical correctness."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=Path("adapted-alpaca.tar.gz"))
    parser.add_argument("--output", type=Path, default=Path("docs/evidence/export-inspection.json"))
    args = parser.parse_args()
    result = inspect(args.artifact)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
