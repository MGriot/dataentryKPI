import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json

class FormulaInputsDialog(simpledialog.Dialog):
    def __init__(self, parent, title, current_inputs_json_str, all_kpis_for_selection_map):
        self.current_inputs = []
        if current_inputs_json_str:
            try:
                self.current_inputs = json.loads(current_inputs_json_str)
                if not isinstance(self.current_inputs, list):
                    self.current_inputs = []
            except json.JSONDecodeError:
                messagebox.showwarning("JSON Errato", "Stringa JSON input formula non valida. Inizio con lista vuota.", parent=parent)
                self.current_inputs = []

        self.all_kpis_map = all_kpis_for_selection_map
        self.result_json_str = current_inputs_json_str
        super().__init__(parent, title)

    def body(self, master):
        # ... (widget creation logic from the guide) ...
        return self.kpi_input_cb

    def _add_input(self):
        # ... (logic from the guide) ...
        pass

    def _remove_selected_input(self):
        # ... (logic from the guide) ...
        pass

    def _refresh_inputs_listbox(self):
        # ... (logic from the guide) ...
        pass

    def apply(self):
        try:
            self.result_json_str = json.dumps(self.current_inputs)
        except Exception as e:
            messagebox.showerror("Errore JSON", f"Impossibile serializzare inputs: {e}", parent=self)
