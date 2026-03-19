# src/interfaces/tkinter_app/components/analysis_tab.py
import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import calendar
from src import data_retriever as db_retriever
from src.interfaces.common_ui.helpers import get_kpi_display_name
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import pandas as pd
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import traceback

class AnalysisTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.target1_display_name = self.app.settings.get('display_names', {}).get('target1', 'Target 1')
        self.target2_display_name = self.app.settings.get('display_names', {}).get('target2', 'Target 2')
        
        self.view_mode = tk.StringVar(value="single")
        self.res_plants_map = {}
        self.kpi_hierarchy = {}
        self.selected_years = {} # year_str -> BooleanVar
        self._last_loaded_plant_id = -1

        self.create_widgets()

    def create_widgets(self):
        # View Switcher
        mode_frame = ttk.Frame(self, style="Content.TFrame")
        mode_frame.pack(fill="x", pady=5)
        ttk.Radiobutton(mode_frame, text="Single KPI Focus", variable=self.view_mode, value="single", command=self.switch_view).pack(side="left", padx=20)
        ttk.Radiobutton(mode_frame, text="Global Overview", variable=self.view_mode, value="global", command=self.switch_view).pack(side="left", padx=20)

        # Global Filters
        filter_bar = ttk.Frame(self, style="Content.TFrame", padding=(20, 0))
        filter_bar.pack(fill="x")

        # Req 11: Multi-year selector
        ttk.Label(filter_bar, text="Years:").pack(side="left", padx=5)
        self.year_mb = ttk.Menubutton(filter_bar, text="Select Years...", width=15)
        self.year_mb.pack(side="left", padx=5)
        self.year_menu = tk.Menu(self.year_mb, tearoff=0)
        self.year_mb["menu"] = self.year_menu

        ttk.Label(filter_bar, text="Plant:").pack(side="left", padx=15)
        self.plant_var = tk.StringVar()
        self.plant_cb = ttk.Combobox(filter_bar, textvariable=self.plant_var, width=20, state="readonly")
        self.plant_cb.pack(side="left", padx=5)
        self.plant_cb.bind("<<ComboboxSelected>>", lambda e: self.on_filter_change())

        ttk.Label(filter_bar, text="Detail:").pack(side="left", padx=15)
        self.period_var = tk.StringVar(value="Month")
        self.period_cb = ttk.Combobox(filter_bar, textvariable=self.period_var, values=["Day", "Week", "Month", "Quarter", "Year"], width=10, state="readonly")
        self.period_cb.pack(side="left", padx=5)
        self.period_cb.bind("<<ComboboxSelected>>", lambda e: self.on_filter_change())

        # Main Content Area
        self.content_container = ttk.Frame(self, style="Content.TFrame")
        self.content_container.pack(fill="both", expand=True, pady=10)
        
        self.switch_view()

    def populate_initial_data(self):
        years = [str(y["year"]) for y in db_retriever.get_distinct_years() if y["year"] is not None]
        all_years = sorted(list(set(years + [str(datetime.datetime.now().year)])), reverse=True)
        
        self.year_menu.delete(0, "end")
        for y in all_years:
            if y not in self.selected_years:
                is_current = (y == str(datetime.datetime.now().year))
                self.selected_years[y] = tk.BooleanVar(value=is_current)
            self.year_menu.add_checkbutton(label=y, variable=self.selected_years[y], command=self.on_filter_change)
        
        self._update_year_mb_text()
        
        plants = db_retriever.get_all_plants()
        self.res_plants_map = {p["name"]: p["id"] for p in plants}
        
        if self.view_mode.get() == "single":
            p_list = list(self.res_plants_map.keys())
            self.plant_cb["values"] = p_list
            if self.plant_var.get() == "All Plants" or not self.plant_var.get():
                if p_list: self.plant_var.set(p_list[0])
        else:
            self.plant_cb["values"] = ["All Plants"] + list(self.res_plants_map.keys())
            if not self.plant_var.get(): self.plant_var.set("All Plants")

    def _update_year_mb_text(self):
        active = [y for y, v in self.selected_years.items() if v.get()]
        if not active: self.year_mb.config(text="None Selected")
        elif len(active) == 1: self.year_mb.config(text=active[0])
        else: self.year_mb.config(text=f"{len(active)} Years")

    def on_filter_change(self):
        self._update_year_mb_text()
        if self.view_mode.get() == "single":
            self.load_kpi_hierarchy()
            self.update_single_view()
        else:
            self.load_global_dashboard()

    def switch_view(self):
        self._last_loaded_plant_id = -1
        for w in self.content_container.winfo_children(): w.destroy()
        self.populate_initial_data()

        if self.view_mode.get() == "single":
            self._create_single_layout()
            self.load_kpi_hierarchy()
        else:
            self._create_global_layout()
            self.load_global_dashboard()

    def _create_single_layout(self):
        pane = ttk.PanedWindow(self.content_container, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=10)

        tree_f = ttk.Frame(pane, style="Card.TFrame")
        pane.add(tree_f, weight=1)
        self.kpi_tree = ttk.Treeview(tree_f, show="tree", selectmode="browse")
        self.kpi_tree.pack(fill="both", expand=True)
        self.kpi_tree.bind("<<TreeviewSelect>>", lambda e: self.update_single_view())

        detail_f = ttk.Frame(pane, style="Content.TFrame")
        pane.add(detail_f, weight=4)

        # Dynamic columns for table based on targets? 
        # For UI simplicity we'll use generic Target labels if more than 2
        self.table = ttk.Treeview(detail_f, columns=("Y", "P", "T1", "T2", "T3+"), show="headings", height=8)
        self.table.heading("Y", text="Year"); self.table.column("Y", width=60)
        self.table.heading("P", text="Period")
        self.table.heading("T1", text=self.target1_display_name)
        self.table.heading("T2", text=self.target2_display_name)
        self.table.heading("T3+", text="Other Targets")
        self.table.pack(fill="x", padx=10, pady=5)

        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=detail_f)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=5)

    def load_kpi_hierarchy(self):
        p_name = self.plant_var.get()
        p_id = self.res_plants_map.get(p_name)
        if self._last_loaded_plant_id == p_id and self.kpi_tree.get_children(): return

        for item in self.kpi_tree.get_children(): self.kpi_tree.delete(item)
        kpis = db_retriever.get_all_kpis_detailed(only_visible=True, plant_id=p_id)
        
        hierarchy = {}
        for k_row in kpis:
            k = dict(k_row)
            path = k.get('hierarchy_path', 'No Group')
            parts = path.split(' > ')
            g = parts[0]; sg = parts[1] if len(parts) > 1 else 'Default'
            if g not in hierarchy: hierarchy[g] = {}
            if sg not in hierarchy[g]: hierarchy[g][sg] = []
            hierarchy[g][sg].append(k)

        for g in sorted(hierarchy.keys()):
            gid = self.kpi_tree.insert("", "end", text=f"📁 {g}", open=True)
            for sg in sorted(hierarchy[g].keys()):
                sgid = self.kpi_tree.insert(gid, "end", text=f"📂 {sg}")
                for k in hierarchy[g][sg]:
                    self.kpi_tree.insert(sgid, "end", iid=f"KPI_{k['id']}", text=f"📊 {k['indicator_name']}", values=(k['id'],))
        self._last_loaded_plant_id = p_id

    def update_single_view(self):
        sel = self.kpi_tree.selection()
        if not sel or not sel[0].startswith("KPI_"): return
        
        kpi_id = int(sel[0].split("_")[1])
        years = [int(y) for y, v in self.selected_years.items() if v.get()]
        p_id = self.res_plants_map.get(self.plant_var.get())
        period_type = self.period_var.get()

        if not p_id or not years: return

        self.ax.clear()
        for i in self.table.get_children(): self.table.delete(i)
        
        all_periods = set()
        # structure: {year: {target_num: {period: val}}}
        data_tree = {}

        for year in sorted(years):
            data_tree[year] = {}
            # Find available target numbers for this KPI/Year
            t_nums = db_retriever.get_available_target_numbers_for_kpi(year, p_id, kpi_id)
            if not t_nums: t_nums = [1, 2] # Fallback
            
            for tn in t_nums:
                res = db_retriever.get_periodic_targets_for_kpi(year, p_id, kpi_id, period_type, tn)
                data_tree[year][tn] = {r["period"]: r["Target"] for r in res}
                all_periods.update(data_tree[year][tn].keys())

        sorted_all_ps = self._sort_periods(list(all_periods), period_type)

        # Update Table
        for year in sorted(years, reverse=True):
            for p in sorted_all_ps:
                row_vals = [year, self._format_period(p, period_type)]
                # Add T1, T2, and sum of others
                t1 = data_tree[year].get(1, {}).get(p, 0)
                t2 = data_tree[year].get(2, {}).get(p, 0)
                others = sum(data_tree[year].get(tn, {}).get(p, 0) for tn in data_tree[year].keys() if tn > 2)
                
                # Check if any target has data for this year/period
                has_any = any(p in data_tree[year].get(tn, {}) for tn in data_tree[year].keys())
                if has_any:
                    self.table.insert("", "end", values=(year, self._format_period(p, period_type), f"{t1:,.2f}", f"{t2:,.2f}", f"{others:,.2f}"))

        # Update Plot
        colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
        c_idx = 0
        for year in sorted(years):
            t_nums = sorted(data_tree[year].keys())
            for tn in t_nums:
                y_map = data_tree[year][tn]
                # Filter periods present for THIS specific target
                y_ps = [p for p in sorted_all_ps if p in y_map]
                if not y_ps: continue
                
                x_indices = [sorted_all_ps.index(p) for p in y_ps]
                y_vals = [y_map[p] for p in y_ps]
                
                label = f"{year} T{tn}"
                if tn == 1: label = f"{year} {self.target1_display_name}"
                elif tn == 2: label = f"{year} {self.target2_display_name}"
                
                style = "-" if tn == 1 else "--"
                marker = "o" if tn == 1 else "x"
                
                self.ax.plot(x_indices, y_vals, marker=marker, linestyle=style, label=label, color=colors[c_idx % len(colors)])
                c_idx += 1
        
        if period_type == "Day" and len(sorted_all_ps) > 31:
            step = max(1, len(sorted_all_ps) // 10)
            indices = range(0, len(sorted_all_ps), step)
            self.ax.set_xticks(indices)
            self.ax.set_xticklabels([self._format_period(sorted_all_ps[i], period_type) for i in indices], rotation=45, ha="right")
        else:
            self.ax.set_xticks(range(len(sorted_all_ps)))
            self.ax.set_xticklabels([self._format_period(p, period_type) for p in sorted_all_ps], rotation=45, ha="right")
            
        self.ax.legend(fontsize=8); self.ax.grid(True, alpha=0.3)
        self.fig.tight_layout()
        self.canvas.draw()

    def _create_global_layout(self):
        container = ttk.Frame(self.content_container, style="Card.TFrame")
        container.pack(fill="both", expand=True, padx=10)
        self.canvas_g = tk.Canvas(container, background="#FFFFFF", highlightthickness=0)
        self.canvas_g.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(container, orient="vertical", command=self.canvas_g.yview)
        sb.pack(side="right", fill="y")
        self.canvas_g.configure(yscrollcommand=sb.set)
        self.scroll_f = ttk.Frame(self.canvas_g, style="Card.TFrame")
        self.win_g = self.canvas_g.create_window((0, 0), window=self.scroll_f, anchor="nw")
        
        self.scroll_f.bind("<Configure>", lambda e: self.canvas_g.configure(scrollregion=self.canvas_g.bbox("all")))
        container.bind("<Configure>", lambda e: self.canvas_g.itemconfig(self.win_g, width=e.width))

    def load_global_dashboard(self):
        for w in self.scroll_f.winfo_children(): w.destroy()
        years = [int(y) for y, v in self.selected_years.items() if v.get()]
        p_id = self.res_plants_map.get(self.plant_var.get())
        period_type = self.period_var.get()

        kpis = db_retriever.get_all_kpis_detailed(only_visible=True)
        for k_row in kpis:
            k = dict(k_row)
            all_df_data = []
            for year in years:
                data = db_retriever.get_periodic_targets_for_kpi_all_plants(k["id"], period_type, year)
                all_df_data.extend([dict(row) for row in data])
            
            if not all_df_data: continue
            df = pd.DataFrame(all_df_data)
            if p_id: df = df[df['plant_id'] == p_id]
            if df.empty: continue

            card = ttk.LabelFrame(self.scroll_f, text=get_kpi_display_name(k), style="Card.TLabelframe", padding=10)
            card.pack(fill="x", padx=10, pady=10)
            fig = Figure(figsize=(8, 3), dpi=90); ax = fig.add_subplot(111)
            
            # Segregate by both plant AND target number
            df['series_label'] = df.apply(lambda x: f"{x['plant_name']} (T{x['target_number']})", axis=1)
            df['period_label'] = df.apply(lambda x: f"{x['year']}-{self._format_period(x['period'], period_type)}", axis=1)
            
            df = self._sort_dashboard_df(df, period_type)
            unique_labels = df['period_label'].unique()
            l_map = {l: i for i, l in enumerate(unique_labels)}
            
            for label in df['series_label'].unique():
                pdf = df[df['series_label'] == label]
                ax.plot([l_map[l] for l in pdf['period_label']], pdf['target_value'], marker="o", label=label)
            
            ax.set_xticks(range(len(unique_labels)))
            ax.set_xticklabels(unique_labels, rotation=45, ha="right", fontsize=8)
            ax.legend(fontsize=7, loc='upper left', bbox_to_anchor=(1, 1)); ax.grid(True, alpha=0.2)
            fig.tight_layout()
            canvas = FigureCanvasTkAgg(fig, master=card)
            canvas.get_tk_widget().pack(fill="x")

    def _format_period(self, p, p_type):
        if p_type == "Month": return calendar.month_name[int(p)] if str(p).isdigit() else p
        return str(p)

    def _sort_periods(self, periods, p_type):
        try:
            if p_type == "Month":
                m_map = {m: i for i, m in enumerate(list(calendar.month_name)[1:], 1)}
                # periods could be strings like "January" or integers like 1
                def get_m_idx(val):
                    if str(val).isdigit(): return int(val)
                    return m_map.get(val, 0)
                return sorted(periods, key=get_m_idx)
            return sorted(periods)
        except: return sorted(periods)

    def _sort_dashboard_df(self, df, p_type):
        if p_type == "Month":
            m_map = {m: i for i, m in enumerate(list(calendar.month_name)[1:], 1)}
            df['s'] = df['period'].apply(lambda x: m_map.get(x, 0) if not str(x).isdigit() else int(x))
            return df.sort_values(['year', 's']).drop('s', axis=1)
        return df.sort_values(['year', 'period'])
