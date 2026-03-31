# Aha Hook Event Spec (MVP)

This document defines `hook_variant_id` and event instrumentation rules for replayable A/B analysis.

## 1) `hook_variant_id` format

Use this canonical format:

`{topic_key}:{hook_type}:{variant}:{content_rev}`

Examples:

- `function_composition:analogy:A:r1`
- `probability_combination:visual:B:r3`
- `word_roots:story:C:r2`

Rules:

- `topic_key`: snake_case key from curriculum taxonomy.
- `hook_type`: one of `analogy|story|visual|misconception_fix|exam_shortcut`.
- `variant`: A/B/C... for experiment arm.
- `content_rev`: `r{number}` increments whenever hook wording changes.

Do not reuse old `content_rev` after content changes.

## 2) Required event sequence

For each question flow, emit events in this order when possible:

1. `confused` (optional, if learner explicitly reports confusion)
2. `hint_shown` (required when a hook is shown)
3. `aha_reported` (optional, learner self-report)
4. `question_answered` (required if an answer is submitted)
5. `review_passed` (optional, for delayed retention checks)

`question_corrected` can be emitted when user moves from incorrect to correct after a hint.

## 3) Required fields by event

Common required fields:

- `tenant_id`
- `profile_id`
- `topic_key`
- `event_type`
- `metadata.session_id`
- `metadata.client_ts` (ISO-8601 string)

Event-specific requirements:

- `hint_shown`: must include `hook_id` and `hook_variant_id`.
- `aha_reported`: should include `latency_ms` from hint exposure.
- `question_answered`: must include `is_correct` and `question_id`.
- `review_passed`: should include `metadata.review_day` (e.g. `d1`, `d7`).

## 4) Metadata contract

Recommended `metadata` keys:

- `session_id`: trace a single learning session.
- `attempt_id_client`: client-side attempt id for replay joins.
- `client_ts`: original client timestamp.
- `surface`: `lab|exam|knowledge|handout`.
- `ui_lang`: UI language, e.g. `zh-TW`.
- `used_hook`: boolean for `question_answered`.
- `answer_latency_ms`: answer duration.
- `source_question_bank`: optional question bank identifier.

Keep metadata flat when possible to simplify SQL querying.

## 5) Replayability guarantees

To guarantee replayable experiments:

- Every `hint_shown` must carry immutable `hook_variant_id`.
- `question_answered` must include the same `hook_variant_id` when a hook was used.
- If no hook was used, set `hook_variant_id = null`.
- Do not mutate historical events; append correction events instead.

## 6) A/B analysis minimum sample guardrail

Before promoting a variant for a segment (`age_band`, `region_code`):

- impressions >= 50
- and `aha_rate` delta >= 0.05 against current baseline
- and no negative `lift` in `question_answered` correctness

If guardrails are not met, keep exploration traffic on multiple variants.
