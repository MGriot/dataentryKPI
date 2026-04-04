# src/interfaces/tkinter_app/components/target_entry_tab.py
import tkinter as tk
from tkinter import ttk, messagebox
import json
import re
from src import data_retriever
from src.target_management import annual as annual_targets_manager
from src.kpi_management import specs as kpi_specs_manager
from src.core.node_engine import KpiDAG
import datetime

class TargetEntryTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.plants = []
        self.all_kpis_data_cache = {} # { kpi_id: { kpi_info, targets: { target_num: {val, manual, hist_y1, hist_y2} }, global_split_id } }
        self.kpi_target_entry_widgets = {} # { kpi_id: { card_frame, targets: { target_num: { var, ent, m_var, data } }, gs_var } }
        
        self._populating_target_kpi_entries = False
        self._recalculating_ui = False

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._on_filter_change())

        self.create_widgets()

    def _refresh_gs_options(self):
        year_val = self.year_cb_target.get()
        if not year_val: return
        year = int(year_val)
        splits_raw = data_retriever.get_all_global_splits(year=year)
        self.gs_map = {f"{s['name']}": s['id'] for s in splits_raw}
        self.gs_names = ["None (Custom)"] + list(self.gs_map.keys())

    def create_widgets(self):
        # Top toolbar
        toolbar = ttk.Frame(self, style="Content.TFrame", padding=10)
        toolbar.pack(side='top', fill='x')

        ttk.Label(toolbar, text="Year:").pack(side='left', padx=5)
        current_year = datetime.datetime.now().year
        self.year_cb_target = ttk.Combobox(toolbar, values=[str(y) for y in range(current_year-2, current_year+5)], width=10, state='readonly')
        self.year_cb_target.set(str(current_year))
        self.year_cb_target.pack(side='left', padx=5)
        self.year_cb_target.bind("<<ComboboxSelected>>", lambda e: self.load_data())

        ttk.Label(toolbar, text="Plant:").pack(side='left', padx=5)
        self.plant_cb_target = ttk.Combobox(toolbar, width=30, state='readonly')
        self.plant_cb_target.pack(side='left', padx=5)
        self.plant_cb_target.bind("<<ComboboxSelected>>", lambda e: self.load_data())

        ttk.Label(toolbar, text="Search:").pack(side='left', padx=(20, 5))
        ttk.Entry(toolbar, textvariable=self.search_var, width=30).pack(side='left', padx=5)

        self.apply_all_plants_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(toolbar, text="Apply to all plants", variable=self.apply_all_plants_var).pack(side='left', padx=20)

        save_btn = ttk.Button(toolbar, text="💾 Save All Targets", command=self.save_all_targets_entry, style="Action.TButton")
        save_btn.pack(side='right', padx=10)

        # Scrollable area
        content_f = ttk.Frame(self, style="Content.TFrame")
        content_f.pack(fill='both', expand=True)

        self.canvas = tk.Canvas(content_f, background="#F5F5F7", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(content_f, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.scrollable = ttk.Frame(self.canvas, style="Content.TFrame")
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable, anchor="nw")

        self.scrollable.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        content_f.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    def populate_target_comboboxes(self):
        self.plants = [dict(row) for row in data_retriever.get_all_plants(visible_only=True)]
        self.plant_cb_target['values'] = [p['name'] for p in self.plants]
        if self.plants:
            self.plant_cb_target.set(self.plants[0]['name'])
            self.load_data()

    def on_tab_selected(self):
        """Called by main app when this tab is shown."""
        self.load_data()

    def load_data(self):
        """Loads all data into cache and builds tree."""
        self._refresh_gs_options()
        self.target_config = self.app.settings.get('targets', [{"id": 1, "name": "Target"}])
        year_str = self.year_cb_target.get()
        p_name = self.plant_cb_target.get()
        if not year_str or not p_name: return

        year = int(year_str)
        p_id = [p['id'] for p in self.plants if p['name'] == p_name][0]
        kpis = [dict(row) for row in data_retriever.get_all_kpis_detailed(only_visible=True, plant_id=p_id)]
        
        # Current year targets
        targets = {t['kpi_id']: dict(t) for t in data_retriever.get_annual_targets(p_id, year)}
        
        # Fetch standardized GS links for this year
        from src.kpi_management.splits import get_all_global_splits, get_indicators_for_global_split
        all_gs = get_all_global_splits(year=year)
        
        # indicator_id -> list of {'id', 'name'}
        self.kpi_to_gs_options = {} 
        for gs in all_gs:
            for ind in get_indicators_for_global_split(gs['id']):
                iid = ind['indicator_id']
                if iid not in self.kpi_to_gs_options:
                    self.kpi_to_gs_options[iid] = []
                self.kpi_to_gs_options[iid].append({'id': gs['id'], 'name': gs['name']})

        # Historical targets
        hist1 = {t['kpi_id']: dict(t) for t in data_retriever.get_annual_targets(p_id, year - 1)}
        hist2 = {t['kpi_id']: dict(t) for t in data_retriever.get_annual_targets(p_id, year - 2)}

        # Populate state cache
        self.all_kpis_data_cache = {}
        for k in kpis:
            tid = k['id']
            ind_id = k.get('indicator_id')
            t_data = targets.get(tid, {})
            h1_data = hist1.get(tid, {})
            h2_data = hist2.get(tid, {})
            
            # Valid splits for this specific indicator
            valid_splits = self.kpi_to_gs_options.get(ind_id, [])
            valid_split_ids = [vs['id'] for vs in valid_splits]

            # Pre-select standardized GS if not manually set
            cur_gs_id = t_data.get('global_split_id')
            is_standard = False
            
            if cur_gs_id is None and len(valid_splits) == 1:
                cur_gs_id = valid_splits[0]['id']
                is_standard = True
            elif cur_gs_id in valid_split_ids:
                is_standard = True

            t_values = {}
            # Initialize with default targets if no data
            config_target_ids = [tc['id'] for tv in [self.target_config] for tc in tv] # Simplified
            
            # We need to map actual values from target_values list
            db_vals = {tv['target_number']: tv for tv in t_data.get('target_values', [])}
            
            for tc in self.target_config:
                tn = tc['id']
                tv = db_vals.get(tn, {})
                t_values[tn] = {
                    'val': tv.get('target_value', 0.0),
                    'manual': bool(tv.get('is_manual', True)),
                    'hist_y1': None,
                    'hist_y2': None
                }
            
            # Fill history
            for tv in h1_data.get('target_values', []):
                tn = tv['target_number']
                if tn in t_values: t_values[tn]['hist_y1'] = tv['target_value']
            for tv in h2_data.get('target_values', []):
                tn = tv['target_number']
                if tn in t_values: t_values[tn]['hist_y2'] = tv['target_value']

            self.all_kpis_data_cache[tid] = {
                'kpi_info': k,
                'targets': t_values,
                'global_split_id': cur_gs_id,
                'is_standard': is_standard
            }

        self._refresh_ui()

    def _on_filter_change(self):
        self._refresh_ui()

    def _refresh_ui(self):
        self._populating_target_kpi_entries = True
        for c in self.scrollable.winfo_children(): c.destroy()
        self.kpi_target_entry_widgets = {}

        query = self.search_var.get().lower()
        
        # Sort by hierarchy path
        sorted_kids = sorted(self.all_kpis_data_cache.keys(), 
                            key=lambda x: (self.all_kpis_data_cache[x]['kpi_info'].get('hierarchy_path','') or '', 
                                           self.all_kpis_data_cache[x]['kpi_info'].get('indicator_name','') or ''))

        for kid in sorted_kids:
            data = self.all_kpis_data_cache[kid]
            k_info = data['kpi_info']
            if query and query not in k_info['indicator_name'].lower() and query not in (k_info.get('hierarchy_path','') or '').lower():
                continue
            self._create_card(kid, data)
        
        self._populating_target_kpi_entries = False
        # Recalculate all formulas once UI is built
        for tc in self.target_config:
            self._recalculate_all_formulas_ui(tc['id'])

    def _create_card(self, kid, data):
        k_info = data['kpi_info']
        card = ttk.Frame(self.scrollable, style="Card.TFrame", padding=15)
        card.pack(fill='x', padx=15, pady=8)

        self.kpi_target_entry_widgets[kid] = {'card_frame': card, 'targets': {}}

        # Header
        top_f = ttk.Frame(card, style="Card.TFrame")
        top_f.pack(fill='x')
        
        path = k_info.get('hierarchy_path', 'Root')
        ttk.Label(top_f, text=f"{path} >", font=("Segoe UI", 9), foreground="#666", background="#FFFFFF").pack(side='left')
        ttk.Label(top_f, text=k_info['indicator_name'], font=("Segoe UI", 11, "bold"), background="#FFFFFF").pack(side='left', padx=5)
        
        type_color = "#007AFF" if k_info.get('is_calculated') else "#28a745"
        calc_type = k_info.get('calculation_type', 'Incremental')
        calc_label = f"({calc_type})" if calc_type != 'Incremental' else ""
        ttk.Label(top_f, text=calc_label, font=("Segoe UI", 9), foreground=type_color, background="#FFFFFF").pack(side='left')

        # Global Split Selector
        gs_frame = ttk.Frame(card, style="Card.TFrame")
        gs_frame.pack(fill='x', pady=(5, 10))
        
        ttk.Label(gs_frame, text="Split Profile:", font=("Segoe UI", 9), background="#FFFFFF").pack(side='left')
        
        gs_var = tk.StringVar()
        cur_gs_id = data.get('global_split_id')
        
        # Build local options for this specific KPI
        ind_id = k_info.get('indicator_id')
        local_valid_splits = self.kpi_to_gs_options.get(ind_id, [])
        local_gs_map = {s['name']: s['id'] for s in local_valid_splits}
        local_gs_names = ["None (Custom)"] + list(local_gs_map.keys())
        
        cur_gs_name = next((name for name, sid in local_gs_map.items() if sid == cur_gs_id), "None (Custom)")
        gs_var.set(cur_gs_name)
        
        gs_cb = ttk.Combobox(gs_frame, textvariable=gs_var, values=local_gs_names, state='readonly', width=30)
        gs_cb.pack(side='left', padx=10)
        gs_cb.bind("<<ComboboxSelected>>", lambda e, k=kid, v=gs_var, m=local_gs_map: self._on_gs_change(k, v.get(), m))

        if data.get('is_standard'):
            ttk.Label(gs_frame, text="⭐ Standard", foreground="#d32f2f", font=("Segoe UI", 8, "bold"), background="#FFFFFF").pack(side='left')

        # Targets grid
        targets_f = ttk.Frame(card, style="Card.TFrame")
        targets_f.pack(fill='x')

        is_calc = bool(k_info.get('is_calculated'))

        for tc in self.target_config:
            tn = tc['id']
            t_data = data['targets'].get(tn, {'val': 0.0, 'manual': True, 'hist_y1': None, 'hist_y2': None})
            
            f = ttk.Frame(targets_f, style="Card.TFrame")
            f.pack(fill='x', pady=2)
            
            ttk.Label(f, text=f"{tc['name']}:", width=12, background="#FFFFFF").pack(side='left')
            
            var = tk.StringVar(value=str(t_data['val']))
            m_var = tk.BooleanVar(value=t_data['manual'])
            
            state = 'normal' if (not is_calc or t_data['manual']) else 'disabled'
            ent = ttk.Entry(f, textvariable=var, width=15, state=state)
            ent.pack(side='left', padx=5)
            
            # History info
            h1 = t_data.get('hist_y1')
            h2 = t_data.get('hist_y2')
            parts = []
            if h1 is not None: parts.append(f"Y-1: {round(h1, 2)}")
            if h2 is not None: parts.append(f"Y-2: {round(h2, 2)}")
            h_text = f"({', '.join(parts)})" if parts else "(No History)"
            color = "#0056b3" if parts else "#999999"
            ttk.Label(f, text=h_text, font=("Segoe UI", 8), foreground=color, background="#FFFFFF").pack(side='left', padx=2)

            ent.bind("<FocusOut>", lambda e, k=kid, t=tn, v=var: self._sync_cache(k, t, v.get()))
            ent.bind("<Return>", lambda e, k=kid, t=tn, v=var: self._sync_cache(k, t, v.get()))

            if is_calc:
                cb = ttk.Checkbutton(f, text="Override", variable=m_var, command=lambda k=kid, t=tn: self._sync_and_update(k, t))
                cb.pack(side='left', padx=10)

            self.kpi_target_entry_widgets[kid]['targets'][tn] = {
                'var': var, 'ent': ent, 'm_var': m_var, 'data': t_data
            }

    def _on_gs_change(self, kid, name, local_map):
        gs_id = local_map.get(name)
        self.all_kpis_data_cache[kid]['global_split_id'] = gs_id
        # Update standard status if needed (optional visual only)

    def _sync_cache(self, kid, tn, val):
        if self._populating_target_kpi_entries: return
        try:
            val_float = float(val or 0)
            self.all_kpis_data_cache[kid]['targets'][tn]['val'] = val_float
        except: pass

        if not self._recalculating_ui:
            self._recalculate_all_formulas_ui(tn)

    def _sync_and_update(self, kid, tn):
        w = self.kpi_target_entry_widgets[kid]['targets'][tn]
        m = w['m_var'].get()
        self.all_kpis_data_cache[kid]['targets'][tn]['manual'] = m
        w['ent'].config(state='normal' if m else 'disabled')

        if not m: self._recalculate_all_formulas_ui(tn)

    def _recalculate_all_formulas_ui(self, tn):
        if self._populating_target_kpi_entries or self._recalculating_ui: return
        self._recalculating_ui = True
        
        # Simple topological sort would be better, but we'll just iterate a few times 
        # to handle dependencies for now (max depth 3)
        for _ in range(3):
            for kid, data in self.all_kpis_data_cache.items():
                if data['kpi_info'].get('is_calculated') and not data['targets'][tn]['manual']:
                    new_val = self._evaluate_kpi(kid, tn)
                    data['targets'][tn]['val'] = new_val
                    if kid in self.kpi_target_entry_widgets:
                        self.kpi_target_entry_widgets[kid]['targets'][tn]['var'].set(str(round(new_val, 4)))
        
        self._recalculating_ui = False

    def _evaluate_kpi(self, kid, tn):
        info = self.all_kpis_data_cache[kid]['kpi_info']
        f_json = info.get('formula_json')
        f_str = info.get('formula_string')

        if f_json:
            try:
                dag = KpiDAG.from_json(f_json)
                def resolver(id, target_num):
                    target_num = int(target_num)
                    k_data = self.all_kpis_data_cache.get(int(id))
                    if k_data and target_num in k_data['targets']:
                        return k_data['targets'][target_num]['val']
                    return 0.0
                return dag.evaluate(resolver, default_target_num=tn)
            except: return 0.0
        elif f_str:
            processed = f_str
            for match in re.findall(r'\[(\d+)\]', f_str):
                mid = int(match)
                k_data = self.all_kpis_data_cache.get(mid)
                val = 0.0
                if k_data and tn in k_data['targets']:
                    val = k_data['targets'][tn]['val']
                processed = processed.replace(f"[{match}]", str(val))
            try: return float(eval(processed, {"__builtins__": None}, {"abs": abs, "min": min, "max": max, "round": round}))
            except: return 0.0
        return 0.0

    def save_all_targets_entry(self):
        year = int(self.year_cb_target.get())
        p_name = self.plant_cb_target.get()
        p_id = [p['id'] for p in self.plants if p['name'] == p_name][0]

        if self.apply_all_plants_var.get():
            target_plant_ids = [p['id'] for p in self.plants]
            msg = f"Save these targets for ALL {len(target_plant_ids)} plants?"
        else:
            target_plant_ids = [p_id]
            msg = f"Save targets for {p_name}?"

        if not messagebox.askyesno("Confirm Save", msg): return

        data_map = {}
        for kid, data in self.all_kpis_data_cache.items():
            targets_list = []
            for tn, t_data in data['targets'].items():
                targets_list.append({
                    'target_number': tn,
                    'target_value': t_data['val'],
                    'is_manual': t_data['manual'],
                    'is_formula_based': bool(data['kpi_info'].get('is_calculated')) and not t_data['manual']
                })
            data_map[str(kid)] = {
                'targets': targets_list,
                'global_split_id': data.get('global_split_id')
            }

        def run():
            try:
                for pid in target_plant_ids:
                    annual_targets_manager.save_annual_targets(year, pid, data_map)
                self.app.after(0, lambda: messagebox.showinfo("Success", "Targets saved successfully."))
            except Exception as e:
                self.app.after(0, lambda: messagebox.showerror("Error", f"Failed to save: {e}"))

        import threading
        tk.Label(self, text="Saving...").pack() # Temp status
        threading.Thread(target=run, daemon=True).start()
