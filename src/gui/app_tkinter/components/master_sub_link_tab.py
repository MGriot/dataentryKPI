import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import traceback

from kpi_management import links as kpi_links_manager
import data_retriever as db_retriever
from ...shared.helpers import get_kpi_display_name
from ..dialogs.link_sub_kpi_dialog import LinkSubKpiDialog

class MasterSubLinkTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill="both", expand=True)

        master_frame = ttk.LabelFrame(main_frame, text="Master KPIs", padding=10)
        master_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        self.master_kpi_tree = ttk.Treeview(master_frame, columns=("ID", "KPI Name"), show="headings", selectmode="browse")
        self.master_kpi_tree.heading("ID", text="ID")
        self.master_kpi_tree.column("ID", width=50, stretch=tk.NO)
        self.master_kpi_tree.heading("KPI Name", text="KPI Name")
        self.master_kpi_tree.pack(fill="both", expand=True)
        self.master_kpi_tree.bind("<<TreeviewSelect>>", self.on_kpi_select)

        sub_frame = ttk.LabelFrame(main_frame, text="Sub KPIs Linked", padding=10)
        sub_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        self.sub_kpi_listbox = tk.Listbox(sub_frame, selectmode="extended")
        self.sub_kpi_listbox.pack(fill="both", expand=True)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="y", side="left", padx=10)

        ttk.Button(btn_frame, text="Link Sub-KPI", command=self.link_sub_kpi, style="Accent.TButton").pack(pady=5)
        ttk.Button(btn_frame, text="Unlink Sub-KPI", command=self.unlink_sub_kpi).pack(pady=5)
        ttk.Button(btn_frame, text="Update Weight", command=self.update_weight).pack(pady=5)

    def refresh_display(self):
        self.master_kpi_tree.delete(*self.master_kpi_tree.get_children())
        all_kpis = db_retriever.get_all_kpis_detailed(only_visible=False)
        for kpi in all_kpis:
            display_name = get_kpi_display_name(kpi)
            self.master_kpi_tree.insert("", "end", iid=kpi["id"], values=(kpi["id"], display_name))
        self.on_kpi_select()

    def on_kpi_select(self, event=None):
        self.sub_kpi_listbox.delete(0, tk.END)
        selected_item = self.master_kpi_tree.focus()
        if not selected_item: return

        master_kpi_id = int(selected_item)
        linked_subs = db_retriever.get_linked_sub_kpis(master_kpi_id)
        for sub in linked_subs:
            display_name = get_kpi_display_name(sub)
            self.sub_kpi_listbox.insert(tk.END, f"{display_name} (Weight: {sub['weight']})")

    def link_sub_kpi(self):
        selected_master_item = self.master_kpi_tree.focus()
        if not selected_master_item: 
            messagebox.showwarning("Attenzione", "Seleziona un Master KPI.")
            return

        master_kpi_id = int(selected_master_item)
        all_kpis = db_retriever.get_all_kpis_detailed(only_visible=False)
        
        # Exclude master and already linked subs
        linked_sub_ids = {sub['sub_kpi_id'] for sub in db_retriever.get_linked_sub_kpis(master_kpi_id)}
        available_kpis = [kpi for kpi in all_kpis if kpi["id"] != master_kpi_id and kpi["id"] not in linked_sub_ids]

        # Simple dialog for now, can be improved
        dialog = LinkSubKpiDialog(self, "Link Sub-KPI", available_kpis)
        sub_kpi_to_link = dialog.result_kpi

        if not sub_kpi_to_link:
            messagebox.showerror("Errore", "Sub-KPI non trovato.")
            return

        weight = simpledialog.askfloat("Insert Weight", "Enter weight for this Sub-KPI:", initialvalue=1.0)
        if weight is None: return

        try:
            kpi_links_manager.link_sub_kpi(master_kpi_id, sub_kpi_to_link["id"], weight)
            self.on_kpi_select()
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile collegare Sub-KPI: {e}")

    def unlink_sub_kpi(self):
        selected_master_item = self.master_kpi_tree.focus()
        if not selected_master_item: return
        master_kpi_id = int(selected_master_item)

        selected_sub_indices = self.sub_kpi_listbox.curselection()
        if not selected_sub_indices: 
            messagebox.showwarning("Attenzione", "Seleziona uno o più Sub-KPI da scollegare.")
            return

        linked_subs = db_retriever.get_linked_sub_kpis(master_kpi_id)
        for index in selected_sub_indices:
            sub_kpi_id_to_unlink = linked_subs[index]['sub_kpi_id']
            try:
                kpi_links_manager.unlink_sub_kpi(master_kpi_id, sub_kpi_id_to_unlink)
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile scollegare Sub-KPI: {e}")
        self.on_kpi_select()

    def update_weight(self):
        selected_master_item = self.master_kpi_tree.focus()
        if not selected_master_item: return
        master_kpi_id = int(selected_master_item)

        selected_sub_index = self.sub_kpi_listbox.curselection()
        if len(selected_sub_index) != 1:
            messagebox.showwarning("Attenzione", "Seleziona un solo Sub-KPI per aggiornare il peso.")
            return

        linked_subs = db_retriever.get_linked_sub_kpis(master_kpi_id)
        sub_kpi_to_update = linked_subs[selected_sub_index[0]]

        new_weight = simpledialog.askfloat("Update Weight", "Enter new weight:", initialvalue=sub_kpi_to_update['weight'])
        if new_weight is not None:
            try:
                kpi_links_manager.update_link_weight(master_kpi_id, sub_kpi_to_update['sub_kpi_id'], new_weight)
                self.on_kpi_select()
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile aggiornare il peso: {e}")