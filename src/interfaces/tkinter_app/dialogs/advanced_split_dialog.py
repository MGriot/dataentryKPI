# src/interfaces/tkinter_app/dialogs/advanced_split_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
from src.services import split_analyzer

class AdvancedSplitDialog(tk.Toplevel):
    def __init__(self, parent, title="Advanced Seasonality Analysis"):
        super().__init__(parent)
        self.title(title)
        self.geometry("600x500")
        self.result_weights = None
        
        self.file_path = tk.StringVar()
        self.columns = []
        
        self._setup_ui()

    def _setup_ui(self):
        main = ttk.Frame(self, padding=20)
        main.pack(fill="both", expand=True)
        
        # 1. File Selection
        f_frame = ttk.LabelFrame(main, text="1. Data Source (CSV/XLSX)", padding=10)
        f_frame.pack(fill="x", pady=5)
        
        ttk.Entry(f_frame, textvariable=self.file_path, width=50).pack(side="left", padx=5)
        ttk.Button(f_frame, text="Browse...", command=self._browse_file).pack(side="left")
        
        # 2. Mapping
        self.m_frame = ttk.LabelFrame(main, text="2. Column Mapping", padding=10)
        self.m_frame.pack(fill="x", pady=10)
        
        ttk.Label(self.m_frame, text="Indicator/Target Column:").grid(row=0, column=0, sticky="w", pady=2)
        self.ind_col_var = tk.StringVar()
        self.ind_col_cb = ttk.Combobox(self.m_frame, textvariable=self.ind_col_var, state="readonly")
        self.ind_col_cb.grid(row=0, column=1, sticky="ew", padx=5)
        
        ttk.Label(self.m_frame, text="Date/Period Column:").grid(row=1, column=0, sticky="w", pady=2)
        self.date_col_var = tk.StringVar()
        self.date_col_cb = ttk.Combobox(self.m_frame, textvariable=self.date_col_var, state="readonly")
        self.date_col_cb.grid(row=1, column=1, sticky="ew", padx=5)
        
        ttk.Label(self.m_frame, text="Analyze Period as:").grid(row=2, column=0, sticky="w", pady=2)
        self.period_var = tk.StringVar(value="Month")
        ttk.Combobox(self.m_frame, textvariable=self.period_var, values=["Month", "Quarter", "Week", "Day"], state="readonly").grid(row=2, column=1, sticky="ew", padx=5)
        
        self.m_frame.columnconfigure(1, weight=1)
        
        # 3. Preview/Run
        btn_f = ttk.Frame(main)
        btn_f.pack(fill="x", pady=20)
        
        ttk.Button(btn_f, text="Analyze & Suggest Weights", command=self._run_analysis, style="Action.TButton").pack(side="top", fill="x")
        
        # Results area
        self.res_text = tk.Text(main, height=10, font=("Courier", 9), state="disabled")
        self.res_text.pack(fill="both", expand=True, pady=10)
        
        # Footer
        footer = ttk.Frame(main)
        footer.pack(fill="x")
        ttk.Button(footer, text="Apply Weights", command=self._on_apply).pack(side="right", padx=5)
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
                if self.columns:
                    self.ind_col_var.set(self.columns[0])
                    self.date_col_var.set(self.columns[0])
            except Exception as e:
                messagebox.showerror("Error", f"Could not read file: {e}")

    def _run_analysis(self):
        if not self.file_path.get(): return
        try:
            weights = split_analyzer.analyze_seasonality_from_file(
                self.file_path.get(),
                self.ind_col_var.get(),
                self.date_col_var.get(),
                self.period_var.get()
            )
            self.result_weights = weights
            
            self.res_text.config(state="normal")
            self.res_text.delete("1.0", "end")
            self.res_text.insert("1.0", "Suggested Seasonality Weights:\n\n")
            for p, w in sorted(weights.items(), key=lambda x: int(x[0]) if x[0].isdigit() else x[0]):
                self.res_text.insert("end", f"Period {p}: {w*100:.2f}%\n")
            self.res_text.config(state="disabled")
            
        except Exception as e:
            messagebox.showerror("Analysis Error", str(e))

    def _on_apply(self):
        if not self.result_weights:
            messagebox.showwarning("Warning", "Please run analysis first.")
            return
        self.destroy()

    def get_result(self):
        return self.result_weights
