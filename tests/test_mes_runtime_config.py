from src.mes.runtime.config import load_runtime_config
from src.mes.runtime.context import MESAPIContext
from src.mes.runtime.naming import equipment_display_name, stage_display_name


def test_runtime_config_loads_nested_yaml_as_manufacturing_env_config(tmp_path) -> None:
    config_path = tmp_path / "mes-runtime.yaml"
    config_path.write_text(
        """
name: Test MES Runtime
version: 0.1.0
schema: v1
simulator:
  num_machines:
    A: 2
    B: 1
    C: 1
  batch_size:
    A: 4
    B: 2
    C: 3
  process_time:
    A: 30
    B: 9
    C: 4
  max_packs_per_step: 2
  deterministic_mode: true
display:
  stages:
    A: Lithography QA
    B: Wet Clean QA
    C: Final Packing
  equipment:
    A_0: LITHO-X1
    A_1: LITHO-X2
    B_0: CLEAN-X1
    C_0: PACK-X1
""",
        encoding="utf-8",
    )

    config = load_runtime_config(config_path)

    assert config["num_machines_A"] == 2
    assert config["num_machines_B"] == 1
    assert config["num_machines_C"] == 1
    assert config["batch_size_A"] == 4
    assert config["process_time_A"] == 30
    assert config["max_packs_per_step"] == 2
    assert config["deterministic_mode"] is True
    assert config["stage_display_names"]["A"] == "Lithography QA"
    assert config["equipment_display_names"]["A_1"] == "LITHO-X2"


def test_runtime_context_uses_mes_runtime_config_env_var(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "mes.sqlite3"
    config_path = tmp_path / "runtime.yaml"
    config_path.write_text(
        """
simulator:
  num_machines:
    A: 1
    B: 1
    C: 1
display:
  stages:
    A: Custom A
    B: Custom B
    C: Custom C
  equipment:
    A_0: CUSTOM-A-01
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("MES_RUNTIME_CONFIG", str(config_path))
    monkeypatch.setenv("MES_DB_PATH", str(db_path))

    context = MESAPIContext()

    assert stage_display_name(context, "A") == "Custom A"
    assert equipment_display_name(context, "A_0") == "CUSTOM-A-01"
    assert len(context.operation_registry.equipment_for_operation("A")) == 1


def test_runtime_config_missing_file_falls_back_to_default_names(tmp_path) -> None:
    config = load_runtime_config(tmp_path / "missing.yaml")

    assert config["stage_display_names"]["A"] == "Lithography QA"
    assert config["equipment_display_names"]["A_0"] == "LITHO-01"
