# A Spatial Quality Map V1 Design

Status: approved
Date: 2026-06-14

## 1. Goal

Process A currently produces one scalar QA value for each task:

```text
realized_qa_A = f(recipe, consumable usage u, machine age m_age, noise)
```

V1 extends this result into a deterministic spatial quality field so an
engineer can ask the MES Agent to show where local quality risk exists.

The extension must preserve the existing scalar contract. Existing scheduling,
APC, pass/fail, and regression behavior continue to use `realized_qa_A`.

## 2. Product Decision

The selected visualization is a product-surface or wafer-style quality map.
The map answers:

```text
1. Which locations are PASS, near the specification boundary, or OOS?
2. Can a scalar PASS still contain a local OOS cluster?
3. Which simulated process factor produced the spatial pattern?
4. What process action should an engineer investigate next?
```

The map is simulated evidence, not observed metrology. Every payload must use:

```text
source = SIMULATOR
evidence_type = SIMULATED_SPATIAL_QUALITY
```

## 3. Model

The existing scalar result is the spatial map mean:

```text
base = existing Process A scalar QA

q(x, y) =
    base
    + radial_component(x, y, m_age)
    + directional_component(x, y, recipe)
    + hotspot_component(x, y, u, task_seed)
    + local_noise(x, y, u, task_seed)
```

After generating the field, it is recentered so:

```text
mean(q(x, y)) == base
```

This preserves the current process model while adding local variation.

### 3.1 Determinism

The map seed is derived from stable input:

```text
task_uid + equipment_id + completion_time + model_version
```

The same completed task and model version must produce the same map.

### 3.2 Spatial components

| Component | Driver | Meaning |
|---|---|---|
| radial | `m_age` | increasing edge-to-center non-uniformity as equipment ages |
| directional | recipe balance | recipe-dependent gradient across the product |
| hotspot | `u` and stable seed | localized consumable-related degradation |
| local noise | `u` and stable seed | reproducible fine variation |

The model is intentionally synthetic. Coefficients are isolated in one module
so production metrology or a learned model can replace the implementation
without changing consumers.

## 4. Verdict

Each valid grid cell contains:

```json
{
  "x": -0.25,
  "y": 0.5,
  "value": 47.82,
  "verdict": "PASS",
  "margin": 2.82,
  "zone": "CENTER"
}
```

Verdicts:

- `PASS`: value is inside specification with sufficient margin.
- `MARGIN`: value is inside specification but close to either boundary.
- `OOS_LOW`: value is below the lower boundary.
- `OOS_HIGH`: value is above the upper boundary.

The margin threshold is derived from the specification width and remains
explicit in the response.

## 5. Summary Contract

```json
{
  "mean": 49.2,
  "std": 1.84,
  "minimum": 43.8,
  "maximum": 52.4,
  "oos_ratio": 0.073,
  "margin_ratio": 0.106,
  "edge_mean": 48.6,
  "center_mean": 49.5,
  "edge_center_delta": -0.9,
  "largest_oos_cluster": 6,
  "scalar_passed": true,
  "map_passed": false
}
```

`scalar_passed` preserves the current scalar verdict. `map_passed` requires no
OOS cells. The difference is intentionally visible.

## 6. Runtime Storage

Process A completion events receive a compact `spatial_quality` payload. Task
history receives the summary and model metadata, not a duplicated full grid.

```text
ProcessA_Env
  -> existing scalar QA
  -> spatial quality model
  -> completion event spatial_quality
  -> MES read-only query tool
  -> typed visual artifact
  -> Active Inspector
```

The environment remains responsible for simulated physics and quality
outcomes. Agent tools only read completed evidence.

## 7. Agent Tool

New tool:

```text
query_process_a_spatial_quality
```

Inputs:

```json
{
  "equipment_id": "LITHO-01",
  "task_uid": 184
}
```

Both fields are optional individually:

- equipment only: return its latest completed A map;
- task only: locate the completion record for that task;
- both: require both to match.

The tool is read-only and only supports Process A in V1. Requests for B/C fail
with a clear unsupported-operation error.

## 8. Visual Artifact

New artifact:

```text
artifact_type = process_a_spatial_quality
chart_type = spatial_quality_map
```

It contains:

- equipment and task identity;
- recipe and machine state;
- specification and scalar result;
- geometry and cells;
- map summary;
- component amplitudes and reason codes;
- model id/version/seed;
- simulator provenance.

The LLM cannot provide HTML, SVG, JavaScript, chart expressions, or colors.
The browser uses a built-in allowlisted renderer.

## 9. Active Inspector

The Chart tab renders:

- circular canonical product geometry;
- cell color by verdict;
- selected hotspot/OOS cell details;
- scalar versus map verdict;
- mean, standard deviation, OOS ratio, min/max, edge-center delta;
- model causes and recommended investigation.

The Data tab renders position-level rows. The Events tab renders map reason
codes such as:

```text
LOCAL_OOS_CLUSTER
EDGE_NON_UNIFORMITY
DIRECTIONAL_BIAS
CONSUMABLE_HOTSPOT
```

## 10. Boundaries

V1 does not:

- claim the map is measured FDC/metrology evidence;
- change Process A scalar pass/fail or rework behavior;
- add Process B spatial quality;
- train a learned model;
- issue recipe, maintenance, dispatch, or equipment commands;
- accept executable visualization definitions from the LLM.

## 11. Completion Criteria

1. A completion produces a deterministic spatial map whose mean matches the
   existing scalar QA within numerical tolerance.
2. Existing Process A pass/fail behavior remains unchanged.
3. The query tool resolves canonical and display equipment names.
4. A tool response creates a validated typed visual artifact.
5. Agent Mode can choose the tool from a natural-language map request.
6. Active Inspector renders the map, summary, cells, and reason evidence.
7. Simulator provenance is visible.
8. Existing full tests remain green.
