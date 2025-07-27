import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import data_retriever as db_retriever
from ...shared.helpers import get_kpi_display_name
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.dates as mdates

class ResultsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.target1_display_name = self.app.settings.get('display_names', {}).get('target1', 'Target 1')
        self.target2_display_name = self.app.settings.get('display_names', {}).get('target2', 'Target 2')
        self.create_widgets()

    def on_tab_selected(self):
        """Called when the tab is selected."""
        self.populate_results_comboboxes()

    def create_widgets(self):
        # Main container for filters, table, and chart
        results_main_container = ttk.Frame(self)
        results_main_container.pack(fill="both", expand=True)

        # --- Filters Frame ---
        filter_frame_outer_res = ttk.Frame(results_main_container)
        filter_frame_outer_res.pack(fill="x", pady=5)
        filter_frame_res = ttk.Frame(filter_frame_outer_res)
        filter_frame_res.pack()  # Center the filter content

        row1_filters = ttk.Frame(filter_frame_res)
        row1_filters.pack(fill="x", pady=2)
        ttk.Label(row1_filters, text="Anno:").pack(side="left")
        self.res_year_var_vis = tk.StringVar(value=str(datetime.datetime.now().year))
        ttk.Spinbox(
            row1_filters,
            from_=2020,
            to=2050,
            textvariable=self.res_year_var_vis,
            width=6,
            command=self.show_results_data,
        ).pack(side="left", padx=(2, 10))
        ttk.Label(row1_filters, text="Stabilimento:").pack(side="left")
        self.res_stabilimento_var_vis = tk.StringVar()
        self.res_stabilimento_cb_vis = ttk.Combobox(
            row1_filters,
            textvariable=self.res_stabilimento_var_vis,
            state="readonly",
            width=20,
        )
        self.res_stabilimento_cb_vis.pack(side="left", padx=(2, 10))
        self.res_stabilimento_cb_vis.bind("<<ComboboxSelected>>", self.show_results_data)
        
        ttk.Label(row1_filters, text="Periodo:").pack(side="left")
        self.res_period_var_vis = tk.StringVar(value="Mese")
        self.res_period_cb_vis = ttk.Combobox(
            row1_filters,
            textvariable=self.res_period_var_vis,
            state="readonly",
            values=["Giorno", "Settimana", "Mese", "Trimestre"],
            width=10,
        )
        self.res_period_cb_vis.current(2)
        self.res_period_cb_vis.pack(side="left", padx=(2, 10))
        self.res_period_cb_vis.bind("<<ComboboxSelected>>", self.show_results_data)

        row2_filters = ttk.Frame(filter_frame_res)
        row2_filters.pack(fill="x", pady=2)
        ttk.Label(row2_filters, text="Gruppo:").pack(side="left")
        self.res_group_var = tk.StringVar()
        self.res_group_cb = ttk.Combobox(
            row2_filters, textvariable=self.res_group_var, state="readonly", width=20
        )
        self.res_group_cb.pack(side="left", padx=(2, 5))
        self.res_group_cb.bind(
            "<<ComboboxSelected>>", self.on_res_group_selected_refresh_results
        )
        ttk.Label(row2_filters, text="Sottogruppo:").pack(side="left")
        self.res_subgroup_var = tk.StringVar()
        self.res_subgroup_cb = ttk.Combobox(
            row2_filters,
            textvariable=self.res_subgroup_var,
            state="readonly",
            width=25,
        )
        self.res_subgroup_cb.pack(side="left", padx=(2, 5))
        self.res_subgroup_cb.bind(
            "<<ComboboxSelected>>", self.on_res_subgroup_selected_refresh_results
        )
        ttk.Label(row2_filters, text="Indicatore:").pack(side="left")
        self.res_indicator_var = tk.StringVar()
        self.res_indicator_cb = ttk.Combobox(
            row2_filters,
            textvariable=self.res_indicator_var,
            state="readonly",
            width=30,
        )
        self.res_indicator_cb.pack(side="left", padx=(2, 10))
        self.res_indicator_cb.bind("<<ComboboxSelected>>", self.show_results_data)
        ttk.Button(
            row2_filters,
            text="Aggiorna Vista",
            command=self.show_results_data,
            style="Accent.TButton",
        ).pack(side="left", padx=5)

        # --- PanedWindow for Table and Chart ---
        self.results_paned_window = ttk.PanedWindow(
            results_main_container, orient=tk.VERTICAL
        )
        self.results_paned_window.pack(fill="both", expand=True, pady=(10, 0))

        # --- Table Frame (Top Pane) ---
        table_frame = ttk.Frame(self.results_paned_window, height=200)
        self.results_paned_window.add(table_frame, weight=1)

        self.results_data_tree = ttk.Treeview(
            table_frame, columns=("Periodo", "Target 1", "Target 2"), show="headings"
        )
        self.results_data_tree.heading("Periodo", text="Periodo")
        self.results_data_tree.heading("Target 1", text=self.target1_display_name)
        self.results_data_tree.heading("Target 2", text=self.target2_display_name)
        self.results_data_tree.column("Periodo", width=250, anchor="w", stretch=tk.YES)
        self.results_data_tree.column("Target 1", width=150, anchor="e", stretch=tk.YES)
        self.results_data_tree.column("Target 2", width=150, anchor="e", stretch=tk.YES)

        tree_scrollbar_y = ttk.Scrollbar(
            table_frame, orient="vertical", command=self.results_data_tree.yview
        )
        self.results_data_tree.configure(yscrollcommand=tree_scrollbar_y.set)
        tree_scrollbar_y.pack(side="right", fill="y")
        self.results_data_tree.pack(side="left", fill="both", expand=True)

        # --- Chart Frame (Bottom Pane) ---
        chart_outer_frame = ttk.Frame(self.results_paned_window, height=300)
        self.results_paned_window.add(chart_outer_frame, weight=2)

        self.fig_results = Figure(figsize=(8, 4), dpi=100)
        self.ax_results = self.fig_results.add_subplot(111)

        self.canvas_results_plot = FigureCanvasTkAgg(
            self.fig_results, master=chart_outer_frame
        )
        self.canvas_results_plot.get_tk_widget().pack(
            side=tk.TOP, fill=tk.BOTH, expand=True
        )

        toolbar_frame = ttk.Frame(chart_outer_frame)
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
            font=("Calibri", 10, "italic"),
        ).pack(pady=5, anchor="e", padx=10)

    def on_res_group_selected_refresh_results(self, event=None):
        self._populate_res_subgroups()

    def on_res_subgroup_selected_refresh_results(self, event=None):
        self._populate_res_indicators()

    def populate_results_comboboxes(self):
        current_stab_name_res = self.res_stabilimento_var_vis.get()
        stabilimenti_all = db_retriever.get_all_stabilimenti()
        self.res_stabilimenti_map_vis = {s["name"]: s["id"] for s in stabilimenti_all}
        self.res_stabilimento_cb_vis["values"] = list(
            self.res_stabilimenti_map_vis.keys()
        )
        if (
            current_stab_name_res
            and current_stab_name_res in self.res_stabilimenti_map_vis
        ):
            self.res_stabilimento_var_vis.set(current_stab_name_res)
        elif self.res_stabilimenti_map_vis:
            self.res_stabilimento_var_vis.set(
                list(self.res_stabilimenti_map_vis.keys())[0]
            )
        else:
            self.res_stabilimento_var_vis.set("")
            
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
        self, pre_selected_subgroup_raw_name=None, pre_selected_indicator_name=None
    ):
        group_name = self.res_group_var.get()
        self.res_subgroup_cb["values"] = []
        self.res_indicator_cb["values"] = []
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
                self._populate_res_indicators(pre_selected_indicator_name)
            else:
                self._populate_res_indicators()
        else:
            self._populate_res_indicators()

    def _populate_res_indicators(self, pre_selected_indicator_name=None):
        display_subgroup_name = self.res_subgroup_var.get()
        self.res_indicator_cb["values"] = []
        if not pre_selected_indicator_name:
            self.res_indicator_var.set("")
        self.current_kpi_id_for_results = None
        
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
        
        if selected_subgroup_obj_from_list:
            all_indicators_in_subgroup = db_retriever.get_kpi_indicators_by_subgroup(
                selected_subgroup_obj_from_list["id"]
            )
            all_kpi_specs_with_data = db_retriever.get_all_kpis_detailed()
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
        
        self.show_results_data()

    def show_results_data(self, event=None):
        for i in self.results_data_tree.get_children():
            self.results_data_tree.delete(i)

        if hasattr(self, "ax_results"):
            self.ax_results.clear()
        else:
            self.summary_label_var_vis.set("Errore: Grafico non inizializzato.")
            if hasattr(self, "canvas_results_plot"):
                self.canvas_results_plot.draw()
            return

        self.summary_label_var_vis.set("")
        plot_periods_for_xaxis = []

        try:
            year_val_res_str = self.res_year_var_vis.get()
            if not year_val_res_str:
                self.summary_label_var_vis.set("Selezionare un anno.")
                if hasattr(self, "canvas_results_plot"):
                    self.canvas_results_plot.draw()
                return
            year_val_res = int(year_val_res_str)

            stabilimento_name_res = self.res_stabilimento_var_vis.get()
            indicator_name_res = self.res_indicator_var.get()
            period_type_res = self.res_period_var_vis.get()

            if not all([stabilimento_name_res, indicator_name_res, period_type_res]):
                self.summary_label_var_vis.set(
                    "Selezionare Anno, Stabilimento, Indicatore e Periodo."
                )
                if hasattr(self, "canvas_results_plot"):
                    self.canvas_results_plot.draw()
                return

            stabilimento_id_res = self.res_stabilimenti_map_vis.get(
                stabilimento_name_res
            )
            if stabilimento_id_res is None:
                self.summary_label_var_vis.set("Stabilimento selezionato non valido.")
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
                    f"Indicatore '{indicator_name_res}' non trovato o senza specifica KPI attiva."
                )
                if hasattr(self, "canvas_results_plot"):
                    self.canvas_results_plot.draw()
                return

            indicator_actual_id = selected_indicator_details_obj["id"]
            kpi_spec_obj = next(
                (
                    spec
                    for spec in db_retriever.get_all_kpis_detailed(only_visible=False, stabilimento_id=stabilimento_id_res)
                    if spec["actual_indicator_id"] == indicator_actual_id
                ),
                None,
            )

            if not kpi_spec_obj:
                self.summary_label_var_vis.set(
                    f"Specifica KPI non trovata per Indicatore ID {indicator_actual_id}."
                )
                if hasattr(self, "canvas_results_plot"):
                    self.canvas_results_plot.draw()
                return

            kpi_spec_id_res = kpi_spec_obj["id"]
            calc_type_res = kpi_spec_obj["calculation_type"]
            kpi_unit_res = kpi_spec_obj['unit_of_measure'] if 'unit_of_measure' in kpi_spec_obj.keys() else ''
            kpi_display_name_res_str = get_kpi_display_name(kpi_spec_obj)

            target_ann_info_res = db_retriever.get_annual_target_entry(
                year_val_res, stabilimento_id_res, kpi_spec_id_res
            )
            profile_disp_res = "N/D"
            if target_ann_info_res:
                profile_disp_res = target_ann_info_res['distribution_profile'] if 'distribution_profile' in target_ann_info_res.keys() and target_ann_info_res['distribution_profile'] else 'N/D'

            data_t1 = db_retriever.get_periodic_targets_for_kpi(
                year_val_res, stabilimento_id_res, kpi_spec_id_res, period_type_res, 1
            )
            data_t2 = db_retriever.get_periodic_targets_for_kpi(
                year_val_res, stabilimento_id_res, kpi_spec_id_res, period_type_res, 2
            )

            map_t1 = {row["Periodo"]: row["Target"] for row in data_t1} if data_t1 else {}
            map_t2 = {row["Periodo"]: row["Target"] for row in data_t2} if data_t2 else {}

            ordered_periods = (
                [row["Periodo"] for row in data_t1]
                if data_t1
                else ([row["Periodo"] for row in data_t2] if data_t2 else [])
            )
            plot_periods_for_xaxis = list(ordered_periods)

            if not ordered_periods:
                self.summary_label_var_vis.set(
                    f"Nessun dato ripartito per {kpi_display_name_res_str} (Profilo: {profile_disp_res})."
                )
                self.ax_results.set_title(f"Nessun dato per {kpi_display_name_res_str}")
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
                self.results_data_tree.insert("", "end", values=(period_name, t1_disp_table, t2_disp_table))
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

            self.ax_results.plot(x_indices, plot_target1_values, marker="o", linestyle="-", label="Target 1")
            self.ax_results.plot(x_indices, plot_target2_values, marker="x", linestyle="--", label="Target 2")

            self.ax_results.set_xlabel(f"Periodo ({period_type_res})")
            self.ax_results.set_ylabel(f"Valore Target ({kpi_unit_res})")
            self.ax_results.set_title(f"Andamento Target: {kpi_display_name_res_str}\n{year_val_res} - {stabilimento_name_res}")

            if plot_periods_for_xaxis:
                self.ax_results.set_xticks(range(len(plot_periods_for_xaxis)))
                self.ax_results.set_xticklabels(plot_periods_for_xaxis, rotation=45, ha="right")
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
                f"Profilo Annuale: {profile_disp_res}",
            ]
            if count_t1_table > 0:
                agg_t1 = (total_sum_t1_table if calc_type_res == 'Incrementale' else (total_sum_t1_table / count_t1_table))
                summary_parts.append(f"{'Tot T1' if calc_type_res == 'Incrementale' else 'Media T1'} ({period_type_res}): {agg_t1:,.2f} {kpi_unit_res}")
            if count_t2_table > 0:
                agg_t2 = (total_sum_t2_table if calc_type_res == 'Incrementale' else (total_sum_t2_table / count_t2_table))
                summary_parts.append(f"{'Tot T2' if calc_type_res == 'Incrementale' else 'Media T2'} ({period_type_res}): {agg_t2:,.2f} {kpi_unit_res}")
            self.summary_label_var_vis.set(" | ".join(summary_parts))

        except ValueError as ve:
            self.summary_label_var_vis.set(f"Errore Input: {ve}")
            if hasattr(self, "ax_results"):
                self.ax_results.clear()
                self.ax_results.set_title("Errore nei dati di input")
            if hasattr(self, "canvas_results_plot"):
                self.canvas_results_plot.draw()
        except Exception as e:
            self.summary_label_var_vis.set(f"Errore visualizzazione: {e}")
            if hasattr(self, "ax_results"):
                self.ax_results.clear()
                self.ax_results.set_title("Errore durante la visualizzazione")
            if hasattr(self, "canvas_results_plot"):
                self.canvas_results_plot.draw()
            messagebox.showerror("Errore", f"Errore imprevisto: {e}")