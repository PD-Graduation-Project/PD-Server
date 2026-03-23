#!/usr/bin/env python3
"""
Mock ML Worker for Testing

Simulates ML inference worker without loading PyTorch models.
Returns fixed scores for all predictions.

Environment Variables:
    REDIS_URL: Redis URL (default: redis://redis:6379/0)
    MOCK_SCORE: Default score to return (default: 0.5)
"""

import os
import time

import redis
from rq import Queue
from rq.worker import SimpleWorker


def mock_predict_tremor(test_id: int) -> float:
    print(f"[MockWorker] Predicting tremor for test {test_id}")
    time.sleep(0.1)
    return float(os.getenv("MOCK_SCORE", "0.5"))


def mock_predict_drawing(test_id: int) -> float:
    print(f"[MockWorker] Predicting drawing for test {test_id}")
    time.sleep(0.1)
    return float(os.getenv("MOCK_SCORE", "0.5"))


def mock_predict_voice(test_id: int) -> float:
    print(f"[MockWorker] Predicting voice for test {test_id}")
    time.sleep(0.1)
    return float(os.getenv("MOCK_SCORE", "0.5"))


def mock_predict_overall(group_id: int) -> float:
    print(f"[MockWorker] Predicting overall for group {group_id}")
    time.sleep(0.1)
    return float(os.getenv("MOCK_SCORE", "0.5"))


class MockMLWorker(SimpleWorker):
    def perform_job(self, job, queue):
        print(f"[MockWorker] Processing job {job.id}: {job.func_name}")

        if "predict_tremor" in str(job.func_name):
            result = mock_predict_tremor(job.args[0] if job.args else 0)
        elif "predict_drawing" in str(job.func_name):
            result = mock_predict_drawing(job.args[0] if job.args else 0)
        elif "predict_voice" in str(job.func_name):
            result = mock_predict_voice(job.args[0] if job.args else 0)
        elif "predict_overall" in str(job.func_name):
            result = mock_predict_overall(job.args[0] if job.args else 0)
        else:
            print(f"[MockWorker] Unknown function: {job.func_name}, executing normally")
            return super().perform_job(job, queue)

        print(f"[MockWorker] Job {job.id} completed with result: {result}")
        job._result = result
        return True


def run_mock_worker():
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    print(f"[MockWorker] Connecting to Redis: {redis_url}")

    conn = redis.from_url(redis_url)
    q = Queue("ml", connection=conn)

    print("[MockWorker] Starting mock ML worker...")
    print("[MockWorker] Listening for jobs on queue 'ml'")

    worker = MockMLWorker([q], connection=conn)
    worker.work()


if __name__ == "__main__":
    run_mock_worker()
