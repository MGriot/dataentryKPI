import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import traceback

from kpi_management import groups as kpi_groups_manager
from kpi_management import subgroups as kpi_subgroups_manager
from kpi_management import indicators as kpi_indicators_manager
import data_retriever as db_retriever
from ..dialogs.subgroup_editor import SubgroupEditorDialog

class KpiHierarchyTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        
        self.current_groups_map = {}
        self.current_subgroups_map = {}
        self.current_indicators_map = {}

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True)

        # --- Group Frame ---
        group_frame = ttk.LabelFrame(main_frame, text="Gruppi KPI", padding=10)
        group_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.groups_listbox = tk.Listbox(group_frame, exportselection=False, height=15, width=25)
        self.groups_listbox.pack(fill="both", expand=True, pady=(0, 5))
        self.groups_listbox.bind("<<ListboxSelect>>", self.on_group_select)

        group_btn_frame = ttk.Frame(group_frame)
        group_btn_frame.pack(fill="x")
        ttk.Button(group_btn_frame, text="Nuovo", command=self.add_new_group, width=8, style="Accent.TButton").pack(side="left", padx=2)
        self.edit_group_btn = ttk.Button(group_btn_frame, text="Modifica", command=self.edit_selected_group, state="disabled", width=8)
        self.edit_group_btn.pack(side="left", padx=2)
        self.delete_group_btn = ttk.Button(group_btn_frame, text="Elimina", command=self.delete_selected_group, state="disabled", width=8)
        self.delete_group_btn.pack(side="left", padx=2)

        # --- Subgroup Frame ---
        subgroup_frame = ttk.LabelFrame(main_frame, text="Sottogruppi", padding=10)
        subgroup_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.subgroups_listbox = tk.Listbox(subgroup_frame, exportselection=False, height=15, width=35)
        self.subgroups_listbox.pack(fill="both", expand=True, pady=(0, 5))
        self.subgroups_listbox.bind("<<ListboxSelect>>", self.on_subgroup_select)

        subgroup_btn_frame = ttk.Frame(subgroup_frame)
        subgroup_btn_frame.pack(fill="x")
        self.add_subgroup_btn = ttk.Button(subgroup_btn_frame, text="Nuovo", command=self.add_new_subgroup, state="disabled", width=8, style="Accent.TButton")
        self.add_subgroup_btn.pack(side="left", padx=2)
        self.edit_subgroup_btn = ttk.Button(subgroup_btn_frame, text="Modifica", command=self.edit_selected_subgroup, state="disabled", width=8)
        self.edit_subgroup_btn.pack(side="left", padx=2)
        self.delete_subgroup_btn = ttk.Button(subgroup_btn_frame, text="Elimina", command=self.delete_selected_subgroup, state="disabled", width=8)
        self.delete_subgroup_btn.pack(side="left", padx=2)

        # --- Indicator Frame ---
        indicator_frame = ttk.LabelFrame(main_frame, text="Indicatori", padding=10)
        indicator_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.indicators_listbox = tk.Listbox(indicator_frame, exportselection=False, height=15, width=30)
        self.indicators_listbox.pack(fill="both", expand=True, pady=(0, 5))
        self.indicators_listbox.bind("<<ListboxSelect>>", self.on_indicator_select)

        indicator_btn_frame = ttk.Frame(indicator_frame)
        indicator_btn_frame.pack(fill="x")
        self.add_indicator_btn = ttk.Button(indicator_btn_frame, text="Nuovo", command=self.add_new_indicator, state="disabled", width=8, style="Accent.TButton")
        self.add_indicator_btn.pack(side="left", padx=2)
        self.edit_indicator_btn = ttk.Button(indicator_btn_frame, text="Modifica", command=self.edit_selected_indicator, state="disabled", width=8)
        self.edit_indicator_btn.pack(side="left", padx=2)
        self.delete_indicator_btn = ttk.Button(indicator_btn_frame, text="Elimina", command=self.delete_selected_indicator, state="disabled", width=8)
        self.delete_indicator_btn.pack(side="left", padx=2)

    def refresh_displays(self, pre_selected_group_name=None, pre_selected_subgroup_raw_name=None):
        self.groups_listbox.delete(0, tk.END)
        self.current_groups_map.clear()
        groups_data = db_retriever.get_kpi_groups()
        group_selected_idx = -1
        for i, group in enumerate(groups_data):
            self.groups_listbox.insert(tk.END, group["name"])
            self.current_groups_map[group["name"]] = group["id"]
            if group["name"] == pre_selected_group_name:
                group_selected_idx = i

        if group_selected_idx != -1:
            self.groups_listbox.selection_set(group_selected_idx)
            self.groups_listbox.activate(group_selected_idx)
            self.groups_listbox.see(group_selected_idx)
            self.on_group_select(pre_selected_subgroup_raw_name=pre_selected_subgroup_raw_name)
        else:
            self.on_group_select()

    def on_group_select(self, event=None, pre_selected_subgroup_raw_name=None):
        self.subgroups_listbox.delete(0, tk.END)
        self.indicators_listbox.delete(0, tk.END)
        self.current_subgroups_map.clear()
        self.current_indicators_map.clear()
        
        self.edit_group_btn.config(state="disabled")
        self.delete_group_btn.config(state="disabled")
        self.add_subgroup_btn.config(state="disabled")

        selection = self.groups_listbox.curselection()
        if not selection:
            return

        self.edit_group_btn.config(state="normal")
        self.delete_group_btn.config(state="normal")
        self.add_subgroup_btn.config(state="normal")

        group_name = self.groups_listbox.get(selection[0])
        group_id = self.current_groups_map.get(group_name)
        if group_id:
            subgroups_data = db_retriever.get_kpi_subgroups_by_group_revised(group_id)
            subgroup_selected_idx = -1
            for i, sg in enumerate(subgroups_data):
                raw_sg_name = sg["name"]
                display_name = raw_sg_name + (f" (Tpl: {sg['template_name']})" if sg.get("template_name") else "")
                self.subgroups_listbox.insert(tk.END, display_name)
                self.current_subgroups_map[display_name] = {"id": sg["id"], "template_id": sg.get("indicator_template_id")}
                if pre_selected_subgroup_raw_name and raw_sg_name == pre_selected_subgroup_raw_name:
                    subgroup_selected_idx = i
            
            if subgroup_selected_idx != -1:
                self.subgroups_listbox.selection_set(subgroup_selected_idx)
                self.subgroups_listbox.activate(subgroup_selected_idx)
                self.subgroups_listbox.see(subgroup_selected_idx)
        
        self.on_subgroup_select()

    def on_subgroup_select(self, event=None):
        self.indicators_listbox.delete(0, tk.END)
        self.current_indicators_map.clear()

        self.edit_subgroup_btn.config(state="disabled")
        self.delete_subgroup_btn.config(state="disabled")
        self.add_indicator_btn.config(state="disabled")

        selection = self.subgroups_listbox.curselection()
        if not selection:
            return

        self.edit_subgroup_btn.config(state="normal")
        self.delete_subgroup_btn.config(state="normal")

        display_subgroup_name = self.subgroups_listbox.get(selection[0])
        subgroup_info = self.current_subgroups_map.get(display_subgroup_name)
        if subgroup_info:
            subgroup_id = subgroup_info["id"]
            is_templated = subgroup_info["template_id"] is not None
            
            if not is_templated:
                self.add_indicator_btn.config(state="normal")
            else:
                self.add_indicator_btn.config(text="Nuovo (da Tpl)", state="disabled")

            for ind in db_retriever.get_kpi_indicators_by_subgroup(subgroup_id):
                self.indicators_listbox.insert(tk.END, ind["name"])
                self.current_indicators_map[ind["name"]] = ind["id"]
        
        self.on_indicator_select()

    def on_indicator_select(self, event=None):
        self.edit_indicator_btn.config(state="disabled")
        self.delete_indicator_btn.config(state="disabled")

        if self.indicators_listbox.curselection() and self.subgroups_listbox.curselection():
            display_subgroup_name = self.subgroups_listbox.get(self.subgroups_listbox.curselection()[0])
            subgroup_info = self.current_subgroups_map.get(display_subgroup_name)
            if subgroup_info and not subgroup_info["template_id"]:
                self.edit_indicator_btn.config(state="normal")
                self.delete_indicator_btn.config(state="normal")

    def add_new_group(self):
        name = simpledialog.askstring("Nuovo Gruppo", "Nome Gruppo KPI:", parent=self)
        if name:
            try:
                kpi_groups_manager.add_kpi_group(name)
                self.app.refresh_all_data()
                self.after(100, lambda: self._select_item_in_listbox(self.groups_listbox, name))
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile aggiungere gruppo: {e}")

    def edit_selected_group(self):
        if not self.groups_listbox.curselection(): return
        old_name = self.groups_listbox.get(self.groups_listbox.curselection()[0])
        group_id = self.current_groups_map.get(old_name)
        new_name = simpledialog.askstring("Modifica Gruppo", "Nuovo nome:", initialvalue=old_name, parent=self)
        if new_name and new_name != old_name:
            try:
                kpi_groups_manager.update_kpi_group(group_id, new_name)
                self.app.refresh_all_data()
                self.after(100, lambda: self._select_item_in_listbox(self.groups_listbox, new_name))
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile modificare gruppo: {e}")

    def delete_selected_group(self):
        if not self.groups_listbox.curselection(): return
        name = self.groups_listbox.get(self.groups_listbox.curselection()[0])
        group_id = self.current_groups_map.get(name)
        if messagebox.askyesno("Conferma", f"Eliminare gruppo '{name}' e tutti i suoi contenuti?"):
            try:
                kpi_groups_manager.delete_kpi_group(group_id)
                self.app.refresh_all_data()
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile eliminare gruppo: {e}\n{traceback.format_exc()}")

    def add_new_subgroup(self):
        if not self.groups_listbox.curselection(): return
        group_name = self.groups_listbox.get(self.groups_listbox.curselection()[0])
        group_id = self.current_groups_map.get(group_name)
        dialog = SubgroupEditorDialog(self, title="Nuovo Sottogruppo", group_id_context=group_id)
        if dialog.result_name:
            try:
                kpi_subgroups_manager.add_kpi_subgroup(dialog.result_name, group_id, dialog.result_template_id)
                self.app.refresh_all_data()
                self.after(100, lambda: self.refresh_displays(pre_selected_group_name=group_name, pre_selected_subgroup_raw_name=dialog.result_name))
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile aggiungere sottogruppo: {e}\n{traceback.format_exc()}")

    def edit_selected_subgroup(self):
        if not self.subgroups_listbox.curselection() or not self.groups_listbox.curselection(): return
        group_name = self.groups_listbox.get(self.groups_listbox.curselection()[0])
        group_id = self.current_groups_map.get(group_name)
        display_name = self.subgroups_listbox.get(self.subgroups_listbox.curselection()[0])
        subgroup_info = self.current_subgroups_map.get(display_name)
        if not subgroup_info: return
        
        old_raw_name = display_name.split(" (Tpl:")[0]
        dialog = SubgroupEditorDialog(self, title="Modifica Sottogruppo", group_id_context=group_id, initial_name=old_raw_name, initial_template_id=subgroup_info.get("template_id"))
        if dialog.result_name:
            try:
                kpi_subgroups_manager.update_kpi_subgroup(subgroup_info["id"], dialog.result_name, group_id, dialog.result_template_id)
                self.app.refresh_all_data()
                self.after(100, lambda: self.refresh_displays(pre_selected_group_name=group_name, pre_selected_subgroup_raw_name=dialog.result_name))
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile modificare sottogruppo: {e}\n{traceback.format_exc()}")

    def delete_selected_subgroup(self):
        if not self.subgroups_listbox.curselection(): return
        display_name = self.subgroups_listbox.get(self.subgroups_listbox.curselection()[0])
        subgroup_info = self.current_subgroups_map.get(display_name)
        if not subgroup_info: return

        if messagebox.askyesno("Conferma", f"Eliminare sottogruppo '{display_name.split(' (Tpl:')[0]}' e tutti i suoi contenuti?"):
            try:
                kpi_subgroups_manager.delete_kpi_subgroup(subgroup_info["id"])
                self.app.refresh_all_data()
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile eliminare sottogruppo: {e}\n{traceback.format_exc()}")

    def add_new_indicator(self):
        if not self.subgroups_listbox.curselection(): return
        display_subgroup_name = self.subgroups_listbox.get(self.subgroups_listbox.curselection()[0])
        subgroup_info = self.current_subgroups_map.get(display_subgroup_name)
        if not subgroup_info: return

        name = simpledialog.askstring("Nuovo Indicatore", "Nome Indicatore:", parent=self)
        if name:
            try:
                kpi_indicators_manager.add_kpi_indicator(name, subgroup_info["id"])
                self.app.refresh_all_data()
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile aggiungere indicatore: {e}")

    def edit_selected_indicator(self):
        if not self.indicators_listbox.curselection() or not self.subgroups_listbox.curselection(): return
        old_name = self.indicators_listbox.get(self.indicators_listbox.curselection()[0])
        indicator_id = self.current_indicators_map.get(old_name)
        display_subgroup_name = self.subgroups_listbox.get(self.subgroups_listbox.curselection()[0])
        subgroup_id = self.current_subgroups_map.get(display_subgroup_name)["id"]

        new_name = simpledialog.askstring("Modifica Indicatore", "Nuovo nome:", initialvalue=old_name, parent=self)
        if new_name and new_name != old_name:
            try:
                kpi_indicators_manager.update_kpi_indicator(indicator_id, new_name, subgroup_id)
                self.app.refresh_all_data()
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile modificare indicatore: {e}")

    def delete_selected_indicator(self):
        if not self.indicators_listbox.curselection(): return
        name = self.indicators_listbox.get(self.indicators_listbox.curselection()[0])
        indicator_id = self.current_indicators_map.get(name)
        if messagebox.askyesno("Conferma", f"Eliminare indicatore '{name}' e la sua specifica/target?"):
            try:
                kpi_indicators_manager.delete_kpi_indicator(indicator_id)
                self.app.refresh_all_data()
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile eliminare indicatore: {e}\n{traceback.format_exc()}")

    def _select_item_in_listbox(self, listbox, item_name):
        for i in range(listbox.size()):
            if listbox.get(i) == item_name:
                listbox.selection_clear(0, tk.END)
                listbox.selection_set(i)
                listbox.activate(i)
                listbox.see(i)
                listbox.event_generate("<<ListboxSelect>>")
                return True
        return False