import tkinter as tk
from tkinter import ttk, messagebox
import traceback

from stabilimenti_management import crud as stabilimenti_manager
import data_retriever

class StabilimentiTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.create_widgets()

    def create_widgets(self):
        self.st_tree = ttk.Treeview(
            self,
            columns=("ID", "Nome", "Descrizione", "Visibile"),
            show="headings",
        )
        self.st_tree.heading("ID", text="ID")
        self.st_tree.column("ID", width=50, anchor="center", stretch=tk.NO)
        self.st_tree.heading("Nome", text="Nome")
        self.st_tree.column("Nome", width=250, stretch=tk.YES)
        self.st_tree.heading("Descrizione", text="Descrizione")
        self.st_tree.column("Descrizione", width=300, stretch=tk.YES)
        self.st_tree.heading("Visibile", text="Visibile")
        self.st_tree.column("Visibile", width=80, anchor="center", stretch=tk.NO)

        self.st_tree.pack(expand=True, fill="both", padx=5, pady=5)

        bf_container = ttk.Frame(self)
        bf_container.pack(fill="x", pady=10)
        bf = ttk.Frame(bf_container)
        bf.pack()

        ttk.Button(bf, text="Aggiungi", command=self.add_stabilimento_window, style="Accent.TButton").pack(side="left", padx=5)
        ttk.Button(bf, text="Modifica", command=self.edit_stabilimento_window).pack(side="left", padx=5)
        ttk.Button(bf, text="Elimina", command=self.delete_stabilimento).pack(side="left", padx=5)

    def refresh_tree(self):
        for i in self.st_tree.get_children():
            self.st_tree.delete(i)
        try:
            for row in data_retriever.get_all_stabilimenti():
                self.st_tree.insert(
                    "",
                    "end",
                    values=(row["id"], row["name"], row["description"] if row["description"] is not None else "", "Sì" if row["visible"] else "No"),
                )
        except Exception as e:
            messagebox.showerror("Errore di Caricamento", f"Impossibile caricare gli stabilimenti dal database:\n{e}")

    def add_stabilimento_window(self):
        self.stabilimento_editor_window()

    def edit_stabilimento_window(self):
        selected_item_iid = self.st_tree.focus()
        if not selected_item_iid:
            messagebox.showwarning("Attenzione", "Seleziona uno stabilimento da modificare.")
            return
        
        item_values = self.st_tree.item(selected_item_iid)["values"]
        if not item_values:
            messagebox.showerror("Errore", "Impossibile leggere i dati dello stabilimento selezionato.")
            return
            
        try:
            data_tuple = (
                int(item_values[0]), 
                item_values[1], 
                item_values[2], 
                item_values[3]
            )
            self.stabilimento_editor_window(data_tuple=data_tuple)
        except (ValueError, IndexError) as e:
            messagebox.showerror("Errore Dati", f"I dati per lo stabilimento selezionato non sono validi: {e}")

    def delete_stabilimento(self):
        selected_item = self.st_tree.focus()
        if not selected_item:
            messagebox.showwarning("Attenzione", "Seleziona uno stabilimento da eliminare.")
            return
        
        item_values = self.st_tree.item(selected_item)["values"]
        try:
            stabilimento_id = int(item_values[0])
            stabilimento_name = item_values[1]
        except (ValueError, IndexError):
            messagebox.showerror("Errore", "ID stabilimento non valido.")
            return

        if messagebox.askyesno("Conferma Eliminazione", f"Sei sicuro di voler eliminare lo stabilimento '{stabilimento_name}'?\nQuesta azione è irreversibile."):
            try:
                stabilimenti_manager.delete_stabilimento(stabilimento_id)
                self.app.refresh_all_data() 
                messagebox.showinfo("Successo", f"Stabilimento '{stabilimento_name}' eliminato con successo.")
            except ValueError as ve:
                messagebox.showerror("Errore di Eliminazione", f"Impossibile eliminare lo stabilimento:\n{ve}")
            except Exception as e:
                messagebox.showerror("Errore di Eliminazione", f"Impossibile eliminare lo stabilimento:\n{e}\n\n{traceback.format_exc()}")

    def stabilimento_editor_window(self, data_tuple=None):
        win = tk.Toplevel(self)
        win.title("Nuovo Stabilimento" if data_tuple is None else "Modifica Stabilimento")
        win.transient(self)
        win.grab_set()
        win.geometry("450x220")
        win.resizable(False, False)

        s_id, s_name, s_desc, s_vis_str = (
            data_tuple
            if data_tuple
            else (None, "", "", "Sì")
        )

        form_frame = ttk.Frame(win, padding=15)
        form_frame.pack(expand=True, fill="both")

        ttk.Label(form_frame, text="Nome Stabilimento:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        name_var = tk.StringVar(value=s_name)
        name_entry = ttk.Entry(form_frame, textvariable=name_var, width=40)
        name_entry.grid(row=0, column=1, padx=5, pady=5)
        name_entry.focus_set()

        ttk.Label(form_frame, text="Descrizione:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        desc_var = tk.StringVar(value=s_desc)
        desc_entry = ttk.Entry(form_frame, textvariable=desc_var, width=40)
        desc_entry.grid(row=1, column=1, padx=5, pady=5)

        visible_var = tk.BooleanVar(value=(s_vis_str == "Sì"))
        ttk.Checkbutton(form_frame, text="Visibile per Inserimento Target", variable=visible_var).grid(row=2, column=1, sticky="w", padx=5, pady=10)

        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=3, columnspan=2, pady=15)

        def save_action():
            nome_val = name_var.get().strip()
            desc_val = desc_var.get().strip()
            if not nome_val:
                messagebox.showerror("Errore di Validazione", "Il campo 'Nome' è obbligatorio.", parent=win)
                return
            
            try:
                if s_id is not None:
                    stabilimenti_manager.update_stabilimento(s_id, nome_val, desc_val, visible_var.get())
                else:
                    stabilimenti_manager.add_stabilimento(nome_val, desc_val, visible_var.get())
                
                self.app.refresh_all_data()
                win.destroy()
                messagebox.showinfo("Successo", "Stabilimento salvato con successo.")

            except Exception as e:
                messagebox.showerror("Errore di Salvataggio", f"Salvataggio fallito:\n{e}\n\n{traceback.format_exc()}", parent=win)

        ttk.Button(btn_frame, text="Salva", command=save_action, style="Accent.TButton").pack(side="left", padx=10)
        ttk.Button(btn_frame, text="Annulla", command=win.destroy).pack(side="left", padx=10)