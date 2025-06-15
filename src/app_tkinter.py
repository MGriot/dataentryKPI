# app_tkinter.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import database_manager as db
import export_manager
import json
import datetime
import calendar
from pathlib import Path
import sqlite3
import os
import sys
import subprocess


# --- Helper Function ---
def get_kpi_display_name(kpi_data):
    """
    Generates a display name for a KPI using its hierarchy.
    Example: "Group > Subgroup > Indicator"
    Handles cases where names might be None or empty from the database.
    """
    if not kpi_data:
        return "N/D (KPI Data Mancante)"
    # sqlite3.Row allows access by column name like a dictionary
    # Default to 'N/G', 'N/S', 'N/I' if the actual name is None or an empty string.
    try:
        g_name = kpi_data["group_name"] if kpi_data["group_name"] else "N/G"
        sg_name = kpi_data["subgroup_name"] if kpi_data["subgroup_name"] else "N/S"
        i_name = kpi_data["indicator_name"] if kpi_data["indicator_name"] else "N/I"
        return f"{g_name} > {sg_name} > {i_name}"
    except KeyError as e:
        # This means the SQL query in db.get_kpis() didn't return the expected column.
        # This should ideally not happen if the SQL is correct.
        print(
            f"KeyError in get_kpi_display_name: La colonna '{e}' è mancante nei dati KPI."
        )
        return "N/D (Struttura Dati KPI Incompleta)"
    except Exception as ex:
        # Catch any other unexpected error during name construction.
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
        self.kpi_spec_frame = ttk.Frame(self.notebook, padding="10")
        self.stabilimenti_frame = ttk.Frame(self.notebook, padding="10")
        self.results_frame = ttk.Frame(self.notebook, padding="10")
        self.export_frame = ttk.Frame(self.notebook, padding="10")

        self.notebook.add(self.target_frame, text="🎯 Inserimento Target")
        self.notebook.add(self.kpi_hierarchy_frame, text="🗂️ Gestione Gerarchia KPI")
        self.notebook.add(self.kpi_spec_frame, text="⚙️ Gestione Specifiche KPI")
        self.notebook.add(self.stabilimenti_frame, text="🏭 Gestione Stabilimenti")
        self.notebook.add(self.results_frame, text="📈 Visualizzazione Risultati")
        self.notebook.add(self.export_frame, text="📦 Esportazione Dati")

        self.distribution_profile_options_tk = [
            "annual_progressive",
            "monthly_sinusoidal",
            "legacy_intra_period_progressive",
        ]

        self.create_target_widgets()
        self.create_kpi_hierarchy_widgets()
        self.create_kpi_spec_widgets()
        self.create_stabilimenti_widgets()
        self.create_results_widgets()
        self.create_export_widgets()

        self.refresh_all_relevant_data()

    def refresh_all_relevant_data(self):
        self.refresh_kpi_hierarchy_displays()
        self.refresh_kpi_specs_tree()
        self.refresh_stabilimenti_tree()
        self.populate_target_comboboxes()
        self.populate_results_comboboxes()

    # --- Scheda Gestione Gerarchia KPI ---
    def create_kpi_hierarchy_widgets(self):
        main_frame = ttk.Frame(self.kpi_hierarchy_frame)
        main_frame.pack(fill="both", expand=True)

        group_frame = ttk.LabelFrame(main_frame, text="Gruppi KPI", padding=10)
        group_frame.pack(side="left", fill="both", expand=True, padx=5)

        self.groups_listbox = tk.Listbox(group_frame, exportselection=False, height=15)
        self.groups_listbox.pack(fill="both", expand=True)
        self.groups_listbox.bind("<<ListboxSelect>>", self.on_group_select)

        group_btn_frame = ttk.Frame(group_frame)
        group_btn_frame.pack(fill="x", pady=5)
        ttk.Button(
            group_btn_frame, text="Nuovo Gruppo", command=self.add_new_group
        ).pack(side="left")

        subgroup_frame = ttk.LabelFrame(
            main_frame, text="Sottogruppi (del gruppo selezionato)", padding=10
        )
        subgroup_frame.pack(side="left", fill="both", expand=True, padx=5)

        self.subgroups_listbox = tk.Listbox(
            subgroup_frame, exportselection=False, height=15
        )
        self.subgroups_listbox.pack(fill="both", expand=True)
        self.subgroups_listbox.bind("<<ListboxSelect>>", self.on_subgroup_select)

        subgroup_btn_frame = ttk.Frame(subgroup_frame)
        subgroup_btn_frame.pack(fill="x", pady=5)
        self.add_subgroup_btn = ttk.Button(
            subgroup_btn_frame,
            text="Nuovo Sottogruppo",
            command=self.add_new_subgroup,
            state="disabled",
        )
        self.add_subgroup_btn.pack(side="left")

        indicator_frame = ttk.LabelFrame(
            main_frame, text="Indicatori (del sottogruppo selezionato)", padding=10
        )
        indicator_frame.pack(side="left", fill="both", expand=True, padx=5)

        self.indicators_listbox = tk.Listbox(
            indicator_frame, exportselection=False, height=15
        )
        self.indicators_listbox.pack(fill="both", expand=True)

        indicator_btn_frame = ttk.Frame(indicator_frame)
        indicator_btn_frame.pack(fill="x", pady=5)
        self.add_indicator_btn = ttk.Button(
            indicator_btn_frame,
            text="Nuovo Indicatore",
            command=self.add_new_indicator,
            state="disabled",
        )
        self.add_indicator_btn.pack(side="left")

    def refresh_kpi_hierarchy_displays(self):
        selected_group_name = None
        if self.groups_listbox.curselection():
            selected_group_name = self.groups_listbox.get(
                self.groups_listbox.curselection()[0]
            )

        selected_subgroup_name = None
        if self.subgroups_listbox.curselection():
            selected_subgroup_name = self.subgroups_listbox.get(
                self.subgroups_listbox.curselection()[0]
            )

        self.groups_listbox.delete(0, tk.END)
        self.current_groups_map = {}
        groups_data = db.get_kpi_groups()
        for i, group in enumerate(groups_data):
            self.groups_listbox.insert(tk.END, group["name"])
            self.current_groups_map[group["name"]] = group["id"]
            if group["name"] == selected_group_name:
                self.groups_listbox.selection_set(i)
                self.groups_listbox.activate(i)
                self.groups_listbox.see(i)

        self.subgroups_listbox.delete(0, tk.END)
        self.indicators_listbox.delete(0, tk.END)
        self.add_subgroup_btn.config(state="disabled")
        self.add_indicator_btn.config(state="disabled")

        if selected_group_name:
            self.on_group_select(
                event=None, pre_selected_subgroup_name=selected_subgroup_name
            )
        else:
            self.add_subgroup_btn.config(state="disabled")
            self.add_indicator_btn.config(state="disabled")

    def on_group_select(self, event=None, pre_selected_subgroup_name=None):
        selection = self.groups_listbox.curselection()
        if not selection:
            self.subgroups_listbox.delete(0, tk.END)
            self.indicators_listbox.delete(0, tk.END)
            self.add_subgroup_btn.config(state="disabled")
            self.add_indicator_btn.config(state="disabled")
            self.current_subgroups_map = {}
            return

        group_name = self.groups_listbox.get(selection[0])
        group_id = self.current_groups_map.get(group_name)

        self.subgroups_listbox.delete(0, tk.END)
        self.indicators_listbox.delete(0, tk.END)
        self.current_subgroups_map = {}
        if group_id:
            self.selected_group_id_for_new_subgroup = group_id
            self.add_subgroup_btn.config(state="normal")
            subgroups_data = db.get_kpi_subgroups_by_group(group_id)
            for i, sg in enumerate(subgroups_data):
                self.subgroups_listbox.insert(tk.END, sg["name"])
                self.current_subgroups_map[sg["name"]] = sg["id"]
                if (
                    pre_selected_subgroup_name
                    and sg["name"] == pre_selected_subgroup_name
                ):
                    self.subgroups_listbox.selection_set(i)
                    self.subgroups_listbox.activate(i)
                    self.subgroups_listbox.see(i)
            if pre_selected_subgroup_name and self.subgroups_listbox.curselection():
                self.on_subgroup_select()
            elif not self.subgroups_listbox.curselection():
                self.add_indicator_btn.config(state="disabled")
        else:
            self.add_subgroup_btn.config(state="disabled")
            self.add_indicator_btn.config(state="disabled")

    def on_subgroup_select(self, event=None):
        selection = self.subgroups_listbox.curselection()
        if not selection:
            self.indicators_listbox.delete(0, tk.END)
            self.add_indicator_btn.config(state="disabled")
            self.current_indicators_map = {}
            return

        subgroup_name = self.subgroups_listbox.get(selection[0])
        subgroup_id = self.current_subgroups_map.get(subgroup_name)

        self.indicators_listbox.delete(0, tk.END)
        self.current_indicators_map = {}
        if subgroup_id:
            self.selected_subgroup_id_for_new_indicator = subgroup_id
            self.add_indicator_btn.config(state="normal")
            for ind in db.get_kpi_indicators_by_subgroup(subgroup_id):
                self.indicators_listbox.insert(tk.END, ind["name"])
                self.current_indicators_map[ind["name"]] = ind["id"]
        else:
            self.add_indicator_btn.config(state="disabled")

    def add_new_group(self):
        name = simpledialog.askstring(
            "Nuovo Gruppo", "Nome del nuovo Gruppo KPI:", parent=self
        )
        if name:
            try:
                db.add_kpi_group(name)
                self.refresh_all_relevant_data()
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile aggiungere gruppo: {e}")

    def add_new_subgroup(self):
        if (
            not hasattr(self, "selected_group_id_for_new_subgroup")
            or not self.selected_group_id_for_new_subgroup
        ):
            messagebox.showwarning("Attenzione", "Seleziona prima un gruppo.")
            return
        name = simpledialog.askstring(
            "Nuovo Sottogruppo", "Nome del nuovo Sottogruppo KPI:", parent=self
        )
        if name:
            try:
                db.add_kpi_subgroup(name, self.selected_group_id_for_new_subgroup)
                selected_group_name = None
                if self.groups_listbox.curselection():
                    selected_group_name = self.groups_listbox.get(
                        self.groups_listbox.curselection()[0]
                    )
                self.refresh_all_relevant_data()

                if selected_group_name:
                    for i in range(self.groups_listbox.size()):
                        if self.groups_listbox.get(i) == selected_group_name:
                            self.groups_listbox.selection_set(i)
                            self.groups_listbox.event_generate("<<ListboxSelect>>")
                            self.after(
                                50,
                                lambda n=name: self._select_new_item_in_listbox(
                                    self.subgroups_listbox, n
                                ),
                            )
                            break
            except Exception as e:
                messagebox.showerror(
                    "Errore", f"Impossibile aggiungere sottogruppo: {e}"
                )

    def _select_new_item_in_listbox(self, listbox, item_name):
        for i in range(listbox.size()):
            if listbox.get(i) == item_name:
                listbox.selection_set(i)
                listbox.activate(i)
                listbox.see(i)
                listbox.event_generate("<<ListboxSelect>>")
                break

    def add_new_indicator(self):
        if (
            not hasattr(self, "selected_subgroup_id_for_new_indicator")
            or not self.selected_subgroup_id_for_new_indicator
        ):
            messagebox.showwarning(
                "Attenzione", "Seleziona prima un gruppo e un sottogruppo."
            )
            return
        name = simpledialog.askstring(
            "Nuovo Indicatore", "Nome del nuovo Indicatore KPI:", parent=self
        )
        if name:
            try:
                db.add_kpi_indicator(name, self.selected_subgroup_id_for_new_indicator)
                selected_group_name = None
                selected_subgroup_name = None
                if self.groups_listbox.curselection():
                    selected_group_name = self.groups_listbox.get(
                        self.groups_listbox.curselection()[0]
                    )
                if self.subgroups_listbox.curselection():
                    selected_subgroup_name = self.subgroups_listbox.get(
                        self.subgroups_listbox.curselection()[0]
                    )

                self.refresh_all_relevant_data()

                if selected_group_name:
                    for i in range(self.groups_listbox.size()):
                        if self.groups_listbox.get(i) == selected_group_name:
                            self.groups_listbox.selection_set(i)
                            self.groups_listbox.event_generate("<<ListboxSelect>>")
                            if selected_subgroup_name:
                                self.after(
                                    50,
                                    lambda sn=selected_subgroup_name, new_ind_name=name: self._select_sub_and_new_indicator(
                                        sn, new_ind_name
                                    ),
                                )
                            break
            except Exception as e:
                messagebox.showerror(
                    "Errore", f"Impossibile aggiungere indicatore: {e}"
                )

    def _select_sub_and_new_indicator(self, subgroup_name, indicator_name):
        for i in range(self.subgroups_listbox.size()):
            if self.subgroups_listbox.get(i) == subgroup_name:
                self.subgroups_listbox.selection_set(i)
                self.subgroups_listbox.activate(i)
                self.subgroups_listbox.see(i)
                self.subgroups_listbox.event_generate("<<ListboxSelect>>")
                self.after(
                    50,
                    lambda n=indicator_name: self._select_new_item_in_listbox(
                        self.indicators_listbox, n
                    ),
                )
                break

    # --- Scheda Gestione Specifiche KPI ---
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
            width=20,
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
                "ID",
                "Gruppo",
                "Sottogruppo",
                "Indicatore",
                "Descrizione",
                "Tipo Calcolo",
                "Unità Misura",
                "Visibile",
            ),
            show="headings",
        )
        cols_widths = {
            "ID": 40,
            "Gruppo": 120,
            "Sottogruppo": 120,
            "Indicatore": 150,
            "Descrizione": 200,
            "Tipo Calcolo": 100,
            "Unità Misura": 100,
            "Visibile": 70,
        }
        for col_name in self.kpi_specs_tree["columns"]:
            self.kpi_specs_tree.heading(col_name, text=col_name)
            anchor = "center" if col_name in ["ID", "Visibile"] else "w"
            stretch = (
                tk.NO
                if col_name in ["ID", "Visibile", "Tipo Calcolo", "Unità Misura"]
                else tk.YES
            )
            self.kpi_specs_tree.column(
                col_name,
                width=cols_widths.get(col_name, 100),
                anchor=anchor,
                stretch=stretch,
            )

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

    # --- Wrapper methods for UI-driven combobox selections ---
    def on_kpi_spec_group_selected_ui_driven(self, event=None):
        if self._populating_kpi_spec_combos:
            return
        self._populate_kpi_spec_subgroups(pre_selected_indicator_name=None)

    def on_kpi_spec_subgroup_selected_ui_driven(self, event=None):
        if self._populating_kpi_spec_combos:
            return
        self._populate_kpi_spec_indicators(pre_selected_indicator_name=None)

    def on_kpi_spec_indicator_selected_ui_driven(self, event=None):
        if self._populating_kpi_spec_combos:
            return
        self._load_or_prepare_kpi_spec_fields()

    def populate_kpi_spec_hier_combos(
        self, group_to_select=None, subgroup_to_select=None, indicator_to_select=None
    ):
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

    def _populate_kpi_spec_subgroups(
        self, subgroup_to_select=None, pre_selected_indicator_name=None
    ):
        group_name = self.kpi_spec_group_var.get()
        self.kpi_spec_subgroup_cb["values"] = []
        self.kpi_spec_indicator_cb["values"] = []

        if not subgroup_to_select:
            self.kpi_spec_subgroup_var.set("")
        if not pre_selected_indicator_name:
            self.kpi_spec_indicator_var.set("")

        selected_group = next(
            (g for g in self.groups_for_kpi_spec if g["name"] == group_name), None
        )
        if selected_group:
            self.subgroups_for_kpi_spec = db.get_kpi_subgroups_by_group(
                selected_group["id"]
            )
            subgroup_names = [sg["name"] for sg in self.subgroups_for_kpi_spec]
            self.kpi_spec_subgroup_cb["values"] = subgroup_names
            if subgroup_to_select and subgroup_to_select in subgroup_names:
                self.kpi_spec_subgroup_var.set(subgroup_to_select)
                self._populate_kpi_spec_indicators(pre_selected_indicator_name)
            elif not self._populating_kpi_spec_combos and not subgroup_to_select:
                self.clear_kpi_spec_fields(keep_hierarchy=True, keep_group=True)
        elif not self._populating_kpi_spec_combos:
            self.clear_kpi_spec_fields(keep_hierarchy=True)

    def _populate_kpi_spec_indicators(self, pre_selected_indicator_name=None):
        subgroup_name = self.kpi_spec_subgroup_var.get()
        self.kpi_spec_indicator_cb["values"] = []
        if not pre_selected_indicator_name:
            self.kpi_spec_indicator_var.set("")

        selected_subgroup = None
        if hasattr(self, "subgroups_for_kpi_spec") and self.subgroups_for_kpi_spec:
            selected_subgroup = next(
                (
                    sg
                    for sg in self.subgroups_for_kpi_spec
                    if sg["name"] == subgroup_name
                ),
                None,
            )

        if selected_subgroup:
            self.indicators_for_kpi_spec = db.get_kpi_indicators_by_subgroup(
                selected_subgroup["id"]
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
        self.save_kpi_spec_btn.config(text="Aggiungi Specifica KPI")

        selected_indicator_obj = None
        if hasattr(self, "indicators_for_kpi_spec") and self.indicators_for_kpi_spec:
            selected_indicator_obj = next(
                (
                    ind
                    for ind in self.indicators_for_kpi_spec
                    if isinstance(ind, (sqlite3.Row, dict))
                    and ind["name"] == indicator_name
                ),
                None,
            )

        if selected_indicator_obj:
            self.selected_indicator_id_for_spec = selected_indicator_obj["id"]
            existing_kpi_spec = next(
                (
                    kpi
                    for kpi in db.get_kpis()
                    if isinstance(kpi, (sqlite3.Row, dict))
                    and kpi["indicator_id"] == self.selected_indicator_id_for_spec
                ),
                None,
            )
            if existing_kpi_spec:
                self._set_kpi_spec_fields_from_data(existing_kpi_spec)
                self.current_editing_kpi_id = existing_kpi_spec["id"]
                self.save_kpi_spec_btn.config(text="Modifica Specifica KPI")
            else:
                self.clear_kpi_spec_fields(
                    keep_hierarchy=True,
                    keep_group=True,
                    keep_subgroup=True,
                    keep_indicator=True,
                )
        else:
            self.clear_kpi_spec_fields(
                keep_hierarchy=True,
                keep_group=True,
                keep_subgroup=True,
                keep_indicator=False,
            )

    def _set_kpi_spec_fields_from_data(self, kpi_data):
        self.kpi_spec_desc_var.set(kpi_data["description"] or "")
        self.kpi_spec_type_var.set(kpi_data["calculation_type"] or "Incrementale")
        self.kpi_spec_unit_var.set(kpi_data["unit_of_measure"] or "")
        self.kpi_spec_visible_var.set(bool(kpi_data["visible"]))

    def load_kpi_spec_for_editing(self, kpi_data):
        self._populating_kpi_spec_combos = True

        self.current_editing_kpi_id = kpi_data["id"]
        self.selected_indicator_id_for_spec = kpi_data["indicator_id"]

        self.populate_kpi_spec_hier_combos(
            group_to_select=kpi_data["group_name"],
            subgroup_to_select=kpi_data["subgroup_name"],
            indicator_to_select=kpi_data["indicator_name"],
        )
        # The call to populate_kpi_spec_hier_combos above will correctly set the combobox values
        # and trigger the chain that calls _load_or_prepare_kpi_spec_fields,
        # which then calls _set_kpi_spec_fields_from_data to fill the description, type, unit, etc.
        # It also sets the save button text.

        self._populating_kpi_spec_combos = False

    def clear_kpi_spec_fields_button_action(self):
        self._populating_kpi_spec_combos = True
        self.clear_kpi_spec_fields(keep_hierarchy=False)
        self.kpi_spec_group_var.set("")  # Explicitly clear vars tied to comboboxes
        self.kpi_spec_subgroup_var.set("")
        self.kpi_spec_indicator_var.set("")
        self.kpi_spec_subgroup_cb["values"] = []  # Clear lists
        self.kpi_spec_indicator_cb["values"] = []
        self.populate_kpi_spec_hier_combos()  # This will repopulate groups, and others will be cleared
        self._populating_kpi_spec_combos = False

    def clear_kpi_spec_fields(
        self,
        keep_hierarchy=False,
        keep_group=False,
        keep_subgroup=False,
        keep_indicator=False,
    ):
        # This method is primarily for clearing the data entry fields (description, type, etc.)
        # and managing the state (current_editing_kpi_id, selected_indicator_id_for_spec).
        # The StringVars for comboboxes are reset here IF their 'keep_X' flag is false.
        # The actual 'values' list of comboboxes should be managed by _populate methods.

        if not keep_hierarchy:  # Clears all three hierarchy StringVars
            self.kpi_spec_group_var.set("")
            self.kpi_spec_subgroup_var.set("")
            self.kpi_spec_indicator_var.set("")
            self.selected_indicator_id_for_spec = None
        elif not keep_group:  # Clears group and its dependents
            self.kpi_spec_group_var.set("")
            self.kpi_spec_subgroup_var.set("")
            self.kpi_spec_indicator_var.set("")
            self.selected_indicator_id_for_spec = None
        elif not keep_subgroup:  # Clears subgroup and its dependent
            self.kpi_spec_subgroup_var.set("")
            self.kpi_spec_indicator_var.set("")
            self.selected_indicator_id_for_spec = None
        elif not keep_indicator:  # Clears only indicator
            self.kpi_spec_indicator_var.set("")
            self.selected_indicator_id_for_spec = None
        # If all keep_X are True, none of the StringVars for comboboxes are changed here.

        self.kpi_spec_desc_var.set("")
        self.kpi_spec_type_var.set("Incrementale")
        self.kpi_spec_unit_var.set("")
        self.kpi_spec_visible_var.set(True)
        self.current_editing_kpi_id = None
        self.save_kpi_spec_btn.config(text="Aggiungi Specifica KPI")

    def save_kpi_specification(self):
        if not self.selected_indicator_id_for_spec:
            messagebox.showerror(
                "Errore", "Nessun indicatore valido selezionato per la specifica KPI."
            )
            return

        desc = self.kpi_spec_desc_var.get().strip()
        calc_type = self.kpi_spec_type_var.get()
        unit = self.kpi_spec_unit_var.get().strip()
        visible = self.kpi_spec_visible_var.get()

        if not desc:
            messagebox.showerror("Errore", "La descrizione del KPI è obbligatoria.")
            return

        try:
            if self.current_editing_kpi_id is not None:
                db.update_kpi(
                    self.current_editing_kpi_id,
                    self.selected_indicator_id_for_spec,
                    desc,
                    calc_type,
                    unit,
                    visible,
                )
                messagebox.showinfo(
                    "Successo", "Specifica KPI aggiornata con successo!"
                )
            else:
                db.add_kpi(
                    self.selected_indicator_id_for_spec, desc, calc_type, unit, visible
                )
                messagebox.showinfo(
                    "Successo", "Nuova specifica KPI aggiunta con successo!"
                )

            self.refresh_all_relevant_data()
            self.clear_kpi_spec_fields_button_action()
        except sqlite3.IntegrityError as ie:
            if (
                "UNIQUE constraint failed: kpis.indicator_id" in str(ie)
                and self.current_editing_kpi_id is None
            ):
                messagebox.showerror(
                    "Errore di Integrità",
                    f"Una specifica KPI per l'indicatore '{self.kpi_spec_indicator_var.get()}' esiste già. "
                    "Non è possibile aggiungerne un'altra. Selezionala per modificarla.",
                )
            else:
                messagebox.showerror(
                    "Errore di Integrità", f"Errore di integrità del database: {ie}"
                )
        except Exception as e:
            messagebox.showerror("Errore Inatteso", f"Salvataggio fallito: {e}")
            import traceback

            traceback.print_exc()

    def delete_selected_kpi_spec(self):
        selected_item_iid = self.kpi_specs_tree.focus()
        if not selected_item_iid:
            messagebox.showwarning(
                "Attenzione", "Nessuna specifica KPI selezionata nella tabella."
            )
            return

        item_values = self.kpi_specs_tree.item(selected_item_iid, "values")
        try:
            kpi_spec_id_to_delete = int(item_values[0])
            kpi_name_for_confirm = (
                f"{item_values[1]} > {item_values[2]} > {item_values[3]}"
            )
        except (IndexError, ValueError, TypeError):
            messagebox.showerror(
                "Errore",
                "Impossibile ottenere i dettagli della specifica KPI selezionata.",
            )
            return

        if messagebox.askyesno(
            "Conferma Eliminazione",
            f"Sei sicuro di voler eliminare la specifica KPI:\n{kpi_name_for_confirm}\n(ID: {kpi_spec_id_to_delete})?\n\nQuesta azione eliminerà anche tutti i target annuali e ripartiti associati.",
            parent=self,
        ):
            try:
                with sqlite3.connect(db.DB_TARGETS) as conn_targets:
                    conn_targets.execute(
                        "DELETE FROM annual_targets WHERE kpi_id = ?",
                        (kpi_spec_id_to_delete,),
                    )
                    conn_targets.commit()

                periodic_dbs = [
                    db.DB_KPI_DAYS,
                    db.DB_KPI_WEEKS,
                    db.DB_KPI_MONTHS,
                    db.DB_KPI_QUARTERS,
                ]
                periodic_tables = [
                    "daily_targets",
                    "weekly_targets",
                    "monthly_targets",
                    "quarterly_targets",
                ]
                for i, db_path in enumerate(periodic_dbs):
                    with sqlite3.connect(db_path) as conn_periodic:
                        conn_periodic.execute(
                            f"DELETE FROM {periodic_tables[i]} WHERE kpi_id = ?",
                            (kpi_spec_id_to_delete,),
                        )
                        conn_periodic.commit()

                with sqlite3.connect(db.DB_KPIS) as conn_kpis:
                    conn_kpis.execute(
                        "DELETE FROM kpis WHERE id = ?", (kpi_spec_id_to_delete,)
                    )
                    conn_kpis.commit()

                messagebox.showinfo(
                    "Successo", "Specifica KPI e target associati eliminati."
                )
                self.refresh_all_relevant_data()
                self.clear_kpi_spec_fields_button_action()
            except Exception as e:
                messagebox.showerror(
                    "Errore Eliminazione",
                    f"Impossibile eliminare la specifica KPI: {e}",
                )
                import traceback

                traceback.print_exc()

    def refresh_kpi_specs_tree(self):
        for i in self.kpi_specs_tree.get_children():
            self.kpi_specs_tree.delete(i)
        all_kpis = db.get_kpis()
        for kpi_row in all_kpis:
            if not isinstance(kpi_row, (sqlite3.Row, dict)):
                print(f"Skipping invalid KPI data in refresh_kpi_specs_tree: {kpi_row}")
                continue
            self.kpi_specs_tree.insert(
                "",
                "end",
                values=(
                    kpi_row["id"],
                    kpi_row["group_name"],
                    kpi_row["subgroup_name"],
                    kpi_row["indicator_name"],
                    kpi_row["description"],
                    kpi_row["calculation_type"],
                    kpi_row["unit_of_measure"] or "",
                    "Sì" if kpi_row["visible"] else "No",
                ),
            )
        self.populate_kpi_spec_hier_combos(
            group_to_select=(
                self.kpi_spec_group_var.get()
                if not self._populating_kpi_spec_combos
                else None
            ),
            subgroup_to_select=(
                self.kpi_spec_subgroup_var.get()
                if not self._populating_kpi_spec_combos
                else None
            ),
            indicator_to_select=(
                self.kpi_spec_indicator_var.get()
                if not self._populating_kpi_spec_combos
                else None
            ),
        )

    def on_kpi_spec_double_click(self, event):
        item_id_str = self.kpi_specs_tree.focus()
        if not item_id_str:
            return
        item_values = self.kpi_specs_tree.item(item_id_str, "values")

        if not item_values or len(item_values) == 0:
            return

        try:
            kpi_id_to_edit = int(item_values[0])
        except (ValueError, TypeError):
            messagebox.showerror(
                "Errore", "ID KPI non valido o mancante nella riga selezionata."
            )
            return

        kpi_data_full = db.get_kpi_by_id(kpi_id_to_edit)

        if kpi_data_full and isinstance(kpi_data_full, (sqlite3.Row, dict)):
            self.load_kpi_spec_for_editing(kpi_data_full)
        elif kpi_data_full:
            messagebox.showerror(
                "Errore", f"Formato dati KPI inatteso per ID {kpi_id_to_edit}."
            )

    # --- Scheda Gestione Stabilimenti ---
    def create_stabilimenti_widgets(self):
        self.st_tree = ttk.Treeview(
            self.stabilimenti_frame, columns=("ID", "Nome", "Visibile"), show="headings"
        )
        for col in self.st_tree["columns"]:
            self.st_tree.heading(col, text=col)
        self.st_tree.column("ID", width=50, anchor="center", stretch=tk.NO)
        self.st_tree.column("Nome", width=200)
        self.st_tree.column("Visibile", width=80, anchor="center", stretch=tk.NO)
        self.st_tree.pack(expand=True, fill="both")

        bf_container = ttk.Frame(self.stabilimenti_frame)
        bf_container.pack(fill="x", pady=5)

        bf = ttk.Frame(bf_container)
        bf.pack()

        ttk.Button(bf, text="Aggiungi", command=self.add_stabilimento_window).pack(
            side="left", padx=2
        )
        ttk.Button(bf, text="Modifica", command=self.edit_stabilimento_window).pack(
            side="left", padx=2
        )

    def refresh_stabilimenti_tree(self):
        for i in self.st_tree.get_children():
            self.st_tree.delete(i)
        for r_dict in db.get_stabilimenti():
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
        sel = self.st_tree.focus()
        if not sel:
            messagebox.showwarning(
                "Attenzione", "Seleziona uno stabilimento da modificare."
            )
            return
        item_data = self.st_tree.item(sel)
        item_values = item_data["values"]
        if not item_values or len(item_values) < 3:
            return

        try:
            st_id = int(item_values[0])
            st_name = item_values[1]
            st_visible_str = item_values[2]
            self.stabilimento_editor_window(data_tuple=(st_id, st_name, st_visible_str))
        except (ValueError, TypeError):
            messagebox.showerror(
                "Errore", "Dati stabilimento non validi per la modifica."
            )
            return

    def stabilimento_editor_window(self, data_tuple=None):
        win = tk.Toplevel(self)
        win.title("Editor Stabilimento" if data_tuple else "Nuovo Stabilimento")
        win.transient(self)
        win.grab_set()
        win.geometry("350x150")

        s_id = data_tuple[0] if data_tuple else None
        s_name = data_tuple[1] if data_tuple else ""
        s_vis_str = data_tuple[2] if data_tuple else "Sì"

        form_frame = ttk.Frame(win, padding=10)
        form_frame.pack(expand=True, fill="both")

        ttk.Label(form_frame, text="Nome:").grid(
            row=0, column=0, sticky="w", padx=5, pady=5
        )
        nv = tk.StringVar(value=s_name)
        name_entry = ttk.Entry(form_frame, textvariable=nv, width=30)
        name_entry.grid(row=0, column=1, padx=5, pady=5)
        name_entry.focus()

        vv = tk.BooleanVar(value=(s_vis_str == "Sì"))
        ttk.Checkbutton(
            form_frame, text="Visibile per Inserimento Target", variable=vv
        ).grid(row=1, column=1, sticky="w", padx=5, pady=5)

        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=2, columnspan=2, pady=10)

        def save_st():
            nome_val = nv.get().strip()
            if not nome_val:
                messagebox.showerror(
                    "Errore", "Il nome dello stabilimento è obbligatorio.", parent=win
                )
                return
            try:
                if s_id is not None:
                    db.update_stabilimento(s_id, nome_val, vv.get())
                else:
                    db.add_stabilimento(nome_val, vv.get())
                self.refresh_all_relevant_data()
                win.destroy()
            except sqlite3.IntegrityError:
                messagebox.showerror(
                    "Errore",
                    f"Uno stabilimento con nome '{nome_val}' esiste già.",
                    parent=win,
                )
            except Exception as e:
                messagebox.showerror("Errore", f"Salvataggio fallito: {e}", parent=win)

        ttk.Button(
            btn_frame, text="Salva", command=save_st, style="Accent.TButton"
        ).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Annulla", command=win.destroy).pack(
            side="left", padx=5
        )

    # --- Scheda Inserimento Target ---
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
        save_button_frame = ttk.Frame(self.target_frame)
        save_button_frame.pack(fill="x", pady=8)
        ttk.Button(
            save_button_frame,
            text="SALVA TUTTI I TARGET",
            command=self.save_all_targets_entry,
            style="Accent.TButton",
        ).pack()
        self.kpi_target_entry_widgets = {}

    def _on_mousewheel_target(self, event):
        widget = self.winfo_containing(event.x_root, event.y_root)
        if (
            widget is self.canvas_target
            or (
                hasattr(widget, "master")
                and widget.master is self.scrollable_frame_target
            )
            or widget is self.scrollable_frame_target
        ):
            if sys.platform.startswith("win") or sys.platform.startswith("darwin"):
                delta = -1 * (event.delta // 120)
            else:
                if event.num == 4:
                    delta = -1
                elif event.num == 5:
                    delta = 1
                else:
                    delta = 0
            self.canvas_target.yview_scroll(delta, "units")

    def populate_target_comboboxes(self):
        stabilimenti_vis = db.get_stabilimenti(only_visible=True)
        self.stabilimenti_map_target = {s["name"]: s["id"] for s in stabilimenti_vis}
        current_stabilimento = self.stabilimento_var_target.get()
        self.stabilimento_cb_target["values"] = list(
            self.stabilimenti_map_target.keys()
        )
        if (
            current_stabilimento
            and current_stabilimento in self.stabilimenti_map_target
        ):
            self.stabilimento_var_target.set(current_stabilimento)
        elif self.stabilimenti_map_target:
            self.stabilimento_var_target.set(
                list(self.stabilimenti_map_target.keys())[0]
            )
        else:
            self.stabilimento_var_target.set("")
        self.load_kpi_targets_for_entry_target()

    def _update_repartition_input_area_tk(
        self,
        container,
        profile_var,
        logic_var,
        repartition_vars_dict,
        default_repartition_map,
        kpi_id,
        calc_type,
    ):
        for widget in container.winfo_children():
            widget.destroy()
        repartition_vars_dict.clear()
        profile = profile_var.get()
        if profile in ["monthly_sinusoidal", "legacy_intra_period_progressive"]:
            logic_frame = ttk.Frame(container)
            logic_frame.pack(fill="x", pady=(5, 2))
            ttk.Label(
                logic_frame, text="Logica Ripartizione % Annuale:", width=25
            ).pack(side="left", padx=(0, 5))
            cmd = lambda p=profile_var, l=logic_var, r_vars=repartition_vars_dict, c=container, def_map=default_repartition_map, kid=kpi_id, ct=calc_type: self._update_repartition_input_area_tk(
                c, p, l, r_vars, def_map, kid, ct
            )
            ttk.Radiobutton(
                logic_frame, text="Mese", variable=logic_var, value="Mese", command=cmd
            ).pack(side="left")
            ttk.Radiobutton(
                logic_frame,
                text="Trimestre",
                variable=logic_var,
                value="Trimestre",
                command=cmd,
            ).pack(side="left", padx=5)
            if not logic_var.get():
                logic_var.set("Mese")
            input_area = ttk.Frame(container)
            input_area.pack(fill="x", expand=True)
            current_logic = logic_var.get()
            periods = (
                [calendar.month_name[i] for i in range(1, 13)]
                if current_logic == "Mese"
                else ["Q1", "Q2", "Q3", "Q4"] if current_logic == "Trimestre" else []
            )
            num_cols = 4
            default_perc_val = (100.0 / len(periods)) if periods else 0
            for i, period_name in enumerate(periods):
                row, col = divmod(i, num_cols)
                period_frame = ttk.Frame(input_area)
                period_frame.grid(row=row, column=col, padx=3, pady=2, sticky="ew")
                input_area.columnconfigure(col, weight=1)
                ttk.Label(period_frame, text=f"{period_name} (%):", width=12).pack(
                    side="left"
                )
                val_to_set = default_repartition_map.get(period_name, default_perc_val)
                var = tk.DoubleVar(value=round(val_to_set, 2))
                repartition_vars_dict[period_name] = var
                ttk.Entry(period_frame, textvariable=var, width=7).pack(
                    side="left", fill="x", expand=True
                )
        else:
            logic_var.set("")

    def load_kpi_targets_for_entry_target(self, event=None):
        for widget in self.scrollable_frame_target.winfo_children():
            widget.destroy()
        self.kpi_target_entry_widgets.clear()
        self.canvas_target.yview_moveto(0)
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
            kpi_id = kpi_row_data["id"]
            if kpi_id is None:
                continue
            kpi_display_name_str = get_kpi_display_name(kpi_row_data)
            kpi_unit = kpi_row_data["unit_of_measure"] or ""
            calc_type = kpi_row_data["calculation_type"]
            frame_label_text = (
                f"{kpi_display_name_str}{f' (Unità: {kpi_unit})' if kpi_unit else ''}"
            )
            kpi_entry_frame = ttk.LabelFrame(
                self.scrollable_frame_target, text=frame_label_text, padding=10
            )
            kpi_entry_frame.pack(fill="x", expand=True, padx=5, pady=(0, 7))
            existing_target_db = db.get_annual_target(year, stabilimento_id, kpi_id)
            (
                def_target1_val,
                def_target2_val,
                def_logic_val,
                def_profile_val,
                def_repart_map_val,
            ) = (0.0, 0.0, "Mese", "annual_progressive", {})
            if existing_target_db and isinstance(
                existing_target_db, (sqlite3.Row, dict)
            ):
                def_target1_val = float(existing_target_db["annual_target1"] or 0.0)
                def_target2_val = float(existing_target_db["annual_target2"] or 0.0)
                def_logic_val = existing_target_db["repartition_logic"] or "Mese"
                db_profile = existing_target_db["distribution_profile"]
                if db_profile and db_profile in self.distribution_profile_options_tk:
                    def_profile_val = db_profile
                elif not db_profile:
                    def_profile_val = "annual_progressive"
                repart_values_str = existing_target_db["repartition_values"]
                if repart_values_str:
                    try:
                        loaded_map = json.loads(repart_values_str)
                        if isinstance(loaded_map, dict):
                            def_repart_map_val = loaded_map
                    except json.JSONDecodeError:
                        pass
            target1_var, target2_var = tk.DoubleVar(
                value=def_target1_val
            ), tk.DoubleVar(value=def_target2_val)
            profile_var_entry, logic_var_entry = tk.StringVar(
                value=def_profile_val
            ), tk.StringVar(value=def_logic_val)
            repartition_input_vars_entry = {}
            top_row_frame_entry = ttk.Frame(kpi_entry_frame)
            top_row_frame_entry.pack(fill="x", pady=(0, 5))
            ttk.Label(top_row_frame_entry, text="Target 1:", width=8).pack(side="left")
            ttk.Entry(top_row_frame_entry, textvariable=target1_var, width=10).pack(
                side="left", padx=(2, 8)
            )
            ttk.Label(top_row_frame_entry, text="Target 2:", width=8).pack(side="left")
            ttk.Entry(top_row_frame_entry, textvariable=target2_var, width=10).pack(
                side="left", padx=(2, 8)
            )
            ttk.Label(
                top_row_frame_entry, text="Profilo Distribuzione:", width=18
            ).pack(side="left")
            profile_cb_entry = ttk.Combobox(
                top_row_frame_entry,
                textvariable=profile_var_entry,
                values=self.distribution_profile_options_tk,
                state="readonly",
                width=26,
            )
            profile_cb_entry.pack(side="left", padx=(2, 0), fill="x", expand=True)
            repartition_controls_container_entry = ttk.Frame(kpi_entry_frame)
            repartition_controls_container_entry.pack(fill="x", pady=(2, 0))
            cmd_profile_change = lambda e, p=profile_var_entry, l=logic_var_entry, r=repartition_input_vars_entry, cont=repartition_controls_container_entry, dmap=def_repart_map_val, kid=kpi_id, ctype=calc_type: self._update_repartition_input_area_tk(
                cont, p, l, r, dmap, kid, ctype
            )
            profile_cb_entry.bind("<<ComboboxSelected>>", cmd_profile_change)
            self.kpi_target_entry_widgets[kpi_id] = {
                "target1_var": target1_var,
                "target2_var": target2_var,
                "profile_var": profile_var_entry,
                "logic_var": logic_var_entry,
                "repartition_vars": repartition_input_vars_entry,
                "calc_type": calc_type,
                "repartition_controls_container": repartition_controls_container_entry,
                "kpi_display_name": kpi_display_name_str,
            }
            self._update_repartition_input_area_tk(
                repartition_controls_container_entry,
                profile_var_entry,
                logic_var_entry,
                repartition_input_vars_entry,
                def_repart_map_val,
                kpi_id,
                calc_type,
            )
        self.scrollable_frame_target.update_idletasks()
        self.canvas_target.config(scrollregion=self.canvas_target.bbox("all"))

    def save_all_targets_entry(self):
        try:
            year_val = int(self.year_var_target.get())
            stabilimento_id_val = self.stabilimenti_map_target.get(
                self.stabilimento_var_target.get()
            )
            if stabilimento_id_val is None:
                messagebox.showerror("Errore", "Stabilimento non valido selezionato.")
                return
        except (ValueError, KeyError):
            messagebox.showerror("Errore", "Seleziona anno e stabilimento validi.")
            return
        targets_to_save_for_db, all_inputs_valid_target = {}, True
        for kpi_id_val, widgets_dict in self.kpi_target_entry_widgets.items():
            try:
                annual_target1, annual_target2 = (
                    widgets_dict["target1_var"].get(),
                    widgets_dict["target2_var"].get(),
                )
            except tk.TclError:
                messagebox.showerror(
                    "Errore Validazione",
                    f"KPI '{widgets_dict['kpi_display_name']}': Valore target non numerico.",
                )
                all_inputs_valid_target = False
                break
            profile_val, repartition_logic_val, repartition_values_val = (
                widgets_dict["profile_var"].get(),
                widgets_dict["logic_var"].get(),
                {},
            )
            if profile_val in ["monthly_sinusoidal", "legacy_intra_period_progressive"]:
                if not repartition_logic_val:
                    messagebox.showerror(
                        "Errore Interno",
                        f"KPI '{widgets_dict['kpi_display_name']}': Logica di ripartizione non impostata per profilo {profile_val}.",
                    )
                    all_inputs_valid_target = False
                    break
                current_sum_perc, num_repart_periods = 0.0, 0
                for key, var_obj in widgets_dict["repartition_vars"].items():
                    try:
                        val = var_obj.get()
                        repartition_values_val[key] = val
                        current_sum_perc += val
                        num_repart_periods += 1
                    except tk.TclError:
                        messagebox.showerror(
                            "Errore Validazione",
                            f"KPI '{widgets_dict['kpi_display_name']}': Valore percentuale non numerico per '{key}'.",
                        )
                        all_inputs_valid_target = False
                        break
                if not all_inputs_valid_target:
                    break
                if (
                    num_repart_periods > 0
                    and (annual_target1 > 1e-9 or annual_target2 > 1e-9)
                    and not (99.9 <= current_sum_perc <= 100.1)
                ):
                    messagebox.showerror(
                        "Errore Validazione",
                        f"KPI '{widgets_dict['kpi_display_name']}', la somma delle percentuali di ripartizione ({repartition_logic_val}) è {current_sum_perc:.2f}%. Deve essere circa 100%.",
                    )
                    all_inputs_valid_target = False
                    break
            else:
                repartition_logic_val, repartition_values_val = "Mese", {
                    calendar.month_name[i]: round(100.0 / 12.0, 5) for i in range(1, 13)
                }
            targets_to_save_for_db[kpi_id_val] = {
                "annual_target1": annual_target1,
                "annual_target2": annual_target2,
                "repartition_logic": repartition_logic_val,
                "repartition_values": repartition_values_val,
                "distribution_profile": profile_val,
            }
        if not all_inputs_valid_target:
            return
        if not targets_to_save_for_db:
            messagebox.showwarning("Attenzione", "Nessun target definito da salvare.")
            return
        try:
            db.save_annual_targets(
                year_val, stabilimento_id_val, targets_to_save_for_db
            )
            messagebox.showinfo(
                "Successo", "Target salvati e ripartizioni ricalcolate (inclusi CSV)!"
            )
            self.refresh_all_relevant_data()
        except Exception as e:
            messagebox.showerror(
                "Errore Salvataggio",
                f"Errore durante il salvataggio o il ricalcolo: {e}",
            )
            import traceback

            traceback.print_exc()

    # --- Scheda Visualizzazione Risultati ---
    def create_results_widgets(self):
        filter_frame_outer_res = ttk.Frame(self.results_frame)
        filter_frame_outer_res.pack(fill="x", pady=5)
        filter_frame_res = ttk.Frame(filter_frame_outer_res)
        filter_frame_res.pack()
        ttk.Label(filter_frame_res, text="Anno:").pack(side="left")
        self.res_year_var_vis = tk.StringVar(value=str(datetime.datetime.now().year))
        ttk.Spinbox(
            filter_frame_res,
            from_=2020,
            to=2050,
            textvariable=self.res_year_var_vis,
            width=6,
            command=self.show_results_data,
        ).pack(side="left", padx=(2, 5))
        ttk.Label(filter_frame_res, text="Stabilimento:").pack(side="left", padx=(5, 0))
        self.res_stabilimento_var_vis = tk.StringVar()
        self.res_stabilimento_cb_vis = ttk.Combobox(
            filter_frame_res,
            textvariable=self.res_stabilimento_var_vis,
            state="readonly",
            width=16,
        )
        self.res_stabilimento_cb_vis.pack(side="left", padx=(2, 5))
        self.res_stabilimento_cb_vis.bind(
            "<<ComboboxSelected>>", self.show_results_data
        )
        ttk.Label(filter_frame_res, text="Gruppo:").pack(side="left", padx=(5, 0))
        self.res_group_var = tk.StringVar()
        self.res_group_cb = ttk.Combobox(
            filter_frame_res,
            textvariable=self.res_group_var,
            state="readonly",
            width=13,
        )
        self.res_group_cb.pack(side="left", padx=(2, 2))
        self.res_group_cb.bind(
            "<<ComboboxSelected>>", self.on_res_group_selected_refresh_results
        )
        ttk.Label(filter_frame_res, text="Sottogruppo:").pack(side="left")
        self.res_subgroup_var = tk.StringVar()
        self.res_subgroup_cb = ttk.Combobox(
            filter_frame_res,
            textvariable=self.res_subgroup_var,
            state="readonly",
            width=13,
        )
        self.res_subgroup_cb.pack(side="left", padx=(2, 2))
        self.res_subgroup_cb.bind(
            "<<ComboboxSelected>>", self.on_res_subgroup_selected_refresh_results
        )
        ttk.Label(filter_frame_res, text="Indicatore:").pack(side="left")
        self.res_indicator_var = tk.StringVar()
        self.res_indicator_cb = ttk.Combobox(
            filter_frame_res,
            textvariable=self.res_indicator_var,
            state="readonly",
            width=18,
        )
        self.res_indicator_cb.pack(side="left", padx=(2, 5))
        self.res_indicator_cb.bind("<<ComboboxSelected>>", self.show_results_data)
        ttk.Label(filter_frame_res, text="Periodo:").pack(side="left", padx=(5, 0))
        self.res_period_var_vis = tk.StringVar(value="Mese")
        self.res_period_cb_vis = ttk.Combobox(
            filter_frame_res,
            textvariable=self.res_period_var_vis,
            state="readonly",
            values=["Giorno", "Settimana", "Mese", "Trimestre"],
            width=9,
        )
        self.res_period_cb_vis.current(2)
        self.res_period_cb_vis.pack(side="left", padx=(2, 5))
        self.res_period_cb_vis.bind("<<ComboboxSelected>>", self.show_results_data)
        ttk.Label(filter_frame_res, text="Target:").pack(side="left", padx=(5, 0))
        self.res_target_num_var = tk.IntVar(value=1)
        ttk.Radiobutton(
            filter_frame_res,
            text="T1",
            variable=self.res_target_num_var,
            value=1,
            command=self.show_results_data,
        ).pack(side="left")
        ttk.Radiobutton(
            filter_frame_res,
            text="T2",
            variable=self.res_target_num_var,
            value=2,
            command=self.show_results_data,
        ).pack(side="left", padx=(0, 5))
        ttk.Button(
            filter_frame_res,
            text="Aggiorna Vista",
            command=self.show_results_data,
            style="Accent.TButton",
        ).pack(side="left", padx=5)
        self.results_data_tree = ttk.Treeview(
            self.results_frame, columns=("Periodo", "Target"), show="headings"
        )
        self.results_data_tree.heading("Periodo", text="Periodo")
        self.results_data_tree.heading("Target", text="Valore Target")
        self.results_data_tree.column("Periodo", width=200, anchor="w")
        self.results_data_tree.column("Target", width=150, anchor="e")
        self.results_data_tree.pack(fill="both", expand=True, pady=(5, 0))
        self.summary_label_var_vis = tk.StringVar()
        ttk.Label(
            self.results_frame,
            textvariable=self.summary_label_var_vis,
            font=("Calibri", 10, "italic"),
        ).pack(pady=5, anchor="e", padx=10)

    def on_res_group_selected_refresh_results(self, event=None):
        self.on_res_group_selected(event)
        self.show_results_data()

    def on_res_subgroup_selected_refresh_results(self, event=None):
        self.on_res_subgroup_selected(event)
        self.show_results_data()

    def populate_results_comboboxes(self):
        current_stabilimento = self.res_stabilimento_var_vis.get()
        stabilimenti_all = db.get_stabilimenti()
        self.res_stabilimenti_map_vis = {s["name"]: s["id"] for s in stabilimenti_all}
        self.res_stabilimento_cb_vis["values"] = list(
            self.res_stabilimenti_map_vis.keys()
        )
        if (
            current_stabilimento
            and current_stabilimento in self.res_stabilimenti_map_vis
        ):
            self.res_stabilimento_var_vis.set(current_stabilimento)
        elif self.res_stabilimenti_map_vis:
            self.res_stabilimento_var_vis.set(
                list(self.res_stabilimenti_map_vis.keys())[0]
            )
        else:
            self.res_stabilimento_var_vis.set("")

        current_group, current_subgroup, current_indicator = (
            self.res_group_var.get(),
            self.res_subgroup_var.get(),
            self.res_indicator_var.get(),
        )
        self.res_groups_list = db.get_kpi_groups()
        self.res_group_cb["values"] = [g["name"] for g in self.res_groups_list]

        if current_group and current_group in [g["name"] for g in self.res_groups_list]:
            self.res_group_var.set(current_group)
            self.on_res_group_selected(
                pre_selected_subgroup=current_subgroup,
                pre_selected_indicator=current_indicator,
            )
        else:
            self.res_group_var.set("")
            self.res_subgroup_var.set("")
            self.res_indicator_var.set("")
            # Corrected individual assignments here
            self.res_subgroup_cb["values"] = []
            self.res_indicator_cb["values"] = []
            self.current_kpi_id_for_results = None
        self.show_results_data()

    def on_res_group_selected(
        self, event=None, pre_selected_subgroup=None, pre_selected_indicator=None
    ):
        group_name = self.res_group_var.get()
        self.res_subgroup_cb["values"], self.res_indicator_cb["values"] = [], []
        if not pre_selected_subgroup:
            self.res_subgroup_var.set("")
        if not pre_selected_indicator:
            self.res_indicator_var.set("")
        self.current_kpi_id_for_results = None
        selected_group = next(
            (
                g
                for g in self.res_groups_list
                if isinstance(g, (sqlite3.Row, dict)) and g["name"] == group_name
            ),
            None,
        )
        if selected_group:
            self.res_subgroups_list = db.get_kpi_subgroups_by_group(
                selected_group["id"]
            )
            self.res_subgroup_cb["values"] = [
                sg["name"]
                for sg in self.res_subgroups_list
                if isinstance(sg, (sqlite3.Row, dict))
            ]
            if (
                pre_selected_subgroup
                and pre_selected_subgroup in self.res_subgroup_cb["values"]
            ):
                self.res_subgroup_var.set(pre_selected_subgroup)
                self.on_res_subgroup_selected(
                    pre_selected_indicator=pre_selected_indicator
                )

    def on_res_subgroup_selected(self, event=None, pre_selected_indicator=None):
        subgroup_name = self.res_subgroup_var.get()
        self.res_indicator_cb["values"] = []
        if not pre_selected_indicator:
            self.res_indicator_var.set("")
        self.current_kpi_id_for_results = None
        selected_subgroup = None
        if hasattr(self, "res_subgroups_list") and self.res_subgroups_list is not None:
            selected_subgroup = next(
                (
                    sg
                    for sg in self.res_subgroups_list
                    if isinstance(sg, (sqlite3.Row, dict))
                    and sg["name"] == subgroup_name
                ),
                None,
            )
        if selected_subgroup:
            all_indicators_in_subgroup = db.get_kpi_indicators_by_subgroup(
                selected_subgroup["id"]
            )
            kpis_defined_specs = db.get_kpis()
            defined_indicator_ids_with_spec = {
                k["indicator_id"]
                for k in kpis_defined_specs
                if isinstance(k, (sqlite3.Row, dict))
            }
            self.res_indicators_list_filtered = [
                ind
                for ind in all_indicators_in_subgroup
                if isinstance(ind, (sqlite3.Row, dict))
                and ind["id"] in defined_indicator_ids_with_spec
            ]
            self.res_indicator_cb["values"] = [
                ind["name"] for ind in self.res_indicators_list_filtered
            ]
            if (
                pre_selected_indicator
                and pre_selected_indicator in self.res_indicator_cb["values"]
            ):
                self.res_indicator_var.set(pre_selected_indicator)

    def show_results_data(self, event=None):
        for i in self.results_data_tree.get_children():
            self.results_data_tree.delete(i)
        self.summary_label_var_vis.set("")
        try:
            year_val_res_str = self.res_year_var_vis.get()
            if not year_val_res_str:
                return
            year_val_res = int(year_val_res_str)
            stabilimento_name_res, indicator_name_res, period_type_res = (
                self.res_stabilimento_var_vis.get(),
                self.res_indicator_var.get(),
                self.res_period_var_vis.get(),
            )
            target_num_to_show = self.res_target_num_var.get()
            if not all([stabilimento_name_res, indicator_name_res, period_type_res]):
                return
            stabilimento_id_res = self.res_stabilimenti_map_vis.get(
                stabilimento_name_res
            )
            if stabilimento_id_res is None:
                return
            selected_indicator_obj = None
            if (
                hasattr(self, "res_indicators_list_filtered")
                and self.res_indicators_list_filtered
            ):
                selected_indicator_obj = next(
                    (
                        ind
                        for ind in self.res_indicators_list_filtered
                        if isinstance(ind, (sqlite3.Row, dict))
                        and ind["name"] == indicator_name_res
                    ),
                    None,
                )
            if not selected_indicator_obj:
                return
            indicator_id_for_spec_lookup = selected_indicator_obj["id"]
            if indicator_id_for_spec_lookup is None:
                return
            kpi_data_obj = next(
                (
                    kpi_spec
                    for kpi_spec in db.get_kpis()
                    if isinstance(kpi_spec, (sqlite3.Row, dict))
                    and kpi_spec["indicator_id"] == indicator_id_for_spec_lookup
                ),
                None,
            )
            if not kpi_data_obj:
                return
            kpi_id_res, calc_type_res, kpi_unit_res = (
                kpi_data_obj["id"],
                kpi_data_obj["calculation_type"],
                kpi_data_obj["unit_of_measure"] or "",
            )
            kpi_display_name_res_str = get_kpi_display_name(kpi_data_obj)
            target_ann_info_res = db.get_annual_target(
                year_val_res, stabilimento_id_res, kpi_id_res
            )
            profile_disp_res = "N/D"
            if target_ann_info_res and isinstance(
                target_ann_info_res, (sqlite3.Row, dict)
            ):
                prof_val = target_ann_info_res["distribution_profile"]
                profile_disp_res = prof_val if prof_val else "annual_progressive"
            data_ripartiti_res = db.get_ripartiti_data(
                year_val_res,
                stabilimento_id_res,
                kpi_id_res,
                period_type_res,
                target_num_to_show,
            )
            if not data_ripartiti_res:
                self.summary_label_var_vis.set(
                    f"Nessun dato ripartito per {kpi_display_name_res_str}, Target {target_num_to_show} (Profilo: {profile_disp_res})."
                )
                return
            total_sum_res, count_res = 0.0, 0
            for row_data in data_ripartiti_res:
                period_val, target_val = row_data["Periodo"], row_data["Target"]
                self.results_data_tree.insert(
                    "", "end", values=(period_val, f"{target_val:.2f}")
                )
                if isinstance(target_val, (int, float)):
                    total_sum_res += target_val
                    count_res += 1
            summary_text_res = f"KPI: {kpi_display_name_res_str} | Profilo: {profile_disp_res} | Target: {target_num_to_show} | "
            if count_res > 0:
                summary_text_res += (
                    f"Totale Ripartito ({period_type_res}): {total_sum_res:,.2f} {kpi_unit_res}"
                    if calc_type_res == "Incrementale"
                    else f"Media Ripartita ({period_type_res}): {(total_sum_res / count_res if count_res > 0 else 0):,.2f} {kpi_unit_res}"
                )
            else:
                summary_text_res += "Nessun dato aggregato."
            self.summary_label_var_vis.set(summary_text_res)
        except ValueError:
            return
        except Exception as e:
            self.summary_label_var_vis.set(f"Errore: {e}")

    # --- Scheda Esportazione Dati ---
    def create_export_widgets(self):
        export_main_frame = ttk.Frame(self.export_frame, padding=20)
        export_main_frame.pack(expand=True, fill="both")
        export_info_label_frame = ttk.Frame(export_main_frame)
        export_info_label_frame.pack(pady=10, anchor="center")
        resolved_path_str = "Percorso non disponibile"
        try:
            resolved_path_str = str(Path(db.CSV_EXPORT_BASE_PATH).resolve())
        except Exception:
            pass
        export_info_label = ttk.Label(
            export_info_label_frame,
            text=(
                f"I 5 file CSV globali vengono generati/sovrascritti automaticamente ogni volta che si salvano i target annuali.\n\nQuesti file sono salvati direttamente in:\n{resolved_path_str}"
            ),
            wraplength=700,
            justify="center",
            font=("Calibri", 11),
        )
        export_info_label.pack()
        export_button_frame = ttk.Frame(export_main_frame)
        export_button_frame.pack(pady=30, anchor="center")
        ttk.Button(
            export_button_frame,
            text="Esporta i CSV Globali Esistenti in un File ZIP...",
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
            export_path = Path(db.CSV_EXPORT_BASE_PATH).resolve()
            if not export_path.exists():
                export_path.mkdir(parents=True, exist_ok=True)
                messagebox.showinfo(
                    "Cartella Creata",
                    f"La cartella delle esportazioni è stata creata:\n{export_path}\n\nÈ attualmente vuota. Salva qualche target per popolarla.",
                    parent=self,
                )
            if sys.platform == "win32":
                os.startfile(export_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(export_path)])
            else:
                subprocess.Popen(["xdg-open", str(export_path)])
        except AttributeError:
            messagebox.showerror(
                "Errore Configurazione",
                "Il percorso base per le esportazioni CSV non è configurato correttamente.",
                parent=self,
            )
        except Exception as e:
            messagebox.showerror(
                "Errore Apertura Cartella",
                f"Impossibile aprire la cartella delle esportazioni: {e}",
                parent=self,
            )

    def export_all_data_to_zip(self):
        try:
            export_base_path_str = db.CSV_EXPORT_BASE_PATH
            if not export_base_path_str:
                messagebox.showerror(
                    "Errore Configurazione",
                    "Percorso base esportazioni non definito.",
                    parent=self,
                )
                return
            export_base_path = Path(export_base_path_str)
        except AttributeError:
            messagebox.showerror(
                "Errore Configurazione",
                "Il percorso base per le esportazioni CSV non è configurato.",
                parent=self,
            )
            return
        if not export_base_path.exists() or not any(
            f.name in export_manager.GLOBAL_CSV_FILES.values()
            for f in export_base_path.iterdir()
            if f.is_file()
        ):
            messagebox.showwarning(
                "Nessun Dato",
                f"Nessuno dei file CSV globali attesi è stato trovato in {export_base_path.resolve()}. Salva prima qualche target.",
                parent=self,
            )
            return
        default_zip_name = f"kpi_global_data_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        zip_filepath = filedialog.asksaveasfilename(
            title="Salva archivio ZIP con i CSV globali",
            initialfile=default_zip_name,
            defaultextension=".zip",
            filetypes=[("File ZIP", "*.zip"), ("Tutti i file", "*.*")],
            parent=self,
        )
        if not zip_filepath:
            return
        try:
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
                f"Si è verificato un errore imprevisto durante la creazione dello ZIP: {e}",
                parent=self,
            )


if __name__ == "__main__":
    app = KpiApp()
    app.mainloop()
