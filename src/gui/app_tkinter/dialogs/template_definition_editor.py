import tkinter as tk
from tkinter import ttk, simpledialog, messagebox

from app_config import CALC_TYPE_INCREMENTALE, CALC_TYPE_MEDIA

class TemplateDefinitionEditorDialog(simpledialog.Dialog):
    def __init__(self, parent, title=None, template_id_context=None, initial_data=None):
        self.initial_data = dict(initial_data) if initial_data else {}
        self.result_data = None
        self.kpi_calc_type_options = [CALC_TYPE_INCREMENTALE, CALC_TYPE_MEDIA]
        super().__init__(parent, title)

    def body(self, master):
        self.name_var = tk.StringVar(value=self.initial_data.get("indicator_name_in_template", ""))
        self.desc_var = tk.StringVar(value=self.initial_data.get("default_description", ""))
        self.type_var = tk.StringVar(value=self.initial_data.get("default_calculation_type", self.kpi_calc_type_options[0]))
        self.unit_var = tk.StringVar(value=self.initial_data.get("default_unit_of_measure", ""))
        self.visible_var = tk.BooleanVar(value=bool(self.initial_data.get("default_visible", True)))

        ttk.Label(master, text="Nome Indicatore Template:").grid(row=0, column=0, sticky="w", padx=5, pady=3)
        self.name_entry = ttk.Entry(master, textvariable=self.name_var, width=35)
        self.name_entry.grid(row=0, column=1, padx=5, pady=3)
        self.name_entry.focus_set()

        ttk.Label(master, text="Descrizione Default:").grid(row=1, column=0, sticky="w", padx=5, pady=3)
        self.desc_entry = ttk.Entry(master, textvariable=self.desc_var, width=35)
        self.desc_entry.grid(row=1, column=1, padx=5, pady=3)

        ttk.Label(master, text="Tipo Calcolo:").grid(row=2, column=0, sticky="w", padx=5, pady=3)
        self.type_cb = ttk.Combobox(master, textvariable=self.type_var, values=self.kpi_calc_type_options, state="readonly", width=33)
        self.type_cb.grid(row=2, column=1, padx=5, pady=3)

        ttk.Label(master, text="Unità di Misura:").grid(row=3, column=0, sticky="w", padx=5, pady=3)
        self.unit_entry = ttk.Entry(master, textvariable=self.unit_var, width=35)
        self.unit_entry.grid(row=3, column=1, padx=5, pady=3)

        ttk.Label(master, text="Visibile di Default:").grid(row=4, column=0, sticky="w", padx=5, pady=3)
        self.visible_cb = ttk.Checkbutton(master, variable=self.visible_var)
        self.visible_cb.grid(row=4, column=1, sticky="w", padx=5, pady=3)
        return self.name_entry

    def apply(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Input Mancante", "Il nome dell'indicatore nel template è obbligatorio.", parent=self)
            self.result_data = None
            return

        self.result_data = {
            "indicator_name_in_template": name,
            "default_description": self.desc_var.get().strip(),
            "default_calculation_type": self.type_var.get(),
            "default_unit_of_measure": self.unit_var.get().strip(),
            "default_visible": self.visible_var.get(),
        }

