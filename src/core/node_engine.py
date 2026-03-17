# src/core/node_engine.py
import json
import math
from typing import Dict, List, Any, Optional

class NodeType:
    KPI_INPUT = "kpi_input"
    CONSTANT = "constant"
    OPERATOR = "operator"
    OUTPUT = "output"

class KpiNode:
    def __init__(self, node_id: str, node_type: str, data: Dict[str, Any], position: Dict[str, float] = None):
        self.id = node_id
        self.type = node_type
        self.data = data
        self.position = position or {"x": 0, "y": 0}

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "data": self.data,
            "position": self.position
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]):
        return cls(d["id"], d["type"], d["data"], d.get("position"))

class KpiEdge:
    def __init__(self, edge_id: str, source: str, target: str, target_handle: str = "in"):
        self.id = edge_id
        self.source = source
        self.target = target
        self.target_handle = target_handle

    def to_dict(self):
        return {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "target_handle": self.target_handle
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]):
        return cls(d["id"], d["source"], d["target"], d.get("target_handle", "in"))

class KpiDAG:
    def __init__(self, nodes: List[KpiNode] = None, edges: List[KpiEdge] = None):
        self.nodes: Dict[str, KpiNode] = {n.id: n for n in (nodes or [])}
        self.edges: List[KpiEdge] = edges or []

    def add_node(self, node: KpiNode):
        self.nodes[node.id] = node

    def add_edge(self, edge: KpiEdge):
        self.edges.append(edge)

    def to_json(self) -> str:
        return json.dumps({
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges]
        }, indent=2)

    def to_formula(self) -> str:
        """
        Converts the DAG structure into a Python-like formula string.
        Uses [ID] syntax for KPI inputs.
        """
        output_node = next((n for n in self.nodes.values() if n.type == NodeType.OUTPUT), None)
        if not output_node:
            return ""
        
        memo = {}
        return self._to_formula_recursive(output_node.id, memo)

    @classmethod
    def from_formula(cls, formula_str: str):
        """
        Simple parser to convert a formula string back to a DAG.
        Note: This is a basic implementation supporting simple expressions.
        """
        import re
        dag = cls()
        out_node = KpiNode("OUTPUT_NODE", NodeType.OUTPUT, {}, {"x": 900, "y": 350})
        dag.add_node(out_node)
        
        if not formula_str: return dag

        # 1. Identify all [ID] patterns
        pattern = r'\[(\d+)\]'
        kpi_ids = list(set(re.findall(pattern, formula_str)))
        
        kpi_nodes = {}
        for i, kid in enumerate(kpi_ids):
            node_id = f"kpi_{kid}"
            node = KpiNode(node_id, NodeType.KPI_INPUT, {"kpi_id": int(kid), "kpi_name": f"KPI {kid}"}, {"x": 50, "y": 50 + i*100})
            dag.add_node(node)
            kpi_nodes[kid] = node_id

        # 2. For now, since parsing arbitrary nested logic back to nodes is complex,
        # if it's a string formula, we often just keep it as a string in the spec.
        # But to show 'something' in the editor, we link all detected KPIs to a single operator.
        if kpi_ids:
            op_node = KpiNode("op_main", NodeType.OPERATOR, {"op": "+", "num_inputs": len(kpi_ids)}, {"x": 400, "y": 300})
            dag.add_node(op_node)
            for i, kid in enumerate(kpi_ids):
                dag.add_edge(KpiEdge(str(uuid.uuid4()), kpi_nodes[kid], "op_main", f"In {i+1}"))
            dag.add_edge(KpiEdge(str(uuid.uuid4()), "op_main", "OUTPUT_NODE", "in"))
        
        return dag

    def _to_formula_recursive(self, node_id: str, memo: Dict[str, str]) -> str:
        if node_id in memo:
            return memo[node_id]

        node = self.nodes.get(node_id)
        if not node:
            return "0"

        result = ""
        if node.type == NodeType.CONSTANT:
            result = str(node.data.get("value", 0.0))
        elif node.type == NodeType.KPI_INPUT:
            kpi_id = node.data.get("kpi_id")
            result = f"[{kpi_id}]"
        elif node.type in (NodeType.OPERATOR, NodeType.OUTPUT):
            inputs = []
            node_edges = [e for e in self.edges if e.target == node_id]
            node_edges.sort(key=lambda e: e.target_handle)
            
            for edge in node_edges:
                inputs.append(self._to_formula_recursive(edge.source, memo))

            if node.type == NodeType.OUTPUT:
                result = inputs[0] if inputs else "0"
            else:
                op = node.data.get("op", "+")
                if not inputs:
                    result = "0"
                elif op == "+":
                    result = f"({' + '.join(inputs)})"
                elif op == "-":
                    if len(inputs) > 1:
                        result = f"({inputs[0]} - {' - '.join(inputs[1:])})"
                    else:
                        result = f"(-{inputs[0]})"
                elif op == "*":
                    result = f"({' * '.join(inputs)})"
                elif op == "/":
                    result = f"({inputs[0]} / {inputs[1]})" if len(inputs) >= 2 else f"({inputs[0]})"
                elif op == "pow":
                    result = f"({inputs[0]} ** {inputs[1]})" if len(inputs) >= 2 else f"({inputs[0]})"
                else: # min, max, avg
                    result = f"{op}({', '.join(inputs)})"

        memo[node_id] = result
        return result

    @classmethod
    def from_json(cls, json_str: str):
        if not json_str:
            return cls()
        data = json.loads(json_str)
        nodes = [KpiNode.from_dict(n) for n in data.get("nodes", [])]
        edges = [KpiEdge.from_dict(e) for e in data.get("edges", [])]
        return cls(nodes, edges)

    def evaluate(self, kpi_resolver_func, default_target_num: int = 1) -> float:
        """
        Evaluates the DAG starting from the 'output' node.
        kpi_resolver_func: callable(kpi_id, target_num) -> float
        """
        output_node = next((n for n in self.nodes.values() if n.type == NodeType.OUTPUT), None)
        if not output_node:
            print("ERROR: No output node found in DAG.")
            return 0.0
        
        memo = {}
        return self._evaluate_recursive(output_node.id, kpi_resolver_func, memo, default_target_num)

    def _evaluate_recursive(self, node_id: str, resolver, memo: Dict[str, float], default_target_num: int) -> float:
        if node_id in memo:
            return memo[node_id]

        node = self.nodes.get(node_id)
        if not node:
            return 0.0

        result = 0.0
        if node.type == NodeType.CONSTANT:
            result = float(node.data.get("value", 0.0))
        elif node.type == NodeType.KPI_INPUT:
            kpi_id = node.data.get("kpi_id")
            # Use specific target_num if defined in node, otherwise use the global default for this evaluation
            target_num = node.data.get("target_num", default_target_num)
            result = resolver(kpi_id, target_num)
        elif node.type in (NodeType.OPERATOR, NodeType.OUTPUT):
            # Get inputs for this node
            inputs = []
            # Sort edges by target_handle to ensure consistent order for non-commutative ops (like subtraction)
            # Standard handles: "a", "b" or "in1", "in2"
            node_edges = [e for e in self.edges if e.target == node_id]
            node_edges.sort(key=lambda e: e.target_handle)
            
            for edge in node_edges:
                inputs.append(self._evaluate_recursive(edge.source, resolver, memo, default_target_num))

            if node.type == NodeType.OUTPUT:
                result = inputs[0] if inputs else 0.0
            else:
                op = node.data.get("op", "+")
                result = self._apply_operator(op, inputs)

        memo[node_id] = result
        return result

    def _apply_operator(self, op: str, inputs: List[float]) -> float:
        if not inputs:
            return 0.0
        
        if op == "+":
            return sum(inputs)
        elif op == "-":
            return inputs[0] - sum(inputs[1:]) if len(inputs) > 1 else -inputs[0]
        elif op == "*":
            res = 1.0
            for i in inputs: res *= i
            return res
        elif op == "/":
            if len(inputs) < 2 or abs(inputs[1]) < 1e-12:
                return 0.0
            return inputs[0] / inputs[1]
        elif op == "pow":
            if len(inputs) < 2: return inputs[0]
            return math.pow(inputs[0], inputs[1])
        elif op == "min":
            return min(inputs)
        elif op == "max":
            return max(inputs)
        elif op == "avg":
            return sum(inputs) / len(inputs)
        
        return 0.0

    def find_all_kpi_dependencies(self) -> List[Dict[str, Any]]:
        """Returns a list of all KPI dependencies in this DAG."""
        deps = []
        for node in self.nodes.values():
            if node.type == NodeType.KPI_INPUT:
                deps.append({
                    "kpi_id": node.data.get("kpi_id"),
                    "target_num": node.data.get("target_num", 1)
                })
        return deps

    def has_cycle(self) -> bool:
        """Checks if the internal DAG has a cycle."""
        visited = set()
        path = set()

        def visit(node_id):
            if node_id in path: return True
            if node_id in visited: return False
            
            visited.add(node_id)
            path.add(node_id)
            
            # Follow edges backwards (from target to source)
            node_edges = [e for e in self.edges if e.target == node_id]
            for edge in node_edges:
                if visit(edge.source): return True
                
            path.remove(node_id)
            return False

        for node_id in self.nodes:
            if visit(node_id): return True
        return False

def check_for_global_circular_dependencies(kpis_data: Dict[int, Dict[str, Any]]) -> List[List[Any]]:
    """
    Checks a collection of KPIs for inter-KPI circular dependencies.
    kpis_data: mapping of kpi_id -> { "target1_formula": json_str, "target2_formula": json_str, ... }
    Returns a list of cycles (list of (kpi_id, target_num) tuples).
    """
    # Build a graph where nodes are (kpi_id, target_num)
    # and edges are "depends on"
    graph = {} # (kpi_id, target_num) -> list of (dep_kpi_id, dep_target_num)
    
    for kpi_id, data in kpis_data.items():
        for tn in [1, 2]:
            formula = data.get(f"target{tn}_formula")
            if not formula: continue
            
            # Check if it's a DAG
            try:
                dag_data = json.loads(formula)
                if not (isinstance(dag_data, dict) and "nodes" in dag_data): continue
                dag = KpiDAG.from_json(formula)
                deps = dag.find_all_kpi_dependencies()
                graph[(kpi_id, tn)] = [(d['kpi_id'], d['target_num']) for d in deps]
            except Exception:
                continue

    cycles = []
    visited = set()
    path = []
    path_set = set()

    def dfs(node):
        if node in path_set:
            # Cycle detected
            idx = path.index(node)
            cycles.append(path[idx:])
            return
        if node in visited:
            return
        
        visited.add(node)
        path.append(node)
        path_set.add(node)
        
        for neighbor in graph.get(node, []):
            dfs(neighbor)
            
        path.pop()
        path_set.remove(node)

    for node in list(graph.keys()):
        dfs(node)
        
    return cycles
