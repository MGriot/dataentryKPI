import tkinter as tk
from tkinter import ttk, simpledialog, messagebox

import data_retriever as db_retriever

class SubgroupEditorDialog(simpledialog.Dialog):
    def __init__(self, parent, title=None, group_id_context=None, initial_name="", initial_template_id=None):
        self.group_id = group_id_context
        self.initial_name = initial_name
        self.initial_template_id = initial_template_id
        self.result_name = None
        self.result_template_id = None
        self.templates_map = {"(Nessun Template)": None}
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text="Nome Sottogruppo:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.name_var = tk.StringVar(value=self.initial_name)
        self.name_entry = ttk.Entry(master, textvariable=self.name_var, width=35)
        self.name_entry.grid(row=0, column=1, padx=5, pady=5)
        self.name_entry.focus_set()

        ttk.Label(master, text="Template Indicatori:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.template_var = tk.StringVar()
        self.template_cb = ttk.Combobox(master, textvariable=self.template_var, state="readonly", width=33)
        available_templates = db_retriever.get_kpi_indicator_templates()
        for tpl in available_templates:
            self.templates_map[tpl["name"]] = tpl["id"]
        self.template_cb["values"] = list(self.templates_map.keys())
        selected_template_name = next((
            name for name, id_val in self.templates_map.items() if id_val == self.initial_template_id
        ), "(Nessun Template)")
        self.template_var.set(selected_template_name)
        self.template_cb.grid(row=1, column=1, padx=5, pady=5)
        return self.name_entry

    def apply(self):
        self.result_name = self.name_var.get().strip()
        if not self.result_name:
            messagebox.showwarning("Input Mancante", "Il nome del sottogruppo è obbligatorio.", parent=self)
            self.result_name = None
            return
        self.result_template_id = self.templates_map.get(self.template_var.get())

