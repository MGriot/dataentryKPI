import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import calendar
from src import data_retriever as db_retriever
from src.interfaces.common_ui.helpers import get_kpi_display_name
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import pandas as pd
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import traceback

class AnalysisTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.target1_display_name = self.app.settings.get('display_names', {}).get('target1', 'Target 1')
        self.target2_display_name = self.app.settings.get('display_names', {}).get('target2', 'Target 2')
        
        self.view_mode = tk.StringVar(value="single")

        # Initialize single KPI view variables
        self.res_year_var_vis = tk.StringVar()
        self.res_plant_var_vis = tk.StringVar()
        self.res_period_var_vis = tk.StringVar()
        self.res_group_var = tk.StringVar()
        self.res_subgroup_var = tk.StringVar()
        self.res_indicator_var = tk.StringVar()
        self.summary_label_var_vis = tk.StringVar()
        self.res_plants_map_vis = {}
        self.res_groups_list = []
        self.res_subgroups_list_details = []
        self.res_subgroup_display_to_raw_map = {}
        self.res_indicators_list_filtered_details = []
        self.current_kpi_id_for_results = None

        # Initialize global dashboard view variables
        self.dashboard_year_var = tk.StringVar()
        self.dashboard_period_var = tk.StringVar()
        
        self.create_widgets()

    def on_tab_selected(self):
        if self.view_mode.get() == "single":
            self.populate_results_comboboxes()
        else:
            self.populate_dashboard_comboboxes()

    def _sort_periods(self, periods, period_type):
        if periods is None or len(periods) == 0:
            return []

        if isinstance(periods, pd.Series):
            periods = periods.tolist()

        if period_type == 'Month':
            english_months_map = {
                'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
                'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12
            }
            return sorted(periods, key=lambda p: english_months_map.get(p, 0))
        elif period_type == 'Quarter':
            quarters_map = {'Q1': 1, 'Q2': 2, 'Q3': 3, 'Q4': 4}
            return sorted(periods, key=lambda p: quarters_map.get(p, 0))
        elif period_type == 'Week':
            return sorted(periods, key=lambda p: (int(p.split('-W')[0]), int(p.split('-W')[1])))
        elif period_type == 'Day':
            return sorted(periods, key=lambda p: datetime.datetime.strptime(p, '%Y-%m-%d'))
        else: # Year
            return sorted(periods, key=lambda p: int(p))

    def switch_view(self):
        # Clear existing content
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        if self.view_mode.get() == "single":
            self.create_single_kpi_view()
            self.populate_results_comboboxes()
        else:
            self.create_global_dashboard_view()
            self.populate_dashboard_comboboxes()

    def get_plant_color(self, plant_name):
        # Fallback colors if not in settings
        color_list = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
        plant_colors_settings = self.app.settings.get('plant_colors', {})
        if plant_name in plant_colors_settings:
            return plant_colors_settings[plant_name]
        
        # If not in settings, use internal map or generate
        if not hasattr(self, '_internal_plant_colors'):
            self._internal_plant_colors = {}
        
        if plant_name not in self._internal_plant_colors:
            self._internal_plant_colors[plant_name] = color_list[len(self._internal_plant_colors) % len(color_list)]
        
        return self._internal_plant_colors[plant_name]

    def populate_dashboard_comboboxes(self):
        years = [str(y["year"]) for y in db_retriever.get_distinct_years()]
        self.dashboard_year_cb["values"] = ["All"] + years
        if not self.dashboard_year_var.get():
            self.dashboard_year_var.set("All")
        self.load_dashboard_data()

    def load_dashboard_data(self, event=None):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        year_str = self.dashboard_year_var.get()
        year = int(year_str) if year_str != "All" and year_str else None
        period_type = self.dashboard_period_var.get()

        try:
            all_kpis = db_retriever.get_all_kpis_detailed(only_visible=True)
            if not all_kpis:
                ttk.Label(self.scrollable_frame, text="No visible KPIs defined.", background="#FFFFFF").pack(pady=20)
                return

            for kpi in all_kpis:
                kpi_id = kpi["id"]
                kpi_display_name = get_kpi_display_name(kpi)
                
                kpi_data = db_retriever.get_periodic_targets_for_kpi_all_plants(kpi_id, period_type, year)
                if not kpi_data:
                    continue

                df = pd.DataFrame([dict(row) for row in kpi_data])

                chart_card = ttk.LabelFrame(self.scrollable_frame, text=kpi_display_name, style="Card.TLabelframe", padding=10)
                chart_card.pack(fill="x", expand=True, padx=10, pady=10)

                fig = Figure(figsize=(10, 5), dpi=100)
                ax = fig.add_subplot(111)

                for plant_name, plant_data in df.groupby('plant_name'):
                    color = self.get_plant_color(plant_name)
                    # Filter by target_number if available in data
                    t1_df = plant_data[plant_data['target_number'] == 1] if 'target_number' in plant_data.columns else plant_data
                    t2_df = plant_data[plant_data['target_number'] == 2] if 'target_number' in plant_data.columns else pd.DataFrame()

                    if not t1_df.empty:
                        ax.plot(t1_df['period'], t1_df['target_value'], marker='o', linestyle='-', label=f'{plant_name} - {self.target1_display_name}', color=color)
                    if not t2_df.empty:
                        ax.plot(t2_df['period'], t2_df['target_value'], marker='x', linestyle='--', label=f'{plant_name} - {self.target2_display_name}', color=color)

                ax.set_title(f"{period_type} Trend - {kpi_display_name}")
                ax.set_xlabel(period_type)
                ax.set_ylabel("Value")
                ax.legend(fontsize='small', loc='upper right')
                ax.grid(True, linestyle='--', alpha=0.6)
                fig.tight_layout()

                canvas = FigureCanvasTkAgg(fig, master=chart_card)
                canvas.get_tk_widget().pack(fill="both", expand=True)
                canvas.draw()

        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Data Loading Error", f"Could not load dashboard data: {e}")

    def _bind_dashboard_mousewheel(self, event):
        self.main_canvas.bind_all("<MouseWheel>", self._on_dashboard_mousewheel)

    def _unbind_dashboard_mousewheel(self, event):
        self.main_canvas.unbind_all("<MouseWheel>")

    def _on_dashboard_mousewheel(self, event):
        self.main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def create_widgets(self):
        # --- View Mode Selection ---
        view_mode_frame = ttk.Frame(self, style="Content.TFrame")
        view_mode_frame.pack(fill="x", pady=10)
        
        rb1 = ttk.Radiobutton(view_mode_frame, text="Single KPI Analysis", variable=self.view_mode, value="single", command=self.switch_view)
        rb1.pack(side="left", padx=15)
        rb2 = ttk.Radiobutton(view_mode_frame, text="Global Dashboard", variable=self.view_mode, value="global", command=self.switch_view)
        rb2.pack(side="left", padx=15)

        # --- Main container for content ---
        self.content_frame = ttk.Frame(self, style="Content.TFrame")
        self.content_frame.pack(fill="both", expand=True)

        self.switch_view()

    # --- Single KPI Analysis (ResultsTab) ---
    def create_single_kpi_view(self):
        # Main container for filters, table, and chart
        results_main_container = ttk.Frame(self.content_frame, style="Content.TFrame")
        results_main_container.pack(fill="both", expand=True)

        # --- Filters Frame (Card) ---
        filter_card = ttk.Frame(results_main_container, style="Card.TFrame", padding=15)
        filter_card.pack(fill="x", padx=0, pady=(0, 15))

        row1_filters = ttk.Frame(filter_card, style="Card.TFrame")
        row1_filters.pack(fill="x", pady=5)
        ttk.Label(row1_filters, text="Year:", background="#FFFFFF").pack(side="left")
        self.res_year_var_vis = tk.StringVar(value=str(datetime.datetime.now().year))
        ttk.Spinbox(
            row1_filters,
            from_=2020,
            to=2050,
            textvariable=self.res_year_var_vis,
            width=6,
            command=self.show_results_data,
        ).pack(side="left", padx=(5, 15))
        
        ttk.Label(row1_filters, text="Plant:", background="#FFFFFF").pack(side="left")
        self.res_plant_var_vis = tk.StringVar()
        self.res_plant_cb_vis = ttk.Combobox(
            row1_filters,
            textvariable=self.res_plant_var_vis,
            state="readonly",
            width=20,
        )
        self.res_plant_cb_vis.pack(side="left", padx=(5, 15))
        self.res_plant_cb_vis.bind("<<ComboboxSelected>>", self.show_results_data)
        
        ttk.Label(row1_filters, text="Period:", background="#FFFFFF").pack(side="left")
        self.res_period_var_vis = tk.StringVar(value="Month")
        self.res_period_cb_vis = ttk.Combobox(
            row1_filters,
            textvariable=self.res_period_var_vis,
            state="readonly",
            values=["Day", "Week", "Month", "Quarter"],
            width=10,
        )
        self.res_period_cb_vis.current(2)
        self.res_period_cb_vis.pack(side="left", padx=(5, 15))
        self.res_period_cb_vis.bind("<<ComboboxSelected>>", self.show_results_data)

        row2_filters = ttk.Frame(filter_card, style="Card.TFrame")
        row2_filters.pack(fill="x", pady=5)
        ttk.Label(row2_filters, text="Group:", background="#FFFFFF").pack(side="left")
        self.res_group_var = tk.StringVar()
        self.res_group_cb = ttk.Combobox(
            row2_filters, textvariable=self.res_group_var, state="readonly", width=20
        )
        self.res_group_cb.pack(side="left", padx=(5, 15))
        self.res_group_cb.bind(
            "<<ComboboxSelected>>", self.on_res_group_selected_refresh_results
        )
        
        ttk.Label(row2_filters, text="Subgroup:", background="#FFFFFF").pack(side="left")
        self.res_subgroup_var = tk.StringVar()
        self.res_subgroup_cb = ttk.Combobox(
            row2_filters,
            textvariable=self.res_subgroup_var,
            state="readonly",
            width=25,
        )
        self.res_subgroup_cb.pack(side="left", padx=(5, 15))
        self.res_subgroup_cb.bind(
            "<<ComboboxSelected>>", self.on_res_subgroup_selected_refresh_results
        )
        
        ttk.Label(row2_filters, text="Indicator:", background="#FFFFFF").pack(side="left")
        self.res_indicator_cb = ttk.Combobox(
            row2_filters,
            textvariable=self.res_indicator_var,
            state="readonly",
            width=30,
        )
        self.res_indicator_cb.pack(side="left", padx=(5, 15))
        self.res_indicator_cb.bind("<<ComboboxSelected>>", self.show_results_data)
        
        ttk.Button(
            row2_filters,
            text="Update View",
            command=self.show_results_data,
            style="Action.TButton",
        ).pack(side="left", padx=15)

        # --- PanedWindow for Table and Chart (Wrapped in Card style if possible, or just frames) ---
        # Note: PanedWindow background customization can be tricky. We'll use frames inside panes.
        self.results_paned_window = ttk.PanedWindow(
            results_main_container, orient=tk.VERTICAL
        )
        self.results_paned_window.pack(fill="both", expand=True)

        # --- Table Frame (Top Pane) ---
        table_card = ttk.Frame(self.results_paned_window, style="Card.TFrame", padding=0) # Padding inside card
        self.results_paned_window.add(table_card, weight=1)

        self.results_data_tree = ttk.Treeview(
            table_card, columns=("Period", "Target 1", "Target 2"), show="headings"
        )
        self.results_data_tree.heading("Period", text="Period")
        self.results_data_tree.heading("Target 1", text=self.target1_display_name)
        self.results_data_tree.heading("Target 2", text=self.target2_display_name)
        self.results_data_tree.column("Period", width=250, anchor="w", stretch=tk.YES)
        self.results_data_tree.column("Target 1", width=150, anchor="e", stretch=tk.YES)
        self.results_data_tree.column("Target 2", width=150, anchor="e", stretch=tk.YES)

        tree_scrollbar_y = ttk.Scrollbar(
            table_card, orient="vertical", command=self.results_data_tree.yview
        )
        self.results_data_tree.configure(yscrollcommand=tree_scrollbar_y.set)
        tree_scrollbar_y.pack(side="right", fill="y")
        self.results_data_tree.pack(side="left", fill="both", expand=True)

        # --- Chart Frame (Bottom Pane) ---
        chart_card = ttk.Frame(self.results_paned_window, style="Card.TFrame", padding=10)
        self.results_paned_window.add(chart_card, weight=2)

        self.fig_results = Figure(figsize=(8, 4), dpi=100)
        self.ax_results = self.fig_results.add_subplot(111)

        self.canvas_results_plot = FigureCanvasTkAgg(
            self.fig_results, master=chart_card
        )
        self.canvas_results_plot.get_tk_widget().pack(
            side=tk.TOP, fill=tk.BOTH, expand=True
        )

        toolbar_frame = ttk.Frame(chart_card, style="Card.TFrame")
        toolbar_frame.pack(side=tk.TOP, fill=tk.X)
        self.toolbar_results = NavigationToolbar2Tk(
            self.canvas_results_plot, toolbar_frame
        )
        self.toolbar_results.update()

        # --- Summary Label ---
        self.summary_label_var_vis = tk.StringVar()
        ttk.Label(
            results_main_container,
            textvariable=self.summary_label_var_vis,
            font=("Helvetica", 10, "italic"),
            background="#F5F5F5" # Match content bg
        ).pack(pady=5, anchor="e", padx=10)

    def on_res_group_selected_refresh_results(self, event=None):
        self.res_indicator_var.set("")
        self.res_indicator_cb["values"] = []
        self.res_indicators_list_filtered_details = []
        self._populate_res_subgroups()

    def on_res_subgroup_selected_refresh_results(self, event=None):
        self._populate_res_indicators()

    def populate_results_comboboxes(self):
        current_plant_name_res = self.res_plant_var_vis.get()
        plants_all = db_retriever.get_all_plants()
        self.res_plants_map_vis = {s["name"]: s["id"] for s in plants_all}
        self.res_plant_cb_vis["values"] = list(
            self.res_plants_map_vis.keys()
        )
        if (
            current_plant_name_res
            and current_plant_name_res in self.res_plants_map_vis
        ):
            self.res_plant_var_vis.set(current_plant_name_res)
        elif self.res_plants_map_vis:
            self.res_plant_var_vis.set(
                list(self.res_plants_map_vis.keys())[0]
            )
        else:
            self.res_plant_var_vis.set("")
            
        current_group_name_res = self.res_group_var.get()
        current_subgroup_display_name_res = self.res_subgroup_var.get()
        current_indicator_name_res = self.res_indicator_var.get()
        
        self.res_groups_list = db_retriever.get_kpi_groups()
        self.res_group_cb["values"] = [g["name"] for g in self.res_groups_list]
        
        if (
            current_group_name_res
            and current_group_name_res in self.res_group_cb["values"]
        ):
            self.res_group_var.set(current_group_name_res)
            current_subgroup_raw_name_res = (
                self.res_subgroup_display_to_raw_map.get(
                    current_subgroup_display_name_res
                )
                if hasattr(self, "res_subgroup_display_to_raw_map")
                and current_subgroup_display_name_res
                else None
            )
            self._populate_res_subgroups(
                pre_selected_subgroup_raw_name=current_subgroup_raw_name_res,
                pre_selected_indicator_name=current_indicator_name_res,
            )
        else:
            self.res_group_var.set("")
            self.res_subgroup_var.set("")
            self.res_indicator_var.set("")
            self.res_subgroup_cb["values"] = []
            self.res_indicator_cb["values"] = []
            self.current_kpi_id_for_results = None
            self.show_results_data()

    def _populate_res_subgroups(
        self,
        pre_selected_subgroup_raw_name=None,
        pre_selected_indicator_name=None,
    ):
        group_name = self.res_group_var.get()
        self.res_subgroup_cb["values"] = []
        if not pre_selected_subgroup_raw_name:
            self.res_subgroup_var.set("")
        if not pre_selected_indicator_name:
            self.res_indicator_var.set("")
        self.current_kpi_id_for_results = None
        
        selected_group_obj = next(
            (g for g in self.res_groups_list if g["name"] == group_name), None
        )
        
        if selected_group_obj:
            self.res_subgroups_list_details = (
                db_retriever.get_kpi_subgroups_by_group_revised(
                    selected_group_obj["id"]
                )
            )
            self.res_subgroup_display_to_raw_map = {}
            display_subgroup_names = []
            for sg_dict in self.res_subgroups_list_details:
                raw_name = sg_dict["name"]
                display_name = raw_name + (
                    f" (Tpl: {sg_dict['template_name']})"
                    if sg_dict.get("template_name")
                    else ""
                )
                display_subgroup_names.append(display_name)
                self.res_subgroup_display_to_raw_map[display_name] = raw_name
            
            self.res_subgroup_cb["values"] = display_subgroup_names
            
            target_display_subgroup_name = (
                next(
                    (
                        dn
                        for dn, rn in self.res_subgroup_display_to_raw_map.items()
                        if rn == pre_selected_subgroup_raw_name
                    ),
                    None,
                )
                if pre_selected_subgroup_raw_name
                else None
            )
            
            if target_display_subgroup_name:
                self.res_subgroup_var.set(target_display_subgroup_name)

        self._populate_res_indicators(pre_selected_indicator_name=pre_selected_indicator_name)

    def _populate_res_indicators(self, pre_selected_indicator_name=None):
        display_subgroup_name = self.res_subgroup_var.get()
        self.res_indicator_cb["values"] = []
        if not pre_selected_indicator_name:
            self.res_indicator_var.set("")
        self.current_kpi_id_for_results = None

        # Get plant_id right away to filter KPIs that have specs
        plant_name_res = self.res_plant_var_vis.get()
        plant_id_res = self.res_plants_map_vis.get(plant_name_res)

        raw_subgroup_name_lookup = (
            self.res_subgroup_display_to_raw_map.get(display_subgroup_name)
            if hasattr(self, "res_subgroup_display_to_raw_map")
            else None
        )
        
        selected_subgroup_obj_from_list = (
            next(
                (
                    s
                    for s in self.res_subgroups_list_details
                    if s["name"] == raw_subgroup_name_lookup
                ),
                None,
            )
            if raw_subgroup_name_lookup and hasattr(self, "res_subgroups_list_details")
            else None
        )
        
        if selected_subgroup_obj_from_list and plant_id_res is not None:
            group_name = self.res_group_var.get()
            selected_group_obj = next(
                (g for g in self.res_groups_list if g["name"] == group_name), None
            )
            group_id = selected_group_obj["id"] if selected_group_obj else None

            all_indicators_in_subgroup = db_retriever.get_kpi_indicators_by_subgroup(
                selected_subgroup_obj_from_list["id"]
            )
            # Fetch all specs for the selected plant to see which indicators are actually used
            all_kpi_specs_with_data = db_retriever.get_all_kpis_detailed(
                plant_id=plant_id_res,
                group_id=group_id,
                subgroup_id=selected_subgroup_obj_from_list["id"]
            )
            indicator_ids_with_spec = {
                k_spec["actual_indicator_id"] for k_spec in all_kpi_specs_with_data
            }
            self.res_indicators_list_filtered_details = [
                ind
                for ind in all_indicators_in_subgroup
                if ind["id"] in indicator_ids_with_spec
            ]
            self.res_indicator_cb["values"] = [
                ind["name"] for ind in self.res_indicators_list_filtered_details
            ]
            if (
                pre_selected_indicator_name
                and pre_selected_indicator_name in self.res_indicator_cb["values"]
            ):
                self.res_indicator_var.set(pre_selected_indicator_name)
        else:
            self.show_results_data()

    def show_results_data(self, event=None):
        for i in self.results_data_tree.get_children():
            self.results_data_tree.delete(i)

        if hasattr(self, "ax_results"):
            self.ax_results.clear()
        else:
            self.summary_label_var_vis.set("Error: Chart not initialized.")
            if hasattr(self, "canvas_results_plot"):
                self.canvas_results_plot.draw()
            return

        self.summary_label_var_vis.set("")
        plot_periods_for_xaxis = []

        try:
            year_val_res_str = self.res_year_var_vis.get()
            if not year_val_res_str:
                self.summary_label_var_vis.set("Select a year.")
                if hasattr(self, "canvas_results_plot"):
                    self.canvas_results_plot.draw()
                return
            year_val_res = int(year_val_res_str)

            plant_name_res = self.res_plant_var_vis.get()
            indicator_name_res = self.res_indicator_var.get()
            period_type_res = self.res_period_var_vis.get()

            if not all([plant_name_res, indicator_name_res, period_type_res]):
                self.summary_label_var_vis.set(
                    "Select Year, Plant, Indicator and Period."
                )
                if hasattr(self, "canvas_results_plot"):
                    self.canvas_results_plot.draw()
                return

            plant_id_res = self.res_plants_map_vis.get(
                plant_name_res
            )
            if plant_id_res is None:
                self.summary_label_var_vis.set("Selected plant not valid.")
                if hasattr(self, "canvas_results_plot"):
                    self.canvas_results_plot.draw()
                return

            selected_indicator_details_obj = None
            if (
                hasattr(self, "res_indicators_list_filtered_details")
                and self.res_indicators_list_filtered_details
            ):
                selected_indicator_details_obj = next(
                    (
                        ind
                        for ind in self.res_indicators_list_filtered_details
                        if ind["name"] == indicator_name_res
                    ),
                    None,
                )

            if not selected_indicator_details_obj:
                self.summary_label_var_vis.set(
                    f"Indicator '{indicator_name_res}' not found or without active KPI spec."
                )
                if hasattr(self, "canvas_results_plot"):
                    self.canvas_results_plot.draw()
                return

            indicator_actual_id = selected_indicator_details_obj["id"]
            kpi_spec_obj = next(
                (
                    spec
                    for spec in db_retriever.get_all_kpis_detailed(only_visible=False, plant_id=plant_id_res)
                    if spec["actual_indicator_id"] == indicator_actual_id
                ),
                None,
            )

            if not kpi_spec_obj:
                self.summary_label_var_vis.set(
                    f"KPI Specification not found for Indicator ID {indicator_actual_id}."
                )
                if hasattr(self, "canvas_results_plot"):
                    self.canvas_results_plot.draw()
                return

            kpi_spec_id_res = kpi_spec_obj["id"]
            calc_type_res = kpi_spec_obj["calculation_type"]
            kpi_unit_res = kpi_spec_obj['unit_of_measure'] if 'unit_of_measure' in kpi_spec_obj.keys() else ''
            kpi_display_name_res_str = get_kpi_display_name(kpi_spec_obj)

            target_ann_info_res = db_retriever.get_annual_target_entry(
                year_val_res, plant_id_res, kpi_spec_id_res
            )
            profile_disp_res = "N/A"
            if target_ann_info_res:
                profile_disp_res = target_ann_info_res['distribution_profile'] if 'distribution_profile' in target_ann_info_res.keys() and target_ann_info_res['distribution_profile'] else 'N/A'

            data_t1 = db_retriever.get_periodic_targets_for_kpi(
                year_val_res, plant_id_res, kpi_spec_id_res, period_type_res, 1
            )
            data_t2 = db_retriever.get_periodic_targets_for_kpi(
                year_val_res, plant_id_res, kpi_spec_id_res, period_type_res, 2
            )

            map_t1 = {row["Period"]: row["Target"] for row in data_t1} if data_t1 else {}
            map_t2 = {row["Period"]: row["Target"] for row in data_t2} if data_t2 else {}

            ordered_periods = (
                [row["Period"] for row in data_t1]
                if data_t1
                else ([row["Period"] for row in data_t2] if data_t2 else [])
            )
            ordered_periods = self._sort_periods(ordered_periods, period_type_res)
            plot_periods_for_xaxis = list(ordered_periods)

            if not ordered_periods:
                self.summary_label_var_vis.set(
                    f"No repartitioned data for {kpi_display_name_res_str} (Profile: {profile_disp_res})."
                )
                self.ax_results.set_title(f"No data for {kpi_display_name_res_str}")
                self.ax_results.set_xticks([])
                self.ax_results.set_xticklabels([])
                if hasattr(self, "canvas_results_plot"):
                    self.canvas_results_plot.draw()
                return

            # --- TABLE POPULATION ---
            total_sum_t1_table, count_t1_table = 0.0, 0
            total_sum_t2_table, count_t2_table = 0.0, 0
            for period_name in ordered_periods:
                val_t1_table = map_t1.get(period_name)
                val_t2_table = map_t2.get(period_name)
                t1_disp_table = f"{val_t1_table:.2f}" if isinstance(val_t1_table, (int, float)) else "N/A"
                t2_disp_table = f"{val_t2_table:.2f}" if isinstance(val_t2_table, (int, float)) else "N/A"
                self.results_data_tree.insert("", "end", values=(self._format_period(period_name, period_type_res), t1_disp_table, t2_disp_table))
                if isinstance(val_t1_table, (int, float)):
                    total_sum_t1_table += val_t1_table
                    count_t1_table += 1
                if isinstance(val_t2_table, (int, float)):
                    total_sum_t2_table += val_t2_table
                    count_t2_table += 1

            # --- Data Preparation for PLOTTING ---
            plot_target1_values = [map_t1.get(p) for p in ordered_periods]
            plot_target2_values = [map_t2.get(p) for p in ordered_periods]

            # --- Plotting ---
            self.ax_results.clear()
            x_indices = range(len(ordered_periods))

            color = self.get_plant_color(plant_name_res)

            self.ax_results.plot(x_indices, plot_target1_values, marker="o", linestyle="-", label="Target 1", color=color)
            self.ax_results.plot(x_indices, plot_target2_values, marker="x", linestyle="--", label="Target 2", color=color)

            self.ax_results.set_xlabel(f"Period ({period_type_res})")
            self.ax_results.set_ylabel(f"Target Value ({kpi_unit_res})")
            self.ax_results.set_title(f"Target Trend: {kpi_display_name_res_str}\n{year_val_res} - {plant_name_res}")

            if plot_periods_for_xaxis:
                self.ax_results.set_xticks(range(len(plot_periods_for_xaxis)))
                self.ax_results.set_xticklabels([self._format_period(p, period_type_res) for p in plot_periods_for_xaxis], rotation=45, ha="right")
                if len(plot_periods_for_xaxis) > 15:
                    self.ax_results.xaxis.set_major_locator(mticker.MaxNLocator(15))
            else:
                self.ax_results.set_xticks([])
                self.ax_results.set_xticklabels([])

            self.fig_results.tight_layout()
            self.ax_results.legend()
            self.ax_results.grid(True, linestyle="--", alpha=0.7)
            if hasattr(self, "canvas_results_plot"):
                self.canvas_results_plot.draw()

            # --- Summary Label Update ---
            summary_parts = [
                f"KPI: {kpi_display_name_res_str}",
                f"Annual Profile: {profile_disp_res}",
            ]
            if count_t1_table > 0:
                agg_t1 = (total_sum_t1_table if calc_type_res == 'Incremental' else (total_sum_t1_table / count_t1_table))
                summary_parts.append(f"{('Tot T1' if calc_type_res == 'Incremental' else 'Avg T1')} ({period_type_res}): {agg_t1:,.2f} {kpi_unit_res}")
            if count_t2_table > 0:
                agg_t2 = (total_sum_t2_table if calc_type_res == 'Incremental' else (total_sum_t2_table / count_t2_table))
                summary_parts.append(f"{('Tot T2' if calc_type_res == 'Incremental' else 'Avg T2')} ({period_type_res}): {agg_t2:,.2f} {kpi_unit_res}")
            self.summary_label_var_vis.set(" | ".join(summary_parts))

        except ValueError as ve:
            self.summary_label_var_vis.set(f"Input Error: {ve}")
            if hasattr(self, "ax_results"):
                self.ax_results.clear()
                self.ax_results.set_title("Error in input data")
            if hasattr(self, "canvas_results_plot"):
                self.canvas_results_plot.draw()
        except Exception as e:
            self.summary_label_var_vis.set(f"Display error: {e}")
            if hasattr(self, "ax_results"):
                self.ax_results.clear()
                self.ax_results.set_title("Error during display")
            if hasattr(self, "canvas_results_plot"):
                self.canvas_results_plot.draw()
            messagebox.showerror("Error", f"Unexpected error: {e}")

    # --- Global Dashboard (DashboardTab) ---
    def _format_period(self, period_str, period_type):
        if not period_str: return ""
        if period_type == 'Day':
            try:
                dt = datetime.datetime.strptime(period_str, '%Y-%m-%d')
                return dt.strftime('%d/%m/%y')
            except:
                return period_str
        return period_str

    def _on_canvas_configure(self, event):
        # Update width of scrollable frame to match canvas
        self.main_canvas.itemconfig(self.canvas_window, width=event.width)

    def create_global_dashboard_view(self):
        # Filter Card
        filter_card = ttk.Frame(self.content_frame, style="Card.TFrame", padding=15)
        filter_card.pack(fill="x", padx=0, pady=(0, 15))

        ttk.Label(filter_card, text="Year:", background="#FFFFFF").pack(side="left", padx=(0, 5))
        self.dashboard_year_var = tk.StringVar()
        self.dashboard_year_cb = ttk.Combobox(filter_card, textvariable=self.dashboard_year_var, state="readonly", width=10)
        self.dashboard_year_cb.pack(side="left", padx=5)
        self.dashboard_year_cb.bind("<<ComboboxSelected>>", self.load_dashboard_data)

        ttk.Label(filter_card, text="Detail Level:", background="#FFFFFF").pack(side="left", padx=(20, 5))
        self.dashboard_period_var = tk.StringVar()
        self.dashboard_period_cb = ttk.Combobox(filter_card, textvariable=self.dashboard_period_var, state="readonly", width=15)
        self.dashboard_period_cb["values"] = ["Year", "Quarter", "Month", "Week", "Day"]
        self.dashboard_period_cb.set("Month")
        self.dashboard_period_cb.pack(side="left", padx=5)
        self.dashboard_period_cb.bind("<<ComboboxSelected>>", self.load_dashboard_data)

        # Content Card for Charts
        content_card = ttk.Frame(self.content_frame, style="Card.TFrame")
        content_card.pack(fill="both", expand=True)

        self.main_canvas = tk.Canvas(content_card, background="#FFFFFF", highlightthickness=0)
        self.main_canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        self.scrollbar = ttk.Scrollbar(content_card, orient="vertical", command=self.main_canvas.yview)
        self.scrollbar.pack(side="right", fill="y")

        self.main_canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollable_frame = ttk.Frame(self.main_canvas, style="Card.TFrame") # Inner frame matches white canvas

        self.main_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.scrollable_frame.bind("<Configure>", lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all")))

        self.main_canvas.bind('<Enter>', self._bind_dashboard_mousewheel)
        self.main_canvas.bind('<Leave>', self._unbind_dashboard_mousewheel)