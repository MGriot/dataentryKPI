import tkinter as tk
from tkinter import ttk
import sys
from pathlib import Path

# The main entry point (main.py) adds the project root to the path.
# All imports should be absolute from the 'src' package.

from src.data_access.setup import setup_databases
from src.interfaces.tkinter_app.components.plants_tab import PlantsTab
from src.interfaces.tkinter_app.components.kpi_management_tab import KpiManagementTab
from src.interfaces.tkinter_app.components.target_entry_tab import TargetEntryTab
from src.interfaces.tkinter_app.components.data_management_tab import DataManagementTab
from src.interfaces.tkinter_app.components.analysis_tab import AnalysisTab
from src.interfaces.tkinter_app.components.settings_tab import SettingsTab
from src.interfaces.common_ui.constants import KPI_CALC_TYPE_OPTIONS
from src.config.settings import reload_app_settings, SETTINGS

class KpiApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("KPI Target Manager")
        self.geometry("1400x900")
        
        # Load settings
        reload_app_settings()
        self.settings = SETTINGS

        # Configure styles first
        self.style = ttk.Style(self)
        self._configure_styles()

        # Then, setup database
        try:
            setup_databases()
        except Exception as e:
            print(f"Failed to setup databases: {e}")

        self.kpi_calc_type_options_tk = KPI_CALC_TYPE_OPTIONS

        # Main Layout
        self._create_layout()
        
        # Initialize default view
        self.show_view("target_entry")
        
        # Finally, refresh data
        self.refresh_all_data()

    def load_settings(self):
        reload_app_settings()
        self.settings = SETTINGS
        self.refresh_all_data()

    def _configure_styles(self):
        style = self.style
        
        # Use 'clam' as base for better color customization
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass

        # Colors
        bg_charcoal = "#2C2C2C"
        bg_light_grey = "#F5F5F5"
        bg_white = "#FFFFFF"
        text_dark = "#333333"
        text_white = "#FFFFFF"
        accent_black = "#000000"
        
        # Fonts
        base_font = ("Helvetica", 10)
        heading_font = ("Helvetica", 12, "bold")
        nav_font = ("Helvetica", 11)

        # General Configuration
        style.configure(".", background=bg_light_grey, foreground=text_dark, font=base_font)
        
        # Sidebar Styles
        style.configure("Sidebar.TFrame", background=bg_charcoal)
        
        # Navigation Button Style
        style.configure("Nav.TButton", 
                        background=bg_charcoal, 
                        foreground=text_white, 
                        borderwidth=0, 
                        font=nav_font,
                        anchor="w",
                        padding=10)
        style.map("Nav.TButton",
                  background=[("active", "#404040"), ("pressed", "#202020")],
                  foreground=[("active", text_white)])

        # Content Area Styles
        style.configure("Content.TFrame", background=bg_light_grey)
        
        # Card Styles (White bg, rounded look simulated with border/relief)
        style.configure("Card.TFrame", background=bg_white, relief="flat", borderwidth=0)
        style.configure("Card.TLabelframe", background=bg_white, relief="flat", borderwidth=1)
        style.configure("Card.TLabelframe.Label", background=bg_white, foreground=text_dark, font=heading_font)

        # Specialty Labelframes for KPI States
        style.configure("Formula.TLabelframe", background="#E3F2FD", borderwidth=1) # Light Blue
        style.configure("Formula.TLabelframe.Label", background="#E3F2FD", foreground=text_dark, font=heading_font)
        
        style.configure("Formula.TFrame", background="#E3F2FD")
        
        style.configure("Manual.TLabelframe", background=bg_white, borderwidth=1)
        style.configure("Manual.TLabelframe.Label", background=bg_white, foreground=text_dark, font=heading_font)
        
        style.configure("Manual.TFrame", background=bg_white)

        # Input Fields
        style.configure("TEntry", fieldbackground=bg_white, borderwidth=1, relief="solid")
        style.configure("TCombobox", fieldbackground=bg_white, background=bg_white)

        # Action Buttons (Solid Black)
        style.configure("Action.TButton", 
                        background=accent_black, 
                        foreground=text_white, 
                        borderwidth=0, 
                        font=("Helvetica", 10, "bold"),
                        padding=8)
        style.map("Action.TButton",
                  background=[("active", "#333333"), ("pressed", "#000000")])

        # Treeview (Data Grid)
        style.configure("Treeview", 
                        background=bg_white, 
                        fieldbackground=bg_white, 
                        foreground=text_dark, 
                        rowheight=25,
                        borderwidth=0)
        style.configure("Treeview.Heading", 
                        background="#E0E0E0", 
                        foreground=text_dark, 
                        font=heading_font,
                        borderwidth=0)
        style.map("Treeview", background=[("selected", "#E0E0E0")], foreground=[("selected", text_dark)])

        # Specific component adjustments
        style.configure("Accent.TButton", background=accent_black, foreground=text_white) # Mapping old accent to new black

    def _create_layout(self):
        # Main Container
        self.main_container = ttk.Frame(self)
        self.main_container.pack(fill="both", expand=True)

        # Sidebar (Left)
        self.sidebar_frame = ttk.Frame(self.main_container, style="Sidebar.TFrame", width=250)
        self.sidebar_frame.pack(side="left", fill="y")
        self.sidebar_frame.pack_propagate(False)

        # Sidebar Title/Logo Area
        title_label = ttk.Label(self.sidebar_frame, text="KPI Manager", 
                                background="#2C2C2C", foreground="#FFFFFF", 
                                font=("Helvetica", 16, "bold"))
        title_label.pack(pady=30, padx=20, anchor="w")

        # Navigation Menu
        self._create_nav_button("Target Entry", "target_entry")
        self._create_nav_button("KPI Management", "kpi_management")
        self._create_nav_button("Plants", "plants")
        self._create_nav_button("Data Management", "data_management")
        self._create_nav_button("Results Analysis", "analysis")
        self._create_nav_button("Settings", "settings")

        # Content Area (Right)
        self.content_area = ttk.Frame(self.main_container, style="Content.TFrame")
        self.content_area.pack(side="right", fill="both", expand=True)
        
        # Dictionary to hold view instances
        self.views = {}

    def _create_nav_button(self, text, view_name):
        btn = ttk.Button(self.sidebar_frame, text=text, style="Nav.TButton",
                         command=lambda: self.show_view(view_name))
        btn.pack(fill="x", pady=2, padx=10)

    def show_view(self, view_name):
        # Hide all existing views in content area
        for widget in self.content_area.winfo_children():
            widget.pack_forget()

        # Instantiate view if not already created
        if view_name not in self.views:
            if view_name == "target_entry":
                self.views[view_name] = TargetEntryTab(self.content_area, self)
            elif view_name == "kpi_management":
                self.views[view_name] = KpiManagementTab(self.content_area, self)
            elif view_name == "plants":
                self.views[view_name] = PlantsTab(self.content_area, self)
            elif view_name == "data_management":
                self.views[view_name] = DataManagementTab(self.content_area, self)
            elif view_name == "analysis":
                self.views[view_name] = AnalysisTab(self.content_area, self)
            elif view_name == "settings":
                self.views[view_name] = SettingsTab(self.content_area, self)

        # Show selected view
        view = self.views[view_name]
        view.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Trigger on_tab_selected if method exists (legacy support from Tab logic)
        if hasattr(view, 'on_tab_selected'):
            view.on_tab_selected()

    def refresh_all_data(self):
        # Refresh all loaded views
        for view in self.views.values():
            if hasattr(view, 'refresh_tree'):
                view.refresh_tree()
            if hasattr(view, 'refresh_display'):
                view.refresh_display()
            if hasattr(view, 'populate_target_comboboxes'):
                view.populate_target_comboboxes()
            if hasattr(view, 'populate_filters'):
                view.populate_filters()

if __name__ == "__main__":
    app = KpiApp()
    app.mainloop()