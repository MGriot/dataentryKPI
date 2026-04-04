import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from src.interfaces.common_ui.constants import KPI_CALC_TYPE_OPTIONS
from src import data_retriever
from src.kpi_management import visibility as kpi_visibility
from src.gui.node_editor import NodeEditorDialog

class IndicatorSpecEditorDialog(simpledialog.Dialog):
    def __init__(self, parent, title=None, initial_indicator_name="", initial_spec_data=None):
        self.initial_indicator_name = initial_indicator_name
        self.initial_spec_data = initial_spec_data if initial_spec_data is not None else {}
        self.result_data = None
        self.kpi_calc_type_options = KPI_CALC_TYPE_OPTIONS

        # Fetch all plants for per-plant visibility management
        self.all_plants = data_retriever.get_all_plants()
        self.plant_visibility_vars = {}

        super().__init__(parent, title)

    def body(self, master):
        # Indicator Name
        ttk.Label(master, text="Indicator Name:").grid(row=0, column=0, sticky="w", padx=5, pady=3)
        self.indicator_name_var = tk.StringVar(value=self.initial_indicator_name)
        self.indicator_name_entry = ttk.Entry(master, textvariable=self.indicator_name_var, width=40)
        self.indicator_name_entry.grid(row=0, column=1, padx=5, pady=3)
        self.indicator_name_entry.focus_set()

        # Description
        ttk.Label(master, text="Description:").grid(row=1, column=0, sticky="w", padx=5, pady=3)
        self.desc_var = tk.StringVar(value=self.initial_spec_data.get("description", ""))
        self.desc_entry = ttk.Entry(master, textvariable=self.desc_var, width=40)
        self.desc_entry.grid(row=1, column=1, padx=5, pady=3)

        # Calc Type
        ttk.Label(master, text="Calc Type:").grid(row=2, column=0, sticky="w", padx=5, pady=3)
        self.calc_type_var = tk.StringVar(value=self.initial_spec_data.get("calculation_type", self.kpi_calc_type_options[0]))
        self.calc_type_cb = ttk.Combobox(master, textvariable=self.calc_type_var, values=self.kpi_calc_type_options, state="readonly", width=38)
        self.calc_type_cb.grid(row=2, column=1, padx=5, pady=3)

        # Unit
        ttk.Label(master, text="Unit:").grid(row=3, column=0, sticky="w", padx=5, pady=3)
        self.unit_var = tk.StringVar(value=self.initial_spec_data.get("unit_of_measure", ""))
        self.unit_entry = ttk.Entry(master, textvariable=self.unit_var, width=40)
        self.unit_entry.grid(row=3, column=1, padx=5, pady=3)

        # Default Visible
        ttk.Label(master, text="Default Visible:").grid(row=4, column=0, sticky="w", padx=5, pady=3)
        self.visible_var = tk.BooleanVar(value=bool(self.initial_spec_data.get("visible", True)))
        self.visible_chk = ttk.Checkbutton(master, variable=self.visible_var)
        self.visible_chk.grid(row=4, column=1, sticky="w", padx=5, pady=3)

        # Calculation Mode
        ttk.Label(master, text="Calc Mode:").grid(row=5, column=0, sticky="w", padx=5, pady=3)
        self.is_calculated_var = tk.BooleanVar(value=bool(self.initial_spec_data.get("is_calculated", False)))
        mode_frame = ttk.Frame(master)
        mode_frame.grid(row=5, column=1, sticky="w", padx=5, pady=3)
        ttk.Radiobutton(mode_frame, text="Manual", variable=self.is_calculated_var, value=False, command=self._toggle_formula_ui).pack(side="left")
        ttk.Radiobutton(mode_frame, text="Formula", variable=self.is_calculated_var, value=True, command=self._toggle_formula_ui).pack(side="left", padx=10)

        # Formula Type (Nodes vs String)
        self.formula_type_frame = ttk.Frame(master)
        self.formula_type_frame.grid(row=6, column=0, columnspan=2, sticky="ew", padx=5, pady=2)
        
        ttk.Label(self.formula_type_frame, text="Formula Type:").pack(side="left", padx=5)
        initial_mode = "string" if self.initial_spec_data.get("formula_string") else "nodes"
        self.formula_mode_var = tk.StringVar(value=initial_mode)
        ttk.Radiobutton(self.formula_type_frame, text="Visual Nodes", variable=self.formula_mode_var, value="nodes", command=self._toggle_formula_ui).pack(side="left", padx=5)
        ttk.Radiobutton(self.formula_type_frame, text="Expression String", variable=self.formula_mode_var, value="string", command=self._toggle_formula_ui).pack(side="left", padx=5)

        # --- Formula Editors ---
        self.editor_container = ttk.Frame(master)
        self.editor_container.grid(row=7, column=0, columnspan=2, sticky="ew", padx=5, pady=5)

        # Node Editor UI
        self.nodes_frame = ttk.Frame(self.editor_container)
        self.formula_json_var = tk.StringVar(value=self.initial_spec_data.get("formula_json", ""))
        self.formula_display_var = tk.StringVar(value="Defined" if self.formula_json_var.get() else "None")
        ttk.Label(self.nodes_frame, text="Visual Formula:").pack(side="left", padx=5)
        ttk.Label(self.nodes_frame, textvariable=self.formula_display_var, font=("Helvetica", 9, "bold")).pack(side="left", padx=5)
        self.edit_nodes_btn = ttk.Button(self.nodes_frame, text="Open Node Editor...", command=self._open_node_editor)
        self.edit_nodes_btn.pack(side="left", padx=10)

        # String Editor UI
        self.string_frame = ttk.Frame(self.editor_container)
        ttk.Label(self.string_frame, text="Formula:").pack(side="left", padx=5)
        self.formula_string_var = tk.StringVar(value=self.initial_spec_data.get("formula_string", ""))
        self.string_entry = ttk.Entry(self.string_frame, textvariable=self.formula_string_var, width=40)
        self.string_entry.pack(side="left", padx=5, fill="x", expand=True)
        ttk.Button(self.string_frame, text="KPI Picker", command=self._on_kpi_picker).pack(side="left", padx=2)

        # Standard Distribution Profile
        from src.interfaces.common_ui.constants import DISTRIBUTION_PROFILE_OPTIONS
        ttk.Label(master, text="Split Profile:").grid(row=8, column=0, sticky="w", padx=5, pady=3)
        
        initial_profile = self.initial_spec_data.get("default_distribution_profile", DISTRIBUTION_PROFILE_OPTIONS[0])
        
        # Determine if this indicator is managed by a Global Split
        from src.kpi_management.splits import get_global_splits_for_indicator
        linked_gs = []
        if self.initial_spec_data.get('indicator_id'):
            linked_gs = get_global_splits_for_indicator(self.initial_spec_data['indicator_id'])
        
        state = "readonly"
        gs_info_text = ""
        
        if linked_gs:
            # If multiple, we show the first one but indicate there are others
            gs = linked_gs[0]
            initial_profile = gs['distribution_profile']
            state = "disabled"
            gs_info_text = f"🔗 Managed by GS: {gs['name']}"
            if len(linked_gs) > 1:
                gs_info_text += f" (+{len(linked_gs)-1} more)"

        self.dist_profile_var = tk.StringVar(value=initial_profile)
        self.dist_profile_cb = ttk.Combobox(master, textvariable=self.dist_profile_var, values=DISTRIBUTION_PROFILE_OPTIONS, state=state, width=38)
        self.dist_profile_cb.grid(row=8, column=1, padx=5, pady=3)
        
        if gs_info_text:
            ttk.Label(master, text=gs_info_text, foreground="#d32f2f", font=("Helvetica", 8, "italic")).grid(row=8, column=1, sticky="e", padx=10)

        # Per-Plant Visibility Section
        self.pv_frame = ttk.LabelFrame(master, text="Per-Plant Visibility")
        self.pv_frame.grid(row=9, column=0, columnspan=2, sticky="ew", padx=5, pady=5)

        existing_per_plant_visibility = self.initial_spec_data.get("per_plant_visibility", [])
        existing_per_plant_map = {item["plant_id"]: item["is_enabled"] for item in existing_per_plant_visibility}

        for i, plant in enumerate(self.all_plants):
            var = tk.BooleanVar(value=existing_per_plant_map.get(plant["id"], True))
            self.plant_visibility_vars[plant["id"]] = var
            ttk.Checkbutton(self.pv_frame, text=plant["name"], variable=var).grid(row=i//3, column=i%3, sticky="w", padx=10)

        self._toggle_formula_ui()
        return self.indicator_name_entry

    def _toggle_formula_ui(self):
        is_calc = self.is_calculated_var.get()
        mode = self.formula_mode_var.get()
        
        # Bidirectional conversion
        if is_calc:
            if mode == "string" and self.formula_json_var.get():
                # Convert Nodes -> String
                try:
                    from src.core.node_engine import KpiDAG
                    dag = KpiDAG.from_json(self.formula_json_var.get())
                    formula = dag.to_formula()
                    if formula: self.formula_string_var.set(formula)
                except Exception as e:
                    print(f"Error converting nodes to string: {e}")
            elif mode == "nodes" and self.formula_string_var.get():
                # Convert String -> Nodes
                try:
                    from src.core.node_engine import KpiDAG
                    dag = KpiDAG.from_formula(self.formula_string_var.get())
                    # Redraw names from DB if possible
                    self.formula_json_var.set(dag.to_json())
                    self.formula_display_var.set("Defined (Converted)")
                except Exception as e:
                    print(f"Error converting string to nodes: {e}")

        if is_calc:
            self.formula_type_frame.grid()
            self.nodes_frame.pack_forget()
            self.string_frame.pack_forget()
            
            if mode == "nodes":
                self.nodes_frame.pack(fill="x", expand=True)
            else:
                self.string_frame.pack(fill="x", expand=True)
        else:
            self.formula_type_frame.grid_remove()
            self.nodes_frame.pack_forget()
            self.string_frame.pack_forget()

    def _open_node_editor(self):
        kpis = [dict(row) for row in data_retriever.get_all_kpis_detailed(only_visible=True)]
        kpi_list = [{"id": k['id'], "name": f"{k.get('hierarchy_path', 'Root')} > {k.get('indicator_name')}"} for k in kpis]
        dialog = NodeEditorDialog(self, self.formula_json_var.get(), kpi_list)
        self.wait_window(dialog)
        res = dialog.get_result()
        if res:
            self.formula_json_var.set(res)
            self.formula_display_var.set("Defined")

    def _on_kpi_picker(self):
        picker = tk.Toplevel(self)
        picker.title("Select KPI Reference")
        picker.geometry("400x500")
        
        lb = tk.Listbox(picker, font=("Helvetica", 10))
        lb.pack(fill="both", expand=True, padx=10, pady=10)
        
        kpis = sorted([dict(row) for row in data_retriever.get_all_kpis_detailed(only_visible=True)], key=lambda x: x['indicator_name'] or "")
        for k in kpis:
            path = k.get('hierarchy_path', 'Root')
            lb.insert(tk.END, f"{path} > {k['indicator_name']} [ID:{k['id']}]")
            
        def select():
            if lb.curselection():
                k = kpis[lb.curselection()[0]]
                self.string_entry.insert(tk.INSERT, f"[{k['id']}]")
                picker.destroy()
        
        ttk.Button(picker, text="Insert Reference", command=select).pack(pady=10)

    def apply(self):
        indicator_name = self.indicator_name_var.get().strip()
        if not indicator_name:
            messagebox.showwarning("Missing Input", "Indicator Name is required.", parent=self)
            self.result_data = None
            return

        per_plant_visibility_data = [{"plant_id": pid, "is_enabled": var.get()} for pid, var in self.plant_visibility_vars.items()]

        is_calc = self.is_calculated_var.get()
        mode = self.formula_mode_var.get()
        
        f_json = self.formula_json_var.get() if (is_calc and mode == "nodes") else None
        f_string = self.formula_string_var.get().strip() if (is_calc and mode == "string") else None

        self.result_data = {
            "indicator_name": indicator_name,
            "description": self.desc_var.get().strip(),
            "calculation_type": self.calc_type_var.get(),
            "unit_of_measure": self.unit_var.get().strip(),
            "visible": self.visible_var.get(),
            "is_calculated": is_calc,
            "formula_json": f_json,
            "formula_string": f_string,
            "default_distribution_profile": self.dist_profile_var.get(),
            "per_plant_visibility": per_plant_visibility_data
        }
