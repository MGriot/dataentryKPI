# src/interfaces/tkinter_app/dialogs/advanced_split_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
from src.services import split_analyzer
from src import data_retriever

class AdvancedSplitDialog(tk.Toplevel):
    def __init__(self, parent, title="Advanced Multivariate Seasonality Analysis"):
        super().__init__(parent)
        self.title(title)
        self.geometry("800x700")
        self.result_weights = None
        self.result_target_kpi_ids = []
        
        self.file_path = tk.StringVar()
        self.columns = []
        
        self._setup_ui()
        self.transient(parent)
        self.grab_set()

    def _setup_ui(self):
        main = ttk.Frame(self, padding=20)
        main.pack(fill="both", expand=True)
        
        # 1. File Selection
        f_frame = ttk.LabelFrame(main, text="1. Data Source (CSV/XLSX)", padding=10)
        f_frame.pack(fill="x", pady=5)
        
        ttk.Entry(f_frame, textvariable=self.file_path, width=60).pack(side="left", padx=5)
        ttk.Button(f_frame, text="Browse...", command=self._browse_file).pack(side="left")
        
        # 2. Mapping & Features (Two Column Layout)
        map_cols = ttk.Frame(main)
        map_cols.pack(fill="both", expand=True, pady=10)
        
        # 2a. Mapping (Left)
        left_f = ttk.LabelFrame(map_cols, text="2. Column Mapping", padding=10)
        left_f.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        ttk.Label(left_f, text="Historical Target Column:").grid(row=0, column=0, sticky="w", pady=2)
        self.ind_col_var = tk.StringVar()
        self.ind_col_cb = ttk.Combobox(left_f, textvariable=self.ind_col_var, state="readonly")
        self.ind_col_cb.grid(row=0, column=1, sticky="ew", padx=5)
        
        ttk.Label(left_f, text="Date/Period Column:").grid(row=1, column=0, sticky="w", pady=2)
        self.date_col_var = tk.StringVar()
        self.date_col_cb = ttk.Combobox(left_f, textvariable=self.date_col_var, state="readonly")
        self.date_col_cb.grid(row=1, column=1, sticky="ew", padx=5)
        
        ttk.Label(left_f, text="Analyze Period as:").grid(row=2, column=0, sticky="w", pady=2)
        self.period_var = tk.StringVar(value="Month")
        ttk.Combobox(left_f, textvariable=self.period_var, values=["Month", "Quarter", "Week", "Day"], state="readonly").grid(row=2, column=1, sticky="ew", padx=5)
        
        ttk.Label(left_f, text="ℹ️ 'Period' defines the time bucket (e.g. Month)\ninto which your data will be aggregated.", font=("Helvetica", 8, "italic"), foreground="#666").grid(row=3, column=0, columnspan=2, pady=10)
        
        left_f.columnconfigure(1, weight=1)
        
        # 2b. Features (Right)
        right_f = ttk.LabelFrame(map_cols, text="3. Multivariate Features", padding=10)
        right_f.pack(side="left", fill="both", expand=True, padx=(5, 0))
        
        ttk.Label(right_f, text="Select feature columns to correlate:").pack(anchor="w")
        self.features_lb = tk.Listbox(right_f, selectmode="multiple", height=6)
        self.features_lb.pack(fill="both", expand=True, pady=5)
        
        # 3. Target KPIs (Bottom)
        target_f = ttk.LabelFrame(main, text="4. Target KPIs (Apply this split to:)", padding=10)
        target_f.pack(fill="both", expand=True, pady=10)
        
        self.kpi_lb = tk.Listbox(target_f, selectmode="multiple", height=6)
        self.kpi_lb.pack(fill="both", expand=True, pady=5)
        self._populate_kpis()
        
        # 4. Preview/Run
        btn_f = ttk.Frame(main)
        btn_f.pack(fill="x", pady=10)
        
        ttk.Button(btn_f, text="🚀 Run Multivariate Analysis", command=self._run_analysis, style="Action.TButton").pack(side="top", fill="x")
        
        # Results area
        self.res_text = tk.Text(main, height=8, font=("Courier", 9), state="disabled", background="#F8F9FA")
        self.res_text.pack(fill="x", pady=10)
        
        # Footer
        footer = ttk.Frame(main)
        footer.pack(fill="x")
        ttk.Button(footer, text="Apply Weights & Selections", command=self._on_apply).pack(side="right", padx=5)
        ttk.Button(footer, text="Cancel", command=self.destroy).pack(side="right")

    def _browse_file(self):
        path = filedialog.askopenfilename(filetypes=[("Data files", "*.csv *.xlsx *.xls")])
        if path:
            self.file_path.set(path)
            try:
                df = pd.read_csv(path) if path.endswith('.csv') else pd.read_excel(path)
                self.columns = list(df.columns)
                self.ind_col_cb["values"] = self.columns
                self.date_col_cb["values"] = self.columns
                
                self.features_lb.delete(0, "end")
                for c in self.columns:
                    self.features_lb.insert("end", c)
                    
                if self.columns:
                    self.ind_col_var.set(self.columns[0])
                    self.date_col_var.set(self.columns[0])
            except Exception as e:
                messagebox.showerror("Error", f"Could not read file: {e}")

    def _populate_kpis(self):
        try:
            inds = sorted([dict(r) for r in data_retriever.get_all_kpi_indicators()], key=lambda x: x['name'])
            self.all_inds = inds
            for i in inds:
                self.kpi_lb.insert("end", f"{i['name']} [ID:{i['id']}]")
        except: pass

    def _run_analysis(self):
        if not self.file_path.get(): 
            messagebox.showwarning("Warning", "Please select a data file.")
            return
            
        feature_indices = self.features_lb.curselection()
        selected_features = [self.features_lb.get(i) for i in feature_indices]
        
        try:
            weights = split_analyzer.analyze_seasonality_from_file(
                self.file_path.get(),
                self.ind_col_var.get(),
                selected_features,
                self.date_col_var.get(),
                self.period_var.get()
            )
            self.result_weights = weights
            
            self.res_text.config(state="normal")
            self.res_text.delete("1.0", "end")
            self.res_text.insert("1.0", f"Multivariate Results ({len(selected_features)} features used):\n\n")
            for p, w in sorted(weights.items(), key=lambda x: int(x[0]) if x[0].isdigit() else x[0]):
                label = p
                if self.period_var.get() == "Month":
                    import calendar
                    try: label = calendar.month_name[int(p)]
                    except: pass
                self.res_text.insert("end", f"{label}: {w*100:.2f}%\n")
            self.res_text.config(state="disabled")
            
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            messagebox.showerror("Analysis Error", str(e))

    def _on_apply(self):
        if not self.result_weights:
            messagebox.showwarning("Warning", "Please run analysis first.")
            return
            
        # Get selected KPIs
        kpi_indices = self.kpi_lb.curselection()
        self.result_target_kpi_ids = []
        for idx in kpi_indices:
            text = self.kpi_lb.get(idx)
            iid = int(text.split("[ID:")[1].replace("]", ""))
            name = text.split(" [ID:")[0]
            self.result_target_kpi_ids.append({'indicator_id': iid, 'indicator_name': name, 'override': None})
            
        self.destroy()

    def get_result(self):
        return self.result_weights, self.result_target_kpi_ids
