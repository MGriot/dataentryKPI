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
    PROFILE_ANNUAL_PROGRESSIVE,
    PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS,
    PROFILE_TRUE_ANNUAL_SINUSOIDAL,
    PROFILE_MONTHLY_SINUSOIDAL,
    PROFILE_QUARTERLY_SINUSOIDAL,
    PROFILE_QUARTERLY_PROGRESSIVE
)
from src.interfaces.tkinter_app.dialogs.advanced_split_dialog import AdvancedSplitDialog
from src import data_retriever
from src.kpi_management import splits as kpi_splits_manager

class SplitEditorDialog(tk.Toplevel):
    def __init__(self, parent, title="Standardized Split Editor", initial_data=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("800x850")
        self.result_data = None
        self.initial_data = initial_data or {}
        self.afflicted_indicators = [] # list of {'indicator_id': int, 'indicator_name': str, 'override': str|None}
        
        self._create_widgets()
        self._load_data()
        
        self.transient(parent)
        self.grab_set()
        self.wait_window()

    def _create_widgets(self):
        container = ttk.Frame(self, padding=20)
        container.pack(fill="both", expand=True)

        # Left Column: Config
        left = ttk.Frame(container)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        ttk.Label(left, text="Template Name:").pack(anchor="w")
        self.name_var = tk.StringVar()
        ttk.Entry(left, textvariable=self.name_var, width=40).pack(fill="x", pady=(0, 10))

        ttk.Label(left, text="Target Year:").pack(anchor="w")
        self.year_var = tk.IntVar(value=datetime.datetime.now().year)
        self.year_spin = ttk.Spinbox(left, from_=2000, to_=2100, textvariable=self.year_var, command=lambda: self._on_preset_change(None))
        self.year_spin.pack(fill="x", pady=(0, 10))

        ttk.Label(left, text="Repartition Logic:").pack(anchor="w")
        self.logic_var = tk.StringVar(value=REPARTITION_LOGIC_YEAR)
        self.logic_cb = ttk.Combobox(left, textvariable=self.logic_var, values=REPARTITION_LOGIC_OPTIONS, state="readonly")
        self.logic_cb.pack(fill="x", pady=(0, 10))
        self.logic_cb.bind("<<ComboboxSelected>>", self._on_preset_change)

        ttk.Label(left, text="Default Distribution Profile:").pack(anchor="w")
        self.profile_var = tk.StringVar(value=DISTRIBUTION_PROFILE_OPTIONS[0])
        self.profile_cb = ttk.Combobox(left, textvariable=self.profile_var, values=DISTRIBUTION_PROFILE_OPTIONS, state="readonly")
        self.profile_cb.pack(fill="x", pady=(0, 10))
        self.profile_cb.bind("<<ComboboxSelected>>", self._on_preset_change)

        # Advanced Analysis Button
        ttk.Button(left, text="📊 Run Advanced Seasonality Analysis...", command=self._open_advanced_analysis).pack(fill="x", pady=10)

        ttk.Label(left, text="Repartition Values (JSON):").pack(anchor="w")
        self.values_text = tk.Text(left, height=10, font=("Courier", 10))
        self.values_text.pack(fill="both", expand=True, pady=(0, 10))

        # Right Column: Afflicted Indicators
        right = ttk.LabelFrame(container, text="Indicators Afflicted (Req 9)", padding=10)
        right.pack(side="right", fill="both", expand=True)

        self.ind_tree = ttk.Treeview(right, columns=("ID", "Name", "Override"), show="headings", height=15)
        self.ind_tree.heading("ID", text="ID"); self.ind_tree.column("ID", width=40)
        self.ind_tree.heading("Name", text="Indicator Name"); self.ind_tree.column("Name", width=150)
        self.ind_tree.heading("Override", text="Profile Override"); self.ind_tree.column("Override", width=120)
        self.ind_tree.pack(fill="both", expand=True)

        ind_btns = ttk.Frame(right)
        ind_btns.pack(fill="x", pady=5)
        ttk.Button(ind_btns, text="+ Add Indicators", command=self._add_indicators).pack(side="left", padx=2)
        ttk.Button(ind_btns, text="- Remove", command=self._remove_indicator).pack(side="left", padx=2)
        ttk.Button(ind_btns, text="Set Override", command=self._set_override).pack(side="left", padx=2)

        # Footer
        footer = ttk.Frame(self, padding=10)
        footer.pack(side="bottom", fill="x")
        ttk.Button(footer, text="Save Global Split", command=self._on_save, style="Action.TButton").pack(side="right", padx=5)
        ttk.Button(footer, text="Cancel", command=self.destroy).pack(side="right")

    def _load_data(self):
        if not self.initial_data: 
            self._on_preset_change(None)
            return
            
        self.name_var.set(self.initial_data.get('name', ''))
        self.year_var.set(self.initial_data.get('year', datetime.datetime.now().year))
        self.logic_var.set(self.initial_data.get('repartition_logic', REPARTITION_LOGIC_YEAR))
        self.profile_var.set(self.initial_data.get('distribution_profile', DISTRIBUTION_PROFILE_OPTIONS[0]))
        
        vals = self.initial_data.get('repartition_values', {})
        self.values_text.delete("1.0", tk.END)
        self.values_text.insert("1.0", json.dumps(vals, indent=4))
        
        # Load indicators
        if 'id' in self.initial_data:
            inds = kpi_splits_manager.get_indicators_for_global_split(self.initial_data['id'])
            # We need to resolve names
            all_inds = {i['id']: i['name'] for i in data_retriever.get_all_kpi_indicators()}
            for i in inds:
                self.afflicted_indicators.append({
                    'indicator_id': i['indicator_id'],
                    'indicator_name': all_inds.get(i['indicator_id'], 'Unknown'),
                    'override': i['override_distribution_profile']
                })
            self._refresh_ind_tree()

    def _refresh_ind_tree(self):
        for i in self.ind_tree.get_children(): self.ind_tree.delete(i)
        for i in self.afflicted_indicators:
            self.ind_tree.insert("", "end", iid=str(i['indicator_id']), values=(i['indicator_id'], i['indicator_name'], i['override'] or "Default"))

    def _on_preset_change(self, event):
        logic = self.logic_var.get()
        profile = self.profile_var.get()
        vals = {}
        if logic == REPARTITION_LOGIC_MONTH:
            vals = {m: 100.0/12 for m in calendar.month_name[1:]}
        elif logic == REPARTITION_LOGIC_QUARTER:
            vals = {f"Q{i+1}": 25.0 for i in range(4)}
        
        if event is not None or not self.initial_data:
            self.values_text.delete("1.0", tk.END)
            self.values_text.insert("1.0", json.dumps(vals, indent=4))

    def _open_advanced_analysis(self):
        dialog = AdvancedSplitDialog(self)
        self.wait_window(dialog)
        res = dialog.get_result()
        if res:
            self.values_text.delete("1.0", tk.END)
            self.values_text.insert("1.0", json.dumps(res, indent=4))
            messagebox.showinfo("Analysis", "Suggested weights applied to repartition values.")

    def _add_indicators(self):
        # Multi-select window
        win = tk.Toplevel(self)
        win.title("Select Indicators")
        win.geometry("400x500")
        
        lb = tk.Listbox(win, selectmode="multiple")
        lb.pack(fill="both", expand=True, padx=10, pady=10)
        
        all_inds = sorted([dict(r) for r in data_retriever.get_all_kpi_indicators()], key=lambda x: x['name'])
        existing_ids = [i['indicator_id'] for i in self.afflicted_indicators]
        
        for i in all_inds:
            if i['id'] not in existing_ids:
                lb.insert(tk.END, f"{i['name']} [ID:{i['id']}]")
        
        def add():
            for idx in lb.curselection():
                text = lb.get(idx)
                # Parse ID from text "Name [ID:123]"
                iid = int(text.split("[ID:")[1].replace("]", ""))
                name = text.split(" [ID:")[0]
                self.afflicted_indicators.append({'indicator_id': iid, 'indicator_name': name, 'override': None})
            self._refresh_ind_tree()
            win.destroy()
            
        ttk.Button(win, text="Add Selected", command=add).pack(pady=10)

    def _remove_indicator(self):
        sel = self.ind_tree.selection()
        if not sel: return
        iid = int(sel[0])
        self.afflicted_indicators = [i for i in self.afflicted_indicators if i['indicator_id'] != iid]
        self._refresh_ind_tree()

    def _set_override(self):
        sel = self.ind_tree.selection()
        if not sel: return
        iid = int(sel[0])
        
        # Simple option picker
        ov_win = tk.Toplevel(self)
        ov_win.title("Set Profile Override")
        var = tk.StringVar(value="None")
        ttk.Radiobutton(ov_win, text="Use Global Default", variable=var, value="None").pack(anchor="w", padx=20, pady=5)
        for opt in DISTRIBUTION_PROFILE_OPTIONS:
            ttk.Radiobutton(ov_win, text=opt, variable=var, value=opt).pack(anchor="w", padx=20, pady=2)
            
        def apply():
            val = None if var.get() == "None" else var.get()
            for i in self.afflicted_indicators:
                if i['indicator_id'] == iid: i['override'] = val
            self._refresh_ind_tree()
            ov_win.destroy()
            
        ttk.Button(ov_win, text="Apply", command=apply).pack(pady=10)

    def _on_save(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Error", "Name is required.")
            return
        
        try:
            values = json.loads(self.values_text.get("1.0", tk.END).strip() or "{}")
        except json.JSONDecodeError as e:
            messagebox.showerror("JSON Error", f"Invalid JSON format: {e}")
            return

        self.result_data = {
            "name": name,
            "year": self.year_var.get(),
            "repartition_logic": self.logic_var.get(),
            "repartition_values": values,
            "distribution_profile": self.profile_var.get(),
            "profile_params": {}, # Default empty for now
            "afflicted_indicators": self.afflicted_indicators
        }
        self.destroy()

    def get_result(self):
        return self.result_data
