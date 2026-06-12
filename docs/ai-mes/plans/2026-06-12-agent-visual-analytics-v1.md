# MES Agent Visual Analytics V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add generic read-only equipment visual analytics tools and a chart-focused Active Inspector to Process Chat.

**Architecture:** A telemetry reader normalizes simulator equipment events into metric series and evidence events. Agent tools convert those results into typed visual artifacts, which Process Chat returns separately from natural-language content. The browser renders only allowlisted artifact structures in a resizable 40:60 inspector.

**Tech Stack:** Python 3.12, FastAPI, pytest, existing MES agent runtime, static HTML/CSS/JavaScript, SVG chart rendering.

---

### Task 1: Equipment Telemetry Contract

**Files:**
- Create: `src/mes/runtime/equipment_telemetry.py`
- Create: `tests/test_mes_equipment_telemetry.py`

- [ ] **Step 1: Write failing tests for equipment resolution and metric catalog**

Tests must prove canonical ids and configured display names resolve to the same
equipment and expose `quality`, `utilization`, `throughput`, `alarm`, and
`anomaly`.

- [ ] **Step 2: Run the focused tests and verify missing-module failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_mes_equipment_telemetry.py -q
```

Expected: collection failure because `equipment_telemetry` does not exist.

- [ ] **Step 3: Implement resolution, range normalization, and metric catalog**

Create a focused reader with:

```python
def equipment_metric_catalog(context, equipment_ids): ...
def query_equipment_timeseries(context, equipment_ids, metrics, time_range, aggregation): ...
def query_equipment_anomalies(context, equipment_ids, time_range, severity=None): ...
```

Enforce a maximum of eight equipment records, 365 requested periods, and 2,000
returned points.

- [ ] **Step 4: Add failing tests for A/B/C quality, utilization, throughput, and anomalies**

Seed deterministic event-log rows directly so each metric definition is tested
without relying on an LLM.

- [ ] **Step 5: Implement simulator event normalization**

Use `task_assigned`/`task_completed` for A/B and
`pack_started`/`pack_completed` for C. Emit observed alarms only from explicit
alarm events. Emit derived anomalies for OOS quality and threshold breaches.

- [ ] **Step 6: Run telemetry tests**

```bash
.venv/bin/python -m pytest tests/test_mes_equipment_telemetry.py -q
```

Expected: all telemetry tests pass.

### Task 2: Typed Visual Artifacts

**Files:**
- Create: `src/mes/agent_runtime/visual_artifacts.py`
- Create: `tests/test_mes_visual_artifacts.py`

- [ ] **Step 1: Write failing artifact contract tests**

Cover deterministic artifact ids, allowed chart types, provenance, series,
events, summary fields, and rejection of script/HTML-like visualization fields.

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest tests/test_mes_visual_artifacts.py -q
```

- [ ] **Step 3: Implement artifact builders and validators**

Support:

```text
equipment_timeseries
equipment_anomalies
```

Allow only `line`, `bar`, and `event_timeline` display types.

- [ ] **Step 4: Verify GREEN**

```bash
.venv/bin/python -m pytest tests/test_mes_visual_artifacts.py -q
```

### Task 3: Generic Agent Visual Tools

**Files:**
- Create: `src/mes/agent_runtime/visual_tools.py`
- Modify: `src/mes/agent_runtime/mes_tools.py`
- Modify: `tests/test_mes_agent_tools.py`

- [ ] **Step 1: Add failing catalog and execution tests**

Require:

```text
list_equipment_metrics
query_equipment_timeseries
query_equipment_anomalies
```

All tools must be read-only and return a `visual_artifacts` list when visual
evidence exists.

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest tests/test_mes_agent_tools.py -q
```

- [ ] **Step 3: Implement tool schemas and dispatch**

Keep visual tool metadata and execution in `visual_tools.py`; keep
`MESAgentToolService` as the combined registry/facade.

- [ ] **Step 4: Verify GREEN**

```bash
.venv/bin/python -m pytest tests/test_mes_agent_tools.py -q
```

### Task 4: Chat Artifact Propagation And Persistence

**Files:**
- Modify: `src/mes/agent_runtime/agent_loop.py`
- Modify: `src/mes/agent_runtime/process_chat.py`
- Modify: `src/mes/agent_runtime/run_store.py`
- Modify: `src/mes/agent_runtime/sqlite_run_store.py`
- Modify: `tests/test_mes_agent_runtime.py`
- Modify: `tests/test_mes_process_chat.py`
- Modify: `tests/test_mes_agent_run_store.py`
- Modify: `tests/test_mes_agent_sqlite_run_store.py`

- [ ] **Step 1: Add failing propagation tests**

An executed visual tool must cause the runtime and `/api/v2/process-chat`
payload to contain a deduplicated `visual_artifacts` list.

- [ ] **Step 2: Add failing persistence tests**

Agent run detail must return the artifacts associated with that run.

- [ ] **Step 3: Implement recursive artifact collection**

Collect only validated dictionaries from `tool_call.result.visual_artifacts`.
Do not parse artifacts from model-generated answer text.

- [ ] **Step 4: Persist artifacts in existing agent-run payload storage**

Keep SQLite compatibility by storing artifacts in the existing JSON run payload
rather than adding an unnecessary normalized table in V1.

- [ ] **Step 5: Run focused runtime tests**

```bash
.venv/bin/python -m pytest \
  tests/test_mes_agent_runtime.py \
  tests/test_mes_process_chat.py \
  tests/test_mes_agent_run_store.py \
  tests/test_mes_agent_sqlite_run_store.py -q
```

### Task 5: Active Inspector UI

**Files:**
- Modify: `src/mes/ui/templates/control_room.html`
- Modify: `src/mes/ui/static/control_room.js`
- Modify: `src/mes/ui/static/control_room.css`
- Modify: `tests/test_mes_process_chat.py`

- [ ] **Step 1: Add failing UI mount tests**

Require stable ids for:

```text
chat-active-inspector
chat-inspector-chart
chat-inspector-data
chat-inspector-events
chat-inspector-divider
```

- [ ] **Step 2: Implement the 40:60 desktop shell**

Keep the inspector hidden until an artifact is active. On activation, apply a
chart-focused grid and render source/time-basis metadata.

- [ ] **Step 3: Implement constrained SVG renderers**

Render line/bar/event artifacts from typed fields. Escape all labels and never
insert artifact-provided HTML.

- [ ] **Step 4: Implement inspector interactions**

Add artifact selection, Chart/Data/Events tabs, close, pin, full-screen, and
pointer-driven divider resize with sensible min widths.

- [ ] **Step 5: Implement narrow-screen drawer behavior**

At the existing mobile breakpoint, show the inspector over the Chat workspace
with a visible close command and no horizontal overflow.

- [ ] **Step 6: Run UI contract tests**

```bash
.venv/bin/python -m pytest tests/test_mes_process_chat.py -q
```

### Task 6: Documentation And Verification

**Files:**
- Modify: `docs/ai-mes/00_INDEX.md`
- Modify: `docs/ai-mes/07_API_CONTRACTS.md`
- Modify: `docs/ai-mes/08_UI_CONTROL_ROOM_SPEC.md`
- Modify: `docs/ai-mes/09_PROCESS_APC_MCP_AGENT.md`
- Modify: `docs/ai-mes/16_IMPLEMENTATION_ROADMAP.md`
- Modify: `docs/ai-mes/17_CURRENT_IMPLEMENTATION_STATUS.md`

- [ ] **Step 1: Document tools, artifacts, time semantics, and UI behavior**

- [ ] **Step 2: Run focused Visual Analytics tests**

```bash
.venv/bin/python -m pytest \
  tests/test_mes_equipment_telemetry.py \
  tests/test_mes_visual_artifacts.py \
  tests/test_mes_agent_tools.py \
  tests/test_mes_agent_runtime.py \
  tests/test_mes_process_chat.py -q
```

- [ ] **Step 3: Run the complete regression suite**

```bash
.venv/bin/python -m pytest -q
```

- [ ] **Step 4: Run repository checks**

```bash
git diff --check
```

- [ ] **Step 5: Restart the local MES server and verify with Browser**

Verify desktop and mobile:

- visual tool result opens the 40:60 inspector,
- source/time basis is visible,
- Chart/Data/Events switch correctly,
- close and full-screen work,
- no text overlap or horizontal page overflow,
- existing non-visual Chat still uses the full workspace.

