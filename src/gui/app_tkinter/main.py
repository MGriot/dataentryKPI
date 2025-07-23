import tkinter as tk
from tkinter import ttk
import sys
from pathlib import Path

# Ensure the 'src' directory is in the Python path
src_path = Path(__file__).resolve().parents[2]
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

from db_core.setup import setup_databases
from gui.app_tkinter.components.stabilimenti_tab import StabilimentiTab
from gui.app_tkinter.components.kpi_hierarchy_tab import KpiHierarchyTab
from gui.app_tkinter.components.kpi_templates_tab import KpiTemplatesTab
from gui.app_tkinter.components.kpi_specs_tab import KpiSpecsTab
from gui.app_tkinter.components.master_sub_link_tab import MasterSubLinkTab
from gui.app_tkinter.components.target_entry_tab import TargetEntryTab
from gui.app_tkinter.components.export_tab import ExportTab
from gui.app_tkinter.components.results_tab import ResultsTab
from gui.app_tkinter.components.dashboard_tab import DashboardTab
from gui.app_tkinter.components.settings_tab import SettingsTab
from ..shared.constants import KPI_CALC_TYPE_OPTIONS
from app_config import SETTINGS, load_settings

class KpiApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestione Target KPI")
        self.geometry("1600x950")

        # Load settings
        self.settings = load_settings()

        # Configure styles first
        self.style = ttk.Style(self)
        self._configure_styles()

        # Then, setup database
        try:
            setup_databases()
        except Exception as e:
            print(f"Failed to setup databases: {e}")
            # Consider showing a messagebox and exiting

        # Set other app-level properties
        self.kpi_calc_type_options_tk = KPI_CALC_TYPE_OPTIONS

        # Now, create the UI components
        self._create_main_notebook()
        
        # Finally, refresh data
        self.refresh_all_data()

    def load_settings(self):
        self.settings = load_settings()
        # Here you could add logic to apply settings, e.g., update styles
        # For now, we just reload the data.
        self.refresh_all_data()

    def _configure_styles(self):
        style = self.style
        available_themes = style.theme_names()
        preferred_themes = ["clam", "alt", "default", "vista", "xpnative"]
        theme_set_successfully = False
        for theme_name_attempt in preferred_themes:
            if theme_name_attempt in available_themes:
                try:
                    style.theme_use(theme_name_attempt)
                    theme_set_successfully = True
                    print(f"Successfully set theme: {theme_name_attempt}")
                    break
                except tk.TclError:
                    print(f"Failed to set theme: {theme_name_attempt}, trying next.")
        if not theme_set_successfully:
            print("CRITICAL: No ttk theme could be explicitly set. Using system default.")

        style.configure("Accent.TButton", foreground="white", background="#007bff", font=("Calibri", 10))
        style.configure("Treeview.Heading", font=("Calibri", 10, "bold"))
        style.configure("TLabelframe.Label", font=("Calibri", 10, "bold"))

        # Define styles for different states of KPI target frames
        style.configure("Manual.TLabelframe.Label", background="#FFEBCC", foreground="black")
        style.configure("Formula.TLabelframe.Label", background="#D6EAF8", foreground="black")
        style.configure("Derived.TLabelframe.Label", background="#E0E0E0", foreground="black")

    def _create_main_notebook(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.target_entry_frame = TargetEntryTab(self.notebook, self)
        self.kpi_hierarchy_frame = KpiHierarchyTab(self.notebook, self)
        self.kpi_templates_frame = KpiTemplatesTab(self.notebook, self)
        self.kpi_specs_frame = KpiSpecsTab(self.notebook, self)
        self.master_sub_link_frame = MasterSubLinkTab(self.notebook, self)
        self.stabilimenti_frame = StabilimentiTab(self.notebook, self)
        self.export_frame = ExportTab(self.notebook, self)
        self.results_frame = ResultsTab(self.notebook, self)
        self.dashboard_frame = DashboardTab(self.notebook, self)
        self.settings_frame = SettingsTab(self.notebook, self)

        self.notebook.add(self.target_entry_frame, text="🎯 Inserimento Target")
        self.notebook.add(self.kpi_hierarchy_frame, text="🗂️ Gestione Gerarchia KPI")
        self.notebook.add(self.kpi_templates_frame, text="📋 Gestione Template Indicatori")
        self.notebook.add(self.kpi_specs_frame, text="⚙️ Gestione Specifiche KPI")
        self.notebook.add(self.master_sub_link_frame, text="🔗 Gestione Link Master/Sub")
        self.notebook.add(self.stabilimenti_frame, text="🏭 Gestione Stabilimenti")
        self.notebook.add(self.export_frame, text="📦 Esportazione Dati")
        self.notebook.add(self.results_frame, text="📈 Visualizzazione Risultati")
        self.notebook.add(self.dashboard_frame, text="📊 Dashboard Globale KPI")
        self.notebook.add(self.settings_frame, text="⚙️ Impostazioni")

        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

    def on_tab_changed(self, event):
        selected_tab = self.notebook.nametowidget(self.notebook.select())
        if hasattr(selected_tab, 'on_tab_selected'):
            selected_tab.on_tab_selected()


    def refresh_all_data(self):
        print("Refreshing all GUI data...")
        if hasattr(self.stabilimenti_frame, 'refresh_tree'):
            self.stabilimenti_frame.refresh_tree()
        if hasattr(self.kpi_hierarchy_frame, 'refresh_displays'):
            self.kpi_hierarchy_frame.refresh_displays()
        if hasattr(self.kpi_templates_frame, 'refresh_display'):
            self.kpi_templates_frame.refresh_display()
        if hasattr(self.kpi_specs_frame, 'refresh_display'):
            self.kpi_specs_frame.refresh_display()
        if hasattr(self.master_sub_link_frame, 'refresh_display'):
            self.master_sub_link_frame.refresh_display()
        if hasattr(self.target_entry_frame, 'populate_target_comboboxes'):
            self.target_entry_frame.populate_target_comboboxes()
        print("GUI refresh complete.")

if __name__ == "__main__":
    app = KpiApp()
    app.mainloop()
