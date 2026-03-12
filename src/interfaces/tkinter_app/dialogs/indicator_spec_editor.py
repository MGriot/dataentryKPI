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

        # Default Visible (for general visibility, if not overridden by plant-specific)
        ttk.Label(master, text="Default Visible:").grid(row=4, column=0, sticky="w", padx=5, pady=3)
        self.visible_var = tk.BooleanVar(value=bool(self.initial_spec_data.get("visible", True)))
        self.visible_chk = ttk.Checkbutton(master, variable=self.visible_var)
        self.visible_chk.grid(row=4, column=1, sticky="w", padx=5, pady=3)

        # Calculation Mode
        ttk.Label(master, text="Calculation Mode:").grid(row=5, column=0, sticky="w", padx=5, pady=3)
        self.is_calculated_var = tk.BooleanVar(value=bool(self.initial_spec_data.get("is_calculated", False)))
        mode_frame = ttk.Frame(master)
        mode_frame.grid(row=5, column=1, sticky="w", padx=5, pady=3)
        ttk.Radiobutton(mode_frame, text="Manual Entry", variable=self.is_calculated_var, value=False, command=self._toggle_formula_ui).pack(side="left")
        ttk.Radiobutton(mode_frame, text="Calculated (Formula)", variable=self.is_calculated_var, value=True, command=self._toggle_formula_ui).pack(side="left", padx=10)

        # Formula Section
        ttk.Label(master, text="Visual Formula:").grid(row=6, column=0, sticky="w", padx=5, pady=3)
        self.formula_json_var = tk.StringVar(value=self.initial_spec_data.get("formula_json", ""))
        self.formula_display_var = tk.StringVar(value="Defined" if self.formula_json_var.get() else "None")
        
        self.formula_ui_frame = ttk.Frame(master)
        self.formula_ui_frame.grid(row=6, column=1, sticky="ew", padx=5, pady=3)
        ttk.Label(self.formula_ui_frame, textvariable=self.formula_display_var).pack(side="left")
        self.edit_nodes_btn = ttk.Button(self.formula_ui_frame, text="Edit Nodes...", command=self._open_node_editor)
        self.edit_nodes_btn.pack(side="right")

        # Standard Distribution Profile
        from src.interfaces.common_ui.constants import DISTRIBUTION_PROFILE_OPTIONS
        ttk.Label(master, text="Default Split Profile:").grid(row=7, column=0, sticky="w", padx=5, pady=3)
        self.dist_profile_var = tk.StringVar(value=self.initial_spec_data.get("default_distribution_profile", DISTRIBUTION_PROFILE_OPTIONS[0]))
        self.dist_profile_cb = ttk.Combobox(master, textvariable=self.dist_profile_var, values=DISTRIBUTION_PROFILE_OPTIONS, state="readonly", width=38)
        self.dist_profile_cb.grid(row=7, column=1, padx=5, pady=3)

        # Per-Plant Visibility Section
        plant_visibility_frame = ttk.LabelFrame(master, text="Per-Plant Visibility")
        plant_visibility_frame.grid(row=8, column=0, columnspan=2, sticky="ew", padx=5, pady=5)

        # Populate plant visibility checkboxes
        row_idx = 0
        # Get existing per-plant visibility settings for this KPI
        existing_per_plant_visibility = self.initial_spec_data.get("per_plant_visibility", [])
        existing_per_plant_map = {item["plant_id"]: item["is_enabled"] for item in existing_per_plant_visibility}

        for plant in self.all_plants:
            plant_id = plant["id"]
            plant_name = plant["name"]
            # Default to True if no specific entry exists for this plant
            initial_plant_visible = existing_per_plant_map.get(plant_id, True)
            
            var = tk.BooleanVar(value=initial_plant_visible)
            self.plant_visibility_vars[plant_id] = var

            ttk.Label(plant_visibility_frame, text=plant_name).grid(row=row_idx, column=0, sticky="w", padx=2, pady=1)
            ttk.Checkbutton(plant_visibility_frame, variable=var).grid(row=row_idx, column=1, sticky="w", padx=2, pady=1)
            row_idx += 1

        self._toggle_formula_ui()
        return self.indicator_name_entry

    def _toggle_formula_ui(self):
        state = "normal" if self.is_calculated_var.get() else "disabled"
        self.edit_nodes_btn.config(state=state)

    def _open_node_editor(self):
        # Fetch all KPIs for selection in the node editor
        kpis = [dict(row) for row in data_retriever.get_all_kpis_detailed(only_visible=True)]
        kpi_list = [{"id": k['id'], "name": f"{k.get('group_name')} > {k.get('subgroup_name')} > {k.get('indicator_name')}"} for k in kpis]
        
        dialog = NodeEditorDialog(self, self.formula_json_var.get(), kpi_list)
        self.wait_window(dialog)
        
        result_json = dialog.get_result()
        if result_json:
            self.formula_json_var.set(result_json)
            self.formula_display_var.set("Defined")

    def apply(self):
        indicator_name = self.indicator_name_var.get().strip()
        if not indicator_name:
            messagebox.showwarning("Missing Input", "Indicator Name is required.", parent=self)
            self.result_data = None
            return

        per_plant_visibility_data = []
        for plant_id, var in self.plant_visibility_vars.items():
            per_plant_visibility_data.append({"plant_id": plant_id, "is_enabled": var.get()})

        self.result_data = {
            "indicator_name": indicator_name,
            "description": self.desc_var.get().strip(),
            "calculation_type": self.calc_type_var.get(),
            "unit_of_measure": self.unit_var.get().strip(),
            "visible": self.visible_var.get(), # Default visibility
            "is_calculated": self.is_calculated_var.get(),
            "formula_json": self.formula_json_var.get(),
            "formula_string": None,
            "default_distribution_profile": self.dist_profile_var.get(),
            "per_plant_visibility": per_plant_visibility_data
        }
