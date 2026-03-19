# src/core/node_engine.py
import json
import math
import uuid
import re
import ast
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
            # Sort edges by target_handle to ensure consistent order
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
    def from_formula(cls, formula_str: str):
        """
        Advanced parser to convert a formula string back to a DAG.
        Supports: [ID], numeric constants, +, -, *, /, and parentheses.
        """
        dag = cls()
        out_node = KpiNode("OUTPUT_NODE", NodeType.OUTPUT, {}, {"x": 900, "y": 350})
        dag.add_node(out_node)
        
        if not formula_str: return dag

        # Pre-process: convert [ID] to a temporary variable name like KPI_ID
        processed_str = re.sub(r'\[(\d+)\]', r'KPI_\1', formula_str)
        
        try:
            tree = ast.parse(processed_str, mode='eval')
        except:
            return dag

        def walk(node, depth=0):
            if isinstance(node, ast.BinOp):
                left_id = walk(node.left, depth + 1)
                right_id = walk(node.right, depth + 1)
                
                op_map = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}
                op_char = op_map.get(type(node.op), "+")
                
                op_node_id = str(uuid.uuid4())
                pos = {"x": 700 - (depth * 150), "y": 100 + (len(dag.nodes) * 40)}
                
                op_node = KpiNode(op_node_id, NodeType.OPERATOR, {"op": op_char, "num_inputs": 2}, pos)
                dag.add_node(op_node)
                
                dag.add_edge(KpiEdge(str(uuid.uuid4()), left_id, op_node_id, "A"))
                dag.add_edge(KpiEdge(str(uuid.uuid4()), right_id, op_node_id, "B"))
                return op_node_id

            elif isinstance(node, ast.Name):
                if node.id.startswith("KPI_"):
                    kpi_id = int(node.id.replace("KPI_", ""))
                    node_id = f"node_kpi_{kpi_id}_{uuid.uuid4().hex[:4]}"
                    kpi_node = KpiNode(node_id, NodeType.KPI_INPUT, {"kpi_id": kpi_id, "kpi_name": f"KPI {kpi_id}"}, {"x": 50, "y": 100 + (len(dag.nodes) * 60)})
                    dag.add_node(kpi_node)
                    return node_id
            
            elif isinstance(node, (ast.Constant, getattr(ast, 'Num', type(None)))):
                val = node.value if hasattr(node, 'value') else node.n
                node_id = f"node_const_{uuid.uuid4().hex[:4]}"
                c_node = KpiNode(node_id, NodeType.CONSTANT, {"value": float(val)}, {"x": 50, "y": 100 + (len(dag.nodes) * 60)})
                dag.add_node(c_node)
                return node_id
            
            elif isinstance(node, ast.Expression):
                return walk(node.body, depth)
            
            return None

        root_id = walk(tree)
        if root_id:
            dag.add_edge(KpiEdge(str(uuid.uuid4()), root_id, "OUTPUT_NODE", "in"))
        
        return dag

    @classmethod
    def from_json(cls, json_str: str):
        if not json_str:
            return cls()
        data = json.loads(json_str)
        nodes = [KpiNode.from_dict(n) for n in data.get("nodes", [])]
        edges = [KpiEdge.from_dict(e) for e in data.get("edges", [])]
        return cls(nodes, edges)

    def evaluate(self, kpi_resolver_func, default_target_num: int = 1) -> float:
        output_node = next((n for n in self.nodes.values() if n.type == NodeType.OUTPUT), None)
        if not output_node:
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
            target_num = node.data.get("target_num", default_target_num)
            result = resolver(kpi_id, target_num)
        elif node.type in (NodeType.OPERATOR, NodeType.OUTPUT):
            inputs = []
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
        deps = []
        for node in self.nodes.values():
            if node.type == NodeType.KPI_INPUT:
                deps.append({
                    "kpi_id": node.data.get("kpi_id"),
                    "target_num": node.data.get("target_num", 1)
                })
        return deps

    def has_cycle(self) -> bool:
        visited = set()
        path = set()

        def visit(node_id):
            if node_id in path: return True
            if node_id in visited: return False
            
            visited.add(node_id)
            path.add(node_id)
            
            node_edges = [e for e in self.edges if e.target == node_id]
            for edge in node_edges:
                if visit(edge.source): return True
                
            path.remove(node_id)
            return False

        for node_id in self.nodes:
            if visit(node_id): return True
        return False

def check_for_global_circular_dependencies(kpis_data: Dict[int, Dict[str, Any]]) -> List[List[Any]]:
    graph = {}
    for kpi_id, data in kpis_data.items():
        # Check both target1 and target2 (legacy) or all targets in data_cache if needed
        # For global check, we usually look at kpi_specs
        formula = data.get("formula_json")
        if not formula: continue
        
        try:
            dag_data = json.loads(formula)
            if not (isinstance(dag_data, dict) and "nodes" in dag_data): continue
            dag = KpiDAG.from_json(formula)
            deps = dag.find_all_kpi_dependencies()
            graph[kpi_id] = [d['kpi_id'] for d in deps]
        except: continue

    cycles = []
    visited = set()
    path = []
    path_set = set()

    def dfs(node):
        if node in path_set:
            idx = path.index(node)
            cycles.append(path[idx:])
            return
        if node in visited: return
        
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
