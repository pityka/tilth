#!/usr/bin/env python3
"""
Benchmark analysis and report generation.

Reads JSONL results from run.py and generates a markdown report
with context efficiency metrics and comparisons.
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median, mean, stdev


# Anthropic Claude pricing (per million tokens)
PRICING = {
    "cache_creation": 3.75,  # $3.75 per MTok
    "cache_read": 0.30,      # $0.30 per MTok
    "output": 15.00,         # $15.00 per MTok
    "input": 3.00,           # $3.00 per MTok
}


def compute_cost_breakdown(run: dict) -> dict[str, float]:
    """Compute cost breakdown by token category."""
    return {
        "cache_creation_cost": run.get("cache_creation_tokens", 0) * PRICING["cache_creation"] / 1_000_000,
        "cache_read_cost": run.get("cache_read_tokens", 0) * PRICING["cache_read"] / 1_000_000,
        "output_cost": run.get("output_tokens", 0) * PRICING["output"] / 1_000_000,
        "input_cost": run.get("input_tokens", 0) * PRICING["input"] / 1_000_000,
    }


def format_cost_breakdown(costs: dict[str, float], indent: str = "  ") -> str:
    """Format cost breakdown as single line."""
    parts = [
        f"cache_create=${costs['cache_creation_cost']:.3f}",
        f"cache_read=${costs['cache_read_cost']:.3f}",
        f"output=${costs['output_cost']:.3f}",
        f"input=${costs['input_cost']:.3f}",
    ]
    return f"{indent}{' '.join(parts)}"


def format_cost_delta(baseline_costs: dict[str, float], tilth_costs: dict[str, float], indent: str = "  ") -> str:
    """Format cost delta breakdown."""
    deltas = {
        "cache_creation": tilth_costs['cache_creation_cost'] - baseline_costs['cache_creation_cost'],
        "cache_read": tilth_costs['cache_read_cost'] - baseline_costs['cache_read_cost'],
        "output": tilth_costs['output_cost'] - baseline_costs['output_cost'],
        "input": tilth_costs['input_cost'] - baseline_costs['input_cost'],
    }
    parts = [
        f"Δcache_create={'+' if deltas['cache_creation'] >= 0 else ''}${deltas['cache_creation']:.3f}",
        f"Δcache_read={'+' if deltas['cache_read'] >= 0 else ''}${deltas['cache_read']:.3f}",
        f"Δoutput={'+' if deltas['output'] >= 0 else ''}${deltas['output']:.3f}",
        f"Δinput={'+' if deltas['input'] >= 0 else ''}${deltas['input']:.3f}",
    ]
    return f"{indent}{' '.join(parts)}"


def load_results(path: Path) -> list[dict]:
    """Load JSONL results file."""
    results = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                results.append(json.loads(line))
    return results


def group_by(results: list[dict], *keys: str) -> dict:
    """Group results by specified keys."""
    groups = defaultdict(list)
    for result in results:
        # Skip error entries that don't have all required fields
        if "error" in result:
            continue
        key = tuple(result.get(k) for k in keys)
        groups[key].append(result)
    return dict(groups)


def compute_stats(values: list) -> dict:
    """Compute statistics for a list of values."""
    if not values:
        return {
            "median": 0,
            "mean": 0,
            "stdev": 0,
            "min": 0,
            "max": 0,
        }

    return {
        "median": median(values),
        "mean": mean(values),
        "stdev": stdev(values) if len(values) > 1 else 0,
        "min": min(values),
        "max": max(values),
    }


def ascii_sparkline(values: list[int]) -> str:
    """Generate ASCII sparkline from values."""
    if not values:
        return ""

    if max(values) == min(values):
        return "▄" * len(values)

    chars = " ▁▂▃▄▅▆▇█"
    lo, hi = min(values), max(values)
    return "".join(
        chars[min(int((v - lo) / (hi - lo) * 8), 8)]
        for v in values
    )


def format_delta(baseline_val: float, tilth_val: float) -> str:
    """Format delta as percentage change."""
    if baseline_val == 0:
        return "—"
    pct_change = ((tilth_val - baseline_val) / baseline_val) * 100
    sign = "+" if pct_change > 0 else ""
    return f"{sign}{pct_change:.0f}%"


def find_median_run(runs: list[dict], metric: str) -> dict:
    """Find the run with median value for given metric."""
    if not runs:
        return {}
    sorted_runs = sorted(runs, key=lambda r: r.get(metric, 0))
    return sorted_runs[len(sorted_runs) // 2]


def merge_tool_calls(runs: list[dict]) -> dict[str, float]:
    """Merge tool_calls dicts from multiple runs and compute median counts."""
    # Collect all tool names
    all_tools = set()
    for run in runs:
        if "tool_calls" in run:
            all_tools.update(run["tool_calls"].keys())

    # Compute median count for each tool
    result = {}
    for tool in all_tools:
        counts = [run.get("tool_calls", {}).get(tool, 0) for run in runs]
        result[tool] = median(counts)

    return result


def generate_report(results: list[dict]) -> str:
    """Generate markdown report from results."""
    if not results:
        return "# Error\n\nNo valid results found in file.\n"

    # Filter out error entries
    valid_results = [r for r in results if "error" not in r]
    error_count = len(results) - len(valid_results)

    if not valid_results:
        return f"# Error\n\nAll {len(results)} runs failed.\n"

    # Extract metadata
    models = sorted(set(r["model"] for r in valid_results))
    tasks = sorted(set(r["task"] for r in valid_results))
    modes = sorted(set(r["mode"] for r in valid_results))
    repos = sorted(set(r.get("repo", "synthetic") for r in valid_results))
    max_rep = max(r["repetition"] for r in valid_results)
    num_reps = max_rep + 1

    # Build header
    lines = [
        "# tilth Benchmark Results",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"**Runs:** {len(valid_results)} valid",
    ]

    if error_count > 0:
        lines.append(f" ({error_count} errors)")

    lines.extend([
        f" | **Models:** {', '.join(models)} | **Repos:** {', '.join(repos)} | **Reps:** {num_reps}",
        "",
        "## Context Efficiency",
        "",
        "The primary metric. Context tokens (input + cached) represent the actual context processed each turn. This compounds because each turn re-sends conversation history.",
        "",
        "### Per-task comparison",
        "",
    ])

    # Group by task
    task_groups = group_by(valid_results, "task")

    for task_name in tasks:
        task_results = task_groups.get((task_name,), [])
        if not task_results:
            continue

        lines.append(f"#### {task_name}")
        lines.append("")

        # Show repo for the task
        task_repo = task_results[0].get("repo", "synthetic") if task_results else "synthetic"
        if task_repo != "synthetic":
            lines.append(f"*Repo: {task_repo}*")
            lines.append("")

        # Group by mode
        mode_groups = group_by(task_results, "mode")

        # Check if we have both baseline and tilth
        has_baseline = ("baseline",) in mode_groups
        has_tilth = ("tilth",) in mode_groups

        if has_baseline and has_tilth:
            baseline_runs = mode_groups[("baseline",)]
            tilth_runs = mode_groups[("tilth",)]

            # Compute stats
            metrics = [
                ("Context tokens", "context_tokens"),
                ("Output tokens", "output_tokens"),
                ("Turns", "num_turns"),
                ("Tool calls", "num_tool_calls"),
                ("Cost USD", "total_cost_usd"),
                ("Duration ms", "duration_ms"),
            ]

            lines.append("| Metric | baseline | tilth | delta |")
            lines.append("|--------|----------|-------|-------|")

            for label, key in metrics:
                baseline_stats = compute_stats([r[key] for r in baseline_runs])
                tilth_stats = compute_stats([r[key] for r in tilth_runs])
                delta = format_delta(baseline_stats["median"], tilth_stats["median"])

                if key == "total_cost_usd":
                    baseline_fmt = f"${baseline_stats['median']:.4f}"
                    tilth_fmt = f"${tilth_stats['median']:.4f}"
                else:
                    baseline_fmt = f"{baseline_stats['median']:.0f}"
                    tilth_fmt = f"{tilth_stats['median']:.0f}"

                lines.append(f"| {label} (median) | {baseline_fmt} | {tilth_fmt} | {delta} |")

            # Correctness
            baseline_correct = sum(1 for r in baseline_runs if r["correct"])
            tilth_correct = sum(1 for r in tilth_runs if r["correct"])
            baseline_pct = (baseline_correct / len(baseline_runs)) * 100
            tilth_pct = (tilth_correct / len(tilth_runs)) * 100

            lines.append(f"| Correctness | {baseline_pct:.0f}% | {tilth_pct:.0f}% | — |")
            lines.append("")

            # Cost breakdown
            baseline_median_run_cost = find_median_run(baseline_runs, "total_cost_usd")
            tilth_median_run_cost = find_median_run(tilth_runs, "total_cost_usd")

            baseline_costs = compute_cost_breakdown(baseline_median_run_cost)
            tilth_costs = compute_cost_breakdown(tilth_median_run_cost)

            baseline_total = baseline_median_run_cost.get("total_cost_usd", 0.0)
            tilth_total = tilth_median_run_cost.get("total_cost_usd", 0.0)
            total_delta = tilth_total - baseline_total

            baseline_turns = baseline_median_run_cost.get("num_turns", 0)
            tilth_turns = tilth_median_run_cost.get("num_turns", 0)
            turns_delta = tilth_turns - baseline_turns

            baseline_correct_str = "correct" if baseline_median_run_cost.get("correct", False) else "incorrect"
            tilth_correct_str = "correct" if tilth_median_run_cost.get("correct", False) else "incorrect"

            lines.append("**Cost breakdown (median run):**")
            lines.append("")
            lines.append(f"  baseline: {baseline_turns} turns, ${baseline_total:.2f}, {baseline_correct_str}")
            lines.append(format_cost_breakdown(baseline_costs))
            lines.append(f"  tilth:    {tilth_turns} turns, ${tilth_total:.2f}, {tilth_correct_str}")
            lines.append(format_cost_breakdown(tilth_costs))
            lines.append(f"  delta:    {'+' if turns_delta >= 0 else ''}{turns_delta} turns, {'+' if total_delta >= 0 else ''}${total_delta:.2f}")
            lines.append(format_cost_delta(baseline_costs, tilth_costs))
            lines.append("")

            # Per-turn sparklines
            baseline_median_run = find_median_run(baseline_runs, "context_tokens")
            tilth_median_run = find_median_run(tilth_runs, "context_tokens")

            baseline_per_turn = baseline_median_run.get("per_turn_context_tokens", [])
            tilth_per_turn = tilth_median_run.get("per_turn_context_tokens", [])

            if baseline_per_turn and tilth_per_turn:
                lines.append("**Per-turn context tokens (median run):**")
                lines.append("")
                baseline_spark = ascii_sparkline(baseline_per_turn)
                tilth_spark = ascii_sparkline(tilth_per_turn)
                baseline_range = f"{min(baseline_per_turn):,} → {max(baseline_per_turn):,}"
                tilth_range = f"{min(tilth_per_turn):,} → {max(tilth_per_turn):,}"
                lines.append(f"  baseline: {baseline_spark} ({baseline_range})")
                lines.append(f"  tilth:    {tilth_spark} ({tilth_range})")
                lines.append("")

            # Tool breakdown
            baseline_tools = merge_tool_calls(baseline_runs)
            tilth_tools = merge_tool_calls(tilth_runs)

            if baseline_tools or tilth_tools:
                lines.append("**Tool breakdown (median counts):**")
                lines.append("")
                if baseline_tools:
                    tool_strs = [f"{name}={count:.0f}" for name, count in baseline_tools.items()]
                    lines.append(f"  baseline: {', '.join(tool_strs)}")
                if tilth_tools:
                    tool_strs = [f"{name}={count:.0f}" for name, count in tilth_tools.items()]
                    lines.append(f"  tilth:    {', '.join(tool_strs)}")
                lines.append("")

        else:
            # Only one mode available
            for mode_name in modes:
                mode_results = mode_groups.get((mode_name,), [])
                if not mode_results:
                    continue

                lines.append(f"**Mode: {mode_name}**")
                lines.append("")
                lines.append("| Metric | Median |")
                lines.append("|--------|--------|")

                metrics = [
                    ("Context tokens", "context_tokens"),
                    ("Output tokens", "output_tokens"),
                    ("Turns", "num_turns"),
                    ("Tool calls", "num_tool_calls"),
                    ("Cost USD", "total_cost_usd"),
                    ("Duration ms", "duration_ms"),
                ]

                for label, key in metrics:
                    stats = compute_stats([r[key] for r in mode_results])
                    if key == "total_cost_usd":
                        val_fmt = f"${stats['median']:.4f}"
                    else:
                        val_fmt = f"{stats['median']:.0f}"
                    lines.append(f"| {label} | {val_fmt} |")

                correct = sum(1 for r in mode_results if r["correct"])
                pct = (correct / len(mode_results)) * 100
                lines.append(f"| Correctness | {pct:.0f}% |")
                lines.append("")

        lines.append("")

    # Summary section (only if we have both modes)
    baseline_all = [r for r in valid_results if r["mode"] == "baseline"]
    tilth_all = [r for r in valid_results if r["mode"] == "tilth"]

    if baseline_all and tilth_all:
        lines.append("## Summary")
        lines.append("")
        lines.append("Averaged across all tasks (median of medians):")
        lines.append("")
        lines.append("| Metric | baseline | tilth | Improvement |")
        lines.append("|--------|----------|-------|-------------|")

        # Compute median-of-medians for each metric
        metrics = [
            ("Context tokens", "context_tokens"),
            ("Turns", "num_turns"),
            ("Tool calls", "num_tool_calls"),
            ("Cost USD", "total_cost_usd"),
        ]

        for label, key in metrics:
            # Group baseline/tilth by task, compute median for each task, then median of those
            baseline_by_task = group_by(baseline_all, "task")
            tilth_by_task = group_by(tilth_all, "task")

            baseline_medians = [
                compute_stats([r[key] for r in runs])["median"]
                for runs in baseline_by_task.values()
            ]
            tilth_medians = [
                compute_stats([r[key] for r in runs])["median"]
                for runs in tilth_by_task.values()
            ]

            if baseline_medians and tilth_medians:
                baseline_val = median(baseline_medians)
                tilth_val = median(tilth_medians)
                improvement = format_delta(baseline_val, tilth_val)

                if key == "total_cost_usd":
                    baseline_fmt = f"${baseline_val:.4f}"
                    tilth_fmt = f"${tilth_val:.4f}"
                else:
                    baseline_fmt = f"{baseline_val:.0f}"
                    tilth_fmt = f"{tilth_val:.0f}"

                lines.append(f"| {label} | {baseline_fmt} | {tilth_fmt} | {improvement} |")

        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze benchmark results and generate report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analyze.py results/benchmark_20260212_150000.jsonl
  python analyze.py results/benchmark_20260212_150000.jsonl -o report.md
        """,
    )

    parser.add_argument(
        "results_file",
        type=Path,
        help="Path to JSONL results file from run.py",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Output path for markdown report (default: print to stdout)",
    )

    args = parser.parse_args()

    # Validate input file
    if not args.results_file.exists():
        print(f"ERROR: File not found: {args.results_file}", file=sys.stderr)
        sys.exit(1)

    # Load and analyze
    try:
        results = load_results(args.results_file)
    except Exception as e:
        print(f"ERROR: Failed to load results: {e}", file=sys.stderr)
        sys.exit(1)

    report = generate_report(results)

    # Output
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report)
        print(f"Report written to: {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
