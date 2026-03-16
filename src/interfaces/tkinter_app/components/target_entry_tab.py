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
        # { kpi_id: { 'target1': val, 'target2': val, 'manual1': bool, 'manual2': bool, 'kpi_info': dict } }
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
            
            self.all_kpis_data_cache[tid] = {
                'target1': t_data.get('annual_target1', 0.0),
                'target2': t_data.get('annual_target2', 0.0),
                'manual1': bool(t_data.get('is_target1_manual', False)),
                'manual2': bool(t_data.get('is_target2_manual', False)),
                'hist_y1_t1': h1_data.get('annual_target1'),
                'hist_y1_t2': h1_data.get('annual_target2'),
                'hist_y2_t1': h2_data.get('annual_target1'),
                'hist_y2_t2': h2_data.get('annual_target2'),
                'kpi_info': k
            }

        self._build_tree()
        self.render_cards()

    def _build_tree(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        self.tree.insert("", "end", iid="ALL", text="🌍 All Indicators", open=True)
        
        # Organize for tree using hierarchy_path
        # Map: path_tuple -> tree_iid
        path_map = { (): "ALL" }
        
        # Sort paths to build parent levels before children
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

        # Filter KPIs
        for kid, data in self.all_kpis_data_cache.items():
            info = data['kpi_info']
            # Search filter
            if query and query not in info['indicator_name'].lower(): continue
            
            # Tree filter logic
            if sel_id != "ALL":
                # sel_id is "P_Part1_Part2..."
                path_str = info.get('hierarchy_path', '')
                if not path_str: continue # KPI has no path, but we are in a sub-path
                
                parts = path_str.split(' > ')
                current_p_str = "_".join(parts)
                # Check if current KPI path starts with the selected path
                target_p_str = sel_id[2:] # Remove "P_"
                if not current_p_str.startswith(target_p_str):
                    continue
            
            self._create_card(kid, data)

        self._populating_target_kpi_entries = False
        self._recalculate_all_formulas_ui(1)
        self._recalculate_all_formulas_ui(2)

    def _create_card(self, kid, data):
        info = data['kpi_info']
        is_calc = bool(info.get('is_calculated', False))
        
        style = "Formula.TLabelframe" if is_calc else "Manual.TLabelframe"
        card = ttk.LabelFrame(self.scrollable, text=f"{info['indicator_name']} ({info['unit_of_measure']})", style=style, padding=10)
        card.pack(fill='x', padx=15, pady=5)

        self.kpi_target_entry_widgets[kid] = {'targets': {}}
        row = ttk.Frame(card, style="Card.TFrame")
        row.pack(fill='x')

        self._create_input(row, kid, 1, data, is_calc)
        self._create_input(row, kid, 2, data, is_calc)

    def _create_input(self, parent, kid, tn, data, is_calc):
        f = ttk.Frame(parent, style="Card.TFrame")
        f.pack(side='left', fill='x', expand=True, padx=5)
        
        ttk.Label(f, text=f"T{tn}:", width=4).pack(side='left')
        
        var = tk.StringVar(value=str(data[f'target{tn}']))
        m_var = tk.BooleanVar(value=data[f'manual{tn}'])
        
        state = 'normal' if (not is_calc or m_var.get()) else 'disabled'
        ent = ttk.Entry(f, textvariable=var, width=12, state=state)
        ent.pack(side='left', padx=5)
        
        # Historical info
        h1 = data.get(f'hist_y1_t{tn}')
        h2 = data.get(f'hist_y2_t{tn}')
        h_text = ""
        if h1 is not None or h2 is not None:
            parts = []
            if h1 is not None: parts.append(f"Y-1: {round(h1, 2)}")
            if h2 is not None: parts.append(f"Y-2: {round(h2, 2)}")
            h_text = f"({', '.join(parts)})"
        
        if h_text:
            ttk.Label(f, text=h_text, font=("Segoe UI", 8, "italic"), foreground="gray").pack(side='left', padx=2)
        
        # Prevent immediate trace-driven updates while typing. 
        # Use FocusOut to sync the cache and trigger global updates.
        ent.bind("<FocusOut>", lambda e, k=kid, t=tn, v=var: self._sync_cache(k, t, v.get()))
        ent.bind("<Return>", lambda e, k=kid, t=tn, v=var: self._sync_cache(k, t, v.get()))

        if is_calc or bool(data['kpi_info'].get('master_kpi_id')):
            label = "Override" if is_calc else "M"
            cb = ttk.Checkbutton(f, text=label, variable=m_var, command=lambda: self._sync_and_update(kid, tn))
            cb.pack(side='left')

        self.kpi_target_entry_widgets[kid]['targets'][tn] = {
            'var': var, 'ent': ent, 'm_var': m_var, 'data': data
        }

    def _sync_cache(self, kid, tn, val):
        if self._populating_target_kpi_entries: return
        try: self.all_kpis_data_cache[kid][f'target{tn}'] = float(val or 0)
        except: pass
        
        if not self._recalculating_ui and not self._master_sub_update_active:
            self._recalculate_all_formulas_ui(tn)
            self._sync_master_sub(kid, tn)

    def _sync_and_update(self, kid, tn):
        # Toggle state
        w = self.kpi_target_entry_widgets[kid]['targets'][tn]
        m = w['m_var'].get()
        self.all_kpis_data_cache[kid][f'manual{tn}'] = m
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
                    if data['kpi_info'].get('is_calculated') and not data[f'manual{tn}']:
                        calc = self._evaluate_kpi(kid, tn)
                        if abs(data[f'target{tn}'] - calc) > 1e-9:
                            data[f'target{tn}'] = calc
                            if kid in self.kpi_target_entry_widgets:
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
                    return self.all_kpis_data_cache.get(int(id), {}).get(f'target{target_num}', 0.0)
                return dag.evaluate(resolver, default_target_num=tn)
            except: return 0.0
        elif f_str:
            try:
                # Basic [ID] replacement
                expr = f_str
                for match in re.findall(r'\[(\d+)\]', f_str):
                    val = self.all_kpis_data_cache.get(int(match), {}).get(f'target{tn}', 0.0)
                    expr = expr.replace(f"[{match}]", str(val))
                return float(eval(expr, {"__builtins__": None}, {"abs":abs,"min":min,"max":max,"round":round}))
            except: return 0.0
        return 0.0

    def _sync_master_sub(self, kid, tn):
        if self._master_sub_update_active: return
        info = self.all_kpis_data_cache[kid]['kpi_info']
        if info.get('master_kpi_id'): return # Sub can't push up in this simple UI logic
        
        # If it's a master, distribute
        subs = db_retriever.get_linked_sub_kpis_detailed(kid)
        if not subs: return
        
        self._master_sub_update_active = True
        try:
            total_w = sum(s['distribution_weight'] for s in subs)
            master_val = self.all_kpis_data_cache[kid][f'target{tn}']
            for s in subs:
                sid = s['id']
                if sid in self.all_kpis_data_cache and not self.all_kpis_data_cache[sid][f'manual{tn}']:
                    val = (master_val * s['distribution_weight'] / total_w) if total_w > 0 else 0
                    self.all_kpis_data_cache[sid][f'target{tn}'] = val
                    if sid in self.kpi_target_entry_widgets:
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

        if not messagebox.askyesno("Confirm Save", msg):
            return

        data_map = {}
        for kid, data in self.all_kpis_data_cache.items():
            data_map[str(kid)] = {
                'annual_target1': data['target1'],
                'annual_target2': data['target2'],
                'is_target1_manual': data['manual1'],
                'is_target2_manual': data['manual2'],
                'target1_is_formula_based': bool(data['kpi_info'].get('is_calculated')) and not data['manual1'],
                'target2_is_formula_based': bool(data['kpi_info'].get('is_calculated')) and not data['manual2'],
            }
            
        def run():
            try:
                annual_targets_manager.save_annual_targets(year, target_plant_ids, data_map)
                self.after(0, lambda: messagebox.showinfo("Success", "Targets saved successfully."))
            except Exception as e:
                self.after(0, lambda ex=e: messagebox.showerror("Error", str(ex)))
        threading.Thread(target=run, daemon=True).start()
