# app_tkinter.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import database_manager as db  # Import your database manager
import export_manager
import json
import datetime
import calendar
from pathlib import Path
import sqlite3
import os
import sys
import subprocess
import traceback # Ensure traceback is imported


# --- Helper Function ---
def get_kpi_display_name(kpi_data):
    """
    Generates a display name for a KPI using its hierarchy.
    Example: "Group > Subgroup > Indicator"
    Handles cases where names might be None or empty from the database.
    """
    if not kpi_data:
        return "N/D (KPI Data Mancante)"
    try:
        g_name = (
            kpi_data["group_name"]
            if kpi_data["group_name"]
            else "N/G (Gruppo non specificato)"
        )
        sg_name = (
            kpi_data["subgroup_name"]
            if kpi_data["subgroup_name"]
            else "N/S (Sottogruppo non specificato)"
        )
        i_name = (
            kpi_data["indicator_name"]
            if kpi_data["indicator_name"]
            else "N/I (Indicatore non specificato)"
        )
        return f"{g_name} > {sg_name} > {i_name}"
    except KeyError as e:
        print(
            f"KeyError in get_kpi_display_name: La colonna '{e}' è mancante nei dati KPI."
        )
        return "N/D (Struttura Dati KPI Incompleta)"
    except Exception as ex:
        print(f"Errore imprevisto in get_kpi_display_name: {ex}")
        return "N/D (Errore Display Nome)"


class KpiApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestione Target KPI - Desktop")
        self.geometry("1400x850")

        self._populating_kpi_spec_combos = False

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Accent.TButton", foreground="white", background="#007bff")
        style.configure("Treeview.Heading", font=("Calibri", 10, "bold"))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)

        self.target_frame = ttk.Frame(self.notebook, padding="10")
        self.kpi_hierarchy_frame = ttk.Frame(self.notebook, padding="10")
        self.kpi_template_frame = ttk.Frame(self.notebook, padding="10") # For KPI Indicator Templates
        self.kpi_spec_frame = ttk.Frame(self.notebook, padding="10")
        self.stabilimenti_frame = ttk.Frame(self.notebook, padding="10")
        self.results_frame = ttk.Frame(self.notebook, padding="10")
        self.export_frame = ttk.Frame(self.notebook, padding="10")

        self.notebook.add(self.target_frame, text="🎯 Inserimento Target")
        self.notebook.add(self.kpi_hierarchy_frame, text="🗂️ Gestione Gerarchia KPI")
        self.notebook.add(self.kpi_template_frame, text="📋 Gestione Template Indicatori") # Tab for templates
        self.notebook.add(self.kpi_spec_frame, text="⚙️ Gestione Specifiche KPI")
        self.notebook.add(self.stabilimenti_frame, text="🏭 Gestione Stabilimenti")
        self.notebook.add(self.results_frame, text="📈 Visualizzazione Risultati")
        self.notebook.add(self.export_frame, text="📦 Esportazione Dati")

        self.distribution_profile_options_tk = [
            "even_distribution", "annual_progressive", "annual_progressive_weekday_bias",
            "true_annual_sinusoidal", "monthly_sinusoidal", "legacy_intra_period_progressive",
            "quarterly_progressive", "quarterly_sinusoidal", "event_based_spikes_or_dips",
        ]
        self.repartition_logic_options_tk = ["Anno", "Mese", "Trimestre", "Settimana"]

        # Ensuring the call is correctly spelled as create_target_widgets
        self.create_target_widgets()
        self.create_kpi_hierarchy_widgets()
        self.create_kpi_template_widgets() # Call to create template widgets
        self.create_kpi_spec_widgets()
        self.create_stabilimenti_widgets()
        self.create_results_widgets()
        self.create_export_widgets()

        self.refresh_all_relevant_data()

    def refresh_all_relevant_data(self):
        current_group_sel_hier = None
        if hasattr(self, "groups_listbox") and self.groups_listbox.curselection():
            current_group_sel_hier = self.groups_listbox.get(self.groups_listbox.curselection()[0])

        current_subgroup_sel_hier = None
        if hasattr(self, "subgroups_listbox") and self.subgroups_listbox.curselection():
            full_display_name = self.subgroups_listbox.get(self.subgroups_listbox.curselection()[0])
            current_subgroup_sel_hier = full_display_name.split(" (Template:")[0]

        self.refresh_kpi_hierarchy_displays(
            pre_selected_group_name=current_group_sel_hier,
            pre_selected_subgroup_name=current_subgroup_sel_hier,
        )
        if hasattr(self, "refresh_kpi_templates_display"):
             self.refresh_kpi_templates_display()
        self.refresh_kpi_specs_tree()
        self.refresh_stabilimenti_tree()
        self.populate_target_comboboxes()
        self.populate_results_comboboxes()

    # --- Scheda Gestione Gerarchia KPI ---
    def create_kpi_hierarchy_widgets(self):
        main_frame = ttk.Frame(self.kpi_hierarchy_frame)
        main_frame.pack(fill="both", expand=True)

        group_frame = ttk.LabelFrame(main_frame, text="Gruppi KPI", padding=10)
        group_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        self.groups_listbox = tk.Listbox(group_frame, exportselection=False, height=15)
        self.groups_listbox.pack(fill="both", expand=True, pady=(0, 5))
        self.groups_listbox.bind("<<ListboxSelect>>", self.on_group_select)

        group_btn_frame = ttk.Frame(group_frame)
        group_btn_frame.pack(fill="x")
        ttk.Button(
            group_btn_frame, text="Nuovo", command=self.add_new_group, width=8
        ).pack(side="left", padx=2)
        self.edit_group_btn = ttk.Button(
            group_btn_frame,
            text="Modifica",
            command=self.edit_selected_group,
            state="disabled",
            width=8,
        )
        self.edit_group_btn.pack(side="left", padx=2)
        self.delete_group_btn = ttk.Button(
            group_btn_frame,
            text="Elimina",
            command=self.delete_selected_group,
            state="disabled",
            width=8,
        )
        self.delete_group_btn.pack(side="left", padx=2)

        subgroup_frame = ttk.LabelFrame(
            main_frame, text="Sottogruppi (del gruppo selezionato)", padding=10
        )
        subgroup_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        self.subgroups_listbox = tk.Listbox(
            subgroup_frame, exportselection=False, height=15
        )
        self.subgroups_listbox.pack(fill="both", expand=True, pady=(0, 5))
        self.subgroups_listbox.bind("<<ListboxSelect>>", self.on_subgroup_select)

        subgroup_btn_frame = ttk.Frame(subgroup_frame)
        subgroup_btn_frame.pack(fill="x")
        self.add_subgroup_btn = ttk.Button(
            subgroup_btn_frame,
            text="Nuovo",
            command=self.add_new_subgroup,
            state="disabled",
            width=8,
        )
        self.add_subgroup_btn.pack(side="left", padx=2)
        self.edit_subgroup_btn = ttk.Button(
            subgroup_btn_frame,
            text="Modifica",
            command=self.edit_selected_subgroup,
            state="disabled",
            width=8,
        )
        self.edit_subgroup_btn.pack(side="left", padx=2)
        self.delete_subgroup_btn = ttk.Button(
            subgroup_btn_frame,
            text="Elimina",
            command=self.delete_selected_subgroup,
            state="disabled",
            width=8,
        )
        self.delete_subgroup_btn.pack(side="left", padx=2)

        indicator_frame = ttk.LabelFrame(
            main_frame, text="Indicatori (del sottogruppo selezionato)", padding=10
        )
        indicator_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        self.indicators_listbox = tk.Listbox(
            indicator_frame, exportselection=False, height=15
        )
        self.indicators_listbox.pack(fill="both", expand=True, pady=(0, 5))
        self.indicators_listbox.bind("<<ListboxSelect>>", self.on_indicator_select)

        indicator_btn_frame = ttk.Frame(indicator_frame)
        indicator_btn_frame.pack(fill="x")
        self.add_indicator_btn = ttk.Button(
            indicator_btn_frame,
            text="Nuovo",
            command=self.add_new_indicator,
            state="disabled",
            width=8,
        )
        self.add_indicator_btn.pack(side="left", padx=2)
        self.edit_indicator_btn = ttk.Button(
            indicator_btn_frame,
            text="Modifica",
            command=self.edit_selected_indicator,
            state="disabled",
            width=8,
        )
        self.edit_indicator_btn.pack(side="left", padx=2)
        self.delete_indicator_btn = ttk.Button(
            indicator_btn_frame,
            text="Elimina",
            command=self.delete_selected_indicator,
            state="disabled",
            width=8,
        )
        self.delete_indicator_btn.pack(side="left", padx=2)

    def refresh_kpi_hierarchy_displays(
        self, pre_selected_group_name=None, pre_selected_subgroup_name=None # pre_selected_subgroup_name is raw name
    ):
        if (
            pre_selected_group_name is None
            and hasattr(self, "groups_listbox")
            and self.groups_listbox.curselection()
        ):
            pre_selected_group_name = self.groups_listbox.get(
                self.groups_listbox.curselection()[0]
            )

        true_pre_selected_subgroup_name = pre_selected_subgroup_name # Already raw
        if (
            pre_selected_subgroup_name is None
            and hasattr(self, "subgroups_listbox")
            and self.subgroups_listbox.curselection()
        ):
            full_display_name = self.subgroups_listbox.get(self.subgroups_listbox.curselection()[0])
            true_pre_selected_subgroup_name = full_display_name.split(" (Template:")[0]


        self.groups_listbox.delete(0, tk.END)
        self.current_groups_map = {}
        groups_data = db.get_kpi_groups()
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
            self.on_group_select(pre_selected_subgroup_name=true_pre_selected_subgroup_name)
        else:
            self.on_group_select()

    def on_group_select(self, event=None, pre_selected_subgroup_name=None): # Accepts raw subgroup name
        self.subgroups_listbox.delete(0, tk.END)
        self.indicators_listbox.delete(0, tk.END)
        self.current_subgroups_map = {}
        self.current_subgroups_raw_map = {}
        self.current_indicators_map = {}

        self.add_subgroup_btn.config(state="disabled")
        self.edit_subgroup_btn.config(state="disabled")
        self.delete_subgroup_btn.config(state="disabled")
        self.add_indicator_btn.config(state="disabled")
        self.edit_indicator_btn.config(state="disabled")
        self.delete_indicator_btn.config(state="disabled")

        selection = self.groups_listbox.curselection()
        if not selection:
            self.edit_group_btn.config(state="disabled")
            self.delete_group_btn.config(state="disabled")
            return

        self.edit_group_btn.config(state="normal")
        self.delete_group_btn.config(state="normal")
        group_name = self.groups_listbox.get(selection[0])
        group_id = self.current_groups_map.get(group_name)

        if group_id:
            self.selected_group_id_for_new_subgroup = group_id
            self.add_subgroup_btn.config(state="normal")
            subgroups_data = db.get_kpi_subgroups_by_group_revised(group_id)
            subgroup_selected_idx = -1
            for i, sg in enumerate(subgroups_data):
                raw_sg_name = sg["name"]
                display_name = raw_sg_name
                if sg.get("template_name"):
                    display_name += f" (Template: {sg['template_name']})"
                self.subgroups_listbox.insert(tk.END, display_name)
                self.current_subgroups_map[display_name] = sg["id"] # Map display name to ID
                self.current_subgroups_raw_map[raw_sg_name] = { # Map raw name to details
                    "id": sg["id"], "template_id": sg.get("indicator_template_id"),
                    "template_name": sg.get("template_name")}
                if pre_selected_subgroup_name and raw_sg_name == pre_selected_subgroup_name:
                    subgroup_selected_idx = i
            if subgroup_selected_idx != -1:
                self.subgroups_listbox.selection_set(subgroup_selected_idx)
                self.subgroups_listbox.activate(subgroup_selected_idx)
                self.subgroups_listbox.see(subgroup_selected_idx)
            self.on_subgroup_select()
        else:
            self.add_subgroup_btn.config(state="disabled")

    def on_subgroup_select(self, event=None):
        self.indicators_listbox.delete(0, tk.END)
        self.current_indicators_map = {}
        self.add_indicator_btn.config(state="disabled")
        self.edit_indicator_btn.config(state="disabled")
        self.delete_indicator_btn.config(state="disabled")

        selection = self.subgroups_listbox.curselection()
        if not selection:
            self.edit_subgroup_btn.config(state="disabled")
            self.delete_subgroup_btn.config(state="disabled")
            return

        self.edit_subgroup_btn.config(state="normal")
        self.delete_subgroup_btn.config(state="normal")
        display_subgroup_name = self.subgroups_listbox.get(selection[0])
        subgroup_id = self.current_subgroups_map.get(display_subgroup_name) # Get ID from display name

        if subgroup_id:
            raw_sg_name_for_check = display_subgroup_name.split(" (Template:")[0]
            subgroup_details = self.current_subgroups_raw_map.get(raw_sg_name_for_check)
            is_templated = subgroup_details and subgroup_details.get("template_id") is not None

            if is_templated:
                self.add_indicator_btn.config(state="disabled", text="Nuovo (da Template)")
            else:
                self.add_indicator_btn.config(state="normal", text="Nuovo")

            self.selected_subgroup_id_for_new_indicator = subgroup_id
            for ind in db.get_kpi_indicators_by_subgroup(subgroup_id):
                self.indicators_listbox.insert(tk.END, ind["name"])
                self.current_indicators_map[ind["name"]] = ind["id"]
        self.on_indicator_select()

    def on_indicator_select(self, event=None):
        subgroup_selection = self.subgroups_listbox.curselection()
        is_templated_subgroup = False
        if subgroup_selection:
            display_subgroup_name = self.subgroups_listbox.get(subgroup_selection[0])
            raw_sg_name_for_check = display_subgroup_name.split(" (Template:")[0]
            subgroup_details = self.current_subgroups_raw_map.get(raw_sg_name_for_check)
            is_templated_subgroup = subgroup_details and subgroup_details.get("template_id") is not None

        if self.indicators_listbox.curselection() and not is_templated_subgroup:
            self.edit_indicator_btn.config(state="normal")
            self.delete_indicator_btn.config(state="normal")
        else:
            self.edit_indicator_btn.config(state="disabled")
            self.delete_indicator_btn.config(state="disabled")

    def add_new_group(self):
        name = simpledialog.askstring("Nuovo Gruppo", "Nome del nuovo Gruppo KPI:", parent=self)
        if name:
            try:
                db.add_kpi_group(name)
                self.refresh_all_relevant_data()
                self.after(100, lambda n=name: self._select_item_by_name_and_trigger(self.groups_listbox, n, self.current_groups_map))
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile aggiungere gruppo: {e}")

    def edit_selected_group(self):
        selection = self.groups_listbox.curselection()
        if not selection: return
        old_name = self.groups_listbox.get(selection[0])
        group_id = self.current_groups_map.get(old_name)
        new_name = simpledialog.askstring("Modifica Gruppo", "Nuovo nome per il Gruppo:", initialvalue=old_name, parent=self)
        if new_name and new_name != old_name:
            try:
                db.update_kpi_group(group_id, new_name)
                self.refresh_all_relevant_data()
                self.after(100, lambda n=new_name: self._select_item_by_name_and_trigger(self.groups_listbox, n, self.current_groups_map))
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile modificare gruppo: {e}")

    def _select_item_by_name_and_trigger(self, listbox, item_name, item_map_for_id_lookup_if_needed):
        listbox.selection_clear(0, tk.END)
        for i in range(listbox.size()):
            current_lb_item_display = listbox.get(i)
            raw_lb_item_name = current_lb_item_display.split(" (Template:")[0]
            if raw_lb_item_name == item_name or current_lb_item_display == item_name:
                listbox.selection_set(i)
                listbox.activate(i)
                listbox.see(i)
                listbox.event_generate("<<ListboxSelect>>")
                break

    def delete_selected_group(self):
        selection = self.groups_listbox.curselection()
        if not selection: return
        name_to_delete = self.groups_listbox.get(selection[0])
        group_id = self.current_groups_map.get(name_to_delete)
        if messagebox.askyesno("Conferma Eliminazione", f"Sei sicuro di voler eliminare il gruppo '{name_to_delete}'?\nATTENZIONE: Questo eliminerà anche tutti i sottogruppi, indicatori, specifiche KPI e target associati a questo gruppo.", parent=self):
            try:
                db.delete_kpi_group(group_id)
                self.refresh_all_relevant_data()
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile eliminare gruppo: {e}")

    def add_new_subgroup(self):
        group_selection = self.groups_listbox.curselection()
        if not group_selection:
            messagebox.showwarning("Attenzione", "Seleziona prima un gruppo.")
            return
        group_name_for_refresh = self.groups_listbox.get(group_selection[0])
        group_id = self.current_groups_map.get(group_name_for_refresh)
        if not group_id: return

        dialog = SubgroupEditorDialog(self, title="Nuovo Sottogruppo", group_id_context=group_id)
        if dialog.result_name and dialog.result_template_id is not False:
            new_name = dialog.result_name
            selected_template_id = dialog.result_template_id
            try:
                db.add_kpi_subgroup(new_name, group_id, selected_template_id)
                self.refresh_all_relevant_data()
                self.after(100, lambda gn=group_name_for_refresh, sgn=new_name: self._select_hierarchy_and_indicator(gn, sgn, None, select_subgroup_only=True))
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile aggiungere sottogruppo: {e}\n{traceback.format_exc()}")

    def edit_selected_subgroup(self):
        group_selection = self.groups_listbox.curselection()
        subgroup_selection = self.subgroups_listbox.curselection()
        if not group_selection or not subgroup_selection: return

        group_name_for_refresh = self.groups_listbox.get(group_selection[0])
        group_id = self.current_groups_map.get(group_name_for_refresh)
        display_name_subgroup = self.subgroups_listbox.get(subgroup_selection[0])
        old_raw_name = display_name_subgroup.split(" (Template:")[0]
        subgroup_details_for_edit = self.current_subgroups_raw_map.get(old_raw_name)

        if not subgroup_details_for_edit or not group_id:
            messagebox.showerror("Errore", "Impossibile trovare dettagli sottogruppo per modifica.")
            return
        subgroup_id_to_edit = subgroup_details_for_edit["id"]
        current_template_id = subgroup_details_for_edit.get("template_id")

        dialog = SubgroupEditorDialog(self, title="Modifica Sottogruppo", group_id_context=group_id, initial_name=old_raw_name, initial_template_id=current_template_id)
        if dialog.result_name and dialog.result_template_id is not False:
            new_name = dialog.result_name
            new_template_id = dialog.result_template_id
            if new_name != old_raw_name or new_template_id != current_template_id:
                try:
                    db.update_kpi_subgroup(subgroup_id_to_edit, new_name, group_id, new_template_id)
                    self.refresh_all_relevant_data()
                    self.after(100, lambda gn=group_name_for_refresh, sgn=new_name: self._select_hierarchy_and_indicator(gn, sgn, None, select_subgroup_only=True))
                except Exception as e:
                    messagebox.showerror("Errore", f"Impossibile modificare sottogruppo: {e}\n{traceback.format_exc()}")

    def delete_selected_subgroup(self):
        group_selection = self.groups_listbox.curselection()
        subgroup_selection = self.subgroups_listbox.curselection()
        if not subgroup_selection: return

        display_name_to_delete = self.subgroups_listbox.get(subgroup_selection[0])
        raw_name_confirm = display_name_to_delete.split(" (Template:")[0]
        subgroup_id = self.current_subgroups_map.get(display_name_to_delete)
        group_name_for_refresh = (self.groups_listbox.get(group_selection[0]) if group_selection else None)

        if messagebox.askyesno("Conferma Eliminazione", f"Sei sicuro di voler eliminare il sottogruppo '{raw_name_confirm}'?\nATTENZIONE: Questo eliminerà anche tutti gli indicatori, specifiche KPI e target associati.", parent=self):
            try:
                db.delete_kpi_subgroup(subgroup_id)
                self.refresh_all_relevant_data()
                if group_name_for_refresh:
                    self.after(100, lambda: self._select_item_by_name_and_trigger(self.groups_listbox, group_name_for_refresh, self.current_groups_map))
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile eliminare sottogruppo: {e}")

    def add_new_indicator(self):
        subgroup_selection = self.subgroups_listbox.curselection()
        if not subgroup_selection:
            messagebox.showwarning("Attenzione", "Seleziona prima un sottogruppo.")
            return
        display_subgroup_name = self.subgroups_listbox.get(subgroup_selection[0])
        raw_subgroup_name_for_refresh = display_subgroup_name.split(" (Template:")[0]
        subgroup_id = self.current_subgroups_map.get(display_subgroup_name)
        if not subgroup_id: return

        subgroup_details = self.current_subgroups_raw_map.get(raw_subgroup_name_for_refresh)
        if subgroup_details and subgroup_details.get("template_id") is not None:
            messagebox.showinfo("Info", "Gli indicatori per questo sottogruppo sono gestiti dal template associato.", parent=self)
            return

        group_name_for_refresh = (self.groups_listbox.get(self.groups_listbox.curselection()[0]) if self.groups_listbox.curselection() else None)
        name = simpledialog.askstring("Nuovo Indicatore", "Nome del nuovo Indicatore KPI:", parent=self)
        if name:
            try:
                db.add_kpi_indicator(name, subgroup_id)
                self.refresh_all_relevant_data()
                self.after(100, lambda gn=group_name_for_refresh, sgn=raw_subgroup_name_for_refresh, indn=name: self._select_hierarchy_and_indicator(gn, sgn, indn))
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile aggiungere indicatore: {e}")

    def _select_hierarchy_and_indicator(self, group_name, subgroup_raw_name, indicator_name, select_subgroup_only=False):
        if group_name:
            for i in range(self.groups_listbox.size()):
                if self.groups_listbox.get(i) == group_name:
                    self.groups_listbox.selection_set(i)
                    self.groups_listbox.event_generate("<<ListboxSelect>>")
                    self.after(50, lambda sgn=subgroup_raw_name, indn=indicator_name, sgo=select_subgroup_only: self._select_subgroup_and_indicator(sgn, indn, sgo))
                    break

    def _select_subgroup_and_indicator(self, subgroup_raw_name, indicator_name, select_subgroup_only=False):
        if subgroup_raw_name:
            for i in range(self.subgroups_listbox.size()):
                display_sg_name = self.subgroups_listbox.get(i)
                raw_sg_name_in_list = display_sg_name.split(" (Template:")[0]
                if raw_sg_name_in_list == subgroup_raw_name:
                    self.subgroups_listbox.selection_set(i)
                    self.subgroups_listbox.event_generate("<<ListboxSelect>>")
                    if not select_subgroup_only and indicator_name:
                        self.after(50, lambda indn=indicator_name: self._select_new_item_in_listbox(self.indicators_listbox, indn))
                    break

    def _select_new_item_in_listbox(self, listbox, item_name):
        listbox.selection_clear(0, tk.END)
        for i in range(listbox.size()):
            if listbox.get(i) == item_name:
                listbox.selection_set(i)
                listbox.activate(i)
                listbox.see(i)
                listbox.event_generate("<<ListboxSelect>>")
                break

    def edit_selected_indicator(self):
        # ... (Implementation as before, ensuring to check if subgroup is templated)
        group_selection = self.groups_listbox.curselection()
        subgroup_selection = self.subgroups_listbox.curselection()
        indicator_selection = self.indicators_listbox.curselection()
        if not subgroup_selection or not indicator_selection: return

        old_name = self.indicators_listbox.get(indicator_selection[0])
        indicator_id = self.current_indicators_map.get(old_name)

        display_subgroup_name = self.subgroups_listbox.get(subgroup_selection[0])
        raw_subgroup_name_for_refresh = display_subgroup_name.split(" (Template:")[0]
        subgroup_id = self.current_subgroups_map.get(display_subgroup_name) # ID from display name
        
        group_name_for_refresh = (self.groups_listbox.get(group_selection[0]) if group_selection else None)

        subgroup_details = self.current_subgroups_raw_map.get(raw_subgroup_name_for_refresh)
        if subgroup_details and subgroup_details.get("template_id") is not None:
            messagebox.showinfo("Info", "Indicatori gestiti da template. Modifica il template.", parent=self)
            return

        new_name = simpledialog.askstring("Modifica Indicatore", "Nuovo nome:", initialvalue=old_name, parent=self)
        if new_name and new_name != old_name:
            try:
                db.update_kpi_indicator(indicator_id, new_name, subgroup_id)
                self.refresh_all_relevant_data()
                self.after(100, lambda gn=group_name_for_refresh, sgn=raw_subgroup_name_for_refresh, indn=new_name: self._select_hierarchy_and_indicator(gn, sgn, indn))
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile modificare indicatore: {e}")

    def delete_selected_indicator(self):
        # ... (Implementation as before, ensuring to check if subgroup is templated)
        indicator_selection = self.indicators_listbox.curselection()
        if not indicator_selection: return
        name_to_delete = self.indicators_listbox.get(indicator_selection[0])
        indicator_id = self.current_indicators_map.get(name_to_delete)

        group_name_for_refresh, subgroup_name_for_refresh_raw = None, None
        if self.groups_listbox.curselection():
            group_name_for_refresh = self.groups_listbox.get(self.groups_listbox.curselection()[0])
        if self.subgroups_listbox.curselection():
            display_sg_name = self.subgroups_listbox.get(self.subgroups_listbox.curselection()[0])
            subgroup_name_for_refresh_raw = display_sg_name.split(" (Template:")[0]
        
        if subgroup_name_for_refresh_raw:
            subgroup_details = self.current_subgroups_raw_map.get(subgroup_name_for_refresh_raw)
            if subgroup_details and subgroup_details.get("template_id") is not None:
                messagebox.showinfo("Info", "Indicatori gestiti da template. Rimuovi dal template.", parent=self)
                return

        if messagebox.askyesno("Conferma Eliminazione", f"Sei sicuro di voler eliminare l'indicatore '{name_to_delete}'?\nATTENZIONE: Questo eliminerà anche la specifica KPI e tutti i target associati.", parent=self):
            try:
                db.delete_kpi_indicator(indicator_id)
                self.refresh_all_relevant_data()
                if group_name_for_refresh and subgroup_name_for_refresh_raw:
                    self.after(100, lambda gn=group_name_for_refresh, sgn=subgroup_name_for_refresh_raw: self._select_hierarchy_and_indicator(gn, sgn, None, select_subgroup_only=True))
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile eliminare indicatore: {e}")

    # --- Scheda Gestione Template Indicatori ---
    def create_kpi_template_widgets(self):
        main_frame = ttk.Frame(self.kpi_template_frame)
        main_frame.pack(fill="both", expand=True)

        template_list_frame = ttk.LabelFrame(main_frame, text="Template Indicatori KPI", padding=10)
        template_list_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.templates_listbox = tk.Listbox(template_list_frame, exportselection=False, height=15)
        self.templates_listbox.pack(fill="both", expand=True, pady=(0, 5))
        self.templates_listbox.bind("<<ListboxSelect>>", self.on_template_select)
        template_btn_frame = ttk.Frame(template_list_frame)
        template_btn_frame.pack(fill="x")
        ttk.Button(template_btn_frame, text="Nuovo Template", command=self.add_new_kpi_template, width=15).pack(side="left", padx=2)
        self.edit_template_btn = ttk.Button(template_btn_frame, text="Modifica Template", command=self.edit_selected_kpi_template, state="disabled", width=15)
        self.edit_template_btn.pack(side="left", padx=2)
        self.delete_template_btn = ttk.Button(template_btn_frame, text="Elimina Template", command=self.delete_selected_kpi_template, state="disabled", width=15)
        self.delete_template_btn.pack(side="left", padx=2)

        definitions_frame = ttk.LabelFrame(main_frame, text="Definizioni Indicatori (del template selezionato)", padding=10)
        definitions_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.template_definitions_tree = ttk.Treeview(definitions_frame, columns=("ID", "Nome Indicatore", "Tipo Calcolo", "Unità", "Visibile", "Descrizione"), show="headings", height=14)
        cols_widths_def = {"ID": 40, "Nome Indicatore": 150, "Tipo Calcolo": 100, "Unità": 80, "Visibile": 60, "Descrizione": 200}
        for col_name in self.template_definitions_tree["columns"]:
            self.template_definitions_tree.heading(col_name, text=col_name)
            anchor = "center" if col_name in ["ID", "Visibile"] else "w"
            self.template_definitions_tree.column(col_name, width=cols_widths_def.get(col_name, 100), anchor=anchor, stretch=(col_name=="Descrizione" or col_name=="Nome Indicatore"))
        self.template_definitions_tree.pack(fill="both", expand=True, pady=(0,5))
        self.template_definitions_tree.bind("<<TreeviewSelect>>", self.on_template_definition_select)
        definition_btn_frame = ttk.Frame(definitions_frame)
        definition_btn_frame.pack(fill="x")
        self.add_definition_btn = ttk.Button(definition_btn_frame, text="Aggiungi Definizione", command=self.add_new_template_definition, state="disabled", width=18)
        self.add_definition_btn.pack(side="left", padx=2)
        self.edit_definition_btn = ttk.Button(definition_btn_frame, text="Modifica Definizione", command=self.edit_selected_template_definition, state="disabled", width=18)
        self.edit_definition_btn.pack(side="left", padx=2)
        self.remove_definition_btn = ttk.Button(definition_btn_frame, text="Rimuovi Definizione", command=self.remove_selected_template_definition, state="disabled", width=18)
        self.remove_definition_btn.pack(side="left", padx=2)
        self.current_templates_map = {}
        self.current_template_definitions_map = {}

    def refresh_kpi_templates_display(self, pre_selected_template_name=None):
        if pre_selected_template_name is None and hasattr(self, "templates_listbox") and self.templates_listbox.curselection():
            pre_selected_template_name = self.templates_listbox.get(self.templates_listbox.curselection()[0])
        self.templates_listbox.delete(0, tk.END)
        self.current_templates_map.clear()
        templates_data = db.get_kpi_indicator_templates()
        template_selected_idx = -1
        for i, template in enumerate(templates_data):
            self.templates_listbox.insert(tk.END, template["name"])
            self.current_templates_map[template["name"]] = template["id"]
            if template["name"] == pre_selected_template_name: template_selected_idx = i
        if template_selected_idx != -1:
            self.templates_listbox.selection_set(template_selected_idx)
            self.templates_listbox.activate(template_selected_idx)
            self.templates_listbox.see(template_selected_idx)
        self.on_template_select()

    def on_template_select(self, event=None):
        for i in self.template_definitions_tree.get_children(): self.template_definitions_tree.delete(i)
        self.current_template_definitions_map.clear()
        self.edit_template_btn.config(state="disabled")
        self.delete_template_btn.config(state="disabled")
        self.add_definition_btn.config(state="disabled")
        self.edit_definition_btn.config(state="disabled")
        self.remove_definition_btn.config(state="disabled")
        selection = self.templates_listbox.curselection()
        if not selection: return
        self.edit_template_btn.config(state="normal")
        self.delete_template_btn.config(state="normal")
        self.add_definition_btn.config(state="normal")
        template_name = self.templates_listbox.get(selection[0])
        template_id = self.current_templates_map.get(template_name)
        if template_id:
            definitions = db.get_template_defined_indicators(template_id)
            for defi in definitions:
                iid = self.template_definitions_tree.insert("", "end", values=(defi["id"], defi["indicator_name_in_template"], defi["default_calculation_type"], defi["default_unit_of_measure"] or "", "Sì" if defi["default_visible"] else "No", defi["default_description"] or ""))
                self.current_template_definitions_map[iid] = defi["id"]
        self.on_template_definition_select()

    def on_template_definition_select(self, event=None):
        if self.template_definitions_tree.selection():
            self.edit_definition_btn.config(state="normal")
            self.remove_definition_btn.config(state="normal")
        else:
            self.edit_definition_btn.config(state="disabled")
            self.remove_definition_btn.config(state="disabled")

    def add_new_kpi_template(self):
        name = simpledialog.askstring("Nuovo Template", "Nome del nuovo Template Indicatori:", parent=self)
        if name:
            desc = simpledialog.askstring("Nuovo Template", "Descrizione (opzionale):", parent=self)
            desc = desc if desc else ""
            try:
                db.add_kpi_indicator_template(name, desc)
                self.refresh_kpi_templates_display(pre_selected_template_name=name)
            except Exception as e: messagebox.showerror("Errore", f"Impossibile aggiungere template: {e}")

    def edit_selected_kpi_template(self):
        selection = self.templates_listbox.curselection()
        if not selection: return
        old_name = self.templates_listbox.get(selection[0])
        template_id = self.current_templates_map.get(old_name)
        template_data = db.get_kpi_indicator_template_by_id(template_id)
        if not template_data: return
        new_name = simpledialog.askstring("Modifica Template", "Nuovo nome:", initialvalue=old_name, parent=self)
        if new_name:
            new_desc = simpledialog.askstring("Modifica Template", "Nuova descrizione:", initialvalue=template_data["description"], parent=self)
            new_desc = new_desc if new_desc is not None else template_data["description"]
            if new_name != old_name or new_desc != template_data["description"]:
                try:
                    db.update_kpi_indicator_template(template_id, new_name, new_desc)
                    self.refresh_kpi_templates_display(pre_selected_template_name=new_name)
                except Exception as e: messagebox.showerror("Errore", f"Impossibile modificare template: {e}")

    def delete_selected_kpi_template(self):
        selection = self.templates_listbox.curselection()
        if not selection: return
        name_to_delete = self.templates_listbox.get(selection[0])
        template_id = self.current_templates_map.get(name_to_delete)
        if messagebox.askyesno("Conferma Eliminazione", f"Sei sicuro di voler eliminare il template '{name_to_delete}'?\nQuesto rimuoverà tutte le sue definizioni di indicatori.\nI sottogruppi che usano questo template verranno scollegati.", parent=self):
            try:
                db.delete_kpi_indicator_template(template_id)
                self.refresh_kpi_templates_display()
                self.refresh_all_relevant_data()
            except Exception as e: messagebox.showerror("Errore", f"Impossibile eliminare template: {e}")

    def add_new_template_definition(self):
        template_selection = self.templates_listbox.curselection()
        if not template_selection:
            messagebox.showwarning("Attenzione", "Seleziona prima un template.")
            return
        template_name = self.templates_listbox.get(template_selection[0])
        template_id = self.current_templates_map.get(template_name)
        dialog = TemplateDefinitionEditorDialog(self, title="Nuova Definizione Indicatore", template_id_context=template_id)
        if dialog.result_data:
            data = dialog.result_data
            try:
                db.add_indicator_definition_to_template(template_id, data["name"], data["calc_type"], data["unit"], data["visible"], data["desc"])
                self.on_template_select()
                self.refresh_all_relevant_data()
            except Exception as e: messagebox.showerror("Errore", f"Impossibile aggiungere definizione: {e}\n{traceback.format_exc()}")

    def edit_selected_template_definition(self):
        template_selection = self.templates_listbox.curselection()
        definition_selection = self.template_definitions_tree.selection()
        if not template_selection or not definition_selection: return
        template_id = self.current_templates_map.get(self.templates_listbox.get(template_selection[0]))
        definition_id_to_edit = self.current_template_definitions_map.get(definition_selection[0])
        current_def_data_row = db.get_template_indicator_definition_by_id(definition_id_to_edit)
        if not current_def_data_row:
            messagebox.showerror("Errore", "Definizione non trovata per la modifica.")
            return
        dialog = TemplateDefinitionEditorDialog(self, title="Modifica Definizione Indicatore", template_id_context=template_id, initial_data=current_def_data_row)
        if dialog.result_data:
            data = dialog.result_data
            try:
                db.update_indicator_definition_in_template(definition_id_to_edit, data["name"], data["calc_type"], data["unit"], data["visible"], data["desc"])
                self.on_template_select()
                self.refresh_all_relevant_data()
            except Exception as e: messagebox.showerror("Errore", f"Impossibile modificare definizione: {e}\n{traceback.format_exc()}")

    def remove_selected_template_definition(self):
        definition_selection = self.template_definitions_tree.selection()
        if not definition_selection: return
        definition_id_to_remove = self.current_template_definitions_map.get(definition_selection[0])
        def_name_for_confirm = self.template_definitions_tree.item(definition_selection[0], "values")[1]
        if messagebox.askyesno("Conferma Rimozione", f"Sei sicuro di voler rimuovere la definizione '{def_name_for_confirm}' dal template?\nQuesto rimuoverà l'indicatore e i dati dai sottogruppi che usano questo template.", parent=self):
            try:
                db.remove_indicator_definition_from_template(definition_id_to_remove)
                self.on_template_select()
                self.refresh_all_relevant_data()
            except Exception as e: messagebox.showerror("Errore", f"Impossibile rimuovere definizione: {e}\n{traceback.format_exc()}")
    
    # --- END Scheda Gestione Template Indicatori ---

    # --- Scheda Gestione Specifiche KPI ---
    # ... (Code for create_kpi_spec_widgets and its helpers) ...
    # This section is largely unchanged from your provided code,
    # except for the refresh_kpi_specs_tree to potentially show template name.
    # For brevity, I am not repeating it all here, but it should be included.
    # The crucial part is that refresh_kpi_specs_tree and populate_kpi_spec_hier_combos
    # are aware of the display names of subgroups possibly including template info.
    # (The existing implementation for these methods already handles this by using the revised
    # get_kpi_subgroups_by_group_revised or similar logic for fetching subgroup display names)

    # ... (Content of create_kpi_spec_widgets, on_kpi_spec_group_selected_ui_driven, etc. up to on_kpi_spec_double_click)
    # The following methods are copied from your provided code, with minor adjustments if needed for template display

    def create_kpi_spec_widgets(self):
        add_kpi_frame_outer = ttk.LabelFrame(
            self.kpi_spec_frame, text="Aggiungi/Modifica Specifica KPI", padding=10
        )
        add_kpi_frame_outer.pack(fill="x", pady=10)

        hier_frame = ttk.Frame(add_kpi_frame_outer)
        hier_frame.pack(fill="x", pady=5)
        ttk.Label(hier_frame, text="Gruppo:").pack(side="left")
        self.kpi_spec_group_var = tk.StringVar()
        self.kpi_spec_group_cb = ttk.Combobox(
            hier_frame, textvariable=self.kpi_spec_group_var, state="readonly", width=20
        )
        self.kpi_spec_group_cb.pack(side="left", padx=5)
        self.kpi_spec_group_cb.bind(
            "<<ComboboxSelected>>", self.on_kpi_spec_group_selected_ui_driven
        )

        ttk.Label(hier_frame, text="Sottogruppo:").pack(side="left")
        self.kpi_spec_subgroup_var = tk.StringVar()
        self.kpi_spec_subgroup_cb = ttk.Combobox(
            hier_frame,
            textvariable=self.kpi_spec_subgroup_var,
            state="readonly",
            width=28 # Wider to accommodate template name
        )
        self.kpi_spec_subgroup_cb.pack(side="left", padx=5)
        self.kpi_spec_subgroup_cb.bind(
            "<<ComboboxSelected>>", self.on_kpi_spec_subgroup_selected_ui_driven
        )

        ttk.Label(hier_frame, text="Indicatore:").pack(side="left")
        self.kpi_spec_indicator_var = tk.StringVar()
        self.kpi_spec_indicator_cb = ttk.Combobox(
            hier_frame,
            textvariable=self.kpi_spec_indicator_var,
            state="readonly",
            width=25,
        )
        self.kpi_spec_indicator_cb.pack(side="left", padx=5)
        self.kpi_spec_indicator_cb.bind(
            "<<ComboboxSelected>>", self.on_kpi_spec_indicator_selected_ui_driven
        )

        attr_frame = ttk.Frame(add_kpi_frame_outer)
        attr_frame.pack(fill="x", pady=5)
        ttk.Label(attr_frame, text="Descrizione:").grid(
            row=0, column=0, sticky="w", padx=5, pady=2
        )
        self.kpi_spec_desc_var = tk.StringVar()
        ttk.Entry(attr_frame, textvariable=self.kpi_spec_desc_var, width=40).grid(
            row=0, column=1, padx=5, pady=2, sticky="ew"
        )
        attr_frame.columnconfigure(1, weight=1)

        ttk.Label(attr_frame, text="Tipo Calcolo:").grid(
            row=1, column=0, sticky="w", padx=5, pady=2
        )
        self.kpi_spec_type_var = tk.StringVar(value="Incrementale")
        ttk.Combobox(
            attr_frame,
            textvariable=self.kpi_spec_type_var,
            values=["Incrementale", "Media"],
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(attr_frame, text="Unità Misura:").grid(
            row=2, column=0, sticky="w", padx=5, pady=2
        )
        self.kpi_spec_unit_var = tk.StringVar()
        ttk.Entry(attr_frame, textvariable=self.kpi_spec_unit_var, width=40).grid(
            row=2, column=1, padx=5, pady=2, sticky="ew"
        )

        self.kpi_spec_visible_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            attr_frame,
            text="Visibile per Inserimento Target",
            variable=self.kpi_spec_visible_var,
        ).grid(row=3, column=1, sticky="w", padx=5, pady=2)

        self.current_editing_kpi_id = None

        kpi_spec_btn_frame_outer = ttk.Frame(add_kpi_frame_outer)
        kpi_spec_btn_frame_outer.pack(pady=10)
        kpi_spec_btn_frame = ttk.Frame(kpi_spec_btn_frame_outer)
        kpi_spec_btn_frame.pack()

        self.save_kpi_spec_btn = ttk.Button(
            kpi_spec_btn_frame,
            text="Aggiungi Specifica KPI",
            command=self.save_kpi_specification,
            style="Accent.TButton",
        )
        self.save_kpi_spec_btn.pack(side="left", padx=5)
        ttk.Button(
            kpi_spec_btn_frame,
            text="Pulisci Campi",
            command=self.clear_kpi_spec_fields_button_action,
        ).pack(side="left", padx=5)

        tree_frame = ttk.Frame(self.kpi_spec_frame)
        tree_frame.pack(expand=True, fill="both", pady=(10, 0))

        self.kpi_specs_tree = ttk.Treeview(
            tree_frame,
            columns=(
                "ID", "Gruppo", "Sottogruppo", "Indicatore", "Descrizione",
                "Tipo Calcolo", "Unità Misura", "Visibile", "Template Sottogruppo"
            ),
            show="headings",
        )
        cols_widths = {
            "ID": 40, "Gruppo": 110, "Sottogruppo": 130, "Indicatore": 130,
            "Descrizione": 160, "Tipo Calcolo": 90, "Unità Misura": 80,
            "Visibile": 60, "Template Sottogruppo": 120
        }
        for col_name in self.kpi_specs_tree["columns"]:
            self.kpi_specs_tree.heading(col_name, text=col_name)
            anchor = "center" if col_name in ["ID", "Visibile"] else "w"
            stretch = tk.NO if col_name in ["ID", "Visibile", "Tipo Calcolo", "Unità Misura"] else tk.YES
            self.kpi_specs_tree.column(col_name, width=cols_widths.get(col_name, 100), anchor=anchor, stretch=stretch)

        tree_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.kpi_specs_tree.yview)
        self.kpi_specs_tree.configure(yscrollcommand=tree_scrollbar.set)
        tree_scrollbar.pack(side="right", fill="y")
        self.kpi_specs_tree.pack(side="left", expand=True, fill="both")
        self.kpi_specs_tree.bind("<Double-1>", self.on_kpi_spec_double_click)

        tree_buttons_frame = ttk.Frame(self.kpi_spec_frame)
        tree_buttons_frame.pack(fill="x", pady=5)
        ttk.Button(tree_buttons_frame, text="Elimina Specifica Selezionata", command=self.delete_selected_kpi_spec).pack(side="left", padx=5)


    def on_kpi_spec_group_selected_ui_driven(self, event=None):
        if self._populating_kpi_spec_combos: return
        self._populate_kpi_spec_subgroups()

    def on_kpi_spec_subgroup_selected_ui_driven(self, event=None):
        if self._populating_kpi_spec_combos: return
        self._populate_kpi_spec_indicators()

    def on_kpi_spec_indicator_selected_ui_driven(self, event=None):
        if self._populating_kpi_spec_combos: return
        self._load_or_prepare_kpi_spec_fields()

    def populate_kpi_spec_hier_combos(self, group_to_select=None, subgroup_to_select=None, indicator_to_select=None): # subgroup_to_select is raw name
        self._populating_kpi_spec_combos = True
        self.groups_for_kpi_spec = db.get_kpi_groups()
        group_names = [g["name"] for g in self.groups_for_kpi_spec]
        self.kpi_spec_group_cb["values"] = group_names
        if group_to_select and group_to_select in group_names:
            self.kpi_spec_group_var.set(group_to_select)
            self._populate_kpi_spec_subgroups(subgroup_to_select, indicator_to_select)
        else:
            self.kpi_spec_group_var.set("")
            self.kpi_spec_subgroup_var.set("")
            self.kpi_spec_indicator_var.set("")
            self.kpi_spec_subgroup_cb["values"] = []
            self.kpi_spec_indicator_cb["values"] = []
            self.selected_indicator_id_for_spec = None
            self.clear_kpi_spec_fields(keep_hierarchy=False)
        self._populating_kpi_spec_combos = False

    def _populate_kpi_spec_subgroups(self, subgroup_to_select_raw=None, pre_selected_indicator_name=None): # Accepts raw subgroup name
        group_name = self.kpi_spec_group_var.get()
        self.kpi_spec_subgroup_cb["values"] = []
        self.kpi_spec_indicator_cb["values"] = []
        if not subgroup_to_select_raw: self.kpi_spec_subgroup_var.set("")
        if not pre_selected_indicator_name: self.kpi_spec_indicator_var.set("")

        selected_group = next((g for g in self.groups_for_kpi_spec if g["name"] == group_name), None)
        if selected_group:
            self.subgroups_for_kpi_spec_details = db.get_kpi_subgroups_by_group_revised(selected_group["id"])
            self.subgroup_display_to_raw_map_spec = {}
            display_subgroup_names = []
            for sg_dict in self.subgroups_for_kpi_spec_details:
                raw_name = sg_dict["name"]
                display_name = raw_name + (f" (Template: {sg_dict['template_name']})" if sg_dict.get("template_name") else "")
                display_subgroup_names.append(display_name)
                self.subgroup_display_to_raw_map_spec[display_name] = raw_name
            self.kpi_spec_subgroup_cb["values"] = display_subgroup_names

            target_display_subgroup = None
            if subgroup_to_select_raw:
                for disp_name, raw_name_mapped in self.subgroup_display_to_raw_map_spec.items():
                    if raw_name_mapped == subgroup_to_select_raw:
                        target_display_subgroup = disp_name
                        break
            if target_display_subgroup:
                self.kpi_spec_subgroup_var.set(target_display_subgroup)
                self._populate_kpi_spec_indicators(pre_selected_indicator_name)
            elif not self._populating_kpi_spec_combos and not subgroup_to_select_raw:
                 self.clear_kpi_spec_fields(keep_hierarchy=True, keep_group=True)
        elif not self._populating_kpi_spec_combos:
            self.clear_kpi_spec_fields(keep_hierarchy=True)

    def _populate_kpi_spec_indicators(self, pre_selected_indicator_name=None):
        display_subgroup_name = self.kpi_spec_subgroup_var.get()
        self.kpi_spec_indicator_cb["values"] = []
        if not pre_selected_indicator_name: self.kpi_spec_indicator_var.set("")

        raw_subgroup_name = self.subgroup_display_to_raw_map_spec.get(display_subgroup_name)
        selected_subgroup_obj = None
        if raw_subgroup_name and hasattr(self, "subgroups_for_kpi_spec_details"):
            selected_subgroup_obj = next((sg for sg in self.subgroups_for_kpi_spec_details if sg["name"] == raw_subgroup_name), None)
        
        if selected_subgroup_obj:
            self.indicators_for_kpi_spec = db.get_kpi_indicators_by_subgroup(selected_subgroup_obj["id"])
            indicator_names = [ind["name"] for ind in self.indicators_for_kpi_spec]
            self.kpi_spec_indicator_cb["values"] = indicator_names
            if pre_selected_indicator_name and pre_selected_indicator_name in indicator_names:
                self.kpi_spec_indicator_var.set(pre_selected_indicator_name)
                if self._populating_kpi_spec_combos: self._load_or_prepare_kpi_spec_fields()
            elif not self._populating_kpi_spec_combos and not pre_selected_indicator_name:
                 self.clear_kpi_spec_fields(keep_hierarchy=True, keep_group=True, keep_subgroup=True)
        elif not self._populating_kpi_spec_combos:
            self.clear_kpi_spec_fields(keep_hierarchy=True, keep_group=True)

    def _load_or_prepare_kpi_spec_fields(self):
        # ... (Content as before)
        indicator_name = self.kpi_spec_indicator_var.get()
        self.selected_indicator_id_for_spec = None
        self.current_editing_kpi_id = None
        self.save_kpi_spec_btn.config(text="Aggiungi Specifica KPI")

        selected_indicator_obj = None
        if hasattr(self, "indicators_for_kpi_spec") and self.indicators_for_kpi_spec:
            selected_indicator_obj = next((ind for ind in self.indicators_for_kpi_spec if ind["name"] == indicator_name),None)

        if selected_indicator_obj:
            self.selected_indicator_id_for_spec = selected_indicator_obj["id"]
            all_kpi_specs = db.get_kpis()
            existing_kpi_spec = next((kpi for kpi in all_kpi_specs if kpi["indicator_id"] == self.selected_indicator_id_for_spec), None)
            if existing_kpi_spec:
                self._set_kpi_spec_fields_from_data(existing_kpi_spec)
                self.current_editing_kpi_id = existing_kpi_spec["id"]
                self.save_kpi_spec_btn.config(text="Modifica Specifica KPI")
            else:
                self.clear_kpi_spec_fields(keep_hierarchy=True, keep_group=True, keep_subgroup=True, keep_indicator=True)
        else:
            self.clear_kpi_spec_fields(keep_hierarchy=True, keep_group=True, keep_subgroup=True, keep_indicator=False)


    def _set_kpi_spec_fields_from_data(self, kpi_data): # kpi_data is a dict/Row
        self.kpi_spec_desc_var.set(kpi_data["description"] or "")
        self.kpi_spec_type_var.set(kpi_data["calculation_type"] or "Incrementale")
        self.kpi_spec_unit_var.set(kpi_data["unit_of_measure"] or "")
        self.kpi_spec_visible_var.set(bool(kpi_data["visible"]))

    def load_kpi_spec_for_editing(self, kpi_data_full): # kpi_data_full from db.get_kpi_by_id()
        # ... (Content as before, using raw subgroup name for populate_kpi_spec_hier_combos)
        self._populating_kpi_spec_combos = True
        self.current_editing_kpi_id = kpi_data_full["id"]
        self.selected_indicator_id_for_spec = kpi_data_full["actual_indicator_id"] # i.id
        self.populate_kpi_spec_hier_combos(
            group_to_select=kpi_data_full["group_name"],
            subgroup_to_select=kpi_data_full["subgroup_name"], # raw name
            indicator_to_select=kpi_data_full["indicator_name"])
        self._populating_kpi_spec_combos = False
        if self.kpi_spec_indicator_var.get() == kpi_data_full["indicator_name"]:
             self._load_or_prepare_kpi_spec_fields()


    def clear_kpi_spec_fields_button_action(self):
        # ... (Content as before)
        self._populating_kpi_spec_combos = True
        self.kpi_spec_group_var.set("")
        self.kpi_spec_subgroup_var.set("") # This is display name, will be cleared by populate
        self.kpi_spec_indicator_var.set("")
        self.kpi_spec_subgroup_cb["values"] = []
        self.kpi_spec_indicator_cb["values"] = []
        self.clear_kpi_spec_fields(keep_hierarchy=False)
        self._populating_kpi_spec_combos = False
        self.populate_kpi_spec_hier_combos() # Re-initiate population from scratch

    def clear_kpi_spec_fields(self, keep_hierarchy=False, keep_group=False, keep_subgroup=False, keep_indicator=False):
        # ... (Content as before)
        if not keep_hierarchy:
            if not self._populating_kpi_spec_combos or not keep_group : self.kpi_spec_group_var.set("")
            if not self._populating_kpi_spec_combos or not keep_subgroup: self.kpi_spec_subgroup_var.set("")
            if not self._populating_kpi_spec_combos or not keep_indicator: self.kpi_spec_indicator_var.set("")
            self.selected_indicator_id_for_spec = None
        elif not keep_group:
            if not self._populating_kpi_spec_combos: self.kpi_spec_group_var.set("")
            if not self._populating_kpi_spec_combos or not keep_subgroup: self.kpi_spec_subgroup_var.set("")
            if not self._populating_kpi_spec_combos or not keep_indicator: self.kpi_spec_indicator_var.set("")
            self.selected_indicator_id_for_spec = None
        elif not keep_subgroup:
            if not self._populating_kpi_spec_combos: self.kpi_spec_subgroup_var.set("")
            if not self._populating_kpi_spec_combos or not keep_indicator: self.kpi_spec_indicator_var.set("")
            self.selected_indicator_id_for_spec = None
        elif not keep_indicator:
            if not self._populating_kpi_spec_combos: self.kpi_spec_indicator_var.set("")
            self.selected_indicator_id_for_spec = None
        self.kpi_spec_desc_var.set("")
        self.kpi_spec_type_var.set("Incrementale")
        self.kpi_spec_unit_var.set("")
        self.kpi_spec_visible_var.set(True)
        self.current_editing_kpi_id = None
        self.save_kpi_spec_btn.config(text="Aggiungi Specifica KPI")


    def save_kpi_specification(self):
        # ... (Content as before)
        if not self.selected_indicator_id_for_spec:
            messagebox.showerror("Errore", "Nessun indicatore valido selezionato.")
            return
        desc = self.kpi_spec_desc_var.get().strip()
        calc_type = self.kpi_spec_type_var.get()
        unit = self.kpi_spec_unit_var.get().strip()
        visible = self.kpi_spec_visible_var.get()
        try:
            if self.current_editing_kpi_id is not None:
                db.update_kpi(self.current_editing_kpi_id, self.selected_indicator_id_for_spec, desc, calc_type, unit, visible)
                messagebox.showinfo("Successo", "Specifica KPI aggiornata!")
            else:
                db.add_kpi(self.selected_indicator_id_for_spec, desc, calc_type, unit, visible)
                messagebox.showinfo("Successo", "Nuova specifica KPI aggiunta!")
            self.refresh_all_relevant_data()
            self.clear_kpi_spec_fields_button_action()
        except sqlite3.IntegrityError as ie:
            if "UNIQUE constraint failed: kpis.indicator_id" in str(ie) and self.current_editing_kpi_id is None:
                messagebox.showerror("Errore", f"Specifica KPI per '{self.kpi_spec_indicator_var.get()}' esiste già.")
            else: messagebox.showerror("Errore Integrità", f"Errore DB: {ie}")
        except Exception as e: messagebox.showerror("Errore", f"Salvataggio fallito: {e}\n{traceback.format_exc()}")


    def delete_selected_kpi_spec(self):
        # ... (Content as before)
        selected_item_iid = self.kpi_specs_tree.focus()
        if not selected_item_iid:
            messagebox.showwarning("Attenzione", "Nessuna specifica KPI selezionata.")
            return
        item_values = self.kpi_specs_tree.item(selected_item_iid, "values")
        try:
            kpi_spec_id_to_delete = int(item_values[0])
            kpi_name_for_confirm = f"{item_values[1]} > {item_values[2]} > {item_values[3]}"
        except: messagebox.showerror("Errore", "Impossibile ottenere dettagli specifica."); return

        if messagebox.askyesno("Conferma", f"Eliminare specifica KPI:\n{kpi_name_for_confirm} (ID: {kpi_spec_id_to_delete})?\nEliminerà anche i target associati.", parent=self):
            try:
                # Manual deletion of targets before deleting the kpi spec, or rely on DB cascade if set up
                with sqlite3.connect(db.DB_TARGETS) as conn_targets:
                    conn_targets.execute("DELETE FROM annual_targets WHERE kpi_id = ?", (kpi_spec_id_to_delete,))
                for db_path_del, table_name_del in [(db.DB_KPI_DAYS, "daily_targets"), (db.DB_KPI_WEEKS, "weekly_targets"), (db.DB_KPI_MONTHS, "monthly_targets"), (db.DB_KPI_QUARTERS, "quarterly_targets")]:
                    with sqlite3.connect(db_path_del) as conn_periodic:
                        conn_periodic.execute(f"DELETE FROM {table_name_del} WHERE kpi_id = ?", (kpi_spec_id_to_delete,))
                with sqlite3.connect(db.DB_KPIS) as conn_kpis:
                    conn_kpis.execute("DELETE FROM kpis WHERE id = ?", (kpi_spec_id_to_delete,))
                messagebox.showinfo("Successo", "Specifica KPI e target eliminati.")
                self.refresh_all_relevant_data()
                self.clear_kpi_spec_fields_button_action()
            except Exception as e: messagebox.showerror("Errore", f"Impossibile eliminare: {e}\n{traceback.format_exc()}")


    def refresh_kpi_specs_tree(self):
        for i in self.kpi_specs_tree.get_children(): self.kpi_specs_tree.delete(i)
        all_kpis_data = db.get_kpis()
        
        indicator_to_template_map = {}
        all_groups_for_map = db.get_kpi_groups()
        for grp_map in all_groups_for_map:
            subgroups_for_map = db.get_kpi_subgroups_by_group_revised(grp_map["id"])
            for sg_map in subgroups_for_map:
                if sg_map["template_name"]: # Access with ['key'] and check truthiness
                    indicators_in_sg_map = db.get_kpi_indicators_by_subgroup(sg_map["id"])
                    for ind_map in indicators_in_sg_map:
                        indicator_to_template_map[ind_map["id"]] = sg_map["template_name"]
        
        for kpi_row in all_kpis_data:
            if not isinstance(kpi_row, (sqlite3.Row, dict)):
                print(f"Skipping invalid KPI data in refresh_kpi_specs_tree: {kpi_row}")
                continue
            
            template_name_display = indicator_to_template_map.get(kpi_row["indicator_id"], "") # .get is fine for Python dict

            self.kpi_specs_tree.insert("", "end", values=(
                kpi_row["id"], 
                kpi_row["group_name"], 
                kpi_row["subgroup_name"],
                kpi_row["indicator_name"], 
                kpi_row["description"], 
                kpi_row["calculation_type"],
                kpi_row["unit_of_measure"] or "", 
                "Sì" if kpi_row["visible"] else "No",
                template_name_display ))
        
        current_group_sel = self.kpi_spec_group_var.get()
        current_subgroup_sel_display = self.kpi_spec_subgroup_var.get()
        current_indicator_sel = self.kpi_spec_indicator_var.get()
        current_subgroup_sel_raw = None
        if hasattr(self, 'subgroup_display_to_raw_map_spec') and current_subgroup_sel_display:
            current_subgroup_sel_raw = self.subgroup_display_to_raw_map_spec.get(current_subgroup_sel_display, current_subgroup_sel_display.split(" (Template:")[0])
        elif current_subgroup_sel_display: # Fallback if map not ready
             current_subgroup_sel_raw = current_subgroup_sel_display.split(" (Template:")[0]


        self.populate_kpi_spec_hier_combos(
            group_to_select=current_group_sel if not self._populating_kpi_spec_combos else None,
            subgroup_to_select=current_subgroup_sel_raw if not self._populating_kpi_spec_combos else None,
            indicator_to_select=current_indicator_sel if not self._populating_kpi_spec_combos else None)

    def on_kpi_spec_double_click(self, event): # kpi_data_full from get_kpi_by_id will now include template info for the subgroup
        # ... (Content as before)
        item_id_str = self.kpi_specs_tree.focus()
        if not item_id_str: return
        item_values = self.kpi_specs_tree.item(item_id_str, "values")
        if not item_values or len(item_values) == 0: return
        try: kpi_id_to_edit = int(item_values[0])
        except: messagebox.showerror("Errore", "ID KPI non valido."); return
        kpi_data_full = db.get_kpi_by_id(kpi_id_to_edit) # This should fetch all details
        if kpi_data_full: self.load_kpi_spec_for_editing(kpi_data_full)


    # --- Scheda Gestione Stabilimenti ---
    # ... (Content as before) ...
    def create_stabilimenti_widgets(self):
        self.st_tree = ttk.Treeview(self.stabilimenti_frame, columns=("ID", "Nome", "Visibile"), show="headings")
        for col in self.st_tree["columns"]: self.st_tree.heading(col, text=col)
        self.st_tree.column("ID", width=50, anchor="center", stretch=tk.NO)
        self.st_tree.column("Nome", width=200)
        self.st_tree.column("Visibile", width=80, anchor="center", stretch=tk.NO)
        self.st_tree.pack(expand=True, fill="both")
        bf_container = ttk.Frame(self.stabilimenti_frame); bf_container.pack(fill="x", pady=5)
        bf = ttk.Frame(bf_container); bf.pack()
        ttk.Button(bf, text="Aggiungi", command=self.add_stabilimento_window).pack(side="left", padx=2)
        ttk.Button(bf, text="Modifica", command=self.edit_stabilimento_window).pack(side="left", padx=2)

    def refresh_stabilimenti_tree(self):
        for i in self.st_tree.get_children(): self.st_tree.delete(i)
        for r_dict in db.get_stabilimenti():
            self.st_tree.insert("", "end", values=(r_dict["id"], r_dict["name"], "Sì" if r_dict["visible"] else "No"))

    def add_stabilimento_window(self): self.stabilimento_editor_window()
    def edit_stabilimento_window(self):
        sel = self.st_tree.focus()
        if not sel: messagebox.showwarning("Attenzione", "Seleziona uno stabilimento."); return
        item_values = self.st_tree.item(sel)["values"]
        if not item_values or len(item_values) < 3: return
        try: self.stabilimento_editor_window(data_tuple=(int(item_values[0]), item_values[1], item_values[2]))
        except: messagebox.showerror("Errore", "Dati stabilimento non validi."); return

    def stabilimento_editor_window(self, data_tuple=None):
        win = tk.Toplevel(self); win.title("Editor Stabilimento" if data_tuple else "Nuovo Stabilimento")
        win.transient(self); win.grab_set(); win.geometry("350x150")
        s_id, s_name, s_vis_str = (data_tuple[0], data_tuple[1], data_tuple[2]) if data_tuple else (None, "", "Sì")
        form_frame = ttk.Frame(win, padding=10); form_frame.pack(expand=True, fill="both")
        ttk.Label(form_frame, text="Nome:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        nv = tk.StringVar(value=s_name); name_entry = ttk.Entry(form_frame, textvariable=nv, width=30)
        name_entry.grid(row=0, column=1, padx=5, pady=5); name_entry.focus()
        vv = tk.BooleanVar(value=(s_vis_str == "Sì"))
        ttk.Checkbutton(form_frame, text="Visibile per Target", variable=vv).grid(row=1, column=1, sticky="w", padx=5, pady=5)
        btn_frame = ttk.Frame(form_frame); btn_frame.grid(row=2, columnspan=2, pady=10)
        def save_st():
            nome_val = nv.get().strip()
            if not nome_val: messagebox.showerror("Errore", "Nome obbligatorio.", parent=win); return
            try:
                if s_id is not None: db.update_stabilimento(s_id, nome_val, vv.get())
                else: db.add_stabilimento(nome_val, vv.get())
                self.refresh_all_relevant_data(); win.destroy()
            except sqlite3.IntegrityError: messagebox.showerror("Errore", f"Stabilimento '{nome_val}' esiste già.", parent=win)
            except Exception as e: messagebox.showerror("Errore", f"Salvataggio fallito: {e}", parent=win)
        ttk.Button(btn_frame, text="Salva", command=save_st, style="Accent.TButton").pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Annulla", command=win.destroy).pack(side="left", padx=5)


    # --- Scheda Inserimento Target ---
    # ... (Content as before, with refined _update_repartition_input_area_tk and save_all_targets_entry) ...
    def create_target_widgets(self):
        # ... (Identical to your provided code for this method)
        filter_frame_outer = ttk.Frame(self.target_frame)
        filter_frame_outer.pack(fill="x", pady=5)
        filter_frame = ttk.Frame(filter_frame_outer)
        filter_frame.pack()
        ttk.Label(filter_frame, text="Anno:").pack(side="left", padx=(0, 2))
        self.year_var_target = tk.StringVar(value=str(datetime.datetime.now().year))
        self.year_spin_target = ttk.Spinbox(filter_frame, from_=2020, to=2050, textvariable=self.year_var_target, width=6, command=self.load_kpi_targets_for_entry_target)
        self.year_spin_target.pack(side="left", padx=(0, 5))
        ttk.Label(filter_frame, text="Stabilimento:").pack(side="left", padx=(5, 2))
        self.stabilimento_var_target = tk.StringVar()
        self.stabilimento_cb_target = ttk.Combobox(filter_frame, textvariable=self.stabilimento_var_target, state="readonly", width=23)
        self.stabilimento_cb_target.pack(side="left", padx=(0, 5))
        self.stabilimento_cb_target.bind("<<ComboboxSelected>>", self.load_kpi_targets_for_entry_target)
        ttk.Button(filter_frame, text="Carica/Aggiorna KPI", command=self.load_kpi_targets_for_entry_target).pack(side="left", padx=5)
        canvas_frame_target = ttk.Frame(self.target_frame)
        canvas_frame_target.pack(fill="both", expand=True, pady=(5, 0))
        self.canvas_target = tk.Canvas(canvas_frame_target, highlightthickness=0)
        scrollbar_target = ttk.Scrollbar(canvas_frame_target, orient="vertical", command=self.canvas_target.yview)
        self.scrollable_frame_target = ttk.Frame(self.canvas_target)
        self.scrollable_frame_target.bind("<Configure>", lambda e: self.canvas_target.configure(scrollregion=self.canvas_target.bbox("all")))
        self.canvas_target_window = self.canvas_target.create_window((0, 0), window=self.scrollable_frame_target, anchor="nw")
        self.canvas_target.configure(yscrollcommand=scrollbar_target.set)
        self.canvas_target.pack(side="left", fill="both", expand=True)
        scrollbar_target.pack(side="right", fill="y")
        self.canvas_target.bind_all("<MouseWheel>", self._on_mousewheel_target)
        self.canvas_target.bind("<Enter>", lambda e: self.canvas_target.focus_set())
        self.canvas_target.bind("<Leave>", lambda e: self.focus_set())
        save_button_frame = ttk.Frame(self.target_frame)
        save_button_frame.pack(fill="x", pady=8)
        ttk.Button(save_button_frame, text="SALVA TUTTI I TARGET", command=self.save_all_targets_entry, style="Accent.TButton").pack()
        self.kpi_target_entry_widgets = {}

    def _on_mousewheel_target(self, event):
        # ... (Identical to your provided code for this method)
        active_tab_text = self.notebook.tab(self.notebook.select(), "text")
        target_canvas = None
        if active_tab_text == "🎯 Inserimento Target": target_canvas = self.canvas_target
        if target_canvas:
            widget_under_mouse = self.winfo_containing(event.x_root, event.y_root)
            is_over_target_canvas_area = False
            current_widget = widget_under_mouse
            while current_widget is not None:
                if current_widget == target_canvas: is_over_target_canvas_area = True; break
                current_widget = current_widget.master
            if is_over_target_canvas_area:
                if sys.platform.startswith("win") or sys.platform.startswith("darwin"): delta = -1 * (event.delta // (120 if sys.platform.startswith("win") else 1))
                else:
                    if event.num == 4: delta = -1
                    elif event.num == 5: delta = 1
                    else: delta = 0
                target_canvas.yview_scroll(delta, "units")

    def populate_target_comboboxes(self):
        # ... (Identical to your provided code for this method)
        stabilimenti_vis = db.get_stabilimenti(only_visible=True)
        self.stabilimenti_map_target = {s["name"]: s["id"] for s in stabilimenti_vis}
        current_stabilimento = self.stabilimento_var_target.get()
        self.stabilimento_cb_target["values"] = list(self.stabilimenti_map_target.keys())
        if current_stabilimento and current_stabilimento in self.stabilimenti_map_target: self.stabilimento_var_target.set(current_stabilimento)
        elif self.stabilimenti_map_target: self.stabilimento_var_target.set(list(self.stabilimenti_map_target.keys())[0])
        else: self.stabilimento_var_target.set("")
        self.load_kpi_targets_for_entry_target()


    def _update_repartition_input_area_tk(self, container_frame, profile_var, logic_var, repartition_vars_dict, default_repartition_map):
        # ... (Using the refined version from previous response that handles event_json)
        for widget in container_frame.winfo_children(): widget.destroy()
        selected_profile = profile_var.get(); selected_logic = logic_var.get()
        show_logic_radios = True; suggested_logic_for_profile = None
        if selected_profile in ["annual_progressive", "annual_progressive_weekday_bias", "true_annual_sinusoidal", "even_distribution", "event_based_spikes_or_dips"]:
            show_logic_radios = False; logic_var.set("Anno"); selected_logic = "Anno"
        elif selected_profile in ["quarterly_progressive", "quarterly_sinusoidal"]:
            suggested_logic_for_profile = "Trimestre"
            if selected_logic not in ["Mese", "Trimestre", "Settimana"]: logic_var.set("Trimestre"); selected_logic = "Trimestre"
        elif selected_profile in ["monthly_sinusoidal", "legacy_intra_period_progressive"]:
            if selected_logic not in ["Mese", "Trimestre", "Settimana"]: logic_var.set("Mese"); selected_logic = "Mese"
        if show_logic_radios:
            logic_selection_frame = ttk.Frame(container_frame); logic_selection_frame.pack(fill="x", pady=(5,2))
            ttk.Label(logic_selection_frame, text="Logica Rip. Valori:", width=18).pack(side="left", padx=(0,5))
            radio_cmd = lambda p_var=profile_var, l_var=logic_var, r_vars=repartition_vars_dict, c=container_frame, d_map=default_repartition_map: self._update_repartition_input_area_tk(c, p_var, l_var, r_vars, d_map)
            for logic_option in self.repartition_logic_options_tk: ttk.Radiobutton(logic_selection_frame, text=logic_option, variable=logic_var, value=logic_option, command=radio_cmd).pack(side="left", padx=2)
            if not selected_logic and suggested_logic_for_profile: logic_var.set(suggested_logic_for_profile); selected_logic = suggested_logic_for_profile
            elif not selected_logic: logic_var.set("Anno"); selected_logic = "Anno"
        input_details_frame = ttk.Frame(container_frame); input_details_frame.pack(fill="x", expand=True, pady=(5,0))
        if selected_logic == "Mese" and selected_profile not in ["even_distribution", "true_annual_sinusoidal", "annual_progressive", "annual_progressive_weekday_bias", "event_based_spikes_or_dips"]:
            periods = [calendar.month_name[i] for i in range(1,13)]; num_cols=4; default_val_perc = 100.0/len(periods)
            for i, period_name in enumerate(periods):
                row,col = divmod(i,num_cols); period_frame=ttk.Frame(input_details_frame); period_frame.grid(row=row,column=col,padx=2,pady=1,sticky="ew"); input_details_frame.columnconfigure(col,weight=1)
                ttk.Label(period_frame, text=f"{period_name[:3]}:", width=5).pack(side="left"); val_to_set = default_repartition_map.get(period_name, default_val_perc)
                var = tk.DoubleVar(value=round(float(val_to_set),2)); repartition_vars_dict[period_name]=var; ttk.Entry(period_frame, textvariable=var, width=6).pack(side="left",fill="x",expand=True)
        elif selected_logic == "Trimestre" and selected_profile not in ["even_distribution", "true_annual_sinusoidal", "annual_progressive", "annual_progressive_weekday_bias", "event_based_spikes_or_dips"]:
            periods=["Q1","Q2","Q3","Q4"]; num_cols=4; default_val_perc=100.0/len(periods)
            for i, period_name in enumerate(periods):
                row,col=divmod(i,num_cols); period_frame=ttk.Frame(input_details_frame); period_frame.grid(row=row,column=col,padx=2,pady=1,sticky="ew"); input_details_frame.columnconfigure(col,weight=1)
                ttk.Label(period_frame, text=f"{period_name}:", width=5).pack(side="left"); val_to_set = default_repartition_map.get(period_name, default_val_perc)
                var = tk.DoubleVar(value=round(float(val_to_set),2)); repartition_vars_dict[period_name]=var; ttk.Entry(period_frame, textvariable=var, width=6).pack(side="left",fill="x",expand=True)
        elif selected_logic == "Settimana":
            ttk.Label(input_details_frame, text="Valori Sett. (JSON):").pack(side="top",anchor="w",pady=(0,2)); json_text_widget=tk.Text(input_details_frame,height=3,width=50,relief=tk.SOLID,borderwidth=1); json_text_widget.pack(side="top",fill="x",expand=True,pady=(0,2))
            default_json_str=default_repartition_map.get("weekly_json", json.dumps({"Info":"Es: {\"2024-W01\": 2.5}"},indent=2))
            try: parsed_json=json.loads(default_json_str); pretty_json_str=json.dumps(parsed_json,indent=2); json_text_widget.insert("1.0",pretty_json_str)
            except json.JSONDecodeError: json_text_widget.insert("1.0",default_json_str)
            repartition_vars_dict["weekly_json_text_widget"]=json_text_widget; ttk.Label(input_details_frame,text="Formato: {\"ANNO-Wnum\": valore, ...}",font=("Calibri",8,"italic")).pack(side="top",anchor="w")
        elif selected_logic == "Anno" and selected_profile in ["annual_progressive", "annual_progressive_weekday_bias"]:
            start_f=default_repartition_map.get("start_factor",1.2); end_f=default_repartition_map.get("end_factor",0.8)
            start_v=tk.DoubleVar(value=round(start_f,2)); end_v=tk.DoubleVar(value=round(end_f,2)); repartition_vars_dict["start_factor"]=start_v; repartition_vars_dict["end_factor"]=end_v
            ttk.Label(input_details_frame,text="Fatt. Iniziale:",width=12).grid(row=0,column=0,padx=2,pady=2,sticky="w"); ttk.Entry(input_details_frame,textvariable=start_v,width=7).grid(row=0,column=1,padx=2,pady=2,sticky="ew")
            ttk.Label(input_details_frame,text="Fatt. Finale:",width=12).grid(row=0,column=2,padx=2,pady=2,sticky="w"); ttk.Entry(input_details_frame,textvariable=end_v,width=7).grid(row=0,column=3,padx=2,pady=2,sticky="ew")
            input_details_frame.columnconfigure(1,weight=1); input_details_frame.columnconfigure(3,weight=1); ttk.Label(input_details_frame,text="(Modulazione annuale)",font=("Calibri",8,"italic")).grid(row=1,column=0,columnspan=4,sticky="w",pady=(0,5))
        if selected_profile == "event_based_spikes_or_dips":
            ttk.Label(input_details_frame,text="Eventi (JSON):").pack(side="top",anchor="w",pady=(5,2)); event_json_widget=tk.Text(input_details_frame,height=4,width=50,relief=tk.SOLID,borderwidth=1); event_json_widget.pack(side="top",fill="x",expand=True,pady=(0,2))
            default_event_json=default_repartition_map.get("event_json",json.dumps([{"start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD","multiplier":1.0,"addition":0.0}],indent=2))
            try: parsed_event=json.loads(default_event_json); pretty_event=json.dumps(parsed_event,indent=2); event_json_widget.insert("1.0",pretty_event)
            except json.JSONDecodeError: event_json_widget.insert("1.0",default_event_json)
            repartition_vars_dict["event_json_text_widget"]=event_json_widget; ttk.Label(input_details_frame,text="Lista: [{start_date, end_date, mult, add}]",font=("Calibri",8,"italic")).pack(side="top",anchor="w")


    def load_kpi_targets_for_entry_target(self, event=None):
        for widget in self.scrollable_frame_target.winfo_children():
            widget.destroy()
        self.kpi_target_entry_widgets.clear()
        self.canvas_target.yview_moveto(0)  # Reset scroll position

        if not self.stabilimento_var_target.get() or not self.year_var_target.get():
            ttk.Label(
                self.scrollable_frame_target, text="Seleziona anno e stabilimento."
            ).pack(pady=10)
            return
        try:
            year = int(self.year_var_target.get())
            stabilimento_id = self.stabilimenti_map_target.get(
                self.stabilimento_var_target.get()
            )
            if stabilimento_id is None:
                ttk.Label(
                    self.scrollable_frame_target,
                    text="Stabilimento selezionato non valido.",
                ).pack(pady=10)
                return
        except ValueError:
            ttk.Label(self.scrollable_frame_target, text="Anno non valido.").pack(
                pady=10
            )
            return

        kpis_for_target_entry = db.get_kpis(only_visible=True)
        if not kpis_for_target_entry:
            ttk.Label(
                self.scrollable_frame_target,
                text="Nessun KPI (visibile per target) definito nel sistema.",
            ).pack(pady=10)
            return

        for kpi_row_data in kpis_for_target_entry:
            if not isinstance(kpi_row_data, (sqlite3.Row, dict)):
                continue
            kpi_id = kpi_row_data["id"] # This is kpis.id (the spec ID)
            if kpi_id is None:
                continue

            kpi_display_name_str = get_kpi_display_name(kpi_row_data)
            kpi_unit = kpi_row_data["unit_of_measure"] or ""
            calc_type = kpi_row_data["calculation_type"]
            frame_label_text = (
                f"{kpi_display_name_str} (Unità: {kpi_unit if kpi_unit else 'N/D'}, Tipo: {calc_type})"
            )

            kpi_entry_frame = ttk.LabelFrame(
                self.scrollable_frame_target, text=frame_label_text, padding=10
            )
            kpi_entry_frame.pack(fill="x", expand=True, padx=5, pady=(0, 7))

            existing_target_db = db.get_annual_target(year, stabilimento_id, kpi_id)
            def_target1_val, def_target2_val = 0.0, 0.0
            def_profile_val = "annual_progressive"
            def_logic_val = "Anno"
            def_repart_map_val = {}
            def_profile_params_map = {}

            if existing_target_db and isinstance(existing_target_db, (sqlite3.Row, dict)):
                def_target1_val = float(existing_target_db["annual_target1"] or 0.0) # Corrected access
                def_target2_val = float(existing_target_db["annual_target2"] or 0.0) # Corrected access
                db_profile = existing_target_db["distribution_profile"] # Corrected access
                if db_profile and db_profile in self.distribution_profile_options_tk:
                    def_profile_val = db_profile
                def_logic_val = existing_target_db["repartition_logic"] or "Anno" # Corrected access
                
                repart_values_str = existing_target_db["repartition_values"] # Corrected access
                if repart_values_str:
                    try:
                        loaded_map = json.loads(repart_values_str)
                        if isinstance(loaded_map, dict):
                            def_repart_map_val = loaded_map
                            if def_logic_val == "Settimana" and "weekly_json" not in loaded_map:
                                 def_repart_map_val = {"weekly_json": repart_values_str}
                    except json.JSONDecodeError:
                        if def_logic_val == "Settimana":
                            def_repart_map_val["weekly_json"] = repart_values_str
                
                profile_params_str = existing_target_db["profile_params"] # Corrected access
                if profile_params_str:
                    try:
                        loaded_params_map = json.loads(profile_params_str)
                        if isinstance(loaded_params_map, dict):
                            def_profile_params_map = loaded_params_map # Store loaded params
                            # Specifically for event_based_spikes_or_dips, ensure event data is under 'event_json' for the UI text widget
                            if def_profile_val == "event_based_spikes_or_dips" and "events" in def_profile_params_map:
                                # The UI's _update_repartition_input_area_tk expects 'event_json' in its `default_repartition_map`
                                # So we populate it here if events exist in profile_params
                                def_repart_map_val["event_json"] = json.dumps(def_profile_params_map["events"], indent=2)
                    except json.JSONDecodeError:
                        print(f"Warning: Could not parse profile_params for KPI {kpi_id}")
                        def_profile_params_map = {} # Keep it as an empty dict if parsing fails
            
            # Ensure UI defaults for event_json if profile is event_based and no params were loaded
            if def_profile_val == "event_based_spikes_or_dips" and "event_json" not in def_repart_map_val:
                # If 'events' key was not in def_profile_params_map or profile_params_map itself was empty/invalid
                def_repart_map_val["event_json"] = json.dumps([{"start_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD","multiplier":1.0,"addition":0.0, "comment":"Esempio"}], indent=2)
            elif def_logic_val == "Settimana" and "weekly_json" not in def_repart_map_val :
                 def_repart_map_val["weekly_json"] = json.dumps(def_repart_map_val if def_repart_map_val else {"Info":"Es: {\"2024-W01\": 2.5}"},indent=2)


            target1_var = tk.DoubleVar(value=def_target1_val)
            target2_var = tk.DoubleVar(value=def_target2_val)
            profile_var_entry = tk.StringVar(value=def_profile_val)
            logic_var_entry = tk.StringVar(value=def_logic_val)
            repartition_input_vars_entry = {}

            top_row_frame_entry = ttk.Frame(kpi_entry_frame)
            top_row_frame_entry.pack(fill="x", pady=(0, 5))
            ttk.Label(top_row_frame_entry, text="Target 1:", width=8).pack(side="left")
            ttk.Entry(top_row_frame_entry, textvariable=target1_var, width=10).pack(side="left", padx=(2, 8))
            ttk.Label(top_row_frame_entry, text="Target 2:", width=8).pack(side="left")
            ttk.Entry(top_row_frame_entry, textvariable=target2_var, width=10).pack(side="left", padx=(2, 8))
            ttk.Label(top_row_frame_entry, text="Profilo Distrib.:", width=16).pack(side="left")
            profile_cb_entry = ttk.Combobox(
                top_row_frame_entry,
                textvariable=profile_var_entry,
                values=self.distribution_profile_options_tk,
                state="readonly",
                width=28,
            )
            profile_cb_entry.pack(side="left", padx=(2, 0), fill="x", expand=True)

            repartition_controls_outer_container = ttk.Frame(kpi_entry_frame)
            repartition_controls_outer_container.pack(fill="x", pady=(2, 0))
            
            # `def_repart_map_val` now correctly holds specific keys like 'weekly_json' or 'event_json'
            # if they were loaded from DB or set by default for the UI.
            cmd_profile_change = lambda ev, p_var=profile_var_entry, l_var=logic_var_entry, r_vars=repartition_input_vars_entry, c=repartition_controls_outer_container, d_map=def_repart_map_val: \
                self._update_repartition_input_area_tk(c, p_var, l_var, r_vars, d_map)
            profile_cb_entry.bind("<<ComboboxSelected>>", cmd_profile_change)

            self.kpi_target_entry_widgets[kpi_id] = {
                "target1_var": target1_var,
                "target2_var": target2_var,
                "profile_var": profile_var_entry,
                "logic_var": logic_var_entry,
                "repartition_vars": repartition_input_vars_entry,
                "calc_type": calc_type,
                "repartition_controls_container": repartition_controls_outer_container,
                "kpi_display_name": kpi_display_name_str,
            }
            
            self._update_repartition_input_area_tk(
                repartition_controls_outer_container,
                profile_var_entry,
                logic_var_entry,
                repartition_input_vars_entry,
                def_repart_map_val, # Pass the map which may contain 'weekly_json', 'event_json', or period data
            )

        self.scrollable_frame_target.update_idletasks()
        self.canvas_target.config(scrollregion=self.canvas_target.bbox("all"))

    def save_all_targets_entry(self):
        # ... (Using the refined version from previous response that handles event_json correctly into profile_params)
        try: year_val=int(self.year_var_target.get()); stabilimento_id_val=self.stabilimenti_map_target.get(self.stabilimento_var_target.get())
        except (ValueError,KeyError): messagebox.showerror("Errore","Seleziona anno e stabilimento validi."); return
        if stabilimento_id_val is None: messagebox.showerror("Errore","Stabilimento non valido."); return
        targets_to_save={}; all_valid=True
        for kpi_id,widgets in self.kpi_target_entry_widgets.items():
            try: t1=widgets["target1_var"].get(); t2=widgets["target2_var"].get()
            except tk.TclError: messagebox.showerror("Errore",f"KPI '{widgets['kpi_display_name']}': Target non numerico."); all_valid=False; break
            profile=widgets["profile_var"].get(); logic_ui=widgets["logic_var"].get()
            repart_vals_db={}; profile_params_db={}
            eff_logic_db = logic_ui
            if profile in ["annual_progressive","annual_progressive_weekday_bias","true_annual_sinusoidal","even_distribution","event_based_spikes_or_dips"]: eff_logic_db="Anno"
            if eff_logic_db=="Anno":
                if profile in ["annual_progressive","annual_progressive_weekday_bias"]:
                    try: repart_vals_db["start_factor"]=widgets["repartition_vars"]["start_factor"].get(); repart_vals_db["end_factor"]=widgets["repartition_vars"]["end_factor"].get()
                    except: messagebox.showerror("Errore",f"KPI '{widgets['kpi_display_name']}': Fattori non validi."); all_valid=False; break
            elif eff_logic_db in ["Mese","Trimestre"]:
                sum_p=0.0; num_p=0; temp_p_vals={}
                for key,var_obj in widgets["repartition_vars"].items():
                    if key in ["start_factor","end_factor","weekly_json_text_widget","event_json_text_widget"]: continue
                    try: val=var_obj.get(); temp_p_vals[key]=val; sum_p+=val; num_p+=1
                    except tk.TclError: messagebox.showerror("Errore",f"KPI '{widgets['kpi_display_name']}': Valore non numerico per '{key}'."); all_valid=False; break
                if not all_valid: break
                if widgets["calc_type"]=="Incrementale" and num_p>0 and (abs(t1)>1e-9 or abs(t2)>1e-9) and not (99.9<=sum_p<=100.1):
                    messagebox.showerror("Errore",f"KPI '{widgets['kpi_display_name']}' (Incrementale): somma ripartizioni {eff_logic_db} è {sum_p:.2f}%. Deve essere 100%."); all_valid=False; break
                repart_vals_db=temp_p_vals
            elif eff_logic_db=="Settimana":
                json_w=widgets["repartition_vars"].get("weekly_json_text_widget")
                if json_w: json_s=json_w.get("1.0",tk.END).strip()
                if json_s: 
                    try:
                        repart_vals_db=json.loads(json_s) if isinstance(json.loads(json_s),dict) else {}
                    except: 
                        messagebox.showerror("Errore",f"KPI '{widgets['kpi_display_name']}': JSON settimanale non valido."); all_valid=False; break
            if profile=="event_based_spikes_or_dips":
                event_w=widgets["repartition_vars"].get("event_json_text_widget")
                if event_w: 
                    event_s=event_w.get("1.0",tk.END).strip()
                if event_s: 
                    try: 
                        profile_params_db["events"]=json.loads(event_s) if isinstance(json.loads(event_s),list) else []
                    except:
                        messagebox.showerror("Errore",f"KPI '{widgets['kpi_display_name']}': JSON eventi non valido."); all_valid=False; break
            targets_to_save[kpi_id]={"annual_target1":t1,"annual_target2":t2,"repartition_logic":eff_logic_db,"repartition_values":repart_vals_db,"distribution_profile":profile,"profile_params":profile_params_db}
        if not all_valid: return
        if not targets_to_save: messagebox.showwarning("Attenzione","Nessun target da salvare."); return
        try: 
            db.save_annual_targets(year_val,stabilimento_id_val,targets_to_save); messagebox.showinfo("Successo","Target salvati e CSV rigenerati!"); self.load_kpi_targets_for_entry_target()
        except Exception as e: 
            messagebox.showerror("Errore",f"Salvataggio fallito: {e}\n{traceback.format_exc()}")


    # --- Scheda Visualizzazione Risultati ---
    # ... (Content as before, with refined show_results_data to handle T1 & T2) ...
    def create_results_widgets(self):
        # ... (Identical to your provided code for this method)
        filter_frame_outer_res = ttk.Frame(self.results_frame); filter_frame_outer_res.pack(fill="x", pady=5)
        filter_frame_res = ttk.Frame(filter_frame_outer_res); filter_frame_res.pack()
        ttk.Label(filter_frame_res, text="Anno:").pack(side="left"); self.res_year_var_vis = tk.StringVar(value=str(datetime.datetime.now().year))
        ttk.Spinbox(filter_frame_res, from_=2020, to=2050, textvariable=self.res_year_var_vis, width=6, command=self.show_results_data).pack(side="left",padx=(2,5))
        ttk.Label(filter_frame_res, text="Stabilimento:").pack(side="left",padx=(5,0)); self.res_stabilimento_var_vis = tk.StringVar()
        self.res_stabilimento_cb_vis = ttk.Combobox(filter_frame_res, textvariable=self.res_stabilimento_var_vis, state="readonly", width=16); self.res_stabilimento_cb_vis.pack(side="left",padx=(2,5)); self.res_stabilimento_cb_vis.bind("<<ComboboxSelected>>", self.show_results_data)
        ttk.Label(filter_frame_res, text="Gruppo:").pack(side="left",padx=(5,0)); self.res_group_var=tk.StringVar(); self.res_group_cb=ttk.Combobox(filter_frame_res,textvariable=self.res_group_var,state="readonly",width=13); self.res_group_cb.pack(side="left",padx=(2,2)); self.res_group_cb.bind("<<ComboboxSelected>>",self.on_res_group_selected_refresh_results)
        ttk.Label(filter_frame_res, text="Sottogruppo:").pack(side="left"); self.res_subgroup_var=tk.StringVar(); self.res_subgroup_cb=ttk.Combobox(filter_frame_res,textvariable=self.res_subgroup_var,state="readonly",width=13); self.res_subgroup_cb.pack(side="left",padx=(2,2)); self.res_subgroup_cb.bind("<<ComboboxSelected>>",self.on_res_subgroup_selected_refresh_results)
        ttk.Label(filter_frame_res, text="Indicatore:").pack(side="left"); self.res_indicator_var=tk.StringVar(); self.res_indicator_cb=ttk.Combobox(filter_frame_res,textvariable=self.res_indicator_var,state="readonly",width=18); self.res_indicator_cb.pack(side="left",padx=(2,5)); self.res_indicator_cb.bind("<<ComboboxSelected>>",self.show_results_data)
        ttk.Label(filter_frame_res, text="Periodo:").pack(side="left",padx=(5,0)); self.res_period_var_vis=tk.StringVar(value="Mese"); self.res_period_cb_vis=ttk.Combobox(filter_frame_res,textvariable=self.res_period_var_vis,state="readonly",values=["Giorno","Settimana","Mese","Trimestre"],width=9); self.res_period_cb_vis.current(2); self.res_period_cb_vis.pack(side="left",padx=(2,5)); self.res_period_cb_vis.bind("<<ComboboxSelected>>",self.show_results_data)
        ttk.Button(filter_frame_res, text="Aggiorna Vista", command=self.show_results_data, style="Accent.TButton").pack(side="left",padx=5)
        self.results_data_tree=ttk.Treeview(self.results_frame,columns=("Periodo","Valore Target 1","Valore Target 2"),show="headings"); self.results_data_tree.heading("Periodo",text="Periodo"); self.results_data_tree.heading("Valore Target 1",text="Valore Target 1"); self.results_data_tree.heading("Valore Target 2",text="Valore Target 2")
        self.results_data_tree.column("Periodo",width=200,anchor="w"); self.results_data_tree.column("Valore Target 1",width=150,anchor="e"); self.results_data_tree.column("Valore Target 2",width=150,anchor="e")
        self.results_data_tree.pack(fill="both",expand=True,pady=(5,0)); self.summary_label_var_vis=tk.StringVar(); ttk.Label(self.results_frame,textvariable=self.summary_label_var_vis,font=("Calibri",10,"italic")).pack(pady=5,anchor="e",padx=10)

    def on_res_group_selected_refresh_results(self, event=None):
        self.on_res_group_selected(event)
    def on_res_subgroup_selected_refresh_results(self, event=None):
        self.on_res_subgroup_selected(event)
        self.show_results_data() # Show data once subgroup is selected, indicator might auto-select

    def populate_results_comboboxes(self):
        # ... (Using the refined version from previous response)
        cs=self.res_stabilimento_var_vis.get(); sa=db.get_stabilimenti(); self.res_stabilimenti_map_vis={s["name"]:s["id"] for s in sa}; self.res_stabilimento_cb_vis["values"]=list(self.res_stabilimenti_map_vis.keys())
        if cs and cs in self.res_stabilimenti_map_vis: self.res_stabilimento_var_vis.set(cs)
        elif self.res_stabilimenti_map_vis: self.res_stabilimento_var_vis.set(list(self.res_stabilimenti_map_vis.keys())[0])
        else: self.res_stabilimento_var_vis.set("")
        cg,csr,ci = self.res_group_var.get(), (self.res_subgroup_var.get().split(" (Template:")[0] if self.res_subgroup_var.get() else None), self.res_indicator_var.get()
        self.res_groups_list=db.get_kpi_groups(); self.res_group_cb["values"]=[g["name"] for g in self.res_groups_list]
        if cg and cg in self.res_group_cb["values"]: self.res_group_var.set(cg); self.on_res_group_selected(pre_selected_subgroup_raw=csr, pre_selected_indicator=ci)
        else: self.res_group_var.set(""); self.res_subgroup_var.set(""); self.res_indicator_var.set(""); self.res_subgroup_cb["values"]=[]; self.res_indicator_cb["values"]=[]; self.current_kpi_id_for_results=None
        self.show_results_data()

    def on_res_group_selected(self, event=None, pre_selected_subgroup_raw=None, pre_selected_indicator=None):
        # ... (Using the refined version from previous response)
        gn=self.res_group_var.get(); self.res_subgroup_cb["values"]=[]; self.res_indicator_cb["values"]=[]
        if not pre_selected_subgroup_raw: self.res_subgroup_var.set("")
        if not pre_selected_indicator: self.res_indicator_var.set("")
        self.current_kpi_id_for_results=None
        sg=next((g for g in self.res_groups_list if g["name"]==gn),None)
        if sg:
            self.res_subgroups_list_details=db.get_kpi_subgroups_by_group_revised(sg["id"]); dsn=[]; self.res_subgroup_display_to_raw_map={}
            for sgd in self.res_subgroups_list_details: rn=sgd["name"]; dn=rn+(f" (Template: {sgd['template_name']})" if sgd.get("template_name") else ""); dsn.append(dn); self.res_subgroup_display_to_raw_map[dn]=rn
            self.res_subgroup_cb["values"]=dsn; tds=None
            if pre_selected_subgroup_raw: tds=next((d for d,r in self.res_subgroup_display_to_raw_map.items() if r==pre_selected_subgroup_raw), None)
            if tds: self.res_subgroup_var.set(tds); self.on_res_subgroup_selected(pre_selected_indicator=pre_selected_indicator)
            elif not self._populating_kpi_spec_combos and not pre_selected_subgroup_raw: self.show_results_data()

    def on_res_subgroup_selected(self, event=None, pre_selected_indicator=None):
        # ... (Using the refined version from previous response)
        dsn=self.res_subgroup_var.get(); self.res_indicator_cb["values"]=[]
        if not pre_selected_indicator: self.res_indicator_var.set("")
        self.current_kpi_id_for_results=None
        rsn=self.res_subgroup_display_to_raw_map.get(dsn); sdo=None
        if rsn and hasattr(self,"res_subgroups_list_details"): sdo=next((s for s in self.res_subgroups_list_details if s["name"]==rsn),None)
        if sdo:
            aisi=db.get_kpi_indicators_by_subgroup(sdo["id"]); kds=db.get_kpis(); dis={k["indicator_id"] for k in kds}
            self.res_indicators_list_filtered_details=[i for i in aisi if i["id"] in dis]; self.res_indicator_cb["values"]=[i["name"] for i in self.res_indicators_list_filtered_details]
            if pre_selected_indicator and pre_selected_indicator in self.res_indicator_cb["values"]: self.res_indicator_var.set(pre_selected_indicator)
            # self.show_results_data() # This line should be here to update when subgroup changes and indicator might auto-select or become blank
        if not self._populating_kpi_spec_combos: self.show_results_data()


    def show_results_data(self, event=None): # Combined logic for T1 and T2
        for i in self.results_data_tree.get_children():
            self.results_data_tree.delete(i)
        self.summary_label_var_vis.set("")
        try:
            year_val_res_str = self.res_year_var_vis.get()
            if not year_val_res_str:
                # Optional: show a message if year is empty, or just return
                self.summary_label_var_vis.set("Selezionare un anno.")
                return
            year_val_res = int(year_val_res_str)
            
            stabilimento_name_res = self.res_stabilimento_var_vis.get()
            indicator_name_res = self.res_indicator_var.get()
            period_type_res = self.res_period_var_vis.get()

            if not all([stabilimento_name_res, indicator_name_res, period_type_res]):
                self.summary_label_var_vis.set("Selezionare Anno, Stabilimento, Indicatore e Periodo.")
                return

            stabilimento_id_res = self.res_stabilimenti_map_vis.get(stabilimento_name_res)
            if stabilimento_id_res is None:
                self.summary_label_var_vis.set("Stabilimento selezionato non valido.")
                return

            selected_indicator_details_obj = None
            if hasattr(self, "res_indicators_list_filtered_details") and self.res_indicators_list_filtered_details:
                selected_indicator_details_obj = next(
                    (ind for ind in self.res_indicators_list_filtered_details if ind["name"] == indicator_name_res), None
                )
            
            if not selected_indicator_details_obj:
                self.summary_label_var_vis.set(f"Indicatore '{indicator_name_res}' non trovato o senza specifica KPI definita.")
                return
            
            indicator_actual_id = selected_indicator_details_obj["id"] # This is kpi_indicators.id
            
            # Find the kpi_spec (kpis table row) for this indicator
            kpi_spec_obj = next((spec for spec in db.get_kpis() if spec["indicator_id"] == indicator_actual_id), None)
            if not kpi_spec_obj:
                self.summary_label_var_vis.set(f"Specifica KPI non trovata per l'indicatore ID {indicator_actual_id}.")
                return
                
            kpi_id_res = kpi_spec_obj["id"] # This is kpis.id (the spec ID to use for targets)
            calc_type_res = kpi_spec_obj["calculation_type"]
            kpi_unit_res = kpi_spec_obj["unit_of_measure"] or ""
            kpi_display_name_res_str = get_kpi_display_name(kpi_spec_obj)

            target_ann_info_res = db.get_annual_target(year_val_res, stabilimento_id_res, kpi_id_res)
            profile_disp_res = "N/D"
            if target_ann_info_res and isinstance(target_ann_info_res, (sqlite3.Row, dict)): # Check if it's a valid row/dict
                profile_disp_res = target_ann_info_res["distribution_profile"] or "N/D" # Corrected access

            data_t1 = db.get_ripartiti_data(year_val_res, stabilimento_id_res, kpi_id_res, period_type_res, 1)
            data_t2 = db.get_ripartiti_data(year_val_res, stabilimento_id_res, kpi_id_res, period_type_res, 2)

            map_t1 = {row["Periodo"]: row["Target"] for row in data_t1} if data_t1 else {}
            map_t2 = {row["Periodo"]: row["Target"] for row in data_t2} if data_t2 else {}
            
            ordered_periods = [row["Periodo"] for row in data_t1] if data_t1 else ([row["Periodo"] for row in data_t2] if data_t2 else [])
            
            display_rows_added = False
            total_sum_t1, count_t1 = 0.0, 0
            total_sum_t2, count_t2 = 0.0, 0

            for period_name in ordered_periods:
                val_t1 = map_t1.get(period_name) # .get is fine for Python dicts
                val_t2 = map_t2.get(period_name)
                t1_disp = f"{val_t1:.2f}" if isinstance(val_t1, (int, float)) else "N/A"
                t2_disp = f"{val_t2:.2f}" if isinstance(val_t2, (int, float)) else "N/A"
                self.results_data_tree.insert("", "end", values=(period_name, t1_disp, t2_disp))
                display_rows_added = True
                if isinstance(val_t1, (int, float)): 
                    total_sum_t1 += val_t1
                    count_t1 += 1
                if isinstance(val_t2, (int, float)): 
                    total_sum_t2 += val_t2
                    count_t2 += 1

            if not display_rows_added:
                self.summary_label_var_vis.set(f"Nessun dato ripartito per {kpi_display_name_res_str} (Profilo: {profile_disp_res}).")
                return

            summary_parts = [f"KPI: {kpi_display_name_res_str}", f"Profilo: {profile_disp_res}"]
            if count_t1 > 0:
                agg_t1 = total_sum_t1 if calc_type_res == "Incrementale" else (total_sum_t1 / count_t1)
                lbl_t1 = "Totale T1" if calc_type_res == "Incrementale" else "Media T1"
                summary_parts.append(f"{lbl_t1} ({period_type_res}): {agg_t1:,.2f} {kpi_unit_res}")
            if count_t2 > 0:
                agg_t2 = total_sum_t2 if calc_type_res == "Incrementale" else (total_sum_t2 / count_t2)
                lbl_t2 = "Totale T2" if calc_type_res == "Incrementale" else "Media T2"
                summary_parts.append(f"{lbl_t2} ({period_type_res}): {agg_t2:,.2f} {kpi_unit_res}")
            
            self.summary_label_var_vis.set(" | ".join(summary_parts))

        except ValueError as ve: # Catches int() conversion errors for year
            self.summary_label_var_vis.set(f"Errore Input: Anno non valido o altri input numerici errati. ({ve})")
        except Exception as e:
            self.summary_label_var_vis.set(f"Errore durante la visualizzazione dei risultati: {e}")
            import traceback # Import traceback if not already at the top of the file
            traceback.print_exc()

    # --- Scheda Esportazione Dati ---
    # ... (Content as before) ...
    def create_export_widgets(self):
        # ... (Identical to your provided code for this method)
        export_main_frame = ttk.Frame(self.export_frame, padding=20); export_main_frame.pack(expand=True, fill="both")
        export_info_label_frame = ttk.Frame(export_main_frame); export_info_label_frame.pack(pady=10, anchor="center")
        resolved_path_str = "N/D"; 
        try: 
            resolved_path_str = str(Path(db.CSV_EXPORT_BASE_PATH).resolve())
        except: 
            pass
        export_info_label = ttk.Label(export_info_label_frame, text=(f"CSV globali generati/sovrascritti al salvataggio dei target.\nSalvati in:\n{resolved_path_str}"), wraplength=700, justify="center", font=("Calibri",11)); export_info_label.pack()
        export_button_frame = ttk.Frame(export_main_frame); export_button_frame.pack(pady=30,anchor="center")
        ttk.Button(export_button_frame,text="Esporta CSV Globali in ZIP...", command=self.export_all_data_to_zip, style="Accent.TButton").pack()
        open_folder_button_frame = ttk.Frame(export_main_frame); open_folder_button_frame.pack(pady=10,anchor="center")
        ttk.Button(open_folder_button_frame,text="Apri Cartella Esportazioni CSV", command=self.open_export_folder).pack()

    def open_export_folder(self):
        # ... (Identical to your provided code for this method)
        try:
            export_path = Path(db.CSV_EXPORT_BASE_PATH).resolve()
            if not export_path.exists(): export_path.mkdir(parents=True, exist_ok=True); messagebox.showinfo("Cartella Creata", f"Cartella esportazioni creata:\n{export_path}\nVuota. Salva target per popolarla.",parent=self)
            if sys.platform == "win32": os.startfile(export_path)
            elif sys.platform == "darwin": subprocess.Popen(["open", str(export_path)])
            else: subprocess.Popen(["xdg-open", str(export_path)])
        except AttributeError: messagebox.showerror("Errore Config.", "Percorso esportazioni CSV non configurato.",parent=self)
        except Exception as e: messagebox.showerror("Errore Apertura", f"Impossibile aprire cartella: {e}",parent=self)

    def export_all_data_to_zip(self):
        # ... (Identical to your provided code for this method)
        try: export_base_path_str = db.CSV_EXPORT_BASE_PATH
        except AttributeError: messagebox.showerror("Errore Config.","Percorso base esportazioni non definito.",parent=self); return
        if not export_base_path_str : messagebox.showerror("Errore Config.","Percorso base esportazioni non definito.",parent=self); return
        export_base_path = Path(export_base_path_str)
        expected_csv_files = getattr(export_manager, 'GLOBAL_CSV_FILES',None)
        if not export_base_path.exists() or (expected_csv_files and not any(f.name in expected_csv_files.values() for f in export_base_path.iterdir() if f.is_file())):
            messagebox.showwarning("Nessun Dato",f"Nessun CSV globale atteso in {export_base_path.resolve()}. Salva target.",parent=self); return
        default_zip_name = f"kpi_global_data_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        zip_filepath = filedialog.asksaveasfilename(title="Salva archivio ZIP",initialfile=default_zip_name,defaultextension=".zip",filetypes=[("File ZIP","*.zip"),("Tutti i file","*.*")],parent=self)
        if not zip_filepath: return
        try:
            if not hasattr(export_manager, 'package_all_csvs_as_zip'): messagebox.showerror("Errore Funzione","'package_all_csvs_as_zip' non in export_manager.",parent=self); return
            success, message = export_manager.package_all_csvs_as_zip(str(export_base_path), zip_filepath)
            if success: messagebox.showinfo("Esportazione Completata", message,parent=self)
            else: messagebox.showerror("Errore Esportazione", message,parent=self)
        except Exception as e: messagebox.showerror("Errore Critico Esportazione",f"Errore imprevisto ZIP: {e}\n{traceback.format_exc()}",parent=self)

# Dialog classes (SubgroupEditorDialog, TemplateDefinitionEditorDialog)
# These should be placed at the same level as KpiApp class or imported if in separate file.
# For simplicity, including them here.

class SubgroupEditorDialog(simpledialog.Dialog):
    def __init__(self, parent, title=None, group_id_context=None, initial_name="", initial_template_id=None):
        self.group_id = group_id_context
        self.initial_name = initial_name
        self.initial_template_id = initial_template_id
        self.result_name = None
        self.result_template_id = False 
        self.templates_map = {"(Nessun Template)": None}
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text="Nome Sottogruppo:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.name_var = tk.StringVar(value=self.initial_name)
        self.name_entry = ttk.Entry(master, textvariable=self.name_var, width=30)
        self.name_entry.grid(row=0, column=1, padx=5, pady=2); self.name_entry.focus_set()
        ttk.Label(master, text="Template Indicatori:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.template_var = tk.StringVar()
        self.template_cb = ttk.Combobox(master, textvariable=self.template_var, state="readonly", width=28)
        available_templates = db.get_kpi_indicator_templates()
        for tpl in available_templates: self.templates_map[tpl["name"]] = tpl["id"]
        self.template_cb["values"] = list(self.templates_map.keys())
        if self.initial_template_id is not None:
            for name, id_val in self.templates_map.items():
                if id_val == self.initial_template_id: self.template_var.set(name); break
            else: self.template_var.set("(Nessun Template)")
        else: self.template_var.set("(Nessun Template)")
        self.template_cb.grid(row=1, column=1, padx=5, pady=2)
        return self.name_entry

    def apply(self):
        self.result_name = self.name_var.get().strip()
        self.result_template_id = self.templates_map.get(self.template_var.get())
        if not self.result_name:
            messagebox.showwarning("Input Mancante", "Nome sottogruppo obbligatorio.", parent=self)
            self.result_name = None; self.result_template_id = False # Keep dialog open

class TemplateDefinitionEditorDialog(simpledialog.Dialog):
    def __init__(self, parent, title=None, template_id_context=None, initial_data=None):
        self.initial_data = initial_data if initial_data else {}
        self.result_data = None
        super().__init__(parent, title)

    def body(self, master):
        self.name_var = tk.StringVar(value=self.initial_data.get("indicator_name_in_template", ""))
        self.desc_var = tk.StringVar(value=self.initial_data.get("default_description", ""))
        self.type_var = tk.StringVar(value=self.initial_data.get("default_calculation_type", "Incrementale"))
        self.unit_var = tk.StringVar(value=self.initial_data.get("default_unit_of_measure", ""))
        self.visible_var = tk.BooleanVar(value=bool(self.initial_data.get("default_visible", True)))
        ttk.Label(master, text="Nome Indicatore Template:").grid(row=0,column=0,sticky="w",padx=5,pady=2)
        self.name_entry = ttk.Entry(master,textvariable=self.name_var,width=35); self.name_entry.grid(row=0,column=1,padx=5,pady=2); self.name_entry.focus_set()
        ttk.Label(master, text="Descrizione Default:").grid(row=1,column=0,sticky="w",padx=5,pady=2); ttk.Entry(master,textvariable=self.desc_var,width=35).grid(row=1,column=1,padx=5,pady=2)
        ttk.Label(master, text="Tipo Calcolo Default:").grid(row=2,column=0,sticky="w",padx=5,pady=2); ttk.Combobox(master,textvariable=self.type_var,values=["Incrementale","Media"],state="readonly",width=33).grid(row=2,column=1,padx=5,pady=2)
        ttk.Label(master, text="Unità Misura Default:").grid(row=3,column=0,sticky="w",padx=5,pady=2); ttk.Entry(master,textvariable=self.unit_var,width=35).grid(row=3,column=1,padx=5,pady=2)
        ttk.Checkbutton(master,text="Visibile Default",variable=self.visible_var).grid(row=4,column=1,sticky="w",padx=5,pady=5)
        return self.name_entry

    def apply(self):
        name=self.name_var.get().strip(); desc=self.desc_var.get().strip(); calc_type=self.type_var.get(); unit=self.unit_var.get().strip(); visible=self.visible_var.get()
        if not name: messagebox.showwarning("Input Mancante","Nome indicatore nel template obbligatorio.",parent=self); return
        self.result_data = {"name":name,"desc":desc,"calc_type":calc_type,"unit":unit,"visible":visible}

if __name__ == "__main__":
    try:
        db.setup_databases()
        app = KpiApp()
        app.mainloop()
    except Exception as e:
        with open("app_startup_error.log", "a") as f:
            f.write(f"{datetime.datetime.now()}: {traceback.format_exc()}\n")
        try:
            root_err = tk.Tk(); root_err.withdraw()
            messagebox.showerror("Errore Critico Avvio", f"Impossibile avviare l'applicazione:\n{e}\n\nConsultare app_startup_error.log.")
            root_err.destroy()
        except tk.TclError: print(f"ERRORE CRITICO DI AVVIO (TKinter non disponibile):\n{traceback.format_exc()}")
        sys.exit(1)
