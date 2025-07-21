import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import traceback

from kpi_management import templates as kpi_templates_manager
import data_retriever as db_retriever
from ..dialogs.template_definition_editor import TemplateDefinitionEditorDialog

class KpiTemplatesTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.current_templates_map = {}
        self.current_template_definitions_map = {}
        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True)

        template_list_frame = ttk.LabelFrame(main_frame, text="Template Indicatori KPI", padding=10)
        template_list_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.templates_listbox = tk.Listbox(template_list_frame, exportselection=False, height=15, width=30)
        self.templates_listbox.pack(fill="both", expand=True, pady=(0, 5))
        self.templates_listbox.bind("<<ListboxSelect>>", self.on_template_select)

        template_btn_frame = ttk.Frame(template_list_frame)
        template_btn_frame.pack(fill="x")
        ttk.Button(template_btn_frame, text="Nuovo Tpl", command=self.add_new_kpi_template, width=10, style="Accent.TButton").pack(side="left", padx=2)
        self.edit_template_btn = ttk.Button(template_btn_frame, text="Modifica Tpl", command=self.edit_selected_kpi_template, state="disabled", width=11)
        self.edit_template_btn.pack(side="left", padx=2)
        self.delete_template_btn = ttk.Button(template_btn_frame, text="Elimina Tpl", command=self.delete_selected_kpi_template, state="disabled", width=11)
        self.delete_template_btn.pack(side="left", padx=2)

        definitions_frame = ttk.LabelFrame(main_frame, text="Definizioni nel Template", padding=10)
        definitions_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.template_definitions_tree = ttk.Treeview(
            definitions_frame,
            columns=("ID", "Nome Indicatore", "Tipo Calcolo", "Unità", "Visibile", "Descrizione"),
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
            self.template_definitions_tree.column(col, width=width, anchor="center" if col in ["ID", "Visibile"] else "w", stretch=(col in ["Descrizione", "Nome Indicatore"]))
        
        self.template_definitions_tree.pack(fill="both", expand=True, pady=(0, 5))
        self.template_definitions_tree.bind("<<TreeviewSelect>>", self.on_template_definition_select)

        definition_btn_frame = ttk.Frame(definitions_frame)
        definition_btn_frame.pack(fill="x")
        self.add_definition_btn = ttk.Button(definition_btn_frame, text="Aggiungi Def.", command=self.add_new_template_definition, state="disabled", width=12, style="Accent.TButton")
        self.add_definition_btn.pack(side="left", padx=2)
        self.edit_definition_btn = ttk.Button(definition_btn_frame, text="Modifica Def.", command=self.edit_selected_template_definition, state="disabled", width=12)
        self.edit_definition_btn.pack(side="left", padx=2)
        self.remove_definition_btn = ttk.Button(definition_btn_frame, text="Rimuovi Def.", command=self.remove_selected_template_definition, state="disabled", width=12)
        self.remove_definition_btn.pack(side="left", padx=2)

    def refresh_display(self, pre_selected_template_name=None):
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
            template_name = self.templates_listbox.get(self.templates_listbox.curselection()[0])
            template_id = self.current_templates_map.get(template_name)
            if template_id:
                for defi in db_retriever.get_template_defined_indicators(template_id):
                    vis_str = "Sì" if defi["default_visible"] else "No"
                    iid = self.template_definitions_tree.insert(
                        "", "end",
                        values=(
                            defi["id"], defi["indicator_name_in_template"], 
                            defi["default_calculation_type"], defi["default_unit_of_measure"] or "",
                            vis_str, defi["default_description"] or ""
                        )
                    )
                    self.current_template_definitions_map[iid] = defi["id"]
        self.on_template_definition_select()

    def on_template_definition_select(self, event=None):
        buttons_state = "normal" if self.template_definitions_tree.selection() else "disabled"
        self.edit_definition_btn.config(state=buttons_state)
        self.remove_definition_btn.config(state=buttons_state)

    def add_new_kpi_template(self):
        name = simpledialog.askstring("Nuovo Template", "Nome Template:", parent=self)
        if name:
            desc = simpledialog.askstring("Nuovo Template", "Descrizione (opzionale):", parent=self) or ""
            try:
                kpi_templates_manager.add_kpi_indicator_template(name, desc)
                self.refresh_display(pre_selected_template_name=name)
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile aggiungere template: {e}")

    def edit_selected_kpi_template(self):
        if not self.templates_listbox.curselection(): return
        old_name = self.templates_listbox.get(self.templates_listbox.curselection()[0])
        template_id = self.current_templates_map.get(old_name)
        template_data = db_retriever.get_kpi_indicator_template_by_id(template_id)
        if not template_data: return

        new_name = simpledialog.askstring("Modifica Template", "Nuovo nome:", initialvalue=old_name, parent=self)
        if new_name:
            new_desc = simpledialog.askstring("Modifica Template", "Nuova descrizione:", initialvalue=template_data["description"], parent=self)
            new_desc = new_desc if new_desc is not None else template_data["description"]
            if new_name != old_name or new_desc != template_data["description"]:
                try:
                    kpi_templates_manager.update_kpi_indicator_template(template_id, new_name, new_desc)
                    self.refresh_display(pre_selected_template_name=new_name)
                    self.app.refresh_all_data()
                except Exception as e:
                    messagebox.showerror("Errore", f"Impossibile modificare template: {e}")

    def delete_selected_kpi_template(self):
        if not self.templates_listbox.curselection(): return
        name = self.templates_listbox.get(self.templates_listbox.curselection()[0])
        template_id = self.current_templates_map.get(name)
        if messagebox.askyesno("Conferma", f"Eliminare template '{name}'?\nSottogruppi collegati verranno scollegati e i loro indicatori (da questo template) rimossi."):
            try:
                kpi_templates_manager.delete_kpi_indicator_template(template_id)
                self.refresh_display()
                self.app.refresh_all_data()
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile eliminare template: {e}\n{traceback.format_exc()}")

    def add_new_template_definition(self):
        if not self.templates_listbox.curselection(): return
        template_id = self.current_templates_map.get(self.templates_listbox.get(self.templates_listbox.curselection()[0]))
        dialog = TemplateDefinitionEditorDialog(self, title="Nuova Definizione Indicatore", template_id_context=template_id)
        if dialog.result_data:
            data = dialog.result_data
            try:
                kpi_templates_manager.add_indicator_definition_to_template(template_id, data["indicator_name_in_template"], data["default_calculation_type"], data["default_unit_of_measure"], data["default_visible"], data["default_description"])
                self.on_template_select()
                self.app.refresh_all_data()
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile aggiungere definizione: {e}\n{traceback.format_exc()}")

    def edit_selected_template_definition(self):
        if not self.template_definitions_tree.focus() or not self.templates_listbox.curselection(): return
        template_id = self.current_templates_map.get(self.templates_listbox.get(self.templates_listbox.curselection()[0]))
        definition_id = self.current_template_definitions_map.get(self.template_definitions_tree.focus())
        current_def_data = db_retriever.get_template_indicator_definition_by_id(definition_id)
        if not current_def_data: return

        dialog = TemplateDefinitionEditorDialog(self, title="Modifica Definizione Indicatore", template_id_context=template_id, initial_data=current_def_data)
        if dialog.result_data:
            data = dialog.result_data
            try:
                kpi_templates_manager.update_indicator_definition_in_template(definition_id, template_id, data["indicator_name_in_template"], data["default_calculation_type"], data["default_unit_of_measure"], data["default_visible"], data["default_description"])
                self.on_template_select()
                self.app.refresh_all_data()
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile modificare definizione: {e}\n{traceback.format_exc()}")

    def remove_selected_template_definition(self):
        if not self.template_definitions_tree.focus(): return
        definition_id = self.current_template_definitions_map.get(self.template_definitions_tree.focus())
        def_name = self.template_definitions_tree.item(self.template_definitions_tree.focus(), "values")[1]
        if messagebox.askyesno("Conferma", f"Rimuovere definizione '{def_name}' dal template?\nQuesto rimuoverà l'indicatore e i dati dai sottogruppi collegati."):
            try:
                kpi_templates_manager.remove_indicator_definition_from_template(definition_id)
                self.on_template_select()
                self.app.refresh_all_data()
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile rimuovere definizione: {e}\n{traceback.format_exc()}")