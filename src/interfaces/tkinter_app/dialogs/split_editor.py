import tkinter as tk
from tkinter import ttk, messagebox
import json
import calendar
import datetime
from src.interfaces.common_ui.constants import (
    REPARTITION_LOGIC_OPTIONS,
    DISTRIBUTION_PROFILE_OPTIONS,
    REPARTITION_LOGIC_YEAR,
    REPARTITION_LOGIC_MONTH,
    REPARTITION_LOGIC_QUARTER,
    REPARTITION_LOGIC_WEEK,
    PROFILE_EVEN,
    PROFILE_ANNUAL_PROGRESSIVE,
    PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS,
    PROFILE_TRUE_ANNUAL_SINUSOIDAL,
    PROFILE_MONTHLY_SINUSOIDAL,
    PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE,
    PROFILE_QUARTERLY_PROGRESSIVE,
    PROFILE_QUARTERLY_SINUSOIDAL
)

class SplitEditorDialog(tk.Toplevel):
    def __init__(self, parent, title="Standardized Split Editor", initial_data=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("600x700")
        self.result_data = None
        self.initial_data = initial_data or {}
        
        self._create_widgets()
        self._load_data()
        
        self.transient(parent)
        self.grab_set()
        self.wait_window()

    def _create_widgets(self):
        container = ttk.Frame(self, padding=20)
        container.pack(fill="both", expand=True)

        # Name
        ttk.Label(container, text="Template Name:").pack(anchor="w")
        self.name_var = tk.StringVar()
        ttk.Entry(container, textvariable=self.name_var, width=40).pack(fill="x", pady=(0, 10))

        # Year
        ttk.Label(container, text="Target Year:").pack(anchor="w")
        self.year_var = tk.IntVar(value=2024)
        self.year_spin = ttk.Spinbox(container, from_=2000, to_=2100, textvariable=self.year_var, command=lambda: self._on_preset_change(None))
        self.year_spin.pack(fill="x", pady=(0, 10))
        self.year_spin.bind("<FocusOut>", lambda e: self._on_preset_change(None))

        # Repartition Logic
        ttk.Label(container, text="Repartition Logic (Presets for period weights/percentages):").pack(anchor="w")
        self.logic_var = tk.StringVar(value=REPARTITION_LOGIC_YEAR)
        self.logic_cb = ttk.Combobox(container, textvariable=self.logic_var, values=REPARTITION_LOGIC_OPTIONS, state="readonly")
        self.logic_cb.pack(fill="x", pady=(0, 10))
        self.logic_cb.bind("<<ComboboxSelected>>", self._on_preset_change)

        # Distribution Profile
        ttk.Label(container, text="Intra-Period Distribution Profile (Presets for daily curves):").pack(anchor="w")
        self.profile_var = tk.StringVar(value=DISTRIBUTION_PROFILE_OPTIONS[0])
        self.profile_cb = ttk.Combobox(container, textvariable=self.profile_var, values=DISTRIBUTION_PROFILE_OPTIONS, state="readonly")
        self.profile_cb.pack(fill="x", pady=(0, 10))
        self.profile_cb.bind("<<ComboboxSelected>>", self._on_preset_change)

        # Repartition Values
        ttk.Label(container, text="Repartition Values (JSON):").pack(anchor="w")
        self.values_text = tk.Text(container, height=8, font=("Courier", 10))
        self.values_text.pack(fill="x", pady=(0, 10))
        self.values_text.insert("1.0", "{}")

        # Profile Params
        ttk.Label(container, text="Profile Parameters (JSON):").pack(anchor="w")
        self.params_text = tk.Text(container, height=8, font=("Courier", 10))
        self.params_text.pack(fill="x", pady=(0, 10))
        self.params_text.insert("1.0", "{}")

        # Buttons
        btn_f = ttk.Frame(container)
        btn_f.pack(fill="x", pady=10)
        ttk.Button(btn_f, text="Save", command=self._on_save, style="Action.TButton").pack(side="right", padx=5)
        ttk.Button(btn_f, text="Cancel", command=self.destroy).pack(side="right")

    def _load_data(self):
        if not self.initial_data: 
            self._on_preset_change(None) # Load defaults for new split
            return
            
        self.name_var.set(self.initial_data.get('name', ''))
        self.year_var.set(self.initial_data.get('year', 2024))
        self.logic_var.set(self.initial_data.get('repartition_logic', REPARTITION_LOGIC_YEAR))
        self.profile_var.set(self.initial_data.get('distribution_profile', DISTRIBUTION_PROFILE_OPTIONS[0]))
        
        vals = self.initial_data.get('repartition_values', {})
        self.values_text.delete("1.0", tk.END)
        self.values_text.insert("1.0", json.dumps(vals, indent=4))
        
        params = self.initial_data.get('profile_params', {})
        self.params_text.delete("1.0", tk.END)
        self.params_text.insert("1.0", json.dumps(params, indent=4))

    def _on_preset_change(self, event):
        logic = self.logic_var.get()
        profile = self.profile_var.get()
        
        # Default Repartition Values
        vals = {}
        if logic == REPARTITION_LOGIC_MONTH:
            vals = {m: 100.0 for m in calendar.month_name[1:]}
        elif logic == REPARTITION_LOGIC_QUARTER:
            vals = {f"Q{i+1}": 25.0 for i in range(4)}
        elif logic == REPARTITION_LOGIC_WEEK:
            try:
                year = self.year_var.get()
                # ISO weeks in year: check Dec 28th week number
                last_day = datetime.date(year, 12, 28)
                num_weeks = last_day.isocalendar()[1]
                vals = {f"Week {i+1}": 100.0 for i in range(num_weeks)}
            except:
                vals = {f"Week {i+1}": 100.0 for i in range(52)}
        
        # Default Profile Params
        params = {}
        if profile == PROFILE_ANNUAL_PROGRESSIVE:
            params = {"weight_initial": 1.6, "weight_final": 0.4}
        elif profile == PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS:
            params = {"weight_initial": 1.6, "weight_final": 0.4, "weekday_bias": 1.1}
        elif profile in (PROFILE_TRUE_ANNUAL_SINUSOIDAL, PROFILE_MONTHLY_SINUSOIDAL, PROFILE_QUARTERLY_SINUSOIDAL):
            params = {"amplitude": 0.3, "phase_offset": 0.0}
        elif profile == PROFILE_QUARTERLY_PROGRESSIVE:
            params = {"weight_initial": 1.5, "weight_final": 0.5}
        elif profile == "event_based_spikes_or_dips":
            params = {"events": [{"date": f"{self.year_var.get()}-01-01", "multiplier": 2.0}]}

        if event is not None or not self.initial_data:
            self.values_text.delete("1.0", tk.END)
            self.values_text.insert("1.0", json.dumps(vals, indent=4))
            
            self.params_text.delete("1.0", tk.END)
            self.params_text.insert("1.0", json.dumps(params, indent=4))

    def _on_save(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Error", "Name is required.")
            return
        
        try:
            values = json.loads(self.values_text.get("1.0", tk.END).strip() or "{}")
            params = json.loads(self.params_text.get("1.0", tk.END).strip() or "{}")
        except json.JSONDecodeError as e:
            messagebox.showerror("JSON Error", f"Invalid JSON format: {e}")
            return

        self.result_data = {
            "name": name,
            "year": self.year_var.get(),
            "repartition_logic": self.logic_var.get(),
            "repartition_values": values,
            "distribution_profile": self.profile_var.get(),
            "profile_params": params
        }
        self.destroy()

    def _on_save(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Error", "Name is required.")
            return
        
        try:
            values = json.loads(self.values_text.get("1.0", tk.END).strip() or "{}")
            params = json.loads(self.params_text.get("1.0", tk.END).strip() or "{}")
        except json.JSONDecodeError as e:
            messagebox.showerror("JSON Error", f"Invalid JSON format: {e}")
            return

        self.result_data = {
            "name": name,
            "year": self.year_var.get(),
            "repartition_logic": self.logic_var.get(),
            "repartition_values": values,
            "distribution_profile": self.profile_var.get(),
            "profile_params": params
        }
        self.destroy()
