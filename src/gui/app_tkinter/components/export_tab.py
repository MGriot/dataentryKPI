import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import traceback
import datetime # Added this import

import export_manager
import import_manager
import data_retriever as db_retriever # Added this import
from app_config import CSV_EXPORT_BASE_PATH, get_database_path

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

        ttk.Separator(export_main_frame, orient='horizontal').pack(fill='x', pady=20)

        import_frame = ttk.Frame(export_main_frame)
        import_frame.pack(pady=10)

        ttk.Label(import_frame, text="Anno Importazione:").pack(side="left", padx=(0, 5))
        self.import_year_var = tk.StringVar(value=str(datetime.datetime.now().year))
        self.import_year_cb = ttk.Combobox(import_frame, textvariable=self.import_year_var, state="readonly", width=10)
        self.import_year_cb['values'] = [str(y) for y in range(datetime.datetime.now().year - 5, datetime.datetime.now().year + 5)]
        self.import_year_cb.pack(side="left", padx=5)

        ttk.Label(import_frame, text="Stabilimento Importazione:").pack(side="left", padx=(10, 5))
        self.import_stabilimento_var = tk.StringVar()
        self.import_stabilimento_cb = ttk.Combobox(import_frame, textvariable=self.import_stabilimento_var, state="readonly", width=20)
        self.import_stabilimento_cb.pack(side="left", padx=5)

        ttk.Button(export_main_frame, text="Importa da CSV", command=self.import_csv).pack(pady=10, ipadx=10, ipady=5)

        self.populate_import_filters()

    def populate_import_filters(self):
        stabilimenti = db_retriever.get_all_stabilimenti(visible_only=True)
        self.stabilimenti_map = {s['name']: s['id'] for s in stabilimenti}
        self.import_stabilimento_cb['values'] = list(self.stabilimenti_map.keys())
        if self.stabilimenti_map:
            self.import_stabilimento_cb.current(0)

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

    def import_csv(self):
        file_path = filedialog.askopenfilename(
            title="Seleziona il file CSV da importare",
            filetypes=[("CSV files", "*.csv")]
        )
        if not file_path:
            return

        year_str = self.import_year_var.get()
        stabilimento_name = self.import_stabilimento_var.get()
        if not year_str or not stabilimento_name:
            messagebox.showerror("Errore", "Anno e stabilimento devono essere selezionati per l'importazione.")
            return

        year = int(year_str)
        stabilimento_id = self.stabilimenti_map[stabilimento_name]

        file_name = Path(file_path).name
        db_map = {
            "all_annual_kpi_master_targets.csv": ("annual_targets", get_database_path("db_kpi_targets.db")),
            "dict_kpis.csv": ("kpis", get_database_path("db_kpis.db")),
            "dict_stabilimenti.csv": ("stabilimenti", get_database_path("db_stabilimenti.db")),
        }

        if file_name not in db_map:
            messagebox.showerror("Errore", f"File non riconosciuto per l'importazione: {file_name}")
            return

        table_name, db_path = db_map[file_name]

        try:
            result = import_manager.import_data_from_csv(Path(file_path), table_name, db_path, year, stabilimento_id)
            messagebox.showinfo("Importazione Completata", result)
            self.app.refresh_all_data()
        except Exception as e:
            messagebox.showerror("Errore Importazione", f"Si è verificato un errore durante l'importazione:\n{e}")
            traceback.print_exc()
