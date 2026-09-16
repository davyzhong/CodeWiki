"""Paired statistics for the M8 A/B benchmark (standard library only).

Thresholds mirror the pre-registered criteria in the frozen design:
H1 = paired success-rate difference >= +10pp or exact McNemar p < 0.10;
H2 = success not degraded beyond one task AND token median reduction
>= 20% with Wilcoxon signed-rank p < 0.10. Do not tune these between
runs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def _erf(x: float) -> float:
    return math.erf(x)


def _two_sided_p_from_z(z: float) -> float:
    return 2.0 * (1.0 - 0.5 * (1.0 + _erf(abs(z) / math.sqrt(2.0))))


def mcnemar_exact(discordant_a_only: int, discordant_b_only: int) -> float:
    """Exact McNemar test on the discordant pair counts.

    ``discordant_a_only`` = treatment success + control failure;
    ``discordant_b_only`` = control success + treatment failure.
    """

    total = discordant_a_only + discordant_b_only
    if total == 0:
        return 1.0
    larger = max(discordant_a_only, discordant_b_only)
    tail = sum(
        math.comb(total, k) for k in range(larger, total + 1)
    ) / (2**total)
    return min(1.0, 2.0 * tail)


def wilcoxon_signed_rank(differences: list[float]) -> tuple[float, float]:
    """Wilcoxon signed-rank test (normal approximation, drop zeros).

    Returns ``(w_statistic, two_sided_p)``. Suitable for n >= 10 as in
    the frozen design (15 tasks).
    """

    samples = [value for value in differences if value != 0]
    n = len(samples)
    if n < 5:
        return (0.0, 1.0)
    ranked = sorted(
        enumerate(samples), key=lambda pair: (abs(pair[1]), pair[0])
    )
    # Average ranks for ties, then split by sign.
    magnitudes = [abs(value) for _index, value in ranked]
    ranks: dict[int, float] = {}
    position = 0
    while position < len(magnitudes):
        stop = position
        while (
            stop + 1 < len(magnitudes)
            and magnitudes[stop + 1] == magnitudes[position]
        ):
            stop += 1
        average = (position + stop) / 2.0 + 1.0
        for offset in range(position, stop + 1):
            ranks[ranked[offset][0]] = average
        position = stop + 1
    positive = sum(
        ranks[index] for index, value in enumerate(samples) if value > 0
    )
    negative = sum(
        ranks[index] for index, value in enumerate(samples) if value < 0
    )
    statistic = min(positive, negative)
    mean = n * (n + 1) / 4.0
    variance = n * (n + 1) * (2 * n + 1) / 24.0
    z = (statistic - mean) / math.sqrt(variance)
    return statistic, _two_sided_p_from_z(z)


@dataclass(frozen=True)
class ArmSummary:
    arm: str
    runs: int
    successes: int
    success_rate: float
    token_median: float


@dataclass(frozen=True)
class BenchmarkVerdict:
    h1_supported: bool
    h2_supported: bool
    h1_detail: str
    h2_detail: str


def summarize(
    records: list[object],
    control_arm: str = "control",
    treatment_arm: str = "treatment-a",
) -> tuple[dict[str, ArmSummary], BenchmarkVerdict]:
    by_task_arm_seed: dict[tuple[str, str, int], object] = {}
    for record in records:
        by_task_arm_seed[(record.task_id, record.arm, record.seed)] = record

    def arm_summary(arm: str) -> ArmSummary:
        arm_records = [r for r in records if r.arm == arm]
        tokens = sorted(r.total_tokens for r in arm_records)
        successes = sum(1 for r in arm_records if r.success)
        middle = len(tokens) // 2
        median = (
            float(tokens[middle])
            if len(tokens) % 2
            else (tokens[middle - 1] + tokens[middle]) / 2.0
        )
        return ArmSummary(
            arm=arm,
            runs=len(arm_records),
            successes=successes,
            success_rate=successes / len(arm_records) if arm_records else 0.0,
            token_median=median,
        )

    control = arm_summary(control_arm)
    treatment = arm_summary(treatment_arm)

    task_ids = sorted({record.task_id for record in records})
    paired_control = {
        task_id: [
            r
            for r in records
            if r.task_id == task_id and r.arm == control_arm and r.success
        ]
        for task_id in task_ids
    }
    paired_treatment = {
        task_id: [
            r
            for r in records
            if r.task_id == task_id and r.arm == treatment_arm and r.success
        ]
        for task_id in task_ids
    }
    treatment_only = sum(
        1
        for task_id in task_ids
        if paired_treatment[task_id] and not paired_control[task_id]
    )
    control_only = sum(
        1
        for task_id in task_ids
        if paired_control[task_id] and not paired_treatment[task_id]
    )
    p_mcnemar = mcnemar_exact(treatment_only, control_only)
    rate_delta = treatment.success_rate - control.success_rate
    h1_supported = (
        rate_delta >= 0.10
        or (treatment_only + control_only > 0 and p_mcnemar < 0.10)
    )
    h1_detail = (
        f"paired delta {rate_delta:+.1%}; discordant "
        f"treatment-only={treatment_only} control-only={control_only}; "
        f"exact McNemar p={p_mcnemar:.3f}"
    )

    per_task_token_delta: list[float] = []
    degraded_tasks = 0
    for task_id in task_ids:
        c_tokens = [r.total_tokens for r in records if r.task_id == task_id and r.arm == control_arm]
        t_tokens = [r.total_tokens for r in records if r.task_id == task_id and r.arm == treatment_arm]
        if c_tokens and t_tokens:
            c_median = sorted(c_tokens)[len(c_tokens) // 2]
            t_median = sorted(t_tokens)[len(t_tokens) // 2]
            per_task_token_delta.append(float(c_median - t_median))
        t_success = sum(1 for r in records if r.task_id == task_id and r.arm == treatment_arm and r.success)
        c_success = sum(1 for r in records if r.task_id == task_id and r.arm == control_arm and r.success)
        if t_success < c_success:
            degraded_tasks += 1
    reduction = (
        (control.token_median - treatment.token_median) / control.token_median
        if control.token_median
        else 0.0
    )
    _w, p_wilcoxon = wilcoxon_signed_rank(per_task_token_delta)
    h2_supported = (
        degraded_tasks <= 1 and reduction >= 0.20 and p_wilcoxon < 0.10
    )
    h2_detail = (
        f"degraded tasks {degraded_tasks}; token median reduction "
        f"{reduction:+.1%} (control {control.token_median:.0f} vs treatment"
        f" {treatment.token_median:.0f}); Wilcoxon p={p_wilcoxon:.3f}"
    )
    summaries = {control_arm: control, treatment_arm: treatment}
    return summaries, BenchmarkVerdict(
        h1_supported=h1_supported,
        h2_supported=h2_supported,
        h1_detail=h1_detail,
        h2_detail=h2_detail,
    )


def render_summary_markdown(
    manifest_name: str,
    summaries: dict[str, ArmSummary],
    verdict: BenchmarkVerdict,
) -> str:
    lines = [f"# M8 A/B summary — {manifest_name}", ""]
    lines.append("| arm | runs | successes | success rate | token median |")
    lines.append("| --- | --- | --- | --- | --- |")
    for arm in sorted(summaries):
        summary = summaries[arm]
        lines.append(
            f"| {summary.arm} | {summary.runs} | {summary.successes} |"
            f" {summary.success_rate:.1%} |"
            f" {summary.token_median:.0f} |"
        )
    lines += [
        "",
        f"- **H1 (success rate):** {'SUPPORTED' if verdict.h1_supported else 'not supported'}"
        f" — {verdict.h1_detail}",
        f"- **H2 (cost at equal success):** {'SUPPORTED' if verdict.h2_supported else 'not supported'}"
        f" — {verdict.h2_detail}",
        "",
        "Pre-registered criteria per frozen design v1.0 (do not retune).",
    ]
    return "\n".join(lines) + "\n"


__all__ = [
    "ArmSummary",
    "BenchmarkVerdict",
    "mcnemar_exact",
    "render_summary_markdown",
    "summarize",
    "wilcoxon_signed_rank",
]
