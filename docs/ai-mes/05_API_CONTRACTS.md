# API Contracts

Status: canonical  
Last updated: 2026-05-23

## Purpose

This document defines the simulator-backed MES API surface and the target API
contracts needed for the layered AI architecture.

The current route implementation lives in `src/mes/api.py`. Route functions are
thin and delegate runtime behavior to `src/mes/runtime/*`.

| Runtime concern | Module |
|---|---|
| lifecycle/reset | `src/mes/runtime/context.py` |
| run-cycle/run-until/autoplay/generate lot | `src/mes/runtime/simulation_control.py` |
| live control-room state | `src/mes/runtime/live_state.py` |
| decision-chain traceability | `src/mes/runtime/decision_trace.py` |
| assignment and genealogy traceability | `src/mes/runtime/assignment_trace.py`, `src/mes/runtime/genealogy.py` |
| AI developer console payloads | `src/mes/runtime/ai_dev.py` |
| operation registry and action proposal routes | `src/mes/runtime/production_boundary_api.py`, `src/mes/runtime/operations.py`, `src/mes/operations/registry.py` |
| run and ledger index routes | `src/mes/runtime/run_ledger_api.py`, `src/mes/runtime/run_ledger.py` |
| equipment detail | `src/mes/runtime/equipment_detail.py` |
| Gantt state | `src/mes/runtime/gantt.py` |

## Current Read APIs

| Endpoint | Purpose |
|---|---|
| `GET /health` | Service health |
| `GET /api/v1/decision-state` | Raw simulator decision state |
| `GET /api/v1/kpis/fab` | Fab KPI summary |
| `GET /api/v1/wip` | WIP by stage |
| `GET /api/v1/equipment` | Equipment list |
| `GET /api/v1/lots` | Lot list from store-backed runtime snapshot |
| `GET /api/v1/wafers` | Wafer list, optional `lot_id` filter |
| `GET /api/v1/recipes` | Recipe list, optional `operation_id` filter |
| `GET /api/v1/dispatch/candidates?stage=A` | L1 policy-stack dispatch candidates |
| `GET /api/v1/ai/recommendations` | Recommendation records, optional `correlation_id` |
| `GET /api/v1/events` | Event records, optional `correlation_id` |
| `GET /api/v1/commands` | Command records, optional `correlation_id` |
| `GET /api/v2/decision-chain/{correlation_id}` | Aggregated chain details |
| `GET /api/v2/candidate-portfolio/latest` | Latest actionable selected/rejected portfolio workbench payload |
| `GET /api/v2/candidate-portfolio/{correlation_id}` | Portfolio snapshot for one decision correlation |
| `GET /api/v2/ai-dev/policy-stack` | Active L1/L2/L3/L4 policy stack and config |
| `GET /api/v2/ai-dev/decision-cycles` | Correlation-level AI decision cycle browser |
| `GET /api/v2/ai-dev/candidate-portfolio/{correlation_id}` | Developer portfolio payload with score/L2 details |
| `GET /api/v2/equipment/{equipment_id}/detail` | A/B/C machine quality and packing detail data |
| `GET /api/v2/gantt` | Gantt rows, bars, stage views, and horizon |
| `GET /api/v2/fab/live` | Live control-room state |
| `GET /api/v2/runs` | Current and historical local simulator run/session index |
| `GET /api/v2/operations` | Operation and equipment registry for simulator and future production process mapping |
| `GET /api/v2/action-proposals` | Legacy-safe action proposals derived from validated MES commands |
| `GET /api/v2/ledger-index/{index_name}` | Run-scoped normalized SQLite index rows |
| `GET /api/v2/genealogy/task/{task_uid}` | Run-scoped task/wafer lineage with assignments, command links, and simulator events |
| `GET /api/v2/genealogy/equipment/{equipment_id}` | Run-scoped equipment command and process timeline |
| `GET /api/v2/genealogy/lot/{lot_id}` | Run-scoped lot-level task and command rollout |
| `GET /api/v2/execution-ledger/{correlation_id}` | Run-scoped command, rule, simulator-action, and post-state ledger |
| `GET /api/v2/digital-twin/state-at?time=0` | Run-scoped replayable decision-state snapshot at or before time |
| `GET /api/v2/process-tools/catalog` | Read-only process model tool catalog for LLM/MCP callers |
| `GET /api/v2/process-chat/models` | Continue-style chat model catalog for process chat |
| `GET /api/v2/agent-runs` | Recent Agent Mode and local fallback run records |
| `GET /api/v2/agent-runs/{agent_run_id}` | Agent run detail with metadata, tool calls, and step trace |

## Current Mutation APIs

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/harness/run` | Preview one stage, or execute L3-budget AUTO |
| `POST /api/v1/rules/validate` | Validate recommendation payloads |
| `POST /api/v1/commands/track-in/preview` | Preview track-in command |
| `POST /api/v1/commands/track-in/execute` | Execute validated command |
| `POST /api/v2/tasks/generate` | Generate simulator tasks |
| `POST /api/v2/harness/run-cycle` | Run and execute one cycle |
| `POST /api/v2/harness/run-until` | Run cycles until stop condition |
| `POST /api/v2/simulation/reset` | Reset simulator runtime and start a new run_id while preserving prior audit/ledger history |
| `POST /api/v2/simulation/autoplay/start` | Enable autoplay |
| `POST /api/v2/simulation/autoplay/stop` | Disable autoplay |
| `GET /api/v2/simulation/autoplay/status` | Poll autoplay and optionally step |
| `POST /api/v2/process-tools/{tool_id}/run` | Read-only process model inference with structured input |
| `POST /api/v2/process-chat` | Process-engineer chat over read-only process tools with LLM/fallback mode |

## Current V2 Payload Summary

`POST /api/v2/harness/run-cycle` with `target_stage="AUTO"` returns an L3
budget-driven execution payload:

```python
{
    "mode": "AUTO",
    "selection_source": "l3_budget_plan",
    "budget_plan": {
        "selected_candidate_ids": ["CAND_..."],
        "dispatch_budgets": {"A": 5, "B": 0, "C": 0},
        "budget_candidate_ids": {"A": ["CAND_..."], "B": [], "C": []}
    },
    "combined_actions": {"A": {...}, "B": {}, "C": {}},
    "cycles": [...]
}
```

`GET /api/v2/decision-chain/{correlation_id}` returns the persisted audit chain
and a `traceability` block with L4/L3 policy ids, selected candidates, final
L1/L2 actions, validated command, and `portfolio_summary`.

`GET /api/v2/candidate-portfolio/latest` and
`GET /api/v2/candidate-portfolio/{correlation_id}` return the workbench-ready
portfolio snapshot. `latest` prefers the latest actionable portfolio over a
newer empty cycle, while still reporting the latest empty correlation and empty
diagnostics.

```python
{
    "correlation_id": "CORR_...",
    "feature_snapshot_id": "FS_...",
    "kind": "ACTIONABLE",
    "is_actionable": True,
    "empty_reason": None,
    "last_actionable_correlation_id": "CORR_...",
    "latest_empty_correlation_id": "CORR_...",
    "diagnostics": {
        "stages": {
            "A": {"queue_size": 12, "idle_machines": 2, "candidate_count": 5}
        }
    },
    "count": 12,
    "summary": {
        "selected_count": 1,
        "rejected_count": 11,
        "stage_counts": {"A": 5, "B": 3, "C": 4},
        "objective_id": "OBJ_DUE_DATE_RECOVERY",
        "l4_policy_id": "L4_CYCLE_WEIGHT_RULE",
        "l3_policy_id": "L3_CANDIDATE_PORTFOLIO_RULE"
    },
    "items": [
        {
            "candidate_id": "CAND_C_ALPHA_001",
            "stage": "C",
            "candidate_type": "PACK",
            "group_key": {"customer_id": "ALPHA"},
            "equipment_id": "C_0",
            "task_uids": [1, 2, 3, 4],
            "local_score": 90.0,
            "upper_score": 124.2,
            "score_components": {
                "local_candidate_score": 90.0,
                "due_date_pressure": 2.0,
                "wip_pressure": 4.0,
                "objective_weight_bonus": 34.2,
                "quality_risk_penalty": 0.0,
                "final_upper_score": 124.2
            },
            "l2_annotation": {"quality_risk": "LOW"},
            "selected": True,
            "budget_selected": True,
            "rejection_reason": None,
            "linked_recommendation_ids": {"L4": "REC_...", "L3": "REC_..."},
            "command_status": "EXECUTED"
        }
    ]
}
```

`GET /api/v2/process-tools/catalog` lists process model tools that are safe for
LLM/MCP use. `POST /api/v2/process-tools/{tool_id}/run` executes one read-only
inference. The first implemented tool is `predict_process_a_apc`, backed by the
Process A rule-based APC model.

```python
POST /api/v2/process-tools/predict_process_a_apc/run
{
    "task_rows": [{"task_uid": "T0", "spec_a": [48.0, 53.0]}],
    "machine_state": {"u": 6, "m_age": 12},
    "recipe": [10.0, 2.0, 1.0],
    "current_time": 120
}

{
    "tool_id": "predict_process_a_apc",
    "stage": "A",
    "model_id": "A_RULE_BASED_APC_PREDICTOR",
    "read_only": True,
    "recipe": [10.0, 2.0, 1.0],
    "predicted_qa": 49.6646,
    "quality_risk": "LOW",
    "replace_consumable": True
}
```

`POST /api/v2/process-chat` accepts a natural-language process/MES question and
returns a chat answer plus any tool calls used. `use_llm=true` attempts the local
Continue-inspired runtime first and falls back to the local A APC parser/tool
when the model is unavailable. `use_llm=false` runs the local parser/tool
directly. `mode=agent` runs a multi-step read-only tool loop; `mode=chat` sends
one model request without tool execution. `max_steps` bounds Agent Mode.
`model_name` may select any configured chat model by `name` or `model` id. V1
supports `ollama` and `openai` providers. By default the runtime reads
`config/mes-process-agent.yaml`; `MES_PROCESS_AGENT_CONFIG` can override this
path. The model list is filtered to Continue `chat` role models. Continue
`capabilities` are combined with provider/model autodetection; `tool_use`
controls native tool-schema sending. Models without native `tool_use` use a
system-message JSON tool fallback in Agent Mode.

```python
POST /api/v2/process-chat
{
    "message": "A 공정에서 spec_a 48~53이고 u=6, m_age=12, recipe=[10,2,1]이면 QA가 어떻게 나올까?",
    "use_llm": False,
    "model_name": "Gemma4 Remote",
    "mode": "agent",
    "max_steps": 5
}

{
    "agent_run_id": "ARUN_...",
    "mode": "local_process_tool",
    "status": "completed",
    "answer": "A 공정 APC 예측 결과 predicted_qa=49.6646...",
    "tool_calls": [
        {
            "tool_name": "predict_process_a_apc",
            "status": "executed",
            "policy": "local_process_tool",
            "result": {"stage": "A", "quality_risk": "LOW"}
        }
    ],
    "agent_trace": []
}
```

Agent Mode may return `mode="llm_agent"`, `status`, `agent_trace`, and multiple
tool calls. The MES API process registers these read-only tools for Agent Mode:
`predict_process_a_apc`, `get_fab_snapshot`, `get_policy_stack`,
`get_candidate_portfolio_latest`, `get_equipment_detail`, and
`get_assignment_trace`. Non-read-only or unknown tool calls are rejected with
`status="policy_blocked"` and `policy="excluded"`.

`GET /api/v2/agent-runs` and `GET /api/v2/agent-runs/{agent_run_id}` expose the
inspection record created by each chat request. In the MES API process these
records are SQLite-backed through the runtime database path, so recent Agent
Mode and local fallback runs survive process restarts. Standalone chat service
usage without a runtime context may still use the in-memory store.

```python
GET /api/v2/agent-runs/{agent_run_id}
{
    "found": True,
    "agent_run_id": "ARUN_...",
    "mes_run_id": "RUN_...",
    "question": "현재 fab 상태와 active policy stack을 보고 병목을 설명해줘",
    "mode": "agent",
    "status": "completed",
    "answer": "A 공정이 병목입니다...",
    "tool_count": 2,
    "step_count": 5,
    "metadata": {
        "model_name": "gemma4:latest",
        "provider": "ollama",
        "max_steps": 5,
        "prompt_id": "MES_AGENT_SYSTEM_PROMPT",
        "prompt_version": "0.1.0",
        "tool_catalog_version": "mes-agent-tools-v1",
        "requested_think": True
    },
    "tool_calls": [
        {"tool_name": "get_fab_snapshot", "status": "executed"}
    ],
    "agent_trace": [
        {"type": "llm_response", "step": 1, "tool_call_count": 1},
        {"type": "tool_call", "step": 1, "tool_name": "get_fab_snapshot"}
    ]
}
```

Process and equipment naming is display metadata, not a state/action key
replacement. Live state, Gantt rows, and equipment detail payloads can include:

```python
{
    "stage": "A",
    "label": "Lithography QA",
    "equipment_id": "A_0",
    "display_name": "Lithography Tool 01"
}
```

Canonical ids (`A`, `B`, `C`, `A_0`, `B_0`, `C_0`) remain the values used for
policy decisions, Rule Engine validation, command payloads, and simulator
actions.

`GET /api/v2/operations` returns the active operation/equipment registry. A/B/C
are default simulator operations today, but the contract is shaped for future
production operations loaded from route and equipment master data.

```python
{
    "source": "operation_registry",
    "canonical_id_policy": "operation_id_and_equipment_id_are_stable_contract_keys",
    "count": 3,
    "equipment_count": 11,
    "items": [
        {
            "operation_id": "A",
            "display_name": "Process QA",
            "operation_type": "process_qa",
            "equipment_group_id": "A",
            "execution_boundary": "SIMULATOR_STAGE",
            "upstream_operation_ids": [],
            "downstream_operation_ids": ["B"],
            "batch_size": 3,
            "process_time": 20,
            "l1_policy_key": "scheduler_A",
            "l2_policy_key": "tuner_A",
            "legacy_submission_mode": "SIMULATOR_ONLY"
        }
    ],
    "equipment": [
        {
            "equipment_id": "A_0",
            "display_name": "A_0",
            "equipment_group_id": "A",
            "capable_operations": ["A"],
            "batch_size": 3,
            "execution_boundary": "SIMULATOR_STAGE"
        }
    ]
}
```

`GET /api/v2/action-proposals` returns production-facing proposal envelopes
derived from validated `MESCommand` records. Optional `correlation_id` and
`run_id` query parameters filter the result. The contract intentionally says the
AI layer is proposing an action to legacy MES, not directly driving equipment.

```python
{
    "count": 1,
    "correlation_id": "CORR_...",
    "run_id": "RUN_...",
    "items": [
        {
            "proposal_id": "PROP_CMD_...",
            "proposal_type": "LEGACY_MES_ACTION_PROPOSAL",
            "correlation_id": "CORR_...",
            "operation_id": "A",
            "source_command_id": "CMD_...",
            "source_command_type": "RESERVE_AND_TRACK_IN",
            "validation_status": "PASSED",
            "status": "PROPOSED",
            "candidate_id": "CAND_A_...",
            "target_equipment_id": "A_0",
            "target_unit_ids": ["WAFER_1", "WAFER_2", "WAFER_3"],
            "policy_refs": {
                "dispatch_recommendation_id": "REC_L1_...",
                "recipe_recommendation_id": "REC_L2_..."
            },
            "legacy_submission_mode": "SIMULATOR_ONLY",
            "direct_equipment_control": False,
            "payload": {"stage": "A", "task_uids": [1, 2, 3]}
        }
    ]
}
```

`GET /api/v2/ai-dev/policy-stack` returns the active factory-built stack:

```python
{
    "factory_name": "build_mes_policy_stack",
    "l1_policy_id": "L1_FIFO_BASELINE",
    "l2_policy_id": "L2_RULE_BASED_APC",
    "l3_policy_id": "L3_CANDIDATE_PORTFOLIO_RULE",
    "l4_policy_id": "L4_CYCLE_WEIGHT_RULE",
    "config": {"scheduler_A": "fifo", "tuner_A": "rule-based"},
    "layers": {
        "L3": {
            "policy_id": "L3_CANDIDATE_PORTFOLIO_RULE",
            "model_id": "candidate-portfolio-meta-scheduler",
            "model_version": "0.1.0"
        }
    }
}
```

`GET /api/v2/ai-dev/decision-cycles` returns recent correlation rows for the
developer cycle browser. `GET /api/v2/ai-dev/candidate-portfolio/{correlation_id}`
adds objective weights, L3 action, policy stack metadata, selected candidate,
score breakdown, and L2 annotations to the base portfolio payload.

`GET /api/v2/gantt` returns `flow`, `rows`, `bars`, `stage_views`, `horizon`,
and `legend`.

`GET /api/v2/equipment/{equipment_id}/detail` returns A/B APC quality trends or
C packing composition quality, including material/color counts for C.

## Future Standalone Layered AI APIs

The current API can run the baseline chain. The target architecture needs APIs
that expose candidate portfolios before final upper-layer selection.

### Candidate Portfolio

```http
GET /api/v1/ai/candidates?stage=C
```

Response:

```python
{
    "time": 42,
    "stage": "C",
    "count": 12,
    "group_keys": [
        {"customer_id": "ALPHA", "product_id": "P1"},
        {"customer_id": "BETA", "product_id": "P2"}
    ],
    "items": [
        {
            "candidate_id": "CAND_C_ALPHA_001",
            "candidate_type": "PACK",
            "stage": "C",
            "group_key": {"customer_id": "ALPHA"},
            "equipment_id": "C_0",
            "task_uids": [1, 2, 3, 4],
            "local_score": 100.0,
            "features": {"compatibility": 0.98}
        }
    ]
}
```

### Candidate Annotation

```http
POST /api/v1/ai/candidates/annotate
```

Request:

```python
{
    "correlation_id": "CORR_...",
    "candidates": [...]
}
```

Response:

```python
{
    "correlation_id": "CORR_...",
    "count": 12,
    "items": [
        {
            "candidate_id": "CAND_C_ALPHA_001",
            "l2": {
                "pack_quality_prediction": 72.1,
                "quality_risk": "LOW"
            }
        }
    ]
}
```

### Objective Recommendation

```http
POST /api/v1/ai/recommendations/objective
```

Creates or previews L4 objective weights.

### Meta Selection

```http
POST /api/v1/ai/recommendations/meta-selection
```

Consumes annotated candidate portfolios and returns L3/L4 group selection.

Request:

```python
{
    "correlation_id": "CORR_...",
    "objective": {...},
    "candidate_portfolio": [...]
}
```

Response:

```python
{
    "recommendation_id": "REC_L3_...",
    "layer_id": "L3",
    "recommended_action": {
        "selected_stage": "C",
        "selected_group_key": {"customer_id": "ALPHA"},
        "selected_candidate_id": "CAND_C_ALPHA_001"
    }
}
```

### Finalize Command

```http
POST /api/v1/commands/finalize
```

Consumes selected L4/L3/L1/L2 recommendations and returns validation/command
preview.

### Execute Command

```http
POST /api/v1/commands/{command_id}/execute
```

Executes only commands that are validated and executable.

## Response Envelope Rules

Every AI-facing response should include:

- `time`,
- `correlation_id` when part of a decision chain,
- `count` for collections,
- `items` for lists,
- stable ids for recommendations, snapshots, candidates, and commands,
- validation status when available.

## Error Rules

Recommended error categories:

| HTTP status | Use |
|---:|---|
| 400 | invalid target stage, malformed recommendation, impossible request |
| 404 | unknown lot, wafer, equipment, command, or correlation id |
| 409 | command no longer executable because state changed |
| 422 | syntactically valid but rule-invalid request |
| 500 | unexpected internal error |

Rule rejects should usually return `200` with `validation_status="REJECTED"`

## Current Control Room Runtime Baseline

The local `/mes` runtime currently starts with:

```text
A: 5 equipment, batch_size=3, process_time=20
B: 3 equipment, batch_size=2, process_time=8
C: 3 equipment, batch_size=4, process_time=2, max_packs_per_step=3
```

The UI exposes Start, Stop, Run cycle, Generate lot, and Reset. Server startup
and Reset initialize a clean simulator runtime and start a new `run_id`.
Historical audit, genealogy, and normalized ledger-index rows are preserved
under their prior `run_id`, which is required because simulator task ids are
reused after reset.

Rule rejects should remain successful HTTP responses when the request shape is
valid but the recommendation is not executable.

## AI Developer Experiment APIs

Policy Experiment Runner V1 is intentionally a development API. It captures an
immutable scenario snapshot from the current simulator state, replays that
snapshot through multiple factory-built policy stacks, and returns comparison
payloads without mutating the live simulator.

### Capture Scenario

```http
POST /api/v2/ai-dev/scenarios/capture
```

Response shape:

```python
{
    "scenario_id": "SCN_...",
    "time": 37,
    "source_correlation_id": "CORR_...",
    "config": {"scheduler_A": "fifo", "tuner_A": "rule-based"},
    "decision_state": {"A": {}, "B": {}, "C": {}, "tasks": {}},
    "tasks": {},
    "A": {},
    "B": {},
    "C": {},
    "equipment": [],
    "kpis": {}
}
```

### List Scenarios

```http
GET /api/v2/ai-dev/scenarios
```

Returns summary rows with `scenario_id`, `time`, `task_count`, `queue_sizes`,
and `equipment_count`.

### List Policy Variants

```http
GET /api/v2/ai-dev/policy-variants
```

V1 variants are config/objective presets:

- `baseline_fifo_rule`
- `l3_due_date_aggressive`
- `l3_throughput_aggressive`
- `c_grouped_packing`
- `bottleneck_relief`

### Run Experiment

```http
POST /api/v2/ai-dev/experiments/run
```

Request:

```python
{
    "scenario_id": "SCN_...",
    "variant_ids": ["baseline_fifo_rule", "c_grouped_packing"]
}
```

Response:

```python
{
    "experiment_id": "EXP_...",
    "scenario_id": "SCN_...",
    "count": 2,
    "results": [
        {
            "variant_id": "baseline_fifo_rule",
            "correlation_id": "CORR_EXP_...",
            "l4_objective_id": "OBJ_THROUGHPUT_FIRST",
            "selected_stage": "A",
            "selected_candidate_id": "CAND_A_...",
            "candidate_count": 5,
            "local_score": 17.8,
            "upper_score": 23.9,
            "quality_risk": "LOW",
            "command_valid": True,
            "validation_status": "PASSED",
            "portfolio": {"items": []},
            "score_components": {},
            "kpi_delta": {
                "selected_task_count": 3,
                "expected_wip_reduction": 3,
                "expected_completion_delta": 0,
                "command_count_delta": 1
            }
        }
    ],
    "comparison": {
        "best_variant_id": "baseline_fifo_rule",
        "best_reason": "highest_upper_score_then_expected_wip_reduction",
        "decision_diff": []
    }
}
```

### Read Experiment

```http
GET /api/v2/ai-dev/experiments/{experiment_id}
```

Returns the stored in-memory experiment payload. V1 experiment storage is reset
with the runtime and is not part of SQLite genealogy.

## Assignment Trace API

Assignment Trace Inspector V1 resolves a concrete equipment/task assignment back
to the full layered decision chain.

```http
GET /api/v2/assignment-trace
```

Query options:

```text
equipment_id=A_0
task_uid=0
correlation_id=CORR_...
candidate_id=CAND_...
```

Lookup precedence:

- if `correlation_id` is supplied, search commands in that decision chain,
- if `candidate_id` is supplied, match the selected candidate command,
- if `equipment_id + task_uid` are supplied, match the command that assigned
  that task to that equipment,
- if no command matches, return `200` with `found=false`.

Response shape:

```python
{
    "found": True,
    "lookup": {
        "equipment_id": "A_0",
        "task_uid": 0,
        "correlation_id": None,
        "candidate_id": None
    },
    "assignment": {
        "stage": "A",
        "equipment_id": "A_0",
        "task_uids": [0, 1, 2],
        "task_type": "new",
        "candidate_id": "CAND_A_...",
        "correlation_id": "CORR_...",
        "command_id": "CMD_...",
        "start": 0,
        "end": 20
    },
    "decision_state": {},
    "state_summary": {},
    "task_snapshots": [],
    "machine_snapshot": {},
    "layers": {
        "L4": {},
        "L3": {},
        "L1": {},
        "L2": {},
        "RULE_ENGINE": {},
        "COMMAND": {}
    },
    "candidate_portfolio": {},
    "simulator_action": {},
    "raw": {}
}
```

No-match response:

```python
{
    "found": False,
    "reason": "NO_MATCHING_COMMAND",
    "lookup": {...}
}
```

## Digital Twin Genealogy And Execution Ledger APIs

Digital Twin Genealogy V1 adds an execution backbone over the existing
recommendation chain. Run-Scoped Normalized Ledger Index V1 adds a durable
`run_id` namespace and normalized SQLite index tables so resets no longer
delete prior genealogy. Assignment Trace answers "why was this assigned";
genealogy answers "what did that assignment create over time".

All genealogy/ledger endpoints default to the current run. Pass `run_id=RUN_...`
to query prior runs after reset.

### Runs

```http
GET /api/v2/runs
```

Response includes:

- `current_run_id`: active simulator run,
- `items`: historical runs with reason, start time, config metadata, and
  normalized index counts,
- `is_current`: whether a row is the active run.

### Normalized Ledger Index

```http
GET /api/v2/ledger-index/{index_name}?run_id=RUN_...&limit=200
```

Allowed `index_name` values:

- `run_index`,
- `task_index`,
- `lot_index`,
- `assignment_index`,
- `equipment_timeline_index`,
- `command_ledger_index`,
- `event_ledger_index`,
- `state_snapshot_index`,
- `genealogy_edge_index`.

This endpoint exposes the SQLite normalized index rows used by developer
diagnostics. It is not the final production schema, but it gives stable
run-scoped lookup surfaces for task, lot, equipment, command, event, and state
snapshot evidence.

### Task Genealogy

```http
GET /api/v2/genealogy/task/{task_uid}
```

Response shape:

```python
{
    "found": True,
    "entity_type": "TASK",
    "run_id": "RUN_...",
    "task_uid": 0,
    "wafer_id": "WAFER_0",
    "lot_id": "LOYM",
    "current_state": {"uid": 0, "location": "PROC_A_0"},
    "related_correlation_ids": ["CORR_..."],
    "assignments": [
        {
            "command_id": "CMD_...",
            "correlation_id": "CORR_...",
            "candidate_id": "CAND_...",
            "stage": "A",
            "equipment_id": "A_0",
            "task_uids": [0, 1, 2],
            "status": "EXECUTED",
            "trace_url": "/api/v2/assignment-trace?correlation_id=CORR_...&run_id=RUN_..."
        }
    ],
    "timeline": [
        {"event_type": "TASK_CREATED", "time": 0},
        {"event_type": "COMMAND_CREATED", "time": 0},
        {"event_type": "EQUIPMENT_STARTED", "time": 0},
        {"event_type": "COMMAND_EXECUTED", "time": 1}
    ],
    "assignment_trace": {
        "found": True,
        "correlation_id": "CORR_...",
        "command_id": "CMD_..."
    }
}
```

### Equipment Genealogy

```http
GET /api/v2/genealogy/equipment/{equipment_id}
```

Returns current equipment state, executed command summaries, and simulator
start/finish events for the tool.

### Lot Genealogy

```http
GET /api/v2/genealogy/lot/{lot_id}
```

Rolls task-level timelines up to the lot/job id from simulator task rows.

### Execution Ledger

```http
GET /api/v2/execution-ledger/{correlation_id}
```

Response includes:

- `command`: final `MESCommand`,
- `recommendations`: persisted L4/L3/L1/L2 recommendation records,
- `validations`: Rule Engine validation records,
- `records`: ordered event ledger, including `COMMAND_CREATED`,
  `RULE_VALIDATION_PASSED`, `COMMAND_EXECUTED`, and
  `SIMULATOR_ACTION_APPLIED`,
- `decision_state` and `post_state`,
- `assignment_trace_url`,
- `run_scoped_assignment_trace_url`.

### Digital Twin State At Time

```http
GET /api/v2/digital-twin/state-at?time=0&run_id=RUN_...
```

Returns the best available decision-state snapshot at or before the requested
time. V1 sources are feature snapshots, post-execution snapshots, and current
runtime state. This is a replayability contract, not a full event-sourced
reconstruction yet.

## API Evolution Rules

- Keep `/api/v1/*` stable for current UI.
- Add new candidate-portfolio endpoints without breaking existing harness APIs.
- Keep `/api/v2/*` simulation control endpoints as MVP runtime controls.
- Keep `/api/v2/ai-dev/*` as explicit development endpoints. They may replay
  frozen state, but they must not mutate the live simulator except scenario
  capture metadata stored on the API context.
- Do not expose direct simulator mutations except through validated commands or
  explicit development endpoints such as task generation/reset.
