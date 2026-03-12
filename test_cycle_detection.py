# test_cycle_detection.py
from src.core.node_engine import KpiDAG, KpiNode, KpiEdge, NodeType, check_for_global_circular_dependencies
import json

def test_internal_cycle():
    print("Testing Internal DAG Cycle Detection...")
    dag = KpiDAG()
    dag.add_node(KpiNode("n1", NodeType.OPERATOR, {"op": "+"}))
    dag.add_node(KpiNode("n2", NodeType.OPERATOR, {"op": "+"}))
    dag.add_edge(KpiEdge("e1", "n1", "n2"))
    dag.add_edge(KpiEdge("e2", "n2", "n1"))
    
    assert dag.has_cycle() == True
    print("Internal Cycle Detected correctly.")

def test_global_cycle():
    print("Testing Global inter-KPI Cycle Detection...")
    # KPI 1 depends on KPI 2
    dag1 = KpiDAG()
    dag1.add_node(KpiNode("n1", NodeType.KPI_INPUT, {"kpi_id": 2, "target_num": 1}))
    dag1.add_node(KpiNode("n2", NodeType.OUTPUT, {}))
    dag1.add_edge(KpiEdge("e1", "n1", "n2"))
    
    # KPI 2 depends on KPI 1
    dag2 = KpiDAG()
    dag2.add_node(KpiNode("n3", NodeType.KPI_INPUT, {"kpi_id": 1, "target_num": 1}))
    dag2.add_node(KpiNode("n4", NodeType.OUTPUT, {}))
    dag2.add_edge(KpiEdge("e2", "n3", "n4"))
    
    kpis_data = {
        1: {"target1_formula": dag1.to_json()},
        2: {"target1_formula": dag2.to_json()}
    }
    
    cycles = check_for_global_circular_dependencies(kpis_data)
    print(f"Detected Cycles: {cycles}")
    assert len(cycles) > 0
    print("Global Cycle Detected correctly.")

if __name__ == "__main__":
    test_internal_cycle()
    test_global_cycle()
    print("All cycle detection tests passed!")
