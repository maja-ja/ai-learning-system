#!/usr/bin/env python3
"""
Generate first batch of Aha seed data with resume/retry support.

This script writes to your FastAPI endpoints:
  - POST /api/learner/context
  - POST /api/aha/events/batch

It is designed for large batches like 10,000 rows.
"""

from __future__ import annotations

import argparse
import json
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4


AGE_BANDS = ["13_15", "16_18", "19_22", "23_plus"]
REGIONS = ["TW-TPE", "TW-NWT", "TW-TXG", "TW-TNN", "TW-KHH", "HK", "SG"]
TOPICS = [
    "quadratic_func",
    "trig_laws",
    "vector_inner_product",
    "classic_prob",
    "conditional_prob_bayes",
    "ma_derivative_logic",
    "ma_calculus_fundamental",
    "ma_complex_demoivre",
]
HOOK_VARIANTS = [
    ("analogy", "A"),
    ("visual", "B"),
    ("misconception_fix", "C"),
    ("exam_shortcut", "D"),
    ("story", "E"),
]


@dataclass
class Progress:
    done: int = 0
    failed: int = 0
    contexts: int = 0


def _post_json(url: str, payload: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        if not raw:
            return {}
        return json.loads(raw)


def _post_with_retry(
    url: str,
    payload: Dict[str, Any],
    retries: int,
    backoff_sec: float,
    timeout: int,
) -> Dict[str, Any]:
    last_error: Exception | None = None
    for i in range(retries + 1):
        try:
            return _post_json(url, payload, timeout=timeout)
        except (urllib.error.URLError, TimeoutError, ValueError) as ex:
            last_error = ex
            if i >= retries:
                break
            time.sleep(backoff_sec * (2**i))
    raise RuntimeError(f"POST failed after retries: {url}: {last_error}")


def _checkpoint_save(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _checkpoint_load(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {"cursor": 0, "failed": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {"cursor": 0, "failed": []}


def make_event(profile_id: str, tenant_id: str, idx: int) -> Dict[str, Any]:
    topic = random.choice(TOPICS)
    hook_type, arm = random.choice(HOOK_VARIANTS)
    variant = f"{topic}:{hook_type}:{arm}:r1"
    is_correct = random.random() < 0.62
    event_type = random.choice(["hint_shown", "aha_reported", "question_answered"])
    payload: Dict[str, Any] = {
        "tenant_id": tenant_id,
        "profile_id": profile_id,
        "event_type": event_type,
        "topic_key": topic,
        "hook_variant_id": variant,
        "metadata": {
            "session_id": f"seed-sess-{idx // 10}",
            "client_ts": int(time.time() * 1000),
            "surface": "lab",
            "seed_run": True,
        },
    }
    if event_type == "aha_reported":
        payload["latency_ms"] = random.randint(800, 32000)
        payload["self_report_delta"] = random.randint(1, 4)
    if event_type == "question_answered":
        payload["question_id"] = f"q-{topic}-{idx % 100}"
        payload["is_correct"] = is_correct
    return payload


def make_context(profile_id: str, tenant_id: str) -> Dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "profile_id": profile_id,
        "age_band": random.choice(AGE_BANDS),
        "region_code": random.choice(REGIONS),
        "preferred_language": "zh-TW",
        "metadata": {"source": "seed_generator"},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate Aha seed events in large batches")
    ap.add_argument("--api-base", default="http://127.0.0.1:8000", help="FastAPI base URL")
    ap.add_argument("--tenant-id", required=True, help="Target tenant UUID")
    ap.add_argument("--count", type=int, default=10000, help="Total rows to generate")
    ap.add_argument("--batch-size", type=int, default=200, help="Batch insert size")
    ap.add_argument("--retry", type=int, default=3, help="Retry count per request")
    ap.add_argument("--backoff-sec", type=float, default=0.5, help="Exponential backoff base")
    ap.add_argument("--timeout-sec", type=int, default=30, help="HTTP timeout")
    ap.add_argument("--delay-sec", type=float, default=0.1, help="Delay between batches")
    ap.add_argument(
        "--checkpoint",
        default=".tmp/aha_seed_checkpoint.json",
        help="Checkpoint path for resume",
    )
    ap.add_argument(
        "--profile-pool-size",
        type=int,
        default=120,
        help="How many profile IDs to cycle (only used without --profile-ids-file)",
    )
    ap.add_argument(
        "--profile-ids-file",
        default="",
        help="Path to newline-delimited existing profile UUIDs (recommended for FK-safe inserts)",
    )
    ap.add_argument(
        "--allow-synthetic-profiles",
        action="store_true",
        help="Allow generated UUIDs if no profile-ids-file is provided",
    )
    args = ap.parse_args()

    if args.batch_size <= 0:
        raise SystemExit("batch-size must be > 0")
    if args.profile_pool_size <= 0:
        raise SystemExit("profile-pool-size must be > 0")

    base = args.api_base.rstrip("/")
    url_context = f"{base}/api/learner/context"
    url_events = f"{base}/api/aha/events/batch"
    checkpoint_path = Path(args.checkpoint)
    state = _checkpoint_load(checkpoint_path)
    cursor = int(state.get("cursor", 0))
    failed = list(state.get("failed", []))

    progress = Progress(done=cursor, failed=len(failed), contexts=0)
    profile_pool: List[str] = []
    if args.profile_ids_file:
        p = Path(args.profile_ids_file)
        if not p.is_file():
            raise SystemExit(f"profile-ids-file not found: {p}")
        profile_pool = [
            ln.strip()
            for ln in p.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        if not profile_pool:
            raise SystemExit("profile-ids-file is empty")
    elif args.allow_synthetic_profiles:
        profile_pool = [str(uuid4()) for _ in range(args.profile_pool_size)]
    else:
        raise SystemExit(
            "Provide --profile-ids-file for existing profile UUIDs "
            "or use --allow-synthetic-profiles for non-FK test environments."
        )

    # Ensure contexts exist first (idempotent upsert)
    for profile_id in profile_pool:
        payload = make_context(profile_id, args.tenant_id)
        _post_with_retry(
            url_context,
            payload,
            retries=args.retry,
            backoff_sec=args.backoff_sec,
            timeout=args.timeout_sec,
        )
        progress.contexts += 1

    while cursor < args.count:
        end = min(cursor + args.batch_size, args.count)
        events: List[Dict[str, Any]] = []
        for i in range(cursor, end):
            profile_id = profile_pool[i % len(profile_pool)]
            events.append(make_event(profile_id, args.tenant_id, i))
        try:
            _post_with_retry(
                url_events,
                {"events": events},
                retries=args.retry,
                backoff_sec=args.backoff_sec,
                timeout=args.timeout_sec,
            )
            cursor = end
            progress.done = cursor
        except RuntimeError as ex:
            failed.append({"start": cursor, "end": end, "error": str(ex)})
            progress.failed = len(failed)
            cursor = end
        _checkpoint_save(checkpoint_path, {"cursor": cursor, "failed": failed})
        print(
            f"[seed] done={progress.done}/{args.count} "
            f"contexts={progress.contexts} failed_batches={progress.failed}"
        )
        time.sleep(args.delay_sec)

    print("Finished.")
    print(
        json.dumps(
            {
                "generated": progress.done,
                "contexts_upserted": progress.contexts,
                "failed_batches": progress.failed,
                "checkpoint": str(checkpoint_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
