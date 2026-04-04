import tkinter as tk
from tkinter import ttk, messagebox
import json
import calendar
import datetime
import math
from src.interfaces.common_ui.constants import (
    DISTRIBUTION_PROFILE_OPTIONS,
    REPARTITION_LOGIC_MONTH,
    REPARTITION_LOGIC_QUARTER,
    PROFILE_EVEN,
    PROFILE_ANNUAL_PROGRESSIVE,
    PROFILE_TRUE_ANNUAL_SINUSOIDAL
)
from src.interfaces.tkinter_app.dialogs.advanced_split_dialog import AdvancedSplitDialog
from src import data_retriever
from src.kpi_management import splits as kpi_splits_manager

class SplitEditorDialog(tk.Toplevel):
    def __init__(self, parent, title="Standardized Split Editor", initial_data=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("850x900")
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

        ttk.Label(left, text="Template Name:", font=("Helvetica", 10, "bold")).pack(anchor="w")
        self.name_var = tk.StringVar()
        ttk.Entry(left, textvariable=self.name_var, width=40).pack(fill="x", pady=(0, 10))

        ttk.Label(left, text="Target Year(s):", font=("Helvetica", 10, "bold")).pack(anchor="w")
        year_frame = ttk.Frame(left)
        year_frame.pack(fill="x", pady=(0, 10))
        
        self.year_listbox = tk.Listbox(year_frame, selectmode="multiple", height=5, exportselection=False)
        self.year_listbox.pack(side="left", fill="x", expand=True)
        
        ysb = ttk.Scrollbar(year_frame, orient="vertical", command=self.year_listbox.yview)
        ysb.pack(side="right", fill="y")
        self.year_listbox.config(yscrollcommand=ysb.set)
        
        current_year = datetime.datetime.now().year
        for y in range(current_year - 2, current_year + 6):
            self.year_listbox.insert(tk.END, str(y))

        ttk.Label(left, text="Universal Distribution Profile:", font=("Helvetica", 10, "bold")).pack(anchor="w")
        self.profile_var = tk.StringVar(value=PROFILE_EVEN)
        self.profile_cb = ttk.Combobox(left, textvariable=self.profile_var, values=DISTRIBUTION_PROFILE_OPTIONS, state="readonly")
        self.profile_cb.pack(fill="x", pady=(0, 10))
        self.profile_cb.bind("<<ComboboxSelected>>", self._on_profile_change)

        # Advanced Analysis Button
        ttk.Button(left, text="📊 Run Advanced Seasonality Analysis...", command=self._open_advanced_analysis).pack(fill="x", pady=10)

        ttk.Label(left, text="Repartition Weights (%):", font=("Helvetica", 10, "bold")).pack(anchor="w")
        self.values_text = tk.Text(left, height=15, font=("Courier", 10))
        self.values_text.pack(fill="both", expand=True, pady=(0, 10))

        # Right Column: Afflicted Indicators
        right = ttk.LabelFrame(container, text="🎯 Indicators Afflicted", padding=10)
        right.pack(side="right", fill="both", expand=True)

        ttk.Label(right, text="These KPIs follow this template. Use 'Set Override' to\nassign a different profile to specific KPIs.", font=("Helvetica", 8, "italic")).pack(anchor="w", pady=(0, 5))

        self.ind_tree = ttk.Treeview(right, columns=("ID", "Name", "Override"), show="headings", height=15)
        self.ind_tree.heading("ID", text="ID"); self.ind_tree.column("ID", width=40)
        self.ind_tree.heading("Name", text="Indicator Name"); self.ind_tree.column("Name", width=150)
        self.ind_tree.heading("Override", text="Profile Override"); self.ind_tree.column("Override", width=120)
        
        self.ind_tree.tag_configure("override", background="#FFF3E0")
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
            self._on_profile_change(None)
            return
            
        self.name_var.set(self.initial_data.get('name', ''))
        
        # Load multiple years in listbox
        years = self.initial_data.get('years', [])
        if not years and 'year' in self.initial_data:
            years = [self.initial_data['year']]
        
        for idx in range(self.year_listbox.size()):
            try:
                y_val = int(self.year_listbox.get(idx))
                if y_val in years:
                    self.year_listbox.selection_set(idx)
            except: pass
        
        self.profile_var.set(self.initial_data.get('distribution_profile', PROFILE_EVEN))
        
        vals = self.initial_data.get('repartition_values', {})
        self.values_text.delete("1.0", tk.END)
        self.values_text.insert("1.0", json.dumps(vals, indent=4))
        
        # Load indicators
        if 'id' in self.initial_data:
            inds = kpi_splits_manager.get_indicators_for_global_split(self.initial_data['id'])
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
            ov_disp = i.get('override') or "(Default)"
            tags = ("override",) if i.get('override') else ()
            self.ind_tree.insert("", "end", iid=str(i['indicator_id']), values=(i['indicator_id'], i['indicator_name'], ov_disp), tags=tags)

    def _on_profile_change(self, event):
        profile = self.profile_var.get()
        months = [m for m in calendar.month_name[1:] if m]
        
        def calculate_weights(num_periods, p_type):
            if profile == PROFILE_EVEN:
                factors = [1.0] * num_periods
            elif profile == PROFILE_ANNUAL_PROGRESSIVE:
                factors = [0.8 + (1.2 - 0.8) * (i / (num_periods-1)) for i in range(num_periods)]
            elif profile == PROFILE_TRUE_ANNUAL_SINUSOIDAL:
                factors = [1.0 + 0.2 * math.sin(2 * math.pi * (i / (num_periods-1))) for i in range(num_periods)]
            else:
                factors = [1.0] * num_periods
            
            total_f = sum(factors)
            return {label: round((factors[i] / total_f) * 100.0, 4) for i, label in enumerate(p_type)}

        monthly = calculate_weights(12, months)
        quarterly = calculate_weights(4, ["Q1", "Q2", "Q3", "Q4"])
        
        # We define a "Universal" JSON structure
        vals = {
            "mode": "universal",
            "monthly": monthly,
            "quarterly": quarterly
        }
        
        if event is not None or not self.initial_data:
            self.values_text.delete("1.0", tk.END)
            self.values_text.insert("1.0", json.dumps(vals, indent=4))

    def _open_advanced_analysis(self):
        dialog = AdvancedSplitDialog(self)
        self.wait_window(dialog)
        res_tuple = dialog.get_result()
        if res_tuple:
            weights, target_kpis = res_tuple
            self.values_text.delete("1.0", tk.END)
            self.values_text.insert("1.0", json.dumps(weights, indent=4))
            
            existing_ids = [i['indicator_id'] for i in self.afflicted_indicators]
            for k in target_kpis:
                if k['indicator_id'] not in existing_ids:
                    self.afflicted_indicators.append(k)
            
            self._refresh_ind_tree()
            messagebox.showinfo("Analysis", f"Multivariate weights applied and {len(target_kpis)} indicators linked.")

    def _add_indicators(self):
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
        
        years = []
        for idx in self.year_listbox.curselection():
            years.append(int(self.year_listbox.get(idx)))
            
        if not years:
            messagebox.showwarning("Error", "At least one year is required.")
            return

        try:
            values = json.loads(self.values_text.get("1.0", tk.END).strip() or "{}")
        except json.JSONDecodeError as e:
            messagebox.showerror("JSON Error", f"Invalid JSON format: {e}")
            return

        self.result_data = {
            "name": name,
            "years": years,
            "repartition_logic": "universal", # Set to universal to signal multi-level support
            "repartition_values": values,
            "distribution_profile": self.profile_var.get(),
            "profile_params": {}, 
            "afflicted_indicators": self.afflicted_indicators
        }
        self.destroy()

    def get_result(self):
        return self.result_data
