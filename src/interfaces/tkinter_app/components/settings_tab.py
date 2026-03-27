import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
from src.config.settings import SETTINGS_FILE
from src.interfaces.common_ui import constants as const

class SettingsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.settings = self.app.settings
        self.calculation_constants = {}
        self.constant_vars = {}
        self.target_rows = []
        self.create_widgets()
        self.load_calculation_constants()

    def create_widgets(self):
        # Create a canvas and a scrollbar
        self.canvas = tk.Canvas(self, background="#F5F5F5", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        
        # Inner scrollable frame
        self.scrollable_frame = ttk.Frame(self.canvas, style="Content.TFrame")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        self.scrollbar.pack(side="right", fill="y")

        # --- Target Configuration ---
        targets_frame = ttk.LabelFrame(self.scrollable_frame, text="Target Configuration", style="Card.TLabelframe", padding=15)
        targets_frame.pack(fill='x', expand=True, pady=10, padx=5)

        ttk.Label(targets_frame, text="Define the targets available in the system. Default is 1.", font=("Helvetica", 9, "italic"), background="#FFFFFF").pack(anchor='w', pady=(0, 10))

        self.targets_list_frame = ttk.Frame(targets_frame, style="Card.TFrame")
        self.targets_list_frame.pack(fill='x', expand=True)

        self.load_targets_ui()

        btn_f = ttk.Frame(targets_frame, style="Card.TFrame")
        btn_f.pack(fill='x', pady=10)
        ttk.Button(btn_f, text="+ Add Target", command=self.add_target_row).pack(side='left', padx=5)

        # --- Database Path ---
        db_path_frame = ttk.LabelFrame(self.scrollable_frame, text="Database Path", style="Card.TLabelframe", padding=15)
        db_path_frame.pack(fill='x', expand=True, pady=10, padx=5)

        ttk.Label(db_path_frame, text="Database Folder:", background="#FFFFFF").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.db_path_var = tk.StringVar(value=self.settings.get('database_path', ''))
        ttk.Entry(db_path_frame, textvariable=self.db_path_var, width=50).grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ttk.Button(db_path_frame, text="Browse...", command=self.browse_db_path).grid(row=0, column=2, padx=5, pady=5)

        # --- Calculation Constants ---
        constants_frame = ttk.LabelFrame(self.scrollable_frame, text="Calculation Constants", style="Card.TLabelframe", padding=15)
        constants_frame.pack(fill='x', expand=True, pady=10, padx=5)
        
        self.constants_inner_frame = ttk.Frame(constants_frame, style="Card.TFrame")
        self.constants_inner_frame.pack(fill='both', expand=True)

        # --- Save Button ---
        save_button = ttk.Button(self.scrollable_frame, text="Save Settings", command=self.save_settings, style="Action.TButton")
        save_button.pack(pady=20, padx=5, anchor='e')

    def load_targets_ui(self):
        for row in self.target_rows:
            row['frame'].destroy()
        self.target_rows = []
        targets = self.settings.get('targets', [{"id": 1, "name": "Target"}])
        for t in targets:
            self._create_target_row(t['id'], t['name'])

    def _create_target_row(self, t_id, t_name):
        row_f = ttk.Frame(self.targets_list_frame, style="Card.TFrame")
        row_f.pack(fill='x', pady=2)

        ttk.Label(row_f, text="ID:", width=4, background="#FFFFFF").pack(side='left', padx=2)
        id_var = tk.StringVar(value=str(t_id))
        id_ent = ttk.Entry(row_f, textvariable=id_var, width=5)
        id_ent.pack(side='left', padx=2)

        ttk.Label(row_f, text="Name:", width=6, background="#FFFFFF").pack(side='left', padx=5)
        name_var = tk.StringVar(value=t_name)
        ent = ttk.Entry(row_f, textvariable=name_var, width=30)
        ent.pack(side='left', padx=5)

        row_obj = {'id_var': id_var, 'name_var': name_var, 'frame': row_f}
        btn = ttk.Button(row_f, text="Delete", width=8, command=lambda: self.delete_target_row(row_obj))
        btn.pack(side='left', padx=5)

        self.target_rows.append(row_obj)

    def add_target_row(self):
        ids = []
        for r in self.target_rows:
            try: ids.append(int(r['id_var'].get()))
            except: pass
        next_id = max(ids) + 1 if ids else 1
        self._create_target_row(next_id, f"Target {next_id}")

    def delete_target_row(self, row_obj):
        if len(self.target_rows) <= 1:
            messagebox.showwarning("Warning", "At least one target is required.")
            return
        row_obj['frame'].destroy()
        self.target_rows.remove(row_obj)

    def populate_constants_frame(self):
        for widget in self.constants_inner_frame.winfo_children():
            widget.destroy()
        self.constant_vars = {}
        row = 0
        for name, value in self.calculation_constants.items():
            ttk.Label(self.constants_inner_frame, text=f"{name}:", background="#FFFFFF").grid(row=row, column=0, padx=5, pady=2, sticky='w')
            var = tk.StringVar(value=str(value))
            ttk.Entry(self.constants_inner_frame, textvariable=var).grid(row=row, column=1, padx=5, pady=2, sticky='ew')
            self.constant_vars[name] = var
            row += 1

    def load_calculation_constants(self):
        try:
            with open('user_constants.json', 'r') as f:
                self.calculation_constants = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.calculation_constants = {
                'WEIGHT_INITIAL_FACTOR_INC': const.WEIGHT_INITIAL_FACTOR_INC,
                'WEIGHT_FINAL_FACTOR_INC': const.WEIGHT_FINAL_FACTOR_INC,
                'WEIGHT_INITIAL_FACTOR_AVG': const.WEIGHT_INITIAL_FACTOR_AVG,
                'WEIGHT_FINAL_FACTOR_AVG': const.WEIGHT_FINAL_FACTOR_AVG,
                'SINE_AMPLITUDE_INCREMENTAL': const.SINE_AMPLITUDE_INCREMENTAL,
                'SINE_AMPLITUDE_MEDIA': const.SINE_AMPLITUDE_MEDIA,
                'SINE_PHASE_OFFSET': const.SINE_PHASE_OFFSET,
                'WEEKDAY_BIAS_FACTOR_INCREMENTAL': const.WEEKDAY_BIAS_FACTOR_INCREMENTAL,
                'WEEKDAY_BIAS_FACTOR_MEDIA': const.WEEKDAY_BIAS_FACTOR_MEDIA,
                'DEVIATION_SCALE_FACTOR_AVG': const.DEVIATION_SCALE_FACTOR_AVG,
            }
        self.populate_constants_frame()

    def browse_db_path(self):
        path = tk.filedialog.askdirectory()
        if path:
            self.db_path_var.set(path)

    def save_settings(self):
        new_targets = []
        seen_ids = set()
        for row in self.target_rows:
            try:
                tid = int(row['id_var'].get().strip())
                if tid in seen_ids:
                    messagebox.showerror("Error", f"Duplicate Target ID: {tid}")
                    return
                seen_ids.add(tid)
                new_targets.append({
                    'id': tid,
                    'name': row['name_var'].get().strip() or f"Target {tid}"
                })
            except ValueError:
                messagebox.showerror("Error", "Target ID must be a number.")
                return

        try:
            current_settings = {}
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    current_settings = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                pass

            current_settings['targets'] = new_targets
            current_settings['database_path'] = self.db_path_var.get()
            
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(current_settings, f, indent=4)
            
            new_constants = {}
            for name, var in self.constant_vars.items():
                try:
                    new_constants[name] = float(var.get())
                except ValueError:
                    messagebox.showerror("Error", f"Invalid value for {name}. Please enter a number.")
                    return
            
            with open('user_constants.json', 'w') as f:
                json.dump(new_constants, f, indent=4)

            self.calculation_constants = new_constants
            self.settings.update(current_settings)

            messagebox.showinfo("Success", "Settings saved successfully.")
            self.app.load_settings()
        except Exception as e:
            messagebox.showerror("Error", f"Could not save settings: {e}")
