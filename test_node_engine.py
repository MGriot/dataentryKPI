# test_node_engine.py
from src.core.node_engine import KpiDAG, KpiNode, KpiEdge, NodeType
import json

def test_node_engine():
    print("Testing Node Engine Serialization & Evaluation...")
    
    # 1. Create a DAG manually
    # (Input KPI 1) --+
    #                 | [Op: +] --> (Output)
    # (Constant 10) --+
    
    dag = KpiDAG()
    dag.add_node(KpiNode("n1", NodeType.KPI_INPUT, {"kpi_id": 101, "target_num": 1}))
    dag.add_node(KpiNode("n2", NodeType.CONSTANT, {"value": 10.0}))
    dag.add_node(KpiNode("n3", NodeType.OPERATOR, {"op": "+"}))
    dag.add_node(KpiNode("n4", NodeType.OUTPUT, {}))
    
    dag.add_edge(KpiEdge("e1", "n1", "n3", "a"))
    dag.add_edge(KpiEdge("e2", "n2", "n3", "b"))
    dag.add_edge(KpiEdge("e3", "n3", "n4", "in"))
    
    # 2. Serialize
    json_data = dag.to_json()
    print("Serialized DAG:")
    print(json_data)
    
    # 3. Deserialize
    dag2 = KpiDAG.from_json(json_data)
    assert len(dag2.nodes) == 4
    assert len(dag2.edges) == 3
    print("Deserialization verified.")
    
    # 4. Evaluate
    def mock_resolver(kpi_id, target_num):
        if kpi_id == 101: return 50.0
        return 0.0
        
    result = dag2.evaluate(mock_resolver)
    print(f"Evaluation Result (50 + 10): {result}")
    assert result == 60.0
    
    # 5. Test another op (Division)
    dag_div = KpiDAG()
    dag_div.add_node(KpiNode("n1", NodeType.CONSTANT, {"value": 100.0}))
    dag_div.add_node(KpiNode("n2", NodeType.CONSTANT, {"value": 4.0}))
    dag_div.add_node(KpiNode("n3", NodeType.OPERATOR, {"op": "/"}))
    dag_div.add_node(KpiNode("n4", NodeType.OUTPUT, {}))
    dag_div.add_edge(KpiEdge("e1", "n1", "n3", "a")) # numerator
    dag_div.add_edge(KpiEdge("e2", "n2", "n3", "b")) # denominator
    dag_div.add_edge(KpiEdge("e3", "n3", "n4", "in"))
    
    result_div = dag_div.evaluate(mock_resolver)
    print(f"Evaluation Result (100 / 4): {result_div}")
    assert result_div == 25.0
    
    print("All tests passed!")

if __name__ == "__main__":
    test_node_engine()
