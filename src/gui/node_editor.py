# src/gui/node_editor.py
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import uuid
import json
from typing import Dict, List, Optional, Any
from src.core.node_engine import KpiDAG, KpiNode, KpiEdge, NodeType

class NodeEditorDialog(tk.Toplevel):
    def __init__(self, parent, initial_json: str = None, kpi_list: list = None):
        super().__init__(parent)
        self.title("Visual KPI Formula Editor")
        self.geometry("1100x800")
        
        self.kpi_list = kpi_list or []
        self.dag = KpiDAG.from_json(initial_json) if initial_json else KpiDAG()
        
        # UI State
        self.nodes_ui = {} # node_id -> { 'rect': id, 'text': id, 'sockets': { 'in': [ids], 'out': id } }
        self.edges_ui = {} # edge_id -> line_id
        self.drag_data = {"item": None, "x": 0, "y": 0, "node_id": None}
        self.conn_data = {"active": False, "start_node": None, "start_socket_type": None, "line": None}
        self.selected_node = None
        self.selected_edge = None
        
        self._setup_ui()
        self._load_dag()

    def _setup_ui(self):
        toolbar = ttk.Frame(self)
        toolbar.pack(side="top", fill="x", padx=5, pady=5)
        
        ttk.Button(toolbar, text="+ KPI Input", command=self._add_kpi_input_node).pack(side="left", padx=2)
        ttk.Button(toolbar, text="+ Constant", command=self._add_constant_node).pack(side="left", padx=2)
        ttk.Button(toolbar, text="+ Operator", command=self._add_operator_node).pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Button(toolbar, text="Delete Selected", command=lambda: self._on_delete_key(None)).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Clear All", command=self._clear_canvas).pack(side="left", padx=2)
        
        ttk.Button(toolbar, text="SAVE FORMULA", command=self._on_save, style="Action.TButton").pack(side="right", padx=5)
        
        # Canvas with scrollbars
        self.canvas_frame = ttk.Frame(self)
        self.canvas_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg="#F8F9FA", highlightthickness=1, highlightbackground="#DEE2E6")
        self.canvas.pack(fill="both", expand=True)
        
        # Bindings
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.bind("<Delete>", self._on_delete_key)
        self.bind("<BackSpace>", self._on_delete_key)
        self.canvas.focus_set()

    def _load_dag(self):
        self.canvas.delete("all")
        self.nodes_ui.clear()
        self.edges_ui.clear()

        # Ensure there's an Output node
        if not any(n.type == NodeType.OUTPUT for n in self.dag.nodes.values()):
            out_node = KpiNode("OUTPUT_NODE", NodeType.OUTPUT, {}, {"x": 900, "y": 350})
            self.dag.add_node(out_node)

        for node in self.dag.nodes.values():
            self._draw_node(node)
        
        for edge in self.dag.edges:
            self._draw_edge(edge)

    def _draw_node(self, node: KpiNode):
        x, y = node.position["x"], node.position["y"]
        w, h = 150, 80
        
        # Color mapping
        colors = {
            NodeType.KPI_INPUT: {"bg": "#E3F2FD", "border": "#2196F3"},
            NodeType.CONSTANT: {"bg": "#F3E5F5", "border": "#9C27B0"},
            NodeType.OPERATOR: {"bg": "#FFF9C4", "border": "#FBC02D"},
            NodeType.OUTPUT: {"bg": "#E8F5E9", "border": "#4CAF50"}
        }
        cfg = colors.get(node.type, {"bg": "#FFFFFF", "border": "#333"})
        
        # Main Rectangle
        rect = self.canvas.create_rectangle(x, y, x+w, y+h, fill=cfg["bg"], outline=cfg["border"], width=2, tags=("node", node.id))
        
        # Title/Label
        title = node.type.replace("_", " ").title()
        if node.type == NodeType.KPI_INPUT:
            title = f"KPI: {node.data.get('kpi_name', 'Unknown')}"
        elif node.type == NodeType.CONSTANT:
            title = f"Const: {node.data.get('value', 0)}"
        elif node.type == NodeType.OPERATOR:
            title = f"Op: {node.data.get('op', '+')}"
            
        text = self.canvas.create_text(x + w/2, y + h/2, text=title, width=w-20, justify="center", font=("Helvetica", 9, "bold"), tags=("node", node.id))
        
        # Sockets
        sockets = {"in": {}, "out": None}
        
        # Output Socket (Right)
        if node.type != NodeType.OUTPUT:
            out_y = y + h/2
            s_id = self.canvas.create_oval(x+w-6, out_y-6, x+w+6, out_y+6, fill="#333", tags=("socket", "out", node.id))
            sockets["out"] = s_id
            
        # Input Sockets (Left)
        if node.type in (NodeType.OPERATOR, NodeType.OUTPUT):
            in_labels = self._get_input_labels(node)
            for i, label in enumerate(in_labels):
                spacing = h / (len(in_labels) + 1)
                in_y = y + (i + 1) * spacing
                s_id = self.canvas.create_oval(x-6, in_y-6, x+6, in_y+6, fill="#333", tags=("socket", "in", node.id, label))
                self.canvas.create_text(x + 10, in_y, text=label, anchor="w", font=("Helvetica", 7), tags=("node", node.id))
                sockets["in"][label] = s_id

        self.nodes_ui[node.id] = {"rect": rect, "text": text, "sockets": sockets}

    def _get_input_labels(self, node: KpiNode) -> List[str]:
        if node.type == NodeType.OUTPUT:
            return ["Result"]
        
        op = node.data.get("op", "+")
        if op in ("/", "pow"):
            return ["A (Num/Base)", "B (Den/Exp)"]
        elif op == "-":
            return ["A", "B"]
        else:
            return ["In 1", "In 2", "In 3"] # Default multi-input

    def _draw_edge(self, edge: KpiEdge):
        coords = self._get_edge_coords(edge)
        if not coords: return
        line = self.canvas.create_line(*coords, arrow=tk.LAST, width=2, fill="#666", smooth=True, tags=("edge", edge.id))
        self.edges_ui[edge.id] = line

    def _get_edge_coords(self, edge: KpiEdge):
        source_ui = self.nodes_ui.get(edge.source)
        target_ui = self.nodes_ui.get(edge.target)
        if not source_ui or not target_ui: return None
        
        # Get actual socket coordinates
        out_socket = source_ui["sockets"]["out"]
        in_socket = target_ui["sockets"]["in"].get(edge.target_handle)
        
        if not out_socket or not in_socket:
            # Fallback if handle name changed
            if target_ui["sockets"]["in"]:
                in_socket = list(target_ui["sockets"]["in"].values())[0]
            else:
                return None

        s_box = self.canvas.coords(out_socket)
        t_box = self.canvas.coords(in_socket)
        
        return (s_box[0]+6, s_box[1]+6, t_box[0]+6, t_box[1]+6)

    def _on_canvas_click(self, event):
        self.canvas.focus_set()
        
        # Deselect previous
        if self.selected_node:
            self.canvas.itemconfig(self.nodes_ui[self.selected_node]["rect"], width=2)
        if self.selected_edge:
            self.canvas.itemconfig(self.edges_ui[self.selected_edge], fill="#666")
            
        self.selected_node = None
        self.selected_edge = None

        item = self.canvas.find_closest(event.x, event.y)
        tags = self.canvas.gettags(item)
        
        if "node" in tags:
            node_id = tags[1]
            self.selected_node = node_id
            self.canvas.itemconfig(self.nodes_ui[node_id]["rect"], width=4) # Highlight
            self.drag_data = {"item": item, "x": event.x, "y": event.y, "node_id": node_id}
            self.canvas.tag_raise(node_id)
            # Ensure text and sockets stay on top
            self.canvas.tag_raise(f"socket and {node_id}")
        elif "socket" in tags:
            if "out" in tags:
                # Start connection
                coords = self.canvas.coords(item)
                cx, cy = (coords[0]+coords[2])/2, (coords[1]+coords[3])/2
                self.conn_data = {
                    "active": True, 
                    "start_node": tags[2], 
                    "start_socket_type": "out",
                    "line": self.canvas.create_line(cx, cy, cx, cy, width=2, fill="#999", dash=(4,4))
                }
        elif "edge" in tags:
            self.selected_edge = tags[1]
            self.canvas.itemconfig(item, fill="red")

    def _on_canvas_drag(self, event):
        if self.drag_data["item"]:
            dx, dy = event.x - self.drag_data["x"], event.y - self.drag_data["y"]
            node_id = self.drag_data["node_id"]
            
            self.dag.nodes[node_id].position["x"] += dx
            self.dag.nodes[node_id].position["y"] += dy
            
            # Move all objects tagged with this node_id
            for item in self.canvas.find_withtag(node_id):
                self.canvas.move(item, dx, dy)
            
            self._update_node_edges(node_id)
            self.drag_data["x"], self.drag_data["y"] = event.x, event.y
            
        elif self.conn_data["active"]:
            coords = self.canvas.coords(self.conn_data["line"])
            self.canvas.coords(self.conn_data["line"], coords[0], coords[1], event.x, event.y)

    def _on_canvas_release(self, event):
        if self.conn_data["active"]:
            # Find what's under the mouse
            items = self.canvas.find_overlapping(event.x-2, event.y-2, event.x+2, event.y+2)
            target_socket = None
            for item in items:
                tags = self.canvas.gettags(item)
                if "socket" in tags and "in" in tags:
                    target_socket = item
                    break
            
            if target_socket:
                tags = self.canvas.gettags(target_socket)
                target_node_id = tags[2]
                handle = tags[3]
                
                # Check for existing edge on this specific input handle and remove it (single input per handle)
                existing = [e for e in self.dag.edges if e.target == target_node_id and e.target_handle == handle]
                for e in existing:
                    self.canvas.delete(self.edges_ui[e.id])
                    self.dag.edges.remove(e)

                # Create new edge
                edge_id = str(uuid.uuid4())
                new_edge = KpiEdge(edge_id, self.conn_data["start_node"], target_node_id, handle)
                self.dag.add_edge(new_edge)
                self._draw_edge(new_edge)
                
            self.canvas.delete(self.conn_data["line"])
            self.conn_data["active"] = False
            
        self.drag_data["item"] = None

    def _update_node_edges(self, node_id: str):
        for edge in self.dag.edges:
            if edge.source == node_id or edge.target == node_id:
                coords = self._get_edge_coords(edge)
                if coords:
                    self.canvas.coords(self.edges_ui[edge.id], *coords)

    def _on_delete_key(self, event):
        if self.selected_node:
            node_id = self.selected_node
            if node_id == "OUTPUT_NODE":
                messagebox.showwarning("Delete", "Cannot delete the Output node.")
                return
            
            # Remove edges
            edges_to_remove = [e for e in self.dag.edges if e.source == node_id or e.target == node_id]
            for e in edges_to_remove:
                if e.id in self.edges_ui:
                    self.canvas.delete(self.edges_ui[e.id])
                    del self.edges_ui[e.id]
                self.dag.edges.remove(e)
            
            # Remove UI
            self.canvas.delete(node_id)
            self.canvas.delete(f"socket and {node_id}")
            del self.nodes_ui[node_id]
            del self.dag.nodes[node_id]
            self.selected_node = None
            
        elif self.selected_edge:
            edge_id = self.selected_edge
            edge = next((e for e in self.dag.edges if e.id == edge_id), None)
            if edge:
                self.canvas.delete(self.edges_ui[edge_id])
                self.dag.edges.remove(edge)
                del self.edges_ui[edge_id]
            self.selected_edge = None

    def _add_kpi_input_node(self):
        selection_win = tk.Toplevel(self)
        selection_win.title("Select KPI")
        selection_win.geometry("400x500")
        
        lb = tk.Listbox(selection_win, font=("Helvetica", 10))
        lb.pack(fill="both", expand=True, padx=10, pady=10)
        
        sorted_kpis = sorted(self.kpi_list, key=lambda x: x.get('name', ''))
        for k in sorted_kpis: lb.insert(tk.END, k['name'])
            
        def on_select():
            if lb.curselection():
                kpi = sorted_kpis[lb.curselection()[0]]
                node = KpiNode(str(uuid.uuid4()), NodeType.KPI_INPUT, {"kpi_id": kpi['id'], "kpi_name": kpi['name']}, {"x": 50, "y": 50})
                self.dag.add_node(node)
                self._draw_node(node)
                selection_win.destroy()
        
        ttk.Button(selection_win, text="Select", command=on_select).pack(pady=10)

    def _add_constant_node(self):
        val = simpledialog.askfloat("Constant", "Enter numeric value:", parent=self)
        if val is not None:
            node = KpiNode(str(uuid.uuid4()), NodeType.CONSTANT, {"value": val}, {"x": 50, "y": 200})
            self.dag.add_node(node)
            self._draw_node(node)

    def _add_operator_node(self):
        op_win = tk.Toplevel(self)
        op_win.title("Operator")
        
        ops = ["+", "-", "*", "/", "pow", "min", "max", "avg"]
        var = tk.StringVar(value="+")
        for op in ops: ttk.Radiobutton(op_win, text=op, variable=var, value=op).pack(anchor="w", padx=30, pady=2)
            
        def on_ok():
            node = KpiNode(str(uuid.uuid4()), NodeType.OPERATOR, {"op": var.get()}, {"x": 400, "y": 300})
            self.dag.add_node(node)
            self._draw_node(node)
            op_win.destroy()
            
        ttk.Button(op_win, text="OK", command=on_ok).pack(pady=10)

    def _clear_canvas(self):
        if messagebox.askyesno("Clear", "Reset formula?"):
            self.dag = KpiDAG()
            self._load_dag()

    def _on_save(self):
        self.result_json = self.dag.to_json()
        self.destroy()

    def get_result(self):
        return getattr(self, "result_json", None)
