"""
Your defense. Implement register(ctx) and a handler per event type.
See ../README.md for the full interface + toolkit reference, and
../RULES.md before you start.
"""
from api import Verdict


def register(ctx):
    ctx.on("data_batch", check_data_batch)
    ctx.on("contract_checkpoint", check_contract_checkpoint)
    ctx.on("lineage_run", check_lineage_run)
    ctx.on("feature_materialization", check_feature_materialization)
    ctx.on("embedding_batch", check_embedding_batch)


def check_data_batch(payload, ctx):
    res = ctx.tools.batch_profile(payload["batch_id"])
    if "error" in res:
        return Verdict(alert=False, reason=res["error"], pillar="checks")

    rows = res.get("row_count", 0)
    null_rate = res.get("null_rate", {}).get("customer_id", 0.0)
    mean_amount = res.get("mean_amount", 0.0)
    staleness_min = res.get("staleness_min", 0.0)

    b = ctx.baseline
    row_count_min = b.get("row_count_min", 435.4732)
    row_count_max = b.get("row_count_max", 561.2948)
    null_rate_max = b.get("null_rate_max", 0.0109)
    mean_amount_min = b.get("mean_amount_min", 72.7645)
    mean_amount_max = b.get("mean_amount_max", 90.6053)
    staleness_min_max = b.get("staleness_min_max", 8.418)

    if rows < row_count_min or rows > row_count_max:
        return Verdict(alert=True, confidence=1.0, reason=f"Volume anomaly: row_count={rows}", pillar="checks")
    if null_rate > null_rate_max:
        return Verdict(alert=True, confidence=1.0, reason=f"Null spike: null_rate={null_rate}", pillar="checks")
    if mean_amount < mean_amount_min or mean_amount > mean_amount_max:
        return Verdict(alert=True, confidence=1.0, reason=f"Distribution shift: mean_amount={mean_amount}", pillar="checks")
    if staleness_min > staleness_min_max:
        return Verdict(alert=True, confidence=1.0, reason=f"Freshness lag: staleness_min={staleness_min}", pillar="checks")

    return Verdict(alert=False, pillar="checks")


def check_contract_checkpoint(payload, ctx):
    res = ctx.tools.contract_diff(payload["contract_id"], payload["checkpoint_batch_id"])
    if "error" in res:
        return Verdict(alert=False, reason=res["error"], pillar="contracts")

    violations = res.get("violations", [])
    if violations:
        return Verdict(alert=True, confidence=1.0, reason=f"Contract violations: {violations}", pillar="contracts")

    freshness_delay = res.get("freshness_delay_min", 0.0)
    b = ctx.baseline
    freshness_delay_max = b.get("freshness_delay_max_min", 11.1141)
    if freshness_delay > freshness_delay_max:
        return Verdict(alert=True, confidence=1.0, reason=f"SLA freshness delay: {freshness_delay} > {freshness_delay_max}", pillar="contracts")

    declared_freshness = payload.get("declared_sla", {}).get("freshness_min")
    if declared_freshness is not None and freshness_delay > declared_freshness:
        return Verdict(alert=True, confidence=1.0, reason=f"Declared SLA breached: {freshness_delay} > {declared_freshness}", pillar="contracts")

    return Verdict(alert=False, pillar="contracts")


def check_lineage_run(payload, ctx):
    res = ctx.tools.lineage_graph_slice(payload["run_id"])
    if "error" in res:
        return Verdict(alert=False, reason=res["error"], pillar="lineage")

    downstream_count = res.get("actual_downstream_count", 0)
    if downstream_count == 0:
        return Verdict(alert=True, confidence=1.0, reason="Orphan output: downstream count is 0", pillar="lineage")

    upstream = set(res.get("actual_upstream", []))
    if "raw.orders" not in upstream or "raw.customers" not in upstream:
        return Verdict(alert=True, confidence=1.0, reason=f"Missing upstream dependency: {upstream}", pillar="lineage")

    duration_ms = res.get("duration_ms", 0.0)
    b = ctx.baseline
    duration_max = b.get("lineage_duration_ms_max", 5134.9804)
    if duration_ms > duration_max:
        return Verdict(alert=True, confidence=1.0, reason=f"Runtime anomaly: duration_ms={duration_ms}", pillar="lineage")

    return Verdict(alert=False, pillar="lineage")


def check_feature_materialization(payload, ctx):
    res = ctx.tools.feature_drift(payload["feature_view"], payload["batch_id"])
    if "error" in res:
        return Verdict(alert=False, reason=res["error"], pillar="ai_infra")

    shift_sigma = res.get("mean_shift_sigma")
    if shift_sigma is None:
        serve_mean = res.get("serve_mean", 0.0)
        train_mean = res.get("train_mean", 0.0)
        train_std = res.get("train_std", 1.0)
        if train_std > 0:
            shift_sigma = abs(serve_mean - train_mean) / train_std
        else:
            shift_sigma = 0.0

    if shift_sigma > 0.60:
        return Verdict(alert=True, confidence=1.0, reason=f"Feature skew detected: shift_sigma={shift_sigma}", pillar="ai_infra")

    return Verdict(alert=False, pillar="ai_infra")


def check_embedding_batch(payload, ctx):
    res = ctx.tools.embedding_drift(payload["corpus"], payload["chunk_batch_id"])
    if "error" in res:
        return Verdict(alert=False, reason=res["error"], pillar="ai_infra")

    centroid_shift = res.get("centroid_shift", 0.0)
    avg_doc_age_days = res.get("avg_doc_age_days", 0.0)

    b = ctx.baseline
    centroid_max = b.get("embedding_centroid_shift_max", 0.0435)
    doc_age_max = b.get("corpus_avg_doc_age_days_max", 49.7955)

    if centroid_shift > min(centroid_max, 0.040):
        return Verdict(alert=True, confidence=1.0, reason=f"Embedding drift: centroid_shift={centroid_shift}", pillar="ai_infra")
    if avg_doc_age_days > min(doc_age_max, 45.0):
        return Verdict(alert=True, confidence=1.0, reason=f"Corpus staleness: avg_doc_age_days={avg_doc_age_days}", pillar="ai_infra")

    return Verdict(alert=False, pillar="ai_infra")
