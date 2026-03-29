# src/interfaces/tkinter_app/components/kpi_management_tab.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import traceback
import json

from src.kpi_management import hierarchy as kpi_hierarchy_manager
from src.kpi_management import indicators as kpi_indicators_manager
from src.kpi_management import templates as kpi_templates_manager
from src.kpi_management import specs as kpi_specs_manager
from src.kpi_management import visibility as kpi_visibility
from src import data_retriever as db_retriever
from src.interfaces.tkinter_app.dialogs.indicator_spec_editor import IndicatorSpecEditorDialog
from src.interfaces.common_ui.constants import KPI_CALC_TYPE_OPTIONS
from src.interfaces.common_ui.helpers import get_kpi_display_name

from src.kpi_management import splits as kpi_splits_manager
from src.interfaces.tkinter_app.dialogs.split_editor import SplitEditorDialog

class KpiManagementTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.node_cache = {} # id -> row
        self.indicator_cache = {} # id -> row
        self.template_cache = {} # id -> row
        self.split_cache = {} # id -> row
        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self, style="Content.TFrame")
        main_frame.pack(fill="both", expand=True)

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill="both", expand=True, padx=15, pady=15)

        # Tabs
        self.hierarchy_frame = ttk.Frame(self.notebook, style="Card.TFrame")
        self.templates_frame = ttk.Frame(self.notebook, style="Card.TFrame")
        self.splits_frame = ttk.Frame(self.notebook, style="Card.TFrame")

        self.notebook.add(self.hierarchy_frame, text="📁 KPI Explorer")
        self.notebook.add(self.templates_frame, text="📋 Templates")
        self.notebook.add(self.splits_frame, text="✂️ Global Splits")

        self._create_hierarchy_ui(self.hierarchy_frame)
        self._create_templates_ui(self.templates_frame)
        self._create_splits_ui(self.splits_frame)

        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self.refresh_all())

    def _create_hierarchy_ui(self, parent):
        pane = ttk.PanedWindow(parent, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=10, pady=10)

        # Left: Tree
        tree_f = ttk.Frame(pane, style="Card.TFrame")
        pane.add(tree_f, weight=1)

        toolbar = ttk.Frame(tree_f, style="Card.TFrame")
        toolbar.pack(fill="x", pady=(0, 5))
        
        # New split button for node types
        ttk.Button(toolbar, text="+ Group", command=lambda: self.add_node('group'), width=8).pack(side="left", padx=2)
        ttk.Button(toolbar, text="+ Subgroup", command=lambda: self.add_node('subgroup'), width=10).pack(side="left", padx=2)
        ttk.Button(toolbar, text="+ Folder", command=lambda: self.add_node('folder'), width=8).pack(side="left", padx=2)
        ttk.Button(toolbar, text="+ KPI", command=self.add_kpi, width=8, style="Action.TButton").pack(side="left", padx=2)

        self.tree = ttk.Treeview(tree_f, show="tree", selectmode="browse")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        # Right: Details
        self.detail_f = ttk.LabelFrame(pane, text="Details & Properties", style="Card.TLabelframe", padding=15)     
        pane.add(self.detail_f, weight=2)
        self.detail_content = ttk.Frame(self.detail_f, style="Card.TFrame")
        self.detail_content.pack(fill="both", expand=True)

    def _create_templates_ui(self, parent):
        pane = ttk.PanedWindow(parent, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=10, pady=10)

        # Left: Template List
        list_f = ttk.Frame(pane, style="Card.TFrame")
        pane.add(list_f, weight=1)

        toolbar = ttk.Frame(list_f, style="Card.TFrame")
        toolbar.pack(fill="x", pady=(0, 5))
        ttk.Button(toolbar, text="+ Template", command=self.add_template, width=12).pack(side="left", padx=2)

        self.tpl_list = tk.Listbox(list_f, font=("Helvetica", 10))
        self.tpl_list.pack(fill="both", expand=True)
        self.tpl_list.bind("<<ListboxSelect>>", self.on_template_select)

        # Right: Template Details
        self.tpl_detail_f = ttk.LabelFrame(pane, text="Template Definitions", style="Card.TLabelframe", padding=15)
        pane.add(self.tpl_detail_f, weight=2)
        
        self.tpl_detail_content = ttk.Frame(self.tpl_detail_f, style="Card.TFrame")
        self.tpl_detail_content.pack(fill="both", expand=True)

    def _create_splits_ui(self, parent):
        pane = ttk.PanedWindow(parent, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=10, pady=10)

        # Left: Split List
        list_f = ttk.Frame(pane, style="Card.TFrame")
        pane.add(list_f, weight=1)

        toolbar = ttk.Frame(list_f, style="Card.TFrame")
        toolbar.pack(fill="x", pady=(0, 5))
        ttk.Button(toolbar, text="+ Split", command=self.add_split, width=12).pack(side="left", padx=2)

        self.split_list = tk.Listbox(list_f, font=("Helvetica", 10))
        self.split_list.pack(fill="both", expand=True)
        self.split_list.bind("<<ListboxSelect>>", self.on_split_select)

        # Right: Split Details
        self.split_detail_f = ttk.LabelFrame(pane, text="Standardized Annual Split Details", style="Card.TLabelframe", padding=15)
        pane.add(self.split_detail_f, weight=2)
        
        self.split_detail_content = ttk.Frame(self.split_detail_f, style="Card.TFrame")
        self.split_detail_content.pack(fill="both", expand=True)

    def refresh_all(self):
        tab_idx = self.notebook.index(self.notebook.select())
        if tab_idx == 0: self.refresh_tree()
        elif tab_idx == 1: self.refresh_templates()
        elif tab_idx == 2: self.refresh_splits()

    def refresh_tree(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        self.node_cache = {}
        self.indicator_cache = {}
        self._load_level(None, "")

    def _load_level(self, parent_id, tree_parent):
        # 1. Load Nodes (Folders/Groups)
        nodes_raw = db_retriever.get_hierarchy_nodes(parent_id)
        for n_row in nodes_raw:
            n = dict(n_row)
            iid = f"N_{n['id']}"
            
            # Icon mapping for node types
            icon = "📁"
            if n.get('node_type') == 'group': icon = "🏢"
            elif n.get('node_type') == 'subgroup': icon = "📂"
            
            self.tree.insert(tree_parent, "end", iid=iid, text=f"{icon} {n['name']}", open=False)
            self.node_cache[n['id']] = n
            self._load_level(n['id'], iid) # Recursive load

        # 2. Load Indicators for this level
        # Logic: If parent_id is None, we are at root.
        # But get_indicators_by_node(None) might not work depending on DB schema (node_id is likely NOT NULL).
        # Assuming indicators always belong to a node.
        if parent_id:
            inds_raw = db_retriever.get_indicators_by_node(parent_id)
            for i_row in inds_raw:
                i = dict(i_row)
                iid = f"I_{i['id']}"
                self.tree.insert(tree_parent, "end", iid=iid, text=f"📊 {i['name']}")
                self.indicator_cache[i['id']] = i

    def refresh_templates(self):
        self.tpl_list.delete(0, tk.END)
        self.template_cache = {}
        templates_raw = db_retriever.get_kpi_indicator_templates()
        for t_row in templates_raw:
            t = dict(t_row)
            self.template_cache[t['id']] = t
            self.tpl_list.insert(tk.END, t['name'])

    def refresh_splits(self):
        self.split_list.delete(0, tk.END)
        self.split_cache = {}
        splits_raw = kpi_splits_manager.get_all_global_splits()
        for s in splits_raw:
            self.split_cache[s['id']] = s
            self.split_list.insert(tk.END, f"{s['year']} - {s['name']}")

    def on_tree_select(self, event):
        sel = self.tree.selection()
        for c in self.detail_content.winfo_children(): c.destroy()
        if not sel: return

        item_id = sel[0]
        if item_id.startswith("N_"):
            node_id = int(item_id.split("_")[1])
            self._show_node_details(node_id)
        else:
            ind_id = int(item_id.split("_")[1])
            self._show_indicator_details(ind_id)

    def on_template_select(self, event):
        sel = self.tpl_list.curselection()
        for c in self.tpl_detail_content.winfo_children(): c.destroy()
        if not sel: return

        tpl_name = self.tpl_list.get(sel[0])
        tpl_id = next(tid for tid, t in self.template_cache.items() if t['name'] == tpl_name)
        self._show_template_details(tpl_id)

    def _show_node_details(self, node_id):
        node = self.node_cache[node_id]
        ttk.Label(self.detail_content, text=f"Node: {node['name']}", font=("Helvetica", 14, "bold"), background="#FFFFFF").pack(anchor="w")
        ttk.Label(self.detail_content, text=f"Type: {node.get('node_type', 'folder').capitalize()}", background="#FFFFFF").pack(anchor="w", pady=5)

        btn_f = ttk.Frame(self.detail_content, style="Card.TFrame")
        btn_f.pack(fill="x", pady=20)
        ttk.Button(btn_f, text="Rename", command=lambda: self.rename_node(node_id)).pack(side="left", padx=5)
        ttk.Button(btn_f, text="Delete Node", command=lambda: self.delete_node(node_id)).pack(side="left", padx=5)

    def on_split_select(self, event):
        sel = self.split_list.curselection()
        for c in self.split_detail_content.winfo_children(): c.destroy()
        if not sel: return

        split_label = self.split_list.get(sel[0])
        # Find ID by label "year - name"
        split_id = next(sid for sid, s in self.split_cache.items() if f"{s['year']} - {s['name']}" == split_label)
        self._show_split_details(split_id)

    def _show_indicator_details(self, ind_id):
        ind = dict(self.indicator_cache[ind_id])
        spec_row = kpi_specs_manager.get_kpi_spec_by_indicator_id(ind_id)
        spec = dict(spec_row) if spec_row else None

        # Header with icon
        header = ttk.Frame(self.detail_content, style="Card.TFrame")
        header.pack(fill="x", pady=(0, 15))
        ttk.Label(header, text=f"📊 {ind['name']}", font=("Helvetica", 16, "bold"), background="#FFFFFF").pack(side="left")

        if spec:
            props_f = ttk.LabelFrame(self.detail_content, text="Core Specification", style="Card.TLabelframe", padding=10)
            props_f.pack(fill="x", pady=5)
            
            grid = ttk.Frame(props_f, style="Card.TFrame")
            grid.pack(fill="x")
            
            # 2x2 Grid for properties
            ttk.Label(grid, text="Unit:", font=("Helvetica", 9, "bold"), background="#FFFFFF").grid(row=0, column=0, sticky="w", padx=5, pady=2)
            ttk.Label(grid, text=spec['unit_of_measure'], background="#FFFFFF").grid(row=0, column=1, sticky="w", padx=5, pady=2)
            
            ttk.Label(grid, text="Type:", font=("Helvetica", 9, "bold"), background="#FFFFFF").grid(row=0, column=2, sticky="w", padx=20, pady=2)
            ttk.Label(grid, text=spec['calculation_type'], background="#FFFFFF").grid(row=0, column=3, sticky="w", padx=5, pady=2)
            
            ttk.Label(grid, text="Split Profile:", font=("Helvetica", 9, "bold"), background="#FFFFFF").grid(row=1, column=0, sticky="w", padx=5, pady=2)
            
            profile_text = spec.get('default_distribution_profile', 'Standard (Equal)')
            profile_color = "#333333"
            
            if spec.get('global_split_id'):
                gs = db_retriever.get_all_global_splits()
                gs_obj = next((s for s in gs if s['id'] == spec['global_split_id']), None)
                if gs_obj:
                    profile_text = f"🔗 Global Split: {gs_obj['name']} ({gs_obj['year']})"
                    profile_color = "#d32f2f" # Reddish to indicate external control
            
            ttk.Label(grid, text=profile_text, background="#FFFFFF", foreground=profile_color).grid(row=1, column=1, sticky="w", padx=5, pady=2)
            
            ttk.Label(grid, text="Visible:", font=("Helvetica", 9, "bold"), background="#FFFFFF").grid(row=1, column=2, sticky="w", padx=20, pady=2)
            ttk.Label(grid, text="Yes" if spec['visible'] else "No", background="#FFFFFF").grid(row=1, column=3, sticky="w", padx=5, pady=2)

            if spec['is_calculated']:
                formula_f = ttk.LabelFrame(self.detail_content, text="Formula Preview (Calculated KPI)", style="Formula.TLabelframe", padding=10)
                formula_f.pack(fill="x", pady=10)
                
                # 1. Raw ID-based formula
                f_str = spec.get('formula_string')
                if not f_str and spec.get('formula_json'):
                    try:
                        from src.core.node_engine import KpiDAG
                        dag = KpiDAG.from_json(spec['formula_json'])
                        f_str = dag.to_formula()
                    except: pass
                
                f_str = f_str or 'No expression defined.'
                ttk.Label(formula_f, text=f"Expression: {f_str}", wraplength=400, font=("Courier", 9), background="#E3F2FD", foreground="#666").pack(fill="x")
                
                # 2. Name-based expanded formula
                expanded_formula = self._get_expanded_formula(f_str)
                ttk.Label(formula_f, text="Readable:", font=("Helvetica", 9, "bold"), background="#E3F2FD").pack(anchor="w", pady=(5, 0))
                ttk.Label(formula_f, text=expanded_formula, wraplength=400, font=("Helvetica", 10, "italic"), background="#E3F2FD", foreground="#0056b3").pack(fill="x", pady=(0, 5))

                # 3. Dummy Result
                preview_val = self._evaluate_formula_preview(spec)
                preview_f = tk.Frame(formula_f, background="#E3F2FD")
                preview_f.pack(fill="x", pady=5)
                ttk.Label(preview_f, text="Preview Result (inputs=10):", font=("Helvetica", 9), background="#E3F2FD").pack(side="left")
                ttk.Label(preview_f, text=f"{round(preview_val, 4)}", font=("Helvetica", 10, "bold"), background="#E3F2FD", foreground="#28a745").pack(side="left", padx=5)

                ttk.Button(formula_f, text="🛠️ Open Visual Editor", 
                           command=lambda: self.open_visual_editor(ind_id), 
                           width=20).pack(pady=10)

        # Actions for the KPI (Always visible)
        btn_f = ttk.Frame(self.detail_content, style="Card.TFrame")
        btn_f.pack(fill="x", pady=20)
        ttk.Button(btn_f, text="Full Edit", command=lambda: self.edit_kpi(ind_id), style="Action.TButton").pack(side="left", padx=5)
        ttk.Button(btn_f, text="Delete KPI", command=lambda: self.delete_kpi(ind_id)).pack(side="left", padx=5)

    def _get_expanded_formula(self, formula_str: str) -> str:
        if not formula_str: return "None"
        import re
        pattern = r'\[(\d+)\]'
        matches = re.findall(pattern, formula_str)
        
        all_kpis = db_retriever.get_all_kpis_detailed()
        name_map = {k['id']: k['indicator_name'] for k in all_kpis}
        
        expanded = formula_str
        for mid in set(matches):
            name = name_map.get(int(mid), f"KPI_{mid}")
            expanded = expanded.replace(f"[{mid}]", f"'{name}'")
        
        return expanded

    def _evaluate_formula_preview(self, spec) -> float:
        from src.core.node_engine import KpiDAG
        f_json = spec.get('formula_json')
        f_str = spec.get('formula_string')
        
        try:
            if f_json:
                dag = KpiDAG.from_json(f_json)
                return dag.evaluate(lambda kid, tn: 10.0)
            elif f_str:
                import re
                processed = re.sub(r'\[\d+\]', '10.0', f_str)
                return float(eval(processed, {"__builtins__": None}, {"abs": abs, "min": min, "max": max, "round": round}))
        except:
            return 0.0
        return 0.0

    def open_visual_editor(self, ind_id):
        from src.gui.node_editor import NodeEditorDialog
        spec_row = kpi_specs_manager.get_kpi_spec_by_indicator_id(ind_id)
        if not spec_row: return
        spec = dict(spec_row)
        
        all_kpis = db_retriever.get_all_kpis_detailed(only_visible=True)
        kpi_list = [{"id": k['id'], "name": k['indicator_name']} for k in all_kpis if k['indicator_id'] != ind_id]

        dialog = NodeEditorDialog(self.app, initial_json=spec.get('formula_json'), kpi_list=kpi_list)
        self.wait_window(dialog)
        if dialog.get_result():
            new_json = dialog.get_result()
            kpi_specs_manager.update_kpi_spec(spec['id'], formula_json=new_json)
            messagebox.showinfo("Success", "Formula updated.")
            self.refresh_tree()
            self._show_indicator_details(ind_id)

    def _show_split_details(self, split_id):
        s = self.split_cache[split_id]
        ttk.Label(self.split_detail_content, text=f"Split: {s['name']}", font=("Helvetica", 14, "bold"), background="#FFFFFF").pack(anchor="w")
        ttk.Label(self.split_detail_content, text=f"Year: {s['year']} | Logic: {s['repartition_logic']}", background="#FFFFFF").pack(anchor="w", pady=5)
        ttk.Label(self.split_detail_content, text=f"Profile: {s['distribution_profile']}", background="#FFFFFF").pack(anchor="w")

        # Visual representation of values (simplified)
        vals_f = ttk.LabelFrame(self.split_detail_content, text="Repartition Values", padding=10)
        vals_f.pack(fill="both", expand=True, pady=15)
        
        vals_text = tk.Text(vals_f, height=8, font=("Courier", 9))
        vals_text.pack(fill="both", expand=True)
        vals_text.insert("1.0", json.dumps(s['repartition_values'], indent=2))
        vals_text.config(state="disabled")

        btn_f = ttk.Frame(self.split_detail_content, style="Card.TFrame")
        btn_f.pack(fill="x", pady=10)
        ttk.Button(btn_f, text="Edit Split", command=lambda: self.edit_split(split_id), style="Action.TButton").pack(side="left", padx=5)
        ttk.Button(btn_f, text="Delete Split", command=lambda: self.delete_split(split_id)).pack(side="left", padx=5)

        # Show Affected KPIs
        st_f = ttk.LabelFrame(self.split_detail_content, text="🎯 Affected KPIs", padding=10)
        st_f.pack(fill="both", expand=True, pady=(15, 0))
        
        from src.kpi_management.splits import get_indicators_for_global_split
        afflicted = get_indicators_for_global_split(split_id)
        
        if afflicted:
            # We need indicator names. Fetching all KPIs to map.
            all_inds = db_retriever.get_all_kpi_indicators()
            ind_map = {i['id']: i['name'] for i in all_inds}
            
            # Use a listbox to show KPIs
            kpi_lb = tk.Listbox(st_f, font=("Helvetica", 9), height=10)
            kpi_lb.pack(fill="both", expand=True)
            for a in afflicted:
                name = ind_map.get(a['indicator_id'], f"ID:{a['indicator_id']}")
                profile_info = f" (Override: {a['override_distribution_profile']})" if a.get('override_distribution_profile') else ""
                kpi_lb.insert(tk.END, f"- {name}{profile_info}")
        else:
            ttk.Label(st_f, text="No KPIs linked to this split.", foreground="#999").pack()

    def _show_template_details(self, tpl_id):
        for c in self.tpl_detail_content.winfo_children(): c.destroy()
        tpl = self.template_cache[tpl_id]
        ttk.Label(self.tpl_detail_content, text=f"Template: {tpl['name']}", font=("Helvetica", 14, "bold"), background="#FFFFFF").pack(anchor="w")
        ttk.Label(self.tpl_detail_content, text=tpl.get('description', ''), wraplength=400, background="#FFFFFF").pack(anchor="w", pady=(0, 10))

        toolbar = ttk.Frame(self.tpl_detail_content, style="Card.TFrame")
        toolbar.pack(fill="x", pady=5)
        ttk.Button(toolbar, text="+ Add Indicator", command=lambda: self.add_template_indicator(tpl_id)).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Delete Template", command=lambda: self.delete_template(tpl_id)).pack(side="right", padx=2)

        # Treeview for indicators
        cols = ("Name", "Type", "Unit", "Visible")
        self.def_tree = ttk.Treeview(self.tpl_detail_content, columns=cols, show="headings", height=10)
        for col in cols: self.def_tree.heading(col, text=col)
        self.def_tree.pack(fill="both", expand=True)

        defs_raw = db_retriever.get_template_defined_indicators(tpl_id)
        for d_row in defs_raw:
            d = dict(d_row)
            v = "Yes" if d['default_visible'] else "No"
            # Ensure iid is string and unique
            self.def_tree.insert("", "end", iid=str(d['id']), values=(d['indicator_name_in_template'], d['default_calculation_type'], d['default_unit_of_measure'], v))

        btn_f = ttk.Frame(self.tpl_detail_content, style="Card.TFrame")
        btn_f.pack(fill="x", pady=10)
        ttk.Button(btn_f, text="Edit Selected", command=lambda: self.edit_template_indicator(tpl_id)).pack(side="left", padx=5)
        ttk.Button(btn_f, text="Remove Selected", command=self.remove_template_indicator).pack(side="left", padx=5)

    # --- Actions: Hierarchy ---

    def add_node(self, node_type='folder'):
        sel = self.tree.selection()
        parent_id = int(sel[0].split("_")[1]) if sel and sel[0].startswith("N_") else None
        
        type_labels = {'folder': 'Folder', 'group': 'KPI Group', 'subgroup': 'KPI Subgroup'}
        name = simpledialog.askstring(f"New {type_labels.get(node_type, 'Node')}", "Enter name:")
        if name:
            kpi_hierarchy_manager.add_node(name.strip(), parent_id, node_type)
            self.refresh_tree()

    def add_kpi(self):
        sel = self.tree.selection()
        if not (sel and sel[0].startswith("N_")):
            messagebox.showwarning("Warning", "Please select a destination folder first.")
            return
        node_id = int(sel[0].split("_")[1])
        dialog = IndicatorSpecEditorDialog(self.app, title="New KPI")
        if dialog.result_data:
            try:
                new_id = kpi_indicators_manager.add_kpi_indicator(dialog.result_data["indicator_name"], node_id)
                spec_id = kpi_specs_manager.add_kpi_spec(indicator_id=new_id, **{k:v for k,v in dialog.result_data.items() if k not in ["indicator_name", "per_plant_visibility"]})
                if "per_plant_visibility" in dialog.result_data:
                    kpi_visibility.update_plant_visibility(spec_id, dialog.result_data["per_plant_visibility"])
                self.refresh_tree()
                # Auto-select the newly added KPI
                iid = f"I_{new_id}"
                self.tree.selection_set(iid)
                self.tree.see(iid)
                self._show_indicator_details(new_id)
            except Exception as e: messagebox.showerror("Error", str(e))

    def rename_node(self, node_id):
        old_name = self.node_cache[node_id]['name']
        new_name = simpledialog.askstring("Rename", "New name:", initialvalue=old_name)
        if new_name and new_name.strip() != old_name:
            kpi_hierarchy_manager.update_node(node_id, name=new_name.strip())
            self.refresh_tree()

    def delete_node(self, node_id):
        if messagebox.askyesno("Confirm", "Delete this folder and everything inside?"):
            kpi_hierarchy_manager.delete_node(node_id)
            self.refresh_tree()

    def edit_kpi(self, ind_id):
        ind = dict(self.indicator_cache[ind_id])
        spec_row = kpi_specs_manager.get_kpi_spec_by_indicator_id(ind_id)
        spec = dict(spec_row) if spec_row else {}
        
        # Fetch current visibility
        visibility = kpi_visibility.get_plant_visibility_for_kpi(spec.get('id')) if spec.get('id') else []
        spec['per_plant_visibility'] = visibility

        dialog = IndicatorSpecEditorDialog(self.app, title="Edit KPI", initial_indicator_name=ind['name'], initial_spec_data=spec)
        if dialog.result_data:
            kpi_indicators_manager.update_kpi_indicator(ind_id, dialog.result_data["indicator_name"], ind['node_id'])
            spec_id = kpi_specs_manager.add_kpi_spec(indicator_id=ind_id, **{k:v for k,v in dialog.result_data.items() if k not in ["indicator_name", "per_plant_visibility"]})
            if "per_plant_visibility" in dialog.result_data:
                kpi_visibility.update_plant_visibility(spec_id, dialog.result_data["per_plant_visibility"])
            self.refresh_tree()
            # Restore selection and refresh details
            iid = f"I_{ind_id}"
            self.tree.selection_set(iid)
            self.tree.see(iid)
            self._show_indicator_details(ind_id)

    def delete_kpi(self, ind_id):
        if messagebox.askyesno("Confirm", "Delete this KPI?"):
            kpi_indicators_manager.delete_kpi_indicator(ind_id)
            self.refresh_tree()

    # --- Actions: Templates ---

    def add_template(self):
        name = simpledialog.askstring("New Template", "Template Name:")
        if name:
            kpi_templates_manager.add_kpi_indicator_template(name.strip())
            self.refresh_templates()

    def delete_template(self, tpl_id):
        if messagebox.askyesno("Confirm", "Delete template? This won't delete propagated KPIs."):
            kpi_templates_manager.delete_kpi_indicator_template(tpl_id)
            self.refresh_templates()
            for c in self.tpl_detail_content.winfo_children(): c.destroy()

    def add_template_indicator(self, tpl_id):
        from src.interfaces.tkinter_app.dialogs.template_definition_editor import TemplateDefinitionEditorDialog
        dialog = TemplateDefinitionEditorDialog(self.app, title="Add Template Indicator")
        if dialog.result_data:
            kpi_templates_manager.add_indicator_definition_to_template(tpl_id, **dialog.result_data)
            self._show_template_details(tpl_id)

    def edit_template_indicator(self, tpl_id):
        sel = self.def_tree.selection()
        if not sel: return
        def_id = int(sel[0])
        # Get existing data
        defs_raw = db_retriever.get_template_defined_indicators(tpl_id)
        existing = next(dict(d) for d in defs_raw if d['id'] == def_id)
        
        from src.interfaces.tkinter_app.dialogs.template_definition_editor import TemplateDefinitionEditorDialog
        dialog = TemplateDefinitionEditorDialog(self.app, title="Edit Template Indicator", initial_data=existing)
        if dialog.result_data:
            kpi_templates_manager.update_indicator_definition_in_template(def_id, tpl_id, **dialog.result_data)
            self._show_template_details(tpl_id)

    def remove_template_indicator(self):
        sel = self.def_tree.selection()
        if not sel: return
        if messagebox.askyesno("Confirm", "Remove definition from template?"):
            kpi_templates_manager.remove_indicator_definition_from_template(int(sel[0]))
            # Refresh via session state or re-call select logic
            sel_list = self.tpl_list.curselection()
            if sel_list: 
                tpl_name = self.tpl_list.get(sel_list[0])
                tpl_id = next(tid for tid, t in self.template_cache.items() if t['name'] == tpl_name)
                self._show_template_details(tpl_id)

    # --- Actions: Splits ---

    def add_split(self):
        dialog = SplitEditorDialog(self.app, title="New Global Split")
        if dialog.result_data:
            kpi_splits_manager.add_global_split(**dialog.result_data)
            self.refresh_splits()

    def edit_split(self, split_id):
        existing = self.split_cache[split_id]
        dialog = SplitEditorDialog(self.app, title="Edit Global Split", initial_data=existing)
        if dialog.result_data:
            kpi_splits_manager.update_global_split(split_id, **dialog.result_data)
            self.refresh_splits()
            self._show_split_details(split_id)

    def delete_split(self, split_id):
        if messagebox.askyesno("Confirm", "Delete this global split template?"):
            kpi_splits_manager.delete_global_split(split_id)
            self.refresh_splits()
            for c in self.split_detail_content.winfo_children(): c.destroy()
