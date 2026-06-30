"""Reusable CPU/RAM profiler — context manager that samples psutil every 0.5s.

Usage:
    with Profiler(pid=123) as p:
        run_something()
    p.summary()  # prints report
    p.save("results.json")
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Event, Thread
from typing import Optional

import psutil

SCRIPT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = SCRIPT_DIR / "bench_results"


class Profiler:
    """Sample CPU% and RSS every `interval` seconds for a given PID or subprocess."""

    def __init__(
        self,
        pid: Optional[int] = None,
        cmd: Optional[str] = None,
        label: str = "unknown",
        interval: float = 0.5,
    ):
        self.pid = pid
        self.cmd = cmd  # shell command to run & profile
        self.label = label
        self.interval = interval
        self._stop = Event()
        self._thread: Optional[Thread] = None
        self.samples: list[dict] = []
        self._proc: Optional[psutil.Process] = None
        self._process: Optional[subprocess.Popen] = None
        self.duration: float = 0.0

    def __enter__(self):
        self._start = time.time()
        if self.cmd:
            self._process = subprocess.Popen(
                self.cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )
            self.pid = self._process.pid
            # wait for process to be spawnable
            _proc = None
            for _ in range(50):
                try:
                    _proc = psutil.Process(self.pid)
                    _proc.cpu_percent()
                    break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    time.sleep(0.1)
            self._proc = _proc
        elif self.pid:
            self._proc = psutil.Process(self.pid)
        else:
            self._proc = psutil.Process()
        self._thread = Thread(target=self._sample, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *args):
        self._stop.set()
        if self._thread:
            self._thread.join()
        self.duration = time.time() - self._start
        if self._process:
            try:
                self._process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)

    def _sample(self):
        # warm up — first call returns 0.0 on many OSes
        try:
            self._proc.cpu_percent()
        except Exception:
            pass
        while not self._stop.is_set():
            try:
                cpu = self._proc.cpu_percent()
                mem = self._proc.memory_info()
                rss = mem.rss
                vms = mem.vms
                mem_pct = self._proc.memory_percent()
                create_time = self._proc.create_time()
                elapsed = (time.time() - create_time) * 1000
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self._stop.set()
                break
            self.samples.append(
                {
                    "t_ms": round(elapsed, 1),
                    "cpu_pct": cpu,
                    "rss_mb": round(rss / 1024 / 1024, 2),
                    "vms_mb": round(vms / 1024 / 1024, 2),
                    "mem_pct": round(mem_pct, 2),
                }
            )
            self._stop.wait(self.interval)

    def _cpu_values(self):
        return [s["cpu_pct"] for s in self.samples]

    def _rss_values(self):
        return [s["rss_mb"] for s in self.samples]

    def stats(self) -> dict:
        cpus = self._cpu_values()
        rss = self._rss_values()
        n = len(cpus)
        if n == 0:
            return {"n_samples": 0, "error": "no samples collected"}

        cpus_sorted = sorted(cpus)
        rss_sorted = sorted(rss)
        mean_cpu = sum(cpus) / n
        mean_rss = sum(rss) / n

        # spike: any sample > 2x the mean (after excluding the sample itself)
        spike_threshold = mean_cpu * 2
        spikes = [c for c in cpus if c > spike_threshold]

        return {
            "label": self.label,
            "n_samples": n,
            "duration_s": round(self.duration, 2),
            "cpu": {
                "mean": round(mean_cpu, 2),
                "p50": round(cpus_sorted[n // 2], 2),
                "p95": round(cpus_sorted[int(n * 0.95)], 2),
                "p99": round(cpus_sorted[int(n * 0.99)], 2),
                "max": round(max(cpus), 2),
                "min": round(min(cpus), 2),
                "std": round(
                    (sum((c - mean_cpu) ** 2 for c in cpus) / n) ** 0.5, 2
                ),
                "n_spikes": len(spikes),
                "spike_pct": round(len(spikes) / n * 100, 2) if n else 0,
                "spike_threshold": round(spike_threshold, 2),
            },
            "rss_mb": {
                "mean": round(mean_rss, 1),
                "min": round(min(rss), 1),
                "max": round(max(rss), 1),
                "delta": round(max(rss) - min(rss), 1),
                "first": round(rss[0], 1) if rss else 0,
                "last": round(rss[-1], 1) if rss else 0,
            },
        }

    def summary(self) -> str:
        s = self.stats()
        if "error" in s:
            return f"[{self.label}] {s['error']}"

        cpu = s["cpu"]
        rss = s["rss_mb"]
        lines = [
            f"{'='*60}",
            f"  PROFILER: {self.label}",
            f"  Duration:    {s['duration_s']:.1f}s,  {s['n_samples']} samples",
            f"{'─'*60}",
            f"  CPU (%):     mean={cpu['mean']}  p50={cpu['p50']}  p95={cpu['p95']}  p99={cpu['p99']}",
            f"              max={cpu['max']}  min={cpu['min']}  std={cpu['std']}",
            f"              spikes={cpu['n_spikes']} ({cpu['spike_pct']}% of samples, threshold >{cpu['spike_threshold']}%)",
            f"  RSS (MB):    mean={rss['mean']}  min={rss['min']}  max={rss['max']}",
            f"              delta={rss['delta']}  first={rss['first']}  last={rss['last']}",
            f"              {'⚠️  MEMORY GROWTH' if rss['delta'] > 50 else 'stable'}",
            f"{'='*60}",
        ]
        return "\n".join(lines)

    def save(self, path: Optional[Path] = None):
        if path is None:
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            path = RESULTS_DIR / f"profiler_{self.label}_{ts}.json"
        stats = self.stats()
        stats["samples"] = self.samples
        with open(path, "w") as f:
            json.dump(stats, f, indent=2)
        print(f"  Results saved to {path}")


def profile_ml(runs: int = 10):
    """Run ML inference benchmarks under profiler."""
    bench_script = str(SCRIPT_DIR.parent / "ml/_FINAL_SCRIPTS/bench_inference.py")
    label = f"ml_{runs}runs"
    with Profiler(cmd=f"python {bench_script} --runs {runs}", label=label) as p:
        pass
    print(p.summary())
    p.save()
    return p.stats()


def profile_api(
    vus: int = 20,
    cache_enabled: bool = True,
    base_url: str = "http://localhost:5000",
):
    """Run k6 API load test under profiler."""
    cache_flag = "true" if cache_enabled else "false"
    label = f"k6_{vus}vu_cache{cache_flag}"
    cmd = (
        f"k6 run -e BASE_URL={base_url} -e VUS={vus} "
        f"{SCRIPT_DIR / 'bench_api.js'}"
    )
    # Also profile the app container if running via Docker
    # For now: profile k6 itself as a proxy for app behavior
    with Profiler(cmd=cmd, label=label) as p:
        pass
    print(p.summary())
    p.save()
    return p.stats()


def profile_esp32(
    devices: list[int] = None,
    server_url: str = "http://localhost:5000",
):
    """Run ESP32 concurrency benchmark under profiler."""
    if devices is None:
        devices = [10, 25, 50]
    results = []
    for n in devices:
        label = f"esp32_{n}dev"
        cmd = (
            f"python {SCRIPT_DIR / 'bench_esp32_concurrency.py'} "
            f"--devices {n} "
            f"--server {server_url}"
        )
        with Profiler(cmd=cmd, label=label) as p:
            pass
        print(p.summary())
        p.save()
        results.append(p.stats())
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PD-Server Performance Profiler")
    parser.add_argument(
        "--mode",
        choices=["ml", "api", "esp32", "idle"],
        required=True,
    )
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--vus", type=int, default=20)
    parser.add_argument("--cache", type=str, default="true")
    parser.add_argument("--server", default="http://localhost:5000")
    parser.add_argument("--devices", type=int, nargs="+", default=[10, 25, 50])
    args = parser.parse_args()

    if args.mode == "ml":
        profile_ml(runs=args.runs)
    elif args.mode == "api":
        profile_api(
            vus=args.vus,
            cache_enabled=args.cache.lower() == "true",
            base_url=args.server,
        )
    elif args.mode == "esp32":
        profile_esp32(devices=args.devices, server_url=args.server)
    elif args.mode == "idle":
        label = "idle_baseline"
        with Profiler(label=label, interval=1.0) as p:
            time.sleep(30)
        print(p.summary())
        p.save()
