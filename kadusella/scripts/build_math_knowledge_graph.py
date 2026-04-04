#!/usr/bin/env python3
"""
Build unified math knowledge graph JSON from existing CONCEPTS dictionaries.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


DEFAULT_REGIONS = ["TW-TPE", "TW-NWT", "TW-TXG", "TW-TNN", "TW-KHH", "HK", "SG"]
DEFAULT_AGE_BANDS = ["13_15", "16_18", "19_22", "23_plus"]


def load_module_concepts(py_path: Path) -> Dict[str, Dict[str, Any]]:
    spec = importlib.util.spec_from_file_location(py_path.stem, py_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from: {py_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    data = getattr(module, "CONCEPTS", None)
    if not isinstance(data, dict):
        raise RuntimeError(f"CONCEPTS dict missing in: {py_path}")
    return data


def _stable_ascii_token(text: str, prefix: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{digest}"


def _extract_summary(md_text: str) -> str:
    for raw in md_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        if line.startswith("---"):
            continue
        line = re.sub(r"^\-\s*", "", line).strip()
        if line:
            return line[:140]
    return ""


def _extract_formula(md_text: str) -> str:
    candidates = re.findall(r"\$([^$]{1,120})\$", md_text)
    for c in candidates:
        stripped = c.strip()
        if len(stripped) >= 5:
            return stripped
    return candidates[0].strip() if candidates else ""


def _parse_unit_label(unit_name: str) -> Tuple[int, str]:
    m = re.match(r"^\s*(\d+)\s*(.*)$", unit_name)
    if not m:
        return 0, unit_name.strip()
    num = int(m.group(1))
    title = (m.group(2) or "").strip()
    return num, title or unit_name.strip()


def _infer_level_by_order(order: int) -> int:
    if order <= 10:
        return 1
    if order <= 25:
        return 2
    if order <= 40:
        return 3
    return 4


def _extract_related_unit_numbers(md_text: str) -> List[int]:
    marker = "## 延伸"
    idx = md_text.find(marker)
    if idx < 0:
        return []
    tail = md_text[idx:]
    nums = re.findall(r"(?:^|\D)(\d{1,3})(?=\D|$)", tail)
    out: List[int] = []
    for n in nums:
        v = int(n)
        if v not in out:
            out.append(v)
    return out


def _extract_related_names(md_text: str) -> List[str]:
    """Extract concept names (not just numbers) from the 延伸 section."""
    marker = "## 延伸"
    idx = md_text.find(marker)
    if idx < 0:
        return []
    tail = md_text[idx:]
    names: List[str] = []
    for m in re.finditer(r"\*\*(.+?)\*\*", tail):
        raw = re.sub(r"^\d+\s*", "", m.group(1)).strip()
        if raw and len(raw) >= 2:
            names.append(raw)
    return names


# Curriculum-level chapter ordering: each chapter's first unit depends on
# foundational concepts from earlier chapters.
_CHAPTER_PROGRESSION = [
    "方程",
    "不等式",
    "函數",
    "三角",
    "數列",
    "向量",
    "機率計數",
]


def load_math_notes_concepts(
    notes_root: Path,
) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    """Returns (concepts_dict, structural_edges).

    structural_edges are generated here because we have full topology knowledge:
      1. intra-chapter sequential: unit N-1 → unit N
      2. cross-chapter bridges: last of chapter A → first of chapter B
      3. explicit cross-references from 延伸 section (global lookup)
    """
    if not notes_root.is_dir():
        raise RuntimeError(f"notes root not found: {notes_root}")

    note_paths = sorted(notes_root.glob("*/*/note.md"))

    # Global order→key map (units use a global numbering 01-52).
    global_order_to_key: Dict[int, str] = {}
    chapter_to_units: Dict[str, Dict[int, str]] = {}
    key_to_title: Dict[str, str] = {}
    title_to_key: Dict[str, str] = {}

    concepts: Dict[str, Dict[str, Any]] = {}

    # First pass: build topology maps.
    for note_path in note_paths:
        chapter = note_path.parent.parent.name
        unit_name = note_path.parent.name
        order, title = _parse_unit_label(unit_name)
        chapter_token = _stable_ascii_token(chapter, "ch")
        key = (
            f"ma_{chapter_token}_{order:03d}"
            if order > 0
            else f"ma_{chapter_token}_{_stable_ascii_token(unit_name, 'u')}"
        )
        chapter_to_units.setdefault(chapter, {})
        if order > 0:
            chapter_to_units[chapter][order] = key
            global_order_to_key[order] = key
        key_to_title[key] = title
        title_to_key[title] = key

    # Second pass: read content, materialize concepts.
    for note_path in note_paths:
        chapter = note_path.parent.parent.name
        unit_name = note_path.parent.name
        order, title = _parse_unit_label(unit_name)
        chapter_token = _stable_ascii_token(chapter, "ch")
        key = (
            f"ma_{chapter_token}_{order:03d}"
            if order > 0
            else f"ma_{chapter_token}_{_stable_ascii_token(unit_name, 'u')}"
        )
        text = note_path.read_text(encoding="utf-8")
        summary = _extract_summary(text)
        formula = _extract_formula(text)
        concepts[key] = {
            "title": title,
            "summary": summary,
            "detail": text[:5000],
            "level": _infer_level_by_order(order),
            "formula": formula,
            "_chapter": chapter,
            "_order": order,
            "_related_numbers": _extract_related_unit_numbers(text),
            "_related_names": _extract_related_names(text),
        }

    # --- Edge generation (the actual "graph" part) ---
    edges: List[Dict[str, Any]] = []
    edge_set: set = set()

    def _add(src: str, dst: str, etype: str, w: float, ev: str) -> None:
        if src == dst:
            return
        triple = (src, dst, etype)
        if triple in edge_set:
            return
        edge_set.add(triple)
        edges.append({"from": src, "to": dst, "type": etype, "weight": w, "evidence": ev})

    # 1) Intra-chapter sequential: unit N → unit N+1.
    for chapter, units in chapter_to_units.items():
        orders = sorted(units.keys())
        for i in range(len(orders) - 1):
            _add(units[orders[i]], units[orders[i + 1]], "prerequisite", 1.0, "sequential_within_chapter")

    # 2) Cross-chapter bridge: last unit of chapter A → first unit of chapter B.
    ordered_chapters = [
        ch for ch in _CHAPTER_PROGRESSION if ch in chapter_to_units
    ]
    for i in range(len(ordered_chapters) - 1):
        ch_from = ordered_chapters[i]
        ch_to = ordered_chapters[i + 1]
        last_order = max(chapter_to_units[ch_from].keys())
        first_order = min(chapter_to_units[ch_to].keys())
        _add(
            chapter_to_units[ch_from][last_order],
            chapter_to_units[ch_to][first_order],
            "prerequisite",
            0.7,
            "chapter_progression_bridge",
        )

    # 3) Explicit cross-references from 延伸 (global lookup by number and name).
    for key, data in concepts.items():
        for num in data.get("_related_numbers") or []:
            target = global_order_to_key.get(num)
            if target:
                _add(key, target, "prerequisite", 0.8, "explicit_延伸_number")
        for name in data.get("_related_names") or []:
            target = title_to_key.get(name)
            if target:
                _add(key, target, "analogy_bridge", 0.6, "explicit_延伸_name")

    # 4) Exam co-occurrence: units at similar positions across chapters.
    for key, data in concepts.items():
        order = data.get("_order", 0)
        if order <= 0:
            continue
        for other_key, other_data in concepts.items():
            if other_key == key:
                continue
            o2 = other_data.get("_order", 0)
            if o2 <= 0:
                continue
            if data.get("_chapter") == other_data.get("_chapter"):
                continue
            if abs(order - o2) <= 2:
                _add(key, other_key, "exam_cooccurrence", 0.4, "similar_curriculum_position")

    return concepts, edges


_CHAPTER_SUBDOMAIN_MAP: Dict[str, str] = {
    "函數": "functions_equations",
    "方程": "functions_equations",
    "不等式": "functions_equations",
    "三角": "trigonometry",
    "向量": "linear_algebra",
    "矩陣": "linear_algebra",
    "數列": "sequences_series",
    "機率計數": "probability_statistics",
    "機率": "probability_statistics",
    "統計": "probability_statistics",
    "排列組合": "probability_statistics",
    "幾何": "geometry",
    "空間": "geometry",
    "座標": "geometry",
    "微積分": "calculus_analysis",
    "極限": "calculus_analysis",
    "複數": "complex_numbers",
}


def infer_subdomain(key: str, chapter_hint: str = "") -> str:
    if chapter_hint:
        for pattern, sub in _CHAPTER_SUBDOMAIN_MAP.items():
            if pattern in chapter_hint:
                return sub
    text = key.lower()
    if "prob" in text or "random" in text:
        return "probability_statistics"
    if "matrix" in text or "vector" in text or "plane" in text:
        return "linear_algebra"
    if "calculus" in text or "derivative" in text or "limit" in text:
        return "calculus_analysis"
    if "trig" in text:
        return "trigonometry"
    if "complex" in text:
        return "complex_numbers"
    if "geo" in text or "spatial" in text:
        return "geometry"
    if "quadratic" in text or "func" in text or "poly" in text or "log" in text:
        return "functions_equations"
    return "general_math_foundations"


def infer_scope(source: str, level: int, key: str) -> tuple[str, List[str]]:
    tags = ["數學"]
    if source == "knowledge_notes_math":
        tags.append("學測")
        tags.append("進階" if level >= 2 else "基礎")
        if level >= 3:
            tags.append("分科")
        return "學測", sorted(set(tags))
    if source == "gsat_math_adv":
        tags.extend(["分科", "進階"])
        if "calculus" in key or "complex" in key:
            tags.append("高等")
        return "分科", sorted(set(tags))
    if source == "gsat_math":
        tags.append("學測")
        if level <= 1:
            tags.append("基礎")
        else:
            tags.append("進階")
        return "學測", sorted(set(tags))
    if level >= 4:
        tags.extend(["高等", "進階"])
        return "高等", sorted(set(tags))
    if level <= 1:
        tags.append("基礎")
        return "基礎", sorted(set(tags))
    tags.append("進階")
    return "進階", sorted(set(tags))


def build_history_stub(key: str, title: str) -> Dict[str, Any]:
    return {
        "era": "to_be_filled",
        "origin_people": [],
        "origin_problem": f"{title} 的原始歷史問題脈絡待補充",
        "timeline_events": [],
        "notes": f"auto_stub_for_{key}",
    }


def build_aha_stub(key: str, title: str) -> List[Dict[str, Any]]:
    base = key.replace(":", "_")
    return [
        {
            "trigger_id": f"{base}:analogy:A:r1",
            "variant_id": f"{base}:analogy:A:r1",
            "hook_type": "analogy",
            "target_profiles": {
                "age_band": DEFAULT_AGE_BANDS,
                "region_code": DEFAULT_REGIONS,
            },
            "prompt": f"請以生活化比喻說明「{title}」的核心結構，避免口語贅字。",
            "expected_shift": "從公式記憶轉成結構理解",
            "success_signals": ["aha_reported", "question_answered.is_correct=true"],
        },
        {
            "trigger_id": f"{base}:misconception_fix:B:r1",
            "variant_id": f"{base}:misconception_fix:B:r1",
            "hook_type": "misconception_fix",
            "target_profiles": {
                "age_band": DEFAULT_AGE_BANDS,
                "region_code": DEFAULT_REGIONS,
            },
            "prompt": f"請條列「{title}」之常見誤解，並各附簡短反例或修正說明。",
            "expected_shift": "修正錯誤心智模型",
            "success_signals": ["question_corrected", "question_answered.is_correct=true"],
        },
        {
            "trigger_id": f"{base}:cold_fact:C:r1",
            "variant_id": f"{base}:cold_fact:C:r1",
            "hook_type": "cold_fact",
            "target_profiles": {
                "age_band": DEFAULT_AGE_BANDS,
                "region_code": DEFAULT_REGIONS,
            },
            "prompt": f"請提供與「{title}」相關之簡要史實或背景知識（須可核實、避免軼聞堆砌）。",
            "expected_shift": "提升注意力與記憶黏性",
            "success_signals": ["hint_shown", "aha_reported"],
        },
    ]


def build_representations_stub(title: str) -> List[Dict[str, Any]]:
    return [
        {"format": "text", "content": f"{title} 的文字直覺解釋"},
        {"format": "visual", "content": f"{title} 的圖像化表示方式"},
        {"format": "example", "content": f"{title} 的考題型例題"},
        {"format": "counterexample", "content": f"{title} 的反例與陷阱"},
    ]


def to_node(key: str, data: Dict[str, Any], source: str) -> Dict[str, Any]:
    title = str(data.get("title") or key)
    level = int(data.get("level", 0))
    chapter_hint = str(data.get("_chapter") or "")
    subdomain = infer_subdomain(key, chapter_hint=chapter_hint)
    scope_primary, scope_tags = infer_scope(source, level, key)
    return {
        "id": key,
        "source": source,
        "domain": "math",
        "scope_primary": scope_primary,
        "scope_tags": scope_tags,
        "subdomain": subdomain,
        "title": title,
        "summary": str(data.get("summary") or ""),
        "detail": str(data.get("detail") or ""),
        "level": level,
        "formula": str(data.get("formula") or ""),
        "tags": [subdomain, scope_primary, source],
        "difficulty": "advanced" if level >= 3 else "intermediate" if level == 2 else "basic",
        "exam_relevance": 90 if level >= 2 else 70,
        "history_origin": build_history_stub(key, title),
        "cold_knowledge": [f"{title} 的冷知識待補充（歷史、跨域、反直覺案例）"],
        "aha_triggers": build_aha_stub(key, title),
        "representations": build_representations_stub(title),
        "misconceptions": [f"{title} 常見誤解待補充"],
        "assessment_probes": [
            {
                "probe_id": f"{key}:probe:1",
                "question": f"如何用自己的話解釋 {title}？",
                "answer_mode": "short_text",
            }
        ],
    }


def to_edges_legacy(key: str, data: Dict[str, Any]) -> List[Dict[str, Any]]:
    edges: List[Dict[str, Any]] = []
    for parent in data.get("parents") or []:
        edges.append(
            {
                "from": parent,
                "to": key,
                "type": "prerequisite",
                "weight": 1.0,
                "evidence": "from_concepts_parents_field",
            }
        )
    return edges


def dedupe_nodes(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for node in nodes:
        by_id[node["id"]] = node
    return list(by_id.values())


def merge_graphs(
    concept_sources: List[Tuple[str, Dict[str, Dict[str, Any]]]],
    structural_edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = list(structural_edges)
    for source_name, concepts in concept_sources:
        for key, data in concepts.items():
            nodes.append(to_node(key, data, source=source_name))
            edges.extend(to_edges_legacy(key, data))

    node_ids = {n["id"] for n in nodes}
    valid_edges = [e for e in edges if e["from"] in node_ids and e["to"] in node_ids]
    unique_edges = {(e["from"], e["to"], e["type"]): e for e in valid_edges}
    merged_nodes = dedupe_nodes(nodes)
    subdomains = sorted(
        {str(n.get("subdomain")) for n in merged_nodes if str(n.get("subdomain", "")).strip()}
    )
    scopes = sorted(
        {
            tag
            for n in merged_nodes
            for tag in (n.get("scope_tags") or [])
            if str(tag).strip()
        }
    )
    scope_subdomains: Dict[str, List[str]] = {}
    for scope in scopes:
        subs = sorted(
            {
                str(n.get("subdomain"))
                for n in merged_nodes
                if scope in (n.get("scope_tags") or [])
            }
        )
        scope_subdomains[scope] = subs
    return {
        "graph_version": "1.0.0",
        "domain": "math",
        "curriculum": "gsat+advanced",
        "nodes": merged_nodes,
        "edges": list(unique_edges.values()),
        "taxonomy": {
            "age_bands": DEFAULT_AGE_BANDS,
            "regions": DEFAULT_REGIONS,
            "scopes": scopes,
            "subdomains": subdomains,
            "scope_subdomains": scope_subdomains,
        },
    }


def _graph_topology(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute real graph topology metrics."""
    node_ids = {n["id"] for n in nodes}
    adj: Dict[str, List[str]] = {nid: [] for nid in node_ids}
    in_degree: Dict[str, int] = {nid: 0 for nid in node_ids}
    out_degree: Dict[str, int] = {nid: 0 for nid in node_ids}
    edge_types: Dict[str, int] = {}

    for e in edges:
        src, dst = e["from"], e["to"]
        if src in node_ids and dst in node_ids:
            adj[src].append(dst)
            out_degree[src] += 1
            in_degree[dst] += 1
            etype = e.get("type", "unknown")
            edge_types[etype] = edge_types.get(etype, 0) + 1

    # Connected components (undirected).
    undirected: Dict[str, set] = {nid: set() for nid in node_ids}
    for e in edges:
        src, dst = e["from"], e["to"]
        if src in node_ids and dst in node_ids:
            undirected[src].add(dst)
            undirected[dst].add(src)
    visited: set = set()
    components = 0
    for nid in node_ids:
        if nid in visited:
            continue
        components += 1
        stack = [nid]
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            stack.extend(undirected[cur] - visited)

    # Orphan nodes (zero edges).
    orphans = sum(1 for nid in node_ids if in_degree[nid] == 0 and out_degree[nid] == 0)

    # Longest prerequisite chain (DAG longest path via BFS/topological).
    prereq_adj: Dict[str, List[str]] = {nid: [] for nid in node_ids}
    for e in edges:
        if e.get("type") == "prerequisite" and e["from"] in node_ids and e["to"] in node_ids:
            prereq_adj[e["from"]].append(e["to"])
    depth: Dict[str, int] = {}
    def _depth(nid: str, seen: set) -> int:
        if nid in depth:
            return depth[nid]
        if nid in seen:
            return 0
        seen.add(nid)
        d = 0
        for child in prereq_adj.get(nid, []):
            d = max(d, 1 + _depth(child, seen))
        depth[nid] = d
        return d
    for nid in node_ids:
        _depth(nid, set())
    longest_chain = max(depth.values()) if depth else 0

    # Cross-chapter edges count.
    node_subdomain = {n["id"]: n.get("subdomain", "") for n in nodes}
    cross_subdomain_edges = sum(
        1 for e in edges
        if node_subdomain.get(e["from"], "") != node_subdomain.get(e["to"], "")
        and e["from"] in node_ids and e["to"] in node_ids
    )

    n = len(node_ids)
    avg_degree = (sum(in_degree.values()) + sum(out_degree.values())) / n if n > 0 else 0

    return {
        "node_count": n,
        "edge_count": len(edges),
        "edge_types": edge_types,
        "avg_degree": round(avg_degree, 2),
        "connected_components": components,
        "orphan_nodes": orphans,
        "longest_prerequisite_chain": longest_chain,
        "cross_subdomain_edges": cross_subdomain_edges,
        "subdomain_count": len({n.get("subdomain") for n in nodes}),
    }


def compute_quality(graph: Dict[str, Any]) -> Dict[str, Any]:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    topo = _graph_topology(nodes, edges)

    n = topo["node_count"]
    e = topo["edge_count"]

    # Graph-structural quality score (not content-completeness).
    score = 0.0
    score += min(20.0, (n / 50.0) * 20.0)
    score += min(20.0, (e / 100.0) * 20.0)
    score += min(15.0, (topo["longest_prerequisite_chain"] / 8.0) * 15.0)
    score += max(0.0, 15.0 - topo["orphan_nodes"] * 3.0)
    score += min(10.0, (1.0 / max(topo["connected_components"], 1)) * 10.0)
    score += min(10.0, (topo["cross_subdomain_edges"] / 20.0) * 10.0)
    score += min(10.0, (topo["subdomain_count"] / 5.0) * 10.0)

    return {
        "functionality": 1,
        "technical_level": round(score, 2),
        "technical_level_min_required": 60.0,
        "humanized_beautiful_structure_baseline": 60.0,
        "topology": topo,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build unified math knowledge graph")
    ap.add_argument(
        "--mathpath-db",
        default="",
        help="Optional path to legacy mathpath database.py",
    )
    ap.add_argument(
        "--gsat-math-db",
        default="",
        help="Optional path to legacy GSAT advanced math db",
    )
    ap.add_argument(
        "--gsat-basic-db",
        default="",
        help="Optional path to legacy GSAT basic math db",
    )
    ap.add_argument(
        "--notes-root",
        default="知識/數學",
        help="Path to math notes root (default: 知識/數學)",
    )
    ap.add_argument(
        "--out",
        default="docs/samples/math_knowledge_graph_v1.json",
        help="Output graph JSON path",
    )
    ap.add_argument(
        "--min-technical-level",
        type=float,
        default=60.0,
        help="Minimum technical level required",
    )
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[2]
    notes_root = (root / args.notes_root).resolve()
    out_path = (root / args.out).resolve()

    concept_sources: List[Tuple[str, Dict[str, Dict[str, Any]]]] = []
    notes_concepts, structural_edges = load_math_notes_concepts(notes_root)
    concept_sources.append(("knowledge_notes_math", notes_concepts))

    # Legacy references are optional: keep compatibility, but do not require them in repo.
    legacy_inputs = [
        ("mathpath", args.mathpath_db),
        ("gsat_math", args.gsat_basic_db),
        ("gsat_math_adv", args.gsat_math_db),
    ]
    for source_name, rel in legacy_inputs:
        rel = (rel or "").strip()
        if not rel:
            continue
        p = (root / rel).resolve()
        if p.is_file():
            concept_sources.append((source_name, load_module_concepts(p)))
        else:
            print(f"skip missing optional source: {p}")

    graph = merge_graphs(concept_sources, structural_edges)
    quality = compute_quality(graph)
    quality["technical_level_min_required"] = float(args.min_technical_level)
    graph["quality_gate"] = quality
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    topo = quality.get("topology", {})
    print(f"written: {out_path}")
    print(f"nodes={topo.get('node_count',0)} edges={topo.get('edge_count',0)}")
    print(f"  edge_types: {topo.get('edge_types',{})}")
    print(f"  longest_prerequisite_chain: {topo.get('longest_prerequisite_chain',0)}")
    print(f"  connected_components: {topo.get('connected_components',0)}  orphans: {topo.get('orphan_nodes',0)}")
    print(f"  cross_subdomain_edges: {topo.get('cross_subdomain_edges',0)}  subdomains: {topo.get('subdomain_count',0)}")
    print(f"  avg_degree: {topo.get('avg_degree',0)}")
    print(f"graph_quality_score={quality['technical_level']} required>={args.min_technical_level}")
    if float(quality["technical_level"]) < float(args.min_technical_level):
        print("quality gate FAILED — graph needs more edges or connectivity")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
