import tkinter as tk
from tkinter import ttk, simpledialog

from ...shared.helpers import get_kpi_display_name

class LinkSubKpiDialog(simpledialog.Dialog):
    def __init__(self, parent, title, available_kpis):
        self.available_kpis = available_kpis
        self.result_kpi = None
        super().__init__(parent, title)

    def body(self, master):
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.on_search)
        ttk.Label(master, text="Search:").pack()
        ttk.Entry(master, textvariable=self.search_var).pack(fill="x", expand=True)

        self.listbox = tk.Listbox(master, selectmode="single")
        self.listbox.pack(fill="both", expand=True)
        self.populate_listbox()

        return self.listbox

    def populate_listbox(self, filter_text=""):
        self.listbox.delete(0, tk.END)
        for kpi in self.available_kpis:
            display_name = get_kpi_display_name(kpi)
            if filter_text.lower() in display_name.lower():
                self.listbox.insert(tk.END, display_name)

    def on_search(self, *args):
        self.populate_listbox(self.search_var.get())

    def apply(self):
        selected_indices = self.listbox.curselection()
        if not selected_indices: return
        selected_name = self.listbox.get(selected_indices[0])
        self.result_kpi = next((kpi for kpi in self.available_kpis if get_kpi_display_name(kpi) == selected_name), None)
