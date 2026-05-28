# Runtime Config

Status: canonical production-transition specification  
Last updated: 2026-05-25

## Purpose

Runtime Config V1 moves simulator and display settings out of Python code and
into `config/mes-runtime.yaml`.

This is a transition step toward production operation insertion. The simulator
still uses canonical ids such as `A`, `B`, `C`, `A_0`, `B_0`, and `C_0`, but
process names, equipment names, batch sizes, process times, and machine counts
can now be changed without editing `MESAPIContext`.

## Config Location

Default:

```text
config/mes-runtime.yaml
```

Override:

```bash
MES_RUNTIME_CONFIG=/path/to/mes-runtime.yaml
```

Loader:

```text
src/mes/runtime/config.py
```

Runtime owner:

```text
src/mes/runtime/context.py
```

## V1 Shape

```yaml
name: MES Runtime
version: 0.1.0
schema: v1

simulator:
  num_machines:
    A: 5
    B: 3
    C: 3
  batch_size:
    A: 3
    B: 2
    C: 4
  process_time:
    A: 20
    B: 8
    C: 2
  max_packs_per_step: 3
  deterministic_mode: true

display:
  stages:
    A: Lithography QA
    B: Wet Clean QA
    C: Final Packing
  equipment:
    A_0: LITHO-01
    A_1: LITHO-02
    B_0: CLEAN-01
    C_0: PACK-01
```

The loader normalizes this friendly shape into the existing `ManufacturingEnv`
flat keys:

```python
{
    "num_machines_A": 5,
    "batch_size_A": 3,
    "process_time_A": 20,
    "stage_display_names": {"A": "Lithography QA"},
    "equipment_display_names": {"A_0": "LITHO-01"}
}
```

## Boundary

Display names are metadata. They must not replace canonical ids.

| Purpose | Uses canonical id | Uses display name |
|---|---:|---:|
| Policy decisions | yes | no |
| Rule Engine validation | yes | no |
| Simulator action payload | yes | no |
| Genealogy lookup | yes | optional label |
| UI labels | no | yes |
| Operator-facing text | no | yes |

This lets the current simulator remain stable while future production adapters
map real operation and equipment names into the registry.

## Future Extensions

Runtime Config V1 intentionally stays small. Later production work should add:

- route/equipment master import into `operations` and `equipment`,
- config validation with field-level error messages,
- hot reload or admin update workflow,
- per-operation policy binding in config,
- production profile selection for dev/stage/prod environments.
