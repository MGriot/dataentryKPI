import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import data_retriever as db_retriever
from ...shared.helpers import get_kpi_display_name
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class DashboardTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.create_widgets()

    def create_widgets(self):
        top_frame = ttk.Frame(self)
        top_frame.pack(fill="x", pady=10, padx=5)

        ttk.Label(top_frame, text="Anno:").pack(side="left", padx=(0, 5))
        self.dashboard_year_var = tk.StringVar()
        self.dashboard_year_cb = ttk.Combobox(top_frame, textvariable=self.dashboard_year_var, state="readonly", width=10)
        self.dashboard_year_cb.pack(side="left", padx=5)
        self.dashboard_year_cb.bind("<<ComboboxSelected>>", self.load_dashboard_data)

        ttk.Label(top_frame, text="Stabilimento:").pack(side="left", padx=(20, 5))
        self.dashboard_stabilimento_var = tk.StringVar()
        self.dashboard_stabilimento_cb = ttk.Combobox(top_frame, textvariable=self.dashboard_stabilimento_var, state="readonly", width=30)
        self.dashboard_stabilimento_cb.pack(side="left", padx=5)
        self.dashboard_stabilimento_cb.bind("<<ComboboxSelected>>", self.load_dashboard_data)

        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, pady=5, padx=5)

        self.dashboard_tree = ttk.Treeview(main_frame, columns=("KPI", "Target Annuo", "Actual Cumulato", "Performance"), show="headings")
        self.dashboard_tree.pack(side="left", fill="both", expand=True)

        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=main_frame)
        self.canvas.get_tk_widget().pack(side="left", fill="both", expand=True)

    def populate_dashboard_comboboxes(self):
        current_year = datetime.datetime.now().year
        self.dashboard_year_cb["values"] = [str(y) for y in range(current_year - 5, current_year + 5)]
        self.dashboard_year_var.set(str(current_year))

        self.stabilimenti_for_dashboard = {s["name"]: s["id"] for s in db_retriever.get_all_stabilimenti(visible_only=True)}
        self.dashboard_stabilimento_cb["values"] = list(self.stabilimenti_for_dashboard.keys())
        if self.stabilimenti_for_dashboard:
            self.dashboard_stabilimento_var.set(list(self.stabilimenti_for_dashboard.keys())[0])
        
        self.load_dashboard_data()

    def load_dashboard_data(self, event=None):
        year_str = self.dashboard_year_var.get()
        stabilimento_name = self.dashboard_stabilimento_var.get()

        if not year_str or not stabilimento_name:
            return

        year = int(year_str)
        stabilimento_id = self.stabilimenti_for_dashboard.get(stabilimento_name)

        if not stabilimento_id:
            return

        # Clear previous data
        for i in self.dashboard_tree.get_children():
            self.dashboard_tree.delete(i)
        self.ax.clear()

        try:
            dashboard_data = db_retriever.get_dashboard_data(stabilimento_id, year)
            
            kpi_names = []
            performances = []

            for row in dashboard_data:
                self.dashboard_tree.insert("", "end", values=(
                    get_kpi_display_name(row),
                    f"{row['annual_target']:.2f}",
                    f"{row['cumulative_actual']:.2f}",
                    f"{row['performance']:.2f}%"
                ))
                kpi_names.append(get_kpi_display_name(row))
                performances.append(row['performance'])
            
            self.ax.barh(kpi_names, performances)
            self.ax.set_title(f"Performance KPI per {stabilimento_name} - {year}")
            self.ax.set_xlabel("Performance (%)")
            self.ax.grid(True)
            self.fig.tight_layout()
            self.canvas.draw()

        except Exception as e:
            messagebox.showerror("Errore Caricamento Dati", f"Impossibile caricare i dati della dashboard: {e}")