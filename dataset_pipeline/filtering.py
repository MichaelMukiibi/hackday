"""Deterministic topic selection and provenance-preserving QA deduplication."""
import csv
import hashlib
import json
import re
import unicodedata
import zipfile
from collections import Counter
from pathlib import PurePosixPath
import xml.etree.ElementTree as ET


def text_of(element):
    return "" if element is None else "".join(element.itertext()).strip()


def normalized(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def content_key(question, answer):
    value = json.dumps([normalized(question), normalized(answer)], ensure_ascii=False)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def match_topics(focus, rules):
    reasons = []
    for topic in rules["topics"]:
        if any(re.search(pattern, focus, re.I) for pattern in topic["exclude_patterns"]):
            continue
        for pattern in topic["patterns"]:
            if re.search(pattern, focus, re.I):
                reasons.append({"topic": topic["name"], "field": "document_focus",
                                "value": focus, "pattern": pattern})
    return reasons


def write_jsonl(path, rows):
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def run(here, data, source, digest, write_json):
    archive = data / "medquad.zip"
    manifest = json.loads((data / "download_manifest.json").read_text(encoding="utf-8"))
    archive_hash = digest(archive)
    if manifest["source"] != source or archive_hash != manifest["sha256"]:
        raise RuntimeError("Source/checksum verification failed; filtering stopped")
    rules_path = here / "filter_rules.json"
    rules = json.loads(rules_path.read_text(encoding="utf-8-sig"))
    selected, decisions, documents = {}, [], []
    for topic in rules["topics"]:
        for pattern in topic["patterns"] + topic["exclude_patterns"]:
            re.compile(pattern)
    with zipfile.ZipFile(archive) as bundle:
        for name in sorted(bundle.namelist()):
            if not name.endswith(".xml"):
                continue
            path = str(PurePosixPath(name).relative_to(PurePosixPath(name).parts[0]))
            root = ET.fromstring(bundle.read(name))
            focus = text_of(root.find("Focus"))
            reasons = match_topics(focus, rules)
            topics = sorted({reason["topic"] for reason in reasons})
            pairs = root.findall(".//QAPair")
            document = {"path": path, "document_id": root.get("id", ""),
                        "source": root.get("source", ""), "source_url": root.get("url", ""),
                        "focus": focus, "topics": topics, "qa_pairs": len(pairs),
                        "selected_pairs_before_dedup": 0}
            for ordinal, pair in enumerate(pairs, 1):
                question_node = pair.find("Question")
                question, answer = text_of(question_node), text_of(pair.find("Answer"))
                qid = question_node.get("qid", "") if question_node is not None else ""
                qtype = question_node.get("qtype", "") if question_node is not None else ""
                pair_id = pair.get("pid", "")
                row_id = f"{path}#{ordinal}"
                decision = {"source_row_id": row_id, "document_path": path,
                            "question_id": qid, "topics": topics,
                            "selection_reasons": reasons}
                if not question or not answer:
                    decision["decision"] = "missing_question_or_answer"
                elif not reasons:
                    decision["decision"] = "outside_topic_scope"
                else:
                    document["selected_pairs_before_dedup"] += 1
                    key = content_key(question, answer)
                    record_id = "medquad-" + key
                    provenance = {"source_row_id": row_id, "document_path": path,
                                  "document_id": document["document_id"], "pair_id": pair_id,
                                  "question_id": qid, "question_type": qtype, "focus": focus,
                                  "source": document["source"], "source_url": document["source_url"],
                                  "source_xml_url": f'{source["repository"]}/blob/{source["revision"]}/{path}',
                                  "selection_reasons": reasons}
                    decision["retained_record_id"] = record_id
                    if key in selected:
                        decision["decision"] = "duplicate_merged"
                        selected[key]["provenance"].append(provenance)
                        selected[key]["topics"] = sorted(set(selected[key]["topics"]) | set(topics))
                    else:
                        decision["decision"] = "selected"
                        selected[key] = {"id": record_id, "question": question, "answer": answer,
                                         "question_type": qtype, "focus": focus, "topics": topics,
                                         "language": "en", "origin": "medquad_source",
                                         "source_revision": source["revision"], "license": source["license"],
                                         "attribution": source["attribution"],
                                         "clinical_review_status": "not_reviewed",
                                         "language_review_status": "not_reviewed",
                                         "split": "unassigned", "provenance": [provenance]}
                decisions.append(decision)
            documents.append(document)
    records = sorted(selected.values(), key=lambda row: row["id"])
    if not records:
        raise RuntimeError("No answered candidates selected")
    output = data / "filtered"
    output.mkdir(exist_ok=True)
    write_jsonl(output / "ijwicare_seed.jsonl", records)
    fields = list(records[0])
    with (output / "ijwicare_seed.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({key: json.dumps(value, ensure_ascii=False, sort_keys=True)
                             if isinstance(value, (list, dict)) else value for key, value in record.items()})
    write_jsonl(output / "selection_audit.jsonl", decisions)
    write_json(output / "document_inventory.json", documents)
    counts = dict(sorted(Counter(row["decision"] for row in decisions).items()))
    topic_totals = Counter(topic for row in records for topic in row["topics"])
    topic_counts = {topic["name"]: topic_totals[topic["name"]] for topic in rules["topics"]}
    report = {"source_revision": source["revision"], "archive_sha256": archive_hash,
              "rules_version": rules["version"], "rules_sha256": digest(rules_path),
              "filter_code_sha256": digest(here / "filtering.py"),
              "input_documents": len(documents), "input_qa_pairs": len(decisions),
              "matched_documents": sum(bool(row["topics"]) for row in documents),
              "selected_source_documents": sum(bool(row["selected_pairs_before_dedup"]) for row in documents),
              "selected_pairs_before_dedup": sum(row["selected_pairs_before_dedup"] for row in documents),
              "unique_records": len(records), "decisions": counts, "topic_counts": topic_counts,
              "question_type_counts": dict(sorted(Counter(row["question_type"] for row in records).items())),
              "notes": ["Topic counts overlap; records may have multiple topics.",
                        "Exact normalized QA deduplication only; near duplicates remain for review.",
                        "No clinical or translation review; source text is retained.",
                        "No split, translation, generation, or Adaption job has run."]}
    report["outputs"] = {path.name: {"sha256": digest(path), "bytes": path.stat().st_size}
                         for path in sorted(output.iterdir())
                         if path.name in {"ijwicare_seed.jsonl", "ijwicare_seed.csv", "selection_audit.jsonl", "document_inventory.json"}}
    write_json(output / "selection_report.json", report)
    lines = ["# IjwiCare seed selection report", "", f'Selected **{len(records)} unique answered QA records** from {report["selected_source_documents"]} source documents.',
             f'Before deduplication: {report["selected_pairs_before_dedup"]} records. Duplicate pairs merged: {counts.get("duplicate_merged", 0)}.',
             "", "## Topics (overlapping)", "", "| Topic | Unique records |", "| --- | --- |"]
    lines += [f"| {topic} | {count} |" for topic, count in topic_counts.items()]
    lines += ["", "## Selected source documents", "", "| Source path | Focus | Selected pairs before deduplication |", "| --- | --- | --- |"]
    lines += [f'| {row["path"]} | {row["focus"].replace("|", "/")} | {row["selected_pairs_before_dedup"]} |'
              for row in documents if row["selected_pairs_before_dedup"]]
    lines += ["", "## Review status", "", *report["notes"], "",
              "Source answers may contain historical guidance, country-specific services or rare conditions. Review topic relevance, current evidence, and local applicability before augmentation.", ""]
    (output / "selection_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "outputs"}, indent=2))
