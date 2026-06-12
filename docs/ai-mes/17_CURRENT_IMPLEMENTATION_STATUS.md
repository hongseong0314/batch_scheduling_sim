# Current Implementation Status

Status: canonical implementation snapshot
Last updated: 2026-05-31

## Reader

Primary reader: everyone who needs a quick factual snapshot of what is
implemented now and what remains a production gap.

Use this before planning new work, reviewing branch scope, or explaining the
current product maturity level.

Read after: [01_ARCHITECTURE_FLOW_GUIDE.md](01_ARCHITECTURE_FLOW_GUIDE.md) or
after any deeper document when checking implementation status.

## Purpose

This document answers one question:

```text
What is implemented today, and what is still a production-transition gap?
```

It is intentionally separate from [00_INDEX.md](00_INDEX.md) so the index stays
focused on navigation.

## Current Maturity Map

```mermaid
flowchart LR
  Done["Implemented today"] --> Sim["simulator-backed MES"]
  Done --> Trace["traceability and AI dev console"]
  Done --> Agent["read-only LLM process agent"]
  Done --> Boundary["action proposal boundary"]

  Gap["Remaining production gaps"] --> Auth["auth/roles/security"]
  Gap --> Ops["operator approval and legacy submission"]
  Gap --> DataOps["scheduled adapters/backfills"]
  Gap --> DB["normalized production DB"]
  Gap --> Learning["learning policy training/deployment"]
```

Read this diagram as the maturity boundary: the AI MES has a strong simulator
and production-transition skeleton, but it is not yet a deployable autonomous
manufacturing control system.

## Implemented Today

| Area | Implemented capability |
|---|---|
| Simulator kernel | `ManufacturingEnv`, `ProcessA_Env`, `ProcessB_Env`, `ProcessC_Env` |
| Local policies | A/B schedulers, A/B tuners, C packers |
| Policy factory | Config-built L1/L2/L3/L4 stack through `src/agents/factory.py` |
| L1/L2/L3/L4 chain | `L1 portfolio -> L2 annotations -> L4 objective -> L3 selection -> L1 finalization -> L2 finalization` |
| Rule Engine | Layer consistency validation and command creation |
| Harness | Planner, generator, evaluator, DTO artifacts under `src/mes/harnessing/` |
| Runtime APIs | Live state, Gantt, equipment detail, decision chain, assignment trace, genealogy, candidate portfolio, AI dev, experiments |
| Store | In-memory store plus SQLite JSON payload and normalized ledger indexes |
| UI | `/mes` control room with Fab, Flow/Gantt, Equipment, Machine Detail, Decision Chain, Assignment Trace, Candidate Portfolio, AI Dev Console, Chat, Events |
| Agent tools | Read-only MES/APC chat agent with Continue-style config, Ollama/OpenAI-compatible providers, tool-use loop, agent run inspector |
| Production boundary | Operation registry, source key mapping, ingestion contracts, production schema/data-quality diagnostics, canonical twin replay/genealogy, action proposal boundary, review-gated proposal workflow |

## Current Default Policy Stack

| Layer | Current policy id | Current role |
|---|---|---|
| L1 | `L1_FIFO_BASELINE` | Local dispatch/packing baseline |
| L2 | `L2_RULE_BASED_APC` | Rule-based APC/process annotation |
| L3 | `L3_CANDIDATE_PORTFOLIO_RULE` | Cross-process candidate portfolio scoring |
| L4 | `L4_CYCLE_WEIGHT_RULE` | Cycle-level objective weighting |

## Current Simulator Baseline

```text
A: 5 tools, batch_size=3, process_time=20
B: 3 tools, batch_size=2, process_time=8
C: 3 tools, batch_size=4, process_time=2, max_packs_per_step=3
```

Display names are configurable through `config/mes-runtime.yaml` and
`MES_RUNTIME_CONFIG`; canonical simulator ids remain stable state/action keys.

## Production-Transition Capabilities

Implemented V1 production-transition surfaces:

- operation/equipment registry,
- legacy-safe `ActionProposal` records with `direct_equipment_control=false`,
- source key mapping,
- raw source and canonical ingestion records,
- canonical production schema contract endpoint,
- source data quality diagnostics,
- canonical digital twin replay and policy-ready decision state,
- canonical entity genealogy with raw evidence,
- canonical twin recommendation run into action proposal,
- source-specific legacy adapter examples,
- decision dataset and policy evaluation summary APIs,
- approval queue and action proposal review records,
- recommendation lifecycle feedback summaries,
- production readiness diagnostics.

## Not Implemented Yet

The system is not yet production-deployable as an autonomous or write-capable
manufacturing system.

Remaining gaps:

- production action-proposal outbox submission integration,
- legacy MES acceptance/rejection/modification outcome ingestion at production
  scale,
- production reservation locks and role-enforced operator approval workflows,
- auth, roles, and tenant/security model,
- normalized PostgreSQL schema and migrations,
- source adapter scheduling/backfill jobs through Airflow, Cron, or a similar
  orchestration layer,
- primary event-sourced digital twin replacing simulator state for live runtime,
- source data quality dashboard and alerting workflows,
- learning-based policy training and model deployment,
- production MES/RMS/FDC/ERP adapters hardened against late, duplicate, missing,
  and conflicting source events.

## Current Boundary

The most important boundary remains:

```text
AI MES may recommend and explain.
Legacy MES remains responsible for execution authority.
```

Any future write-capable workflow should route through:

```text
Recommendation
-> Rule Engine
-> ActionProposal
-> operator or auto-gated approval
-> legacy MES acceptance
-> observed execution outcome
```
