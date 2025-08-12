import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import traceback

from src import export_manager
from src import import_manager
from src.app_config import CSV_EXPORT_BASE_PATH

class DataManagementTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(expand=True, fill="both")

        ttk.Label(main_frame, text="Gestione Dati", font=("TkDefaultFont", 16, "bold")).pack(pady=(0, 20))

        backup_frame = ttk.LabelFrame(main_frame, text="Backup", padding=15)
        backup_frame.pack(fill="x", expand=True, pady=10)

        ttk.Button(backup_frame, text="Crea Backup (ZIP)", command=self.create_backup).pack(pady=10, ipadx=10, ipady=5)
        ttk.Label(backup_frame, text="Esporta tutti i dati (KPI, stabilimenti, target) in un singolo file ZIP.", wraplength=400).pack(pady=(0,10))

        restore_frame = ttk.LabelFrame(main_frame, text="Ripristino", padding=15)
        restore_frame.pack(fill="x", expand=True, pady=10)

        ttk.Button(restore_frame, text="Ripristina da Backup (ZIP)", command=self.restore_backup).pack(pady=10, ipadx=10, ipady=5)
        ttk.Label(restore_frame, text="Ripristina i dati da un file ZIP. ATTENZIONE: questa operazione sovrascriverà i dati esistenti.", wraplength=400).pack(pady=(0,10))

    def create_backup(self):
        try:
            # First, ensure the CSVs are up-to-date
            export_manager.export_all_data_to_global_csvs()

            # Then, ask where to save the ZIP
            output_zip_filepath = filedialog.asksaveasfilename(
                title="Salva Backup",
                initialdir=CSV_EXPORT_BASE_PATH,
                initialfile="dataentryKPI_backup.zip",
                defaultextension=".zip",
                filetypes=[("ZIP files", "*.zip")]
            )
            if not output_zip_filepath:
                return

            success, message = export_manager.package_all_csvs_as_zip(output_zip_filepath_str=output_zip_filepath)
            if success:
                messagebox.showinfo("Successo", f"Backup creato con successo:{output_zip_filepath}")
            else:
                messagebox.showerror("Errore", f"Impossibile creare il backup:{message}")
        except Exception as e:
            messagebox.showerror("Errore", f"Si è verificato un errore imprevisto durante la creazione del backup:{e}")
            traceback.print_exc()

    def restore_backup(self):
        file_path = filedialog.askopenfilename(
            title="Seleziona il file di Backup da ripristinare",
            filetypes=[("ZIP files", "*.zip")]
        )
        if not file_path:
            return

        if not messagebox.askyesno("Conferma Ripristino", "Sei sicuro di voler ripristinare i dati da questo backup? L'operazione è irreversibile e sovrascriverà tutti i dati attuali."):
            return

        try:
            result = import_manager.import_from_zip(file_path)
            messagebox.showinfo("Ripristino Completato", result)
            self.app.refresh_all_data()
        except Exception as e:
            messagebox.showerror("Errore di Ripristino", f"Si è verificato un errore durante il ripristino:{e}")
            traceback.print_exc()