"""Reproducible MedQuAD acquisition. Python standard library only."""
import argparse
import hashlib
import json
import platform
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
SOURCE = json.loads((HERE / "source.json").read_text(encoding="utf-8"))


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def download():
    DATA.mkdir(exist_ok=True)
    archive = DATA / "medquad.zip"
    manifest = DATA / "download_manifest.json"
    if archive.exists():
        if not manifest.exists():
            raise RuntimeError("Archive exists without manifest; move it aside before downloading.")
        previous = json.loads(manifest.read_text(encoding="utf-8"))
        if previous["source"] != SOURCE or digest(archive) != previous["sha256"]:
            raise RuntimeError("Existing download differs from recorded source/checksum.")
        print("Reusing verified archive:", archive)
        return
    partial = DATA / "medquad.zip.part"
    request = urllib.request.Request(SOURCE["archive_url"], headers={"User-Agent": "IjwiCare-dataset-pipeline/1"})
    with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as target:
        while chunk := response.read(1024 * 1024):
            target.write(chunk)
    with zipfile.ZipFile(partial) as bundle:
        if bundle.testzip() is not None:
            raise RuntimeError("Archive integrity check failed")
    partial.replace(archive)
    write_json(manifest, {"source": SOURCE, "sha256": digest(archive),
                         "bytes": archive.stat().st_size,
                         "downloaded_at": datetime.now(timezone.utc).isoformat(),
                         "python": platform.python_version()})
    print("Downloaded:", archive, archive.stat().st_size, "bytes")


def validate():
    archive = DATA / "medquad.zip"
    manifest = json.loads((DATA / "download_manifest.json").read_text(encoding="utf-8"))
    if manifest["source"] != SOURCE or digest(archive) != manifest["sha256"]:
        raise RuntimeError("Source/checksum verification failed")
    files, documents, questions, answered = [], 0, 0, 0
    with zipfile.ZipFile(archive) as bundle:
        for info in sorted(bundle.infolist(), key=lambda item: item.filename):
            if info.is_dir():
                continue
            content = bundle.read(info)
            files.append({"path": info.filename, "bytes": len(content),
                          "sha256": hashlib.sha256(content).hexdigest()})
            name = PurePosixPath(info.filename).name.lower()
            if name in {"license.txt", "readme.txt"}:
                (DATA / name).write_bytes(content)
            if not name.endswith(".xml"):
                continue
            root = ET.fromstring(content)
            documents += 1
            for pair in root.findall(".//QAPair"):
                questions += 1
                answer = pair.find("Answer")
                if answer is not None and "".join(answer.itertext()).strip():
                    answered += 1
    if not documents or not questions or not answered:
        raise RuntimeError("No usable XML question/answer data found")
    write_json(DATA / "file_manifest.json", files)
    report = {"revision": SOURCE["revision"], "archive_sha256": manifest["sha256"],
              "archive_bytes": manifest["bytes"], "file_count": len(files),
              "uncompressed_bytes": sum(item["bytes"] for item in files),
              "xml_documents": documents, "qa_pairs": questions,
              "pairs_with_nonempty_answers": answered,
              "pairs_without_answers": questions - answered,
              "clinical_review_status": "not_reviewed"}
    write_json(DATA / "validation_report.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["download", "validate", "filter", "review", "split", "pilot", "smoke"])
    args = parser.parse_args()
    if args.stage == "filter":
        from filtering import run
        run(HERE, DATA, SOURCE, digest, write_json)
    elif args.stage in {"pilot", "smoke"}:
        import pilot
        if args.stage == "pilot":
            pilot.run(HERE, DATA, SOURCE, digest, write_json)
        else:
            pilot.smoke(HERE, DATA, SOURCE, digest, write_json, validate)
    elif args.stage in {"review", "split"}:
        import preparation
        getattr(preparation, args.stage)(HERE, DATA, SOURCE, digest, write_json)
    else:
        {"download": download, "validate": validate}[args.stage]()
