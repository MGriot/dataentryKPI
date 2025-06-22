# app_tkinter.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import database_manager as db_manager
import data_retriever as db_retriever
import export_manager

import json
import datetime
import calendar
from pathlib import Path
import sqlite3
import os
import sys
import subprocess
import traceback
from app_config import *


# --- Helper Function ---
def get_kpi_display_name(
    kpi_data_row,
):
    if not kpi_data_row:
        return "N/D (KPI Data Mancante)"
    try:
        g_name = (
            kpi_data_row["group_name"]
            if "group_name" in kpi_data_row.keys()
            else "N/G (No Group)"
        )
        sg_name = (
            kpi_data_row["subgroup_name"]
            if "subgroup_name" in kpi_data_row.keys()
            else "N/S (No Subgroup)"
        )
        i_name = (
            kpi_data_row["indicator_name"]
            if "indicator_name" in kpi_data_row.keys()
            else "N/I (No Indicator)"
        )
        g_name = g_name or "N/G (Nome Gruppo Vuoto)"
        sg_name = sg_name or "N/S (Nome Sottogruppo Vuoto)"
        i_name = i_name or "N/I (Nome Indicatore Vuoto)"
        return f"{g_name} > {sg_name} > {i_name}"
    except (
        AttributeError,
        KeyError,
        IndexError,
        TypeError,
    ) as ex:
        print(f"Errore in get_kpi_display_name (Dati: {type(kpi_data_row)}): {ex}")
        return "N/D (Errore Struttura Dati KPI)"
    except Exception as ex_general:
        print(f"Errore imprevisto in get_kpi_display_name: {ex_general}")
        return "N/D (Errore Display Nome Imprevisto)"


def safe_get_from_row(row, key, default=None):
    if row is None:
        return default
    try:
        return row[key]
    except IndexError:
        return default
    except KeyError:
        return default


def _set_kpi_spec_fields_from_data(self, kpi_data_row):
    if kpi_data_row is None:
        return
    self.kpi_spec_desc_var.set(safe_get_from_row(kpi_data_row, "description", ""))
    self.kpi_spec_type_var.set(
        safe_get_from_row(
            kpi_data_row, "calculation_type", self.kpi_calc_type_options_tk[0]
        )
    )
    self.kpi_spec_unit_var.set(safe_get_from_row(kpi_data_row, "unit_of_measure", ""))
    self.kpi_spec_visible_var.set(
        bool(safe_get_from_row(kpi_data_row, "visible", True))
    )


class KpiApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestione Target KPI - Desktop v2.3 (Weighted Links)")
        self.geometry("1600x950")

        self._populating_kpi_spec_combos = False
        self._populating_target_kpi_entries = False
        self._master_sub_update_active = False

        style = ttk.Style(self)
        available_themes = style.theme_names()
        preferred_themes = ["clam", "alt", "vista", "xpnative", "default"]
        theme_set_successfully = False
        for theme_name_attempt in preferred_themes:
            if theme_name_attempt in available_themes:
                try:
                    style.theme_use(theme_name_attempt)
                    theme_set_successfully = True
                    print(f"Successfully set theme: {theme_name_attempt}")
                    break
                except tk.TclError:
                    print(f"Failed to set theme: {theme_name_attempt}, trying next.")
        if not theme_set_successfully:
            print(
                "CRITICAL: No ttk theme could be explicitly set. Using system default."
            )

        current_theme_in_use = style.theme_use()
        print(f"Final theme in use: {current_theme_in_use}")

        self.style_defaults = {}
        try:
            self.style_defaults["TLabelFrame_relief"] = style.lookup(
                "TLabelFrame", "relief"
            )
            self.style_defaults["TLabelFrame_borderwidth"] = style.lookup(
                "TLabelFrame", "borderwidth"
            )
            self.style_defaults["TLabelframe.Label_background"] = style.lookup(
                "TLabelframe.Label", "background"
            )
            self.style_defaults["TLabelframe.Label_foreground"] = style.lookup(
                "TLabelframe.Label", "foreground"
            )
            self.default_app_bg = self.cget("bg")
        except tk.TclError as e:
            print(
                f"Warning: Could not lookup some default style properties for theme '{current_theme_in_use}': {e}"
            )
            self.style_defaults.setdefault("TLabelFrame_relief", "groove")
            self.style_defaults.setdefault("TLabelFrame_borderwidth", 2)
            self.style_defaults.setdefault("TLabelframe.Label_background", "#f0f0f0")
            self.style_defaults.setdefault("TLabelframe.Label_foreground", "black")
            self.default_app_bg = "#f0f0f0"

        style.configure(
            "Accent.TButton",
            foreground="white",
            background="#007bff",
            font=("Calibri", 10),
        )
        style.configure("Treeview.Heading", font=("Calibri", 10, "bold"))
        style.configure("TListbox", font=("Calibri", 10))
        style.configure("TCombobox", font=("Calibri", 10))
        style.configure("TEntry", font=("Calibri", 10), padding=(3, 3))
        style.configure("TLabel", font=("Calibri", 10))
        style.configure("TButton", font=("Calibri", 10))
        style.configure("TRadiobutton", font=("Calibri", 10))
        style.configure("TCheckbutton", font=("Calibri", 10))
        style.configure("TSpinbox", font=("Calibri", 10))
        style.configure("TLabelframe.Label", font=("Calibri", 10, "bold"))
        style.configure("TLabelframe", font=("Calibri", 10))

        style.configure(
            "ManualState.TLabelframe.Label", background="#fff0f0", foreground="black"
        )
        style.configure(
            "DerivedState.TLabelframe.Label",
            background=self.style_defaults.get(
                "TLabelframe.Label_background", "#e0e0e0"
            ),
            foreground=self.style_defaults.get("TLabelframe.Label_foreground", "black"),
        )

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)

        self.target_frame = ttk.Frame(self.notebook, padding="10")
        self.kpi_hierarchy_frame = ttk.Frame(self.notebook, padding="10")
        self.kpi_template_frame = ttk.Frame(self.notebook, padding="10")
        self.kpi_spec_frame = ttk.Frame(self.notebook, padding="10")
        self.master_sub_link_frame = ttk.Frame(self.notebook, padding="10")
        self.stabilimenti_frame = ttk.Frame(self.notebook, padding="10")
        self.results_frame = ttk.Frame(self.notebook, padding="10")
        self.export_frame = ttk.Frame(self.notebook, padding="10")

        self.notebook.add(self.target_frame, text="🎯 Inserimento Target")
        self.notebook.add(self.kpi_hierarchy_frame, text="🗂️ Gestione Gerarchia KPI")
        self.notebook.add(
            self.kpi_template_frame, text="📋 Gestione Template Indicatori"
        )
        self.notebook.add(self.kpi_spec_frame, text="⚙️ Gestione Specifiche KPI")
        self.notebook.add(
            self.master_sub_link_frame, text="🔗 Gestione Link Master/Sub"
        )
        self.notebook.add(self.stabilimenti_frame, text="🏭 Gestione Stabilimenti")
        self.notebook.add(self.results_frame, text="📈 Visualizzazione Risultati")
        self.notebook.add(self.export_frame, text="📦 Esportazione Dati")

        self.distribution_profile_options_tk = [
            PROFILE_EVEN,
            PROFILE_ANNUAL_PROGRESSIVE,
            PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS,
            PROFILE_TRUE_ANNUAL_SINUSOIDAL,
            PROFILE_MONTHLY_SINUSOIDAL,
            PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE,
            PROFILE_QUARTERLY_PROGRESSIVE,
            PROFILE_QUARTERLY_SINUSOIDAL,
            "event_based_spikes_or_dips",
        ]
        self.repartition_logic_options_tk = [
            REPARTITION_LOGIC_ANNO,
            REPARTITION_LOGIC_MESE,
            REPARTITION_LOGIC_TRIMESTRE,
            REPARTITION_LOGIC_SETTIMANA,
        ]
        self.kpi_calc_type_options_tk = [CALC_TYPE_INCREMENTALE, CALC_TYPE_MEDIA]

        self.create_target_widgets()
        self.create_kpi_hierarchy_widgets()
        self.create_kpi_template_widgets()
        self.create_kpi_spec_widgets()
        self.create_master_sub_link_widgets()
        self.create_stabilimenti_widgets()
        self.create_results_widgets()
        self.create_export_widgets()

        self.refresh_all_relevant_data()

    def refresh_all_relevant_data(self):
        current_group_sel_hier_name = None
        if hasattr(self, "groups_listbox") and self.groups_listbox.curselection():
            current_group_sel_hier_name = self.groups_listbox.get(
                self.groups_listbox.curselection()[0]
            )
        current_subgroup_sel_hier_raw_name = None
        if hasattr(self, "subgroups_listbox") and self.subgroups_listbox.curselection():
            full_display_name = self.subgroups_listbox.get(
                self.subgroups_listbox.curselection()[0]
            )
            current_subgroup_sel_hier_raw_name = full_display_name.split(" (Template:")[
                0
            ]
        self.refresh_kpi_hierarchy_displays(
            pre_selected_group_name=current_group_sel_hier_name,
            pre_selected_subgroup_raw_name=current_subgroup_sel_hier_raw_name,
        )
        if hasattr(self, "refresh_kpi_templates_display"):
            self.refresh_kpi_templates_display()
        self.refresh_kpi_specs_tree()
        if hasattr(self, "refresh_master_sub_displays"):
            current_master_sub_selection_iid = None
            if (
                hasattr(self, "master_sub_kpi_tree")
                and self.master_sub_kpi_tree.selection()
            ):
                try:
                    current_master_sub_selection_iid = int(
                        self.master_sub_kpi_tree.selection()[0]
                    )
                except ValueError:
                    current_master_sub_selection_iid = None
            self.refresh_master_sub_displays(
                selected_kpi_spec_id_to_restore=current_master_sub_selection_iid
            )
        self.refresh_stabilimenti_tree()
        self.populate_target_comboboxes()
        self.populate_results_comboboxes()

    # --- Scheda Gestione Gerarchia KPI ---
    # ... (code for this tab remains unchanged) ...
    def create_kpi_hierarchy_widgets(
        self,
    ):
        main_frame = ttk.Frame(self.kpi_hierarchy_frame)
        main_frame.pack(fill="both", expand=True)
        group_frame = ttk.LabelFrame(main_frame, text="Gruppi KPI", padding=10)
        group_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.groups_listbox = tk.Listbox(
            group_frame, exportselection=False, height=15, width=25
        )
        self.groups_listbox.pack(fill="both", expand=True, pady=(0, 5))
        self.groups_listbox.bind(
            "<<ListboxSelect>>", self.on_group_select_hierarchy_tab
        )
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
        subgroup_frame = ttk.LabelFrame(main_frame, text="Sottogruppi", padding=10)
        subgroup_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.subgroups_listbox = tk.Listbox(
            subgroup_frame, exportselection=False, height=15, width=35
        )
        self.subgroups_listbox.pack(fill="both", expand=True, pady=(0, 5))
        self.subgroups_listbox.bind(
            "<<ListboxSelect>>", self.on_subgroup_select_hierarchy_tab
        )
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
        indicator_frame = ttk.LabelFrame(main_frame, text="Indicatori", padding=10)
        indicator_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.indicators_listbox = tk.Listbox(
            indicator_frame, exportselection=False, height=15, width=30
        )
        self.indicators_listbox.pack(fill="both", expand=True, pady=(0, 5))
        self.indicators_listbox.bind(
            "<<ListboxSelect>>", self.on_indicator_select_hierarchy_tab
        )
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
        self, pre_selected_group_name=None, pre_selected_subgroup_raw_name=None
    ):
        if (
            pre_selected_group_name is None
            and hasattr(self, "groups_listbox")
            and self.groups_listbox.curselection()
        ):
            pre_selected_group_name = self.groups_listbox.get(
                self.groups_listbox.curselection()[0]
            )
        actual_pre_selected_subgroup_raw_name = pre_selected_subgroup_raw_name
        if (
            actual_pre_selected_subgroup_raw_name is None
            and hasattr(self, "subgroups_listbox")
            and self.subgroups_listbox.curselection()
        ):
            full_display_sg_name = self.subgroups_listbox.get(
                self.subgroups_listbox.curselection()[0]
            )
            actual_pre_selected_subgroup_raw_name = full_display_sg_name.split(
                " (Template:"
            )[0]
        self.groups_listbox.delete(0, tk.END)
        self.current_groups_map = {}
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
            self.on_group_select_hierarchy_tab(
                pre_selected_subgroup_raw_name=actual_pre_selected_subgroup_raw_name
            )
        else:
            self.on_group_select_hierarchy_tab()

    def on_group_select_hierarchy_tab(
        self, event=None, pre_selected_subgroup_raw_name=None
    ):
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
            self.add_subgroup_btn.config(state="normal")
            subgroups_data = db_retriever.get_kpi_subgroups_by_group_revised(group_id)
            subgroup_selected_idx = -1
            for i, sg in enumerate(subgroups_data):
                raw_sg_name = sg["name"]
                display_name = raw_sg_name + (
                    f" (Template: {sg['template_name']})"
                    if sg.get("template_name")
                    else ""
                )
                self.subgroups_listbox.insert(tk.END, display_name)
                self.current_subgroups_map[display_name] = sg["id"]
                self.current_subgroups_raw_map[raw_sg_name] = {
                    "id": sg["id"],
                    "template_id": sg.get("indicator_template_id"),
                    "template_name": sg.get("template_name"),
                }
                if (
                    pre_selected_subgroup_raw_name
                    and raw_sg_name == pre_selected_subgroup_raw_name
                ):
                    subgroup_selected_idx = i
            if subgroup_selected_idx != -1:
                self.subgroups_listbox.selection_set(subgroup_selected_idx)
                self.subgroups_listbox.activate(subgroup_selected_idx)
                self.subgroups_listbox.see(subgroup_selected_idx)
            self.on_subgroup_select_hierarchy_tab()
        else:
            self.add_subgroup_btn.config(state="disabled")

    def on_subgroup_select_hierarchy_tab(self, event=None):
        self.indicators_listbox.delete(0, tk.END)
        self.current_indicators_map.clear()
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
        subgroup_id = self.current_subgroups_map.get(display_subgroup_name)
        if subgroup_id:
            raw_sg_name_for_check = display_subgroup_name.split(" (Template:")[0]
            subgroup_details = self.current_subgroups_raw_map.get(raw_sg_name_for_check)
            is_templated = (
                subgroup_details and subgroup_details.get("template_id") is not None
            )
            if is_templated:
                self.add_indicator_btn.config(state="disabled", text="Nuovo (da Tpl)")
            else:
                self.add_indicator_btn.config(state="normal", text="Nuovo")
            for ind in db_retriever.get_kpi_indicators_by_subgroup(subgroup_id):
                self.indicators_listbox.insert(tk.END, ind["name"])
                self.current_indicators_map[ind["name"]] = ind["id"]
        self.on_indicator_select_hierarchy_tab()

    def on_indicator_select_hierarchy_tab(self, event=None):
        subgroup_selection = self.subgroups_listbox.curselection()
        is_templated_subgroup = False
        if subgroup_selection:
            display_subgroup_name = self.subgroups_listbox.get(subgroup_selection[0])
            raw_sg_name_for_check = display_subgroup_name.split(" (Template:")[0]
            subgroup_details = self.current_subgroups_raw_map.get(raw_sg_name_for_check)
            is_templated_subgroup = (
                subgroup_details and subgroup_details.get("template_id") is not None
            )
        if self.indicators_listbox.curselection() and not is_templated_subgroup:
            self.edit_indicator_btn.config(state="normal")
            self.delete_indicator_btn.config(state="normal")
        else:
            self.edit_indicator_btn.config(state="disabled")
            self.delete_indicator_btn.config(state="disabled")

    def _select_item_in_listbox(
        self, listbox, item_name_to_select, is_subgroup_listbox=False
    ):
        listbox.selection_clear(0, tk.END)
        for i in range(listbox.size()):
            current_lb_item_display = listbox.get(i)
            item_matches = False
            if is_subgroup_listbox:
                raw_lb_item_name = current_lb_item_display.split(" (Template:")[0]
                if raw_lb_item_name == item_name_to_select:
                    item_matches = True
            elif current_lb_item_display == item_name_to_select:
                item_matches = True
            if item_matches:
                listbox.selection_set(i)
                listbox.activate(i)
                listbox.see(i)
                listbox.event_generate("<<ListboxSelect>>")
                return True
        return False

    def add_new_group(self):
        name = simpledialog.askstring("Nuovo Gruppo", "Nome Gruppo KPI:", parent=self)
        if name:
            try:
                db_manager.add_kpi_group(name)
                self.refresh_all_relevant_data()
                self.after(
                    100,
                    lambda n=name: self._select_item_in_listbox(self.groups_listbox, n),
                )
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile aggiungere gruppo: {e}")

    def edit_selected_group(self):
        sel_idx = self.groups_listbox.curselection()
        old_name = self.groups_listbox.get(sel_idx[0]) if sel_idx else None
        if not old_name:
            return
        group_id = self.current_groups_map.get(old_name)
        new_name = simpledialog.askstring(
            "Modifica Gruppo", "Nuovo nome:", initialvalue=old_name, parent=self
        )
        if new_name and new_name != old_name:
            try:
                db_manager.update_kpi_group(group_id, new_name)
                self.refresh_all_relevant_data()
                self.after(
                    100,
                    lambda n=new_name: self._select_item_in_listbox(
                        self.groups_listbox, n
                    ),
                )
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile modificare gruppo: {e}")

    def delete_selected_group(self):
        sel_idx = self.groups_listbox.curselection()
        name_to_delete = self.groups_listbox.get(sel_idx[0]) if sel_idx else None
        if not name_to_delete:
            return
        group_id = self.current_groups_map.get(name_to_delete)
        if messagebox.askyesno(
            "Conferma",
            f"Eliminare gruppo '{name_to_delete}' e tutti i suoi contenuti?",
            parent=self,
        ):
            try:
                db_manager.delete_kpi_group(group_id)
                self.refresh_all_relevant_data()
            except Exception as e:
                messagebox.showerror(
                    "Errore",
                    f"Impossibile eliminare gruppo: {e}\n{traceback.format_exc()}",
                )

    def add_new_subgroup(self):
        group_sel_idx = self.groups_listbox.curselection()
        if not group_sel_idx:
            messagebox.showwarning("Attenzione", "Seleziona un gruppo.")
            return
        group_name_for_refresh = self.groups_listbox.get(group_sel_idx[0])
        group_id = self.current_groups_map.get(group_name_for_refresh)
        if not group_id:
            return
        dialog = SubgroupEditorDialog(
            self, title="Nuovo Sottogruppo", group_id_context=group_id
        )
        if dialog.result_name and dialog.result_template_id is not False:
            try:
                db_manager.add_kpi_subgroup(
                    dialog.result_name, group_id, dialog.result_template_id
                )
                self.refresh_all_relevant_data()
                self.after(
                    100,
                    lambda gn=group_name_for_refresh, sgn_raw=dialog.result_name: self._select_item_in_listbox(
                        self.groups_listbox, gn
                    )
                    or self.after(
                        50,
                        lambda: self._select_item_in_listbox(
                            self.subgroups_listbox, sgn_raw, is_subgroup_listbox=True
                        ),
                    ),
                )
            except Exception as e:
                messagebox.showerror(
                    "Errore",
                    f"Impossibile aggiungere sottogruppo: {e}\n{traceback.format_exc()}",
                )

    def edit_selected_subgroup(self):
        group_sel_idx = self.groups_listbox.curselection()
        subgroup_sel_idx = self.subgroups_listbox.curselection()
        if not group_sel_idx or not subgroup_sel_idx:
            return
        group_name_for_refresh = self.groups_listbox.get(group_sel_idx[0])
        group_id = self.current_groups_map.get(group_name_for_refresh)
        display_name_subgroup = self.subgroups_listbox.get(subgroup_sel_idx[0])
        old_raw_name = display_name_subgroup.split(" (Template:")[0]
        subgroup_details = self.current_subgroups_raw_map.get(old_raw_name)
        if not subgroup_details or not group_id:
            messagebox.showerror("Errore", "Dettagli sottogruppo non trovati.")
            return
        dialog = SubgroupEditorDialog(
            self,
            title="Modifica Sottogruppo",
            group_id_context=group_id,
            initial_name=old_raw_name,
            initial_template_id=subgroup_details.get("template_id"),
        )
        if dialog.result_name and dialog.result_template_id is not False:
            if (
                dialog.result_name != old_raw_name
                or dialog.result_template_id != subgroup_details.get("template_id")
            ):
                try:
                    db_manager.update_kpi_subgroup(
                        subgroup_details["id"],
                        dialog.result_name,
                        group_id,
                        dialog.result_template_id,
                    )
                    self.refresh_all_relevant_data()
                    self.after(
                        100,
                        lambda gn=group_name_for_refresh, sgn_raw=dialog.result_name: self._select_item_in_listbox(
                            self.groups_listbox, gn
                        )
                        or self.after(
                            50,
                            lambda: self._select_item_in_listbox(
                                self.subgroups_listbox,
                                sgn_raw,
                                is_subgroup_listbox=True,
                            ),
                        ),
                    )
                except Exception as e:
                    messagebox.showerror(
                        "Errore",
                        f"Impossibile modificare sottogruppo: {e}\n{traceback.format_exc()}",
                    )

    def delete_selected_subgroup(self):
        subgroup_sel_idx = self.subgroups_listbox.curselection()
        if not subgroup_sel_idx:
            return
        display_name_to_delete = self.subgroups_listbox.get(subgroup_sel_idx[0])
        raw_name_confirm = display_name_to_delete.split(" (Template:")[0]
        subgroup_id = self.current_subgroups_map.get(display_name_to_delete)
        group_name_for_refresh = (
            self.groups_listbox.get(self.groups_listbox.curselection()[0])
            if self.groups_listbox.curselection()
            else None
        )
        if messagebox.askyesno(
            "Conferma",
            f"Eliminare sottogruppo '{raw_name_confirm}' e tutti i suoi contenuti?",
            parent=self,
        ):
            try:
                db_manager.delete_kpi_subgroup(subgroup_id)
                self.refresh_all_relevant_data()
                if group_name_for_refresh:
                    self.after(
                        100,
                        lambda gn=group_name_for_refresh: self._select_item_in_listbox(
                            self.groups_listbox, gn
                        ),
                    )
            except Exception as e:
                messagebox.showerror(
                    "Errore",
                    f"Impossibile eliminare sottogruppo: {e}\n{traceback.format_exc()}",
                )

    def add_new_indicator(self):
        subgroup_sel_idx = self.subgroups_listbox.curselection()
        if not subgroup_sel_idx:
            messagebox.showwarning("Attenzione", "Seleziona un sottogruppo.")
            return
        display_subgroup_name = self.subgroups_listbox.get(subgroup_sel_idx[0])
        raw_subgroup_name_for_refresh = display_subgroup_name.split(" (Template:")[0]
        subgroup_id = self.current_subgroups_map.get(display_subgroup_name)
        if not subgroup_id:
            return
        subgroup_details = self.current_subgroups_raw_map.get(
            raw_subgroup_name_for_refresh
        )
        if subgroup_details and subgroup_details.get("template_id") is not None:
            messagebox.showinfo(
                "Info",
                "Indicatori gestiti da template. Modifica il template.",
                parent=self,
            )
            return
        group_name_for_refresh = (
            self.groups_listbox.get(self.groups_listbox.curselection()[0])
            if self.groups_listbox.curselection()
            else None
        )
        name = simpledialog.askstring(
            "Nuovo Indicatore", "Nome Indicatore KPI:", parent=self
        )
        if name:
            try:
                db_manager.add_kpi_indicator(name, subgroup_id)
                self.refresh_all_relevant_data()
                if group_name_for_refresh:
                    self._select_item_in_listbox(
                        self.groups_listbox, group_name_for_refresh
                    )
                self.after(
                    50,
                    lambda sgn_raw=raw_subgroup_name_for_refresh, indn=name: self._select_item_in_listbox(
                        self.subgroups_listbox, sgn_raw, is_subgroup_listbox=True
                    )
                    or self.after(
                        50,
                        lambda: self._select_item_in_listbox(
                            self.indicators_listbox, indn
                        ),
                    ),
                )
            except Exception as e:
                messagebox.showerror(
                    "Errore", f"Impossibile aggiungere indicatore: {e}"
                )

    def edit_selected_indicator(self):
        indicator_sel_idx = self.indicators_listbox.curselection()
        subgroup_sel_idx = self.subgroups_listbox.curselection()
        if not indicator_sel_idx or not subgroup_sel_idx:
            return
        old_name = self.indicators_listbox.get(indicator_sel_idx[0])
        indicator_id = self.current_indicators_map.get(old_name)
        display_subgroup_name = self.subgroups_listbox.get(subgroup_sel_idx[0])
        raw_subgroup_name_for_refresh = display_subgroup_name.split(" (Template:")[0]
        subgroup_id = self.current_subgroups_map.get(display_subgroup_name)
        subgroup_details = self.current_subgroups_raw_map.get(
            raw_subgroup_name_for_refresh
        )
        if subgroup_details and subgroup_details.get("template_id") is not None:
            messagebox.showinfo(
                "Info",
                "Indicatori gestiti da template. Modifica il template.",
                parent=self,
            )
            return
        group_name_for_refresh = (
            self.groups_listbox.get(self.groups_listbox.curselection()[0])
            if self.groups_listbox.curselection()
            else None
        )
        new_name = simpledialog.askstring(
            "Modifica Indicatore", "Nuovo nome:", initialvalue=old_name, parent=self
        )
        if new_name and new_name != old_name:
            try:
                db_manager.update_kpi_indicator(indicator_id, new_name, subgroup_id)
                self.refresh_all_relevant_data()
                if group_name_for_refresh:
                    self._select_item_in_listbox(
                        self.groups_listbox, group_name_for_refresh
                    )
                self.after(
                    50,
                    lambda sgn_raw=raw_subgroup_name_for_refresh, indn=new_name: self._select_item_in_listbox(
                        self.subgroups_listbox, sgn_raw, is_subgroup_listbox=True
                    )
                    or self.after(
                        50,
                        lambda: self._select_item_in_listbox(
                            self.indicators_listbox, indn
                        ),
                    ),
                )
            except Exception as e:
                messagebox.showerror(
                    "Errore", f"Impossibile modificare indicatore: {e}"
                )

    def delete_selected_indicator(self):
        indicator_sel_idx = self.indicators_listbox.curselection()
        if not indicator_sel_idx:
            return
        name_to_delete = self.indicators_listbox.get(indicator_sel_idx[0])
        indicator_id = self.current_indicators_map.get(name_to_delete)
        raw_subgroup_name_for_refresh = None
        if self.subgroups_listbox.curselection():
            display_sg_name = self.subgroups_listbox.get(
                self.subgroups_listbox.curselection()[0]
            )
            raw_subgroup_name_for_refresh = display_sg_name.split(" (Template:")[0]
            subgroup_details = self.current_subgroups_raw_map.get(
                raw_subgroup_name_for_refresh
            )
            if subgroup_details and subgroup_details.get("template_id") is not None:
                messagebox.showinfo(
                    "Info",
                    "Indicatori gestiti da template. Rimuovi dal template.",
                    parent=self,
                )
                return
        group_name_for_refresh = (
            self.groups_listbox.get(self.groups_listbox.curselection()[0])
            if self.groups_listbox.curselection()
            else None
        )
        if messagebox.askyesno(
            "Conferma",
            f"Eliminare indicatore '{name_to_delete}' e la sua specifica/target?",
            parent=self,
        ):
            try:
                db_manager.delete_kpi_indicator(indicator_id)
                self.refresh_all_relevant_data()
                if group_name_for_refresh:
                    self._select_item_in_listbox(
                        self.groups_listbox, group_name_for_refresh
                    )
                if raw_subgroup_name_for_refresh:
                    self.after(
                        50,
                        lambda sgn_raw=raw_subgroup_name_for_refresh: self._select_item_in_listbox(
                            self.subgroups_listbox, sgn_raw, is_subgroup_listbox=True
                        ),
                    )
            except Exception as e:
                messagebox.showerror(
                    "Errore",
                    f"Impossibile eliminare indicatore: {e}\n{traceback.format_exc()}",
                )

    # --- Scheda Gestione Template Indicatori ---
    # ... (code for this tab remains unchanged) ...
    def create_kpi_template_widgets(
        self,
    ):
        main_frame = ttk.Frame(self.kpi_template_frame)
        main_frame.pack(fill="both", expand=True)
        template_list_frame = ttk.LabelFrame(
            main_frame, text="Template Indicatori KPI", padding=10
        )
        template_list_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.templates_listbox = tk.Listbox(
            template_list_frame, exportselection=False, height=15, width=30
        )
        self.templates_listbox.pack(fill="both", expand=True, pady=(0, 5))
        self.templates_listbox.bind("<<ListboxSelect>>", self.on_template_select)
        template_btn_frame = ttk.Frame(template_list_frame)
        template_btn_frame.pack(fill="x")
        ttk.Button(
            template_btn_frame,
            text="Nuovo Tpl",
            command=self.add_new_kpi_template,
            width=10,
        ).pack(side="left", padx=2)
        self.edit_template_btn = ttk.Button(
            template_btn_frame,
            text="Modifica Tpl",
            command=self.edit_selected_kpi_template,
            state="disabled",
            width=11,
        )
        self.edit_template_btn.pack(side="left", padx=2)
        self.delete_template_btn = ttk.Button(
            template_btn_frame,
            text="Elimina Tpl",
            command=self.delete_selected_kpi_template,
            state="disabled",
            width=11,
        )
        self.delete_template_btn.pack(side="left", padx=2)
        definitions_frame = ttk.LabelFrame(
            main_frame, text="Definizioni nel Template", padding=10
        )
        definitions_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.template_definitions_tree = ttk.Treeview(
            definitions_frame,
            columns=(
                "ID",
                "Nome Indicatore",
                "Tipo Calcolo",
                "Unità",
                "Visibile",
                "Descrizione",
            ),
            show="headings",
            height=14,
        )
        cols_defs = {
            "ID": 40,
            "Nome Indicatore": 180,
            "Tipo Calcolo": 100,
            "Unità": 80,
            "Visibile": 60,
            "Descrizione": 220,
        }
        for col, width in cols_defs.items():
            self.template_definitions_tree.heading(col, text=col)
            self.template_definitions_tree.column(
                col,
                width=width,
                anchor="center" if col in ["ID", "Visibile"] else "w",
                stretch=(col in ["Descrizione", "Nome Indicatore"]),
            )
        self.template_definitions_tree.pack(fill="both", expand=True, pady=(0, 5))
        self.template_definitions_tree.bind(
            "<<TreeviewSelect>>", self.on_template_definition_select
        )
        definition_btn_frame = ttk.Frame(definitions_frame)
        definition_btn_frame.pack(fill="x")
        self.add_definition_btn = ttk.Button(
            definition_btn_frame,
            text="Aggiungi Def.",
            command=self.add_new_template_definition,
            state="disabled",
            width=12,
        )
        self.add_definition_btn.pack(side="left", padx=2)
        self.edit_definition_btn = ttk.Button(
            definition_btn_frame,
            text="Modifica Def.",
            command=self.edit_selected_template_definition,
            state="disabled",
            width=12,
        )
        self.edit_definition_btn.pack(side="left", padx=2)
        self.remove_definition_btn = ttk.Button(
            definition_btn_frame,
            text="Rimuovi Def.",
            command=self.remove_selected_template_definition,
            state="disabled",
            width=12,
        )
        self.remove_definition_btn.pack(side="left", padx=2)
        self.current_templates_map = {}
        self.current_template_definitions_map = {}

    def refresh_kpi_templates_display(self, pre_selected_template_name=None):
        if (
            pre_selected_template_name is None
            and hasattr(self, "templates_listbox")
            and self.templates_listbox.curselection()
        ):
            pre_selected_template_name = self.templates_listbox.get(
                self.templates_listbox.curselection()[0]
            )
        self.templates_listbox.delete(0, tk.END)
        self.current_templates_map.clear()
        selected_idx = -1
        for i, template in enumerate(db_retriever.get_kpi_indicator_templates()):
            self.templates_listbox.insert(tk.END, template["name"])
            self.current_templates_map[template["name"]] = template["id"]
            if template["name"] == pre_selected_template_name:
                selected_idx = i
        if selected_idx != -1:
            self.templates_listbox.selection_set(selected_idx)
            self.templates_listbox.activate(selected_idx)
            self.templates_listbox.see(selected_idx)
        self.on_template_select()

    def on_template_select(self, event=None):
        for i in self.template_definitions_tree.get_children():
            self.template_definitions_tree.delete(i)
        self.current_template_definitions_map.clear()
        buttons_state = "disabled"
        if self.templates_listbox.curselection():
            buttons_state = "normal"
        self.edit_template_btn.config(state=buttons_state)
        self.delete_template_btn.config(state=buttons_state)
        self.add_definition_btn.config(state=buttons_state)
        self.edit_definition_btn.config(state="disabled")
        self.remove_definition_btn.config(state="disabled")
        if buttons_state == "normal":
            template_name = self.templates_listbox.get(
                self.templates_listbox.curselection()[0]
            )
            template_id = self.current_templates_map.get(template_name)
            if template_id:
                for defi in db_retriever.get_template_defined_indicators(template_id):
                    vis_str = "Sì" if defi["default_visible"] else "No"
                    iid = self.template_definitions_tree.insert(
                        "",
                        "end",
                        values=(
                            defi["id"],
                            defi["indicator_name_in_template"],
                            defi["default_calculation_type"],
                            defi["default_unit_of_measure"] or "",
                            vis_str,
                            defi["default_description"] or "",
                        ),
                    )
                    self.current_template_definitions_map[iid] = defi["id"]
        self.on_template_definition_select()

    def on_template_definition_select(self, event=None):
        buttons_state = (
            "normal" if self.template_definitions_tree.selection() else "disabled"
        )
        self.edit_definition_btn.config(state=buttons_state)
        self.remove_definition_btn.config(state=buttons_state)

    def add_new_kpi_template(self):
        name = simpledialog.askstring("Nuovo Template", "Nome Template:", parent=self)
        if name:
            desc = (
                simpledialog.askstring(
                    "Nuovo Template", "Descrizione (opzionale):", parent=self
                )
                or ""
            )
            try:
                db_manager.add_kpi_indicator_template(name, desc)
                self.refresh_kpi_templates_display(pre_selected_template_name=name)
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile aggiungere template: {e}")

    def edit_selected_kpi_template(self):
        sel_idx = self.templates_listbox.curselection()
        old_name = self.templates_listbox.get(sel_idx[0]) if sel_idx else None
        if not old_name:
            return
        template_id = self.current_templates_map.get(old_name)
        template_data = db_retriever.get_kpi_indicator_template_by_id(template_id)
        if not template_data:
            return
        new_name = simpledialog.askstring(
            "Modifica Template", "Nuovo nome:", initialvalue=old_name, parent=self
        )
        if new_name:
            new_desc = simpledialog.askstring(
                "Modifica Template",
                "Nuova descrizione:",
                initialvalue=template_data["description"],
                parent=self,
            )
            new_desc = (
                new_desc if new_desc is not None else template_data["description"]
            )
            if new_name != old_name or new_desc != template_data["description"]:
                try:
                    db_manager.update_kpi_indicator_template(
                        template_id, new_name, new_desc
                    )
                    self.refresh_kpi_templates_display(
                        pre_selected_template_name=new_name
                    )
                    self.refresh_all_relevant_data()
                except Exception as e:
                    messagebox.showerror(
                        "Errore", f"Impossibile modificare template: {e}"
                    )

    def delete_selected_kpi_template(self):
        sel_idx = self.templates_listbox.curselection()
        name_to_delete = self.templates_listbox.get(sel_idx[0]) if sel_idx else None
        if not name_to_delete:
            return
        template_id = self.current_templates_map.get(name_to_delete)
        if messagebox.askyesno(
            "Conferma",
            f"Eliminare template '{name_to_delete}'?\nSottogruppi collegati verranno scollegati e i loro indicatori (da questo template) rimossi.",
            parent=self,
        ):
            try:
                db_manager.delete_kpi_indicator_template(template_id)
                self.refresh_kpi_templates_display()
                self.refresh_all_relevant_data()
            except Exception as e:
                messagebox.showerror(
                    "Errore",
                    f"Impossibile eliminare template: {e}\n{traceback.format_exc()}",
                )

    def add_new_template_definition(self):
        template_sel_idx = self.templates_listbox.curselection()
        if not template_sel_idx:
            messagebox.showwarning("Attenzione", "Seleziona un template.")
            return
        template_id = self.current_templates_map.get(
            self.templates_listbox.get(template_sel_idx[0])
        )
        dialog = TemplateDefinitionEditorDialog(
            self, title="Nuova Definizione Indicatore", template_id_context=template_id
        )
        if dialog.result_data:
            data = dialog.result_data
            try:
                db_manager.add_indicator_definition_to_template(
                    template_id,
                    data["name"],
                    data["calc_type"],
                    data["unit"],
                    data["visible"],
                    data["desc"],
                )
                self.on_template_select()
                self.refresh_all_relevant_data()
            except Exception as e:
                messagebox.showerror(
                    "Errore",
                    f"Impossibile aggiungere definizione: {e}\n{traceback.format_exc()}",
                )

    def edit_selected_template_definition(self):
        def_sel_iid = self.template_definitions_tree.focus()
        template_sel_idx = self.templates_listbox.curselection()
        if not def_sel_iid or not template_sel_idx:
            return
        template_id = self.current_templates_map.get(
            self.templates_listbox.get(template_sel_idx[0])
        )
        definition_id_to_edit = self.current_template_definitions_map.get(def_sel_iid)
        current_def_data = db_retriever.get_template_indicator_definition_by_id(
            definition_id_to_edit
        )
        if not current_def_data:
            messagebox.showerror("Errore", "Definizione non trovata.")
            return
        dialog = TemplateDefinitionEditorDialog(
            self,
            title="Modifica Definizione Indicatore",
            template_id_context=template_id,
            initial_data=current_def_data,
        )
        if dialog.result_data:
            data = dialog.result_data
            try:
                db_manager.update_indicator_definition_in_template(
                    definition_id_to_edit,
                    data["name"],
                    data["calc_type"],
                    data["unit"],
                    data["visible"],
                    data["desc"],
                )
                self.on_template_select()
                self.refresh_all_relevant_data()
            except Exception as e:
                messagebox.showerror(
                    "Errore",
                    f"Impossibile modificare definizione: {e}\n{traceback.format_exc()}",
                )

    def remove_selected_template_definition(self):
        def_sel_iid = self.template_definitions_tree.focus()
        if not def_sel_iid:
            return
        definition_id_to_remove = self.current_template_definitions_map.get(def_sel_iid)
        def_name_confirm = self.template_definitions_tree.item(def_sel_iid, "values")[1]
        if messagebox.askyesno(
            "Conferma",
            f"Rimuovere definizione '{def_name_confirm}' dal template?\nQuesto rimuoverà l'indicatore e i dati dai sottogruppi collegati.",
            parent=self,
        ):
            try:
                db_manager.remove_indicator_definition_from_template(
                    definition_id_to_remove
                )
                self.on_template_select()
                self.refresh_all_relevant_data()
            except Exception as e:
                messagebox.showerror(
                    "Errore",
                    f"Impossibile rimuovere definizione: {e}\n{traceback.format_exc()}",
                )

    # --- Scheda Gestione Specifiche KPI ---
    # ... (code for this tab remains unchanged) ...
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
            width=30,
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
        self.kpi_spec_type_var = tk.StringVar(value=self.kpi_calc_type_options_tk[0])
        self.kpi_spec_type_cb = ttk.Combobox(
            attr_frame,
            textvariable=self.kpi_spec_type_var,
            values=self.kpi_calc_type_options_tk,
            state="readonly",
        )
        self.kpi_spec_type_cb.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        ttk.Label(attr_frame, text="Unità Misura:").grid(
            row=2, column=0, sticky="w", padx=5, pady=2
        )
        self.kpi_spec_unit_var = tk.StringVar()
        ttk.Entry(attr_frame, textvariable=self.kpi_spec_unit_var, width=40).grid(
            row=2, column=1, padx=5, pady=2, sticky="ew"
        )
        self.kpi_spec_visible_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            attr_frame, text="Visibile per Target", variable=self.kpi_spec_visible_var
        ).grid(row=3, column=1, sticky="w", padx=5, pady=2)
        self.current_editing_kpi_id = None
        self.selected_indicator_id_for_spec = None
        kpi_spec_btn_frame_outer = ttk.Frame(add_kpi_frame_outer)
        kpi_spec_btn_frame_outer.pack(pady=10)
        kpi_spec_btn_frame = ttk.Frame(kpi_spec_btn_frame_outer)
        kpi_spec_btn_frame.pack()
        self.save_kpi_spec_btn = ttk.Button(
            kpi_spec_btn_frame,
            text="Aggiungi Specifica",
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
                "ID",
                "Gruppo",
                "Sottogruppo",
                "Indicatore",
                "Descrizione",
                "Tipo Calcolo",
                "Unità",
                "Visibile",
                "Template SG",
            ),
            show="headings",
        )
        cols_widths = {
            "ID": 40,
            "Gruppo": 120,
            "Sottogruppo": 150,
            "Indicatore": 150,
            "Descrizione": 180,
            "Tipo Calcolo": 90,
            "Unità": 80,
            "Visibile": 60,
            "Template SG": 120,
        }
        for col, width in cols_widths.items():
            self.kpi_specs_tree.heading(col, text=col)
            anchor = "center" if col in ["ID", "Visibile"] else "w"
            stretch = (
                tk.NO if col in ["ID", "Visibile", "Tipo Calcolo", "Unità"] else tk.YES
            )
            self.kpi_specs_tree.column(col, width=width, anchor=anchor, stretch=stretch)
        tree_scrollbar = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.kpi_specs_tree.yview
        )
        self.kpi_specs_tree.configure(yscrollcommand=tree_scrollbar.set)
        tree_scrollbar.pack(side="right", fill="y")
        self.kpi_specs_tree.pack(side="left", expand=True, fill="both")
        self.kpi_specs_tree.bind("<Double-1>", self.on_kpi_spec_double_click)
        tree_buttons_frame = ttk.Frame(self.kpi_spec_frame)
        tree_buttons_frame.pack(fill="x", pady=5)
        ttk.Button(
            tree_buttons_frame,
            text="Elimina Specifica Selezionata",
            command=self.delete_selected_kpi_spec,
        ).pack(side="left", padx=5)

    def on_kpi_spec_group_selected_ui_driven(self, event=None):
        if self._populating_kpi_spec_combos:
            return
        self._populate_kpi_spec_subgroups()

    def on_kpi_spec_subgroup_selected_ui_driven(self, event=None):
        if self._populating_kpi_spec_combos:
            return
        self._populate_kpi_spec_indicators()

    def on_kpi_spec_indicator_selected_ui_driven(self, event=None):
        if self._populating_kpi_spec_combos:
            return
        self._load_or_prepare_kpi_spec_fields()

    def populate_kpi_spec_hier_combos(
        self,
        group_to_select_name=None,
        subgroup_to_select_raw_name=None,
        indicator_to_select_name=None,
    ):
        self._populating_kpi_spec_combos = True
        self.groups_for_kpi_spec = db_retriever.get_kpi_groups()
        group_names = [g["name"] for g in self.groups_for_kpi_spec]
        self.kpi_spec_group_cb["values"] = group_names
        if group_to_select_name and group_to_select_name in group_names:
            self.kpi_spec_group_var.set(group_to_select_name)
            self._populate_kpi_spec_subgroups(
                subgroup_to_select_raw_name, indicator_to_select_name
            )
        else:
            self.kpi_spec_group_var.set("")
            self.kpi_spec_subgroup_var.set("")
            self.kpi_spec_indicator_var.set("")
            self.kpi_spec_subgroup_cb["values"] = []
            self.kpi_spec_indicator_cb["values"] = []
            self.clear_kpi_spec_fields(keep_hierarchy=False)
        self._populating_kpi_spec_combos = False

    def _populate_kpi_spec_subgroups(
        self, subgroup_to_select_raw_name=None, pre_selected_indicator_name=None
    ):
        group_name = self.kpi_spec_group_var.get()
        self.kpi_spec_subgroup_cb["values"] = []
        self.kpi_spec_indicator_cb["values"] = []
        if not subgroup_to_select_raw_name:
            self.kpi_spec_subgroup_var.set("")
        if not pre_selected_indicator_name:
            self.kpi_spec_indicator_var.set("")
        selected_group_obj = next(
            (g for g in self.groups_for_kpi_spec if g["name"] == group_name), None
        )
        if selected_group_obj:
            self.subgroups_for_kpi_spec_details = (
                db_retriever.get_kpi_subgroups_by_group_revised(
                    selected_group_obj["id"]
                )
            )
            self.subgroup_display_to_raw_map_spec = {}
            display_subgroup_names = []
            for sg_dict in self.subgroups_for_kpi_spec_details:
                raw_name = sg_dict["name"]
                display_name = raw_name + (
                    f" (Tpl: {sg_dict['template_name']})"
                    if sg_dict.get("template_name")
                    else ""
                )
                display_subgroup_names.append(display_name)
                self.subgroup_display_to_raw_map_spec[display_name] = raw_name
            self.kpi_spec_subgroup_cb["values"] = display_subgroup_names
            target_display_subgroup_name_to_set = (
                next(
                    (
                        dn
                        for dn, rn in self.subgroup_display_to_raw_map_spec.items()
                        if rn == subgroup_to_select_raw_name
                    ),
                    None,
                )
                if subgroup_to_select_raw_name
                else None
            )
            if target_display_subgroup_name_to_set:
                self.kpi_spec_subgroup_var.set(target_display_subgroup_name_to_set)
                self._populate_kpi_spec_indicators(pre_selected_indicator_name)
            elif (
                not self._populating_kpi_spec_combos and not subgroup_to_select_raw_name
            ):
                self.clear_kpi_spec_fields(keep_hierarchy=True, keep_group=True)
        elif not self._populating_kpi_spec_combos:
            self.clear_kpi_spec_fields(keep_hierarchy=True)

    def _populate_kpi_spec_indicators(self, pre_selected_indicator_name=None):
        display_subgroup_name = self.kpi_spec_subgroup_var.get()
        self.kpi_spec_indicator_cb["values"] = []
        if not pre_selected_indicator_name:
            self.kpi_spec_indicator_var.set("")
        raw_subgroup_name_lookup = self.subgroup_display_to_raw_map_spec.get(
            display_subgroup_name
        )
        selected_subgroup_obj_from_list = (
            next(
                (
                    sg
                    for sg in self.subgroups_for_kpi_spec_details
                    if sg["name"] == raw_subgroup_name_lookup
                ),
                None,
            )
            if raw_subgroup_name_lookup
            and hasattr(self, "subgroups_for_kpi_spec_details")
            else None
        )
        if selected_subgroup_obj_from_list:
            self.indicators_for_kpi_spec = db_retriever.get_kpi_indicators_by_subgroup(
                selected_subgroup_obj_from_list["id"]
            )
            indicator_names = [ind["name"] for ind in self.indicators_for_kpi_spec]
            self.kpi_spec_indicator_cb["values"] = indicator_names
            if (
                pre_selected_indicator_name
                and pre_selected_indicator_name in indicator_names
            ):
                self.kpi_spec_indicator_var.set(pre_selected_indicator_name)
                if self._populating_kpi_spec_combos:
                    self._load_or_prepare_kpi_spec_fields()
            elif (
                not self._populating_kpi_spec_combos and not pre_selected_indicator_name
            ):
                self.clear_kpi_spec_fields(
                    keep_hierarchy=True, keep_group=True, keep_subgroup=True
                )
        elif not self._populating_kpi_spec_combos:
            self.clear_kpi_spec_fields(keep_hierarchy=True, keep_group=True)

    def _load_or_prepare_kpi_spec_fields(self):
        indicator_name = self.kpi_spec_indicator_var.get()
        self.selected_indicator_id_for_spec = None
        self.current_editing_kpi_id = None
        self.save_kpi_spec_btn.config(text="Aggiungi Specifica")
        selected_indicator_obj = (
            next(
                (
                    ind
                    for ind in self.indicators_for_kpi_spec
                    if ind["name"] == indicator_name
                ),
                None,
            )
            if hasattr(self, "indicators_for_kpi_spec") and self.indicators_for_kpi_spec
            else None
        )
        if selected_indicator_obj:
            self.selected_indicator_id_for_spec = selected_indicator_obj["id"]
            all_kpi_specs_list = db_retriever.get_all_kpis_detailed()
            existing_kpi_spec_for_indicator = next(
                (
                    kpi_spec
                    for kpi_spec in all_kpi_specs_list
                    if kpi_spec["actual_indicator_id"]
                    == self.selected_indicator_id_for_spec
                ),
                None,
            )
            if existing_kpi_spec_for_indicator:
                self._set_kpi_spec_fields_from_data(existing_kpi_spec_for_indicator)
                self.current_editing_kpi_id = existing_kpi_spec_for_indicator["id"]
                self.save_kpi_spec_btn.config(text="Modifica Specifica")
            else:
                self.clear_kpi_spec_fields(
                    keep_hierarchy=True,
                    keep_group=True,
                    keep_subgroup=True,
                    keep_indicator=True,
                )
                display_subgroup_name = self.kpi_spec_subgroup_var.get()
                raw_subgroup_name_lookup = self.subgroup_display_to_raw_map_spec.get(
                    display_subgroup_name
                )
                subgroup_obj = (
                    next(
                        (
                            sg
                            for sg in self.subgroups_for_kpi_spec_details
                            if sg["name"] == raw_subgroup_name_lookup
                        ),
                        None,
                    )
                    if raw_subgroup_name_lookup
                    and hasattr(self, "subgroups_for_kpi_spec_details")
                    else None
                )
                if subgroup_obj and subgroup_obj.get("template_id"):
                    template_id = subgroup_obj["template_id"]
                    template_def = (
                        db_retriever.get_template_indicator_definition_by_name(
                            template_id, indicator_name
                        )
                    )
                    if template_def:
                        self.kpi_spec_desc_var.set(
                            template_def["default_description"] or ""
                        )
                        self.kpi_spec_type_var.set(
                            template_def["default_calculation_type"]
                            or self.kpi_calc_type_options_tk[0]
                        )
                        self.kpi_spec_unit_var.set(
                            template_def["default_unit_of_measure"] or ""
                        )
                        self.kpi_spec_visible_var.set(
                            bool(template_def["default_visible"])
                        )
        else:
            self.clear_kpi_spec_fields(
                keep_hierarchy=True,
                keep_group=True,
                keep_subgroup=True,
                keep_indicator=False,
            )

    def _set_kpi_spec_fields_from_data(self, kpi_data_row_obj):
        if kpi_data_row_obj is None:
            self.kpi_spec_desc_var.set("")
            self.kpi_spec_type_var.set(self.kpi_calc_type_options_tk[0])
            self.kpi_spec_unit_var.set("")
            self.kpi_spec_visible_var.set(True)
            return
        kpi_data_dict = dict(kpi_data_row_obj)
        self.kpi_spec_desc_var.set(kpi_data_dict.get("description", ""))
        self.kpi_spec_type_var.set(
            kpi_data_dict.get("calculation_type", self.kpi_calc_type_options_tk[0])
        )
        self.kpi_spec_unit_var.set(kpi_data_dict.get("unit_of_measure", ""))
        self.kpi_spec_visible_var.set(bool(kpi_data_dict.get("visible", True)))

    def load_kpi_spec_for_editing(self, kpi_data_full_dict):
        self._populating_kpi_spec_combos = True
        self.current_editing_kpi_id = kpi_data_full_dict["id"]
        self.selected_indicator_id_for_spec = kpi_data_full_dict["actual_indicator_id"]
        self.populate_kpi_spec_hier_combos(
            group_to_select_name=kpi_data_full_dict["group_name"],
            subgroup_to_select_raw_name=kpi_data_full_dict["subgroup_name"],
            indicator_to_select_name=kpi_data_full_dict["indicator_name"],
        )
        self._populating_kpi_spec_combos = False
        if self.kpi_spec_indicator_var.get() == kpi_data_full_dict["indicator_name"]:
            self._set_kpi_spec_fields_from_data(kpi_data_full_dict)
            self.save_kpi_spec_btn.config(text="Modifica Specifica")
        else:
            self.clear_kpi_spec_fields_button_action()

    def clear_kpi_spec_fields_button_action(self):
        self._populating_kpi_spec_combos = True
        self.kpi_spec_group_var.set("")
        self.kpi_spec_subgroup_var.set("")
        self.kpi_spec_indicator_var.set("")
        self.kpi_spec_subgroup_cb["values"] = []
        self.kpi_spec_indicator_cb["values"] = []
        self.clear_kpi_spec_fields(keep_hierarchy=False)
        self._populating_kpi_spec_combos = False
        self.populate_kpi_spec_hier_combos()

    def clear_kpi_spec_fields(
        self,
        keep_hierarchy=False,
        keep_group=False,
        keep_subgroup=False,
        keep_indicator=False,
    ):
        if not keep_hierarchy:
            if not (self._populating_kpi_spec_combos and keep_group):
                self.kpi_spec_group_var.set("")
            if not (self._populating_kpi_spec_combos and keep_subgroup):
                self.kpi_spec_subgroup_var.set("")
            if not (self._populating_kpi_spec_combos and keep_indicator):
                self.kpi_spec_indicator_var.set("")
            self.selected_indicator_id_for_spec = None
        elif not keep_group:
            if not self._populating_kpi_spec_combos:
                self.kpi_spec_group_var.set("")
            if not (self._populating_kpi_spec_combos and keep_subgroup):
                self.kpi_spec_subgroup_var.set("")
            if not (self._populating_kpi_spec_combos and keep_indicator):
                self.kpi_spec_indicator_var.set("")
            self.selected_indicator_id_for_spec = None
        elif not keep_subgroup:
            if not self._populating_kpi_spec_combos:
                self.kpi_spec_subgroup_var.set("")
            if not (self._populating_kpi_spec_combos and keep_indicator):
                self.kpi_spec_indicator_var.set("")
            self.selected_indicator_id_for_spec = None
        elif not keep_indicator:
            if not self._populating_kpi_spec_combos:
                self.kpi_spec_indicator_var.set("")
            self.selected_indicator_id_for_spec = None
        self.kpi_spec_desc_var.set("")
        self.kpi_spec_type_var.set(self.kpi_calc_type_options_tk[0])
        self.kpi_spec_unit_var.set("")
        self.kpi_spec_visible_var.set(True)
        if not (keep_hierarchy and keep_indicator and keep_subgroup and keep_group):
            self.current_editing_kpi_id = None
            self.save_kpi_spec_btn.config(text="Aggiungi Specifica")

    def save_kpi_specification(self):
        if not self.selected_indicator_id_for_spec:
            messagebox.showerror(
                "Errore", "Nessun indicatore valido selezionato per la specifica."
            )
            return
        desc = self.kpi_spec_desc_var.get().strip()
        calc_type = self.kpi_spec_type_var.get()
        unit = self.kpi_spec_unit_var.get().strip()
        visible = self.kpi_spec_visible_var.get()
        try:
            if self.current_editing_kpi_id is not None:
                db_manager.update_kpi_spec(
                    self.current_editing_kpi_id,
                    self.selected_indicator_id_for_spec,
                    desc,
                    calc_type,
                    unit,
                    visible,
                )
                messagebox.showinfo("Successo", "Specifica KPI aggiornata!")
            else:
                db_manager.add_kpi_spec(
                    self.selected_indicator_id_for_spec, desc, calc_type, unit, visible
                )
                messagebox.showinfo(
                    "Successo", "Nuova specifica KPI aggiunta/aggiornata!"
                )
            self.refresh_all_relevant_data()
            self.clear_kpi_spec_fields_button_action()
        except sqlite3.IntegrityError as ie:
            if (
                "UNIQUE constraint failed: kpis.indicator_id" in str(ie)
                and self.current_editing_kpi_id is None
            ):
                messagebox.showerror(
                    "Errore",
                    f"Specifica KPI per '{self.kpi_spec_indicator_var.get()}' esiste già.",
                )
            else:
                messagebox.showerror("Errore Integrità DB", f"Errore DB: {ie}")
        except Exception as e:
            messagebox.showerror(
                "Errore Salvataggio",
                f"Salvataggio fallito: {e}\n{traceback.format_exc()}",
            )

    def delete_selected_kpi_spec(self):
        selected_item_iid = self.kpi_specs_tree.focus()
        if not selected_item_iid:
            messagebox.showwarning("Attenzione", "Nessuna specifica KPI selezionata.")
            return
        item_values = self.kpi_specs_tree.item(selected_item_iid, "values")
        try:
            kpi_spec_id_to_delete = int(item_values[0])
        except (TypeError, ValueError, IndexError):
            messagebox.showerror("Errore", "ID specifica KPI non valido.")
            return
        kpi_name_confirm = f"{item_values[1]} > {item_values[2]} > {item_values[3]}"
        if messagebox.askyesno(
            "Conferma",
            f"Eliminare specifica KPI:\n{kpi_name_confirm} (ID Spec: {kpi_spec_id_to_delete})?\nEliminerà anche tutti i target associati e i link master/sub.",
            parent=self,
        ):
            try:
                kpi_spec_details = db_retriever.get_kpi_detailed_by_id(
                    kpi_spec_id_to_delete
                )
                if (
                    not kpi_spec_details
                    or "actual_indicator_id" not in kpi_spec_details
                ):
                    messagebox.showerror(
                        "Errore",
                        f"Impossibile trovare kpi_indicator.id per kpi_spec.id {kpi_spec_id_to_delete}.",
                    )
                    return
                actual_indicator_id_to_delete = kpi_spec_details["actual_indicator_id"]
                db_manager.delete_kpi_indicator(actual_indicator_id_to_delete)
                messagebox.showinfo(
                    "Successo", "Specifica KPI e relativi dati eliminati."
                )
                self.refresh_all_relevant_data()
                self.clear_kpi_spec_fields_button_action()
            except Exception as e:
                messagebox.showerror(
                    "Errore Eliminazione",
                    f"Impossibile eliminare: {e}\n{traceback.format_exc()}",
                )

    def refresh_kpi_specs_tree(self):
        for i in self.kpi_specs_tree.get_children():
            self.kpi_specs_tree.delete(i)
        all_kpis_data = db_retriever.get_all_kpis_detailed()
        indicator_to_template_name_map = {}
        all_groups_for_map = db_retriever.get_kpi_groups()
        for grp_map_dict in all_groups_for_map:
            subgroups_for_map_list = db_retriever.get_kpi_subgroups_by_group_revised(
                grp_map_dict["id"]
            )
            for sg_map_dict in subgroups_for_map_list:
                if sg_map_dict.get("template_name"):
                    indicators_in_sg_list = db_retriever.get_kpi_indicators_by_subgroup(
                        sg_map_dict["id"]
                    )
                    for ind_map_dict in indicators_in_sg_list:
                        indicator_to_template_name_map[ind_map_dict["id"]] = (
                            sg_map_dict["template_name"]
                        )
        for kpi_row_dict in all_kpis_data:
            template_name_display = indicator_to_template_name_map.get(
                kpi_row_dict["actual_indicator_id"], ""
            )
            self.kpi_specs_tree.insert(
                "",
                "end",
                values=(
                    kpi_row_dict["id"],
                    kpi_row_dict["group_name"],
                    kpi_row_dict["subgroup_name"],
                    kpi_row_dict["indicator_name"],
                    kpi_row_dict["description"],
                    kpi_row_dict["calculation_type"],
                    kpi_row_dict["unit_of_measure"] or "",
                    "Sì" if kpi_row_dict["visible"] else "No",
                    template_name_display,
                ),
            )
        current_group_sel_name = self.kpi_spec_group_var.get()
        current_subgroup_sel_display_name = self.kpi_spec_subgroup_var.get()
        current_indicator_sel_name = self.kpi_spec_indicator_var.get()
        current_subgroup_sel_raw_name = (
            self.subgroup_display_to_raw_map_spec.get(current_subgroup_sel_display_name)
            if hasattr(self, "subgroup_display_to_raw_map_spec")
            and current_subgroup_sel_display_name
            else (
                current_subgroup_sel_display_name.split(" (Tpl:")[0]
                if current_subgroup_sel_display_name
                else None
            )
        )
        self.populate_kpi_spec_hier_combos(
            group_to_select_name=(
                current_group_sel_name if current_group_sel_name else None
            ),
            subgroup_to_select_raw_name=(
                current_subgroup_sel_raw_name if current_subgroup_sel_raw_name else None
            ),
            indicator_to_select_name=(
                current_indicator_sel_name if current_indicator_sel_name else None
            ),
        )

    def on_kpi_spec_double_click(self, event):
        item_iid_str = self.kpi_specs_tree.focus()
        if not item_iid_str:
            return
        item_values = self.kpi_specs_tree.item(item_iid_str, "values")
        if not item_values or len(item_values) == 0:
            return
        try:
            kpi_id_to_edit = int(item_values[0])
        except (TypeError, ValueError, IndexError):
            messagebox.showerror("Errore", "ID KPI non valido.")
            return
        kpi_data_full_dict = db_retriever.get_kpi_detailed_by_id(kpi_id_to_edit)
        if kpi_data_full_dict:
            self.load_kpi_spec_for_editing(kpi_data_full_dict)
        else:
            messagebox.showerror(
                "Errore",
                f"Impossibile caricare dettagli per KPI Spec ID {kpi_id_to_edit}.",
            )

    # --- Scheda Gestione Stabilimenti ---
    # ... (code for this tab remains unchanged) ...
    def create_stabilimenti_widgets(self):
        self.st_tree = ttk.Treeview(
            self.stabilimenti_frame, columns=("ID", "Nome", "Visibile"), show="headings"
        )
        for col in self.st_tree["columns"]:
            self.st_tree.heading(col, text=col)
        self.st_tree.column("ID", width=50, anchor="center", stretch=tk.NO)
        self.st_tree.column("Nome", width=300, stretch=tk.YES)
        self.st_tree.column("Visibile", width=100, anchor="center", stretch=tk.NO)
        self.st_tree.pack(expand=True, fill="both", padx=5, pady=5)
        bf_container = ttk.Frame(self.stabilimenti_frame)
        bf_container.pack(fill="x", pady=10)
        bf = ttk.Frame(bf_container)
        bf.pack()
        ttk.Button(bf, text="Aggiungi", command=self.add_stabilimento_window).pack(
            side="left", padx=5
        )
        ttk.Button(bf, text="Modifica", command=self.edit_stabilimento_window).pack(
            side="left", padx=5
        )

    def refresh_stabilimenti_tree(self):
        for i in self.st_tree.get_children():
            self.st_tree.delete(i)
        for r_dict in db_retriever.get_all_stabilimenti():
            self.st_tree.insert(
                "",
                "end",
                values=(
                    r_dict["id"],
                    r_dict["name"],
                    "Sì" if r_dict["visible"] else "No",
                ),
            )

    def add_stabilimento_window(self):
        self.stabilimento_editor_window()

    def edit_stabilimento_window(self):
        sel_iid = self.st_tree.focus()
        if not sel_iid:
            messagebox.showwarning("Attenzione", "Seleziona uno stabilimento.")
            return
        item_vals = self.st_tree.item(sel_iid)["values"]
        if not item_vals or len(item_vals) < 3:
            messagebox.showerror("Errore", "Dati stabilimento non validi.")
            return
        try:
            self.stabilimento_editor_window(
                data_tuple=(int(item_vals[0]), item_vals[1], item_vals[2])
            )
        except (TypeError, ValueError):
            messagebox.showerror("Errore", "ID stabilimento non valido.")
            return

    def stabilimento_editor_window(self, data_tuple=None):
        win = tk.Toplevel(self)
        win.title("Editor Stabilimento" if data_tuple else "Nuovo Stabilimento")
        win.transient(self)
        win.grab_set()
        win.geometry("400x180")
        s_id, s_name, s_vis_str = (
            (data_tuple[0], data_tuple[1], data_tuple[2])
            if data_tuple
            else (None, "", "Sì")
        )
        form_frame = ttk.Frame(win, padding=15)
        form_frame.pack(expand=True, fill="both")
        ttk.Label(form_frame, text="Nome Stabilimento:").grid(
            row=0, column=0, sticky="w", padx=5, pady=5
        )
        name_var = tk.StringVar(value=s_name)
        name_entry = ttk.Entry(form_frame, textvariable=name_var, width=35)
        name_entry.grid(row=0, column=1, padx=5, pady=5)
        name_entry.focus_set()
        visible_var = tk.BooleanVar(value=(s_vis_str == "Sì"))
        ttk.Checkbutton(
            form_frame, text="Visibile per Inserimento Target", variable=visible_var
        ).grid(row=1, column=1, sticky="w", padx=5, pady=10)
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=2, columnspan=2, pady=15)

        def save_action():
            nome_val = name_var.get().strip()
            if not nome_val:
                messagebox.showerror("Errore", "Nome obbligatorio.", parent=win)
                return
            try:
                if s_id is not None:
                    db_manager.update_stabilimento(s_id, nome_val, visible_var.get())
                else:
                    db_manager.add_stabilimento(nome_val, visible_var.get())
                self.refresh_all_relevant_data()
                win.destroy()
            except sqlite3.IntegrityError:
                messagebox.showerror(
                    "Errore", f"Stabilimento '{nome_val}' esiste già.", parent=win
                )
            except Exception as e_save:
                messagebox.showerror(
                    "Errore", f"Salvataggio fallito: {e_save}", parent=win
                )

        ttk.Button(
            btn_frame, text="Salva", command=save_action, style="Accent.TButton"
        ).pack(side="left", padx=10)
        ttk.Button(btn_frame, text="Annulla", command=win.destroy).pack(
            side="left", padx=10
        )

    # --- Scheda Inserimento Target ---
    # ... (code for this tab remains unchanged, as the logic for _distribute_master_target_to_subs_ui and save_all_targets_entry already handles weights by querying the DB) ...
    def create_target_widgets(self):
        filter_frame_outer = ttk.Frame(self.target_frame)
        filter_frame_outer.pack(fill="x", pady=5)
        filter_frame = ttk.Frame(filter_frame_outer)
        filter_frame.pack()
        ttk.Label(filter_frame, text="Anno:").pack(side="left", padx=(0, 2))
        self.year_var_target = tk.StringVar(value=str(datetime.datetime.now().year))
        self.year_spin_target = ttk.Spinbox(
            filter_frame,
            from_=2020,
            to=2050,
            textvariable=self.year_var_target,
            width=6,
            command=self.load_kpi_targets_for_entry_target,
        )
        self.year_spin_target.pack(side="left", padx=(0, 5))
        ttk.Label(filter_frame, text="Stabilimento:").pack(side="left", padx=(5, 2))
        self.stabilimento_var_target = tk.StringVar()
        self.stabilimento_cb_target = ttk.Combobox(
            filter_frame,
            textvariable=self.stabilimento_var_target,
            state="readonly",
            width=23,
        )
        self.stabilimento_cb_target.pack(side="left", padx=(0, 5))
        self.stabilimento_cb_target.bind(
            "<<ComboboxSelected>>", self.load_kpi_targets_for_entry_target
        )
        ttk.Button(
            filter_frame,
            text="Carica/Aggiorna KPI",
            command=self.load_kpi_targets_for_entry_target,
        ).pack(side="left", padx=5)
        canvas_frame_target = ttk.Frame(self.target_frame)
        canvas_frame_target.pack(fill="both", expand=True, pady=(5, 0))
        self.canvas_target = tk.Canvas(canvas_frame_target, highlightthickness=0)
        scrollbar_target = ttk.Scrollbar(
            canvas_frame_target, orient="vertical", command=self.canvas_target.yview
        )
        self.scrollable_frame_target = ttk.Frame(self.canvas_target)
        self.scrollable_frame_target.bind(
            "<Configure>",
            lambda e: self.canvas_target.configure(
                scrollregion=self.canvas_target.bbox("all")
            ),
        )
        self.canvas_target_window = self.canvas_target.create_window(
            (0, 0), window=self.scrollable_frame_target, anchor="nw"
        )
        self.canvas_target.configure(yscrollcommand=scrollbar_target.set)
        self.canvas_target.pack(side="left", fill="both", expand=True)
        scrollbar_target.pack(side="right", fill="y")
        self.canvas_target.bind_all("<MouseWheel>", self._on_mousewheel_target)
        self.canvas_target.bind("<Enter>", lambda e: self.canvas_target.focus_set())
        save_button_frame = ttk.Frame(self.target_frame)
        save_button_frame.pack(fill="x", pady=10)
        ttk.Button(
            save_button_frame,
            text="SALVA TUTTI I TARGET",
            command=self.save_all_targets_entry,
            style="Accent.TButton",
        ).pack()
        self.kpi_target_entry_widgets = {}

    def _on_mousewheel_target(self, event):
        active_tab_text = ""
        try:
            active_tab_text = self.notebook.tab(self.notebook.select(), "text")
        except tk.TclError:
            return
        if active_tab_text == "🎯 Inserimento Target":
            canvas_x = self.canvas_target.winfo_rootx()
            canvas_y = self.canvas_target.winfo_rooty()
            canvas_w = self.canvas_target.winfo_width()
            canvas_h = self.canvas_target.winfo_height()
            if (
                canvas_x <= event.x_root < canvas_x + canvas_w
                and canvas_y <= event.y_root < canvas_y + canvas_h
            ):
                delta = (
                    -1 * (event.delta // (120 if sys.platform.startswith("win") else 1))
                    if sys.platform.startswith(("win", "darwin"))
                    else (-1 if event.num == 4 else (1 if event.num == 5 else 0))
                )
                self.canvas_target.yview_scroll(delta, "units")

    def populate_target_comboboxes(self):
        stabilimenti_vis = db_retriever.get_all_stabilimenti(only_visible=True)
        self.stabilimenti_map_target = {s["name"]: s["id"] for s in stabilimenti_vis}
        current_stabilimento_name = self.stabilimento_var_target.get()
        self.stabilimento_cb_target["values"] = list(
            self.stabilimenti_map_target.keys()
        )
        if (
            current_stabilimento_name
            and current_stabilimento_name in self.stabilimenti_map_target
        ):
            self.stabilimento_var_target.set(current_stabilimento_name)
        elif self.stabilimenti_map_target:
            self.stabilimento_var_target.set(
                list(self.stabilimenti_map_target.keys())[0]
            )
        else:
            self.stabilimento_var_target.set("")
        self.load_kpi_targets_for_entry_target()

    def _update_repartition_input_area_tk(
        self,
        container_frame,
        profile_var,
        logic_var,
        repartition_vars_dict,
        default_repartition_map_from_db,
    ):
        for widget in container_frame.winfo_children():
            widget.destroy()
        repartition_vars_dict.clear()
        selected_profile = profile_var.get()
        selected_logic_from_var = logic_var.get()
        show_logic_radios = True
        effective_logic_for_db = selected_logic_from_var
        if selected_profile in [
            db_manager.PROFILE_ANNUAL_PROGRESSIVE,
            db_manager.PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS,
            db_manager.PROFILE_TRUE_ANNUAL_SINUSOIDAL,
            db_manager.PROFILE_EVEN,
            "event_based_spikes_or_dips",
        ]:
            show_logic_radios = False
            effective_logic_for_db = db_manager.REPARTITION_LOGIC_ANNO
            logic_var.set(db_manager.REPARTITION_LOGIC_ANNO)
        elif selected_profile in [
            db_manager.PROFILE_QUARTERLY_PROGRESSIVE,
            db_manager.PROFILE_QUARTERLY_SINUSOIDAL,
        ]:
            if selected_logic_from_var not in [
                db_manager.REPARTITION_LOGIC_MESE,
                db_manager.REPARTITION_LOGIC_TRIMESTRE,
                db_manager.REPARTITION_LOGIC_SETTIMANA,
            ]:
                logic_var.set(db_manager.REPARTITION_LOGIC_TRIMESTRE)
            effective_logic_for_db = logic_var.get()
        elif selected_profile in [
            db_manager.PROFILE_MONTHLY_SINUSOIDAL,
            db_manager.PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE,
        ]:
            if selected_logic_from_var not in [
                db_manager.REPARTITION_LOGIC_MESE,
                db_manager.REPARTITION_LOGIC_TRIMESTRE,
                db_manager.REPARTITION_LOGIC_SETTIMANA,
            ]:
                logic_var.set(db_manager.REPARTITION_LOGIC_MESE)
            effective_logic_for_db = logic_var.get()
        else:
            effective_logic_for_db = selected_logic_from_var
            if not effective_logic_for_db:
                logic_var.set(db_manager.REPARTITION_LOGIC_ANNO)
                effective_logic_for_db = db_manager.REPARTITION_LOGIC_ANNO
        if show_logic_radios:
            logic_selection_frame = ttk.Frame(container_frame)
            logic_selection_frame.pack(fill="x", pady=(5, 2))
            ttk.Label(logic_selection_frame, text="Logica Rip. Valori:", width=18).pack(
                side="left", padx=(0, 5)
            )
            radio_cmd = lambda pv=profile_var, lv=logic_var, rvars=repartition_vars_dict, cf=container_frame, dmap=default_repartition_map_from_db: self._update_repartition_input_area_tk(
                cf, pv, lv, rvars, dmap
            )
            for logic_option in self.repartition_logic_options_tk:
                ttk.Radiobutton(
                    logic_selection_frame,
                    text=logic_option,
                    variable=logic_var,
                    value=logic_option,
                    command=radio_cmd,
                ).pack(side="left", padx=2)
        input_details_frame = ttk.Frame(container_frame)
        input_details_frame.pack(fill="x", expand=True, pady=(5, 0))
        if (
            effective_logic_for_db == db_manager.REPARTITION_LOGIC_MESE
            and show_logic_radios
        ):
            periods = [calendar.month_name[i] for i in range(1, 13)]
            num_cols = 4
            default_val = 100.0 / len(periods)
            for i, period_name in enumerate(periods):
                row, col = divmod(i, num_cols)
                pf = ttk.Frame(input_details_frame)
                pf.grid(row=row, column=col, padx=2, pady=1, sticky="ew")
                input_details_frame.columnconfigure(col, weight=1)
                ttk.Label(pf, text=f"{period_name[:3]}:", width=5).pack(side="left")
                val_from_db = default_repartition_map_from_db.get(
                    period_name, default_val
                )
                var = tk.DoubleVar(value=round(float(val_from_db), 2))
                repartition_vars_dict[period_name] = var
                ttk.Entry(pf, textvariable=var, width=6).pack(
                    side="left", fill="x", expand=True
                )
        elif (
            effective_logic_for_db == db_manager.REPARTITION_LOGIC_TRIMESTRE
            and show_logic_radios
        ):
            periods = ["Q1", "Q2", "Q3", "Q4"]
            num_cols = 4
            default_val = 100.0 / len(periods)
            for i, period_name in enumerate(periods):
                row, col = divmod(i, num_cols)
                pf = ttk.Frame(input_details_frame)
                pf.grid(row=row, column=col, padx=2, pady=1, sticky="ew")
                input_details_frame.columnconfigure(col, weight=1)
                ttk.Label(pf, text=f"{period_name}:", width=5).pack(side="left")
                val_from_db = default_repartition_map_from_db.get(
                    period_name, default_val
                )
                var = tk.DoubleVar(value=round(float(val_from_db), 2))
                repartition_vars_dict[period_name] = var
                ttk.Entry(pf, textvariable=var, width=6).pack(
                    side="left", fill="x", expand=True
                )
        elif (
            effective_logic_for_db == db_manager.REPARTITION_LOGIC_SETTIMANA
            and show_logic_radios
        ):
            ttk.Label(input_details_frame, text="Valori Settimanali (JSON):").pack(
                side="top", anchor="w", pady=(0, 2)
            )
            json_text_widget = tk.Text(
                input_details_frame, height=3, width=50, relief=tk.SOLID, borderwidth=1
            )
            json_text_widget.pack(side="top", fill="x", expand=True, pady=(0, 2))
            json_str_from_db = default_repartition_map_from_db.get(
                "weekly_json", json.dumps({"Info": 'Es: {"2024-W01": 2.5}'}, indent=2)
            )
            if (
                isinstance(default_repartition_map_from_db, dict)
                and "weekly_json" not in default_repartition_map_from_db
                and any(
                    k.count("-W") > 0 for k in default_repartition_map_from_db.keys()
                )
            ):
                json_str_from_db = json.dumps(default_repartition_map_from_db, indent=2)
            try:
                pretty_json_str = json.dumps(json.loads(json_str_from_db), indent=2)
                json_text_widget.insert("1.0", pretty_json_str)
            except json.JSONDecodeError:
                json_text_widget.insert("1.0", json_str_from_db)
            repartition_vars_dict["weekly_json_text_widget"] = json_text_widget
            ttk.Label(
                input_details_frame,
                text='Formato: {"ANNO-Wnum": valore_percentuale, ...}',
                font=("Calibri", 8, "italic"),
            ).pack(side="top", anchor="w")
        if selected_profile == "event_based_spikes_or_dips":
            ttk.Label(input_details_frame, text="Parametri Eventi (JSON):").pack(
                side="top", anchor="w", pady=(5, 2)
            )
            event_json_widget = tk.Text(
                input_details_frame, height=4, width=50, relief=tk.SOLID, borderwidth=1
            )
            event_json_widget.pack(side="top", fill="x", expand=True, pady=(0, 2))
            event_json_from_db = default_repartition_map_from_db.get(
                "event_json",
                json.dumps(
                    [
                        {
                            "start_date": "YYYY-MM-DD",
                            "end_date": "YYYY-MM-DD",
                            "multiplier": 1.0,
                            "addition": 0.0,
                            "comment": "Esempio",
                        }
                    ],
                    indent=2,
                ),
            )
            try:
                pretty_event_json = json.dumps(json.loads(event_json_from_db), indent=2)
                event_json_widget.insert("1.0", pretty_event_json)
            except json.JSONDecodeError:
                event_json_widget.insert("1.0", event_json_from_db)
            repartition_vars_dict["event_json_text_widget"] = event_json_widget
            ttk.Label(
                input_details_frame,
                text="Lista: [{start_date, end_date, multiplier, addition}]",
                font=("Calibri", 8, "italic"),
            ).pack(side="top", anchor="w")

    def load_kpi_targets_for_entry_target(self, event=None):
        if self._populating_target_kpi_entries:
            return
        self._populating_target_kpi_entries = True
        for widget in self.scrollable_frame_target.winfo_children():
            widget.destroy()
        self.kpi_target_entry_widgets.clear()
        self.canvas_target.yview_moveto(0)
        if not self.stabilimento_var_target.get() or not self.year_var_target.get():
            ttk.Label(
                self.scrollable_frame_target, text="Seleziona anno e stabilimento."
            ).pack(pady=10)
            self._populating_target_kpi_entries = False
            return
        try:
            year = int(self.year_var_target.get())
            stabilimento_id = self.stabilimenti_map_target.get(
                self.stabilimento_var_target.get()
            )
            if stabilimento_id is None:
                ttk.Label(
                    self.scrollable_frame_target, text="Stabilimento non valido."
                ).pack(pady=10)
                self._populating_target_kpi_entries = False
                return
        except ValueError:
            ttk.Label(self.scrollable_frame_target, text="Anno non valido.").pack(
                pady=10
            )
            self._populating_target_kpi_entries = False
            return
        kpis_for_entry = db_retriever.get_all_kpis_detailed(only_visible=True)
        if not kpis_for_entry:
            ttk.Label(
                self.scrollable_frame_target, text="Nessun KPI visibile definito."
            ).pack(pady=10)
            self._populating_target_kpi_entries = False
            return
        for kpi_data_dict in kpis_for_entry:
            kpi_spec_id = kpi_data_dict["id"]
            if kpi_spec_id is None:
                continue
            frame_label = f"{get_kpi_display_name(kpi_data_dict)} (ID Spec: {kpi_spec_id}, Unità: {kpi_data_dict['unit_of_measure'] or 'N/D'}, Tipo: {kpi_data_dict['calculation_type']})"
            kpi_entry_frame = ttk.LabelFrame(
                self.scrollable_frame_target, text=frame_label, padding=10
            )
            kpi_entry_frame.pack(fill="x", expand=True, padx=5, pady=(0, 7))
            existing_target_db_row = db_retriever.get_annual_target_entry(
                year, stabilimento_id, kpi_spec_id
            )
            def_t1, def_t2 = 0.0, 0.0
            def_profile = db_manager.PROFILE_ANNUAL_PROGRESSIVE
            def_logic = db_manager.REPARTITION_LOGIC_ANNO
            def_repart_map_for_ui = {}
            def_is_manual1, def_is_manual2 = (
                True,
                True,
            )
            if existing_target_db_row:
                def_t1 = float(existing_target_db_row["annual_target1"] or 0.0)
                def_t2 = float(existing_target_db_row["annual_target2"] or 0.0)
                db_profile_val = existing_target_db_row["distribution_profile"]
                if (
                    db_profile_val
                    and db_profile_val in self.distribution_profile_options_tk
                ):
                    def_profile = db_profile_val
                def_logic = (
                    existing_target_db_row["repartition_logic"]
                    or db_manager.REPARTITION_LOGIC_ANNO
                )
                def_is_manual1 = bool(existing_target_db_row["is_target1_manual"])
                def_is_manual2 = bool(existing_target_db_row["is_target2_manual"])
                try:
                    def_repart_map_for_ui = json.loads(
                        existing_target_db_row["repartition_values"] or "{}"
                    )
                except json.JSONDecodeError:
                    print(
                        f"WARN: JSON repartition_values non valido per KPI {kpi_spec_id}"
                    )
                profile_params_json_str = None
                if "profile_params" in existing_target_db_row.keys():
                    profile_params_json_str = existing_target_db_row["profile_params"]
                if profile_params_json_str:
                    try:
                        loaded_profile_params = json.loads(profile_params_json_str)
                        if (
                            isinstance(loaded_profile_params, dict)
                            and "events" in loaded_profile_params
                        ):
                            def_repart_map_for_ui["event_json"] = json.dumps(
                                loaded_profile_params["events"], indent=2
                            )
                    except json.JSONDecodeError:
                        print(
                            f"WARN: JSON profile_params non valido per KPI {kpi_spec_id}"
                        )
            kpi_role = db_retriever.get_kpi_role_details(kpi_spec_id)
            is_sub_kpi = kpi_role["role"] == "sub"
            target1_var = tk.DoubleVar(value=def_t1)
            target2_var = tk.DoubleVar(value=def_t2)
            profile_var = tk.StringVar(value=def_profile)
            logic_var = tk.StringVar(value=def_logic)
            repart_input_vars = {}
            current_kpi_widgets = {
                "target1_var": target1_var,
                "target2_var": target2_var,
                "profile_var": profile_var,
                "logic_var": logic_var,
                "repartition_vars": repart_input_vars,
                "calc_type": kpi_data_dict["calculation_type"],
                "kpi_display_name": get_kpi_display_name(kpi_data_dict),
                "is_sub_kpi": is_sub_kpi,
                "master_kpi_id": kpi_role.get("master_id") if is_sub_kpi else None,
                "entry_frame": kpi_entry_frame,
            }
            self.kpi_target_entry_widgets[kpi_spec_id] = current_kpi_widgets
            top_row = ttk.Frame(kpi_entry_frame)
            top_row.pack(fill="x", pady=(0, 5))
            ttk.Label(top_row, text="Target 1:").pack(side="left")
            target1_entry = ttk.Entry(top_row, textvariable=target1_var, width=10)
            target1_entry.pack(side="left", padx=(2, 1))
            current_kpi_widgets["target1_entry"] = target1_entry
            force_manual1_var = tk.BooleanVar(value=def_is_manual1)
            force_manual1_cb = ttk.Checkbutton(
                top_row,
                text="Man.",
                variable=force_manual1_var,
                command=lambda k_id=kpi_spec_id, t_num=1: self._on_force_manual_toggle(
                    k_id, t_num
                ),
            )
            if is_sub_kpi:
                force_manual1_cb.pack(side="left", padx=(0, 6))
            current_kpi_widgets["force_manual1_var"] = force_manual1_var
            ttk.Label(top_row, text="Target 2:").pack(side="left")
            target2_entry = ttk.Entry(top_row, textvariable=target2_var, width=10)
            target2_entry.pack(side="left", padx=(2, 1))
            current_kpi_widgets["target2_entry"] = target2_entry
            force_manual2_var = tk.BooleanVar(value=def_is_manual2)
            force_manual2_cb = ttk.Checkbutton(
                top_row,
                text="Man.",
                variable=force_manual2_var,
                command=lambda k_id=kpi_spec_id, t_num=2: self._on_force_manual_toggle(
                    k_id, t_num
                ),
            )
            if is_sub_kpi:
                force_manual2_cb.pack(side="left", padx=(0, 10))
            current_kpi_widgets["force_manual2_var"] = force_manual2_var
            ttk.Label(top_row, text="Profilo Distrib.:", width=14).pack(side="left")
            profile_cb = ttk.Combobox(
                top_row,
                textvariable=profile_var,
                values=self.distribution_profile_options_tk,
                state="readonly",
                width=26,
            )
            profile_cb.pack(side="left", padx=(2, 0), fill="x", expand=True)
            repart_controls_container = ttk.Frame(kpi_entry_frame)
            repart_controls_container.pack(fill="x", pady=(2, 0))
            cmd_profile_chg = lambda ev, pv=profile_var, lv=logic_var, rvars=repart_input_vars, cframe=repart_controls_container, dmap=def_repart_map_for_ui: self._update_repartition_input_area_tk(
                cframe, pv, lv, rvars, dmap
            )
            profile_cb.bind("<<ComboboxSelected>>", cmd_profile_chg)
            self._update_repartition_input_area_tk(
                repart_controls_container,
                profile_var,
                logic_var,
                repart_input_vars,
                def_repart_map_for_ui,
            )
            if kpi_role["role"] == "master":
                target1_var.trace_add(
                    "write",
                    lambda *args, k_id=kpi_spec_id, tn=1: self._on_master_target_change(
                        k_id, tn
                    ),
                )
                target2_var.trace_add(
                    "write",
                    lambda *args, k_id=kpi_spec_id, tn=2: self._on_master_target_change(
                        k_id, tn
                    ),
                )
            if is_sub_kpi:
                self._update_sub_kpi_target_field_state(kpi_spec_id, 1)
                self._update_sub_kpi_target_field_state(kpi_spec_id, 2)
        self.after(100, self._initial_master_sub_ui_distribution)
        self._populating_target_kpi_entries = False
        self.scrollable_frame_target.update_idletasks()
        self.canvas_target.config(scrollregion=self.canvas_target.bbox("all"))

    def _initial_master_sub_ui_distribution(self):
        if self._master_sub_update_active:
            return
        self._master_sub_update_active = True
        print("Esecuzione _initial_master_sub_ui_distribution...")
        for kpi_spec_id_master, widgets_master in self.kpi_target_entry_widgets.items():
            if widgets_master.get("master_kpi_id") is None and not widgets_master.get(
                "is_sub_kpi"
            ):
                role_check = db_retriever.get_kpi_role_details(kpi_spec_id_master)
                if role_check["role"] == "master":
                    print(
                        f"  Inizializzazione distribuzione per Master KPI: {kpi_spec_id_master}"
                    )
                    self._distribute_master_target_to_subs_ui(kpi_spec_id_master, 1)
                    self._distribute_master_target_to_subs_ui(kpi_spec_id_master, 2)
        self._master_sub_update_active = False

    def _on_force_manual_toggle(self, sub_kpi_id, target_number):
        if self._master_sub_update_active or self._populating_target_kpi_entries:
            return
        self._master_sub_update_active = True
        self._update_sub_kpi_target_field_state(sub_kpi_id, target_number)
        sub_kpi_widgets = self.kpi_target_entry_widgets.get(sub_kpi_id)
        if sub_kpi_widgets and sub_kpi_widgets["master_kpi_id"]:
            master_id = sub_kpi_widgets["master_kpi_id"]
            self._distribute_master_target_to_subs_ui(master_id, target_number)
        self._master_sub_update_active = False

    def _on_master_target_change(self, master_kpi_id, target_number_changed):
        if self._master_sub_update_active or self._populating_target_kpi_entries:
            return
        self._master_sub_update_active = True
        self._distribute_master_target_to_subs_ui(master_kpi_id, target_number_changed)
        self._master_sub_update_active = False

    def _update_sub_kpi_target_field_state(self, sub_kpi_id, target_number):
        widgets = self.kpi_target_entry_widgets.get(sub_kpi_id)
        if not widgets or not widgets.get("is_sub_kpi"):
            return
        manual_var = widgets.get(f"force_manual{target_number}_var")
        target_entry_widget = widgets.get(f"target{target_number}_entry")
        entry_frame_widget = widgets.get("entry_frame")
        if not all([manual_var, target_entry_widget, entry_frame_widget]):
            print(
                f"WARN: Missing widget references for sub_kpi_id {sub_kpi_id}, target {target_number} in _update_sub_kpi_target_field_state."
            )
            return
        if manual_var.get():
            target_entry_widget.config(state="normal")
            try:
                entry_frame_widget.configure(relief="sunken", borderwidth=2)
                if (
                    hasattr(entry_frame_widget, "labelwidget")
                    and entry_frame_widget.labelwidget
                ):
                    entry_frame_widget.labelwidget.configure(
                        style="ManualState.TLabelframe.Label"
                    )
                else:
                    entry_frame_widget.configure(
                        labelstyle="ManualState.TLabelframe.Label"
                    )
            except tk.TclError as e:
                print(
                    f"Error applying direct 'manual' properties/styles to frame for KPI {sub_kpi_id}: {e}"
                )
        else:
            target_entry_widget.config(state="disabled")
            try:
                entry_frame_widget.configure(
                    relief=self.style_defaults.get("TLabelFrame_relief", "flat"),
                    borderwidth=self.style_defaults.get("TLabelFrame_borderwidth", 1),
                )
                if (
                    hasattr(entry_frame_widget, "labelwidget")
                    and entry_frame_widget.labelwidget
                ):
                    entry_frame_widget.labelwidget.configure(
                        style="DerivedState.TLabelframe.Label"
                    )
                else:
                    entry_frame_widget.configure(
                        labelstyle="DerivedState.TLabelframe.Label"
                    )
            except tk.TclError as e:
                print(
                    f"Error applying direct 'derived' properties/styles to frame for KPI {sub_kpi_id}: {e}"
                )

    def _distribute_master_target_to_subs_ui(
        self, master_kpi_id, target_num_to_distribute
    ):
        if self._populating_target_kpi_entries:
            return
        master_widgets = self.kpi_target_entry_widgets.get(master_kpi_id)
        if not master_widgets:
            print(f"WARN: Master widgets non trovati per {master_kpi_id}")
            return

        linked_sub_details_with_weights = []
        raw_sub_ids = db_retriever.get_sub_kpis_for_master(master_kpi_id)
        if raw_sub_ids:
            with sqlite3.connect(DB_KPIS) as conn_ui_weights:
                conn_ui_weights.row_factory = sqlite3.Row
                for sub_id_raw in raw_sub_ids:
                    link_row = conn_ui_weights.execute(
                        "SELECT sub_kpi_spec_id, distribution_weight FROM kpi_master_sub_links WHERE master_kpi_spec_id = ? AND sub_kpi_spec_id = ?",
                        (master_kpi_id, sub_id_raw),
                    ).fetchone()
                    if link_row:
                        linked_sub_details_with_weights.append(
                            {
                                "sub_kpi_spec_id": link_row["sub_kpi_spec_id"],
                                "weight": link_row["distribution_weight"],
                            }
                        )

        if not linked_sub_details_with_weights:
            return

        print(
            f"Distribuendo (UI) Target {target_num_to_distribute} da Master {master_kpi_id} a subs: {linked_sub_details_with_weights}"
        )

        try:
            master_target_val_var = master_widgets.get(
                f"target{target_num_to_distribute}_var"
            )
            if master_target_val_var is None:
                print(
                    f"WARN: Master target var non trovata per {master_kpi_id}, target {target_num_to_distribute}"
                )
                return
            master_target_val = master_target_val_var.get()
        except tk.TclError:
            master_target_val = 0.0

        sum_manual_sub_targets = 0.0
        non_manual_sub_kpis_info_in_ui = []
        total_weight_for_distribution_ui = 0.0

        for sub_detail in linked_sub_details_with_weights:
            sub_id = sub_detail["sub_kpi_spec_id"]
            sub_weight = sub_detail["weight"]
            if not isinstance(sub_weight, (int, float)) or sub_weight <= 0:
                sub_weight = 1.0

            sub_widgets = self.kpi_target_entry_widgets.get(sub_id)
            if sub_widgets and sub_widgets["is_sub_kpi"]:
                manual_var_sub = sub_widgets.get(
                    f"force_manual{target_num_to_distribute}_var"
                )
                target_var_sub = sub_widgets.get(
                    f"target{target_num_to_distribute}_var"
                )
                if manual_var_sub and target_var_sub:
                    if manual_var_sub.get():
                        try:
                            sum_manual_sub_targets += target_var_sub.get()
                        except tk.TclError:
                            pass
                    else:
                        non_manual_sub_kpis_info_in_ui.append(
                            {"id": sub_id, "weight": sub_weight}
                        )
                        total_weight_for_distribution_ui += sub_weight

        remaining_master_target = master_target_val - sum_manual_sub_targets

        if non_manual_sub_kpis_info_in_ui:
            for sub_info_update in non_manual_sub_kpis_info_in_ui:
                sub_id_to_update = sub_info_update["id"]
                current_sub_weight = sub_info_update["weight"]
                target_per_sub = 0.0
                if total_weight_for_distribution_ui > 1e-9:
                    target_per_sub = (
                        current_sub_weight / total_weight_for_distribution_ui
                    ) * remaining_master_target
                elif (
                    remaining_master_target != 0
                    and len(non_manual_sub_kpis_info_in_ui) > 0
                ):
                    target_per_sub = remaining_master_target / len(
                        non_manual_sub_kpis_info_in_ui
                    )

                sub_widgets_to_update = self.kpi_target_entry_widgets.get(
                    sub_id_to_update
                )
                if sub_widgets_to_update:
                    target_var_to_set = sub_widgets_to_update.get(
                        f"target{target_num_to_distribute}_var"
                    )
                    if target_var_to_set:
                        target_var_to_set.set(round(target_per_sub, 2))
                    self._update_sub_kpi_target_field_state(
                        sub_id_to_update, target_num_to_distribute
                    )
        print(
            f"  Fine distribuzione UI per Master {master_kpi_id}, Target {target_num_to_distribute}. Rimanente: {remaining_master_target}"
        )

    def save_all_targets_entry(self):
        try:
            year = int(self.year_var_target.get())
            stabilimento_id = self.stabilimenti_map_target.get(
                self.stabilimento_var_target.get()
            )
        except (ValueError, KeyError, TypeError):
            messagebox.showerror("Errore", "Anno o stabilimento non validi.")
            return
        if stabilimento_id is None:
            messagebox.showerror("Errore", "Stabilimento non selezionato.")
            return
        targets_to_save_db = {}
        all_inputs_valid = True
        initiator_kpi_id_for_save = None
        for kpi_id, kpi_widgets in self.kpi_target_entry_widgets.items():
            try:
                t1_val = kpi_widgets["target1_var"].get()
                t2_val = kpi_widgets["target2_var"].get()
            except tk.TclError:
                messagebox.showerror(
                    "Errore",
                    f"KPI '{kpi_widgets['kpi_display_name']}': Target non numerico.",
                )
                all_inputs_valid = False
                break
            profile_ui = kpi_widgets["profile_var"].get()
            logic_ui = kpi_widgets["logic_var"].get()
            repart_values_for_db = {}
            profile_params_for_db = {}
            effective_logic_db = logic_ui
            if profile_ui in [
                db_manager.PROFILE_ANNUAL_PROGRESSIVE,
                db_manager.PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS,
                db_manager.PROFILE_TRUE_ANNUAL_SINUSOIDAL,
                db_manager.PROFILE_EVEN,
                "event_based_spikes_or_dips",
            ]:
                effective_logic_db = db_manager.REPARTITION_LOGIC_ANNO
            if effective_logic_db in [
                db_manager.REPARTITION_LOGIC_MESE,
                db_manager.REPARTITION_LOGIC_TRIMESTRE,
            ]:
                sum_percent = 0.0
                num_periods = 0
                for period_key, tk_var in kpi_widgets["repartition_vars"].items():
                    if isinstance(tk_var, tk.DoubleVar):
                        try:
                            val = tk_var.get()
                            repart_values_for_db[period_key] = val
                            sum_percent += val
                            num_periods += 1
                        except tk.TclError:
                            messagebox.showerror(
                                "Errore",
                                f"KPI '{kpi_widgets['kpi_display_name']}': Valore non numerico per '{period_key}'.",
                            )
                            all_inputs_valid = False
                            break
                if not all_inputs_valid:
                    break
                if (
                    kpi_widgets["calc_type"] == db_manager.CALC_TYPE_INCREMENTALE
                    and num_periods > 0
                    and (abs(t1_val) > 1e-9 or abs(t2_val) > 1e-9)
                    and not (99.9 <= sum_percent <= 100.1)
                ):
                    messagebox.showerror(
                        "Errore",
                        f"KPI '{kpi_widgets['kpi_display_name']}' ({db_manager.CALC_TYPE_INCREMENTALE}): Somma ripartizioni {effective_logic_db} è {sum_percent:.2f}%. Deve essere 100%.",
                    )
                    all_inputs_valid = False
                    break
            elif effective_logic_db == db_manager.REPARTITION_LOGIC_SETTIMANA:
                json_text_widget = kpi_widgets["repartition_vars"].get(
                    "weekly_json_text_widget"
                )
                if json_text_widget:
                    json_str = json_text_widget.get("1.0", tk.END).strip()
                    if json_str:
                        try:
                            repart_values_for_db = json.loads(json_str)
                        except json.JSONDecodeError:
                            messagebox.showerror(
                                "Errore",
                                f"KPI '{kpi_widgets['kpi_display_name']}': JSON settimanale non valido.",
                            )
                            all_inputs_valid = False
                            break
            if profile_ui == "event_based_spikes_or_dips":
                event_text_widget = kpi_widgets["repartition_vars"].get(
                    "event_json_text_widget"
                )
                if event_text_widget:
                    event_json_str = event_text_widget.get("1.0", tk.END).strip()
                    if event_json_str:
                        try:
                            profile_params_for_db["events"] = json.loads(event_json_str)
                        except json.JSONDecodeError:
                            messagebox.showerror(
                                "Errore",
                                f"KPI '{kpi_widgets['kpi_display_name']}': JSON eventi non valido.",
                            )
                            all_inputs_valid = False
                            break
            is_manual1, is_manual2 = (
                True,
                True,
            )
            if kpi_widgets["is_sub_kpi"]:
                if "force_manual1_var" in kpi_widgets:
                    is_manual1 = kpi_widgets["force_manual1_var"].get()
                if "force_manual2_var" in kpi_widgets:
                    is_manual2 = kpi_widgets["force_manual2_var"].get()
            targets_to_save_db[kpi_id] = {
                "annual_target1": t1_val,
                "annual_target2": t2_val,
                "repartition_logic": effective_logic_db,
                "repartition_values": repart_values_for_db,
                "distribution_profile": profile_ui,
                "profile_params": profile_params_for_db,
                "is_target1_manual": is_manual1,
                "is_target2_manual": is_manual2,
            }
        if not all_inputs_valid:
            return
        if not targets_to_save_db:
            messagebox.showwarning("Attenzione", "Nessun target valido da salvare.")
            return
        try:
            db_manager.save_annual_targets(
                year,
                stabilimento_id,
                targets_to_save_db,
                initiator_kpi_spec_id=initiator_kpi_id_for_save,
            )
            messagebox.showinfo("Successo", "Target salvati e CSV rigenerati!")
            self.load_kpi_targets_for_entry_target()
        except Exception as e:
            messagebox.showerror(
                "Errore Salvataggio",
                f"Salvataggio fallito: {e}\n{traceback.format_exc()}",
            )

    # --- Scheda Visualizzazione Risultati ---
    # ... (code for this tab remains unchanged) ...
    def create_results_widgets(self):
        filter_frame_outer_res = ttk.Frame(self.results_frame)
        filter_frame_outer_res.pack(fill="x", pady=5)
        filter_frame_res = ttk.Frame(filter_frame_outer_res)
        filter_frame_res.pack()
        row1_filters = ttk.Frame(filter_frame_res)
        row1_filters.pack(fill="x", pady=2)
        ttk.Label(row1_filters, text="Anno:").pack(side="left")
        self.res_year_var_vis = tk.StringVar(value=str(datetime.datetime.now().year))
        ttk.Spinbox(
            row1_filters,
            from_=2020,
            to=2050,
            textvariable=self.res_year_var_vis,
            width=6,
            command=self.show_results_data,
        ).pack(side="left", padx=(2, 10))
        ttk.Label(row1_filters, text="Stabilimento:").pack(side="left")
        self.res_stabilimento_var_vis = tk.StringVar()
        self.res_stabilimento_cb_vis = ttk.Combobox(
            row1_filters,
            textvariable=self.res_stabilimento_var_vis,
            state="readonly",
            width=20,
        )
        self.res_stabilimento_cb_vis.pack(side="left", padx=(2, 10))
        self.res_stabilimento_cb_vis.bind(
            "<<ComboboxSelected>>", self.show_results_data
        )
        ttk.Label(row1_filters, text="Periodo:").pack(side="left")
        self.res_period_var_vis = tk.StringVar(value="Mese")
        self.res_period_cb_vis = ttk.Combobox(
            row1_filters,
            textvariable=self.res_period_var_vis,
            state="readonly",
            values=["Giorno", "Settimana", "Mese", "Trimestre"],
            width=10,
        )
        self.res_period_cb_vis.current(2)
        self.res_period_cb_vis.pack(side="left", padx=(2, 10))
        self.res_period_cb_vis.bind("<<ComboboxSelected>>", self.show_results_data)
        row2_filters = ttk.Frame(filter_frame_res)
        row2_filters.pack(fill="x", pady=2)
        ttk.Label(row2_filters, text="Gruppo:").pack(side="left")
        self.res_group_var = tk.StringVar()
        self.res_group_cb = ttk.Combobox(
            row2_filters, textvariable=self.res_group_var, state="readonly", width=20
        )
        self.res_group_cb.pack(side="left", padx=(2, 5))
        self.res_group_cb.bind(
            "<<ComboboxSelected>>", self.on_res_group_selected_refresh_results
        )
        ttk.Label(row2_filters, text="Sottogruppo:").pack(side="left")
        self.res_subgroup_var = tk.StringVar()
        self.res_subgroup_cb = ttk.Combobox(
            row2_filters, textvariable=self.res_subgroup_var, state="readonly", width=25
        )
        self.res_subgroup_cb.pack(side="left", padx=(2, 5))
        self.res_subgroup_cb.bind(
            "<<ComboboxSelected>>", self.on_res_subgroup_selected_refresh_results
        )
        ttk.Label(row2_filters, text="Indicatore:").pack(side="left")
        self.res_indicator_var = tk.StringVar()
        self.res_indicator_cb = ttk.Combobox(
            row2_filters,
            textvariable=self.res_indicator_var,
            state="readonly",
            width=30,
        )
        self.res_indicator_cb.pack(side="left", padx=(2, 10))
        self.res_indicator_cb.bind("<<ComboboxSelected>>", self.show_results_data)
        ttk.Button(
            row2_filters,
            text="Aggiorna Vista",
            command=self.show_results_data,
            style="Accent.TButton",
        ).pack(side="left", padx=5)
        self.results_data_tree = ttk.Treeview(
            self.results_frame,
            columns=("Periodo", "Target 1", "Target 2"),
            show="headings",
        )
        self.results_data_tree.heading("Periodo", text="Periodo")
        self.results_data_tree.heading("Target 1", text="Valore Target 1")
        self.results_data_tree.heading("Target 2", text="Valore Target 2")
        self.results_data_tree.column("Periodo", width=250, anchor="w", stretch=tk.YES)
        self.results_data_tree.column("Target 1", width=150, anchor="e", stretch=tk.YES)
        self.results_data_tree.column("Target 2", width=150, anchor="e", stretch=tk.YES)
        self.results_data_tree.pack(fill="both", expand=True, pady=(10, 0))
        self.summary_label_var_vis = tk.StringVar()
        ttk.Label(
            self.results_frame,
            textvariable=self.summary_label_var_vis,
            font=("Calibri", 10, "italic"),
        ).pack(pady=5, anchor="e", padx=10)

    def on_res_group_selected_refresh_results(self, event=None):
        self._populate_res_subgroups()

    def on_res_subgroup_selected_refresh_results(self, event=None):
        self._populate_res_indicators()

    def populate_results_comboboxes(self):
        current_stab_name_res = self.res_stabilimento_var_vis.get()
        stabilimenti_all = db_retriever.get_all_stabilimenti()
        self.res_stabilimenti_map_vis = {s["name"]: s["id"] for s in stabilimenti_all}
        self.res_stabilimento_cb_vis["values"] = list(
            self.res_stabilimenti_map_vis.keys()
        )
        if (
            current_stab_name_res
            and current_stab_name_res in self.res_stabilimenti_map_vis
        ):
            self.res_stabilimento_var_vis.set(current_stab_name_res)
        elif self.res_stabilimenti_map_vis:
            self.res_stabilimento_var_vis.set(
                list(self.res_stabilimenti_map_vis.keys())[0]
            )
        else:
            self.res_stabilimento_var_vis.set("")
        current_group_name_res = self.res_group_var.get()
        current_subgroup_display_name_res = self.res_subgroup_var.get()
        current_indicator_name_res = self.res_indicator_var.get()
        self.res_groups_list = db_retriever.get_kpi_groups()
        self.res_group_cb["values"] = [g["name"] for g in self.res_groups_list]
        if (
            current_group_name_res
            and current_group_name_res in self.res_group_cb["values"]
        ):
            self.res_group_var.set(current_group_name_res)
            current_subgroup_raw_name_res = (
                self.res_subgroup_display_to_raw_map.get(
                    current_subgroup_display_name_res
                )
                if hasattr(self, "res_subgroup_display_to_raw_map")
                and current_subgroup_display_name_res
                else None
            )
            self._populate_res_subgroups(
                pre_selected_subgroup_raw_name=current_subgroup_raw_name_res,
                pre_selected_indicator_name=current_indicator_name_res,
            )
        else:
            self.res_group_var.set("")
            self.res_subgroup_var.set("")
            self.res_indicator_var.set("")
            self.res_subgroup_cb["values"] = []
            self.res_indicator_cb["values"] = []
            self.current_kpi_id_for_results = None
            self.show_results_data()

    def _populate_res_subgroups(
        self, pre_selected_subgroup_raw_name=None, pre_selected_indicator_name=None
    ):
        group_name = self.res_group_var.get()
        self.res_subgroup_cb["values"] = []
        self.res_indicator_cb["values"] = []
        if not pre_selected_subgroup_raw_name:
            self.res_subgroup_var.set("")
        if not pre_selected_indicator_name:
            self.res_indicator_var.set("")
        self.current_kpi_id_for_results = None
        selected_group_obj = next(
            (g for g in self.res_groups_list if g["name"] == group_name), None
        )
        if selected_group_obj:
            self.res_subgroups_list_details = (
                db_retriever.get_kpi_subgroups_by_group_revised(
                    selected_group_obj["id"]
                )
            )
            self.res_subgroup_display_to_raw_map = {}
            display_subgroup_names = []
            for sg_dict in self.res_subgroups_list_details:
                raw_name = sg_dict["name"]
                display_name = raw_name + (
                    f" (Tpl: {sg_dict['template_name']})"
                    if sg_dict.get("template_name")
                    else ""
                )
                display_subgroup_names.append(display_name)
                self.res_subgroup_display_to_raw_map[display_name] = raw_name
            self.res_subgroup_cb["values"] = display_subgroup_names
            target_display_subgroup_name = (
                next(
                    (
                        dn
                        for dn, rn in self.res_subgroup_display_to_raw_map.items()
                        if rn == pre_selected_subgroup_raw_name
                    ),
                    None,
                )
                if pre_selected_subgroup_raw_name
                else None
            )
            if target_display_subgroup_name:
                self.res_subgroup_var.set(target_display_subgroup_name)
                self._populate_res_indicators(pre_selected_indicator_name)
            else:
                self._populate_res_indicators()
        else:
            self._populate_res_indicators()

    def _populate_res_indicators(self, pre_selected_indicator_name=None):
        display_subgroup_name = self.res_subgroup_var.get()
        self.res_indicator_cb["values"] = []
        if not pre_selected_indicator_name:
            self.res_indicator_var.set("")
        self.current_kpi_id_for_results = None
        raw_subgroup_name_lookup = (
            self.res_subgroup_display_to_raw_map.get(display_subgroup_name)
            if hasattr(self, "res_subgroup_display_to_raw_map")
            else None
        )
        selected_subgroup_obj_from_list = (
            next(
                (
                    s
                    for s in self.res_subgroups_list_details
                    if s["name"] == raw_subgroup_name_lookup
                ),
                None,
            )
            if raw_subgroup_name_lookup and hasattr(self, "res_subgroups_list_details")
            else None
        )
        if selected_subgroup_obj_from_list:
            all_indicators_in_subgroup = db_retriever.get_kpi_indicators_by_subgroup(
                selected_subgroup_obj_from_list["id"]
            )
            all_kpi_specs_with_data = db_retriever.get_all_kpis_detailed()
            indicator_ids_with_spec = {
                k_spec["actual_indicator_id"] for k_spec in all_kpi_specs_with_data
            }
            self.res_indicators_list_filtered_details = [
                ind
                for ind in all_indicators_in_subgroup
                if ind["id"] in indicator_ids_with_spec
            ]
            self.res_indicator_cb["values"] = [
                ind["name"] for ind in self.res_indicators_list_filtered_details
            ]
            if (
                pre_selected_indicator_name
                and pre_selected_indicator_name in self.res_indicator_cb["values"]
            ):
                self.res_indicator_var.set(pre_selected_indicator_name)
        self.show_results_data()

    def show_results_data(self, event=None):
        for i in self.results_data_tree.get_children():
            self.results_data_tree.delete(i)
        self.summary_label_var_vis.set("")
        try:
            year_val_res_str = self.res_year_var_vis.get()
            if not year_val_res_str:
                self.summary_label_var_vis.set("Selezionare un anno.")
                return
            year_val_res = int(year_val_res_str)
            stabilimento_name_res = self.res_stabilimento_var_vis.get()
            indicator_name_res = self.res_indicator_var.get()
            period_type_res = self.res_period_var_vis.get()
            if not all([stabilimento_name_res, indicator_name_res, period_type_res]):
                self.summary_label_var_vis.set(
                    "Selezionare Anno, Stabilimento, Indicatore e Periodo."
                )
                return
            stabilimento_id_res = self.res_stabilimenti_map_vis.get(
                stabilimento_name_res
            )
            if stabilimento_id_res is None:
                self.summary_label_var_vis.set("Stabilimento selezionato non valido.")
                return
            selected_indicator_details_obj = (
                next(
                    (
                        ind
                        for ind in self.res_indicators_list_filtered_details
                        if ind["name"] == indicator_name_res
                    ),
                    None,
                )
                if hasattr(self, "res_indicators_list_filtered_details")
                and self.res_indicators_list_filtered_details
                else None
            )
            if not selected_indicator_details_obj:
                self.summary_label_var_vis.set(
                    f"Indicatore '{indicator_name_res}' non trovato o senza specifica KPI."
                )
                return
            indicator_actual_id = selected_indicator_details_obj["id"]
            kpi_spec_obj = next(
                (
                    spec
                    for spec in db_retriever.get_all_kpis_detailed()
                    if spec["actual_indicator_id"] == indicator_actual_id
                ),
                None,
            )
            if not kpi_spec_obj:
                self.summary_label_var_vis.set(
                    f"Specifica KPI non trovata per Indicatore ID {indicator_actual_id}."
                )
                return
            kpi_spec_id_res = kpi_spec_obj["id"]
            calc_type_res = kpi_spec_obj["calculation_type"]
            kpi_unit_res = kpi_spec_obj["unit_of_measure"] or ""
            kpi_display_name_res_str = get_kpi_display_name(kpi_spec_obj)
            target_ann_info_res = db_retriever.get_annual_target_entry(
                year_val_res, stabilimento_id_res, kpi_spec_id_res
            )
            profile_disp_res = "N/D"
            if target_ann_info_res:
                if "distribution_profile" in target_ann_info_res.keys():
                    profile_disp_res = (
                        target_ann_info_res["distribution_profile"] or "N/D"
                    )
            data_t1 = db_retriever.get_periodic_targets_for_kpi(
                year_val_res, stabilimento_id_res, kpi_spec_id_res, period_type_res, 1
            )
            data_t2 = db_retriever.get_periodic_targets_for_kpi(
                year_val_res, stabilimento_id_res, kpi_spec_id_res, period_type_res, 2
            )
            map_t1 = (
                {row["Periodo"]: row["Target"] for row in data_t1} if data_t1 else {}
            )
            map_t2 = (
                {row["Periodo"]: row["Target"] for row in data_t2} if data_t2 else {}
            )
            ordered_periods = (
                [row["Periodo"] for row in data_t1]
                if data_t1
                else ([row["Periodo"] for row in data_t2] if data_t2 else [])
            )
            display_rows_added = False
            total_sum_t1, count_t1 = 0.0, 0
            total_sum_t2, count_t2 = 0.0, 0
            for period_name in ordered_periods:
                val_t1 = map_t1.get(period_name)
                val_t2 = map_t2.get(period_name)
                t1_disp = f"{val_t1:.2f}" if isinstance(val_t1, (int, float)) else "N/A"
                t2_disp = f"{val_t2:.2f}" if isinstance(val_t2, (int, float)) else "N/A"
                self.results_data_tree.insert(
                    "", "end", values=(period_name, t1_disp, t2_disp)
                )
                display_rows_added = True
                if isinstance(val_t1, (int, float)):
                    total_sum_t1 += val_t1
                    count_t1 += 1
                if isinstance(val_t2, (int, float)):
                    total_sum_t2 += val_t2
                    count_t2 += 1
            if not display_rows_added:
                self.summary_label_var_vis.set(
                    f"Nessun dato ripartito per {kpi_display_name_res_str} (Profilo: {profile_disp_res})."
                )
                return
            summary_parts = [
                f"KPI: {kpi_display_name_res_str}",
                f"Profilo: {profile_disp_res}",
            ]
            if count_t1 > 0:
                agg_t1 = (
                    total_sum_t1
                    if calc_type_res == db_manager.CALC_TYPE_INCREMENTALE
                    else (total_sum_t1 / count_t1)
                )
                summary_parts.append(
                    f"{'Totale T1' if calc_type_res==db_manager.CALC_TYPE_INCREMENTALE else 'Media T1'} ({period_type_res}): {agg_t1:,.2f} {kpi_unit_res}"
                )
            if count_t2 > 0:
                agg_t2 = (
                    total_sum_t2
                    if calc_type_res == db_manager.CALC_TYPE_INCREMENTALE
                    else (total_sum_t2 / count_t2)
                )
                summary_parts.append(
                    f"{'Totale T2' if calc_type_res==db_manager.CALC_TYPE_INCREMENTALE else 'Media T2'} ({period_type_res}): {agg_t2:,.2f} {kpi_unit_res}"
                )
            self.summary_label_var_vis.set(" | ".join(summary_parts))
        except ValueError as ve:
            self.summary_label_var_vis.set(f"Errore Input: {ve}")
        except Exception as e:
            self.summary_label_var_vis.set(f"Errore: {e}")
            traceback.print_exc()

    # --- Scheda Esportazione Dati ---
    # ... (code for this tab remains unchanged) ...
    def create_export_widgets(self):
        export_main_frame = ttk.Frame(self.export_frame, padding=20)
        export_main_frame.pack(expand=True, fill="both")
        export_info_label_frame = ttk.Frame(export_main_frame)
        export_info_label_frame.pack(pady=10, anchor="center")
        resolved_path_str = (
            str(Path(db_manager.CSV_EXPORT_BASE_PATH).resolve())
            if hasattr(db_manager, "CSV_EXPORT_BASE_PATH")
            else "N/D"
        )
        ttk.Label(
            export_info_label_frame,
            text=(
                f"CSV globali generati/sovrascritti al salvataggio dei target.\nSalvati in:\n{resolved_path_str}"
            ),
            wraplength=700,
            justify="center",
            font=("Calibri", 11),
        ).pack()
        export_button_frame = ttk.Frame(export_main_frame)
        export_button_frame.pack(pady=30, anchor="center")
        ttk.Button(
            export_button_frame,
            text="Esporta CSV Globali in ZIP...",
            command=self.export_all_data_to_zip,
            style="Accent.TButton",
        ).pack()
        open_folder_button_frame = ttk.Frame(export_main_frame)
        open_folder_button_frame.pack(pady=10, anchor="center")
        ttk.Button(
            open_folder_button_frame,
            text="Apri Cartella Esportazioni CSV",
            command=self.open_export_folder,
        ).pack()

    def open_export_folder(self):
        try:
            export_path = Path(db_manager.CSV_EXPORT_BASE_PATH).resolve()
        except AttributeError:
            messagebox.showerror(
                "Errore Config.",
                "Percorso esportazioni CSV non configurato.",
                parent=self,
            )
            return
        if not export_path.exists():
            export_path.mkdir(parents=True, exist_ok=True)
            messagebox.showinfo(
                "Cartella Creata",
                f"Cartella esportazioni creata:\n{export_path}\nVuota. Salva target per popolarla.",
                parent=self,
            )
        if sys.platform == "win32":
            os.startfile(export_path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(export_path)])
        else:
            subprocess.Popen(["xdg-open", str(export_path)])

    def export_all_data_to_zip(self):
        try:
            export_base_path_str = db_manager.CSV_EXPORT_BASE_PATH
        except AttributeError:
            messagebox.showerror(
                "Errore Config.",
                "Percorso base esportazioni non definito.",
                parent=self,
            )
            return
        if not export_base_path_str:
            messagebox.showerror(
                "Errore Config.",
                "Percorso base esportazioni non definito.",
                parent=self,
            )
            return
        export_base_path = Path(export_base_path_str)
        expected_csv_files = getattr(export_manager, "GLOBAL_CSV_FILES", None)
        if not export_base_path.exists() or (
            expected_csv_files
            and not any(
                (export_base_path / fname).exists()
                for fname in expected_csv_files.values()
            )
        ):
            messagebox.showwarning(
                "Nessun Dato",
                f"Nessun CSV globale atteso in {export_base_path.resolve()}. Salva target.",
                parent=self,
            )
            return
        default_zip_name = f"kpi_global_data_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        zip_filepath = filedialog.asksaveasfilename(
            title="Salva archivio ZIP",
            initialfile=default_zip_name,
            defaultextension=".zip",
            filetypes=[("File ZIP", "*.zip"), ("Tutti i file", "*.*")],
            parent=self,
        )
        if not zip_filepath:
            return
        try:
            if not hasattr(export_manager, "package_all_csvs_as_zip"):
                messagebox.showerror(
                    "Errore Funzione",
                    "'package_all_csvs_as_zip' non in export_manager.",
                    parent=self,
                )
                return
            success, message = export_manager.package_all_csvs_as_zip(
                str(export_base_path), zip_filepath
            )
            if success:
                messagebox.showinfo("Esportazione Completata", message, parent=self)
            else:
                messagebox.showerror("Errore Esportazione", message, parent=self)
        except Exception as e:
            messagebox.showerror(
                "Errore Critico Esportazione",
                f"Errore imprevisto ZIP: {e}\n{traceback.format_exc()}",
                parent=self,
            )

    # --- Scheda Gestione Link Master/Sub (NEW) ---
    def create_master_sub_link_widgets(self):
        main_frame = ttk.Frame(self.master_sub_link_frame, padding=10)
        main_frame.pack(fill="both", expand=True)

        kpi_list_frame = ttk.LabelFrame(
            main_frame, text="Tutti i KPI (Specifiche Definite)", padding=10
        )
        kpi_list_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        cols = ("ID Spec", "Nome Completo KPI", "Ruolo Attuale")
        self.master_sub_kpi_tree = ttk.Treeview(
            kpi_list_frame, columns=cols, show="headings", height=20
        )
        self.master_sub_kpi_tree.heading("ID Spec", text="ID Spec")
        self.master_sub_kpi_tree.column(
            "ID Spec", width=60, anchor="center", stretch=tk.NO
        )
        self.master_sub_kpi_tree.heading("Nome Completo KPI", text="Nome Completo KPI")
        self.master_sub_kpi_tree.column("Nome Completo KPI", width=350, stretch=tk.YES)
        self.master_sub_kpi_tree.heading("Ruolo Attuale", text="Ruolo")
        self.master_sub_kpi_tree.column(
            "Ruolo Attuale",
            width=150,
            anchor="w",
            stretch=tk.NO,  # Increased width for weight display
        )
        self.master_sub_kpi_tree.pack(fill="both", expand=True, pady=(0, 5))
        self.master_sub_kpi_tree.bind(
            "<<TreeviewSelect>>", self.on_master_sub_kpi_select
        )

        details_actions_frame = ttk.Frame(main_frame, padding=10)
        details_actions_frame.pack(
            side="left", fill="both", expand=True, padx=5, pady=5
        )

        self.selected_kpi_label_var = tk.StringVar(value="KPI Selezionato: Nessuno")
        ttk.Label(
            details_actions_frame,
            textvariable=self.selected_kpi_label_var,
            font=("Calibri", 11, "bold"),
        ).pack(pady=10, anchor="w")

        manages_frame = ttk.LabelFrame(
            details_actions_frame,
            text="Gestisce come Master (Subordinati e Pesi):",
            padding=10,
        )
        manages_frame.pack(fill="x", pady=5)
        self.subs_of_master_listbox = tk.Listbox(
            manages_frame, height=6, width=60, exportselection=False
        )
        self.subs_of_master_listbox.pack(fill="x", expand=True, pady=(0, 5))
        manages_btn_frame = ttk.Frame(manages_frame)
        manages_btn_frame.pack(fill="x")
        self.link_sub_btn = ttk.Button(
            manages_btn_frame,
            text="Collega SubKPI",
            command=self.link_new_sub_kpi,
            state="disabled",
        )
        self.link_sub_btn.pack(side="left", padx=2)

        self.edit_link_weight_btn = ttk.Button(
            manages_btn_frame,
            text="Modifica Peso",
            command=self.edit_selected_link_weight,
            state="disabled",
        )
        self.edit_link_weight_btn.pack(side="left", padx=2)

        self.unlink_sub_btn = ttk.Button(
            manages_btn_frame,
            text="Scollega SubKPI",
            command=self.unlink_selected_sub_kpi,
            state="disabled",
        )
        self.unlink_sub_btn.pack(side="left", padx=2)

        # Bind the selection event to a dedicated handler
        self.subs_of_master_listbox.bind(
            "<<ListboxSelect>>", self.on_subs_of_master_listbox_select  # CHANGED
        )

        managed_by_frame = ttk.LabelFrame(
            details_actions_frame, text="Gestito da Master (con Peso):", padding=10
        )
        managed_by_frame.pack(fill="x", pady=5)
        self.master_of_sub_label_var = tk.StringVar(value="Nessun Master")
        ttk.Label(managed_by_frame, textvariable=self.master_of_sub_label_var).pack(
            anchor="w"
        )

        self.all_kpis_for_linking_map = {}
        self.current_sub_links_details = {}

    def on_subs_of_master_listbox_select(self, event=None):  # NEW METHOD
        is_sub_selected = bool(self.subs_of_master_listbox.curselection())
        self.unlink_sub_btn.config(state="normal" if is_sub_selected else "disabled")
        self.edit_link_weight_btn.config(
            state="normal" if is_sub_selected else "disabled"
        )

    def refresh_master_sub_displays(self, selected_kpi_spec_id_to_restore=None):
        for i in self.master_sub_kpi_tree.get_children():
            self.master_sub_kpi_tree.delete(i)
        self.all_kpis_for_linking_map.clear()

        all_kpis = db_retriever.get_all_kpis_detailed()
        item_to_select_iid = None
        for kpi_spec in all_kpis:
            display_name = get_kpi_display_name(kpi_spec)
            self.all_kpis_for_linking_map[kpi_spec["id"]] = display_name

            role_info = db_retriever.get_kpi_role_details(kpi_spec["id"])
            role_display = role_info["role"].capitalize()

            if role_info["role"] == "sub" and role_info["master_id"]:
                with sqlite3.connect(DB_KPIS) as conn:
                    link_weight_row = conn.execute(
                        "SELECT distribution_weight FROM kpi_master_sub_links WHERE master_kpi_spec_id = ? AND sub_kpi_spec_id = ?",
                        (role_info["master_id"], kpi_spec["id"]),
                    ).fetchone()
                    link_weight = (
                        link_weight_row[0]
                        if link_weight_row and link_weight_row[0] is not None
                        else 1.0
                    )
                master_name = self.all_kpis_for_linking_map.get(
                    role_info["master_id"], f"ID {role_info['master_id']}"
                )
                role_display += f" (di {master_name[:20]}.., Peso: {link_weight:.2f})"
            elif role_info["role"] == "master" and role_info["related_kpis"]:
                role_display += f" (gestisce {len(role_info['related_kpis'])})"

            iid = self.master_sub_kpi_tree.insert(
                "",
                "end",
                values=(kpi_spec["id"], display_name, role_display),
                iid=str(kpi_spec["id"]),
            )
            if (
                selected_kpi_spec_id_to_restore is not None
                and kpi_spec["id"] == selected_kpi_spec_id_to_restore
            ):
                item_to_select_iid = iid

        if item_to_select_iid:
            self.master_sub_kpi_tree.selection_set(item_to_select_iid)
            self.master_sub_kpi_tree.focus(item_to_select_iid)
            self.master_sub_kpi_tree.see(item_to_select_iid)

        self.on_master_sub_kpi_select()  # This will also update button states

    def on_master_sub_kpi_select(self, event=None):
        self.subs_of_master_listbox.delete(0, tk.END)
        self.current_sub_links_details.clear()
        self.master_of_sub_label_var.set("Nessun Master")
        self.link_sub_btn.config(state="disabled")
        self.unlink_sub_btn.config(state="disabled")  # Initially disabled
        self.edit_link_weight_btn.config(state="disabled")  # Initially disabled

        selected_items = self.master_sub_kpi_tree.selection()
        if not selected_items:
            self.selected_kpi_label_var.set("KPI Selezionato: Nessuno")
            return

        try:
            selected_kpi_spec_id = int(selected_items[0])
        except ValueError:
            self.selected_kpi_label_var.set("KPI Selezionato: ID non valido")
            return

        display_name = self.all_kpis_for_linking_map.get(selected_kpi_spec_id, "N/D")
        self.selected_kpi_label_var.set(
            f"KPI Selezionato: {display_name} (ID Spec: {selected_kpi_spec_id})"
        )
        self.link_sub_btn.config(state="normal")

        with sqlite3.connect(DB_KPIS) as conn:
            conn.row_factory = sqlite3.Row
            linked_subs_rows = conn.execute(
                "SELECT sub_kpi_spec_id, distribution_weight FROM kpi_master_sub_links WHERE master_kpi_spec_id = ?",
                (selected_kpi_spec_id,),
            ).fetchall()

        for sub_link_row in linked_subs_rows:
            sub_id = sub_link_row["sub_kpi_spec_id"]
            weight = sub_link_row["distribution_weight"]
            sub_display_name = self.all_kpis_for_linking_map.get(
                sub_id, f"Sub ID Spec: {sub_id}"
            )
            listbox_entry_text = (
                f"{sub_display_name} (ID: {sub_id}, Peso: {weight:.2f})"
            )
            self.subs_of_master_listbox.insert(tk.END, listbox_entry_text)
            self.current_sub_links_details[listbox_entry_text] = {
                "sub_id": sub_id,
                "weight": weight,
            }

        with sqlite3.connect(DB_KPIS) as conn:
            conn.row_factory = sqlite3.Row
            master_link_row = conn.execute(
                "SELECT master_kpi_spec_id, distribution_weight FROM kpi_master_sub_links WHERE sub_kpi_spec_id = ?",
                (selected_kpi_spec_id,),
            ).fetchone()

        if master_link_row:
            master_id = master_link_row["master_kpi_spec_id"]
            weight_as_sub = master_link_row["distribution_weight"]
            master_display_name = self.all_kpis_for_linking_map.get(
                master_id, f"Master ID Spec: {master_id}"
            )
            self.master_of_sub_label_var.set(
                f"{master_display_name} (ID: {master_id}, Mio Peso: {weight_as_sub:.2f})"
            )

        # After populating, check if any sub is selected to enable buttons
        self.on_subs_of_master_listbox_select()

    def link_new_sub_kpi(self):
        selected_master_items = self.master_sub_kpi_tree.selection()
        if not selected_master_items:
            messagebox.showwarning(
                "Attenzione", "Seleziona un KPI da designare come Master."
            )
            return
        master_kpi_spec_id = int(selected_master_items[0])

        available_kpis_for_sub = {
            id: name
            for id, name in self.all_kpis_for_linking_map.items()
            if id != master_kpi_spec_id
        }

        dialog = LinkSubKpiDialog(
            self, "Collega SubKPI", master_kpi_spec_id, available_kpis_for_sub
        )
        if dialog.result_sub_kpi_id and dialog.result_weight is not None:
            try:
                if db_retriever.get_sub_kpis_for_master(dialog.result_sub_kpi_id):
                    messagebox.showerror(
                        "Errore Logica",
                        "Un KPI che è già Master di altri non può diventare SubKPI.",
                        parent=self,
                    )
                    return
                existing_master_of_chosen_sub = db_retriever.get_master_kpi_for_sub(
                    dialog.result_sub_kpi_id
                )
                if (
                    existing_master_of_chosen_sub
                    and existing_master_of_chosen_sub != master_kpi_spec_id
                ):
                    messagebox.showerror(
                        "Errore Logica",
                        "Questo KPI è già SubKPI di un altro Master.",
                        parent=self,
                    )
                    return

                db_manager.add_master_sub_kpi_link(
                    master_kpi_spec_id, dialog.result_sub_kpi_id, dialog.result_weight
                )
                self.refresh_all_relevant_data()
                self.after(
                    100,
                    lambda: self.master_sub_kpi_tree.selection_set(
                        str(master_kpi_spec_id)
                    ),
                )
                self.after(
                    110, lambda: self.master_sub_kpi_tree.focus(str(master_kpi_spec_id))
                )
                self.after(
                    120, lambda: self.master_sub_kpi_tree.see(str(master_kpi_spec_id))
                )
                self.after(150, lambda: self.on_master_sub_kpi_select())

                self.populate_target_comboboxes()
            except sqlite3.IntegrityError:
                messagebox.showerror(
                    "Errore DB",
                    "Collegamento già esistente o ID non validi.",
                    parent=self,
                )
            except ValueError as ve:
                messagebox.showerror("Errore Logica/Input", str(ve), parent=self)
            except Exception as e:
                messagebox.showerror(
                    "Errore", f"Impossibile collegare: {e}", parent=self
                )

    def edit_selected_link_weight(self):
        selected_master_items = self.master_sub_kpi_tree.selection()
        selected_sub_item_indices = self.subs_of_master_listbox.curselection()

        if not selected_master_items or not selected_sub_item_indices:
            messagebox.showwarning(
                "Attenzione",
                "Seleziona un Master KPI e un SubKPI dalla lista per modificarne il peso.",
            )
            return

        master_kpi_spec_id = int(selected_master_items[0])
        sub_item_text = self.subs_of_master_listbox.get(selected_sub_item_indices[0])

        link_details = self.current_sub_links_details.get(sub_item_text)
        if not link_details:
            messagebox.showerror(
                "Errore Interno",
                "Impossibile recuperare i dettagli del link selezionato.",
            )
            return

        sub_kpi_spec_id = link_details["sub_id"]
        current_weight = link_details["weight"]

        new_weight_str = simpledialog.askstring(
            "Modifica Peso Distribuzione",
            f"Nuovo peso per SubKPI '{self.all_kpis_for_linking_map.get(sub_kpi_spec_id, sub_kpi_spec_id)}' (ID: {sub_kpi_spec_id})\n"
            f"collegato a Master '{self.all_kpis_for_linking_map.get(master_kpi_spec_id, master_kpi_spec_id)}' (ID: {master_kpi_spec_id}):",
            initialvalue=str(current_weight),
            parent=self,
        )

        if new_weight_str is not None:
            try:
                new_weight = float(new_weight_str)
                if new_weight <= 0:
                    messagebox.showerror(
                        "Errore Input",
                        "Il peso deve essere un numero positivo.",
                        parent=self,
                    )
                    return

                db_manager.update_master_sub_kpi_link_weight(
                    master_kpi_spec_id, sub_kpi_spec_id, new_weight
                )
                messagebox.showinfo(
                    "Successo",
                    f"Peso per SubKPI {sub_kpi_spec_id} aggiornato a {new_weight:.2f}.",
                )

                # 1. Refresh the master/sub link display first to show the new weight immediately on this tab
                self.refresh_master_sub_displays(
                    selected_kpi_spec_id_to_restore=master_kpi_spec_id
                )

                # Ensure the master KPI remains selected after refresh and the listbox is updated
                # The calls to selection_set, focus, see, and on_master_sub_kpi_select
                # ensure the UI for the link management tab is correctly updated.
                self.after(
                    50,
                    lambda: self.master_sub_kpi_tree.selection_set(
                        str(master_kpi_spec_id)
                    ),
                )
                self.after(
                    60, lambda: self.master_sub_kpi_tree.focus(str(master_kpi_spec_id))
                )
                self.after(
                    70, lambda: self.master_sub_kpi_tree.see(str(master_kpi_spec_id))
                )
                # Call on_master_sub_kpi_select to ensure the listbox of subs is correctly repopulated
                # and the newly modified sub-item (if still in the list) might be re-selected or its state updated.
                self.after(100, lambda: self.on_master_sub_kpi_select())

                # 2. Trigger a recalculation and save of targets for the current year/stab.
                # This will ensure that the database reflects the new weighted distribution
                # and the Target Entry tab UI is also updated.
                current_year_str = self.year_var_target.get()
                current_stab_name = self.stabilimento_var_target.get()

                if current_year_str and current_stab_name:
                    try:
                        year = int(current_year_str)
                        stab_id = self.stabilimenti_map_target.get(current_stab_name)
                        if stab_id is not None:
                            print(
                                f"Ricalcolo target per Master {master_kpi_spec_id} (e i suoi sub) dopo modifica peso."
                            )

                            # To make save_annual_targets aware of the trigger, we can pass the master_kpi_id
                            # It will then specifically re-evaluate this master.
                            # We need to gather all current UI data for targets_data_map.

                            targets_data_from_ui = {}
                            all_valid_for_save = True
                            for (
                                k_id,
                                k_widgets,
                            ) in self.kpi_target_entry_widgets.items():
                                try:
                                    t1 = k_widgets["target1_var"].get()
                                    t2 = k_widgets["target2_var"].get()
                                    is_m1 = (
                                        k_widgets.get("force_manual1_var").get()
                                        if k_widgets.get("force_manual1_var")
                                        else True
                                    )
                                    is_m2 = (
                                        k_widgets.get("force_manual2_var").get()
                                        if k_widgets.get("force_manual2_var")
                                        else True
                                    )

                                    # Gather repartition data as in save_all_targets_entry
                                    repart_vals_db = (
                                        {}
                                    )  # Simplified for this specific call, assume defaults for now
                                    profile_params_db = (
                                        {}
                                    )  # Simplified for this specific call

                                    targets_data_from_ui[str(k_id)] = {
                                        "annual_target1": t1,
                                        "annual_target2": t2,
                                        "is_target1_manual": is_m1,
                                        "is_target2_manual": is_m2,
                                        # Include other necessary fields if they can change dynamically,
                                        # otherwise save_annual_targets will fetch from DB or use defaults.
                                        "repartition_logic": k_widgets[
                                            "logic_var"
                                        ].get(),
                                        "distribution_profile": k_widgets[
                                            "profile_var"
                                        ].get(),
                                        "repartition_values": repart_vals_db,  # Placeholder
                                        "profile_params": profile_params_db,  # Placeholder
                                    }
                                except tk.TclError:
                                    # This KPI might not have valid numbers if user was editing.
                                    # For a targeted update, we might only need master's info.
                                    # However, save_annual_targets expects a comprehensive map.
                                    # For robustness, we could just reload, or be more selective.
                                    print(
                                        f"WARN: Valore non numerico per KPI {k_id} durante raccolta per ricalcolo peso."
                                    )
                                    all_valid_for_save = (
                                        False  # Or decide to skip this KPI
                                    )
                                    break

                            if all_valid_for_save and targets_data_from_ui:
                                db_manager.save_annual_targets(
                                    year,
                                    stab_id,
                                    targets_data_from_ui,  # Pass all current UI data
                                    initiator_kpi_spec_id=master_kpi_spec_id,  # Crucial: tell save_annual_targets which master caused this
                                )
                                # save_annual_targets will call calculate_and_save_all_repartitions
                                # and then the UI refresh for target tab is usually triggered by loading data.
                                # We need to explicitly reload the target entry tab
                                self.load_kpi_targets_for_entry_target()
                            elif not targets_data_from_ui:
                                print(
                                    "WARN: Nessun dato target dalla UI per ricalcolo dopo modifica peso."
                                )
                            else:  # Some data was invalid
                                messagebox.showwarning(
                                    "Attenzione",
                                    "Alcuni valori target non sono validi. Ricalcolo pesato potrebbe non essere completo nella UI.",
                                )
                                self.load_kpi_targets_for_entry_target()  # Still refresh UI

                        else:
                            print(
                                "WARN: Stabilimento non valido per ricalcolo target dopo modifica peso."
                            )
                            self.load_kpi_targets_for_entry_target()  # Refresh UI anyway
                    except ValueError:
                        print(
                            "WARN: Anno non valido per ricalcolo target dopo modifica peso."
                        )
                        self.load_kpi_targets_for_entry_target()  # Refresh UI anyway
                else:
                    print(
                        "WARN: Anno o Stabilimento non selezionati nella scheda Target. Impossibile ricalcolare automaticamente i target derivati."
                    )
                    # Even if targets are not recalculated, refresh the link display
                    # self.refresh_master_sub_displays(selected_kpi_spec_id_to_restore=master_kpi_spec_id)
                    # self.after(150, lambda: self.on_master_sub_kpi_select())

            except ValueError:
                messagebox.showerror(
                    "Errore Input",
                    "Il peso deve essere un valore numerico.",
                    parent=self,
                )
            except Exception as e:
                messagebox.showerror(
                    "Errore Aggiornamento Peso",
                    f"Impossibile aggiornare il peso: {e}\n{traceback.format_exc()}",
                    parent=self,
                )

    def unlink_selected_sub_kpi(self):
        selected_master_items = self.master_sub_kpi_tree.selection()
        selected_sub_item_indices = self.subs_of_master_listbox.curselection()
        if not selected_master_items or not selected_sub_item_indices:
            messagebox.showwarning(
                "Attenzione",
                "Seleziona un Master KPI e un SubKPI da scollegare dalla lista.",
            )
            return

        master_kpi_spec_id = int(selected_master_items[0])
        sub_item_text = self.subs_of_master_listbox.get(selected_sub_item_indices[0])

        link_details = self.current_sub_links_details.get(sub_item_text)
        if not link_details:
            messagebox.showerror(
                "Errore Interno",
                "Impossibile recuperare i dettagli del link selezionato per lo scollegamento.",
            )
            return
        sub_kpi_spec_id = link_details["sub_id"]

        if messagebox.askyesno(
            "Conferma Scollegamento",
            f"Scollegare SubKPI ID Spec {sub_kpi_spec_id} da Master ID Spec {master_kpi_spec_id}?",
            parent=self,
        ):
            try:
                db_manager.remove_master_sub_kpi_link(
                    master_kpi_spec_id, sub_kpi_spec_id
                )

                year_str = self.year_var_target.get()
                stab_name = self.stabilimento_var_target.get()
                year = None
                stabilimento_id_for_targets = None

                if year_str:
                    try:
                        year = int(year_str)
                    except ValueError:
                        pass

                if stab_name and hasattr(self, "stabilimenti_map_target"):
                    stabilimento_id_for_targets = self.stabilimenti_map_target.get(
                        stab_name
                    )

                if year is not None and stabilimento_id_for_targets is not None:
                    target_entry = db_retriever.get_annual_target_entry(
                        year,
                        stabilimento_id_for_targets,
                        sub_kpi_spec_id,
                    )
                    if target_entry:  # target_entry is an sqlite3.Row object
                        # --- START FIX for AttributeError ---
                        profile_params_val = "{}"  # Default to empty JSON string
                        if (
                            "profile_params" in target_entry.keys()
                            and target_entry["profile_params"] is not None
                        ):
                            profile_params_val = target_entry["profile_params"]
                        # --- END FIX for AttributeError ---

                        updated_data_for_sub = {
                            str(sub_kpi_spec_id): {
                                "annual_target1": target_entry["annual_target1"],
                                "annual_target2": target_entry["annual_target2"],
                                "repartition_logic": target_entry["repartition_logic"],
                                "repartition_values": json.loads(
                                    target_entry["repartition_values"] or "{}"
                                ),
                                "distribution_profile": target_entry[
                                    "distribution_profile"
                                ],
                                "profile_params": json.loads(
                                    profile_params_val
                                ),  # Use the safe variable
                                "is_target1_manual": True,
                                "is_target2_manual": True,
                            }
                        }
                        db_manager.save_annual_targets(
                            year,
                            stabilimento_id_for_targets,
                            updated_data_for_sub,
                            initiator_kpi_spec_id=sub_kpi_spec_id,
                        )
                else:
                    print(
                        f"WARN: Anno o stabilimento non validi nella UI Target, skip aggiornamento manuale per SubKPI {sub_kpi_spec_id} dopo scollegamento."
                    )

                self.refresh_all_relevant_data()
                self.after(
                    100,
                    lambda: self.master_sub_kpi_tree.selection_set(
                        str(master_kpi_spec_id)
                    ),
                )
                self.after(
                    110, lambda: self.master_sub_kpi_tree.focus(str(master_kpi_spec_id))
                )
                self.after(
                    120, lambda: self.master_sub_kpi_tree.see(str(master_kpi_spec_id))
                )
                self.after(150, lambda: self.on_master_sub_kpi_select())

                self.populate_target_comboboxes()
            except Exception as e:
                messagebox.showerror(
                    "Errore",
                    f"Impossibile scollegare: {e}\n{traceback.format_exc()}",
                    parent=self,
                )


# --- Dialog Classes ---
# ... (SubgroupEditorDialog and TemplateDefinitionEditorDialog remain unchanged) ...
class SubgroupEditorDialog(simpledialog.Dialog):
    def __init__(
        self,
        parent,
        title=None,
        group_id_context=None,
        initial_name="",
        initial_template_id=None,
    ):
        self.group_id = group_id_context
        self.initial_name = initial_name
        self.initial_template_id = initial_template_id
        self.result_name = None
        self.result_template_id = False
        self.templates_map = {"(Nessun Template)": None}
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text="Nome Sottogruppo:").grid(
            row=0, column=0, sticky="w", padx=5, pady=5
        )
        self.name_var = tk.StringVar(value=self.initial_name)
        self.name_entry = ttk.Entry(master, textvariable=self.name_var, width=35)
        self.name_entry.grid(row=0, column=1, padx=5, pady=5)
        self.name_entry.focus_set()
        ttk.Label(master, text="Template Indicatori:").grid(
            row=1, column=0, sticky="w", padx=5, pady=5
        )
        self.template_var = tk.StringVar()
        self.template_cb = ttk.Combobox(
            master, textvariable=self.template_var, state="readonly", width=33
        )
        available_templates = db_retriever.get_kpi_indicator_templates()
        for tpl in available_templates:
            self.templates_map[tpl["name"]] = tpl["id"]
        self.template_cb["values"] = list(self.templates_map.keys())
        selected_template_name = (
            next(
                (
                    name
                    for name, id_val in self.templates_map.items()
                    if id_val == self.initial_template_id
                ),
                "(Nessun Template)",
            )
            if self.initial_template_id is not None
            else "(Nessun Template)"
        )
        self.template_var.set(selected_template_name)
        self.template_cb.grid(row=1, column=1, padx=5, pady=5)
        return self.name_entry

    def apply(self):
        self.result_name = self.name_var.get().strip()
        selected_template_display_name = self.template_var.get()
        self.result_template_id = self.templates_map.get(selected_template_display_name)
        if not self.result_name:
            messagebox.showwarning(
                "Input Mancante", "Nome sottogruppo obbligatorio.", parent=self
            )
            self.result_name = None
            self.result_template_id = False


class TemplateDefinitionEditorDialog(simpledialog.Dialog):
    def __init__(self, parent, title=None, template_id_context=None, initial_data=None):
        self.initial_data = initial_data if initial_data else {}
        self.result_data = None
        self.kpi_calc_type_options = [
            db_manager.CALC_TYPE_INCREMENTALE,
            db_manager.CALC_TYPE_MEDIA,
        ]
        super().__init__(parent, title)

    def body(self, master):
        self.name_var = tk.StringVar(
            value=self.initial_data.get("indicator_name_in_template", "")
        )
        self.desc_var = tk.StringVar(
            value=self.initial_data.get("default_description", "")
        )
        self.type_var = tk.StringVar(
            value=self.initial_data.get(
                "default_calculation_type", self.kpi_calc_type_options[0]
            )
        )
        self.unit_var = tk.StringVar(
            value=self.initial_data.get("default_unit_of_measure", "")
        )
        self.visible_var = tk.BooleanVar(
            value=bool(self.initial_data.get("default_visible", True))
        )
        ttk.Label(master, text="Nome Indicatore Template:").grid(
            row=0, column=0, sticky="w", padx=5, pady=3
        )
        self.name_entry = ttk.Entry(master, textvariable=self.name_var, width=35)
        self.name_entry.grid(row=0, column=1, padx=5, pady=3)
        self.name_entry.focus_set()
        ttk.Label(master, text="Descrizione Default:").grid(
            row=1, column=0, sticky="w", padx=5, pady=3
        )
        ttk.Entry(master, textvariable=self.desc_var, width=35).grid(
            row=1, column=1, padx=5, pady=3
        )
        ttk.Label(master, text="Tipo Calcolo Default:").grid(
            row=2, column=0, sticky="w", padx=5, pady=3
        )
        ttk.Combobox(
            master,
            textvariable=self.type_var,
            values=self.kpi_calc_type_options,
            state="readonly",
            width=33,
        ).grid(row=2, column=1, padx=5, pady=3)
        ttk.Label(master, text="Unità Misura Default:").grid(
            row=3, column=0, sticky="w", padx=5, pady=3
        )
        ttk.Entry(master, textvariable=self.unit_var, width=35).grid(
            row=3, column=1, padx=5, pady=3
        )
        ttk.Checkbutton(
            master, text="Visibile Default", variable=self.visible_var
        ).grid(row=4, column=1, sticky="w", padx=5, pady=8)
        return self.name_entry

    def apply(self):
        name = self.name_var.get().strip()
        desc = self.desc_var.get().strip()
        calc_type = self.type_var.get()
        unit = self.unit_var.get().strip()
        visible = self.visible_var.get()
        if not name:
            messagebox.showwarning(
                "Input Mancante",
                "Nome indicatore nel template obbligatorio.",
                parent=self,
            )
            return
        self.result_data = {
            "name": name,
            "desc": desc,
            "calc_type": calc_type,
            "unit": unit,
            "visible": visible,
        }


class LinkSubKpiDialog(simpledialog.Dialog):
    def __init__(self, parent, title, master_kpi_id, available_kpis_map):
        self.master_kpi_id = master_kpi_id
        self.available_kpis_map = available_kpis_map
        self.result_sub_kpi_id = None
        self.result_weight = None
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(
            master,
            text=f"Collega SubKPI a Master ID Spec: {self.master_kpi_id}",
        ).grid(row=0, columnspan=2, pady=5)

        ttk.Label(master, text="Seleziona SubKPI:").grid(
            row=1, column=0, sticky="w", padx=5, pady=2
        )
        self.sub_kpi_var = tk.StringVar()
        self.sub_kpi_cb = ttk.Combobox(
            master, textvariable=self.sub_kpi_var, state="readonly", width=50
        )
        linkable_kpis = []
        self.display_to_id_map = {}
        for k_id, name in self.available_kpis_map.items():
            role_info = db_retriever.get_kpi_role_details(k_id)
            if (
                role_info["role"] == "none"
                or (
                    role_info["role"] == "sub"
                    and role_info["master_id"] == self.master_kpi_id
                )
                or (role_info["role"] == "sub" and role_info["master_id"] is None)
            ):
                if not (
                    role_info["role"] == "none"
                    and db_retriever.get_sub_kpis_for_master(k_id)
                ):
                    display_text = f"{name} (ID Spec: {k_id})"
                    linkable_kpis.append(display_text)
                    self.display_to_id_map[display_text] = k_id
        self.sub_kpi_cb["values"] = sorted(linkable_kpis)
        if linkable_kpis:
            self.sub_kpi_var.set(linkable_kpis[0])
        self.sub_kpi_cb.grid(row=1, column=1, padx=5, pady=2, sticky="ew")

        ttk.Label(master, text="Peso Distribuzione:").grid(
            row=2, column=0, sticky="w", padx=5, pady=2
        )
        self.weight_var = tk.DoubleVar(value=1.0)
        self.weight_entry = ttk.Entry(master, textvariable=self.weight_var, width=10)
        self.weight_entry.grid(row=2, column=1, padx=5, pady=2, sticky="w")

        return self.sub_kpi_cb

    def apply(self):
        selected_display_text = self.sub_kpi_var.get()
        if selected_display_text:
            self.result_sub_kpi_id = self.display_to_id_map.get(selected_display_text)

        if not self.result_sub_kpi_id:
            messagebox.showwarning(
                "Selezione Mancante", "Nessun SubKPI valido selezionato.", parent=self
            )
            self.result_weight = None
            return

        try:
            weight_val = self.weight_var.get()
            if weight_val <= 0:
                messagebox.showwarning(
                    "Input Non Valido", "Il peso deve essere positivo.", parent=self
                )
                self.result_sub_kpi_id = None
                self.result_weight = None
                return
            self.result_weight = weight_val
        except tk.TclError:
            messagebox.showwarning(
                "Input Non Valido", "Il peso deve essere un numero.", parent=self
            )
            self.result_sub_kpi_id = None
            self.result_weight = None
            return


if __name__ == "__main__":
    try:
        db_manager.setup_databases()
        app = KpiApp()
        app.mainloop()
    except Exception as e:
        error_log_path = Path("app_startup_error.log")
        with open(error_log_path, "a") as f:
            f.write(f"{datetime.datetime.now()}: {traceback.format_exc()}\n")
        try:
            root_err = tk.Tk()
            root_err.withdraw()
            messagebox.showerror(
                "Errore Critico Avvio",
                f"Impossibile avviare l'applicazione:\n{e}\n\nConsultare {error_log_path.resolve()}.",
            )
            root_err.destroy()
        except tk.TclError:
            print(
                f"ERRORE CRITICO DI AVVIO (TKinter non disponibile):\n{traceback.format_exc()}\nConsultare {error_log_path.resolve()} per dettagli."
            )
        sys.exit(1)
