# Production MES V1 Goals

Status: canonical implementation summary  
Last updated: 2026-05-28

## Goal

Production MES V1 connects the simulator-born AI MES architecture to a
legacy-safe production integration path. It does not replace legacy MES control.
It turns production-shaped data into canonical state, runs the AI policy stack,
creates action proposals, and records feedback for evaluation.

## Implemented V1 Axes

### 1. Canonical Twin Recommendation Runner

Endpoint:

```http
POST /api/v2/digital-twin/recommendation-run
```

Flow:

```text
CanonicalIngestionRecord
-> CANONICAL_TWIN decision_state
-> L4/L3/L1/L2 policy stack
-> Rule Engine
-> MESCommand
-> ActionProposal
```

The runner is read-only with respect to the live simulator. It records audit
artifacts and returns an action proposal with
`direct_equipment_control=false`.

### 2. Source-Specific Legacy Adapters

Endpoints:

```http
GET /api/v2/legacy-adapters
POST /api/v2/legacy-adapters/{adapter_id}/ingest
```

Initial adapters:

- `legacy_mes_wip_unit`
- `legacy_mes_equipment`
- `fdc_quality_event`
- `rms_recipe`

Each adapter maps a source row into the generic ingestion contract:

```text
source row -> RawSourceRecord -> CanonicalIngestionRecord -> SourceKeyMapping
```

### 3. Dynamic Operation / Route Generalization

Endpoint:

```http
GET /api/v2/operations/route-graph
```

The operation registry now exposes a route graph with operation nodes,
downstream edges, and equipment grouped by operation. This keeps A/B/C as
defaults while allowing production operation ids from config or master data.

### 4. Recommendation Lifecycle Feedback Loop

Endpoint:

```http
GET /api/v2/action-proposals/{proposal_id}/feedback-summary
```

The feedback summary links:

- proposed equipment/units,
- legacy MES accept/modify/reject decision,
- actual equipment/units,
- execution/quality outcome,
- learning/evaluation usability signal.

### 5. Policy Evaluation Platform V2

Canonical twin scenarios can be captured and replayed through existing policy
variant experiments.

Endpoint:

```http
POST /api/v2/ai-dev/scenarios/capture-canonical
POST /api/v2/ai-dev/experiments/run
```

This lets policy variants compare against the same production-shaped
`CANONICAL_TWIN` state rather than only simulator state.

### 6. Production Persistence / Deployment Hardening

Endpoint:

```http
GET /api/v2/production-readiness
```

The readiness payload reports:

- persistence backend,
- schema version,
- normalized indexes,
- idempotent surfaces,
- direct-equipment-control boundary,
- read-only LLM/tool default,
- production integration endpoints.

## Current Boundary

Production MES V1 still does not:

- submit commands directly to equipment,
- replace legacy MES scheduling or dispatch engines,
- implement production PostgreSQL,
- provide auth/roles,
- run source adapters on Airflow/Cron schedules,
- train learning-based policies.

Those are next-phase deployment tasks.
