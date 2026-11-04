"""Independent scope-triage and grouped-split stages; no clinical approval."""
import copy
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from urllib.parse import urlsplit
from filtering import normalized, write_jsonl


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_rules(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def focus_key(value):
    return re.sub(r"[^\w]+", " ", normalized(value)).strip()


def canonical_focus(value, rules):
    value = focus_key(value)
    for alias in rules["focus_aliases"]:
        if re.search(alias["pattern"], value):
            return alias["canonical"]
    return value


def scope_decision(row, rules):
    sources = row["provenance"]
    titles = [p["focus"] for p in sources]
    reasons = []
    flags = [pattern for pattern in rules["local_context_content_patterns"]
             if re.search(pattern, row["question"] + " " + row["answer"], re.I)]
    for focus in titles:
        for pattern in rules["local_context_title_patterns"]:
            if re.search(pattern, focus, re.I):
                reasons.append({"reason": "location_specific_title", "focus": focus, "pattern": pattern})
    if reasons:
        return "deferred_local_context", reasons, flags
    specialist = all(p["source"] in rules["specialist_sources"] and
                     focus_key(p["focus"]) not in rules["common_focus_allowlist"] for p in sources)
    specialist_patterns = [pattern for pattern in rules["specialist_title_patterns"]
                           if any(re.search(pattern, focus, re.I) for focus in titles)]
    if specialist or specialist_patterns:
        return "deferred_specialist", [{"reason": "specialist_source_or_title",
                                         "sources": sorted({p["source"] for p in sources}),
                                         "patterns": specialist_patterns}], flags
    return "core_candidate", [{"reason": "in_scope_general_diabetes_or_eye_health"}], flags


def review(here, data, source, digest, write_json):
    parent = data / "filtered" / "ijwicare_seed.jsonl"
    selection = read_rules(data / "filtered" / "selection_report.json")
    if digest(parent) != selection["outputs"][parent.name]["sha256"] or selection["source_revision"] != source["revision"]:
        raise RuntimeError("Filtered source checksum/revision mismatch; rerun filter")
    rules_path = here / "review_rules.json"
    rules = read_rules(rules_path)
    rows = read_rows(parent)
    for row in rows:
        decision, reasons, flags = scope_decision(row, rules)
        row["scope_review"] = {"method": "automated_rules", "rules_version": rules["version"],
                               "decision": decision, "reasons": reasons, "local_context_flags": flags}
    output = data / "reviewed"; output.mkdir(exist_ok=True)
    write_jsonl(output / "scope_review.jsonl", rows)
    with (output / "review_queue.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["id", "decision", "focus", "question", "source_urls", "local_context_flags", "reasons"])
        for row in rows:
            scope = row["scope_review"]
            writer.writerow([row["id"], scope["decision"], row["focus"], row["question"],
                             json.dumps(sorted({p["source_url"] for p in row["provenance"]})),
                             json.dumps(scope["local_context_flags"]), json.dumps(scope["reasons"])])
    report = {"input_sha256": digest(parent), "source_revision": source["revision"],
              "rules_version": rules["version"], "rules_sha256": digest(rules_path),
              "code_sha256": digest(here / "preparation.py"), "input_records": len(rows),
              "decisions": dict(sorted(Counter(r["scope_review"]["decision"] for r in rows).items())),
              "records_with_local_context_flags": sum(bool(r["scope_review"]["local_context_flags"]) for r in rows),
              "review_status": "automated_scope_triage_only_not_clinical_review",
              "output_sha256": digest(output / "scope_review.jsonl"),
              "review_queue_sha256": digest(output / "review_queue.csv")}
    write_json(output / "review_report.json", report)
    print(json.dumps(report, indent=2))


def shingle_set(text, rules):
    words = normalized(text).split()
    if len(words) < rules["answer_minimum_words"]:
        return set()
    width = rules["answer_shingle_words"]
    return {tuple(words[i:i + width]) for i in range(len(words) - width + 1)}


def build_groups(rows, rules):
    parents = {r["id"]: r["id"] for r in rows}
    def find(key):
        while parents[key] != key:
            parents[key] = parents[parents[key]]; key = parents[key]
        return key
    def join(a, b):
        a, b = find(a), find(b)
        if a != b: parents[max(a, b)] = min(a, b)
    seen, edges = {}, Counter()
    for row in sorted(rows, key=lambda r: r["id"]):
        keys = {("question", normalized(row["question"])), ("answer", normalized(row["answer"]))}
        for p in row["provenance"]:
            keys.add(("document", p["document_path"]))
            keys.add(("focus", canonical_focus(p["focus"], rules)))
            url = urlsplit(p["source_url"])
            keys.add(("url", url.netloc.casefold() + url.path.rstrip("/").casefold()))
        for key in sorted(keys):
            if not key[1]: continue
            if key in seen:
                join(row["id"], seen[key]); edges[key[0]] += 1
            else: seen[key] = row["id"]
    ordered = sorted(rows, key=lambda r: r["id"])
    shingles = [shingle_set(r["answer"], rules) for r in ordered]
    for i, left in enumerate(shingles):
        if not left: continue
        for j in range(i + 1, len(ordered)):
            right = shingles[j]
            if not right or min(len(left), len(right)) / max(len(left), len(right)) < rules["answer_near_duplicate_threshold"]:
                continue
            if len(left & right) / len(left | right) >= rules["answer_near_duplicate_threshold"]:
                join(ordered[i]["id"], ordered[j]["id"]); edges["near_duplicate_answer"] += 1
    groups = defaultdict(list)
    for row in ordered: groups[find(row["id"])].append(row)
    return dict(groups), dict(sorted(edges.items()))


def assign_groups(groups, rules):
    ratios = rules["ratios"]
    if set(ratios) != {"train", "validation", "test"} or abs(sum(ratios.values()) - 1) > 1e-9 or min(ratios.values()) <= 0:
        raise ValueError("Split ratios must be positive train/validation/test values summing to one")
    if len(groups) < len(ratios): raise ValueError("Too few independent groups for three splits")
    total = sum(len(rows) for rows in groups.values())
    targets = {name: total * ratio for name, ratio in ratios.items()}
    counts = {name: 0 for name in ratios}
    # Largest groups first; seeded hash breaks equal-size ties without depending on input order.
    order = sorted(groups, key=lambda key: (-len(groups[key]), hashlib.sha256((rules["seed"] + key).encode()).hexdigest()))
    assignments = {}
    for index, key in enumerate(order):
        empty = [name for name in ratios if counts[name] == 0]
        choices = empty if len(order) - index == len(empty) else list(ratios)
        best = min(choices, key=lambda name: sum(((counts[n] + (len(groups[key]) if n == name else 0)) - targets[n]) ** 2 for n in ratios))
        assignments[key] = best; counts[best] += len(groups[key])
    return assignments


def split(here, data, source, digest, write_json):
    parent = data / "reviewed" / "scope_review.jsonl"
    review_report = read_rules(data / "reviewed" / "review_report.json")
    if digest(parent) != review_report["output_sha256"] or review_report["source_revision"] != source["revision"]:
        raise RuntimeError("Scope review checksum/revision mismatch; rerun review")
    rules_path = here / "split_rules.json"; rules = read_rules(rules_path)
    rows = [r for r in read_rows(parent) if r["scope_review"]["decision"] == "core_candidate"]
    groups, edges = build_groups(rows, rules)
    assignment = assign_groups(groups, rules)
    exports = defaultdict(list); group_rows = []
    for key, members in sorted(groups.items()):
        group_id = "group-" + hashlib.sha256("\n".join(r["id"] for r in members).encode()).hexdigest()
        destination = assignment[key]
        group_rows.append({"group_id": group_id, "split": destination, "record_ids": [r["id"] for r in members],
                           "focuses": sorted({p["focus"] for r in members for p in r["provenance"]})})
        for original in members:
            row = copy.deepcopy(original); row["split"] = destination; row["group_id"] = group_id
            exports[destination].append(row)
    # Validate disjoint grouping keys independently on assigned records.
    owners = {}; collisions = []
    for name, records in exports.items():
        for row in records:
            keys = [("id", row["id"]), ("question", normalized(row["question"])), ("answer", normalized(row["answer"]))]
            for p in row["provenance"]:
                url = urlsplit(p["source_url"])
                keys += [("document", p["document_path"]), ("focus", canonical_focus(p["focus"], rules)),
                         ("url", url.netloc.casefold() + url.path.rstrip("/").casefold())]
            for key in keys:
                if not key[1]: continue
                if key in owners and owners[key] != name: collisions.append(key)
                owners[key] = name
    if collisions: raise RuntimeError("Cross-split leakage detected")
    output = data / "splits"; output.mkdir(exist_ok=True)
    for name in rules["ratios"]:
        write_jsonl(output / f"{name}.jsonl", sorted(exports[name], key=lambda r: r["id"]))
    write_json(output / "groups.json", group_rows)
    with (output / "assignment.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream); writer.writerow(["id", "group_id", "split", "focus"])
        for name in rules["ratios"]:
            writer.writerows([r["id"], r["group_id"], name, r["focus"]] for r in sorted(exports[name], key=lambda r: r["id"]))
    report = {"source_revision": source["revision"], "input_sha256": digest(parent),
              "rules_sha256": digest(rules_path), "rules_version": rules["version"],
              "code_sha256": digest(here / "preparation.py"), "seed": rules["seed"],
              "target_ratios": rules["ratios"], "core_records": len(rows), "groups": len(groups),
              "largest_group_records": max(map(len, groups.values())), "grouping_links": edges,
              "splits": {name: {"records": len(exports[name]),
                                 "groups": sum(g["split"] == name for g in group_rows),
                                 "topic_counts": dict(sorted(Counter(t for r in exports[name] for t in r["topics"]).items()))}
                         for name in rules["ratios"]},
              "cross_split_key_collisions": 0,
              "held_out_missing_topics": sorted({t for r in rows for t in r["topics"]} -
                                                {t for name in ["validation", "test"] for r in exports[name] for t in r["topics"]}),
              "limits": ["Automated scope triage; no clinical approval or translation review.",
                         "Grouping covers documents, URL paths, configured focus aliases, exact text, and answer shingle similarity; semantic overlap can remain.",
                         "Target ratios are approximate; groups are indivisible and topics are not stratified.",
                         "Only train parents may be augmented; all descendants inherit parent group and split.",
                         "Deferred scope candidates are excluded from all splits and must be regrouped before later admission.",
                         "Topics missing from both held-out sets require independently sourced evaluation cases; inspect held_out_missing_topics."]}
    report["outputs"] = {name: digest(output / name) for name in ["train.jsonl", "validation.jsonl", "test.jsonl", "groups.json", "assignment.csv"]}
    write_json(output / "split_report.json", report)
    print(json.dumps(report, indent=2))
