import tkinter as tk
from tkinter import ttk, messagebox
import traceback
import sqlite3

from kpi_management import specs as kpi_specs_manager
from kpi_management import indicators as kpi_indicators_manager
import data_retriever as db_retriever
from ...shared.constants import KPI_CALC_TYPE_OPTIONS

class KpiSpecsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._populating_kpi_spec_combos = False
        self.current_editing_kpi_id = None
        self.selected_indicator_id_for_spec = None
        self.create_widgets()

    def create_widgets(self):
        add_kpi_frame_outer = ttk.LabelFrame(self, text="Aggiungi/Modifica Specifica KPI", padding=10)
        add_kpi_frame_outer.pack(fill="x", pady=10, padx=5)

        hier_frame = ttk.Frame(add_kpi_frame_outer)
        hier_frame.pack(fill="x", pady=5)
        ttk.Label(hier_frame, text="Gruppo:").pack(side="left")
        self.kpi_spec_group_var = tk.StringVar()
        self.kpi_spec_group_cb = ttk.Combobox(hier_frame, textvariable=self.kpi_spec_group_var, state="readonly", width=20)
        self.kpi_spec_group_cb.pack(side="left", padx=5)
        self.kpi_spec_group_cb.bind("<<ComboboxSelected>>", self.on_kpi_spec_group_selected)

        ttk.Label(hier_frame, text="Sottogruppo:").pack(side="left")
        self.kpi_spec_subgroup_var = tk.StringVar()
        self.kpi_spec_subgroup_cb = ttk.Combobox(hier_frame, textvariable=self.kpi_spec_subgroup_var, state="readonly", width=30)
        self.kpi_spec_subgroup_cb.pack(side="left", padx=5)
        self.kpi_spec_subgroup_cb.bind("<<ComboboxSelected>>", self.on_kpi_spec_subgroup_selected)

        ttk.Label(hier_frame, text="Indicatore:").pack(side="left")
        self.kpi_spec_indicator_var = tk.StringVar()
        self.kpi_spec_indicator_cb = ttk.Combobox(hier_frame, textvariable=self.kpi_spec_indicator_var, state="readonly", width=25)
        self.kpi_spec_indicator_cb.pack(side="left", padx=5)
        self.kpi_spec_indicator_cb.bind("<<ComboboxSelected>>", self.on_kpi_spec_indicator_selected)

        attr_frame = ttk.Frame(add_kpi_frame_outer)
        attr_frame.pack(fill="x", pady=5)
        ttk.Label(attr_frame, text="Descrizione:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.kpi_spec_desc_var = tk.StringVar()
        ttk.Entry(attr_frame, textvariable=self.kpi_spec_desc_var, width=40).grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        attr_frame.columnconfigure(1, weight=1)

        ttk.Label(attr_frame, text="Tipo Calcolo:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.kpi_spec_type_var = tk.StringVar(value=KPI_CALC_TYPE_OPTIONS[0])
        self.kpi_spec_type_cb = ttk.Combobox(attr_frame, textvariable=self.kpi_spec_type_var, values=KPI_CALC_TYPE_OPTIONS, state="readonly")
        self.kpi_spec_type_cb.grid(row=1, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(attr_frame, text="Unità Misura:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.kpi_spec_unit_var = tk.StringVar()
        ttk.Entry(attr_frame, textvariable=self.kpi_spec_unit_var, width=40).grid(row=2, column=1, padx=5, pady=2, sticky="ew")

        self.kpi_spec_visible_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(attr_frame, text="Visibile per Target", variable=self.kpi_spec_visible_var).grid(row=3, column=1, sticky="w", padx=5, pady=2)

        kpi_spec_btn_frame_outer = ttk.Frame(add_kpi_frame_outer)
        kpi_spec_btn_frame_outer.pack(pady=10)
        kpi_spec_btn_frame = ttk.Frame(kpi_spec_btn_frame_outer)
        kpi_spec_btn_frame.pack()
        self.save_kpi_spec_btn = ttk.Button(kpi_spec_btn_frame, text="Aggiungi Specifica", command=self.save_kpi_specification, style="Accent.TButton")
        self.save_kpi_spec_btn.pack(side="left", padx=5)
        ttk.Button(kpi_spec_btn_frame, text="Pulisci Campi", command=self.clear_kpi_spec_fields_button_action).pack(side="left", padx=5)

        tree_frame = ttk.Frame(self)
        tree_frame.pack(expand=True, fill="both", pady=(10, 0), padx=5)
        self.kpi_specs_tree = ttk.Treeview(tree_frame, columns=("ID", "Gruppo", "Sottogruppo", "Indicatore", "Descrizione", "Tipo Calcolo", "Unità", "Visibile", "Template SG"), show="headings")
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
        tree_buttons_frame = ttk.Frame(self)
        tree_buttons_frame.pack(fill="x", pady=5)
        ttk.Button(
            tree_buttons_frame,
            text="Elimina Specifica Selezionata",
            command=self.delete_selected_kpi_spec,
        ).pack(side="left", padx=5)

    def refresh_display(self):
        self.refresh_tree()
        self.populate_kpi_spec_hier_combos()

    def on_kpi_spec_group_selected(self, event=None):
        if self._populating_kpi_spec_combos:
            return
        self._populate_kpi_spec_subgroups()

    def on_kpi_spec_subgroup_selected(self, event=None):
        if self._populating_kpi_spec_combos:
            return
        self._populate_kpi_spec_indicators()

    def on_kpi_spec_indicator_selected(self, event=None):
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
                            or KPI_CALC_TYPE_OPTIONS[0]
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
            self.kpi_spec_type_var.set(KPI_CALC_TYPE_OPTIONS[0])
            self.kpi_spec_unit_var.set("")
            self.kpi_spec_visible_var.set(True)
            return
        kpi_data_dict = dict(kpi_data_row_obj)
        self.kpi_spec_desc_var.set(kpi_data_dict.get("description", ""))
        self.kpi_spec_type_var.set(
            kpi_data_dict.get("calculation_type", KPI_CALC_TYPE_OPTIONS[0])
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
        self.kpi_spec_type_var.set(KPI_CALC_TYPE_OPTIONS[0])
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
                kpi_specs_manager.update_kpi_spec(
                    self.current_editing_kpi_id,
                    self.selected_indicator_id_for_spec,
                    desc,
                    calc_type,
                    unit,
                    visible,
                )
                messagebox.showinfo("Successo", "Specifica KPI aggiornata!")
            else:
                kpi_specs_manager.add_kpi_spec(
                    self.selected_indicator_id_for_spec, desc, calc_type, unit, visible
                )
                messagebox.showinfo(
                    "Successo", "Nuova specifica KPI aggiunta/aggiornata!"
                )
            self.app.refresh_all_data()
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
                kpi_indicators_manager.delete_kpi_indicator(actual_indicator_id_to_delete)
                messagebox.showinfo(
                    "Successo", "Specifica KPI e relativi dati eliminati."
                )
                self.app.refresh_all_data()
                self.clear_kpi_spec_fields_button_action()
            except Exception as e:
                messagebox.showerror(
                    "Errore Eliminazione",
                    f"Impossibile eliminare: {e}\n{traceback.format_exc()}",
                )

    def refresh_tree(self):
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
