# Math Knowledge Graph Spec (Aha-first)

This spec extends the current `CONCEPTS` structure into a knowledge graph that can drive:

- prerequisite navigation
- historical storytelling
- Aha hook recommendation
- cold-knowledge trigger injection

Domain/range design:

- fixed `domain = math`
- multi-range via `scope_primary` + `scope_tags` (e.g. `學測`, `分科`, `高等`, `基礎`, `進階`, `數學`)
- each node must declare one `subdomain`

Quality gate baseline:

- `functionality = 1`
- `technical_level >= 60`
- `humanized_beautiful_structure_baseline = 60`

## 1) Core entities

- `concept_node`: one concept in the graph.
- `relation_edge`: typed edge between concepts.
- `origin_story`: historical source and timeline facts.
- `aha_trigger`: concrete trigger payloads for different learner profiles.
- `representation_asset`: different explanation modalities (text, visual, analogy, puzzle, etc).
- `assessment_probe`: question/checkpoint items to validate understanding.

## 2) Canonical JSON structure

```json
{
  "graph_version": "1.0.0",
  "domain": "math",
  "curriculum": "gsat+advanced",
  "quality_gate": {
    "functionality": 1,
    "technical_level": 60.0,
    "technical_level_min_required": 60.0,
    "humanized_beautiful_structure_baseline": 60.0
  },
  "nodes": [],
  "edges": [],
  "taxonomy": {
    "age_bands": ["13_15", "16_18", "19_22", "23_plus"],
    "regions": ["TW-TPE", "TW-NWT", "TW-TXG", "TW-TNN", "TW-KHH", "HK", "SG"],
    "scopes": ["數學", "學測", "分科", "高等", "基礎", "進階"],
    "subdomains": ["functions_equations", "trigonometry", "probability_statistics"],
    "scope_subdomains": {
      "學測": ["functions_equations", "trigonometry", "probability_statistics"],
      "分科": ["calculus_analysis", "complex_numbers", "linear_algebra"]
    }
  }
}
```

## 3) `concept_node` fields

- `id`: stable key (e.g. `ma_derivative_logic`)
- `domain`: always `math`
- `scope_primary`: primary range (`學測` / `分科` / `高等` / `基礎` / `進階`)
- `scope_tags`: multi-range tags (must include `數學`)
- `subdomain`: child area inside range
- `title`, `summary`, `detail`
- `level`: depth in conceptual hierarchy
- `formula`: canonical formula string
- `tags`: free tags (`algebra`, `geometry`, `exam_core`, ...)
- `difficulty`: `basic|intermediate|advanced`
- `exam_relevance`: 0-100
- `history_origin`: object
  - `era`: e.g. `17th_century`
  - `origin_people`: list of names
  - `origin_problem`: original problem context
  - `timeline_events`: list of `year + event`
- `cold_knowledge`: list of short facts
- `aha_triggers`: list of trigger payloads
- `representations`: multi-format assets
- `misconceptions`: common mistakes
- `assessment_probes`: diagnostic checks

## 4) `relation_edge` types

- `prerequisite`: A is needed before B
- `historical_influence`: A historically influenced B
- `analogy_bridge`: concept bridge for easier explanation
- `exam_cooccurrence`: often tested together
- `application_to`: concept applies to real-world domain

Each edge includes:

- `from`
- `to`
- `type`
- `weight` (0.0~1.0)
- `evidence`

## 5) Aha trigger payload model

Each `aha_triggers[]` item:

- `trigger_id`: stable ID
- `hook_type`: `analogy|visual|story|misconception_fix|exam_shortcut|cold_fact|counterexample|interactive_sim`
- `target_profiles`: filters by `age_band`, `region_code`, optional `exam_goal`
- `prompt`: content shown to learner
- `expected_shift`: what confusion should be resolved
- `success_signals`: event conditions (e.g. `aha_reported`, `question_answered.is_correct`)
- `variant_id`: versioned arm ID for experimentation

## 6) Minimal data quality rules

- every node must have at least one `prerequisite` or be level-0 root
- every level-2+ node must include at least 2 `aha_triggers`
- every node must include at least 1 `misconception`
- every node must include at least 1 `assessment_probe`
- every node should include at least 1 `cold_knowledge` item

## 7) Mapping from existing `CONCEPTS`

Current fields map as:

- `title` -> `title`
- `summary` -> `summary`
- `detail` -> `detail`
- `level` -> `level`
- `formula` -> `formula`
- `parents` -> `edges(type=prerequisite, from=parent, to=current)`

Additional fields (`history_origin`, `aha_triggers`, `cold_knowledge`, `representations`) are newly added and can be filled by:

1. deterministic templates (first pass)
2. LLM generation with human review (second pass)

## 8) First production target

- primary source: `知識/數學/**/note.md`（repo 內正式知識內容）
- legacy references (`mathpath` / `GSAT-path`) are optional external inputs only
- produce one unified JSON graph
- minimum 100 nodes and 300 edges before recommendation rollout
- ensure `hook_variant_id` aligns with `docs/AHA_HOOK_EVENT_SPEC.md`
