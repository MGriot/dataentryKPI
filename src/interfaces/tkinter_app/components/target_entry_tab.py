# src/interfaces/tkinter_app/components/target_entry_tab.py
import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import threading
import re

from src.target_management import annual as annual_targets_manager
from src import data_retriever as db_retriever
from src.interfaces.common_ui.helpers import get_kpi_display_name
from src.core.node_engine import KpiDAG

class TargetEntryTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._populating_target_kpi_entries = False
        self._master_sub_update_active = False
        self._recalculating_ui = False
        
        self.target1_display_name = self.app.settings.get('display_names', {}).get('target1', 'Target 1')
        self.target2_display_name = self.app.settings.get('display_names', {}).get('target2', 'Target 2')
        
        self.plants = []
        # Persistent state for all KPIs loaded for the current year/plant
        # { kpi_id: { 'targets': { tn: {val, manual, hist_y1, hist_y2} }, 'kpi_info': dict } }
        self.all_kpis_data_cache = {}
        # Active UI widgets for currently visible KPIs
        self.kpi_target_entry_widgets = {}
        
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._on_filter_change())

        self.create_widgets()

    def create_widgets(self):
        # Top toolbar
        toolbar = ttk.Frame(self, style="Content.TFrame", padding=10)
        toolbar.pack(side='top', fill='x')

        ttk.Label(toolbar, text="Year:").pack(side='left', padx=5)
        self.year_cb_target = ttk.Combobox(toolbar, values=[str(y) for y in range(2020, 2031)], width=8, state='readonly')
        self.year_cb_target.set(str(datetime.datetime.now().year))
        self.year_cb_target.pack(side='left', padx=5)
        self.year_cb_target.bind('<<ComboboxSelected>>', lambda e: self.load_data())

        ttk.Label(toolbar, text="Plant:").pack(side='left', padx=5)
        self.plant_cb_target = ttk.Combobox(toolbar, width=20, state='readonly')
        self.plant_cb_target.pack(side='left', padx=5)
        self.plant_cb_target.bind('<<ComboboxSelected>>', lambda e: self.load_data())

        ttk.Button(toolbar, text="Save All Changes", command=self.save_all_targets_entry, style="Action.TButton").pack(side='right', padx=5)
        
        self.apply_all_plants_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(toolbar, text="Apply to All Plants", variable=self.apply_all_plants_var).pack(side='right', padx=15)

        # Paned UI
        self.paned = ttk.PanedWindow(self, orient="horizontal")
        self.paned.pack(fill="both", expand=True, padx=10, pady=5)

        # Sidebar
        sidebar = ttk.Frame(self.paned, style="Card.TFrame")
        self.paned.add(sidebar, weight=1)

        search_f = ttk.Frame(sidebar, style="Card.TFrame", padding=5)
        search_f.pack(fill="x")
        ttk.Label(search_f, text="🔍").pack(side="left")
        ttk.Entry(search_f, textvariable=self.search_var).pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(search_f, text="×", width=3, command=lambda: self.search_var.set("")).pack(side="left")

        self.tree = ttk.Treeview(sidebar, selectmode="browse", show="tree")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_filter_change)

        # Content
        content_f = ttk.Frame(self.paned, style="Content.TFrame")
        self.paned.add(content_f, weight=3)

        self.canvas = tk.Canvas(content_f, bg="#F0F0F0", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        
        sb = ttk.Scrollbar(content_f, orient="vertical", command=self.canvas.yview)
        sb.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=sb.set)

        self.scrollable = ttk.Frame(self.canvas, style="Content.TFrame")
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable, anchor="nw")
        
        self.scrollable.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        content_f.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    def populate_target_comboboxes(self):
        self.plants = [dict(row) for row in db_retriever.get_all_plants(visible_only=True)]
        self.plant_cb_target['values'] = [p['name'] for p in self.plants]
        if self.plants:
            self.plant_cb_target.set(self.plants[0]['name'])
            self.load_data()

    def load_data(self):
        """Loads all data into cache and builds tree."""
        year_str = self.year_cb_target.get()
        p_name = self.plant_cb_target.get()
        if not year_str or not p_name: return

        year = int(year_str)
        p_id = [p['id'] for p in self.plants if p['name'] == p_name][0]
        kpis = [dict(row) for row in db_retriever.get_all_kpis_detailed(only_visible=True, plant_id=p_id)]
        
        # Current year targets
        targets = {t['kpi_id']: dict(t) for t in db_retriever.get_annual_targets(p_id, year)}
        
        # Historical targets
        hist1 = {t['kpi_id']: dict(t) for t in db_retriever.get_annual_targets(p_id, year - 1)}
        hist2 = {t['kpi_id']: dict(t) for t in db_retriever.get_annual_targets(p_id, year - 2)}

        # Populate state cache
        self.all_kpis_data_cache = {}
        for k in kpis:
            tid = k['id']
            t_data = targets.get(tid, {})
            h1_data = hist1.get(tid, {})
            h2_data = hist2.get(tid, {})
            
            t_values = {}
            for tv in t_data.get('target_values', []):
                tn = tv['target_number']
                t_values[tn] = {
                    'val': tv['target_value'],
                    'manual': bool(tv['is_manual']),
                    'hist_y1': None,
                    'hist_y2': None
                }
            
            for tn in [1, 2]:
                if tn not in t_values:
                    t_values[tn] = {'val': 0.0, 'manual': True, 'hist_y1': None, 'hist_y2': None}

            for h_idx, h_data in enumerate([h1_data, h2_data]):
                h_key = f'hist_y{h_idx+1}'
                for tv in h_data.get('target_values', []):
                    tn = tv['target_number']
                    if tn in t_values:
                        t_values[tn][h_key] = tv['target_value']

            self.all_kpis_data_cache[tid] = {
                'targets': t_values,
                'kpi_info': k
            }

        self._build_tree()
        self.render_cards()

    def _build_tree(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        self.tree.insert("", "end", iid="ALL", text="🌍 All Indicators", open=True)
        
        path_map = { (): "ALL" }
        all_paths = set()
        for kid, data in self.all_kpis_data_cache.items():
            path_str = data['kpi_info'].get('hierarchy_path', '')
            if path_str:
                parts = tuple(path_str.split(' > '))
                for i in range(1, len(parts) + 1):
                    all_paths.add(parts[:i])

        sorted_paths = sorted(list(all_paths), key=len)
        for p in sorted_paths:
            parent_p = p[:-1]
            parent_iid = path_map[parent_p]
            iid = "P_" + "_".join(p)
            name = p[-1]
            icon = "📂" if len(p) > 1 else "📁"
            self.tree.insert(parent_iid, "end", iid=iid, text=f"{icon} {name}", open=False)
            path_map[p] = iid

    def _on_filter_change(self, *args):
        self.render_cards()

    def render_cards(self):
        self._populating_target_kpi_entries = True
        for child in self.scrollable.winfo_children(): child.destroy()
        self.kpi_target_entry_widgets.clear()

        query = self.search_var.get().lower()
        sel = self.tree.selection()
        sel_id = sel[0] if sel else "ALL"

        for kid, data in self.all_kpis_data_cache.items():
            info = data['kpi_info']
            if query and query not in info['indicator_name'].lower(): continue
            
            if sel_id != "ALL":
                path_str = info.get('hierarchy_path', '')
                if not path_str: continue
                parts = path_str.split(' > ')
                current_p_str = "_".join(parts)
                target_p_str = sel_id[2:]
                if not current_p_str.startswith(target_p_str):
                    continue
            
            self._create_card(kid, data)

        self._populating_target_kpi_entries = False
        
        all_tns = set()
        for data in self.all_kpis_data_cache.values():
            all_tns.update(data['targets'].keys())
        for tn in sorted(list(all_tns)):
            self._recalculate_all_formulas_ui(tn)

    def _create_card(self, kid, data):
        info = data['kpi_info']
        is_calc = bool(info.get('is_calculated', False))
        
        style = "Formula.TLabelframe" if is_calc else "Manual.TLabelframe"
        card = ttk.LabelFrame(self.scrollable, text=f"{info['indicator_name']} ({info['unit_of_measure']})", style=style, padding=10)
        card.pack(fill='x', padx=15, pady=5)

        self.kpi_target_entry_widgets[kid] = {'targets': {}}
        grid = ttk.Frame(card, style="Card.TFrame")
        grid.pack(fill='x')
        
        t_values = data['targets']
        for tn in sorted(t_values.keys()):
            self._create_input(grid, kid, tn, t_values[tn], is_calc)

        actions = ttk.Frame(card, style="Card.TFrame")
        actions.pack(fill='x', pady=(5, 0))
        ttk.Button(actions, text="+ Add Target", command=lambda: self._add_target_to_kpi(kid), width=12).pack(side='right')

    def _add_target_to_kpi(self, kid):
        t_values = self.all_kpis_data_cache[kid]['targets']
        new_tn = max(t_values.keys()) + 1 if t_values else 1
        t_values[new_tn] = {'val': 0.0, 'manual': True, 'hist_y1': None, 'hist_y2': None}
        self.render_cards()

    def _create_input(self, parent, kid, tn, t_data, is_calc):
        f = ttk.Frame(parent, style="Card.TFrame")
        f.pack(side='left', fill='x', expand=True, padx=5, pady=2)
        
        ttk.Label(f, text=f"T{tn}:", width=4).pack(side='left')
        
        var = tk.StringVar(value=str(t_data['val']))
        m_var = tk.BooleanVar(value=t_data['manual'])
        
        state = 'normal' if (not is_calc or m_var.get()) else 'disabled'
        ent = ttk.Entry(f, textvariable=var, width=10, state=state)
        ent.pack(side='left', padx=5)
        
        h1 = t_data.get('hist_y1')
        h2 = t_data.get('hist_y2')
        parts = []
        if h1 is not None: parts.append(f"Y-1: {round(h1, 2)}")
        if h2 is not None: parts.append(f"Y-2: {round(h2, 2)}")
        h_text = f"({', '.join(parts)})" if parts else "(No History)"
        color = "#0056b3" if parts else "#999999"
        ttk.Label(f, text=h_text, font=("Segoe UI", 8), foreground=color).pack(side='left', padx=2)
        
        ent.bind("<FocusOut>", lambda e, k=kid, t=tn, v=var: self._sync_cache(k, t, v.get()))
        ent.bind("<Return>", lambda e, k=kid, t=tn, v=var: self._sync_cache(k, t, v.get()))

        if is_calc or bool(self.all_kpis_data_cache[kid]['kpi_info'].get('master_kpi_id')):
            label = "Override" if is_calc else "M"
            cb = ttk.Checkbutton(f, text=label, variable=m_var, command=lambda: self._sync_and_update(kid, tn))
            cb.pack(side='left')

        self.kpi_target_entry_widgets[kid]['targets'][tn] = {
            'var': var, 'ent': ent, 'm_var': m_var, 'data': t_data
        }

    def _sync_cache(self, kid, tn, val):
        if self._populating_target_kpi_entries: return
        try:
            val_float = float(val or 0)
            self.all_kpis_data_cache[kid]['targets'][tn]['val'] = val_float
        except: pass
        
        if not self._recalculating_ui and not self._master_sub_update_active:
            self._recalculate_all_formulas_ui(tn)
            self._sync_master_sub(kid, tn)

    def _sync_and_update(self, kid, tn):
        w = self.kpi_target_entry_widgets[kid]['targets'][tn]
        m = w['m_var'].get()
        self.all_kpis_data_cache[kid]['targets'][tn]['manual'] = m
        w['ent'].config(state='normal' if m else 'disabled')
        
        if not m: self._recalculate_all_formulas_ui(tn)
        self._sync_master_sub(kid, tn)

    def _recalculate_all_formulas_ui(self, tn):
        if self._populating_target_kpi_entries or self._recalculating_ui: return
        self._recalculating_ui = True
        try:
            for _ in range(5):
                changed = False
                for kid, data in self.all_kpis_data_cache.items():
                    if tn not in data['targets']: continue
                    if data['kpi_info'].get('is_calculated') and not data['targets'][tn]['manual']:
                        calc = self._evaluate_kpi(kid, tn)
                        if abs(data['targets'][tn]['val'] - calc) > 1e-9:
                            data['targets'][tn]['val'] = calc
                            if kid in self.kpi_target_entry_widgets and tn in self.kpi_target_entry_widgets[kid]['targets']:
                                self.kpi_target_entry_widgets[kid]['targets'][tn]['var'].set(str(round(calc, 4)))
                            changed = True
                if not changed: break
        finally: self._recalculating_ui = False

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

    def _sync_master_sub(self, kid, tn):
        if self._master_sub_update_active: return
        info = self.all_kpis_data_cache[kid]['kpi_info']
        if info.get('master_kpi_id'): return
        
        subs = db_retriever.get_linked_sub_kpis_detailed(kid)
        if not subs: return
        
        self._master_sub_update_active = True
        try:
            total_w = sum(s['distribution_weight'] for s in subs)
            master_val = self.all_kpis_data_cache[kid]['targets'][tn]['val']
            for s in subs:
                sid = s['id']
                if sid in self.all_kpis_data_cache and tn in self.all_kpis_data_cache[sid]['targets']:
                    if not self.all_kpis_data_cache[sid]['targets'][tn]['manual']:
                        val = (master_val * s['distribution_weight'] / total_w) if total_w > 0 else 0
                        self.all_kpis_data_cache[sid]['targets'][tn]['val'] = val
                        if sid in self.kpi_target_entry_widgets and tn in self.kpi_target_entry_widgets[sid]['targets']:
                            self.kpi_target_entry_widgets[sid]['targets'][tn]['var'].set(str(round(val, 4)))
        finally: self._master_sub_update_active = False

    def save_all_targets_entry(self):
        year = int(self.year_cb_target.get())
        p_name = self.plant_cb_target.get()
        p_id = [p['id'] for p in self.plants if p['name'] == p_name][0]
        
        if self.apply_all_plants_var.get():
            target_plant_ids = [p['id'] for p in self.plants]
            msg = f"Save these targets for ALL {len(target_plant_ids)} plants?"
        else:
            target_plant_ids = p_id
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
            data_map[str(kid)] = {'targets': targets_list}
            
        def run():
            try:
                annual_targets_manager.save_annual_targets(year, target_plant_ids, data_map)
                self.after(0, lambda: messagebox.showinfo("Success", "Targets saved successfully."))
            except Exception as e:
                self.after(0, lambda ex=e: messagebox.showerror("Error", str(ex)))
        threading.Thread(target=run, daemon=True).start()
