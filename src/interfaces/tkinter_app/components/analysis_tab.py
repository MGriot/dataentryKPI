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

        self.create_widgets()

    def create_widgets(self):
        # View Switcher
        mode_frame = ttk.Frame(self, style="Content.TFrame")
        mode_frame.pack(fill="x", pady=5)
        ttk.Radiobutton(mode_frame, text="Single KPI Focus", variable=self.view_mode, value="single", command=self.switch_view).pack(side="left", padx=20)
        ttk.Radiobutton(mode_frame, text="Global Overview", variable=self.view_mode, value="global", command=self.switch_view).pack(side="left", padx=20)

        # Global Filters (Year, Plant, Detail)
        filter_bar = ttk.Frame(self, style="Content.TFrame", padding=(20, 0))
        filter_bar.pack(fill="x")

        ttk.Label(filter_bar, text="Year:").pack(side="left", padx=5)
        self.year_var = tk.StringVar(value=str(datetime.datetime.now().year))
        self.year_cb = ttk.Combobox(filter_bar, textvariable=self.year_var, width=8, state="readonly")
        self.year_cb.pack(side="left", padx=5)
        self.year_cb.bind("<<ComboboxSelected>>", lambda e: self.on_filter_change())

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

        # Main Content Area (Paned)
        self.content_container = ttk.Frame(self, style="Content.TFrame")
        self.content_container.pack(fill="both", expand=True, pady=10)
        
        self.switch_view()

    def populate_initial_data(self):
        years = [str(y["year"]) for y in db_retriever.get_distinct_years() if y["year"] is not None]
        self.year_cb["values"] = sorted(list(set(years + [str(datetime.datetime.now().year)])), reverse=True)
        
        plants = db_retriever.get_all_plants()
        self.res_plants_map = {p["name"]: p["id"] for p in plants}
        self.plant_cb["values"] = ["All Plants"] + list(self.res_plants_map.keys())
        if not self.plant_var.get(): self.plant_var.set("All Plants")

    def on_filter_change(self):
        if self.view_mode.get() == "single":
            self.load_kpi_hierarchy()
            self.update_single_view()
        else:
            self.load_global_dashboard()

    def switch_view(self):
        for w in self.content_container.winfo_children(): w.destroy()
        self.populate_initial_data()

        if self.view_mode.get() == "single":
            self._create_single_layout()
            self.load_kpi_hierarchy()
        else:
            self._create_global_layout()
            self.load_global_dashboard()

    # --- Single View Layout ---
    def _create_single_layout(self):
        pane = ttk.PanedWindow(self.content_container, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=10)

        # Left: Tree
        tree_f = ttk.Frame(pane, style="Card.TFrame")
        pane.add(tree_f, weight=1)
        
        self.kpi_tree = ttk.Treeview(tree_f, show="tree", selectmode="browse")
        self.kpi_tree.pack(fill="both", expand=True)
        self.kpi_tree.bind("<<TreeviewSelect>>", lambda e: self.update_single_view())

        # Right: Data
        detail_f = ttk.Frame(pane, style="Content.TFrame")
        pane.add(detail_f, weight=4)

        # Top: Table
        self.table = ttk.Treeview(detail_f, columns=("P", "T1", "T2"), show="headings", height=8)
        self.table.heading("P", text="Period"); self.table.heading("T1", text=self.target1_display_name); self.table.heading("T2", text=self.target2_display_name)
        self.table.pack(fill="x", padx=10, pady=5)

        # Bottom: Chart
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=detail_f)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=5)

    def load_kpi_hierarchy(self):
        for item in self.kpi_tree.get_children(): self.kpi_tree.delete(item)
        
        p_name = self.plant_var.get()
        p_id = self.res_plants_map.get(p_name)
        
        kpis = db_retriever.get_all_kpis_detailed(only_visible=True, plant_id=p_id)
        
        hierarchy = {}
        for k_row in kpis:
            k = dict(k_row)
            path = k.get('hierarchy_path', 'No Group')
            parts = path.split(' > ')
            
            # Simple 2-level hierarchy for now
            g = parts[0]
            sg = parts[1] if len(parts) > 1 else 'Default'
            
            if g not in hierarchy: hierarchy[g] = {}
            if sg not in hierarchy[g]: hierarchy[g][sg] = []
            hierarchy[g][sg].append(k)

        for g in sorted(hierarchy.keys(), key=lambda x: str(x) if x is not None else ""):
            gid = self.kpi_tree.insert("", "end", text=f"📁 {g}", open=True)
            for sg in sorted(hierarchy[g].keys(), key=lambda x: str(x) if x is not None else ""):
                sgid = self.kpi_tree.insert(gid, "end", text=f"📂 {sg}")
                for k in hierarchy[g][sg]:
                    self.kpi_tree.insert(sgid, "end", iid=f"KPI_{k['id']}", text=f"📊 {k['indicator_name']}", values=(k['id'],))

    def update_single_view(self):
        sel = self.kpi_tree.selection()
        if not sel or not sel[0].startswith("KPI_"): return
        
        kpi_id = int(sel[0].split("_")[1])
        year = int(self.year_var.get())
        p_name = self.plant_var.get()
        p_id = self.res_plants_map.get(p_name)
        period_type = self.period_var.get()

        if not p_id: 
            messagebox.showwarning("Selection", "Please select a specific plant for single KPI analysis.")
            return

        # Fetch Data
        t1 = db_retriever.get_periodic_targets_for_kpi(year, p_id, kpi_id, period_type, 1)
        t2 = db_retriever.get_periodic_targets_for_kpi(year, p_id, kpi_id, period_type, 2)
        
        map1 = {r["Period"]: r["Target"] for r in t1}
        map2 = {r["Period"]: r["Target"] for r in t2}
        periods = self._sort_periods(list(set(list(map1.keys()) + list(map2.keys()))), period_type)

        # Update Table
        for i in self.table.get_children(): self.table.delete(i)
        for p in periods:
            v1, v2 = map1.get(p, 0), map2.get(p, 0)
            self.table.insert("", "end", values=(self._format_period(p, period_type), f"{v1:,.2f}", f"{v2:,.2f}"))

        # Update Plot
        self.ax.clear()
        self.ax.plot(range(len(periods)), [map1.get(p, 0) for p in periods], marker="o", label=self.target1_display_name)
        self.ax.plot(range(len(periods)), [map2.get(p, 0) for p in periods], marker="x", linestyle="--", label=self.target2_display_name)
        self.ax.set_xticks(range(len(periods)))
        self.ax.set_xticklabels([self._format_period(p, period_type) for p in periods], rotation=45, ha="right")
        self.ax.legend(); self.ax.grid(True, alpha=0.3)
        self.fig.tight_layout()
        self.canvas.draw()

    # --- Global View Layout ---
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
        
        year_str = self.year_var.get()
        year = int(year_str) if year_str != "All" else None
        p_name = self.plant_var.get()
        p_id = self.res_plants_map.get(p_name)
        period_type = self.period_var.get()

        kpis = db_retriever.get_all_kpis_detailed(only_visible=True)
        for k_row in kpis:
            k = dict(k_row)
            data = db_retriever.get_periodic_targets_for_kpi_all_plants(k["id"], period_type, year)
            if not data: continue
            
            df = pd.DataFrame([dict(row) for row in data])
            if p_id: df = df[df['plant_id'] == p_id]
            if df.empty: continue

            card = ttk.LabelFrame(self.scroll_f, text=get_kpi_display_name(k), style="Card.TLabelframe", padding=10)
            card.pack(fill="x", padx=10, pady=10)

            fig = Figure(figsize=(8, 3), dpi=90); ax = fig.add_subplot(111)
            
            # Use timeline labels if multiple years
            is_all = (year_str == "All")
            if is_all: df['label'] = df.apply(lambda x: f"{x['year']}-{self._format_period(x['period'], period_type)}", axis=1)
            else: df['label'] = df['period'].apply(lambda x: self._format_period(x, period_type))
            
            df = self._sort_dashboard_df(df, period_type)
            unique_labels = df['label'].unique()
            l_map = {l: i for i, l in enumerate(unique_labels)}

            for name, p_data in df.groupby('plant_name'):
                color = self._get_color(name)
                for tn, m in [(1, 'o'), (2, 'x')]:
                    sub = p_data[p_data['target_number'] == tn]
                    if not sub.empty:
                        ax.plot([l_map[l] for l in sub['label']], sub['target_value'], marker=m, label=f"{name} T{tn}", color=color)

            ax.set_xticks(range(len(unique_labels))); ax.set_xticklabels(unique_labels, rotation=45, ha="right", fontsize=8)
            ax.grid(True, alpha=0.2); ax.legend(fontsize=7, loc='upper right', bbox_to_anchor=(1.1, 1))
            fig.tight_layout()
            FigureCanvasTkAgg(fig, master=card).get_tk_widget().pack(fill="both")

    # --- Helpers ---
    def _get_color(self, name):
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
        if not hasattr(self, '_c_map'): self._get_color_map = {}
        if name not in self._get_color_map: self._get_color_map[name] = colors[len(self._get_color_map) % len(colors)]
        return self._get_color_map[name]

    def _format_period(self, p, pt):
        if pt == 'Day' and p:
            try: return datetime.datetime.strptime(p, '%Y-%m-%d').strftime('%d/%m')
            except: return p
        return p

    def _sort_periods(self, periods, pt):
        if pt == 'Month':
            m_map = {m: i for i, m in enumerate(list(calendar.month_name)[1:])}
            return sorted(periods, key=lambda x: m_map.get(x, 0) if x is not None else 0)
        if pt == 'Day': return sorted(periods, key=lambda x: str(x) if x is not None else "")
        return sorted(periods, key=lambda x: str(x) if x is not None else "")

    def _sort_dashboard_df(self, df, pt):
        if pt == 'Month':
            m_map = {m: i for i, m in enumerate(list(calendar.month_name)[1:])}
            df['s'] = df['period'].map(m_map)
            return df.sort_values(['year', 's']).drop('s', axis=1)
        return df.sort_values(['year', 'period'])
