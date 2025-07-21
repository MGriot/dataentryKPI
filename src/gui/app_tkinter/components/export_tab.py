import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import traceback

import export_manager
from app_config import CSV_EXPORT_BASE_PATH

class ExportTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.create_widgets()

    def create_widgets(self):
        export_main_frame = ttk.Frame(self, padding=20)
        export_main_frame.pack(expand=True, fill="both")

        ttk.Label(export_main_frame, text="Directory di Esportazione:").pack(pady=(0, 5))
        self.export_path_label = ttk.Label(export_main_frame, text=str(CSV_EXPORT_BASE_PATH), font=("TkDefaultFont", 10, "bold"))
        self.export_path_label.pack(pady=(0, 20))

        ttk.Button(export_main_frame, text="Esporta Tutti i Dati in CSV", command=self.export_csv).pack(pady=10, ipadx=10, ipady=5)
        ttk.Button(export_main_frame, text="Impacchetta Tutti i CSV in ZIP", command=self.package_zip).pack(pady=10, ipadx=10, ipady=5)

    def export_csv(self):
        try:
            export_manager.export_all_data_to_global_csvs()
            messagebox.showinfo("Successo", f"Dati esportati con successo in:\n{CSV_EXPORT_BASE_PATH}")
        except Exception as e:
            messagebox.showerror("Errore Esportazione", f"Si è verificato un errore durante l'esportazione dei CSV:\n{e}")
            traceback.print_exc()

    def package_zip(self):
        try:
            output_zip_filepath = filedialog.asksaveasfilename(
                title="Salva Archivio ZIP",
                initialdir=CSV_EXPORT_BASE_PATH,
                initialfile="dataentryKPI_export.zip",
                defaultextension=".zip",
                filetypes=[("ZIP files", "*.zip")]
            )
            if not output_zip_filepath:
                return

            success, message = export_manager.package_all_csvs_as_zip(output_zip_filepath_str=output_zip_filepath)
            if success:
                messagebox.showinfo("Successo", f"Archivio ZIP creato con successo:\n{output_zip_filepath}")
            else:
                messagebox.showerror("Errore ZIP", f"Impossibile creare l'archivio ZIP:\n{message}")
        except Exception as e:
            messagebox.showerror("Errore", f"Si è verificato un errore imprevisto:\n{e}")
            traceback.print_exc()
