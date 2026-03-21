import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import calendar
from src import data_retriever as db_retriever
from src.interfaces.common_ui.helpers import get_kpi_display_name
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import pandas as pd

class DashboardTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.plant_colors = self.app.settings.get('plant_colors', {})
        self.color_list = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
        self.target1_display_name = self.app.settings.get('display_names', {}).get('target1', 'Target 1')
        self.target2_display_name = self.app.settings.get('display_names', {}).get('target2', 'Target 2')
        self.create_widgets()

    def on_tab_selected(self):
        self.populate_dashboard_comboboxes()

    def create_widgets(self):
        top_frame = ttk.Frame(self)
        top_frame.pack(fill="x", pady=10, padx=5)

        ttk.Label(top_frame, text="Year:").pack(side="left", padx=(0, 5))
        self.dashboard_year_var = tk.StringVar()
        self.dashboard_year_cb = ttk.Combobox(top_frame, textvariable=self.dashboard_year_var, state="readonly", width=10)
        self.dashboard_year_cb.pack(side="left", padx=5)
        self.dashboard_year_cb.bind("<<ComboboxSelected>>", self.load_dashboard_data)

        ttk.Label(top_frame, text="Detail Level:").pack(side="left", padx=(20, 5))
        self.dashboard_period_var = tk.StringVar()
        self.dashboard_period_cb = ttk.Combobox(top_frame, textvariable=self.dashboard_period_var, state="readonly", width=15)
        self.dashboard_period_cb["values"] = ["Year", "Quarter", "Month", "Week", "Day"]
        self.dashboard_period_cb.set("Month")
        self.dashboard_period_cb.pack(side="left", padx=5)
        self.dashboard_period_cb.bind("<<ComboboxSelected>>", self.load_dashboard_data)

        self.main_canvas = tk.Canvas(self)
        self.main_canvas.pack(side="left", fill="both", expand=True)

        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.main_canvas.yview)
        self.scrollbar.pack(side="right", fill="y")

        self.main_canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollable_frame = ttk.Frame(self.main_canvas)

        self.main_win = self.main_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.scrollable_frame.bind("<Configure>", lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all")))
        self.main_canvas.bind("<Configure>", lambda e: self.main_canvas.itemconfig(self.main_win, width=e.width))

    def populate_dashboard_comboboxes(self):
        years = [str(y["year"]) for y in db_retriever.get_distinct_years() if y["year"] is not None]
        self.dashboard_year_cb["values"] = ["All"] + years
        self.dashboard_year_var.set("All")
        self.load_dashboard_data()

    def get_plant_color(self, plant_name):
        if plant_name in self.app.settings.get('plant_colors', {}):
            return self.app.settings['plant_colors'][plant_name]
        else:
            if plant_name not in self.plant_colors:
                self.plant_colors[plant_name] = self.color_list[len(self.plant_colors) % len(self.color_list)]
            return self.plant_colors[plant_name]

    def _format_period(self, p, p_type):
        if p_type == "Month": return calendar.month_name[int(p)] if str(p).isdigit() else p
        if p_type == "Year": return "Annual"
        return str(p)

    def _sort_dashboard_df(self, df, p_type):
        if p_type == "Month":
            m_map = {m: i for i, m in enumerate(list(calendar.month_name)[1:], 1)}
            df['s'] = df['period'].apply(lambda x: m_map.get(x, 0) if not str(x).isdigit() else int(x))
            res = df.sort_values(['year', 's']).drop('s', axis=1)
            return res
        return df.sort_values(['year', 'period'])

    def load_dashboard_data(self, event=None):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        year_str = self.dashboard_year_var.get()
        year = int(year_str) if year_str != "All" else None
        period_type = self.dashboard_period_var.get()

        try:
            all_kpis = db_retriever.get_all_kpis_detailed(only_visible=True)
            if not all_kpis:
                ttk.Label(self.scrollable_frame, text="No visible KPIs defined.").pack(pady=20)
                return

            for kpi in all_kpis:
                kpi_id = kpi["id"]
                kpi_display_name = get_kpi_display_name(kpi)
                
                kpi_data = db_retriever.get_periodic_targets_for_kpi_all_plants(kpi_id, period_type, year)
                if not kpi_data:
                    continue

                df = pd.DataFrame([dict(row) for row in kpi_data])
                
                # Apply Year-Period formatting and sorting
                df['period_label'] = df.apply(lambda x: f"{x['year']}-{self._format_period(x['period'], period_type)}", axis=1)
                df = self._sort_dashboard_df(df, period_type)
                
                unique_labels = df['period_label'].unique()
                l_map = {l: i for i, l in enumerate(unique_labels)}

                chart_frame = ttk.LabelFrame(self.scrollable_frame, text=kpi_display_name, padding=10)
                chart_frame.pack(fill="x", expand=True, padx=10, pady=10)

                fig = Figure(figsize=(10, 4), dpi=100)
                ax = fig.add_subplot(111)

                for plant_name, plant_data in df.groupby('plant_name'):
                    color = self.get_plant_color(plant_name)
                    # We need to ensure chronological order for each plant's line
                    plant_data = plant_data.copy()
                    plant_data['x_idx'] = plant_data['period_label'].map(l_map)
                    plant_data = plant_data.sort_values('x_idx')

                    target1_data = plant_data[plant_data['target_number'] == 1]
                    target2_data = plant_data[plant_data['target_number'] == 2]

                    if not target1_data.empty:
                        ax.plot(target1_data['x_idx'], target1_data['target_value'], marker='o', linestyle='-', label=f'{plant_name} - {self.target1_display_name}', color=color)
                    if not target2_data.empty:
                        ax.plot(target2_data['x_idx'], target2_data['target_value'], marker='x', linestyle='--', label=f'{plant_name} - {self.target2_display_name}', color=color)

                ax.set_title(f"{period_type} Trend - {kpi_display_name}")
                ax.set_xticks(range(len(unique_labels)))
                if len(unique_labels) > 20:
                    step = max(1, len(unique_labels) // 10)
                    indices = range(0, len(unique_labels), step)
                    ax.set_xticks(indices)
                    ax.set_xticklabels([unique_labels[i] for i in indices], rotation=45, ha="right", fontsize=8)
                else:
                    ax.set_xticklabels(unique_labels, rotation=45, ha="right", fontsize=8)
                
                ax.set_ylabel("Value")
                ax.legend(fontsize=7, loc='upper left', bbox_to_anchor=(1, 1))
                ax.grid(True, alpha=0.3)
                fig.tight_layout()

                canvas = FigureCanvasTkAgg(fig, master=chart_frame)
                canvas.get_tk_widget().pack(fill="both", expand=True)
                canvas.draw()

        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Data Loading Error", f"Could not load dashboard data: {e}")