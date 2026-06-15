# Process Quality Intelligence V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Completed steps are marked with (`- [x]`).

**Goal:** Generalize Process A spatial quality into a common provider-driven quality evidence system and add Process B residual contamination/uniformity evidence, Agent tools, artifacts, and Active Inspector rendering.

**Architecture:** Process environments keep authoritative scalar QA behavior. Process-specific pure providers generate deterministic explanatory fields and return a common `QualityEvidence` envelope. A registry, common runtime query, generic Agent tool, typed artifact, and built-in UI renderer transport evidence without embedding process physics in MES or UI modules.

**Tech Stack:** Python 3.12, NumPy, dataclasses/typed dictionaries, pytest, FastAPI runtime context, Continue-compatible Agent tools, vanilla JavaScript/CSS.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/environment/process_quality/contracts.py` | Common evidence validation and normalization |
| `src/environment/process_quality/registry.py` | Static A/B provider registry |
| `src/environment/process_quality/process_a.py` | A provider adapter around existing model |
| `src/environment/process_quality/process_b.py` | Pure B cleaning-quality field model |
| `src/environment/process_a_spatial_quality.py` | Backward-compatible A public function |
| `src/environment/process_a_env.py` | A completion evidence compatibility |
| `src/environment/process_b_env.py` | B completion evidence |
| `src/mes/runtime/process_quality_maps.py` | Common and legacy runtime queries |
| `src/mes/agent_runtime/visual_tools.py` | Generic and compatibility Agent tools |
| `src/mes/agent_runtime/visual_artifacts.py` | Generic quality artifact |
| `src/mes/ui/static/control_room.js` | Common process-quality renderer |
| `src/mes/ui/static/control_room.css` | Shared map presentation |
| `tests/test_process_quality_registry.py` | Common contract and registry |
| `tests/test_process_b_spatial_quality.py` | B model and environment evidence |
| `tests/test_mes_process_quality_maps.py` | A/B common query and compatibility |
| `tests/test_mes_agent_tools.py` | Tool and artifact execution |
| `tests/test_mes_visual_artifacts.py` | Generic artifact validation |
| `tests/test_mes_process_chat.py` | UI renderer contract |

### Task 1: Common Contract And Registry

**Files:**
- Create: `tests/test_process_quality_registry.py`
- Create: `src/environment/process_quality/__init__.py`
- Create: `src/environment/process_quality/contracts.py`
- Create: `src/environment/process_quality/registry.py`

- [x] **Step 1: Write failing registry and envelope tests**

Test that A and B providers can be registered and resolved, unknown operations
raise `UNKNOWN_QUALITY_PROVIDER`, and evidence normalization requires identity,
geometry, cells, summary, model, and separate scalar/map verdicts.

- [x] **Step 2: Run the test and confirm missing-module failure**

```bash
.venv/bin/python -m pytest tests/test_process_quality_registry.py -q
```

- [x] **Step 3: Implement `QualityProviderRegistry` and `normalize_quality_evidence`**

The registry exposes:

```python
register(operation_id: str, provider: QualityEvidenceProvider) -> None
get(operation_id: str) -> QualityEvidenceProvider
operations() -> list[str]
```

The normalizer returns a data-only dictionary and raises explicit
`INVALID_QUALITY_EVIDENCE:*` errors for missing required fields.

- [x] **Step 4: Run registry tests**

Expected: PASS.

### Task 2: Migrate Process A Behind The Common Contract

**Files:**
- Create: `src/environment/process_quality/process_a.py`
- Modify: `src/environment/process_a_spatial_quality.py`
- Modify: `src/environment/process_a_env.py`
- Modify: `tests/test_process_a_spatial_quality.py`

- [x] **Step 1: Extend existing A tests with common-envelope assertions**

Assert operation `A`, quality kind `PROCESS_A_SPATIAL_QUALITY`, explicit scalar
and map verdicts, and identical existing cell/summary output.

- [x] **Step 2: Run the focused test and confirm missing common fields**

```bash
.venv/bin/python -m pytest tests/test_process_a_spatial_quality.py -q
```

- [x] **Step 3: Add A provider adapter and compatibility wrapper**

Keep:

```python
generate_process_a_spatial_quality(...)
```

Write both event fields:

```text
spatial_quality_maps
quality_evidence
```

- [x] **Step 4: Run A and registry tests**

```bash
.venv/bin/python -m pytest \
  tests/test_process_a_spatial_quality.py \
  tests/test_process_quality_registry.py -q
```

### Task 3: Process B Cleaning Quality Provider

**Files:**
- Create: `tests/test_process_b_spatial_quality.py`
- Create: `src/environment/process_quality/process_b.py`
- Modify: `src/environment/process_b_env.py`

- [x] **Step 1: Write failing deterministic B model tests**

Cover deterministic output, scalar mean preservation, circular grid, strict B
scalar verdict, local OOS risk, process-specific components, and reason codes.

- [x] **Step 2: Verify failure because the B provider is missing**

```bash
.venv/bin/python -m pytest tests/test_process_b_spatial_quality.py -q
```

- [x] **Step 3: Implement `generate_process_b_quality_evidence`**

Use stable SHA256 seeding and components:

```text
edge_residue
flow_direction_bias
solution_hotspot
local_noise
```

Return evidence type `SIMULATED_CLEANING_QUALITY`, model id
`PROCESS_B_CLEANING_FIELD`, version `1.0.0`.

- [x] **Step 4: Attach B evidence after scalar QA**

Store full evidence in completion events and compact summary/model metadata in
task history. Do not change `qa_result["passed"]`.

- [x] **Step 5: Run B tests**

Expected: PASS.

### Task 4: Common Runtime Query With A Compatibility

**Files:**
- Modify: `tests/test_mes_process_quality_maps.py`
- Modify: `src/mes/runtime/process_quality_maps.py`

- [x] **Step 1: Write failing A/B common query tests**

Cover latest A/B lookup, display-name resolution, explicit operation match,
task lookup, unknown operation, mismatch, and absent evidence.

- [x] **Step 2: Run and confirm `query_process_quality_evidence` is missing**

- [x] **Step 3: Implement the common query**

Read `quality_evidence` first and fall back to legacy
`spatial_quality_maps`. Keep `query_process_a_spatial_quality` as a wrapper
that projects the previous response shape.

- [x] **Step 4: Run runtime query tests**

Expected: PASS.

### Task 5: Generic Agent Tool And Typed Artifact

**Files:**
- Modify: `tests/test_mes_agent_tools.py`
- Modify: `tests/test_mes_visual_artifacts.py`
- Modify: `tests/test_mes_agent_runtime.py`
- Modify: `src/mes/agent_runtime/visual_tools.py`
- Modify: `src/mes/agent_runtime/visual_artifacts.py`

- [x] **Step 1: Write failing common tool/artifact tests**

Required contracts:

```text
tool = query_process_quality_evidence
artifact_type = process_quality_evidence
chart_type = process_quality_map
```

Assert the A compatibility tool and artifact still validate.

- [x] **Step 2: Verify unknown tool/artifact failures**

- [x] **Step 3: Implement common tool and artifact builder**

The artifact stores `quality_evidence`; process-specific semantics remain in
structured `quality_kind`, components, labels, and reason codes.

- [x] **Step 4: Compact common evidence before the second LLM turn**

Remove artifact bodies and cells while retaining summary, components, reasons,
identity, and `cell_count`.

- [x] **Step 5: Run Agent/artifact tests**

```bash
.venv/bin/python -m pytest \
  tests/test_mes_agent_tools.py \
  tests/test_mes_visual_artifacts.py \
  tests/test_mes_agent_runtime.py -q
```

### Task 6: Active Inspector Generalization

**Files:**
- Modify: `tests/test_mes_process_chat.py`
- Modify: `src/mes/ui/static/control_room.js`
- Modify: `src/mes/ui/static/control_room.css`
- Modify: `src/mes/ui/templates/control_room.html`

- [x] **Step 1: Write failing UI contract tests**

Assert support for common artifact/chart types, B process copy, common renderer,
and a `B cleaning map` example prompt.

- [x] **Step 2: Verify failure**

- [x] **Step 3: Generalize the renderer**

Replace A-only branches with a common quality renderer. Select title, section
copy, component labels, reason text, and evidence labels by `quality_kind`.
Retain A visual behavior.

- [x] **Step 4: Add B chat example**

```text
CLEAN-01에서 가장 최근 세정된 제품의 잔류 오염과 세정 균일도 맵을 보여줘
```

- [x] **Step 5: Run UI tests and JavaScript syntax check**

```bash
.venv/bin/python -m pytest tests/test_mes_process_chat.py -q
node --check src/mes/ui/static/control_room.js
```

### Task 7: Documentation And End-To-End Verification

**Files:**
- Modify: `docs/ai-mes/03_ABC_CANONICAL_SCHEMA_REFERENCE.md`
- Modify: `docs/ai-mes/07_API_CONTRACTS.md`
- Modify: `docs/ai-mes/08_UI_CONTROL_ROOM_SPEC.md`
- Modify: `docs/ai-mes/09_PROCESS_APC_MCP_AGENT.md`
- Modify: `docs/ai-mes/16_IMPLEMENTATION_ROADMAP.md`
- Modify: `docs/ai-mes/17_CURRENT_IMPLEMENTATION_STATUS.md`
- Modify: `docs/ai-mes/18_AGENT_VISUAL_ANALYTICS_V1.md`

- [x] **Step 1: Document common provider/evidence/tool/artifact contracts**
- [x] **Step 2: Document A/B process-specific semantics and scalar authority**
- [x] **Step 3: Run focused tests**

```bash
.venv/bin/python -m pytest \
  tests/test_process_quality_registry.py \
  tests/test_process_a_spatial_quality.py \
  tests/test_process_b_spatial_quality.py \
  tests/test_mes_process_quality_maps.py \
  tests/test_mes_visual_artifacts.py \
  tests/test_mes_agent_tools.py \
  tests/test_mes_agent_runtime.py \
  tests/test_mes_process_chat.py -q
```

- [x] **Step 4: Run full suite and static checks**

```bash
.venv/bin/python -m pytest -q
node --check src/mes/ui/static/control_room.js
git diff --check
```

- [x] **Step 5: Restart MES and produce B completion evidence**
- [x] **Step 6: Ask Gemma**

```text
CLEAN-01에서 가장 최근 세정된 제품의 잔류 오염과 세정 균일도 맵을 보여줘.
```

Verify selection of `query_process_quality_evidence`, a B artifact, explicit
`SIMULATED_CLEANING_QUALITY` provenance, and Active Inspector rendering.

- [x] **Step 7: Commit**

```bash
git add src tests docs/ai-mes
git commit -m "feat: add process quality intelligence"
```
