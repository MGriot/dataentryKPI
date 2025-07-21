
import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import data_retriever as db_retriever
from ...shared.helpers import get_kpi_display_name
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates

class ResultsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.create_widgets()

    def on_tab_selected(self):
        self.populate_results_comboboxes()

    def create_widgets(self):
        top_frame = ttk.Frame(self)
        top_frame.pack(fill="x", pady=10, padx=5)

        ttk.Label(top_frame, text="Anno:").pack(side="left", padx=(0, 5))
        self.results_year_var = tk.StringVar()
        self.results_year_cb = ttk.Combobox(top_frame, textvariable=self.results_year_var, state="readonly", width=10)
        self.results_year_cb.pack(side="left", padx=5)
        self.results_year_cb.bind("<<ComboboxSelected>>", self.on_results_filter_change)

        ttk.Label(top_frame, text="Stabilimento:").pack(side="left", padx=(20, 5))
        self.results_stabilimento_var = tk.StringVar()
        self.results_stabilimento_cb = ttk.Combobox(top_frame, textvariable=self.results_stabilimento_var, state="readonly", width=30)
        self.results_stabilimento_cb.pack(side="left", padx=5)
        self.results_stabilimento_cb.bind("<<ComboboxSelected>>", self.on_results_filter_change)

        ttk.Label(top_frame, text="KPI:").pack(side="left", padx=(20, 5))
        self.results_kpi_var = tk.StringVar()
        self.results_kpi_cb = ttk.Combobox(top_frame, textvariable=self.results_kpi_var, state="readonly", width=50)
        self.results_kpi_cb.pack(side="left", padx=5, fill='x', expand=True)
        self.results_kpi_cb.bind("<<ComboboxSelected>>", self.on_results_filter_change)

        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, pady=5, padx=5)
        
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        self.results_tree = ttk.Treeview(tree_frame, columns=("Periodo", "Target", "Actual", "Delta"), show="headings")
        self.results_tree.heading("Periodo", text="Periodo")
        self.results_tree.heading("Target", text="Target")
        self.results_tree.heading("Actual", text="Actual")
        self.results_tree.heading("Delta", text="Delta")
        self.results_tree.pack(side="left", fill="both", expand=True)
        
        tree_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=tree_scrollbar.set)
        tree_scrollbar.pack(side="right", fill="y")

        plot_frame = ttk.Frame(main_frame)
        plot_frame.pack(side="left", fill="both", expand=True, padx=(5, 0))

        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

    def populate_results_comboboxes(self):
        current_year = datetime.datetime.now().year
        self.results_year_cb["values"] = [str(y) for y in range(current_year - 5, current_year + 5)]
        self.results_year_var.set(str(current_year))

        self.stabilimenti_for_results = {s["name"]: s["id"] for s in db_retriever.get_all_stabilimenti(visible_only=True)}
        self.results_stabilimento_cb["values"] = list(self.stabilimenti_for_results.keys())
        if self.stabilimenti_for_results:
            self.results_stabilimento_var.set(list(self.stabilimenti_for_results.keys())[0])

        self.kpis_for_results = {get_kpi_display_name(kpi): kpi["id"] for kpi in db_retriever.get_all_kpis_detailed(only_visible=True)}
        self.results_kpi_cb["values"] = list(self.kpis_for_results.keys())
        if self.kpis_for_results:
            self.results_kpi_var.set(list(self.kpis_for_results.keys())[0])
        
        self.on_results_filter_change()

    def on_results_filter_change(self, event=None):
        year_str = self.results_year_var.get()
        stabilimento_name = self.results_stabilimento_var.get()
        kpi_display_name = self.results_kpi_var.get()

        if not year_str or not stabilimento_name or not kpi_display_name:
            return

        year = int(year_str)
        stabilimento_id = self.stabilimenti_for_results.get(stabilimento_name)
        kpi_id = self.kpis_for_results.get(kpi_display_name)

        if not stabilimento_id or not kpi_id:
            return

        self.load_results_data(kpi_id, stabilimento_id, year, kpi_display_name)

    def load_results_data(self, kpi_id, stabilimento_id, year, kpi_display_name):
        # Clear previous data
        for i in self.results_tree.get_children():
            self.results_tree.delete(i)
        self.ax.clear()

        try:
            results = db_retriever.get_periodic_data_for_kpi(kpi_id, stabilimento_id, year)
            
            if not results:
                self.ax.set_title(f"Nessun dato per: {kpi_display_name}")
                self.canvas.draw()
                return

            periods = []
            targets = []
            actuals = []
            
            # Determine period type for date parsing
            period_type = 'monthly' # default
            if results:
                p = results[0]['periodo']
                if '-' in p and len(p.split('-')) == 2:
                    period_type = 'weekly'
                elif len(p) == 7 and '-' in p:
                    period_type = 'monthly'
                elif len(p) == 7 and 'Q' in p:
                    period_type = 'quarterly'


            for row in results:
                self.results_tree.insert("", "end", values=(
                    row["periodo"],
                    f"{row['target_value']:.2f}",
                    f"{row['actual_value']:.2f}",
                    f"{row['delta']:.2f}"
                ))
                
                # Date parsing logic from old file
                period_str = row['periodo']
                try:
                    if period_type == 'weekly':
                        date_obj = datetime.datetime.strptime(f"{year}-{period_str}", "%Y-%W-%w")
                    elif period_type == 'monthly':
                        date_obj = datetime.datetime.strptime(f"{period_str}-01", "%Y-%m-%d")
                    elif period_type == 'quarterly':
                        q_num = int(period_str.split('Q')[1])
                        date_obj = datetime.datetime(year, (q_num - 1) * 3 + 1, 1)
                    else:
                        date_obj = datetime.datetime.strptime(period_str, "%Y-%m-%d") # Fallback
                except (ValueError, TypeError):
                    date_obj = datetime.datetime.now() # Fallback

                periods.append(date_obj)
                targets.append(row["target_value"])
                actuals.append(row["actual_value"])
            
            self.ax.plot(periods, targets, marker='o', linestyle='--', label='Target')
            self.ax.plot(periods, actuals, marker='x', linestyle='-', label='Actual')
            
            self.ax.set_title(f"Andamento KPI: {kpi_display_name}")
            self.ax.set_xlabel("Periodo")
            self.ax.set_ylabel("Valore")
            self.ax.legend()
            self.ax.grid(True)
            
            # Formatting dates on x-axis
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            self.fig.autofmt_xdate()

            self.fig.tight_layout()
            self.canvas.draw()

        except Exception as e:
            messagebox.showerror("Errore Caricamento Dati", f"Impossibile caricare i dati dei risultati: {e}")
