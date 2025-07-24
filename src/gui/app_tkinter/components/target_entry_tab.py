import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import json

from target_management import annual as annual_targets_manager
import data_retriever as db_retriever
from ...shared.helpers import get_kpi_display_name
from ..dialogs.formula_inputs import FormulaInputsDialog

class TargetEntryTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._populating_target_kpi_entries = False
        self.kpi_target_entry_widgets = {}
        self._master_sub_update_active = False
        self.target1_display_name = self.app.settings.get('display_names', {}).get('target1', 'Target 1')
        self.target2_display_name = self.app.settings.get('display_names', {}).get('target2', 'Target 2')
        self.create_widgets()

    def on_tab_selected(self):
        self.populate_filters()

    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self)
        main_frame.pack(fill='both', expand=True)

        # Top filter frame
        filter_frame_outer = ttk.Frame(main_frame)
        filter_frame_outer.pack(fill='x', padx=10, pady=5)

        # Year filter
        ttk.Label(filter_frame_outer, text="Anno:").pack(side='left', padx=(0, 5))
        self.year_cb_target = ttk.Combobox(filter_frame_outer, state='readonly')
        self.year_cb_target.pack(side='left')
        self.year_cb_target.bind('<<ComboboxSelected>>', self.load_kpi_targets_for_entry_target)

        # Stabilimento filter
        ttk.Label(filter_frame_outer, text="Stabilimento:").pack(side='left', padx=(10, 5))
        self.stabilimento_cb_target = ttk.Combobox(filter_frame_outer, state='readonly')
        self.stabilimento_cb_target.pack(side='left', fill='x', expand=True)
        self.stabilimento_cb_target.bind('<<ComboboxSelected>>', self.load_kpi_targets_for_entry_target)

        # Canvas for scrollable content
        self.canvas_target = tk.Canvas(main_frame)
        self.canvas_target.pack(side='left', fill='both', expand=True)

        # Scrollbar
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=self.canvas_target.yview)
        scrollbar.pack(side='right', fill='y')

        # Scrollable frame
        self.scrollable_frame_target = ttk.Frame(self.canvas_target)
        self.canvas_target.create_window((0, 0), window=self.scrollable_frame_target, anchor='nw')
        self.canvas_target.configure(yscrollcommand=scrollbar.set)

        self.scrollable_frame_target.bind('<Configure>', lambda e: canvas_target.configure(scrollregion=canvas_target.bbox('all')))

        # Save button
        save_button = ttk.Button(self, text="SALVA TUTTI I TARGET", command=self.save_all_targets_entry)
        save_button.pack(pady=10)

    def populate_filters(self):
        # Populate year
        current_year = datetime.datetime.now().year
        self.year_cb_target['values'] = [str(y) for y in range(current_year - 5, current_year + 5)]
        self.year_cb_target.set(current_year)

        # Populate stabilimenti
        self.stabilimenti = db_retriever.get_all_stabilimenti(visible_only=True)
        self.stabilimento_cb_target['values'] = [s['name'] for s in self.stabilimenti]
        if self.stabilimenti:
            self.stabilimento_cb_target.current(0)

        self.load_kpi_targets_for_entry_target()

    def load_kpi_targets_for_entry_target(self, event=None):
        # Clear existing widgets
        for widget in self.scrollable_frame_target.winfo_children():
            widget.destroy()
        self.kpi_target_entry_widgets.clear()

        # Get selected filters
        year = self.year_cb_target.get()
        stabilimento_name = self.stabilimento_cb_target.get()
        if not year or not stabilimento_name:
            return

        # Recreate the scrollable frame to ensure it's clean
        if hasattr(self, 'scrollable_frame_target'):
            self.scrollable_frame_target.destroy()
        self.scrollable_frame_target = ttk.Frame(self.canvas_target)
        self.canvas_target.create_window((0, 0), window=self.scrollable_frame_target, anchor='nw')
        self.scrollable_frame_target.bind('<Configure>', lambda e: self.canvas_target.configure(scrollregion=self.canvas_target.bbox('all')))

        stabilimento_id = [s['id'] for s in self.stabilimenti if s['name'] == stabilimento_name][0]

        # Get KPIs and targets
        kpis = [dict(row) for row in db_retriever.get_all_kpis_detailed(only_visible=True)]
        targets = [dict(row) for row in db_retriever.get_annual_targets(stabilimento_id, int(year))]
        targets_map = {t['kpi_id']: t for t in targets}

        # Create widgets for each KPI
        for kpi in kpis:
            kpi_id = kpi['id']
            target_data = targets_map.get(kpi_id)
            self.create_kpi_input_box(self.scrollable_frame_target, kpi, target_data)

    def create_kpi_input_box(self, parent, kpi, target_data):
        kpi_id = kpi['id']
        is_sub_kpi = kpi.get('master_kpi_id') is not None

        # LabelFrame for the KPI
        labelframe = ttk.LabelFrame(parent, text=get_kpi_display_name(kpi))
        labelframe.pack(fill='x', padx=10, pady=5, expand=True)
        
        self.kpi_target_entry_widgets[kpi_id] = {'labelframe': labelframe, 'targets': {}}

        # Target 1 & 2
        for i in range(1, 3):
            self.create_target_input(labelframe, kpi, i, target_data, is_sub_kpi)

        # Repartition profile
        self.create_repartition_input(labelframe, kpi, target_data)
        
        self._update_sub_kpi_target_field_state(kpi_id)


    def create_target_input(self, parent, kpi, target_num, target_data, is_sub_kpi):
        kpi_id = kpi['id']
        frame = ttk.Frame(parent)
        frame.pack(fill='x', expand=True, padx=5, pady=2)

        target_key = f'annual_target{target_num}'
        
        # Target Label
        display_name = self.target1_display_name if target_num == 1 else self.target2_display_name
        ttk.Label(frame, text=f"{display_name}:").pack(side='left', padx=(0, 5))

        # Target entry
        target_val = target_data.get(target_key) if target_data else None
        target_var = tk.StringVar(value=str(target_val) if target_val is not None else "")
        target_entry = ttk.Entry(frame, textvariable=target_var, width=15)
        target_entry.pack(side='left', padx=5)

        # Manual checkbox for sub-KPIs
        manual_var = tk.BooleanVar()
        if is_sub_kpi:
            manual_cb = ttk.Checkbutton(frame, text="Man.", variable=manual_var, 
                                        command=lambda k=kpi_id, tn=target_num: self._on_force_manual_toggle(k, tn))
            manual_cb.pack(side='left', padx=5)
        
        # Use formula checkbox
        formula_var = tk.BooleanVar()
        formula_cb = ttk.Checkbutton(frame, text="Usa Formula", variable=formula_var,
                                     command=lambda k=kpi_id, tn=target_num: self._on_use_formula_toggle(k, tn))
        formula_cb.pack(side='left', padx=5)

        # Formula entry
        formula_entry_var = tk.StringVar()
        formula_entry = ttk.Entry(frame, textvariable=formula_entry_var, width=30)
        formula_entry.pack(side='left', padx=5, fill='x', expand=True)

        # Formula inputs button
        formula_button = ttk.Button(frame, text="Input...", 
                                    command=lambda k=kpi_id, tn=target_num: self._open_formula_inputs_dialog(k, tn))
        formula_button.pack(side='left', padx=5)

        # Store widgets
        self.kpi_target_entry_widgets[kpi_id]['targets'][target_num] = {
            'target_var': target_var,
            'target_entry': target_entry,
            'manual_var': manual_var if is_sub_kpi else None,
            'manual_cb': manual_cb if is_sub_kpi else None,
            'formula_var': formula_var,
            'formula_cb': formula_cb,
            'formula_entry_var': formula_entry_var,
            'formula_entry': formula_entry,
            'formula_button': formula_button
        }

    def create_repartition_input(self, parent, kpi, target_data):
        kpi_id = kpi['id']
        frame = ttk.Frame(parent)
        frame.pack(fill='x', expand=True, padx=5, pady=5)

        # Profile combobox
        ttk.Label(frame, text="Profilo di Distribuzione:").pack(side='left', padx=(0,5))
        profile_var = tk.StringVar(value=target_data.get('distribution_profile', 'uniforme') if target_data else 'uniforme')
        
        # TODO: Populate profiles from a central source
        profiles = ['uniforme', 'progressivo', 'sinusoidale', 'custom_monthly', 'custom_quarterly', 'custom_weekly', 'event_based']
        profile_cb = ttk.Combobox(frame, textvariable=profile_var, values=profiles, state='readonly')
        profile_cb.pack(side='left', padx=5)
        profile_cb.bind('<<ComboboxSelected>>', lambda e, k=kpi_id: self._update_repartition_input_area_tk(k))

        # Repartition input area
        repartition_frame = ttk.Frame(parent)
        repartition_frame.pack(fill='x', expand=True, padx=5, pady=2)

        # Store widgets
        self.kpi_target_entry_widgets[kpi_id]['repartition'] = {
            'profile_var': profile_var,
            'profile_cb': profile_cb,
            'repartition_frame': repartition_frame,
            'repartition_widgets': {}
        }
        self._update_repartition_input_area_tk(kpi_id)

    def _update_repartition_input_area_tk(self, kpi_id):
        widgets = self.kpi_target_entry_widgets[kpi_id]['repartition']
        frame = widgets['repartition_frame']
        profile = widgets['profile_var'].get()

        for child in frame.winfo_children():
            child.destroy()
        widgets['repartition_widgets'].clear()

        if profile in ['custom_monthly', 'custom_quarterly']:
            num_periods = 12 if profile == 'custom_monthly' else 4
            period_label = "Mese" if profile == 'custom_monthly' else "Trimestre"
            
            container = ttk.Frame(frame)
            container.pack(fill='x', expand=True)
            
            vars = []
            for i in range(num_periods):
                ttk.Label(container, text=f"{period_label} {i+1}:").grid(row=0, column=i*2, padx=2)
                var = tk.DoubleVar(value=0.0)
                entry = ttk.Entry(container, textvariable=var, width=5)
                entry.grid(row=0, column=i*2+1, padx=2)
                vars.append(var)
            widgets['repartition_widgets']['period_vars'] = vars

        elif profile in ['custom_weekly', 'event_based']:
            label_text = "Pesi Settimanali (JSON):" if profile == 'custom_weekly' else "Eventi (JSON):"
            text_area = tk.Text(frame, height=4, width=80)
            text_area.pack(fill='x', expand=True)
            widgets['repartition_widgets']['text_area'] = text_area

    def _on_force_manual_toggle(self, kpi_id, target_num):
        widgets = self.kpi_target_entry_widgets[kpi_id]['targets'][target_num]
        is_manual = widgets['manual_var'].get()
        
        widgets['target_entry'].config(state='normal' if is_manual else 'disabled')
        if is_manual:
            widgets['formula_var'].set(False)
            self._on_use_formula_toggle(kpi_id, target_num, force_disable=True)
        
        self._update_sub_kpi_target_field_state(kpi_id)
        self.recalculate_master_sub_distribution(kpi_id, target_num)

    def _on_use_formula_toggle(self, kpi_id, target_num, force_disable=False):
        widgets = self.kpi_target_entry_widgets[kpi_id]['targets'][target_num]
        use_formula = widgets['formula_var'].get() and not force_disable

        widgets['target_entry'].config(state='disabled' if use_formula else 'normal')
        widgets['formula_entry'].config(state='normal' if use_formula else 'disabled')
        widgets['formula_button'].config(state='normal' if use_formula else 'disabled')

        if use_formula and widgets.get('manual_cb'):
            widgets['manual_var'].set(False)
            widgets['manual_cb'].config(state='disabled')
        elif widgets.get('manual_cb'):
             widgets['manual_cb'].config(state='normal')

        self._update_sub_kpi_target_field_state(kpi_id)

    def _update_sub_kpi_target_field_state(self, kpi_id):
        kpi_widgets = self.kpi_target_entry_widgets[kpi_id]
        labelframe = kpi_widgets['labelframe']
        
        # This is a simplified logic. A more robust implementation would check each target.
        # For now, we check the state of the first target to color the frame.
        target1_widgets = kpi_widgets['targets'][1]
        
        style = "Derived.TLabelframe.Label" # Default/DerivedState
        if target1_widgets['formula_var'].get():
            style = "Formula.TLabelframe.Label" # FormulaState
        elif target1_widgets.get('manual_var') and target1_widgets['manual_var'].get():
            style = "Manual.TLabelframe.Label" # ManualState
            
        labelframe.config(style=style)

    def recalculate_master_sub_distribution(self, updated_kpi_id, target_num):
        kpi_info = db_retriever.get_kpi_detailed_by_id(updated_kpi_id)
        master_kpi_id = kpi_info.get('master_kpi_id')
        if not master_kpi_id:
            return

        linked_subs = db_retriever.get_linked_sub_kpis(master_kpi_id)
        master_widgets = self.kpi_target_entry_widgets.get(master_kpi_id)
        if not master_widgets:
            return

        master_target_val = master_widgets['targets'][target_num]['target_var'].get()

        total_weight = 0
        manual_targets_sum = 0
        non_manual_subs = []

        for sub in linked_subs:
            sub_kpi_id = sub['sub_kpi_id']
            sub_widgets = self.kpi_target_entry_widgets.get(sub_kpi_id)
            if not sub_widgets:
                continue

            target_widgets = sub_widgets['targets'][target_num]
            if target_widgets['manual_var'] and target_widgets['manual_var'].get():
                manual_targets_sum += target_widgets['target_var'].get()
            else:
                total_weight += sub['weight']
                non_manual_subs.append(sub)

        remaining_target = master_target_val - manual_targets_sum

        for sub in non_manual_subs:
            sub_kpi_id = sub['sub_kpi_id']
            sub_widgets = self.kpi_target_entry_widgets.get(sub_kpi_id)
            if not sub_widgets:
                continue

            weight = sub['weight']
            proportional_target = (remaining_target * weight / total_weight) if total_weight > 0 else 0
            sub_widgets['targets'][target_num]['target_var'].set(proportional_target)

    def _open_formula_inputs_dialog(self, kpi_id, target_num):
        # Assuming app has a cache of all kpis for selection
        dialog = FormulaInputsDialog(self, self.app.all_kpis_for_formula_selection_cache)
        if dialog.result_formula_data:
            widgets = self.kpi_target_entry_widgets[kpi_id]['targets'][target_num]
            widgets['formula_entry_var'].set(dialog.result_formula_data['formula_string'])
            # Storing mappings requires a place in the data model, e.g., a json field
            # For now, we just set the formula string.

    def save_all_targets_entry(self):
        year_str = self.year_cb_target.get()
        stabilimento_name = self.stabilimento_cb_target.get()
        if not year_str or not stabilimento_name:
            messagebox.showerror("Errore", "Anno e stabilimento devono essere selezionati.")
            return

        year = int(year_str)
        stabilimento_id = [s['id'] for s in self.stabilimenti if s['name'] == stabilimento_name][0]
        
        targets_data_map = {}
        for kpi_id, kpi_widgets in self.kpi_target_entry_widgets.items():
            try:
                t1_val_str = kpi_widgets['targets'][1]['target_var'].get()
                t2_val_str = kpi_widgets['targets'][2]['target_var'].get()

                t1_val = float(t1_val_str) if t1_val_str else None
                t2_val = float(t2_val_str) if t2_val_str else None
            except ValueError:
                messagebox.showerror("Errore", f"Valore non valido per KPI {kpi_id}. Inserire un numero.")
                return

            targets_data = {
                'annual_target1': t1_val,
                'annual_target2': t2_val,
                'is_target1_manual': kpi_widgets['targets'][1]['manual_var'].get() if kpi_widgets['targets'][1]['manual_var'] else True,
                'is_target2_manual': kpi_widgets['targets'][2]['manual_var'].get() if kpi_widgets['targets'][2]['manual_var'] else True,
                'target1_is_formula_based': kpi_widgets['targets'][1]['formula_var'].get(),
                'target2_is_formula_based': kpi_widgets['targets'][2]['formula_var'].get(),
                'target1_formula': kpi_widgets['targets'][1]['formula_entry_var'].get(),
                'target2_formula': kpi_widgets['targets'][2]['formula_entry_var'].get(),
                'distribution_profile': kpi_widgets['repartition']['profile_var'].get(),
                'repartition_values': self.get_repartition_values(kpi_widgets['repartition']),
                'profile_params': self.get_profile_params(kpi_widgets['repartition'])
            }
            targets_data_map[str(kpi_id)] = targets_data

        try:
            annual_targets_manager.save_annual_targets(
                year=year,
                stabilimento_id=stabilimento_id,
                targets_data_map=targets_data_map
            )
            messagebox.showinfo("Successo", "Tutti i target sono stati salvati.")
        except Exception as e:
            messagebox.showerror("Errore Salvataggio", f"Errore nel salvataggio dei target: {e}")
        
        self.load_kpi_targets_for_entry_target()

    def get_repartition_values(self, repartition_widgets):
        profile = repartition_widgets['profile_var'].get()
        if profile in ['custom_monthly', 'custom_quarterly']:
            return { i+1: var.get() for i, var in enumerate(repartition_widgets['repartition_widgets']['period_vars']) }
        elif profile in ['custom_weekly', 'event_based']:
            try:
                return json.loads(repartition_widgets['repartition_widgets']['text_area'].get("1.0", tk.END))
            except (json.JSONDecodeError, tk.TclError):
                return {}
        return {}

    def get_profile_params(self, repartition_widgets):
        # For now, we don't have specific UI for profile_params, so we return an empty dict.
        # This can be expanded in the future.
        return {}