# test_node_integration.py
import sqlite3
import json
import uuid
from src.target_management.annual import save_annual_targets
from src.core.node_engine import KpiDAG, KpiNode, KpiEdge, NodeType
from src.config import settings as app_config

def test_node_integration():
    print("Testing Node-Based Formula Integration in save_annual_targets...")
    
    year = 2026
    plant_id = 1
    kpi_input_id = 10
    kpi_output_id = 20
    
    # 1. Create a DAG for KPI 20: (KPI 10) * 2
    dag = KpiDAG()
    dag.add_node(KpiNode("n1", NodeType.KPI_INPUT, {"kpi_id": kpi_input_id, "target_num": 1}))
    dag.add_node(KpiNode("n2", NodeType.CONSTANT, {"value": 2.0}))
    dag.add_node(KpiNode("n3", NodeType.OPERATOR, {"op": "*"}))
    dag.add_node(KpiNode("n4", NodeType.OUTPUT, {}))
    dag.add_edge(KpiEdge("e1", "n1", "n3", "a"))
    dag.add_edge(KpiEdge("e2", "n2", "n3", "b"))
    dag.add_edge(KpiEdge("e3", "n3", "n4", "in"))
    
    node_formula_json = dag.to_json()
    
    # 2. Prepare targets_data_map
    targets_data = {
        str(kpi_input_id): {
            "annual_target1": 500.0,
            "is_target1_manual": True
        },
        str(kpi_output_id): {
            "target1_is_formula_based": True,
            "target1_formula": node_formula_json,
            "target1_formula_inputs": [
                {"kpi_id": kpi_input_id, "target_source": "annual_target1", "variable_name": "UNUSED_BY_NODE_ENGINE"}
            ]
        }
    }
    
    # 3. Call save_annual_targets
    save_annual_targets(year, plant_id, targets_data)
    
    # 4. Verify results
    db_targets_path = app_config.get_database_path("db_kpi_targets.db")
    with sqlite3.connect(db_targets_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT annual_target1, is_target1_manual FROM annual_targets WHERE year=? AND plant_id=? AND kpi_id=?",
            (year, plant_id, kpi_output_id)
        ).fetchone()
        
        print(f"Output KPI Value: {row['annual_target1']}")
        assert abs(row['annual_target1'] - 1000.0) < 1e-9
        assert not row['is_target1_manual']
        print("Node-Based Formula Integration Verified!")

if __name__ == "__main__":
    test_node_integration()
