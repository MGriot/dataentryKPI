# src/interfaces/tkinter_app/components/kpi_management_tab.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import traceback

from src.kpi_management import groups as kpi_groups_manager
from src.kpi_management import subgroups as kpi_subgroups_manager
from src.kpi_management import indicators as kpi_indicators_manager
from src.kpi_management import templates as kpi_templates_manager
from src.kpi_management import specs as kpi_specs_manager
from src.kpi_management import visibility as kpi_visibility
from src import data_retriever as db_retriever
from src.interfaces.tkinter_app.dialogs.subgroup_editor import SubgroupEditorDialog
from src.interfaces.tkinter_app.dialogs.template_definition_editor import TemplateDefinitionEditorDialog
from src.interfaces.tkinter_app.dialogs.indicator_spec_editor import IndicatorSpecEditorDialog
from src.interfaces.common_ui.constants import KPI_CALC_TYPE_OPTIONS
from src.interfaces.common_ui.helpers import get_kpi_display_name
from src.kpi_management import links as kpi_links_manager

class KpiManagementTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        self.current_groups_map = {}
        self.current_subgroups_map = {}
        self.current_indicators_map = {}
        self.current_templates_map = {}
        self.current_template_definitions_map = {}

        # Master/Sub Links UI variables
        self.ms_kpi_var = tk.StringVar()
        self.ms_kpi_cb = None
        self.ms_role_label_var = tk.StringVar()
        self.ms_links_tree = None
        self.ms_sub_kpi_var = tk.StringVar()
        self.ms_sub_kpi_cb = None
        self.ms_weight_var = tk.DoubleVar()
        
        self.ms_link_btn = None
        self.ms_unlink_btn = None
        self.all_kpis_for_linking = []
        self.selected_master_kpi_id = None

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self, style="Content.TFrame")
        main_frame.pack(fill="both", expand=True)

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill="both", expand=True, padx=15, pady=15)

        self.hierarchy_specs_frame = ttk.Frame(self.notebook, style="Card.TFrame")
        self.templates_frame = ttk.Frame(self.notebook, style="Card.TFrame")
        self.master_sub_frame = ttk.Frame(self.notebook, style="Card.TFrame")
        self.all_kpis_frame = ttk.Frame(self.notebook, style="Card.TFrame")

        self.notebook.add(self.hierarchy_specs_frame, text="Hierarchy & Specifications")
        self.notebook.add(self.templates_frame, text="Templates")
        self.notebook.add(self.master_sub_frame, text="Master/Sub Links")
        self.notebook.add(self.all_kpis_frame, text="All KPIs")

        self._create_hierarchy_specs_ui(self.hierarchy_specs_frame)
        self._create_templates_ui(self.templates_frame)
        self._create_master_sub_ui(self.master_sub_frame)
        self._create_all_kpis_ui(self.all_kpis_frame)

        self.notebook.bind("<<NotebookTabChanged>>", self._on_sub_tab_changed)

    def _create_hierarchy_specs_ui(self, parent_frame):
        self.hierarchy_pane = ttk.PanedWindow(parent_frame, orient="horizontal")
        self.hierarchy_pane.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Left Side: Hierarchy Tree ---
        tree_container = ttk.Frame(self.hierarchy_pane, style="Card.TFrame")
        self.hierarchy_pane.add(tree_container, weight=1)

        tree_toolbar = ttk.Frame(tree_container, style="Card.TFrame")
        tree_toolbar.pack(fill="x", pady=(0, 5))
        
        ttk.Button(tree_toolbar, text="+ Group", command=self.add_new_group, width=10, style="Action.TButton").pack(side="left", padx=2)
        self.add_subgroup_btn = ttk.Button(tree_toolbar, text="+ Subgroup", command=self.add_new_subgroup, state="disabled", width=11)
        self.add_subgroup_btn.pack(side="left", padx=2)
        self.add_indicator_btn = ttk.Button(tree_toolbar, text="+ Indicator", command=self.add_new_indicator, state="disabled", width=11)
        self.add_indicator_btn.pack(side="left", padx=2)

        self.hierarchy_tree = ttk.Treeview(tree_container, selectmode="browse", show="tree")
        self.hierarchy_tree.pack(fill="both", expand=True, side="left")
        
        tree_scroll = ttk.Scrollbar(tree_container, orient="vertical", command=self.hierarchy_tree.yview)
        tree_scroll.pack(side="right", fill="y")
        self.hierarchy_tree.configure(yscrollcommand=tree_scroll.set)
        
        self.hierarchy_tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        # --- Right Side: Detail Panel ---
        self.detail_container = ttk.LabelFrame(self.hierarchy_pane, text="Details & Actions", style="Card.TLabelframe", padding=15)
        self.hierarchy_pane.add(self.detail_container, weight=2)
        
        self.detail_content = ttk.Frame(self.detail_container, style="Card.TFrame")
        self.detail_content.pack(fill="both", expand=True)
        
        self._clear_detail_panel()

    def on_tree_select(self, event=None):
        selected = self.hierarchy_tree.selection()
        if not selected:
            self._clear_detail_panel()
            return
            
        item_id = selected[0]
        self.add_subgroup_btn.config(state="disabled")
        self.add_indicator_btn.config(state="disabled")
        
        for child in self.detail_content.winfo_children():
            child.destroy()

        if item_id.startswith("G_"):
            group_id = int(item_id.split("_")[1])
            self.add_subgroup_btn.config(state="normal")
            self._show_group_details(group_id)
        elif item_id.startswith("S_"):
            subgroup_id = int(item_id.split("_")[1])
            self.add_indicator_btn.config(state="normal")
            self._show_subgroup_details(subgroup_id)
        elif item_id.startswith("I_"):
            indicator_id = int(item_id.split("_")[1])
            self._show_indicator_details(indicator_id)

    def _clear_detail_panel(self):
        for child in self.detail_content.winfo_children():
            child.destroy()
        ttk.Label(self.detail_content, text="Select an item in the tree to view details.", 
                  font=("Helvetica", 10, "italic"), background="#FFFFFF").pack(pady=50)

    def _show_group_details(self, group_id):
        group = self.current_groups_map.get(group_id)
        if not group: return
        ttk.Label(self.detail_content, text=f"Group: {group['name']}", font=("Helvetica", 12, "bold"), background="#FFFFFF").pack(anchor="w", pady=5)
        btn_frame = ttk.Frame(self.detail_content, style="Card.TFrame")
        btn_frame.pack(fill="x", pady=10)
        ttk.Button(btn_frame, text="Rename Group", command=self.edit_selected_group).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Delete Group", command=self.delete_selected_group).pack(side="left", padx=5)

    def _show_subgroup_details(self, subgroup_id):
        subgroup = self.current_subgroups_map.get(subgroup_id)
        if not subgroup: return
        ttk.Label(self.detail_content, text=f"Subgroup: {subgroup['name']}", font=("Helvetica", 12, "bold"), background="#FFFFFF").pack(anchor="w", pady=5)
        if subgroup.get('template_name'):
            ttk.Label(self.detail_content, text=f"Template: {subgroup['template_name']}", background="#FFFFFF").pack(anchor="w")
        btn_frame = ttk.Frame(self.detail_content, style="Card.TFrame")
        btn_frame.pack(fill="x", pady=10)
        ttk.Button(btn_frame, text="Edit Subgroup", command=self.edit_selected_subgroup).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Delete Subgroup", command=self.delete_selected_subgroup).pack(side="left", padx=5)

    def _show_indicator_details(self, indicator_id):
        indicator = self.current_indicators_map.get(indicator_id)
        if not indicator: return
        spec = kpi_specs_manager.get_kpi_spec_by_indicator_id(indicator_id)
        ttk.Label(self.detail_content, text=f"Indicator: {indicator['name']}", font=("Helvetica", 12, "bold"), background="#FFFFFF").pack(anchor="w", pady=5)
        if spec:
            info_frame = ttk.Frame(self.detail_content, style="Card.TFrame")
            info_frame.pack(fill="x", pady=5)
            ttk.Label(info_frame, text=f"Unit: {spec.get('unit_of_measure', 'N/A')}", background="#FFFFFF").pack(anchor="w")
            ttk.Label(info_frame, text=f"Type: {spec.get('calculation_type', 'N/A')}", background="#FFFFFF").pack(anchor="w")
            ttk.Label(info_frame, text=f"Calculated: {'Yes' if spec.get('is_calculated') else 'No'}", background="#FFFFFF").pack(anchor="w")
            desc = spec.get('description', '')
            if desc:
                ttk.Label(self.detail_content, text="Description:", font=("Helvetica", 9, "bold"), background="#FFFFFF").pack(anchor="w", pady=(10, 0))
                ttk.Label(self.detail_content, text=desc, wraplength=400, background="#FFFFFF", justify="left").pack(anchor="w")
        btn_frame = ttk.Frame(self.detail_content, style="Card.TFrame")
        btn_frame.pack(fill="x", pady=20)
        ttk.Button(btn_frame, text="Full Edit", command=self.edit_selected_indicator, style="Action.TButton").pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Delete Indicator", command=self.delete_selected_indicator).pack(side="left", padx=5)

    def refresh_hierarchy_tree(self):
        for item in self.hierarchy_tree.get_children():
            self.hierarchy_tree.delete(item)
        self.current_groups_map = {}
        self.current_subgroups_map = {}
        self.current_indicators_map = {}
        groups = kpi_groups_manager.get_kpi_groups()
        for group in groups:
            g_id = f"G_{group['id']}"
            self.hierarchy_tree.insert("", "end", iid=g_id, text=f"📁 Group: {group['name']}", open=True)
            self.current_groups_map[group["id"]] = group
            subgroups = kpi_subgroups_manager.get_kpi_subgroups_by_group_revised(group["id"])
            for sg in subgroups:
                sg_id = f"S_{sg['id']}"
                self.hierarchy_tree.insert(g_id, "end", iid=sg_id, text=f"📂 {sg['name']}", open=False)
                self.current_subgroups_map[sg["id"]] = sg
                indicators = kpi_indicators_manager.get_kpi_indicators_by_subgroup(sg["id"])
                for ind in indicators:
                    i_id = f"I_{ind['id']}"
                    self.hierarchy_tree.insert(sg_id, "end", iid=i_id, text=f"📊 {ind['name']}")
                    self.current_indicators_map[ind["id"]] = ind

    def refresh_groups_listbox(self):
        self.refresh_hierarchy_tree()

    def add_new_group(self):
        group_name = simpledialog.askstring("New KPI Group", "Enter name for new KPI Group:", parent=self)
        if group_name:
            group_name = group_name.strip()
            if not group_name:
                messagebox.showerror("Input Error", "Group name cannot be empty.")
                return
            try:
                kpi_groups_manager.add_kpi_group(group_name)
                messagebox.showinfo("Success", f"KPI Group '{group_name}' added successfully.")
                self.refresh_hierarchy_tree()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add KPI Group: {e}")

    def edit_selected_group(self):
        selected = self.hierarchy_tree.selection()
        if not selected or not selected[0].startswith("G_"):
            messagebox.showwarning("Selection Error", "Please select a group to edit.")
            return
        group_id = int(selected[0].split("_")[1])
        current_group_name = self.current_groups_map[group_id]["name"]
        new_group_name = simpledialog.askstring("Edit KPI Group", f"Edit name for '{current_group_name}':", initialvalue=current_group_name, parent=self)
        if new_group_name and new_group_name.strip() and new_group_name.strip() != current_group_name:
            try:
                kpi_groups_manager.update_kpi_group(group_id, new_group_name.strip())
                messagebox.showinfo("Success", "KPI Group updated.")
                self.refresh_hierarchy_tree()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update Group: {e}")

    def delete_selected_group(self):
        selected = self.hierarchy_tree.selection()
        if not selected or not selected[0].startswith("G_"): return
        group_id = int(selected[0].split("_")[1])
        group_name = self.current_groups_map[group_id]["name"]
        if messagebox.askyesno("Confirm Delete", f"Delete Group '{group_name}' and all its contents?"):
            try:
                kpi_groups_manager.delete_kpi_group(group_id)
                self.refresh_hierarchy_tree()
                self._clear_detail_panel()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete Group: {e}")

    def add_new_subgroup(self):
        selected = self.hierarchy_tree.selection()
        if not selected or not selected[0].startswith("G_"):
            messagebox.showwarning("Selection Error", "Please select a group first.")
            return
        group_id = int(selected[0].split("_")[1])
        dialog = SubgroupEditorDialog(self.app, title=f"New Subgroup", group_id=group_id)
        if dialog.result_data:
            try:
                kpi_subgroups_manager.add_kpi_subgroup(dialog.result_data["name"], group_id, dialog.result_data["template_name"])
                self.refresh_hierarchy_tree()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add Subgroup: {e}")

    def edit_selected_subgroup(self):
        selected = self.hierarchy_tree.selection()
        if not selected or not selected[0].startswith("S_"): return
        subgroup_id = int(selected[0].split("_")[1])
        subgroup = self.current_subgroups_map[subgroup_id]
        dialog = SubgroupEditorDialog(self.app, title="Edit Subgroup", group_id=subgroup["group_id"], 
                                      initial_subgroup_name=subgroup["name"], initial_template_name=subgroup.get("template_name", ""))
        if dialog.result_data:
            try:
                kpi_subgroups_manager.update_kpi_subgroup(subgroup_id, dialog.result_data["name"], subgroup["group_id"], dialog.result_data["template_name"])
                self.refresh_hierarchy_tree()
                self.on_tree_select() # Refresh details
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update Subgroup: {e}")

    def delete_selected_subgroup(self):
        selected = self.hierarchy_tree.selection()
        if not selected or not selected[0].startswith("S_"): return
        subgroup_id = int(selected[0].split("_")[1])
        if messagebox.askyesno("Confirm", "Delete this subgroup and all its indicators?"):
            try:
                kpi_subgroups_manager.delete_kpi_subgroup(subgroup_id)
                self.refresh_hierarchy_tree()
                self._clear_detail_panel()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete Subgroup: {e}")

    def add_new_indicator(self):
        selected = self.hierarchy_tree.selection()
        if not selected or not selected[0].startswith("S_"): return
        subgroup_id = int(selected[0].split("_")[1])
        dialog = IndicatorSpecEditorDialog(self.app, title="New Indicator")
        if dialog.result_data:
            try:
                new_id = kpi_indicators_manager.add_kpi_indicator(dialog.result_data["indicator_name"], subgroup_id)
                kpi_specs_manager.add_kpi_spec(indicator_id=new_id, **{k:v for k,v in dialog.result_data.items() if k not in ["indicator_name", "per_plant_visibility"]})
                for pv in dialog.result_data.get("per_plant_visibility", []):
                    kpi_visibility.set_kpi_plant_visibility(new_id, pv["plant_id"], pv["is_enabled"])
                self.refresh_hierarchy_tree()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add Indicator: {e}")

    def edit_selected_indicator(self):
        selected = self.hierarchy_tree.selection()
        if not selected or not selected[0].startswith("I_"): return
        indicator_id = int(selected[0].split("_")[1])
        indicator = self.current_indicators_map[indicator_id]
        spec = kpi_specs_manager.get_kpi_spec_by_indicator_id(indicator_id) or {}
        spec["per_plant_visibility"] = kpi_visibility.get_plants_for_kpi(indicator_id)
        dialog = IndicatorSpecEditorDialog(self.app, title="Edit Indicator", initial_indicator_name=indicator["name"], initial_spec_data=spec)
        if dialog.result_data:
            try:
                kpi_indicators_manager.update_kpi_indicator(indicator_id, dialog.result_data["indicator_name"], indicator["subgroup_id"])
                kpi_specs_manager.add_kpi_spec(indicator_id=indicator_id, **{k:v for k,v in dialog.result_data.items() if k not in ["indicator_name", "per_plant_visibility"]})
                for pv in dialog.result_data.get("per_plant_visibility", []):
                    kpi_visibility.set_kpi_plant_visibility(indicator_id, pv["plant_id"], pv["is_enabled"])
                self.refresh_hierarchy_tree()
                self.on_tree_select()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update Indicator: {e}")

    def delete_selected_indicator(self):
        selected = self.hierarchy_tree.selection()
        if not selected or not selected[0].startswith("I_"): return
        indicator_id = int(selected[0].split("_")[1])
        if messagebox.askyesno("Confirm", "Delete this KPI indicator?"):
            try:
                kpi_indicators_manager.delete_kpi_indicator(indicator_id)
                self.refresh_hierarchy_tree()
                self._clear_detail_panel()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete Indicator: {e}")

    def _create_templates_ui(self, parent_frame):
        main_frame = parent_frame
        template_list_frame = ttk.LabelFrame(main_frame, text="KPI Indicator Templates", style="Card.TLabelframe", padding=10)
        template_list_frame.pack(side="left", fill="both", expand=True, padx=15, pady=15)
        self.templates_listbox = tk.Listbox(template_list_frame, exportselection=False, height=15, width=30, relief="flat", borderwidth=1, highlightthickness=1)
        self.templates_listbox.pack(fill="both", expand=True, pady=(0, 5))
        self.templates_listbox.bind("<<ListboxSelect>>", self.on_template_select)
        template_btn_frame = ttk.Frame(template_list_frame, style="Card.TFrame")
        template_btn_frame.pack(fill="x")
        ttk.Button(template_btn_frame, text="New Tpl", command=self.add_new_kpi_template, width=10, style="Action.TButton").pack(side="left", padx=2)
        self.edit_template_btn = ttk.Button(template_btn_frame, text="Edit Tpl", command=self.edit_selected_kpi_template, state="disabled", width=11)
        self.edit_template_btn.pack(side="left", padx=2)
        self.delete_template_btn = ttk.Button(template_btn_frame, text="Delete Tpl", command=self.delete_selected_kpi_template, state="disabled", width=11)
        self.delete_template_btn.pack(side="left", padx=2)
        definitions_frame = ttk.LabelFrame(main_frame, text="Definitions in Template", style="Card.TLabelframe", padding=10)
        definitions_frame.pack(side="left", fill="both", expand=True, padx=15, pady=15)
        self.template_definitions_tree = ttk.Treeview(definitions_frame, columns=("ID", "Indicator Name", "Calc Type", "Unit", "Visible", "Description"), show="headings", height=14)
        cols_defs = {"ID": 40, "Indicator Name": 180, "Calc Type": 100, "Unit": 80, "Visible": 60, "Description": 220}
        for col, width in cols_defs.items():
            self.template_definitions_tree.heading(col, text=col)
            self.template_definitions_tree.column(col, width=width, anchor="center" if col in ["ID", "Visible"] else "w", stretch=(col in ["Description", "Indicator Name"]))
        self.template_definitions_tree.pack(fill="both", expand=True, pady=(0, 5))
        self.template_definitions_tree.bind("<<TreeviewSelect>>", self.on_template_definition_select)
        definition_btn_frame = ttk.Frame(definitions_frame, style="Card.TFrame")
        definition_btn_frame.pack(fill="x")
        self.add_definition_btn = ttk.Button(definition_btn_frame, text="Add Def.", command=self.add_new_template_definition, state="disabled", width=12, style="Action.TButton")
        self.add_definition_btn.pack(side="left", padx=2)
        self.edit_definition_btn = ttk.Button(definition_btn_frame, text="Edit Def.", command=self.edit_selected_template_definition, state="disabled", width=12)
        self.edit_definition_btn.pack(side="left", padx=2)
        self.remove_definition_btn = ttk.Button(definition_btn_frame, text="Remove Def.", command=self.remove_selected_template_definition, state="disabled", width=12)
        self.remove_definition_btn.pack(side="left", padx=2)

    def _create_master_sub_ui(self, parent_frame):
        main_frame = ttk.Frame(parent_frame, padding=15, style="Card.TFrame")
        main_frame.pack(fill="both", expand=True)
        selection_frame = ttk.LabelFrame(main_frame, text="Select a KPI to Manage", style="Card.TLabelframe", padding=10)
        selection_frame.pack(fill="x", pady=5)
        ttk.Label(selection_frame, text="KPI:", background="#FFFFFF").pack(side="left", padx=(0, 5))
        self.ms_kpi_cb = ttk.Combobox(selection_frame, textvariable=self.ms_kpi_var, state="readonly", width=80)
        self.ms_kpi_cb.pack(side="left", fill="x", expand=True, padx=5)
        self.ms_kpi_cb.bind("<<ComboboxSelected>>", self.on_master_kpi_select)
        details_frame = ttk.Frame(main_frame, style="Card.TFrame")
        details_frame.pack(fill="both", expand=True, pady=10)
        role_frame = ttk.LabelFrame(details_frame, text="KPI Role & Links", style="Card.TLabelframe", padding=10)
        role_frame.pack(fill="both", expand=True, side="left", padx=(0, 5))
        self.ms_role_label_var = tk.StringVar(value="Role: (select a KPI)")
        ttk.Label(role_frame, textvariable=self.ms_role_label_var, font=("Helvetica", 10, "bold"), background="#FFFFFF").pack(anchor="w")
        self.ms_links_tree = ttk.Treeview(role_frame, columns=("ID", "Linked KPI", "Weight"), show="headings")
        self.ms_links_tree.heading("ID", text="ID"); self.ms_links_tree.column("ID", width=50, anchor="center")
        self.ms_links_tree.heading("Linked KPI", text="Linked KPI"); self.ms_links_tree.column("Linked KPI", width=300)
        self.ms_links_tree.heading("Weight", text="Weight"); self.ms_links_tree.column("Weight", width=80, anchor="center")
        self.ms_links_tree.pack(fill="both", expand=True, pady=5)
        linking_frame = ttk.LabelFrame(details_frame, text="Add New Link", style="Card.TLabelframe", padding=10)
        linking_frame.pack(fill="y", side="right", padx=(5, 0))
        ttk.Label(linking_frame, text="Available Sub-KPIs:", background="#FFFFFF").pack(anchor="w")
        self.ms_sub_kpi_cb = ttk.Combobox(linking_frame, textvariable=self.ms_sub_kpi_var, state="readonly", width=50)
        self.ms_sub_kpi_cb.pack(fill="x", expand=True, pady=(0, 5))
        ttk.Label(linking_frame, text="Distribution Weight:", background="#FFFFFF").pack(anchor="w")
        ttk.Entry(linking_frame, textvariable=self.ms_weight_var, width=15).pack(anchor="w", pady=(0, 10))
        self.ms_link_btn = ttk.Button(linking_frame, text="Link Sub-KPI", command=self.link_sub_kpi, state="disabled", style="Action.TButton")
        self.ms_link_btn.pack(pady=5)
        self.ms_unlink_btn = ttk.Button(linking_frame, text="Unlink Selected", command=self.unlink_selected_sub_kpi, state="disabled")
        self.ms_unlink_btn.pack(pady=5)

    def _create_all_kpis_ui(self, parent_frame):
        main_frame = parent_frame
        tree_frame = ttk.Frame(main_frame, style="Card.TFrame", padding=15)
        tree_frame.pack(expand=True, fill="both", pady=(10, 0), padx=5)
        self.all_kpis_tree = ttk.Treeview(tree_frame, columns=("ID", "Group", "Subgroup", "Indicator", "Description", "Calc Type", "Unit", "Visible", "Template SG"), show="headings")
        cols_widths = {"ID": 40, "Group": 120, "Subgroup": 150, "Indicator": 150, "Description": 180, "Calc Type": 90, "Unit": 80, "Visible": 60, "Template SG": 120}
        for col, width in cols_widths.items():
            self.all_kpis_tree.heading(col, text=col)
            self.all_kpis_tree.column(col, width=width, anchor="center" if col in ["ID", "Visible"] else "w")
        tree_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.all_kpis_tree.yview)
        self.all_kpis_tree.configure(yscrollcommand=tree_scrollbar.set)
        tree_scrollbar.pack(side="right", fill="y"); self.all_kpis_tree.pack(side="left", expand=True, fill="both")

    def refresh_all_kpis_tree(self):
        for i in self.all_kpis_tree.get_children(): self.all_kpis_tree.delete(i)
        all_kpis_data = db_retriever.get_all_kpis_detailed()
        for kpi in all_kpis_data:
            self.all_kpis_tree.insert("", "end", values=(kpi["id"], kpi["group_name"], kpi["subgroup_name"], kpi["indicator_name"], 
                                                         kpi["description"], kpi["calculation_type"], kpi["unit_of_measure"], 
                                                         "Yes" if kpi["visible"] else "No", ""))

    def _on_sub_tab_changed(self, event):
        selected_tab = self.notebook.tab(self.notebook.select(), "text")
        if selected_tab == "Hierarchy & Specifications": self.refresh_hierarchy_tree()
        elif selected_tab == "Templates": self.refresh_templates_listbox()
        elif selected_tab == "Master/Sub Links": self.populate_master_kpi_combobox()
        elif selected_tab == "All KPIs": self.refresh_all_kpis_tree()

    def populate_master_kpi_combobox(self):
        self.all_kpis_for_linking = db_retriever.get_all_kpis_detailed()
        self.ms_kpi_cb['values'] = [get_kpi_display_name(kpi) for kpi in self.all_kpis_for_linking]
        self.ms_kpi_var.set(""); self.on_master_kpi_select()

    def on_master_kpi_select(self, event=None):
        name = self.ms_kpi_var.get()
        if not name:
            self.selected_master_kpi_id = None; self.ms_role_label_var.set("Role: (select a KPI)")
            self.ms_links_tree.delete(*self.ms_links_tree.get_children()); self.ms_link_btn.config(state="disabled")
            return
        selected_kpi = next((k for k in self.all_kpis_for_linking if get_kpi_display_name(k) == name), None)
        if not selected_kpi: return
        self.selected_master_kpi_id = selected_kpi["id"]
        role = db_retriever.get_kpi_role_details(self.selected_master_kpi_id)
        self.ms_role_label_var.set(f"Role: {role['role'].capitalize()}")
        self.ms_links_tree.delete(*self.ms_links_tree.get_children())
        if role['role'] == 'master':
            for sub in db_retriever.get_linked_sub_kpis_detailed(self.selected_master_kpi_id):
                self.ms_links_tree.insert("", "end", values=(sub["id"], get_kpi_display_name(sub), sub["distribution_weight"]))
        self.ms_link_btn.config(state="normal"); self.ms_unlink_btn.config(state="normal")

    def link_sub_kpi(self):
        sub_name = self.ms_sub_kpi_var.get()
        sub_kpi = next((k for k in self.all_kpis_for_linking if get_kpi_display_name(k) == sub_name), None)
        if sub_kpi and self.selected_master_kpi_id:
            try:
                kpi_links_manager.link_sub_kpi(self.selected_master_kpi_id, sub_kpi["id"], self.ms_weight_var.get())
                self.on_master_kpi_select()
            except Exception as e: messagebox.showerror("Error", str(e))

    def unlink_selected_sub_kpi(self):
        sel = self.ms_links_tree.selection()
        if sel and self.selected_master_kpi_id:
            sub_id = self.ms_links_tree.item(sel[0])["values"][0]
            try:
                kpi_links_manager.unlink_sub_kpi(self.selected_master_kpi_id, sub_id)
                self.on_master_kpi_select()
            except Exception as e: messagebox.showerror("Error", str(e))

    def on_template_select(self, event=None):
        idx = self.templates_listbox.curselection()
        if idx:
            self.edit_template_btn.config(state="normal"); self.delete_template_btn.config(state="normal")
            self.add_definition_btn.config(state="normal"); self.refresh_template_definitions_tree()
        else:
            self.edit_template_btn.config(state="disabled"); self.add_definition_btn.config(state="disabled")

    def on_template_definition_select(self, event=None):
        sel = self.template_definitions_tree.selection()
        self.edit_definition_btn.config(state="normal" if sel else "disabled")
        self.remove_definition_btn.config(state="normal" if sel else "disabled")

    def refresh_templates_listbox(self):
        self.templates_listbox.delete(0, tk.END); self.current_templates_map = {}
        for t in db_retriever.get_kpi_indicator_templates():
            self.templates_listbox.insert(tk.END, t["name"]); self.current_templates_map[t["id"]] = t
        self.on_template_select()

    def refresh_template_definitions_tree(self):
        for i in self.template_definitions_tree.get_children(): self.template_definitions_tree.delete(i)
        idx = self.templates_listbox.curselection()
        if idx:
            tid = list(self.current_templates_map.keys())[idx[0]]
            for d in db_retriever.get_template_defined_indicators(tid):
                self.template_definitions_tree.insert("", "end", values=(d["id"], d["indicator_name_in_template"], d["default_calculation_type"], d["default_unit_of_measure"], "Yes" if d["default_visible"] else "No", d["default_description"]))
                self.current_template_definitions_map[d["id"]] = dict(d)

    def add_new_kpi_template(self):
        name = simpledialog.askstring("New", "Template Name:")
        if name:
            kpi_templates_manager.add_kpi_template(name.strip())
            self.refresh_templates_listbox()

    def edit_selected_kpi_template(self):
        idx = self.templates_listbox.curselection()
        if idx:
            tid = list(self.current_templates_map.keys())[idx[0]]
            name = simpledialog.askstring("Edit", "New Name:", initialvalue=self.current_templates_map[tid]["name"])
            if name: kpi_templates_manager.update_kpi_template(tid, name.strip()); self.refresh_templates_listbox()

    def delete_selected_kpi_template(self):
        idx = self.templates_listbox.curselection()
        if idx and messagebox.askyesno("Confirm", "Delete template?"):
            kpi_templates_manager.delete_kpi_template(list(self.current_templates_map.keys())[idx[0]])
            self.refresh_templates_listbox()

    def add_new_template_definition(self):
        idx = self.templates_listbox.curselection()
        if idx:
            tid = list(self.current_templates_map.keys())[idx[0]]
            d = TemplateDefinitionEditorDialog(self.app, title="New Def")
            if d.result_data:
                kpi_templates_manager.add_indicator_definition_to_template(tid, d.result_data["indicator_name_in_template"], d.result_data.get("default_calculation_type", "incremental"), d.result_data.get("default_unit_of_measure", ""), d.result_data.get("default_visible", True), d.result_data.get("default_description", ""))
                self.refresh_template_definitions_tree()

    def edit_selected_template_definition(self):
        sel = self.template_definitions_tree.selection()
        if sel:
            did = int(self.template_definitions_tree.item(sel[0], "values")[0])
            data = self.current_template_definitions_map[did]
            d = TemplateDefinitionEditorDialog(self.app, title="Edit Def", initial_data=data)
            if d.result_data:
                kpi_templates_manager.update_indicator_definition_in_template(did, data['template_id'], d.result_data["indicator_name_in_template"], d.result_data.get("default_description", ""), d.result_data.get("default_calculation_type", "incremental"), d.result_data.get("default_unit_of_measure", ""), d.result_data.get("default_visible", True))
                self.refresh_template_definitions_tree()

    def remove_selected_template_definition(self):
        sel = self.template_definitions_tree.selection()
        if sel and messagebox.askyesno("Confirm", "Remove definition?"):
            kpi_templates_manager.delete_template_definition(int(self.template_definitions_tree.item(sel[0], "values")[0]))
            self.refresh_template_definitions_tree()
