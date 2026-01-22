import tkinter as tk
from tkinter import ttk, colorchooser, messagebox, filedialog
import json
from src import data_retriever as db_retriever
from src.plants_management import crud as plants_manager
from src.config.settings import SETTINGS_FILE
from src.interfaces.common_ui import constants as const

class SettingsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.settings = self.app.settings
        self.calculation_constants = {}
        self.constant_vars = {}
        self.create_widgets()
        self.load_calculation_constants()

    def create_widgets(self):
        # Create a canvas and a scrollbar
        self.canvas = tk.Canvas(self, background="#F5F5F5", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        
        # Inner scrollable frame - styled to match background or card
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

        # --- Display Names ---
        display_names_frame = ttk.LabelFrame(self.scrollable_frame, text="Display Names", style="Card.TLabelframe", padding=15)
        display_names_frame.pack(fill='x', expand=True, pady=10, padx=5)

        ttk.Label(display_names_frame, text="Target 1:", background="#FFFFFF").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.target1_name_var = tk.StringVar(value=self.settings.get('display_names', {}).get('target1', 'Target 1'))
        ttk.Entry(display_names_frame, textvariable=self.target1_name_var).grid(row=0, column=1, padx=5, pady=5, sticky='ew')

        ttk.Label(display_names_frame, text="Target 2:", background="#FFFFFF").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        self.target2_name_var = tk.StringVar(value=self.settings.get('display_names', {}).get('target2', 'Target 2'))
        ttk.Entry(display_names_frame, textvariable=self.target2_name_var).grid(row=1, column=1, padx=5, pady=5, sticky='ew')

        # --- Database Path ---
        db_path_frame = ttk.LabelFrame(self.scrollable_frame, text="Database Path", style="Card.TLabelframe", padding=15)
        db_path_frame.pack(fill='x', expand=True, pady=10, padx=5)

        ttk.Label(db_path_frame, text="Database Folder:", background="#FFFFFF").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.db_path_var = tk.StringVar(value=self.settings.get('database_path', ''))
        ttk.Entry(db_path_frame, textvariable=self.db_path_var).grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ttk.Button(db_path_frame, text="Browse...", command=self.browse_db_path).grid(row=0, column=2, padx=5, pady=5)

        # --- Calculation Constants ---
        constants_frame = ttk.LabelFrame(self.scrollable_frame, text="Calculation Constants", style="Card.TLabelframe", padding=15)
        constants_frame.pack(fill='x', expand=True, pady=10, padx=5)
        
        self.constants_inner_frame = ttk.Frame(constants_frame, style="Card.TFrame") # Inner frame matches white card
        self.constants_inner_frame.pack(fill='both', expand=True)
        self.populate_constants_frame()

        # --- Save Button ---
        save_button = ttk.Button(self.scrollable_frame, text="Save Settings", command=self.save_settings, style="Action.TButton")
        save_button.pack(pady=20, padx=5, anchor='e')

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

    

    def on_tab_selected(self):
        # This method is called when the tab is selected
        self.load_calculation_constants()

    def browse_db_path(self):
        path = tk.filedialog.askdirectory()
        if path:
            self.db_path_var.set(path)

    

    def save_settings(self):
        self.settings['display_names'] = {
            'target1': self.target1_name_var.get(),
            'target2': self.target2_name_var.get()
        }
        self.settings['database_path'] = self.db_path_var.get()

        try:
            # Load existing settings to merge, then update
            current_settings = {}
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    current_settings = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                pass # File doesn't exist or is empty, start with empty dict

            # Update only the sections managed by this tab
            current_settings['display_names'] = self.settings['display_names']
            current_settings['database_path'] = self.settings['database_path']
            
            

            with open(SETTINGS_FILE, 'w') as f:
                json.dump(current_settings, f, indent=4)
            
            # Save calculation constants
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

            messagebox.showinfo("Success", "Settings saved successfully.")
            self.app.load_settings() # Reload settings in the main app
        except Exception as e:
            messagebox.showerror("Error", f"Could not save settings: {e}")