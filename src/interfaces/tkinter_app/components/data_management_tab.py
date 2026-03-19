# src/interfaces/tkinter_app/components/data_management_tab.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import traceback
import datetime

from src import export_manager
from src import import_manager
from src.config.settings import CSV_EXPORT_BASE_PATH

class DataManagementTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.create_widgets()

    def create_widgets(self):
        # Background frame
        container = ttk.Frame(self, style="Content.TFrame", padding=20)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="Data Management Center", font=("Helvetica", 18, "bold"), background="#F5F5F5").pack(pady=(0, 25))

        # Horizontal container for 3 cards
        cards_frame = ttk.Frame(container, style="Content.TFrame")
        cards_frame.pack(fill="x", expand=True)

        # --- Card 1: CSV Export ---
        csv_card = ttk.LabelFrame(cards_frame, text="CSV Data Export", padding=15, style="Card.TLabelframe")
        csv_card.place(relx=0, rely=0, relwidth=0.32, relheight=0.8) # Using place for equal height or grid
        csv_card.pack(side="left", fill="both", expand=True, padx=5)

        ttk.Label(csv_card, text="Generate flat CSV files for external reporting or Excel analysis.", wraplength=200, background="#FFFFFF").pack(pady=10)
        ttk.Button(csv_card, text="Export CSVs", command=self.export_csvs, style="Action.TButton").pack(side="bottom", pady=10)

        # --- Card 2: Backup ---
        backup_card = ttk.LabelFrame(cards_frame, text="System Backup", padding=15, style="Card.TLabelframe")
        backup_card.pack(side="left", fill="both", expand=True, padx=5)

        ttk.Label(backup_card, text="Create a full ZIP backup of all databases and configuration.", wraplength=200, background="#FFFFFF").pack(pady=10)
        ttk.Button(backup_card, text="Create ZIP", command=self.create_backup, style="Action.TButton").pack(side="bottom", pady=10)

        # --- Card 3: Restore ---
        restore_card = ttk.LabelFrame(cards_frame, text="System Restore", padding=15, style="Card.TLabelframe")
        restore_card.pack(side="left", fill="both", expand=True, padx=5)

        ttk.Label(restore_card, text="Restore system state from a previous ZIP backup. WARN: Overwrites data.", wraplength=200, background="#FFFFFF").pack(pady=10)
        ttk.Button(restore_card, text="Restore ZIP", command=self.restore_backup).pack(side="bottom", pady=10)

    def export_csvs(self):
        try:
            export_manager.export_all_data_to_global_csvs()
            messagebox.showinfo("Success", f"All tables exported as CSV to:\n{CSV_EXPORT_BASE_PATH}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def create_backup(self):
        try:
            # Update CSVs before zipping
            export_manager.export_all_data_to_global_csvs()
            
            path = filedialog.asksaveasfilename(
                title="Save Backup",
                initialdir=CSV_EXPORT_BASE_PATH,
                initialfile=f"KPI_Backup_{datetime.datetime.now().strftime('%Y%m%d')}.zip",
                defaultextension=".zip",
                filetypes=[("ZIP files", "*.zip")]
            )
            if not path: return

            success, msg = export_manager.package_all_csvs_as_zip(output_zip_filepath_str=path)
            if success: messagebox.showinfo("Success", "Backup created successfully.")
            else: messagebox.showerror("Error", msg)
        except Exception as e: messagebox.showerror("Error", str(e))

    def restore_backup(self):
        path = filedialog.askopenfilename(title="Select Backup ZIP", filetypes=[("ZIP files", "*.zip")])
        if not path: return

        if not messagebox.askyesno("Confirm", "Overwrite ALL current data with this backup?"): return

        try:
            res = import_manager.import_from_zip(path)
            messagebox.showinfo("Restore Complete", res)
            self.app.refresh_all_data()
        except Exception as e: messagebox.showerror("Restore Error", str(e))
