# src/interfaces/tkinter_app/dialogs/advanced_split_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import calendar
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from src.services import split_analyzer
from src import data_retriever

class AdvancedSplitDialog(tk.Toplevel):
    def __init__(self, parent, title="Advanced Multivariate Seasonality Analysis"):
        super().__init__(parent)
        self.title(title)
        self.geometry("1200x900")
        self.result_weights = None
        self.result_target_kpi_ids = []
        
        self.file_path = tk.StringVar()
        self.columns = []
        
        self._setup_ui()
        self.transient(parent)
        self.grab_set()

    def _setup_ui(self):
        # Main Outer Container
        self.main_container = ttk.Frame(self, padding=10)
        self.main_container.pack(fill="both", expand=True)

        # 1. Header: File Selection
        header = ttk.LabelFrame(self.main_container, text="1. Data Source", padding=10)
        header.pack(fill="x", pady=(0, 10))
        
        file_f = ttk.Frame(header)
        file_f.pack(fill="x")
        ttk.Entry(file_f, textvariable=self.file_path, width=80).pack(side="left", padx=5)
        ttk.Button(file_f, text="Browse...", command=self._browse_file).pack(side="left")

        # 2. Workspace: Paned Window (Top: Configuration, Bottom: Results)
        self.workspace = ttk.PanedWindow(self.main_container, orient="vertical")
        self.workspace.pack(fill="both", expand=True)

        # --- Top Section: Configuration ---
        config_f = ttk.Frame(self.workspace)
        self.workspace.add(config_f, weight=2)

        config_tabs = ttk.Notebook(config_f)
        config_tabs.pack(fill="both", expand=True)

        # Tab 1: Data Preview
        self.preview_tab = ttk.Frame(config_tabs, padding=10)
        config_tabs.add(self.preview_tab, text="🔍 Data Preview")
        
        self.preview_tree = ttk.Treeview(self.preview_tab, show="headings", height=10)
        vsb = ttk.Scrollbar(self.preview_tab, orient="vertical", command=self.preview_tree.yview)
        hsb = ttk.Scrollbar(self.preview_tab, orient="horizontal", command=self.preview_tree.xview)
        self.preview_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.preview_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.preview_tab.grid_columnconfigure(0, weight=1)
        self.preview_tab.grid_rowconfigure(0, weight=1)

        # Tab 2: Mapping & Features
        mapping_tab = ttk.Frame(config_tabs, padding=10)
        config_tabs.add(mapping_tab, text="⚙️ Model Mapping & KPIs")

        map_grid = ttk.Frame(mapping_tab)
        map_grid.pack(fill="both", expand=True)

        # Grid: [Date/Period] [Targets] [Features] [KPIs]
        # Column 1: Date & Period
        c1 = ttk.Frame(map_grid, padding=5)
        c1.pack(side="left", fill="both", expand=True)
        ttk.Label(c1, text="Date Column:", font=("Helvetica", 9, "bold")).pack(anchor="w")
        self.date_col_var = tk.StringVar()
        self.date_col_cb = ttk.Combobox(c1, textvariable=self.date_col_var, state="readonly")
        self.date_col_cb.pack(fill="x", pady=(2, 10))
        
        ttk.Label(c1, text="Aggregation:", font=("Helvetica", 9, "bold")).pack(anchor="w")
        self.period_var = tk.StringVar(value="Month")
        ttk.Combobox(c1, textvariable=self.period_var, values=["Month", "Quarter", "Week", "Day"], state="readonly").pack(fill="x")

        # Column 2: Historical Targets
        c2 = ttk.Frame(map_grid, padding=5)
        c2.pack(side="left", fill="both", expand=True)
        ttk.Label(c2, text="Historical Targets:", font=("Helvetica", 9, "bold")).pack(anchor="w")
        self.target_cols_lb = tk.Listbox(c2, selectmode="multiple", height=8, exportselection=False)
        self.target_cols_lb.pack(fill="both", expand=True)
        ttk.Label(c2, text="💡 Ctrl+Click", font=("Helvetica", 8, "italic"), foreground="#666").pack(anchor="w")

        # Column 3: Multivariate Features
        c3 = ttk.Frame(map_grid, padding=5)
        c3.pack(side="left", fill="both", expand=True)
        ttk.Label(c3, text="Driver Features:", font=("Helvetica", 9, "bold")).pack(anchor="w")
        self.features_lb = tk.Listbox(c3, selectmode="multiple", height=8, exportselection=False)
        self.features_lb.pack(fill="both", expand=True)

        # Column 4: System KPIs
        c4 = ttk.Frame(map_grid, padding=5)
        c4.pack(side="left", fill="both", expand=True)
        ttk.Label(c4, text="Apply to KPIs:", font=("Helvetica", 9, "bold")).pack(anchor="w")
        self.kpi_lb = tk.Listbox(c4, selectmode="multiple", height=8, exportselection=False)
        self.kpi_lb.pack(fill="both", expand=True)
        self._populate_kpis()

        # Action Bar (Between Config and Results)
        action_bar = ttk.Frame(config_f, padding=(0, 10))
        action_bar.pack(fill="x")
        self.run_btn = ttk.Button(action_bar, text="🚀 RUN MULTIVARIATE ANALYSIS", command=self._run_analysis, style="Action.TButton")
        self.run_btn.pack(side="right", padx=10)

        # --- Bottom Section: Results ---
        results_f = ttk.LabelFrame(self.workspace, text="3. Analysis Results & Visualization", padding=10)
        self.workspace.add(results_f, weight=3)

        res_pane = ttk.PanedWindow(results_f, orient="horizontal")
        res_pane.pack(fill="both", expand=True)

        # Left: Text stats
        self.res_text = tk.Text(res_pane, width=45, font=("Courier New", 10), state="disabled", background="#F8F9FA")
        res_pane.add(self.res_text, weight=1)

        # Right: Plot
        self.plot_frame = ttk.Frame(res_pane)
        res_pane.add(self.plot_frame, weight=3)
        
        self.fig = Figure(figsize=(6, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # --- Fixed Footer ---
        footer = ttk.Frame(self.main_container, padding=(0, 10))
        footer.pack(fill="x", side="bottom")
        
        self.apply_btn = ttk.Button(footer, text="✅ Apply weights to selection", command=self._on_apply, state="disabled")
        self.apply_btn.pack(side="right", padx=5)
        ttk.Button(footer, text="Cancel", command=self.destroy).pack(side="right")

    def _browse_file(self):
        path = filedialog.askopenfilename(filetypes=[("Data files", "*.csv *.xlsx *.xls")])
        if path:
            self.file_path.set(path)
            try:
                # Same detection as service
                if path.endswith('.csv'):
                    try:
                        df = pd.read_csv(path)
                        if len(df.columns) <= 1: df = pd.read_csv(path, sep=';')
                    except:
                        df = pd.read_csv(path, sep=';')
                else:
                    df = pd.read_excel(path)
                
                self.columns = list(df.columns)
                self.date_col_cb["values"] = self.columns
                self.target_cols_lb.delete(0, "end")
                self.features_lb.delete(0, "end")
                
                for c in self.columns:
                    self.target_cols_lb.insert("end", c)
                    self.features_lb.insert("end", c)
                    
                if self.columns:
                    self.date_col_var.set(self.columns[0])
                
                self._update_preview(df)
                
            except Exception as e:
                messagebox.showerror("Error", f"Could not read file: {e}")

    def _update_preview(self, df):
        # Clear tree
        for i in self.preview_tree.get_children(): self.preview_tree.delete(i)
        
        self.preview_tree["columns"] = list(df.columns)
        for c in df.columns:
            self.preview_tree.heading(c, text=c)
            self.preview_tree.column(c, width=120, anchor="center")
            
        # Add first 100 rows
        for _, row in df.head(100).iterrows():
            self.preview_tree.insert("", "end", values=list(row))

    def _populate_kpis(self):
        try:
            inds = sorted([dict(r) for r in data_retriever.get_all_kpi_indicators()], key=lambda x: x['name'])
            for i in inds:
                self.kpi_lb.insert("end", f"{i['name']} [ID:{i['id']}]")
        except: pass

    def _run_analysis(self):
        if not self.file_path.get(): 
            messagebox.showwarning("Warning", "Please select a data file.")
            return
            
        target_indices = self.target_cols_lb.curselection()
        feature_indices = self.features_lb.curselection()
        
        selected_targets = [self.target_cols_lb.get(i) for i in target_indices]
        selected_features = [self.features_lb.get(i) for i in feature_indices]
        
        if not selected_targets:
            messagebox.showwarning("Warning", "Please select at least one Target Column.")
            return

        try:
            weights, coefficients, r_squared, plot_df, model_name = split_analyzer.analyze_seasonality_from_file(
                self.file_path.get(),
                selected_targets,
                selected_features,
                self.date_col_var.get(),
                self.period_var.get()
            )
            self.result_weights = weights
            self.apply_btn.config(state="normal")
            
            # Update Text Results
            self.res_text.config(state="normal")
            self.res_text.delete("1.0", "end")
            self.res_text.insert("1.0", f"--- ANALYSIS REPORT ---\n\n")
            self.res_text.insert("end", f"WINNING MODEL: {model_name}\n")
            self.res_text.insert("end", f"FIT QUALITY (R²): {r_squared:.4f}\n")
            self.res_text.insert("end", "-" * 30 + "\n\n")
            
            if coefficients:
                self.res_text.insert("end", "DRIVER INFLUENCE:\n")
                for feat, coef in coefficients.items():
                    if feat != "Intercept":
                        self.res_text.insert("end", f" • {feat:<20}: {coef:>8.3f}\n")
                self.res_text.insert("end", "\n")
            
            p_type = self.period_var.get()
            self.res_text.insert("end", f"SEASONAL WEIGHTS:\n")
            for p, w in sorted(weights.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else x[0]):
                label = str(p)
                if p_type == "Month":
                    try: label = calendar.month_name[int(p)]
                    except: pass
                self.res_text.insert("end", f" • {label:<15}: {w*100:>6.1f}%\n")
            self.res_text.config(state="disabled")

            # Update Plot
            self.ax.clear()
            # Shaded Confidence Interval (Monte Carlo)
            self.ax.fill_between(plot_df['period_idx'], plot_df['CI_Lower'], plot_df['CI_Upper'], color='red', alpha=0.1, label="90% Confidence Interval")
            
            self.ax.plot(plot_df['period_idx'], plot_df['Actual_Target'], 'bo-', linewidth=2, label="Actual History")
            self.ax.plot(plot_df['period_idx'], plot_df['Predicted_Fit'], 'r--', linewidth=2, label=f"Predicted ({model_name})")
            
            self.ax.set_title(f"Model Seasonality Fit (R²={r_squared:.2f})", fontsize=12, fontweight='bold')
            self.ax.set_xlabel(f"{p_type} Index", fontsize=10)
            self.ax.set_ylabel("Normalized Value", fontsize=10)
            self.ax.legend(fontsize=9, loc='upper right')
            self.ax.grid(True, alpha=0.3, linestyle=':')
            
            if p_type == "Month":
                self.ax.set_xticks(range(1, 13))
                self.ax.set_xticklabels([calendar.month_abbr[i] for i in range(1, 13)], fontsize=8)

            self.fig.tight_layout()
            self.canvas.draw()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Analysis Error", str(e))

    def _on_apply(self):
        if not self.result_weights:
            messagebox.showwarning("Warning", "Please run analysis first.")
            return
            
        kpi_indices = self.kpi_lb.curselection()
        if not kpi_indices:
            if not messagebox.askyesno("Confirm", "No system KPIs selected. Apply only to the current split?"):
                return

        self.result_target_kpi_ids = []
        for idx in kpi_indices:
            text = self.kpi_lb.get(idx)
            iid = int(text.split("[ID:")[1].replace("]", ""))
            name = text.split(" [ID:")[0]
            self.result_target_kpi_ids.append({'indicator_id': iid, 'indicator_name': name, 'override': None})
            
        self.destroy()

    def get_result(self):
        return self.result_weights, self.result_target_kpi_ids
