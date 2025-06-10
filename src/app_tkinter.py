# app_tkinter.py

import tkinter as tk
from tkinter import ttk, messagebox
import database_manager as db  # Assicurati che sia nello stesso percorso
import json
import datetime
import calendar


class KpiApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestione Target KPI - Desktop")
        self.geometry("1300x800")

        style = ttk.Style(self)
        style.theme_use("clam")  # o 'alt', 'default', 'classic'
        style.configure(
            "Accent.TButton", foreground="white", background="#007bff"
        )  # Blu
        style.configure("Treeview.Heading", font=("Calibri", 10, "bold"))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)

        self.target_frame = ttk.Frame(self.notebook, padding="10")
        self.kpi_frame = ttk.Frame(self.notebook, padding="10")
        self.stabilimenti_frame = ttk.Frame(self.notebook, padding="10")
        self.results_frame = ttk.Frame(self.notebook, padding="10")

        self.notebook.add(self.target_frame, text="🎯 Inserimento Target")
        self.notebook.add(self.kpi_frame, text="⚙️ Gestione KPI")
        self.notebook.add(self.stabilimenti_frame, text="🏭 Gestione Stabilimenti")
        self.notebook.add(self.results_frame, text="📈 Visualizzazione Risultati")

        self.create_target_widgets()
        self.create_kpi_widgets()
        self.create_stabilimenti_widgets()
        self.create_results_widgets()

        self.refresh_kpi_tree()
        self.refresh_stabilimenti_tree()
        self.populate_target_comboboxes()  # Carica anche i KPI
        self.populate_results_comboboxes()

    # --- Scheda Gestione KPI ---
    def create_kpi_widgets(self):
        self.kpi_tree = ttk.Treeview(
            self.kpi_frame,
            columns=(
                "ID",
                "Nome",
                "Descrizione",
                "Tipo Calcolo",
                "Unità di Misura",
                "Visibile",
            ),
            show="headings",
        )
        self.kpi_tree.heading("ID", text="ID")
        self.kpi_tree.heading("Nome", text="Nome")
        self.kpi_tree.heading("Descrizione", text="Descrizione")
        self.kpi_tree.heading("Tipo Calcolo", text="Tipo Calcolo")
        self.kpi_tree.heading("Unità di Misura", text="Unità Misura")
        self.kpi_tree.heading("Visibile", text="Visibile")
        self.kpi_tree.column("ID", width=30, anchor="center")
        self.kpi_tree.column("Nome", width=180)
        self.kpi_tree.column("Descrizione", width=250)
        self.kpi_tree.column("Tipo Calcolo", width=100, anchor="center")
        self.kpi_tree.column("Unità di Misura", width=100, anchor="center")
        self.kpi_tree.column("Visibile", width=70, anchor="center")
        self.kpi_tree.pack(expand=True, fill="both")
        btn_frame = ttk.Frame(self.kpi_frame)
        btn_frame.pack(fill="x", pady=5)
        ttk.Button(btn_frame, text="Aggiungi KPI", command=self.add_kpi_window).pack(
            side="left", padx=5
        )
        ttk.Button(
            btn_frame, text="Modifica Selezionato", command=self.edit_kpi_window
        ).pack(side="left", padx=5)
        ttk.Button(
            btn_frame, text="Aggiorna Lista", command=self.refresh_kpi_tree
        ).pack(side="left", padx=5)

    def refresh_kpi_tree(self):
        for i in self.kpi_tree.get_children():
            self.kpi_tree.delete(i)
        for kpi_row in db.get_kpis():  # kpi_row è una Row di sqlite3
            self.kpi_tree.insert(
                "",
                "end",
                values=(
                    kpi_row["id"],
                    kpi_row["name"],
                    kpi_row["description"],
                    kpi_row["calculation_type"],
                    kpi_row["unit_of_measure"] if kpi_row["unit_of_measure"] else "",
                    "Sì" if kpi_row["visible"] else "No",
                ),
            )

    def add_kpi_window(self):
        self.kpi_editor_window(None)

    def edit_kpi_window(self):
        selected_item = self.kpi_tree.focus()
        if not selected_item:
            messagebox.showwarning("Attenzione", "Seleziona un KPI da modificare.")
            return
        self.kpi_editor_window(self.kpi_tree.item(selected_item)["values"])

    def kpi_editor_window(self, kpi_data_tuple=None):
        win = tk.Toplevel(self)
        win.title("Editor KPI")
        win.transient(self)
        win.grab_set()
        k_data = {}  # Converti tupla in dizionario per chiarezza
        if kpi_data_tuple:
            fields = [
                "id",
                "name",
                "description",
                "calculation_type",
                "unit_of_measure",
                "visible_str",
            ]
            k_data = dict(zip(fields, kpi_data_tuple))

        ttk.Label(win, text="Nome:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        name_var = tk.StringVar(value=k_data.get("name", ""))
        ttk.Entry(win, textvariable=name_var, width=40).grid(
            row=0, column=1, padx=10, pady=5
        )
        ttk.Label(win, text="Descrizione:").grid(
            row=1, column=0, padx=10, pady=5, sticky="w"
        )
        desc_var = tk.StringVar(value=k_data.get("description", ""))
        ttk.Entry(win, textvariable=desc_var, width=40).grid(
            row=1, column=1, padx=10, pady=5
        )
        ttk.Label(win, text="Tipo Calcolo:").grid(
            row=2, column=0, padx=10, pady=5, sticky="w"
        )
        type_var = tk.StringVar(value=k_data.get("calculation_type", "Incrementale"))
        ttk.Combobox(
            win,
            textvariable=type_var,
            values=["Incrementale", "Media"],
            state="readonly",
        ).grid(row=2, column=1, padx=10, pady=5, sticky="ew")
        ttk.Label(win, text="Unità di Misura:").grid(
            row=3, column=0, padx=10, pady=5, sticky="w"
        )
        unit_var = tk.StringVar(value=k_data.get("unit_of_measure", ""))
        ttk.Entry(win, textvariable=unit_var, width=40).grid(
            row=3, column=1, padx=10, pady=5
        )
        visible_var = tk.BooleanVar(value=(k_data.get("visible_str", "Sì") == "Sì"))
        ttk.Checkbutton(win, text="Visibile", variable=visible_var).grid(
            row=4, column=1, padx=10, pady=5, sticky="w"
        )

        def save():
            if not name_var.get():
                messagebox.showerror(
                    "Errore", "Il nome KPI è obbligatorio.", parent=win
                )
                return
            try:
                if k_data:  # Modifica
                    db.update_kpi(
                        k_data["id"],
                        name_var.get(),
                        desc_var.get(),
                        type_var.get(),
                        unit_var.get(),
                        visible_var.get(),
                    )
                else:  # Aggiunta
                    db.add_kpi(
                        name_var.get(),
                        desc_var.get(),
                        type_var.get(),
                        unit_var.get(),
                        visible_var.get(),
                    )
                self.refresh_kpi_tree()
                self.populate_target_comboboxes()  # Aggiorna lista KPI per i target
                self.populate_results_comboboxes()  # Aggiorna lista KPI per i risultati
                win.destroy()
            except Exception as e:
                messagebox.showerror("Errore", f"Salvataggio fallito: {e}", parent=win)

        ttk.Button(win, text="Salva", command=save, style="Accent.TButton").grid(
            row=5, columnspan=2, padx=10, pady=10
        )

    # --- Scheda Gestione Stabilimenti ---
    def create_stabilimenti_widgets(self):
        self.stabilimenti_tree = ttk.Treeview(
            self.stabilimenti_frame, columns=("ID", "Nome", "Visibile"), show="headings"
        )
        self.stabilimenti_tree.heading("ID", text="ID")
        self.stabilimenti_tree.heading("Nome", text="Nome")
        self.stabilimenti_tree.heading("Visibile", text="Visibile")
        self.stabilimenti_tree.column("ID", width=50, anchor="center")
        self.stabilimenti_tree.column("Visibile", width=80, anchor="center")
        self.stabilimenti_tree.pack(expand=True, fill="both")
        btn_frame = ttk.Frame(self.stabilimenti_frame)
        btn_frame.pack(fill="x", pady=5)
        ttk.Button(
            btn_frame,
            text="Aggiungi Stabilimento",
            command=self.add_stabilimento_window,
        ).pack(side="left", padx=5)
        ttk.Button(
            btn_frame,
            text="Modifica Selezionato",
            command=self.edit_stabilimento_window,
        ).pack(side="left", padx=5)
        ttk.Button(
            btn_frame, text="Aggiorna Lista", command=self.refresh_stabilimenti_tree
        ).pack(side="left", padx=5)

    def refresh_stabilimenti_tree(self):
        for i in self.stabilimenti_tree.get_children():
            self.stabilimenti_tree.delete(i)
        for s_row in db.get_stabilimenti():
            self.stabilimenti_tree.insert(
                "",
                "end",
                values=(s_row["id"], s_row["name"], "Sì" if s_row["visible"] else "No"),
            )

    def add_stabilimento_window(self):
        self.stabilimento_editor_window(None)

    def edit_stabilimento_window(self):
        selected_item = self.stabilimenti_tree.focus()
        if not selected_item:
            messagebox.showwarning("Attenzione", "Seleziona uno stabilimento.")
            return
        self.stabilimento_editor_window(
            self.stabilimenti_tree.item(selected_item)["values"]
        )

    def stabilimento_editor_window(self, s_data_tuple=None):
        win = tk.Toplevel(self)
        win.title("Editor Stabilimento")
        win.transient(self)
        win.grab_set()
        s_name = s_data_tuple[1] if s_data_tuple else ""
        s_visible_str = s_data_tuple[2] if s_data_tuple else "Sì"

        ttk.Label(win, text="Nome:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        name_var = tk.StringVar(value=s_name)
        ttk.Entry(win, textvariable=name_var, width=40).grid(
            row=0, column=1, padx=10, pady=5
        )
        visible_var = tk.BooleanVar(value=(s_visible_str == "Sì"))
        ttk.Checkbutton(win, text="Visibile", variable=visible_var).grid(
            row=1, column=1, padx=10, pady=5, sticky="w"
        )

        def save():
            if not name_var.get():
                messagebox.showerror("Errore", "Il nome è obbligatorio.", parent=win)
                return
            try:
                if s_data_tuple:  # Modifica
                    db.update_stabilimento(
                        s_data_tuple[0], name_var.get(), visible_var.get()
                    )
                else:  # Aggiunta
                    db.add_stabilimento(name_var.get(), visible_var.get())
                self.refresh_stabilimenti_tree()
                self.populate_target_comboboxes()  # Aggiorna combobox stabilimenti
                self.populate_results_comboboxes()
                win.destroy()
            except Exception as e:
                messagebox.showerror("Errore", f"Salvataggio fallito: {e}", parent=win)

        ttk.Button(win, text="Salva", command=save, style="Accent.TButton").grid(
            row=2, columnspan=2, pady=10
        )

    # --- Scheda Inserimento Target ---
    def create_target_widgets(self):
        filter_frame = ttk.Frame(self.target_frame)
        filter_frame.pack(fill="x", pady=5)
        ttk.Label(filter_frame, text="Anno:").pack(side="left", padx=(0, 5))
        self.year_var = tk.StringVar(value=str(datetime.datetime.now().year))
        self.year_spinbox = ttk.Spinbox(
            filter_frame,
            from_=2020,
            to=2050,
            textvariable=self.year_var,
            width=7,
            command=self.load_kpi_targets_for_entry,
        )
        self.year_spinbox.pack(side="left", padx=5)
        ttk.Label(filter_frame, text="Stabilimento:").pack(side="left", padx=(10, 5))
        self.stabilimento_target_var = tk.StringVar()
        self.stabilimento_target_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.stabilimento_target_var,
            state="readonly",
            width=25,
        )
        self.stabilimento_target_combo.pack(side="left", padx=5)
        self.stabilimento_target_combo.bind(
            "<<ComboboxSelected>>", self.load_kpi_targets_for_entry
        )
        ttk.Button(
            filter_frame,
            text="Carica/Aggiorna KPI",
            command=self.load_kpi_targets_for_entry,
        ).pack(side="left", padx=10)

        canvas_frame = ttk.Frame(self.target_frame)
        canvas_frame.pack(fill="both", expand=True, pady=10)
        self.canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(
            canvas_frame, orient="vertical", command=self.canvas.yview
        )
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Button(
            self.target_frame,
            text="SALVA TUTTI I TARGET",
            command=self.save_all_targets,
            style="Accent.TButton",
        ).pack(pady=10)
        self.kpi_target_widgets = {}  # Per memorizzare i widget di input per ogni KPI

    def populate_target_comboboxes(self):
        stabilimenti_visibili = db.get_stabilimenti(only_visible=True)
        self.stabilimenti_target_data_map = {
            s["name"]: s["id"] for s in stabilimenti_visibili
        }
        self.stabilimento_target_combo["values"] = list(
            self.stabilimenti_target_data_map.keys()
        )
        if self.stabilimenti_target_data_map:
            self.stabilimento_target_combo.current(0)
        self.load_kpi_targets_for_entry()  # Carica i KPI per il primo stabilimento

    def load_kpi_targets_for_entry(self, event=None):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.kpi_target_widgets.clear()

        if not self.stabilimento_target_var.get() or not self.year_var.get():
            ttk.Label(
                self.scrollable_frame, text="Seleziona anno e stabilimento."
            ).pack()
            return

        try:
            year = int(self.year_var.get())
            stabilimento_id = self.stabilimenti_target_data_map[
                self.stabilimento_target_var.get()
            ]
        except (ValueError, KeyError):
            ttk.Label(
                self.scrollable_frame, text="Anno o stabilimento non valido."
            ).pack()
            return

        kpis_visibili = db.get_kpis(only_visible=True)
        if not kpis_visibili:
            ttk.Label(
                self.scrollable_frame, text="Nessun KPI visibile definito."
            ).pack()
            return

        for kpi_row in kpis_visibili:
            kpi_id, name, kpi_unit, calc_type = (
                kpi_row["id"],
                kpi_row["name"],
                kpi_row["unit_of_measure"],
                kpi_row["calculation_type"],
            )
            frame_label = f"{name}"
            if kpi_unit:
                frame_label += f" ({kpi_unit})"
            kpi_entry_frame = ttk.LabelFrame(
                self.scrollable_frame, text=frame_label, padding=10
            )
            kpi_entry_frame.pack(fill="x", expand=True, padx=5, pady=5)

            existing_target_row = db.get_annual_target(year, stabilimento_id, kpi_id)
            default_target_val = (
                existing_target_row["annual_target"] if existing_target_row else 0.0
            )
            default_logic = (
                existing_target_row["repartition_logic"]
                if existing_target_row
                else "Mese"
            )
            default_repartition_json = (
                existing_target_row["repartition_values"]
                if existing_target_row
                else "{}"
            )
            try:
                default_repartition_map = json.loads(default_repartition_json)
            except:
                default_repartition_map = {}

            target_var = tk.DoubleVar(value=default_target_val)
            logic_var = tk.StringVar(
                value=default_logic
            )  # Rilevante per KPI Incrementali
            repartition_input_vars = {}

            top_row_frame = ttk.Frame(kpi_entry_frame)
            top_row_frame.pack(fill="x")
            ttk.Label(top_row_frame, text="Target Annuale:").pack(side="left")
            ttk.Entry(top_row_frame, textvariable=target_var, width=12).pack(
                side="left", padx=5
            )

            if calc_type == "Incrementale":
                ttk.Label(top_row_frame, text="Rip. Utente:").pack(
                    side="left", padx=(10, 0)
                )
                ttk.Radiobutton(
                    top_row_frame,
                    text="Mese",
                    variable=logic_var,
                    value="Mese",
                    command=lambda f=kpi_entry_frame, lv=logic_var, rv=repartition_input_vars, dr=default_repartition_map, kid=kpi_id: self._create_repartition_fields_tk(
                        f, lv, rv, dr, kid, "Incrementale"
                    ),
                ).pack(side="left")
                ttk.Radiobutton(
                    top_row_frame,
                    text="Trimestre",
                    variable=logic_var,
                    value="Trimestre",
                    command=lambda f=kpi_entry_frame, lv=logic_var, rv=repartition_input_vars, dr=default_repartition_map, kid=kpi_id: self._create_repartition_fields_tk(
                        f, lv, rv, dr, kid, "Incrementale"
                    ),
                ).pack(side="left")
            else:  # Media
                ttk.Label(
                    top_row_frame,
                    text="(Ripartizione 'generosa' automatica per KPI Media)",
                ).pack(side="left", padx=(10, 0))
                # Per Media, logic_var e repartition_input_vars non sono usati attivamente per il calcolo, ma li inizializziamo
                logic_var.set("Mese")  # Default non critico
                default_repartition_map = {
                    calendar.month_name[i]: round(100 / 12, 2) for i in range(1, 13)
                }

            self.kpi_target_widgets[kpi_id] = {
                "target_var": target_var,
                "logic_var": logic_var,
                "repartition_vars": repartition_input_vars,
                "calc_type": calc_type,
            }
            self._create_repartition_fields_tk(
                kpi_entry_frame,
                logic_var,
                repartition_input_vars,
                default_repartition_map,
                kpi_id,
                calc_type,
            )

    def _create_repartition_fields_tk(
        self,
        parent_frame,
        logic_var,
        repartition_vars_dict,
        default_map,
        kpi_id_tag,
        kpi_calc_type,
    ):
        # Rimuovi vecchi campi di ripartizione (quelli con il tag specifico)
        for widget in parent_frame.winfo_children():
            if (
                hasattr(widget, "_kpi_repartition_field_tag")
                and widget._kpi_repartition_field_tag == kpi_id_tag
            ):
                widget.destroy()

        repartition_vars_dict.clear()  # Svuota il dizionario per i nuovi var

        if (
            kpi_calc_type != "Incrementale"
        ):  # Per "Media", non mostriamo i campi % utente
            return

        current_logic = logic_var.get()
        rep_frame = ttk.Frame(parent_frame)
        rep_frame._kpi_repartition_field_tag = (
            kpi_id_tag  # Tagga il frame per la rimozione
        )
        rep_frame.pack(fill="x", pady=5)

        ttk.Label(rep_frame, text=f"Percentuali per {current_logic}:").pack(
            side="top", anchor="w", pady=(0, 5)
        )

        fields_per_row = 6 if current_logic == "Mese" else 4
        current_row_frame = None

        if current_logic == "Mese":
            items = [calendar.month_name[i] for i in range(1, 13)]
            default_val = 100.0 / 12
        else:  # Trimestre
            items = ["Q1", "Q2", "Q3", "Q4"]
            default_val = 25.0

        for i, item_name in enumerate(items):
            if i % fields_per_row == 0:
                current_row_frame = ttk.Frame(rep_frame)
                current_row_frame.pack(fill="x")

            var = tk.DoubleVar(value=round(default_map.get(item_name, default_val), 2))
            repartition_vars_dict[item_name] = var
            ttk.Label(
                current_row_frame,
                text=f"{item_name[:3] if current_logic=='Mese' else item_name}%:",
            ).pack(side="left", padx=(0, 2))
            ttk.Entry(current_row_frame, textvariable=var, width=7).pack(
                side="left", padx=(0, 10)
            )

    def save_all_targets(self):
        try:
            year = int(self.year_var.get())
            stabilimento_id = self.stabilimenti_target_data_map[
                self.stabilimento_target_var.get()
            ]
        except (ValueError, KeyError):
            messagebox.showerror("Errore", "Seleziona anno e stabilimento validi.")
            return

        targets_to_save_db = {}
        all_inputs_valid = True
        for kpi_id, widgets in self.kpi_target_widgets.items():
            annual_target = widgets["target_var"].get()
            calc_type = widgets["calc_type"]

            # Per KPI Media, la logica di ripartizione utente è meno critica per il calcolo, ma la salviamo
            # Per KPI Incrementale, è fondamentale
            repartition_logic = widgets["logic_var"].get()
            repartition_values = {
                key: var.get() for key, var in widgets["repartition_vars"].items()
            }

            if (
                calc_type == "Incrementale" and annual_target > 0
            ):  # Validare percentuali solo per Incrementale con target
                total_percentage = sum(repartition_values.values())
                if not (99.9 <= total_percentage <= 100.1):
                    kpi_info = db.get_kpi_by_id(kpi_id)
                    messagebox.showerror(
                        "Errore Validazione",
                        f"Per KPI '{kpi_info['name']}', la somma delle percentuali è {total_percentage:.2f}%. Deve essere ~100%.",
                    )
                    all_inputs_valid = False
                    break

            # Per KPI Media, se repartition_values è vuoto (perché non sono stati creati campi), popolarlo con default
            if calc_type == "Media" and not repartition_values:
                repartition_values = {
                    calendar.month_name[i]: round(100 / 12, 2) for i in range(1, 13)
                }

            targets_to_save_db[kpi_id] = {
                "annual_target": annual_target,
                "repartition_logic": repartition_logic,
                "repartition_values": repartition_values,
            }

        if not all_inputs_valid:
            return
        if not targets_to_save_db:
            messagebox.showwarning("Attenzione", "Nessun target da salvare.")
            return

        try:
            db.save_annual_targets(year, stabilimento_id, targets_to_save_db)
            messagebox.showinfo(
                "Successo", "Target salvati e ripartizioni ricalcolate!"
            )
        except Exception as e:
            messagebox.showerror("Errore Salvataggio", f"Errore: {e}")

    # --- Scheda Visualizzazione Risultati ---
    def create_results_widgets(self):
        filter_frame = ttk.Frame(self.results_frame)
        filter_frame.pack(fill="x", pady=5)
        ttk.Label(filter_frame, text="Anno:").pack(side="left")
        self.res_year_var = tk.StringVar(value=str(datetime.datetime.now().year))
        ttk.Spinbox(
            filter_frame, from_=2020, to=2050, textvariable=self.res_year_var, width=7
        ).pack(side="left", padx=5)
        ttk.Label(filter_frame, text="Stabilimento:").pack(side="left", padx=(10, 5))
        self.res_stabilimento_var = tk.StringVar()
        self.res_stabilimento_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.res_stabilimento_var,
            state="readonly",
            width=20,
        )
        self.res_stabilimento_combo.pack(side="left", padx=5)
        ttk.Label(filter_frame, text="KPI:").pack(side="left", padx=(10, 5))
        self.res_kpi_var = tk.StringVar()
        self.res_kpi_combo = ttk.Combobox(
            filter_frame, textvariable=self.res_kpi_var, state="readonly", width=30
        )
        self.res_kpi_combo.pack(side="left", padx=5)
        ttk.Label(filter_frame, text="Periodicità:").pack(side="left", padx=(10, 5))
        self.res_period_var = tk.StringVar(value="Mese")
        self.res_period_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.res_period_var,
            state="readonly",
            values=["Giorno", "Settimana", "Mese", "Trimestre"],
            width=10,
        )
        self.res_period_combo.current(2)
        self.res_period_combo.pack(side="left", padx=5)
        ttk.Button(
            filter_frame,
            text="Mostra Dati",
            command=self.show_results,
            style="Accent.TButton",
        ).pack(side="left", padx=10)

        self.results_tree = ttk.Treeview(
            self.results_frame, columns=("Periodo", "Target"), show="headings"
        )
        self.results_tree.heading("Periodo", text="Periodo")
        self.results_tree.heading("Target", text="Valore Target")
        self.results_tree.column("Periodo", width=200)
        self.results_tree.column("Target", width=150, anchor="e")
        self.results_tree.pack(fill="both", expand=True, pady=10)

        self.summary_label_var = tk.StringVar()
        ttk.Label(
            self.results_frame,
            textvariable=self.summary_label_var,
            font=("Calibri", 10, "bold"),
        ).pack(pady=5, anchor="e", padx=10)

    def populate_results_comboboxes(self):
        stabilimenti = db.get_stabilimenti()  # Tutti per visualizzazione
        self.res_stabilimenti_data_map = {s["name"]: s["id"] for s in stabilimenti}
        self.res_stabilimento_combo["values"] = list(
            self.res_stabilimenti_data_map.keys()
        )
        if self.res_stabilimenti_data_map:
            self.res_stabilimento_combo.current(0)

        kpis = db.get_kpis()  # Tutti
        self.res_kpi_data_map = {
            k["name"]: {
                "id": k["id"],
                "type": k["calculation_type"],
                "unit": k["unit_of_measure"],
            }
            for k in kpis
        }
        self.res_kpi_combo["values"] = list(self.res_kpi_data_map.keys())
        if self.res_kpi_data_map:
            self.res_kpi_combo.current(0)

    def show_results(self):
        for i in self.results_tree.get_children():
            self.results_tree.delete(i)
        self.summary_label_var.set("")
        try:
            year = int(self.res_year_var.get())
            stabilimento_name = self.res_stabilimento_var.get()
            kpi_name = self.res_kpi_var.get()
            period_type = self.res_period_var.get()

            if not stabilimento_name or not kpi_name:
                messagebox.showwarning(
                    "Selezione incompleta", "Seleziona stabilimento e KPI."
                )
                return

            stabilimento_id = self.res_stabilimenti_data_map[stabilimento_name]
            kpi_info = self.res_kpi_data_map[kpi_name]
            kpi_id = kpi_info["id"]
            kpi_calc_type = kpi_info["type"]
            kpi_unit = kpi_info["unit"] if kpi_info["unit"] else ""

            data_ripartiti = db.get_ripartiti_data(
                year, stabilimento_id, kpi_id, period_type
            )
            if not data_ripartiti:
                messagebox.showinfo("Info", "Nessun dato trovato per questa selezione.")
                return

            total_sum = 0
            count = 0
            for row in data_ripartiti:  # row è una Row di sqlite3
                self.results_tree.insert(
                    "", "end", values=(row["Periodo"], f"{row['Target']:.2f}")
                )
                total_sum += row["Target"]
                count += 1

            summary_text = ""
            if count > 0:
                if kpi_calc_type == "Incrementale":
                    summary_text = (
                        f"Totale ({period_type}): {total_sum:,.2f} {kpi_unit}"
                    )
                else:  # Media
                    avg_val = total_sum / count
                    summary_text = f"Media ({period_type}): {avg_val:,.2f} {kpi_unit}"
            self.summary_label_var.set(summary_text)

        except (KeyError, ValueError) as e:
            messagebox.showerror(
                "Errore Selezione", f"Errore nei filtri selezionati: {e}"
            )
        except Exception as e:
            messagebox.showerror(
                "Errore Caricamento Dati", f"Impossibile caricare i dati: {e}"
            )


if __name__ == "__main__":
    db.setup_databases()  # Assicurati che i DB siano pronti
    app = KpiApp()
    app.mainloop()
