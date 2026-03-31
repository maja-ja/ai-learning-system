#!/usr/bin/env python3
"""
將示範資料寫入本機 SQLite（backend/local.db）。

用法（專案根目錄）:
  代碼制（僅 knowledge）：--cmd g30 / --cmd w0 / --cmd a10 / --cmd 25
  或明確旗標：
  python backend/generate_demo_data.py --only knowledge --wipe-knowledge --knowledge 30
  僅刪舊：python backend/generate_demo_data.py --cmd w0

代碼：gN=刪舊+寫N（g0=僅刪）　w0/w=僅刪舊　aN=只加N筆　純數字N 同 gN（N>0）　?=顯示規則。
--wipe-knowledge：在寫入前清空 knowledge 表。
未清空時：新詞撞名會自動加「（2）」「（3）」…。
"""
from __future__ import annotations

import argparse
import random
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set, Tuple

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend import database as db
from backend.knowledge_cmd import KNOWLEDGE_CMD_RULES, parse_knowledge_cmd

DEMO_TENANT = "demo-tenant"
HOOK_NS = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/ai-learning-system/demo-hooks")

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

HOOK_SPECS: Sequence[Tuple[str, str]] = (
    ("analogy", "A"),
    ("visual", "B"),
    ("misconception_fix", "C"),
    ("exam_shortcut", "D"),
    ("story", "E"),
)

AGE_BANDS = ["under_13", "13_15", "16_18", "19_22", "23_plus"]
REGIONS = ["TW-TPE", "TW-NWT", "TW-TXG", "TW-TNN", "TW-KHH"]

KNOWLEDGE_SEEDS = [
    ("梯度下降", "機器學習", "沿負梯度逐步降低損失"),
    ("貝氏定理", "機率", "先驗與似然更新為後驗"),
    ("向量內積", "線代", "幾何投影與夾角餘弦"),
    ("泰勒展開", "微積分", "局部多項式逼近平滑函數"),
    ("特徵值", "線代", "線性變換的主軸與伸縮量"),
    ("過擬合", "機器學習", "訓練誤差低但泛化差"),
    ("正則化", "機器學習", "懲罰過大權重以換泛化"),
    ("注意力機制", "深度學習", "依查詢對鍵值加權彙整"),
    ("RAG", "應用", "檢索文件再生成答案"),
    ("大數法則", "機率", "樣本平均收斂期望值"),
]


def _hook_id(tenant: str, topic: str, hook_type: str, variant: str) -> str:
    return str(uuid.uuid5(HOOK_NS, f"{tenant}|{topic}|{hook_type}|{variant}"))


def _profile_id(i: int) -> str:
    return f"demo-profile-{i:04d}"


def _unique_word(base: str, taken: Set[str]) -> str:
    w = base.strip()
    if not w:
        w = "示範詞條"
    if w not in taken:
        return w
    k = 2
    while True:
        cand = f"{w}（{k}）"
        if cand not in taken:
            return cand
        k += 1


def gen_knowledge(rng: random.Random, n: int) -> None:
    taken: Set[str] = {
        str(row.get("word") or "").strip()
        for row in db.knowledge_list()
        if str(row.get("word") or "").strip()
    }
    base = list(KNOWLEDGE_SEEDS)
    rng.shuffle(base)
    for i in range(n):
        if i < len(KNOWLEDGE_SEEDS):
            raw_word, category, roots = base[i]
        else:
            raw_word = f"示範概念_{i+1}"
            category = rng.choice(["數學", "物理", "資訊", "語言"])
            roots = f"示範根因說明 #{i+1}"
        word = _unique_word(raw_word, taken)
        taken.add(word)
        rec: Dict[str, Any] = {
            "word": word,
            "category": category,
            "roots": roots,
            "breakdown": f"拆解：{word} 可視為 {roots} 的具體化。",
            "definition": f"{word}：簡短直覺定義（示範資料）。",
            "meaning": "本質上是在練習「把抽象講成可操作的步驟」。",
            "native_vibe": "專家會先畫圖或舉小例子，再寫公式。",
            "example": f"例：當輸入為 x 時，先檢查 {category} 邊界條件。",
            "synonym_nuance": "與相近詞差在適用情境與假設強弱。",
            "usage_warning": "勿把示範內容當正式教材唯一來源。",
            "memory_hook": f"記：{word[:4]}…像「{category}」的門牌。",
            "phonetic": "",
        }
        db.knowledge_upsert(rec)
    print(f"[demo] knowledge: 寫入 {n} 筆（word 彼此不重複且不與寫入前資料庫重複）")


def gen_notes(rng: random.Random, n: int) -> None:
    for i in range(n):
        title = f"示範筆記 {i+1}"
        body = "段落一：複習重點。\n段落二：待釐清問題。\n"
        body += f"隨機碼 {rng.randint(1000, 9999)}（可刪）"
        tags = ",".join(rng.sample(["demo", "math", "review", "scratch"], k=2))
        db.notes_create(title, body, tags)
    print(f"[demo] notes: 新增 {n} 筆")


def gen_learner_contexts(rng: random.Random, tenant: str, profiles: int) -> None:
    for i in range(profiles):
        db.learner_context_upsert(
            {
                "tenant_id": tenant,
                "profile_id": _profile_id(i),
                "age_band": rng.choice(AGE_BANDS),
                "region_code": rng.choice(REGIONS),
                "preferred_language": "zh-TW",
                "metadata": {"source": "generate_demo_data"},
            }
        )
    print(f"[demo] learner_contexts: upsert {profiles} 筆")


def gen_aha_hooks(tenant: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for topic in TOPICS:
        for hook_type, variant in HOOK_SPECS:
            hid = _hook_id(tenant, topic, hook_type, variant)
            title = f"[{variant}] {topic.replace('_', ' ')}"
            text = (
                f"示範 hook：{hook_type}。"
                " 把主題想成「先找模式再驗算」的小步驟。"
            )
            row = db.aha_hook_upsert(
                {
                    "id": hid,
                    "tenant_id": tenant,
                    "created_by": None,
                    "topic_key": topic,
                    "hook_type": hook_type,
                    "hook_variant_id": variant,
                    "hook_title": title,
                    "hook_text": text,
                    "difficulty_band": "basic",
                    "region_tags": ["TW"],
                    "age_tags": ["16_18", "19_22"],
                    "is_active": True,
                    "metadata": {"demo": True},
                }
            )
            rows.append(row)
    print(f"[demo] aha_hooks: upsert {len(rows)} 筆")
    return rows


def gen_aha_events(
    rng: random.Random,
    tenant: str,
    profiles: int,
    events_per_profile: int,
    hooks: List[Dict[str, Any]],
) -> None:
    if not hooks:
        print("[demo] aha_events: 略過（無 hooks）")
        return
    by_topic: Dict[str, List[Dict[str, Any]]] = {}
    for h in hooks:
        tk = str(h.get("topic_key", ""))
        by_topic.setdefault(tk, []).append(h)

    event_types_cycle: List[Tuple[str, Dict[str, Any]]] = [
        ("hint_shown", {}),
        ("question_answered", {"is_correct": True}),
        ("aha_reported", {"self_report_delta": 1, "latency_ms": 1200}),
    ]

    total = 0
    for p in range(profiles):
        pid = _profile_id(p)
        for _ in range(events_per_profile):
            topic = rng.choice(TOPICS)
            pool = by_topic.get(topic) or hooks
            hook = rng.choice(pool)
            hook_id = str(hook.get("id", ""))
            variant = str(hook.get("hook_variant_id", ""))
            etype, extra = rng.choice(event_types_cycle)
            payload: Dict[str, Any] = {
                "tenant_id": tenant,
                "profile_id": pid,
                "event_type": etype,
                "topic_key": topic,
                "hook_id": hook_id,
                "hook_variant_id": variant,
                "question_id": f"q-{uuid.uuid4().hex[:8]}",
                "metadata": {"demo": True},
                **extra,
            }
            if etype == "hint_shown":
                payload["is_correct"] = None
            db.aha_event_insert(payload)
            total += 1
    print(f"[demo] aha_events: 新增 {total} 筆")


def parse_only(raw: str | None) -> Set[str]:
    if not raw or raw.strip().lower() == "all":
        return {"knowledge", "notes", "learner", "aha"}
    parts = {p.strip().lower() for p in raw.split(",") if p.strip()}
    aliases = {"ctx": "learner", "contexts": "learner", "hooks": "aha", "events": "aha"}
    out: Set[str] = set()
    for p in parts:
        out.add(aliases.get(p, p))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="寫入 backend/local.db 示範資料")
    ap.add_argument("--tenant-id", default=DEMO_TENANT, help="tenant_id（預設 demo-tenant）")
    ap.add_argument("--seed", type=int, default=42, help="亂數種子")
    ap.add_argument("--only", default="all", help="逗號分隔：knowledge,notes,learner,aha 或 all")
    ap.add_argument("--knowledge", type=int, default=12, help="知識卡筆數（0 = 可不寫入）")
    ap.add_argument(
        "--wipe-knowledge",
        action="store_true",
        help="處理知識卡前刪除 knowledge 表全部舊資料",
    )
    ap.add_argument(
        "--cmd",
        metavar="CODE",
        default=None,
        help="代碼制（gN/w0/aN/純數字/?）；? 僅印規則後結束；指定後僅執行 knowledge",
    )
    ap.add_argument("--notes", type=int, default=5, help="筆記新增筆數")
    ap.add_argument("--profiles", type=int, default=8, help="示範 learner profile 數")
    ap.add_argument("--events-per-profile", type=int, default=6, help="每位 profile 的 aha 事件數")
    args = ap.parse_args()

    cmd_knowledge_only = False
    if args.cmd is not None:
        if args.cmd.strip() == "?":
            print(KNOWLEDGE_CMD_RULES)
            return
        try:
            pc = parse_knowledge_cmd(args.cmd)
        except ValueError as e:
            ap.error(str(e))
        if pc is None:
            ap.error("--cmd 無效或為空；僅刪舊請用 w0 或 g0")
        args.wipe_knowledge = pc.wipe_first
        args.knowledge = pc.insert_n
        cmd_knowledge_only = True

    if args.knowledge < 0:
        ap.error("--knowledge 不可為負數")

    db.init_schema()
    rng = random.Random(args.seed)
    want = parse_only(args.only)
    if cmd_knowledge_only:
        print("[demo] 已套用 --cmd，僅處理 knowledge。")
        want = {"knowledge"}

    if "knowledge" in want:
        if args.wipe_knowledge:
            removed = db.knowledge_delete_all()
            print(f"[demo] knowledge: 已刪除舊資料（{removed} 筆）")
        if args.knowledge > 0:
            gen_knowledge(rng, args.knowledge)
        elif args.wipe_knowledge:
            print("[demo] knowledge: 僅清空，未寫入新詞條（--knowledge 0）")
    if "notes" in want:
        gen_notes(rng, args.notes)
    if "learner" in want:
        gen_learner_contexts(rng, args.tenant_id, args.profiles)

    hooks: List[Dict[str, Any]] = []
    if "aha" in want:
        hooks = gen_aha_hooks(args.tenant_id)
        gen_aha_events(
            rng,
            args.tenant_id,
            args.profiles,
            args.events_per_profile,
            hooks,
        )

    print(f"[demo] 完成。DB: {db.DB_PATH}")


if __name__ == "__main__":
    main()
