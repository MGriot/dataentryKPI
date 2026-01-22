import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import traceback

from src import export_manager
from src import import_manager
from src.config.settings import CSV_EXPORT_BASE_PATH

class DataManagementTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=20, style="Content.TFrame")
        main_frame.pack(expand=True, fill="both")

        ttk.Label(main_frame, text="Data Management", font=("Helvetica", 16, "bold"), background="#F5F5F5").pack(pady=(0, 20))

        backup_frame = ttk.LabelFrame(main_frame, text="Backup", padding=15, style="Card.TLabelframe")
        backup_frame.pack(fill="x", expand=True, pady=10)

        ttk.Button(backup_frame, text="Create Backup (ZIP)", command=self.create_backup, style="Action.TButton").pack(pady=10, ipadx=10, ipady=5)
        ttk.Label(backup_frame, text="Export all data (KPIs, plants, targets) into a single ZIP file.", wraplength=400, background="#FFFFFF").pack(pady=(0,10))

        restore_frame = ttk.LabelFrame(main_frame, text="Restore", padding=15, style="Card.TLabelframe")
        restore_frame.pack(fill="x", expand=True, pady=10)

        ttk.Button(restore_frame, text="Restore from Backup (ZIP)", command=self.restore_backup, style="Action.TButton").pack(pady=10, ipadx=10, ipady=5)
        ttk.Label(restore_frame, text="Restore data from a ZIP file. WARNING: This operation will overwrite existing data.", wraplength=400, background="#FFFFFF").pack(pady=(0,10))

    def create_backup(self):
        try:
            # First, ensure the CSVs are up-to-date
            export_manager.export_all_data_to_global_csvs()

            # Then, ask where to save the ZIP
            output_zip_filepath = filedialog.asksaveasfilename(
                title="Save Backup",
                initialdir=CSV_EXPORT_BASE_PATH,
                initialfile="dataentryKPI_backup.zip",
                defaultextension=".zip",
                filetypes=[("ZIP files", "*.zip")]
            )
            if not output_zip_filepath:
                return

            success, message = export_manager.package_all_csvs_as_zip(output_zip_filepath_str=output_zip_filepath)
            if success:
                messagebox.showinfo("Success", f"Backup created successfully:{output_zip_filepath}")
            else:
                messagebox.showerror("Error", f"Could not create backup:{message}")
        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred during backup creation:{e}")
            traceback.print_exc()

    def restore_backup(self):
        file_path = filedialog.askopenfilename(
            title="Select the Backup file to restore",
            filetypes=[("ZIP files", "*.zip")]
        )
        if not file_path:
            return

        if not messagebox.askyesno("Confirm Restore", "Are you sure you want to restore data from this backup? This operation is irreversible and will overwrite all current data."):
            return

        try:
            result = import_manager.import_from_zip(file_path)
            messagebox.showinfo("Restore Complete", result)
            self.app.refresh_all_data()
        except Exception as e:
            messagebox.showerror("Restore Error", f"An error occurred during restore:{e}")
            traceback.print_exc()
