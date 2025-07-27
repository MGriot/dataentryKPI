import tkinter as tk
from tkinter import ttk, colorchooser, messagebox, filedialog
import json
import data_retriever as db_retriever
from stabilimenti_management import crud as stabilimenti_manager

from app_config import SETTINGS_FILE

class SettingsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.settings = self.app.settings
        self.create_widgets()

    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # --- Display Names ---
        display_names_frame = ttk.LabelFrame(main_frame, text="Nomi Visualizzati")
        display_names_frame.pack(fill='x', expand=True, pady=5)

        ttk.Label(display_names_frame, text="Target 1:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.target1_name_var = tk.StringVar(value=self.settings.get('display_names', {}).get('target1', 'Target 1'))
        ttk.Entry(display_names_frame, textvariable=self.target1_name_var).grid(row=0, column=1, padx=5, pady=5, sticky='ew')

        ttk.Label(display_names_frame, text="Target 2:").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        self.target2_name_var = tk.StringVar(value=self.settings.get('display_names', {}).get('target2', 'Target 2'))
        ttk.Entry(display_names_frame, textvariable=self.target2_name_var).grid(row=1, column=1, padx=5, pady=5, sticky='ew')

        # --- Database Path ---
        db_path_frame = ttk.LabelFrame(main_frame, text="Percorso Database")
        db_path_frame.pack(fill='x', expand=True, pady=5)

        ttk.Label(db_path_frame, text="Cartella Database:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.db_path_var = tk.StringVar(value=self.settings.get('database_path', ''))
        ttk.Entry(db_path_frame, textvariable=self.db_path_var).grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ttk.Button(db_path_frame, text="Sfoglia...", command=self.browse_db_path).grid(row=0, column=2, padx=5, pady=5)

        # --- Stabilimento Colors ---
        colors_frame = ttk.LabelFrame(main_frame, text="Colori Stabilimenti")
        colors_frame.pack(fill='x', expand=True, pady=5)

        self.stabilimento_colors_vars = {}
        self.colors_inner_frame = ttk.Frame(colors_frame)
        self.colors_inner_frame.pack(fill='both', expand=True)
        self.refresh_stabilimento_colors_display()

        # --- Save Button ---
        save_button = ttk.Button(main_frame, text="Salva Impostazioni", command=self.save_settings)
        save_button.pack(pady=10)

    def refresh_stabilimento_colors_display(self):
        # Clear existing widgets
        for widget in self.colors_inner_frame.winfo_children():
            widget.destroy()
        self.stabilimento_colors_vars = {} # Reset the dictionary

        stabilimenti = db_retriever.get_all_stabilimenti()
        for i, stabilimento in enumerate(stabilimenti):
            stabilimento_name = stabilimento['name']
            stabilimento_id = stabilimento['id']
            color = stabilimento['color'] if 'color' in stabilimento else '#000000'
            
            ttk.Label(self.colors_inner_frame, text=f"{stabilimento_name}:").grid(row=i, column=0, padx=5, pady=5, sticky='w')
            color_var = tk.StringVar(value=color)
            color_label = ttk.Label(self.colors_inner_frame, textvariable=color_var, background=color, width=10)
            color_label.grid(row=i, column=1, padx=5, pady=5, sticky='ew')
            ttk.Button(self.colors_inner_frame, text="Cambia...", command=lambda s_id=stabilimento_id, s_name=stabilimento_name, v=color_var, l=color_label: self.choose_color(s_id, s_name, v, l)).grid(row=i, column=2, padx=5, pady=5)
            self.stabilimento_colors_vars[stabilimento_id] = color_var

    def on_tab_selected(self):
        # This method is called when the tab is selected
        self.refresh_stabilimento_colors_display()

    def browse_db_path(self):
        path = tk.filedialog.askdirectory()
        if path:
            self.db_path_var.set(path)

    def choose_color(self, stabilimento_id, stabilimento_name, color_var, color_label):
        color_code = colorchooser.askcolor(title=f"Scegli colore per {stabilimento_name}")
        if color_code:
            color_hex = color_code[1]
            color_var.set(color_hex)
            color_label.config(background=color_hex)
            # Immediately save the color to the database
            try:
                stabilimenti_manager.update_stabilimento_color(stabilimento_id, color_hex)
                # No messagebox here, as it's a direct update and refresh will happen on tab change
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile salvare il colore per {stabilimento_name}: {e}")

    def save_settings(self):
        self.settings['display_names'] = {
            'target1': self.target1_name_var.get(),
            'target2': self.target2_name_var.get()
        }
        self.settings['database_path'] = self.db_path_var.get()
        # The stabilimento colors are now saved directly when chosen, so remove this line
        # self.settings['stabilimento_colors'] = {name: var.get() for name, var in self.stabilimento_colors_vars.items()}

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
            
            # Remove stabilimento_colors from settings.json if it exists
            if 'stabilimento_colors' in current_settings:
                del current_settings['stabilimento_colors']

            with open(SETTINGS_FILE, 'w') as f:
                json.dump(current_settings, f, indent=4)
            messagebox.showinfo("Successo", "Impostazioni salvate con successo.")
            self.app.load_settings() # Reload settings in the main app
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile salvare le impostazioni: {e}")
