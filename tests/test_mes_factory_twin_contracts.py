import pytest
from pydantic import ValidationError

from src.mes.factory_twin.contracts import FactoryTwinLayoutV1, SpatialEntityV1


def test_layout_contract_rejects_broken_operation_reference():
    with pytest.raises(ValidationError):
        FactoryTwinLayoutV1(
            layout_id="LAYOUT_TEST",
            spatial_source="AUTO_LAYOUT",
            operations=[],
            equipment=[
                SpatialEntityV1(
                    id="X_0",
                    entity_type="equipment",
                    display_name="X",
                    position=[0, 0, 0],
                    size=[1, 1, 1],
                    operation_id="X",
                )
            ],
            queues=[],
            routes=[],
            warehouse=SpatialEntityV1(
                id="WAREHOUSE_FINISHED",
                entity_type="warehouse",
                display_name="Warehouse",
                position=[1, 0, 0],
                size=[1, 1, 1],
            ),
            bounds={"min": [0, 0, 0], "max": [1, 1, 1]},
        )
