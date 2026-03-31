"""知識庫代碼制：字母代碼 + 數字，供 start.py 與 generate_demo_data 共用。

完整說明見常數 KNOWLEDGE_CMD_RULES；輸入「?」可顯示該段文字。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

KNOWLEDGE_CMD_RULES = """
──────── 知識庫代碼規則（不分大小寫）────────
  N         純數字且 N>0：先刪資料庫舊詞條，再寫入 N 筆示範詞（等同 gN）
  gN        先刪舊，再寫入 N 筆；g0 = 只刪舊、不寫入（可寫 g 20，中間可空白）
  w 或 w0   只刪舊詞條，不寫入
  aN        不刪舊，只追加 N 筆（可寫 a 15）
  Enter     不執行知識庫步驟，直接啟動
  ?         顯示本說明（互動時可重複輸入 ?）
範例：
  python start.py g20
  python start.py w0
  python start.py a15
  python backend/generate_demo_data.py --cmd g10
────────────────────────────────────────
""".strip()


@dataclass(frozen=True)
class KnowledgeCmd:
    wipe_first: bool
    insert_n: int


def parse_knowledge_cmd(text: str) -> KnowledgeCmd | None:
    t = (text or "").strip()
    if not t:
        return None
    if t.isdigit():
        n = int(t)
        if n < 0:
            raise ValueError("數字不可為負。")
        if n == 0:
            return None
        return KnowledgeCmd(wipe_first=True, insert_n=n)
    tl_ns = re.sub(r"\s+", "", t.lower())
    if tl_ns == "w" or tl_ns == "w0":
        return KnowledgeCmd(wipe_first=True, insert_n=0)
    m = re.fullmatch(r"g\s*(\d+)", t, re.IGNORECASE)
    if m:
        return KnowledgeCmd(wipe_first=True, insert_n=int(m.group(1)))
    if re.fullmatch(r"g\s*", t, re.IGNORECASE):
        raise ValueError(
            "「g」後面要加數字。例：g20、g0（僅刪舊）、g 20（中間可空白）。? 顯示規則。"
        )
    m = re.fullmatch(r"a\s*(\d+)", t, re.IGNORECASE)
    if m:
        n = int(m.group(1))
        if n <= 0:
            raise ValueError("a 後須為正整數；僅刪舊請用 w0。")
        return KnowledgeCmd(wipe_first=False, insert_n=n)
    if re.fullmatch(r"a\s*", t, re.IGNORECASE):
        raise ValueError(
            "「a」後面要加數字。例：a10、a 15（追加筆數，不刪舊）。? 顯示規則。"
        )
    if tl_ns == "n":
        raise ValueError(
            "沒有「n」這個代碼。若要「加 N 筆不刪舊」請用 a10；"
            "若要「先刪舊再寫 N 筆」請輸入純數字 20 或 g20。? 顯示規則。"
        )
    raise ValueError(
        "不支援的指令。請用：正整數、g20、w0、a10；? 顯示規則。"
    )


def should_run_knowledge_cmd(cmd: KnowledgeCmd | None) -> bool:
    if cmd is None:
        return False
    return cmd.wipe_first or cmd.insert_n > 0
