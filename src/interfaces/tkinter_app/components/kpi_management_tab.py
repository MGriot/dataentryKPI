# src/gui/app_tkinter/components/kpi_management_tab.py
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
from src.interfaces.tkinter_app.dialogs.link_sub_kpi_dialog import LinkSubKpiDialog


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
        # Main container
        main_frame = ttk.Frame(self, style="Content.TFrame")
        main_frame.pack(fill="both", expand=True)

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill="both", expand=True, padx=15, pady=15)

        # Create frames for each sub-tab - styled as Cards for consistent white background inside tabs
        self.hierarchy_specs_frame = ttk.Frame(self.notebook, style="Card.TFrame")
        self.templates_frame = ttk.Frame(self.notebook, style="Card.TFrame")
        self.master_sub_frame = ttk.Frame(self.notebook, style="Card.TFrame")
        self.all_kpis_frame = ttk.Frame(self.notebook, style="Card.TFrame")

        self.notebook.add(self.hierarchy_specs_frame, text="Hierarchy & Specifications")
        self.notebook.add(self.templates_frame, text="Templates")
        self.notebook.add(self.master_sub_frame, text="Master/Sub Links")
        self.notebook.add(self.all_kpis_frame, text="All KPIs")

        # Populate each frame with its respective UI elements
        self._create_hierarchy_specs_ui(self.hierarchy_specs_frame)
        self._create_templates_ui(self.templates_frame)
        self._create_master_sub_ui(self.master_sub_frame)
        self._create_all_kpis_ui(self.all_kpis_frame)

        # Bind tab change event to refresh data
        self.notebook.bind("<<NotebookTabChanged>>", self._on_sub_tab_changed)

    def _create_hierarchy_specs_ui(self, parent_frame):
        # Use a simple Frame to hold the hierarchy sections
        hierarchy_container_frame = ttk.Frame(parent_frame, style="Card.TFrame", padding=15)
        hierarchy_container_frame.pack(fill="both", expand=True)

        # --- Hierarchy Section (Left Pane) ---
        hierarchy_section_frame = ttk.Frame(hierarchy_container_frame, style="Card.TFrame")
        hierarchy_section_frame.pack(fill="both", expand=True, side="left") 

        # Group Frame
        group_frame = ttk.LabelFrame(hierarchy_section_frame, text="KPI Groups", style="Card.TLabelframe", padding=10)
        group_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.groups_listbox = tk.Listbox(group_frame, exportselection=False, height=15, width=25, relief="flat", borderwidth=1, highlightthickness=1)
        self.groups_listbox.pack(fill="both", expand=True, pady=(0, 5))
        self.groups_listbox.bind("<<ListboxSelect>>", self.on_group_select)

        group_btn_frame = ttk.Frame(group_frame, style="Card.TFrame")
        group_btn_frame.pack(fill="x")
        ttk.Button(group_btn_frame, text="New", command=self.add_new_group, width=8, style="Action.TButton").pack(side="left", padx=2)
        self.edit_group_btn = ttk.Button(group_btn_frame, text="Edit", command=self.edit_selected_group, state="disabled", width=8)
        self.edit_group_btn.pack(side="left", padx=2)
        self.delete_group_btn = ttk.Button(group_btn_frame, text="Delete", command=self.delete_selected_group, state="disabled", width=8)
        self.delete_group_btn.pack(side="left", padx=2)

        # Subgroup Frame
        subgroup_frame = ttk.LabelFrame(hierarchy_section_frame, text="Subgroups", style="Card.TLabelframe", padding=10)
        subgroup_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.subgroups_listbox = tk.Listbox(subgroup_frame, exportselection=False, height=15, width=35, relief="flat", borderwidth=1, highlightthickness=1)
        self.subgroups_listbox.pack(fill="both", expand=True, pady=(0, 5))
        self.subgroups_listbox.bind("<<ListboxSelect>>", self.on_subgroup_select)

        subgroup_btn_frame = ttk.Frame(subgroup_frame, style="Card.TFrame")
        subgroup_btn_frame.pack(fill="x")
        self.add_subgroup_btn = ttk.Button(subgroup_btn_frame, text="New", command=self.add_new_subgroup, state="disabled", width=8, style="Action.TButton")
        self.add_subgroup_btn.pack(side="left", padx=2)
        self.edit_subgroup_btn = ttk.Button(subgroup_btn_frame, text="Edit", command=self.edit_selected_subgroup, state="disabled", width=8)
        self.edit_subgroup_btn.pack(side="left", padx=2)
        self.delete_subgroup_btn = ttk.Button(subgroup_btn_frame, text="Delete", command=self.delete_selected_subgroup, state="disabled", width=8)
        self.delete_subgroup_btn.pack(side="left", padx=2)

        # Indicator Frame
        indicator_frame = ttk.LabelFrame(hierarchy_section_frame, text="Indicators", style="Card.TLabelframe", padding=10)
        indicator_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.indicators_listbox = tk.Listbox(indicator_frame, exportselection=False, height=15, width=30, relief="flat", borderwidth=1, highlightthickness=1)
        self.indicators_listbox.pack(fill="both", expand=True, pady=(0, 5))
        self.indicators_listbox.bind("<<ListboxSelect>>", self.on_indicator_select)

        indicator_btn_frame = ttk.Frame(indicator_frame, style="Card.TFrame")
        indicator_btn_frame.pack(fill="x")
        self.add_indicator_btn = ttk.Button(indicator_btn_frame, text="New", command=self.add_new_indicator, state="disabled", width=8, style="Action.TButton")
        self.add_indicator_btn.pack(side="left", padx=2)
        self.edit_indicator_btn = ttk.Button(indicator_btn_frame, text="Edit", command=self.edit_selected_indicator, state="disabled", width=8)
        self.edit_indicator_btn.pack(side="left", padx=2)
        self.delete_indicator_btn = ttk.Button(indicator_btn_frame, text="Delete", command=self.delete_selected_indicator, state="disabled", width=8)
        self.delete_indicator_btn.pack(side="left", padx=2)

    def _create_templates_ui(self, parent_frame):
        main_frame = parent_frame # Main container for this sub-tab

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
        self.template_definitions_tree = ttk.Treeview(
            definitions_frame,
            columns=("ID", "Indicator Name", "Calc Type", "Unit", "Visible", "Description"),
            show="headings",
            height=14,
        )
        cols_defs = {
            "ID": 40,
            "Indicator Name": 180,
            "Calc Type": 100,
            "Unit": 80,
            "Visible": 60,
            "Description": 220,
        }
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
        # Main container
        main_frame = ttk.Frame(parent_frame, padding=15, style="Card.TFrame")
        main_frame.pack(fill="both", expand=True)

        # Top frame for KPI selection
        selection_frame = ttk.LabelFrame(main_frame, text="Select a KPI to Manage", style="Card.TLabelframe", padding=10)
        selection_frame.pack(fill="x", pady=5)

        ttk.Label(selection_frame, text="KPI:", background="#FFFFFF").pack(side="left", padx=(0, 5))
        self.ms_kpi_var = tk.StringVar()
        self.ms_kpi_cb = ttk.Combobox(selection_frame, textvariable=self.ms_kpi_var, state="readonly", width=80)
        self.ms_kpi_cb.pack(side="left", fill="x", expand=True, padx=5)
        self.ms_kpi_cb.bind("<<ComboboxSelected>>", self.on_master_kpi_select)

        # Frame for details and actions
        details_frame = ttk.Frame(main_frame, style="Card.TFrame")
        details_frame.pack(fill="both", expand=True, pady=10)

        # Role and current links
        role_frame = ttk.LabelFrame(details_frame, text="KPI Role & Links", style="Card.TLabelframe", padding=10)
        role_frame.pack(fill="both", expand=True, side="left", padx=(0, 5))

        self.ms_role_label_var = tk.StringVar(value="Role: (select a KPI)")
        ttk.Label(role_frame, textvariable=self.ms_role_label_var, font=("Helvetica", 10, "bold"), background="#FFFFFF").pack(anchor="w")

        self.ms_links_tree = ttk.Treeview(role_frame, columns=("ID", "Linked KPI", "Weight"), show="headings")
        self.ms_links_tree.heading("ID", text="ID")
        self.ms_links_tree.column("ID", width=50, anchor="center")
        self.ms_links_tree.heading("Linked KPI", text="Linked KPI")
        self.ms_links_tree.column("Linked KPI", width=300)
        self.ms_links_tree.heading("Weight", text="Weight")
        self.ms_links_tree.column("Weight", width=80, anchor="center")
        self.ms_links_tree.pack(fill="both", expand=True, pady=5)

        # Form to add new links
        linking_frame = ttk.LabelFrame(details_frame, text="Add New Link", style="Card.TLabelframe", padding=10)
        linking_frame.pack(fill="y", side="right", padx=(5, 0))

        ttk.Label(linking_frame, text="Available Sub-KPIs:", background="#FFFFFF").pack(anchor="w")
        self.ms_sub_kpi_var = tk.StringVar()
        self.ms_sub_kpi_cb = ttk.Combobox(linking_frame, textvariable=self.ms_sub_kpi_var, state="readonly", width=50)
        self.ms_sub_kpi_cb.pack(fill="x", expand=True, pady=(0, 5))

        ttk.Label(linking_frame, text="Distribution Weight:", background="#FFFFFF").pack(anchor="w")
        self.ms_weight_var = tk.DoubleVar(value=1.0)
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
        cols_widths = {
            "ID": 40,
            "Group": 120,
            "Subgroup": 150,
            "Indicator": 150,
            "Description": 180,
            "Calc Type": 90,
            "Unit": 80,
            "Visible": 60,
            "Template SG": 120,
        }
        for col, width in cols_widths.items():
            self.all_kpis_tree.heading(col, text=col)
            anchor = "center" if col in ["ID", "Visible"] else "w"
            stretch = (
                tk.NO if col in ["ID", "Visible", "Calc Type", "Unit"] else tk.YES
            )
            self.all_kpis_tree.column(col, width=width, anchor=anchor, stretch=stretch)
        tree_scrollbar = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.all_kpis_tree.yview
        )
        self.all_kpis_tree.configure(yscrollcommand=tree_scrollbar.set)
        tree_scrollbar.pack(side="right", fill="y")
        self.all_kpis_tree.pack(side="left", expand=True, fill="both")

    def refresh_all_kpis_tree(self):
        for i in self.all_kpis_tree.get_children():
            self.all_kpis_tree.delete(i)
        all_kpis_data = db_retriever.get_all_kpis_detailed()
        indicator_to_template_name_map = {}
        all_groups_for_map = db_retriever.get_kpi_groups()
        for grp_map_dict in all_groups_for_map:
            subgroups_for_map_list = db_retriever.get_kpi_subgroups_by_group_revised(
                grp_map_dict["id"]
            )
            for sg_map_dict in subgroups_for_map_list:
                if sg_map_dict.get("template_name"):
                    indicators_in_sg_list = db_retriever.get_kpi_indicators_by_subgroup(
                        sg_map_dict["id"]
                    )
                    for ind_map_dict in indicators_in_sg_list:
                        indicator_to_template_name_map[ind_map_dict["id"]] = (
                            sg_map_dict["template_name"]
                        )
        for kpi_row_dict in all_kpis_data:
            template_name_display = indicator_to_template_name_map.get(
                kpi_row_dict["actual_indicator_id"], ""
            )
            self.all_kpis_tree.insert(
                "",
                "end",
                values=(
                    kpi_row_dict["id"],
                    kpi_row_dict["group_name"],
                    kpi_row_dict["subgroup_name"],
                    kpi_row_dict["indicator_name"],
                    kpi_row_dict["description"],
                    kpi_row_dict["calculation_type"],
                    kpi_row_dict["unit_of_measure"] or "",
                    "Yes" if kpi_row_dict["visible"] else "No",
                    template_name_display,
                ),
            )

    def _on_sub_tab_changed(self, event):
        selected_tab = self.notebook.tab(self.notebook.select(), "text")
        if selected_tab == "Hierarchy & Specifications":
            self.refresh_groups_listbox()
        elif selected_tab == "Templates":
            self.refresh_templates_listbox()
        elif selected_tab == "Master/Sub Links":
            self.populate_master_kpi_combobox()
        elif selected_tab == "All KPIs":
            self.refresh_all_kpis_tree()

    def populate_master_kpi_combobox(self):
        self.all_kpis_for_linking = db_retriever.get_all_kpis_detailed()
        self.ms_kpi_cb['values'] = [get_kpi_display_name(kpi) for kpi in self.all_kpis_for_linking]
        self.ms_kpi_var.set("")
        self.on_master_kpi_select()

    def on_master_kpi_select(self, event=None):
        selected_kpi_name = self.ms_kpi_var.get()
        if not selected_kpi_name:
            self.selected_master_kpi_id = None
            self.ms_role_label_var.set("Role: (select a KPI)")
            self.ms_links_tree.delete(*self.ms_links_tree.get_children())
            self.ms_sub_kpi_cb['values'] = []
            self.ms_sub_kpi_var.set("")
            self.ms_link_btn.config(state="disabled")
            self.ms_unlink_btn.config(state="disabled")
            return

        selected_kpi = next((kpi for kpi in self.all_kpis_for_linking if get_kpi_display_name(kpi) == selected_kpi_name), None)
        if not selected_kpi:
            return

        self.selected_master_kpi_id = selected_kpi["id"]
        role_details = db_retriever.get_kpi_role_details(self.selected_master_kpi_id)

        # Update role label
        self.ms_role_label_var.set(f"Role: {role_details['role'].capitalize()}")

        # Update links tree
        self.ms_links_tree.delete(*self.ms_links_tree.get_children())
        if role_details['role'] == 'master':
            linked_sub_kpis = db_retriever.get_linked_sub_kpis_detailed(self.selected_master_kpi_id)
            for sub_kpi in linked_sub_kpis:
                self.ms_links_tree.insert("", "end", values=(sub_kpi["id"], get_kpi_display_name(sub_kpi), sub_kpi["distribution_weight"]))
        elif role_details['role'] == 'sub':
            master_kpi = db_retriever.get_kpi_detailed_by_id(role_details['master_id'])
            if master_kpi:
                self.ms_links_tree.insert("", "end", values=(master_kpi["id"], get_kpi_display_name(master_kpi), "N/A"))

        # Update available sub-KPIs combobox
        existing_links = db_retriever.get_all_master_sub_kpi_links()
        linked_kpi_ids = {link['master_kpi_spec_id'] for link in existing_links} | {link['sub_kpi_spec_id'] for link in existing_links}

        available_sub_kpis = [kpi for kpi in self.all_kpis_for_linking if kpi["id"] != self.selected_master_kpi_id and kpi["id"] not in linked_kpi_ids]
        self.ms_sub_kpi_cb['values'] = [get_kpi_display_name(kpi) for kpi in available_sub_kpis]
        self.ms_sub_kpi_var.set("")

        self.ms_link_btn.config(state="normal")
        self.ms_unlink_btn.config(state="normal")

    def link_sub_kpi(self):
        if not self.selected_master_kpi_id:
            messagebox.showwarning("Warning", "Please select a master KPI first.")
            return

        selected_sub_kpi_name = self.ms_sub_kpi_var.get()
        if not selected_sub_kpi_name:
            messagebox.showwarning("Warning", "Please select a sub-KPI to link.")
            return

        sub_kpi_to_link = next((kpi for kpi in self.all_kpis_for_linking if get_kpi_display_name(kpi) == selected_sub_kpi_name), None)
        if not sub_kpi_to_link:
            messagebox.showerror("Error", "Selected sub-KPI not found.")
            return

        try:
            weight = self.ms_weight_var.get()
            if weight <= 0:
                messagebox.showerror("Error", "Weight must be a positive number.")
                return

            kpi_links_manager.link_sub_kpi(self.selected_master_kpi_id, sub_kpi_to_link["id"], weight)
            messagebox.showinfo("Success", "KPI linked successfully.")
            self.on_master_kpi_select()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to link KPI: {e}")

    def unlink_selected_sub_kpi(self):
        selected_items = self.ms_links_tree.selection()
        if not selected_items:
            messagebox.showwarning("Warning", "Please select a linked KPI to unlink.")
            return

        sub_kpi_id = self.ms_links_tree.item(selected_items[0])["values"][0]

        try:
            kpi_links_manager.unlink_sub_kpi(self.selected_master_kpi_id, sub_kpi_id)
            messagebox.showinfo("Success", "KPI unlinked successfully.")
            self.on_master_kpi_select()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to unlink KPI: {e}")

    def on_group_select(self, event=None):
        selected_indices = self.groups_listbox.curselection()
        if selected_indices:
            self.edit_group_btn.config(state="normal")
            self.delete_group_btn.config(state="normal")
            self.add_subgroup_btn.config(state="normal")
            self.refresh_subgroups_listbox()
        else:
            self.edit_group_btn.config(state="disabled")
            self.delete_group_btn.config(state="disabled")
            self.add_subgroup_btn.config(state="disabled")
            self.subgroups_listbox.delete(0, tk.END)
            self.indicators_listbox.delete(0, tk.END)
            self.edit_subgroup_btn.config(state="disabled")
            self.delete_subgroup_btn.config(state="disabled")
            self.add_indicator_btn.config(state="disabled")
            self.edit_indicator_btn.config(state="disabled")
            self.delete_indicator_btn.config(state="disabled")

    def on_subgroup_select(self, event=None):
        selected_indices = self.subgroups_listbox.curselection()
        if selected_indices:
            self.edit_subgroup_btn.config(state="normal")
            self.delete_subgroup_btn.config(state="normal")
            self.add_indicator_btn.config(state="normal")
            self.refresh_indicators_listbox()
        else:
            self.edit_subgroup_btn.config(state="disabled")
            self.delete_subgroup_btn.config(state="disabled")
            self.add_indicator_btn.config(state="disabled")
            self.indicators_listbox.delete(0, tk.END)
            self.edit_indicator_btn.config(state="disabled")
            self.delete_indicator_btn.config(state="disabled")

    def on_indicator_select(self, event=None):
        selected_indices = self.indicators_listbox.curselection()
        if selected_indices:
            self.edit_indicator_btn.config(state="normal")
            self.delete_indicator_btn.config(state="normal")
        else:
            self.edit_indicator_btn.config(state="disabled")
            self.delete_indicator_btn.config(state="disabled")

    def on_template_select(self, event=None):
        selected_indices = self.templates_listbox.curselection()
        if selected_indices:
            self.edit_template_btn.config(state="normal")
            self.delete_template_btn.config(state="normal")
            self.add_definition_btn.config(state="normal")
            self.refresh_template_definitions_tree()
        else:
            self.edit_template_btn.config(state="disabled")
            self.delete_template_btn.config(state="disabled")
            self.add_definition_btn.config(state="disabled")
            for i in self.template_definitions_tree.get_children():
                self.template_definitions_tree.delete(i)
            self.edit_definition_btn.config(state="disabled")
            self.remove_definition_btn.config(state="disabled")

    def on_template_definition_select(self, event=None):
        selected_items = self.template_definitions_tree.selection()
        if selected_items:
            self.edit_definition_btn.config(state="normal")
            self.remove_definition_btn.config(state="normal")
        else:
            self.edit_definition_btn.config(state="disabled")
            self.remove_definition_btn.config(state="disabled")

    def refresh_groups_listbox(self):
        self.groups_listbox.delete(0, tk.END)
        self.current_groups_map = {}
        groups = kpi_groups_manager.get_kpi_groups()
        for group in groups:
            self.groups_listbox.insert(tk.END, group["name"])
            self.current_groups_map[group["id"]] = group
        self.on_group_select() # Update button states and subgroups listbox

    def refresh_subgroups_listbox(self):
        self.subgroups_listbox.delete(0, tk.END)
        self.current_subgroups_map = {}
        selected_indices = self.groups_listbox.curselection()
        if selected_indices:
            group_id = list(self.current_groups_map.keys())[selected_indices[0]]
            subgroups = kpi_subgroups_manager.get_kpi_subgroups_by_group_revised(group_id)
            for subgroup in subgroups:
                self.subgroups_listbox.insert(tk.END, subgroup["name"])
                self.current_subgroups_map[subgroup["id"]] = subgroup
        self.on_subgroup_select() # Update button states and indicators listbox

    def refresh_indicators_listbox(self):
        self.indicators_listbox.delete(0, tk.END)
        self.current_indicators_map = {}
        selected_indices = self.subgroups_listbox.curselection()
        if selected_indices:
            subgroup_id = list(self.current_subgroups_map.keys())[selected_indices[0]]
            indicators = kpi_indicators_manager.get_kpi_indicators_by_subgroup(subgroup_id)
            for indicator in indicators:
                self.indicators_listbox.insert(tk.END, indicator["name"])
                self.current_indicators_map[indicator["id"]] = indicator
        self.on_indicator_select() # Update button states

    def refresh_templates_listbox(self):
        self.templates_listbox.delete(0, tk.END)
        self.current_templates_map = {}
        templates = db_retriever.get_kpi_indicator_templates()
        for template in templates:
            self.templates_listbox.insert(tk.END, template["name"])
            self.current_templates_map[template["id"]] = template
        self.on_template_select() # Update button states and definitions tree

    def refresh_template_definitions_tree(self):
        for i in self.template_definitions_tree.get_children():
            self.template_definitions_tree.delete(i)
        self.current_template_definitions_map = {}
        selected_indices = self.templates_listbox.curselection()
        if selected_indices:
            template_id = list(self.current_templates_map.keys())[selected_indices[0]]
            definitions = db_retriever.get_template_defined_indicators(template_id)
            for definition_row in definitions:
                definition = dict(definition_row) # Convert from sqlite3.Row
                self.template_definitions_tree.insert(
                    "", "end",
                    values=(
                        definition["id"],
                        definition["indicator_name_in_template"],
                        definition["default_calculation_type"],
                        definition["default_unit_of_measure"],
                        "Yes" if definition["default_visible"] else "No",
                        definition["default_description"]
                    )
                )
                self.current_template_definitions_map[definition["id"]] = definition
        self.on_template_definition_select() # Update button states

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
                self.refresh_groups_listbox()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add KPI Group: {e}\n{traceback.format_exc()}")

    def edit_selected_group(self):
        selected_indices = self.groups_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Selection Error", "Please select a group to edit.")
            return

        group_id = list(self.current_groups_map.keys())[selected_indices[0]]
        current_group_name = self.current_groups_map[group_id]["name"]

        new_group_name = simpledialog.askstring("Edit KPI Group", f"Edit name for '{current_group_name}':", initialvalue=current_group_name, parent=self)
        if new_group_name:
            new_group_name = new_group_name.strip()
            if not new_group_name:
                messagebox.showerror("Input Error", "Group name cannot be empty.")
                return
            if new_group_name == current_group_name:
                messagebox.showinfo("No Change", "Group name is the same. No update performed.")
                return
            try:
                kpi_groups_manager.update_kpi_group(group_id, new_group_name)
                messagebox.showinfo("Success", f"KPI Group updated to '{new_group_name}' successfully.")
                self.refresh_groups_listbox()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update KPI Group: {e}\n{traceback.format_exc()}")

    def delete_selected_group(self):
        selected_indices = self.groups_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Selection Error", "Please select a group to delete.")
            return

        group_id = list(self.current_groups_map.keys())[selected_indices[0]]
        group_name = self.current_groups_map[group_id]["name"]

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete KPI Group '{group_name}'? This will also delete all associated subgroups and indicators.", parent=self):
            try:
                kpi_groups_manager.delete_kpi_group(group_id)
                messagebox.showinfo("Success", f"KPI Group '{group_name}' deleted successfully.")
                self.refresh_groups_listbox()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete KPI Group: {e}\n{traceback.format_exc()}")

    def add_new_subgroup(self):
        selected_group_idx = self.groups_listbox.curselection()
        if not selected_group_idx:
            messagebox.showwarning("Selection Error", "Please select a group first.")
            return

        group_id = list(self.current_groups_map.keys())[selected_group_idx[0]]
        group_name = self.current_groups_map[group_id]["name"]

        dialog = SubgroupEditorDialog(self.app, title=f"New Subgroup in {group_name}", group_id=group_id)
        if dialog.result_data:
            subgroup_name = dialog.result_data["name"]
            template_name = dialog.result_data["template_name"]
            try:
                kpi_subgroups_manager.add_kpi_subgroup(subgroup_name, group_id, template_name)
                messagebox.showinfo("Success", f"Subgroup '{subgroup_name}' added successfully to '{group_name}'.")
                self.refresh_subgroups_listbox()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add Subgroup: {e}\n{traceback.format_exc()}")

    def edit_selected_subgroup(self):
        selected_indices = self.subgroups_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Selection Error", "Please select a subgroup to edit.")
            return

        subgroup_id = list(self.current_subgroups_map.keys())[selected_indices[0]]
        subgroup_data = self.current_subgroups_map[subgroup_id]
        current_subgroup_name = subgroup_data["name"]
        current_template_name = subgroup_data.get("template_name", "")
        current_group_id = subgroup_data["group_id"]

        dialog = SubgroupEditorDialog(self.app, title=f"Edit Subgroup: {current_subgroup_name}", 
                                      group_id=current_group_id, 
                                      initial_subgroup_name=current_subgroup_name, 
                                      initial_template_name=current_template_name)
        if dialog.result_data:
            new_subgroup_name = dialog.result_data["name"]
            new_template_name = dialog.result_data["template_name"]
            try:
                kpi_subgroups_manager.update_kpi_subgroup(subgroup_id, new_subgroup_name, current_group_id, new_template_name)
                messagebox.showinfo("Success", f"Subgroup '{current_subgroup_name}' updated to '{new_subgroup_name}'.")
                self.refresh_subgroups_listbox()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update Subgroup: {e}\n{traceback.format_exc()}")

    def delete_selected_subgroup(self):
        selected_indices = self.subgroups_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Selection Error", "Please select a subgroup to delete.")
            return

        subgroup_id = list(self.current_subgroups_map.keys())[selected_indices[0]]
        subgroup_name = self.current_subgroups_map[subgroup_id]["name"]

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete Subgroup '{subgroup_name}'? This will also delete all associated indicators.", parent=self):
            try:
                kpi_subgroups_manager.delete_kpi_subgroup(subgroup_id)
                messagebox.showinfo("Success", f"Subgroup '{subgroup_name}' deleted successfully.")
                self.refresh_subgroups_listbox()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete Subgroup: {e}\n{traceback.format_exc()}")

    def add_new_indicator(self):
        selected_subgroup_idx = self.subgroups_listbox.curselection()
        if not selected_subgroup_idx:
            messagebox.showwarning("Selection Error", "Please select a subgroup first.")
            return

        subgroup_id = list(self.current_subgroups_map.keys())[selected_subgroup_idx[0]]
        subgroup_name = self.current_subgroups_map[subgroup_id]["name"]

        # Open the dialog for adding/editing indicator details, including name
        dialog = IndicatorSpecEditorDialog(self.app, title=f"New KPI Indicator in {subgroup_name}")

        if dialog.result_data:
            indicator_name = dialog.result_data["indicator_name"].strip()
            if not indicator_name:
                messagebox.showerror("Input Error", "Indicator name cannot be empty.")
                return

            # Check for duplicate indicator name within the subgroup
            existing_indicators = kpi_indicators_manager.get_kpi_indicators_by_subgroup(subgroup_id)
            if any(ind['name'].lower() == indicator_name.lower() for ind in existing_indicators):
                messagebox.showerror("Duplicate Name", f"An indicator named '{indicator_name}' already exists in subgroup '{subgroup_name}'.")
                return

            try:
                new_indicator_id = kpi_indicators_manager.add_kpi_indicator(indicator_name, subgroup_id)
                # Save the spec data
                kpi_specs_manager.add_kpi_spec(
                    indicator_id=new_indicator_id,
                    description=dialog.result_data.get("description", ""),
                    calculation_type=dialog.result_data.get("calculation_type", KPI_CALC_TYPE_OPTIONS[0]),
                    unit_of_measure=dialog.result_data.get("unit_of_measure", ""),
                    visible=dialog.result_data.get("visible", True)
                )
                # Save per-plant visibility
                for pv_data in dialog.result_data.get("per_plant_visibility", []):
                    kpi_visibility.set_kpi_plant_visibility(new_indicator_id, pv_data["plant_id"], pv_data["is_enabled"])

                messagebox.showinfo("Success", f"KPI Indicator '{indicator_name}' added successfully.")
                self.refresh_indicators_listbox()
                self.refresh_all_kpis_tree()
            except Exception as e:
                # If an error occurs during spec saving, and the indicator was just added, delete it.
                if 'new_indicator_id' in locals() and new_indicator_id:
                    kpi_indicators_manager.delete_kpi_indicator(new_indicator_id)
                messagebox.showerror("Error", f"""Failed to add KPI Indicator: {e}
{traceback.format_exc()}                    """)

    def edit_selected_indicator(self):
        selected_indicator_idx = self.indicators_listbox.curselection()
        if not selected_indicator_idx:
            messagebox.showwarning("Selection Error", "Please select an indicator to edit.")
            return

        indicator_id = list(self.current_indicators_map.keys())[selected_indicator_idx[0]]
        indicator_data = self.current_indicators_map[indicator_id]
        current_indicator_name = indicator_data["name"]
        current_subgroup_id = indicator_data["subgroup_id"]

        # Retrieve existing spec data for the indicator
        existing_spec = kpi_specs_manager.get_kpi_spec_by_indicator_id(indicator_id)
        initial_spec_data = existing_spec if existing_spec else {}
        # Retrieve existing per-plant visibility
        initial_spec_data["per_plant_visibility"] = kpi_visibility.get_plants_for_kpi(indicator_id)

        # Open the dialog for editing
        dialog = IndicatorSpecEditorDialog(self.app, title=f"Edit KPI Indicator: {current_indicator_name}",
                                           initial_indicator_name=current_indicator_name,
                                           initial_spec_data=initial_spec_data)

        if dialog.result_data:
            new_indicator_name = dialog.result_data["indicator_name"].strip()
            if not new_indicator_name:
                messagebox.showerror("Input Error", "Indicator name cannot be empty.")
                return

            # Check for duplicate name if name changed
            if new_indicator_name.lower() != current_indicator_name.lower():
                existing_indicators = kpi_indicators_manager.get_kpi_indicators_by_subgroup(current_subgroup_id)
                if any(ind['name'].lower() == new_indicator_name.lower() for ind in existing_indicators if ind['id'] != indicator_id):
                    messagebox.showerror("Duplicate Name", f"An indicator named '{new_indicator_name}' already exists in this subgroup.")
                    return

            try:
                # Update indicator name if changed
                if new_indicator_name != current_indicator_name:
                    kpi_indicators_manager.update_kpi_indicator(indicator_id, new_indicator_name, current_subgroup_id)

                # Update or add spec data
                kpi_specs_manager.add_kpi_spec( # add_kpi_spec handles both add and update based on indicator_id uniqueness
                    indicator_id=indicator_id,
                    description=dialog.result_data.get("description", ""),
                    calculation_type=dialog.result_data.get("calculation_type", KPI_CALC_TYPE_OPTIONS[0]),
                    unit_of_measure=dialog.result_data.get("unit_of_measure", ""),
                    visible=dialog.result_data.get("visible", True)
                )
                # Update per-plant visibility
                # First, delete all existing entries for this KPI to ensure clean update
                # This is a simplified approach; a more robust solution might compare and update only changed entries.
                # However, get_plants_for_kpi only returns explicit settings, not default True ones.
                # So, we need to iterate through all plants and set their visibility.
                # A direct delete all for this KPI's plant visibility is not available in kpi_visibility.py
                # So, we will just overwrite.
                for pv_data in dialog.result_data.get("per_plant_visibility", []):
                    kpi_visibility.set_kpi_plant_visibility(indicator_id, pv_data["plant_id"], pv_data["is_enabled"])

                messagebox.showinfo("Success", f"KPI Indicator '{new_indicator_name}' updated successfully.")
                self.refresh_indicators_listbox()
                self.refresh_all_kpis_tree()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update KPI Indicator: {e}\n{traceback.format_exc()}")

    def delete_selected_indicator(self):
        selected_indices = self.indicators_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Selection Error", "Please select an indicator to delete.")
            return

        indicator_id = list(self.current_indicators_map.keys())[selected_indices[0]]
        indicator_name = self.current_indicators_map[indicator_id]["name"]

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete KPI Indicator '{indicator_name}'?", parent=self):
            try:
                kpi_indicators_manager.delete_kpi_indicator(indicator_id)
                messagebox.showinfo("Success", f"KPI Indicator '{indicator_name}' deleted successfully.")
                self.refresh_indicators_listbox()
                self.refresh_all_kpis_tree()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete KPI Indicator: {e}\n{traceback.format_exc()}")

    def add_new_kpi_template(self):
        template_name = simpledialog.askstring("New KPI Template", "Enter name for new KPI Template:", parent=self)
        if template_name:
            template_name = template_name.strip()
            if not template_name:
                messagebox.showerror("Input Error", "Template name cannot be empty.")
                return
            try:
                kpi_templates_manager.add_kpi_template(template_name)
                messagebox.showinfo("Success", f"KPI Template '{template_name}' added successfully.")
                self.refresh_templates_listbox()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add KPI Template: {e}\n{traceback.format_exc()}")

    def edit_selected_kpi_template(self):
        selected_indices = self.templates_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Selection Error", "Please select a template to edit.")
            return

        template_id = list(self.current_templates_map.keys())[selected_indices[0]]
        current_template_name = self.current_templates_map[template_id]["name"]

        new_template_name = simpledialog.askstring("Edit KPI Template", f"Edit name for '{current_template_name}':", initialvalue=current_template_name, parent=self)
        if new_template_name:
            new_template_name = new_template_name.strip()
            if not new_template_name:
                messagebox.showerror("Input Error", "Template name cannot be empty.")
                return
            if new_template_name == current_template_name:
                messagebox.showinfo("No Change", "Template name is the same. No update performed.")
                return
            try:
                kpi_templates_manager.update_kpi_template(template_id, new_template_name)
                messagebox.showinfo("Success", f"KPI Template updated to '{new_template_name}' successfully.")
                self.refresh_templates_listbox()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update KPI Template: {e}\n{traceback.format_exc()}")

    def delete_selected_kpi_template(self):
        selected_indices = self.templates_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Selection Error", "Please select a template to delete.")
            return

        template_id = list(self.current_templates_map.keys())[selected_indices[0]]
        template_name = self.current_templates_map[template_id]["name"]

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete KPI Template '{template_name}'? This will also delete all associated definitions.", parent=self):
            try:
                kpi_templates_manager.delete_kpi_template(template_id)
                messagebox.showinfo("Success", f"KPI Template '{template_name}' deleted successfully.")
                self.refresh_templates_listbox()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete KPI Template: {e}\n{traceback.format_exc()}")

    def add_new_template_definition(self):
        selected_template_idx = self.templates_listbox.curselection()
        if not selected_template_idx:
            messagebox.showwarning("Selection Error", "Please select a template first.")
            return

        template_id = list(self.current_templates_map.keys())[selected_template_idx[0]]
        template_name = self.current_templates_map[template_id]["name"]

        dialog = TemplateDefinitionEditorDialog(self.app, title=f"New Definition in Template '{template_name}'")
        if dialog.result_data:
            indicator_name = dialog.result_data["indicator_name_in_template"]
            description = dialog.result_data.get("default_description", "")
            calculation_type = dialog.result_data.get("default_calculation_type", KPI_CALC_TYPE_OPTIONS[0])
            unit_of_measure = dialog.result_data.get("default_unit_of_measure", "")
            visible = dialog.result_data.get("default_visible", True)
            try:
                kpi_templates_manager.add_indicator_definition_to_template(
                    template_id, indicator_name, calculation_type, unit_of_measure, visible, description
                )
                messagebox.showinfo("Success", f"Definition '{indicator_name}' added successfully to template '{template_name}'.")
                self.refresh_template_definitions_tree()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add Template Definition: {e}\n{traceback.format_exc()}")

    def edit_selected_template_definition(self):
        selected_items = self.template_definitions_tree.selection()
        if not selected_items:
            messagebox.showwarning("Selection Error", "Please select a definition to edit.")
            return

        definition_id = self.template_definitions_tree.item(selected_items[0], "values")[0]
        definition_data = self.current_template_definitions_map[int(definition_id)]

        # The dialog expects 'initial_data' as the keyword argument
        dialog = TemplateDefinitionEditorDialog(self.app, title=f"Edit Definition: {definition_data['indicator_name_in_template']}", initial_data=definition_data)
        if dialog.result_data:
            indicator_name = dialog.result_data["indicator_name_in_template"]
            description = dialog.result_data.get("default_description", "")
            calculation_type = dialog.result_data.get("default_calculation_type", KPI_CALC_TYPE_OPTIONS[0])
            unit_of_measure = dialog.result_data.get("default_unit_of_measure", "")
            visible = dialog.result_data.get("default_visible", True)
            try:
                # The update function in the manager module is named 'update_indicator_definition_in_template'
                kpi_templates_manager.update_indicator_definition_in_template(
                    definition_id=int(definition_id),
                    template_id=definition_data['template_id'],
                    indicator_name=indicator_name,
                    description=description,
                    calc_type=calculation_type,
                    unit=unit_of_measure,
                    visible=visible
                )
                messagebox.showinfo("Success", f"Definition '{indicator_name}' updated successfully.")
                self.refresh_template_definitions_tree()
            except Exception as e:
                messagebox.showerror(
                    "Error",
                    f"Failed to update Template Definition: {e}\n{traceback.format_exc()}",
                )

    def remove_selected_template_definition(self):
        selected_items = self.template_definitions_tree.selection()
        if not selected_items:
            messagebox.showwarning("Selection Error", "Please select a definition to remove.")
            return

        definition_id = self.template_definitions_tree.item(selected_items[0], "values")[0]
        definition_name = self.template_definitions_tree.item(selected_items[0], "values")[1]

        if messagebox.askyesno("Confirm Remove", f"Are you sure you want to remove definition '{definition_name}' from this template?", parent=self):
            try:
                kpi_templates_manager.delete_template_definition(int(definition_id))
                messagebox.showinfo("Success", f"Definition '{definition_name}' removed successfully.")
                self.refresh_template_definitions_tree()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to remove Template Definition: {e}\n{traceback.format_exc()}")
