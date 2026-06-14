# A Spatial Quality Map V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic Process A spatial quality model, read-only Agent tool, typed visual artifact, and Active Inspector renderer without changing existing scalar QA decisions.

**Architecture:** `ProcessA_Env` continues to calculate scalar QA. A focused spatial model expands that scalar into a stable canonical grid, recenters the grid to the scalar mean, and stores the result on completion events. MES runtime and Agent modules read this evidence and produce an allowlisted data-only artifact rendered by built-in browser code.

**Tech Stack:** Python 3.12, NumPy, pytest, FastAPI runtime context, Continue-compatible Agent tools, vanilla JavaScript/SVG/CSS.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/environment/process_a_spatial_quality.py` | Pure deterministic spatial field generation and summary |
| `src/environment/process_a_env.py` | Attach spatial evidence to A completion events |
| `src/mes/runtime/process_quality_maps.py` | Resolve and query completed A maps |
| `src/mes/agent_runtime/visual_tools.py` | Agent tool schema and execution |
| `src/mes/agent_runtime/visual_artifacts.py` | Typed spatial artifact construction and validation |
| `src/mes/ui/static/control_room.js` | Built-in spatial map renderer |
| `src/mes/ui/static/control_room.css` | Map, cell, summary, and evidence layout |
| `tests/test_process_a_spatial_quality.py` | Pure model contract |
| `tests/test_env_validation_matrix.py` | Environment regression and event contract |
| `tests/test_mes_process_quality_maps.py` | Runtime query contract |
| `tests/test_mes_visual_artifacts.py` | Artifact validation |
| `tests/test_mes_agent_tools.py` | Agent catalog and tool execution |
| `tests/test_mes_process_chat.py` | UI mount and renderer contract |

### Task 1: Pure Spatial Model

**Files:**
- Create: `tests/test_process_a_spatial_quality.py`
- Create: `src/environment/process_a_spatial_quality.py`

- [ ] **Step 1: Write failing determinism and scalar-mean tests**

```python
def test_spatial_map_is_deterministic_and_preserves_scalar_mean():
    first = generate_process_a_spatial_quality(
        scalar_qa=49.2,
        spec=(45.0, 55.0),
        recipe=[10.0, 2.0, 1.0],
        u=8,
        m_age=80,
        task_uid=184,
        equipment_id="A_0",
        completion_time=20,
    )
    second = generate_process_a_spatial_quality(...)
    assert first == second
    assert first["summary"]["mean"] == pytest.approx(49.2, abs=1e-6)
    assert first["model"]["evidence_type"] == "SIMULATED_SPATIAL_QUALITY"
```

- [ ] **Step 2: Run test and verify missing-module failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_process_a_spatial_quality.py -q
```

Expected: FAIL because `process_a_spatial_quality` does not exist.

- [ ] **Step 3: Implement canonical circular-grid generation**

Implement:

```python
generate_process_a_spatial_quality(
    *,
    scalar_qa: float,
    spec: tuple[float, float],
    recipe: Sequence[float],
    u: float,
    m_age: float,
    task_uid: int,
    equipment_id: str,
    completion_time: int,
    grid_size: int = 17,
) -> dict[str, Any]
```

Requirements:

- stable SHA256-derived random seed;
- circular valid-cell mask;
- radial, directional, hotspot, and local-noise components;
- recenter valid cells to `scalar_qa`;
- position verdict and specification margin;
- connected-component largest OOS cluster;
- summary and reason codes;
- model id `PROCESS_A_SPATIAL_FIELD`;
- version `1.0.0`.

- [ ] **Step 4: Run model tests**

Expected: PASS.

### Task 2: Process A Completion Evidence

**Files:**
- Modify: `tests/test_env_validation_matrix.py`
- Modify: `src/environment/process_a_env.py`

- [ ] **Step 1: Write failing event-contract test**

Assert that a completed A event contains one spatial map per completed task and
that the existing `realized_qa_A` and rework verdict are unchanged.

- [ ] **Step 2: Run focused test and verify `spatial_quality_maps` is missing**

- [ ] **Step 3: Call the pure model after each scalar QA calculation**

Store full map rows in:

```python
event["spatial_quality_maps"]
```

Store only summary/model reference in:

```python
task.history[-1]["spatial_quality_summary"]
task.history[-1]["spatial_quality_model"]
```

- [ ] **Step 4: Run environment and spatial tests**

```bash
.venv/bin/python -m pytest tests/test_process_a_spatial_quality.py tests/test_env_validation_matrix.py -q
```

### Task 3: Read-Only Runtime Query

**Files:**
- Create: `tests/test_mes_process_quality_maps.py`
- Create: `src/mes/runtime/process_quality_maps.py`

- [ ] **Step 1: Write failing query tests**

Cover:

- latest map by `equipment_id`;
- exact map by `task_uid`;
- display name resolution;
- equipment/task mismatch;
- Process B rejection;
- no-completion result.

- [ ] **Step 2: Verify missing-module failure**

- [ ] **Step 3: Implement**

```python
query_process_a_spatial_quality(
    context,
    *,
    equipment_id: str | None = None,
    task_uid: int | None = None,
) -> dict[str, Any]
```

Return `found=false` for absent evidence and raise explicit validation errors
for unsupported equipment.

- [ ] **Step 4: Run query tests**

Expected: PASS.

### Task 4: Typed Artifact And Agent Tool

**Files:**
- Modify: `tests/test_mes_visual_artifacts.py`
- Modify: `tests/test_mes_agent_tools.py`
- Modify: `src/mes/agent_runtime/visual_artifacts.py`
- Modify: `src/mes/agent_runtime/visual_tools.py`
- Modify: `src/mes/agent_runtime/process_chat.py`

- [ ] **Step 1: Write failing artifact and catalog tests**

Expected contracts:

```text
tool = query_process_a_spatial_quality
artifact_type = process_a_spatial_quality
chart_type = spatial_quality_map
```

- [ ] **Step 2: Verify failures for unknown tool/artifact/chart**

- [ ] **Step 3: Add allowlisted artifact builder and tool**

The tool accepts optional `equipment_id` and `task_uid`; at least one is
required. The artifact includes only structured data and approved visualization
fields. Increment `TOOL_CATALOG_VERSION`.

- [ ] **Step 4: Run Agent and artifact tests**

```bash
.venv/bin/python -m pytest tests/test_mes_visual_artifacts.py tests/test_mes_agent_tools.py tests/test_mes_agent_runtime.py -q
```

### Task 5: Active Inspector Spatial Renderer

**Files:**
- Modify: `tests/test_mes_process_chat.py`
- Modify: `src/mes/ui/static/control_room.js`
- Modify: `src/mes/ui/static/control_room.css`
- Modify: `src/mes/ui/templates/control_room.html`

- [ ] **Step 1: Write failing renderer-contract test**

Assert the HTML/JS contains:

```text
process_a_spatial_quality
spatial_quality_map
renderSpatialQualityMap
SIMULATED_SPATIAL_QUALITY
```

- [ ] **Step 2: Verify test failure**

- [ ] **Step 3: Implement built-in map renderer**

Render:

- circular grid from valid cells;
- PASS/MARGIN/OOS_LOW/OOS_HIGH colors;
- cell tooltip;
- six KPI values;
- scalar/map verdict difference;
- reason cards;
- position rows in Data;
- reason evidence in Events.

The artifact contains no executable markup or style definitions.

- [ ] **Step 4: Run UI contract tests and JS syntax check**

```bash
.venv/bin/python -m pytest tests/test_mes_process_chat.py -q
node --check src/mes/ui/static/control_room.js
```

### Task 6: Documentation

**Files:**
- Modify: `docs/ai-mes/07_API_CONTRACTS.md`
- Modify: `docs/ai-mes/08_UI_CONTROL_ROOM_SPEC.md`
- Modify: `docs/ai-mes/09_PROCESS_APC_MCP_AGENT.md`
- Modify: `docs/ai-mes/17_CURRENT_IMPLEMENTATION_STATUS.md`
- Modify: `docs/ai-mes/18_AGENT_VISUAL_ANALYTICS_V1.md`

- [ ] **Step 1: Document model semantics and simulator provenance**
- [ ] **Step 2: Document tool, artifact, and UI contracts**
- [ ] **Step 3: State explicitly that scalar pass/fail remains authoritative in V1**

### Task 7: End-To-End Verification

- [ ] **Step 1: Run focused suite**

```bash
.venv/bin/python -m pytest \
  tests/test_process_a_spatial_quality.py \
  tests/test_mes_process_quality_maps.py \
  tests/test_mes_visual_artifacts.py \
  tests/test_mes_agent_tools.py \
  tests/test_mes_agent_runtime.py \
  tests/test_mes_process_chat.py -q
```

- [ ] **Step 2: Run full suite**

```bash
.venv/bin/python -m pytest -q
```

- [ ] **Step 3: Run static checks**

```bash
node --check src/mes/ui/static/control_room.js
git diff --check
```

- [ ] **Step 4: Restart MES and test a real Agent question**

```text
LITHO-01에서 가장 최근 완료된 제품의 공간 품질 판정 맵을 보여줘.
```

Verify the LLM selects `query_process_a_spatial_quality`, the map opens in the
Active Inspector, and provenance says `SIMULATED_SPATIAL_QUALITY`.

- [ ] **Step 5: Browser verification**

Check desktop split, full-screen inspector, close, map/data/events tabs, cell
legibility, and mobile drawer without horizontal document overflow.

- [ ] **Step 6: Commit**

```bash
git add src tests docs/ai-mes
git commit -m "feat: add Process A spatial quality maps"
```
