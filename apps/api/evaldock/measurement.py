import math
from collections import Counter
from statistics import mean, pstdev
from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring

from .contracts import GateConfig


def distribution(values: list[float]) -> dict[str, Any]:
    ordered = sorted(values)
    return {
        "n": len(values),
        "mean": mean(values) if values else None,
        "stddev": pstdev(values) if values else None,
        "p95": ordered[math.ceil(0.95 * len(ordered)) - 1] if ordered else None,
        "p95_method": "nearest rank: sorted[ceil(0.95*n)-1]",
    }


def classification_report(rows: list[dict[str, Any]], labels: list[str]) -> dict[str, Any]:
    matrix = {label: {pred: 0 for pred in [*labels, "__unknown__"]} for label in labels}
    for row in rows:
        if row["expected"] in matrix:
            predicted = row["predicted"] if row["predicted"] in labels else "__unknown__"
            matrix[row["expected"]][predicted] += 1
    per_label = {}
    tp_sum, fp_sum, fn_sum = 0, 0, 0
    for label in labels:
        tp = matrix[label][label]
        fp = sum(matrix[other][label] for other in labels if other != label)
        fn = sum(matrix[label][other] for other in matrix[label] if other != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label[label] = {"precision": precision, "recall": recall, "f1": f1, "support": tp + fn}
        tp_sum, fp_sum, fn_sum = tp_sum + tp, fp_sum + fp, fn_sum + fn
    # Unknown predictions count as false positives in the full label universe.
    fp_sum += sum(matrix[label]["__unknown__"] for label in labels)
    precision = tp_sum / (tp_sum + fp_sum) if tp_sum + fp_sum else 0.0
    recall = tp_sum / (tp_sum + fn_sum) if tp_sum + fn_sum else 0.0
    return {
        "confusion_matrix": matrix,
        "per_label": per_label,
        "micro": {
            "precision": precision,
            "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        },
        "macro": {
            metric: mean(v[metric] for v in per_label.values()) if per_label else 0.0
            for metric in ["precision", "recall", "f1"]
        },
        "zero_division": 0,
        "n": len(rows),
    }


def aggregate(
    executions: list[dict[str, Any]], definitions: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    total = len(executions)
    metrics = {}
    for key, definition in definitions.items():
        results = [
            r for execution in executions for r in execution["results"] if r["metric_key"] == key
        ]
        scored = [r for r in results if r["status"] == "scored"]
        errors = sum(r["status"] == "error" for r in results)
        na = sum(r["status"] == "not_applicable" for r in results)
        values = [r["score"] for r in scored if r.get("score") is not None]
        decisions = [r for r in scored if r.get("passed") is not None]
        metric = {
            "definition": definition,
            "denominator": total,
            "scored": len(scored),
            "coverage": len(scored) / total if total else 0.0,
            "not_applicable": na,
            "errors": errors,
            "missing": total - len(results),
            "mean": mean(values) if values else None,
            "passed": sum(r["passed"] is True for r in decisions),
            "failed": sum(r["passed"] is False for r in decisions),
            "pass_rate": sum(r["passed"] is True for r in decisions) / len(decisions)
            if decisions
            else None,
            "decision_denominator": len(decisions),
            "variability": distribution(values),
        }
        classification = [r["details"] for r in scored if "predicted" in r.get("details", {})]
        if classification:
            metric["classification"] = classification_report(
                classification, classification[0]["labels"]
            )
        metrics[key] = metric
    return {
        "total": total,
        "target_errors": sum(bool(e.get("target_error")) for e in executions),
        "execution_states": dict(Counter(e["status"] for e in executions)),
        "metrics": metrics,
        "target_latency_ms": distribution(
            [e["target_latency_ms"] for e in executions if e.get("target_latency_ms") is not None]
        ),
        "evaluation_latency_ms": distribution(
            [
                e["evaluation_latency_ms"]
                for e in executions
                if e.get("evaluation_latency_ms") is not None
            ]
        ),
        "target_cost": cost_summary([e.get("metadata", {}).get("target_cost") for e in executions]),
        "judge_cost": cost_summary(
            [
                r.get("details", {}).get("judge_cost")
                for e in executions
                for r in e["results"]
                if "judge_mode" in r.get("details", {})
            ]
        ),
    }


def cost_summary(values: list[Any]) -> dict[str, Any]:
    available = [
        float(v)
        for v in values
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0
    ]
    return {
        "total_usd": sum(available) if available else None,
        "available_count": len(available),
        "denominator": len(values),
        "provenance": "provider_reported" if available else "unavailable",
    }


def pair_comparison(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    metric: str,
    tag: str | None = None,
    slice_filter: str | None = None,
) -> dict[str, Any]:
    def selected(row: dict[str, Any]) -> bool:
        if tag and tag not in row["case"].get("tags", []):
            return False
        if slice_filter:
            key, _, value = slice_filter.partition("=")
            return row["case"].get("slices", {}).get(key) == value
        return True

    left = {(e["case_id"], e["replicate"]): e for e in baseline["executions"] if selected(e)}
    right = {(e["case_id"], e["replicate"]): e for e in candidate["executions"] if selected(e)}
    added, removed = sorted(right.keys() - left.keys()), sorted(left.keys() - right.keys())
    changed, rows = [], []
    for key in sorted(left.keys() & right.keys()):
        before, after = left[key], right[key]
        if before["case_fingerprint"] != after["case_fingerprint"]:
            changed.append(key)
            continue
        a = next((r for r in before["results"] if r["metric_key"] == metric), None)
        b = next((r for r in after["results"] if r["metric_key"] == metric), None)
        if (
            not a
            or not b
            or a["status"] != "scored"
            or b["status"] != "scored"
            or a.get("passed") is None
            or b.get("passed") is None
            or before.get("target_error")
            or after.get("target_error")
        ):
            state = "unscored_or_error"
        else:
            state = {
                (False, True): "improved",
                (True, False): "regressed",
                (True, True): "unchanged_pass",
                (False, False): "unchanged_fail",
            }[(a["passed"], b["passed"])]
        delta = (
            b["score"] - a["score"]
            if a and b and a.get("score") is not None and b.get("score") is not None
            else None
        )
        rows.append(
            {
                "case_id": key[0],
                "replicate": key[1],
                "state": state,
                "baseline": before,
                "candidate": after,
                "delta": delta,
            }
        )
    same_dataset = baseline["dataset_version_id"] == candidate["dataset_version_id"]
    comparable_latency = (
        same_dataset
        and baseline["mode"] == candidate["mode"] == "http"
        and baseline["concurrency"] == candidate["concurrency"]
        and baseline.get("options", {}).get("warmup", 0)
        == candidate.get("options", {}).get("warmup", 0)
        and baseline.get("target_limits") == candidate.get("target_limits")
    )
    return {
        "metric_key": metric,
        "same_dataset": same_dataset,
        "warning": None
        if same_dataset
        else "Datasets differ: only unchanged shared cases are paired",
        "added": added,
        "removed": removed,
        "changed": changed,
        "counts": dict(Counter(r["state"] for r in rows)),
        "paired_count": len(rows),
        "delta": distribution([r["delta"] for r in rows if r["delta"] is not None]),
        "latency_comparable": comparable_latency,
        "baseline_name": baseline["name"],
        "candidate_name": candidate["name"],
        "rows": rows,
        "statistical_significance": "not_computed",
    }


def evaluate_gate(
    report: dict[str, Any], comparison: dict[str, Any] | None, cfg: GateConfig
) -> dict[str, Any]:
    failures: list[str] = []
    infra: list[str] = []
    summary = report["summary"]
    total = summary["total"]
    if report["status"] not in {"completed", "partially_failed"}:
        infra.append(f"Experiment state is {report['status']}")
    if not total:
        infra.append("No executions")
    if comparison is None:
        infra.append("No pinned baseline available")
    elif comparison["changed"] or comparison["added"] or comparison["removed"]:
        failures.append("Baseline coverage differs: added, removed or changed cases")
    elif comparison["counts"].get("regressed", 0) > cfg.max_regressions:
        failures.append(f"Regression count exceeds {cfg.max_regressions}")
    if comparison:
        if (
            comparison.get("metric_key") is not None
            and comparison["metric_key"] not in summary["metrics"]
        ):
            infra.append("Comparison metric is not defined in the candidate suite")
        if comparison["counts"].get("unscored_or_error", 0):
            failures.append("Comparison includes unscored or execution-error pairs")
        if comparison.get("paired_count") == 0:
            failures.append("No compatible case/replicate pairs")
    if total and summary["target_errors"] / total > cfg.max_target_error_rate:
        failures.append("Target error rate exceeds limit")
    for key, metric in summary["metrics"].items():
        if metric["coverage"] < cfg.min_coverage:
            failures.append(f"{key}: insufficient evaluation coverage")
        if metric["errors"]:
            (infra if cfg.evaluator_errors == "infrastructure_error" else failures).append(
                f"{key}: evaluator errors"
            )
    for key, threshold in cfg.min_accuracy.items():
        metric = summary["metrics"].get(key)
        if not metric:
            infra.append(f"Configured metric does not exist: {key}")
        elif metric["mean"] is None or metric["mean"] < threshold:
            failures.append(f"{key}: minimum accuracy {threshold:g} not met")
    for execution in report["executions"]:
        if cfg.critical_tag in execution["case"].get("tags", []):
            if (
                execution["status"] != "completed"
                or len(execution["results"]) != len(summary["metrics"])
                or any(
                    r["status"] != "scored" or r.get("passed") is not True
                    for r in execution["results"]
                )
            ):
                failures.append(
                    f"Critical case failed or unscored: {execution['case_id']}#{execution['replicate']}"
                )
    if cfg.max_p95_latency_ms is not None:
        if (
            not comparison
            or not comparison["latency_comparable"]
            or summary["target_latency_ms"]["n"] != total
        ):
            infra.append("Latency measurements are unavailable or not comparable")
        elif summary["target_latency_ms"]["p95"] > cfg.max_p95_latency_ms:
            failures.append("P95 latency exceeds limit")
    code = 2 if infra else 1 if failures else 0
    return {
        "passed": code == 0,
        "exit_code": code,
        "quality_failures": failures,
        "infrastructure_errors": infra,
        "policy": cfg.model_dump(),
        "pinned_baseline_id": report.get("baseline_id"),
    }


def junit(report: dict[str, Any], gate: dict[str, Any]) -> str:
    root = Element("testsuite", name="EvalDock", tests=str(len(report["executions"]) + 1))
    failures = errors = 0
    for row in report["executions"]:
        test = SubElement(
            root, "testcase", name=f"{row['case_id']}[{row['replicate']}]", classname=report["name"]
        )
        if row["status"] != "completed":
            SubElement(test, "error", message=row.get("target_error") or row["status"])
            errors += 1
        elif any(r["status"] != "scored" or r.get("passed") is False for r in row["results"]):
            SubElement(test, "failure", message="One or more criteria failed or were unscored")
            failures += 1
    gate_case = SubElement(root, "testcase", name="CI gate", classname="evaldock.gate")
    if gate["exit_code"] == 2:
        SubElement(gate_case, "error", message="; ".join(gate["infrastructure_errors"]))
        errors += 1
    elif not gate["passed"]:
        SubElement(gate_case, "failure", message="; ".join(gate["quality_failures"]))
        failures += 1
    root.set("failures", str(failures))
    root.set("errors", str(errors))
    return tostring(root, encoding="unicode", xml_declaration=True)
