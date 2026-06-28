"""
Benchmark concurrent ESP32 device handling.

Spawns N parallel SSE connections to /api/esp32/stream, registers devices,
sends heartbeats, and measures success rate and latency.

Usage:
    python scripts/bench_esp32_concurrency.py
    python scripts/bench_esp32_concurrency.py --devices 50 --server http://localhost:8080
    python scripts/bench_esp32_concurrency.py --devices 10 25 50 100  # Multi-stage
"""
import argparse
import hashlib
import hmac
import json
import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from config import Config
    FACTORY_SECRET = Config.FACTORY_SECRET
except Exception as e:
    raise RuntimeError(
        "Failed to load Config/FACTORY_SECRET; run from repo root or set FACTORY_SECRET env var"
    ) from e


@dataclass
class BenchResult:
    n_devices: int
    registered: int = 0
    paired: int = 0
    heartbeats_sent: int = 0
    heartbeats_ok: int = 0
    heartbeat_latencies_ms: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def _gen_factory_key(device_id: str, secret: str) -> str:
    return hmac.new(
        secret.encode(),
        device_id.encode(),
        hashlib.sha256,
    ).hexdigest()


def run_device(device_id: str, server_url: str, bench: BenchResult) -> None:
    try:
        # 1. Register device
        factory_key = _gen_factory_key(device_id, FACTORY_SECRET)
        reg_resp = requests.post(
            f"{server_url}/api/esp32/register",
            json={"device_id": device_id, "factory_api_key": factory_key},
            timeout=10,
        )
        if reg_resp.status_code == 200:
            bench.registered += 1
        elif reg_resp.status_code != 409:  # 409 = already registered
            bench.errors.append(f"REGISTER {device_id}: {reg_resp.status_code}")

        # 2. Send heartbeats
        for _ in range(3):
            try:
                t0 = time.perf_counter()
                hb_resp = requests.post(
                    f"{server_url}/api/esp32/heartbeat",
                    json={"device_id": device_id, "api_key": factory_key},
                    timeout=10,
                )
                elapsed = (time.perf_counter() - t0) * 1000
                bench.heartbeats_sent += 1
                if hb_resp.status_code == 200:
                    bench.heartbeats_ok += 1
                    bench.heartbeat_latencies_ms.append(elapsed)
                else:
                    bench.errors.append(f"HEARTBEAT {device_id}: {hb_resp.status_code}")
            except requests.RequestException as e:
                bench.errors.append(f"HEARTBEAT_ERR {device_id}: {e}")
            time.sleep(0.1)

    except requests.RequestException as e:
        bench.errors.append(f"CONNECT_ERR {device_id}: {e}")


def bench_stage(n_devices: int, server_url: str) -> BenchResult:
    print(f"\n── Stage: {n_devices} concurrent devices ──")
    bench = BenchResult(n_devices=n_devices)
    device_ids = [f"BENCH-{i:04d}-{n_devices}" for i in range(n_devices)]

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=n_devices) as pool:
        futures = {pool.submit(run_device, did, server_url, bench): did for did in device_ids}
        for future in as_completed(futures):
            future.result()
    elapsed = time.perf_counter() - t0

    hb_latencies = bench.heartbeat_latencies_ms
    p50 = sorted(hb_latencies)[len(hb_latencies) // 2] if hb_latencies else 0
    p95 = sorted(hb_latencies)[int(len(hb_latencies) * 0.95)] if hb_latencies else 0
    p99 = sorted(hb_latencies)[int(len(hb_latencies) * 0.99)] if hb_latencies else 0

    print(f"  Duration:       {elapsed:.1f}s")
    print(f"  Registered:     {bench.registered}/{n_devices}")
    print(f"  Heartbeats:     {bench.heartbeats_ok}/{bench.heartbeats_sent} ok")
    print(f"  Latency p50:    {p50:.1f} ms")
    print(f"  Latency p95:    {p95:.1f} ms")
    print(f"  Latency p99:    {p99:.1f} ms")
    print(f"  Errors:         {len(bench.errors)}")

    return bench


def main():
    parser = argparse.ArgumentParser(description="Benchmark ESP32 concurrency")
    parser.add_argument("--devices", type=int, nargs="+", default=[10, 25, 50],
                        help="Number of concurrent devices per stage (default: 10 25 50)")
    parser.add_argument("--server", default="http://localhost:8080",
                        help="Server URL (default: http://localhost:8080)")
    parser.add_argument("--output", type=str, default=None,
                        help="Save results to JSON")
    args = parser.parse_args()

    print("=" * 65)
    print("  PD Server — ESP32 Concurrency Benchmarks")
    print(f"  Server:   {args.server}")
    print(f"  Stages:   {args.devices}")
    print("=" * 65)

    all_results = []
    for n in args.devices:
        result = bench_stage(n, args.server)
        all_results.append(result)

    print()
    print("=" * 65)
    print("  SUMMARY TABLE")
    print("=" * 65)
    header = f"{'Devices':<10} {'Registered':<12} {'HB OK%':<10} {'p50(ms)':<10} {'p95(ms)':<10} {'p99(ms)':<10} {'Errors':<8}"
    print(header)
    print("-" * 70)
    for r in all_results:
        hb_latencies = r.heartbeat_latencies_ms
        p50 = sorted(hb_latencies)[len(hb_latencies) // 2] if hb_latencies else 0
        p95 = sorted(hb_latencies)[int(len(hb_latencies) * 0.95)] if hb_latencies else 0
        p99 = sorted(hb_latencies)[int(len(hb_latencies) * 0.99)] if hb_latencies else 0
        hb_ok_pct = (r.heartbeats_ok / r.heartbeats_sent * 100) if r.heartbeats_sent else 0
        print(f"{r.n_devices:<10} {r.registered:<12} {hb_ok_pct:<10.1f} {p50:<10.1f} {p95:<10.1f} {p99:<10.1f} {len(r.errors):<8}")

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        data = []
        for r in all_results:
            hb_latencies = r.heartbeat_latencies_ms
            p50 = sorted(hb_latencies)[len(hb_latencies) // 2] if hb_latencies else 0
            p95 = sorted(hb_latencies)[int(len(hb_latencies) * 0.95)] if hb_latencies else 0
            p99 = sorted(hb_latencies)[int(len(hb_latencies) * 0.99)] if hb_latencies else 0
            hb_ok_pct = (r.heartbeats_ok / r.heartbeats_sent * 100) if r.heartbeats_sent else 0
            data.append({
                "n_devices": r.n_devices,
                "registered": r.registered,
                "heartbeat_ok_pct": round(hb_ok_pct, 1),
                "latency_ms_p50": round(p50, 1),
                "latency_ms_p95": round(p95, 1),
                "latency_ms_p99": round(p99, 1),
                "errors": len(r.errors),
                "error_samples": r.errors[:5],
            })
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\n  Results saved to {out_path}")


if __name__ == "__main__":
    main()
