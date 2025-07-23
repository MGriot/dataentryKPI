import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import data_retriever as db_retriever
from ...shared.helpers import get_kpi_display_name
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import pandas as pd

class DashboardTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.stabilimento_colors = {}
        self.color_list = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
        self.create_widgets()

    def on_tab_selected(self):
        self.populate_dashboard_comboboxes()

    def create_widgets(self):
        top_frame = ttk.Frame(self)
        top_frame.pack(fill="x", pady=10, padx=5)

        ttk.Label(top_frame, text="Anno:").pack(side="left", padx=(0, 5))
        self.dashboard_year_var = tk.StringVar()
        self.dashboard_year_cb = ttk.Combobox(top_frame, textvariable=self.dashboard_year_var, state="readonly", width=10)
        self.dashboard_year_cb.pack(side="left", padx=5)
        self.dashboard_year_cb.bind("<<ComboboxSelected>>", self.load_dashboard_data)

        ttk.Label(top_frame, text="Livello Dettaglio:").pack(side="left", padx=(20, 5))
        self.dashboard_period_var = tk.StringVar()
        self.dashboard_period_cb = ttk.Combobox(top_frame, textvariable=self.dashboard_period_var, state="readonly", width=15)
        self.dashboard_period_cb["values"] = ["Anno", "Trimestre", "Mese", "Settimana", "Giorno"]
        self.dashboard_period_cb.set("Mese")
        self.dashboard_period_cb.pack(side="left", padx=5)
        self.dashboard_period_cb.bind("<<ComboboxSelected>>", self.load_dashboard_data)

        self.main_canvas = tk.Canvas(self)
        self.main_canvas.pack(side="left", fill="both", expand=True)

        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.main_canvas.yview)
        self.scrollbar.pack(side="right", fill="y")

        self.main_canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollable_frame = ttk.Frame(self.main_canvas)

        self.main_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.scrollable_frame.bind("<Configure>", lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all")))

    def populate_dashboard_comboboxes(self):
        years = [str(y["year"]) for y in db_retriever.get_distinct_years()]
        self.dashboard_year_cb["values"] = ["All"] + years
        self.dashboard_year_var.set("All")
        self.load_dashboard_data()

    def get_stabilimento_color(self, stabilimento_name):
        if stabilimento_name not in self.stabilimento_colors:
            self.stabilimento_colors[stabilimento_name] = self.color_list[len(self.stabilimento_colors) % len(self.color_list)]
        return self.stabilimento_colors[stabilimento_name]

    def load_dashboard_data(self, event=None):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        year_str = self.dashboard_year_var.get()
        year = int(year_str) if year_str != "All" else None
        period_type = self.dashboard_period_var.get()

        try:
            all_kpis = db_retriever.get_all_kpis_detailed(only_visible=True)
            if not all_kpis:
                ttk.Label(self.scrollable_frame, text="Nessun KPI visibile definito.").pack(pady=20)
                return

            for kpi in all_kpis:
                kpi_id = kpi["id"]
                kpi_display_name = get_kpi_display_name(kpi)
                
                kpi_data = db_retriever.get_periodic_targets_for_kpi_all_stabilimenti(kpi_id, period_type, year)
                if not kpi_data:
                    continue

                # Convert list of sqlite3.Row objects to a list of dictionaries, then to DataFrame
                df = pd.DataFrame([dict(row) for row in kpi_data])

                chart_frame = ttk.LabelFrame(self.scrollable_frame, text=kpi_display_name, padding=10)
                chart_frame.pack(fill="x", expand=True, padx=10, pady=10)

                fig = Figure(figsize=(12, 6), dpi=100)
                ax = fig.add_subplot(111)

                for stabilimento_name, stabilimento_data in df.groupby('stabilimento_name'):
                    color = self.get_stabilimento_color(stabilimento_name)
                    target1_data = stabilimento_data[stabilimento_data['target_number'] == 1]
                    target2_data = stabilimento_data[stabilimento_data['target_number'] == 2]

                    if not target1_data.empty:
                        ax.plot(target1_data['period'], target1_data['target_value'], marker='o', linestyle='-', label=f'{stabilimento_name} - Target 1', color=color)
                    if not target2_data.empty:
                        ax.plot(target2_data['period'], target2_data['target_value'], marker='x', linestyle='--', label=f'{stabilimento_name} - Target 2', color=color)

                ax.set_title(f"Andamento {period_type} - {kpi_display_name}")
                ax.set_xlabel(period_type)
                ax.set_ylabel("Valore")
                ax.legend()
                ax.grid(True)
                fig.tight_layout()

                canvas = FigureCanvasTkAgg(fig, master=chart_frame)
                canvas.get_tk_widget().pack(fill="both", expand=True)
                canvas.draw()

        except Exception as e:
            messagebox.showerror("Errore Caricamento Dati", f"Impossibile caricare i dati della dashboard: {e}")

