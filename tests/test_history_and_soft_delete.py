# tests/test_history_and_soft_delete.py
import pytest
from src.kpi_management import crud as kpi_crud
from src.services import history_service

pytestmark = pytest.mark.usefixtures("db_dir")

def test_kpi_creation_and_soft_delete():
    # 1. Create a root node
    node_id = kpi_crud.add_kpi_node(None, "Production Group")
    assert node_id > 0

    # 2. Create KPI indicator
    res = kpi_crud.create_kpi_indicator(
        node_id=node_id,
        name="Scrap Rate",
        description="Percentage of scrapped units",
        calculation_type="Average",
        unit_of_measure="%",
        owner="Quality Dept",
        direction="Lower is Better"
    )
    kpi_id = res["kpi_id"]
    assert kpi_id > 0

    # Verify present in tree
    tree = kpi_crud.get_kpi_tree()
    assert len(tree) == 1
    assert tree[0]["indicators"][0]["indicator_name"] == "Scrap Rate"

    # 3. Soft delete KPI
    success = kpi_crud.soft_delete_kpi(kpi_id, changed_by="test_admin")
    assert success is True

    # Verify omitted from active tree
    tree_after = kpi_crud.get_kpi_tree()
    assert len(tree_after[0]["indicators"]) == 0

    # 4. Check definition history log
    hist = history_service.get_definition_history(kpi_id)
    assert len(hist) >= 2  # CREATE and SOFT_DELETE
    change_types = [h["change_type"] for h in hist]
    assert "CREATE" in change_types
    assert "SOFT_DELETE" in change_types

def test_target_update_and_history():
    # Update target
    success = kpi_crud.update_target_value(
        plant_id=1,
        kpi_id=10,
        target_number=1,
        period_start="2026-01-01",
        period_end="2026-01-31",
        target_value=500.0,
        changed_by="planner"
    )
    assert success is True

    # Retrieve history log
    target_hist = history_service.get_target_history(kpi_id=10, plant_id=1)
    assert len(target_hist) == 1
    assert target_hist[0]["new_value"] == 500.0
    assert target_hist[0]["changed_by"] == "planner"


def test_resaving_identical_values_is_not_audited():
    node_id = kpi_crud.add_kpi_node(None, "Ops")
    kpi_id = kpi_crud.create_kpi_indicator(node_id=node_id, name="Units", unit_of_measure="pcs")["kpi_id"]
    assert kpi_crud.update_kpi_spec_extended(kpi_id, {"unit_of_measure": "t"}, changed_by="ann")
    assert kpi_crud.update_kpi_spec_extended(kpi_id, {"unit_of_measure": "t"}, changed_by="ann")  # no-op
    assert [h["change_type"] for h in history_service.get_definition_history(kpi_id)] == ["UPDATE", "CREATE"]
