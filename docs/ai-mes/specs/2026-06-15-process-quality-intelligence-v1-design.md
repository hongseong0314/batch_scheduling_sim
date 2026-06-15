# Process Quality Intelligence V1 Design

Status: approved for implementation  
Date: 2026-06-15

## 1. Objective

Process Quality Intelligence V1 turns the current Process A-only spatial
quality feature into an extensible process-quality subsystem.

The subsystem must:

- preserve the existing Process A scalar QA execution verdict;
- preserve `query_process_a_spatial_quality` as a compatibility tool;
- expose a common quality-evidence lookup for A and B;
- add a Process B cleaning-quality model with process-specific semantics;
- keep all simulator-derived maps explicitly labeled as synthetic evidence;
- allow future FDC, metrology, or learned providers to replace simulator
  implementations without changing Agent or UI contracts.

## 2. Design Principle

Quality evidence is process-specific, but its transport and inspection
contracts are common.

```text
process completion
-> process-specific quality provider
-> QualityEvidence envelope
-> provider registry
-> runtime query
-> Agent tool
-> typed visual artifact
-> Active Inspector
```

The common layer must not force Process B into Process A's wafer-pattern
meaning. A and B share lookup, provenance, summary, and rendering contracts,
while each provider owns its own model components and reason codes.

## 3. Common Quality Evidence Contract

Every provider returns:

```python
{
    "operation_id": "A",
    "quality_kind": "PROCESS_A_SPATIAL_QUALITY",
    "evidence_type": "SIMULATED_SPATIAL_QUALITY",
    "equipment_id": "A_0",
    "task_uid": 7,
    "completion_time": 20,
    "scalar_qa": 49.96,
    "scalar_verdict": "PASS",
    "map_verdict": "PASS",
    "geometry": {...},
    "spec": {...},
    "cells": [...],
    "summary": {...},
    "components": {...},
    "reason_codes": [...],
    "model": {
        "model_id": "...",
        "version": "...",
        "evidence_type": "...",
        "seed": 123
    }
}
```

Required common fields:

- stable operation, equipment, task, and completion identity;
- scalar and map verdicts kept separate;
- structured geometry, cells, summary, causes, and reasons;
- explicit source/model provenance;
- data-only content.

## 4. Provider Registry

`src/environment/process_quality/registry.py` owns provider lookup.

```python
provider = quality_provider_registry.get("A")
evidence = provider.generate(...)
```

V1 providers:

| Operation | Provider | Quality meaning |
|---|---|---|
| A | Process A spatial field | pattern/process uniformity and local OOS |
| B | Process B contamination field | residual contamination and cleaning uniformity |

The registry is intentionally small. It is not a plugin loader and does not
perform dynamic imports. Future production profiles may replace a registered
provider through config/factory wiring.

## 5. Process A Compatibility

The existing public function remains available:

```python
generate_process_a_spatial_quality(...)
```

It delegates to the registered A provider or shares its pure implementation.
Existing completion event fields remain:

```text
spatial_quality_maps
```

The new common event field is also written:

```text
quality_evidence
```

The legacy runtime query and tool remain aliases:

```text
query_process_a_spatial_quality
```

The new preferred tool is:

```text
query_process_quality_evidence
```

## 6. Process B Cleaning Quality Model

Process B currently produces one scalar `realized_qa_B`. V1 adds a synthetic
position-level residual contamination field without changing the scalar
pass/fail decision.

### 6.1 Inputs

- scalar B QA;
- `spec_b`;
- three-value cleaning recipe;
- solution usage `v`;
- equipment age `b_age`;
- task uid;
- equipment id;
- completion time.

### 6.2 Components

The deterministic model contains:

- `residual_baseline`: inverse representation of scalar cleaning quality;
- `edge_residue`: increases with equipment age;
- `flow_direction_bias`: derived from recipe imbalance;
- `solution_hotspot`: increases with solution usage;
- `local_noise`: deterministic small-scale variation.

The field is recentered so its mean quality equals the existing scalar B QA.
Cells retain the same higher-is-better QA orientation as `spec_b`, while UI
copy explains that lower cells represent higher residual contamination risk.

### 6.3 B Reason Codes

```text
RESIDUAL_CONTAMINATION_CLUSTER
EDGE_CLEANING_NON_UNIFORMITY
FLOW_DIRECTION_BIAS
SOLUTION_DEGRADATION_HOTSPOT
```

### 6.4 Verdict Boundary

`realized_qa_B` remains authoritative for simulator pass/rework.

The B map is explanatory evidence. A scalar pass may coexist with local map
risk, and the UI must show both verdicts.

## 7. Runtime Query

Preferred runtime contract:

```python
query_process_quality_evidence(
    context,
    *,
    operation_id: str | None = None,
    equipment_id: str | None = None,
    task_uid: int | None = None,
) -> dict[str, Any]
```

Resolution rules:

1. display equipment names resolve to canonical ids;
2. equipment id determines operation when supplied;
3. explicit operation must match equipment operation;
4. latest matching completion is returned;
5. absent evidence returns `found=false`;
6. unsupported operations raise an explicit error.

## 8. Agent And Artifact Contract

New read-only tool:

```text
query_process_quality_evidence
```

Arguments:

```json
{
  "operation_id": "B",
  "equipment_id": "CLEAN-01",
  "task_uid": 7
}
```

Existing A compatibility tool remains.

Preferred artifact:

```text
artifact_type = process_quality_evidence
chart_type = process_quality_map
```

The artifact contains a `quality_evidence` object. The renderer chooses
process-specific labels, legends, components, and reason explanations from
`quality_kind`.

The Agent receives only compact summaries after tool execution. Full cells and
artifacts remain in the API response and Agent Run record, not in the second
LLM prompt.

## 9. Active Inspector

The common renderer displays:

- scalar verdict and map verdict;
- circular position map;
- mean, standard deviation, OOS ratio, min/max, edge-center delta, largest
  cluster;
- process-specific component values;
- process-specific reason cards;
- data rows and reason events;
- source, time basis, evidence type, model id, version, and tool.

A title example:

```text
LITHO-01 · Task 7 · Pattern Quality
CLEAN-01 · Task 7 · Residual Cleaning Quality
```

## 10. Safety And Provenance

V1 evidence types:

```text
SIMULATED_SPATIAL_QUALITY
SIMULATED_CLEANING_QUALITY
```

The UI and API must not imply measured FDC or metrology evidence.

No tool in this feature mutates:

- simulator state;
- recipes;
- dispatch;
- equipment;
- action proposals.

## 11. Testing

Required coverage:

- provider registry rejects unknown operations;
- common envelope validates A and B evidence;
- A deterministic output and mean compatibility remain unchanged;
- A legacy query/tool/artifact still work;
- B deterministic output and scalar mean match;
- B scalar verdict remains unchanged by map risk;
- B completion events contain full and compact evidence;
- common runtime query resolves canonical and display names;
- Agent catalog exposes common and compatibility tools;
- common artifact validation rejects executable content;
- UI mounts common map renderer and process-specific copy;
- real Gemma chooses the common B tool from a natural-language request;
- complete test suite remains green.

## 12. Non-Goals

V1 does not:

- ingest real FDC/metrology data;
- modify A or B scalar physics;
- change pass/rework decisions;
- add Process C spatial quality;
- train a quality model;
- add write-capable Agent tools;
- add dynamic third-party plugins.
