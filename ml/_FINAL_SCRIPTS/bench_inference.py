"""
Benchmark ML inference times for all 4 PD detection models.

Runs each predictor N times on the example data, reports mean ± std.
Run from the ml/_FINAL_SCRIPTS/ directory.

Usage:
    cd ml/_FINAL_SCRIPTS
    python bench_inference.py
    python bench_inference.py --runs 10 --output ../../scripts/bench_results/bench_ml.json
"""
import argparse
import json
import sys
import time
from pathlib import Path


def _warmup_cpu():
    """Small warmup to prime CPU frequency scaling."""
    for _ in range(3):
        _ = [i ** 2 for i in range(100_000)]


def bench_module(
    module_name: str,
    predict_fn_name: str,
    predict_args: tuple,
    label: str,
    runs: int = 5,
    skip: bool = False,
) -> dict:
    if skip:
        return {"label": label, "runs": 0, "mean_ms": 0, "std_ms": 0, "min_ms": 0, "max_ms": 0, "status": "skipped"}

    mod = __import__(module_name, fromlist=[predict_fn_name])
    predict_fn = getattr(mod, predict_fn_name)

    timings = []
    for i in range(runs):
        t0 = time.perf_counter()
        result = predict_fn(*predict_args)
        elapsed = (time.perf_counter() - t0) * 1000
        timings.append(elapsed)
        print(f"  [{i + 1}/{runs}] {label}: {elapsed:.1f} ms  (score={result:.4f})")

    mean = sum(timings) / len(timings)
    variance = sum((t - mean) ** 2 for t in timings) / len(timings)
    std = variance ** 0.5
    return {
        "label": label,
        "runs": runs,
        "mean_ms": round(mean, 1),
        "std_ms": round(std, 1),
        "min_ms": round(min(timings), 1),
        "max_ms": round(max(timings), 1),
        "status": "ok",
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark ML inference times")
    parser.add_argument("--runs", type=int, default=5, help="Number of runs per model (default: 5)")
    parser.add_argument("--output", type=str, default=None, help="Save results to JSON file")
    parser.add_argument("--skip-tremor", action="store_true", help="Skip tremor benchmark")
    parser.add_argument("--skip-drawing", action="store_true", help="Skip drawing benchmark")
    parser.add_argument("--skip-voice", action="store_true", help="Skip voice benchmark")
    parser.add_argument("--skip-questionnaire", action="store_true", help="Skip questionnaire benchmark")
    args = parser.parse_args()

    EXAMPLES = Path("examples")

    print("=" * 65)
    print("  PD Server — ML Inference Benchmarks")
    print(f"  Runs per model: {args.runs}")
    print("=" * 65)

    _warmup_cpu()

    from ml_utils.helper_functions import load_user_data

    results = []

    # 1. Tremor
    tremor_dir = str(EXAMPLES / "tremor" / "healthy")
    results.append(bench_module(
        "predict_from_tremor", "predict",
        (tremor_dir, 0, "right"),
        "Tremor (healthy, CrossArms)",
        args.runs, args.skip_tremor,
    ))

    # 2. Drawing
    drawing_path = str(EXAMPLES / "Healthy1.png")
    results.append(bench_module(
        "predict_from_drawing", "predict",
        (drawing_path,),
        "Drawing (healthy spiral)",
        args.runs, args.skip_drawing,
    ))

    # 3. Voice
    audio_path = str(EXAMPLES / "healthy_audio.wav")
    results.append(bench_module(
        "predict_from_audio", "predict",
        (audio_path, "M"),
        "Voice (healthy audio)",
        args.runs, args.skip_voice,
    ))

    # 4. Questionnaire
    user_data = load_user_data(str(EXAMPLES / "user_data.yaml"))
    q_input = [
        user_data["age"], user_data["height"], user_data["weight"],
        user_data["gender"], user_data["appearance_in_kinship"],
        user_data["appearance_in_first_grade_kinship"],
        user_data["questions"],
    ]
    results.append(bench_module(
        "predict_from_questionnaire", "predict",
        (q_input,),
        "Questionnaire",
        args.runs, args.skip_questionnaire,
    ))

    print()
    print("=" * 65)
    print("  SUMMARY")
    print("=" * 65)
    table = f"{'Model':<30} {'Mean (ms)':<12} {'Std (ms)':<12} {'Min (ms)':<12} {'Max (ms)':<12}\n"
    table += "-" * 78 + "\n"
    for r in results:
        if r["status"] == "ok":
            table += f"{r['label']:<30} {r['mean_ms']:<12.1f} {r['std_ms']:<12.1f} {r['min_ms']:<12.1f} {r['max_ms']:<12.1f}\n"
        else:
            table += f"{r['label']:<30} {'SKIPPED':<12}\n"
    print(table)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump({"runs": args.runs, "results": results, "system": {"cpus": "limited to 2", "memory": "limited to 12G"}}, f, indent=2)
        print(f"  Results saved to {out_path}")


if __name__ == "__main__":
    main()
