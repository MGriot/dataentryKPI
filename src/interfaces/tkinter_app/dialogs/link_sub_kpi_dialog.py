import tkinter as tk
from tkinter import ttk, simpledialog

from src.interfaces.common_ui.helpers import get_kpi_display_name

class LinkSubKpiDialog(simpledialog.Dialog):
    def __init__(self, parent, title, master_kpi_id=None):
        self.master_kpi_id = master_kpi_id
        from src import data_retriever
        # Fetch available KPIs excluding the master itself
        all_kpis = data_retriever.get_all_kpis_detailed(only_visible=True)
        self.available_kpis = [dict(k) for k in all_kpis if k['id'] != self.master_kpi_id]
        self.result_data = None
        super().__init__(parent, title)

    def body(self, master):
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.on_search)
        ttk.Label(master, text="Search KPI to Link:").pack(anchor="w", padx=5, pady=5)
        ttk.Entry(master, textvariable=self.search_var).pack(fill="x", padx=5, pady=5)

        self.listbox = tk.Listbox(master, selectmode="single", font=("Helvetica", 10), height=15, width=50)
        self.listbox.pack(fill="both", expand=True, padx=5, pady=5)
        
        ttk.Label(master, text="Weight:").pack(anchor="w", padx=5, pady=(10, 0))
        self.weight_var = tk.DoubleVar(value=1.0)
        ttk.Entry(master, textvariable=self.weight_var).pack(fill="x", padx=5, pady=5)

        self.populate_listbox()
        return self.listbox

    def populate_listbox(self, filter_text=""):
        self.listbox.delete(0, tk.END)
        for kpi in self.available_kpis:
            display_name = f"{kpi.get('hierarchy_path', 'N/A')} > {kpi['indicator_name']}"
            if filter_text.lower() in display_name.lower():
                self.listbox.insert(tk.END, display_name)

    def on_search(self, *args):
        self.populate_listbox(self.search_var.get())

    def apply(self):
        sel = self.listbox.curselection()
        if not sel: return
        
        display_name = self.listbox.get(sel[0])
        # Find back the KPI by display name
        selected_kpi = None
        for kpi in self.available_kpis:
            d = f"{kpi.get('hierarchy_path', 'N/A')} > {kpi['indicator_name']}"
            if d == display_name:
                selected_kpi = kpi
                break
        
        if selected_kpi:
            self.result_data = {
                "sub_kpi_id": selected_kpi['id'], # This is kpis.id
                "weight": self.weight_var.get()
            }
