import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import json

from src.target_management import annual as annual_targets_manager
from src import data_retriever as db_retriever
from src.interfaces.common_ui.helpers import get_kpi_display_name
from src.core.node_engine import KpiDAG

class CollapsibleFrame(ttk.Frame):
    def __init__(self, parent, title, **kwargs):
        super().__init__(parent, **kwargs)
        self.is_collapsed = False
        self.title = title
        
        self.toggle_button = ttk.Button(self, text=f"[-] {self.title}", command=self.toggle, style="Link.TButton")
        self.toggle_button.pack(fill='x', expand=True)
        
        self.content_frame = ttk.Frame(self, style="Card.TFrame")
        self.content_frame.pack(fill='both', expand=True, padx=10)

    def toggle(self):
        if self.is_collapsed:
            self.content_frame.pack(fill='both', expand=True, padx=10)
            self.toggle_button.config(text=f"[-] {self.title}")
            self.is_collapsed = False
        else:
            self.content_frame.pack_forget()
            self.toggle_button.config(text=f"[+] {self.title}")
            self.is_collapsed = True

class TargetEntryTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._populating_target_kpi_entries = False
        self._master_sub_update_active = False
        
        self.target1_display_name = "Target 1"
        self.target2_display_name = "Target 2"
        self.plants = []
        self.kpi_target_entry_widgets = {}

        self.create_widgets()

    def create_widgets(self):
        # Top toolbar for filters
        filter_frame = ttk.Frame(self, style="Content.TFrame", padding=10)
        filter_frame.pack(side='top', fill='x')

        ttk.Label(filter_frame, text="Year:").pack(side='left', padx=5)
        self.year_cb_target = ttk.Combobox(filter_frame, values=[str(y) for y in range(2020, 2031)], width=10, state='readonly')
        self.year_cb_target.set(str(datetime.datetime.now().year))
        self.year_cb_target.pack(side='left', padx=5)
        self.year_cb_target.bind('<<ComboboxSelected>>', lambda e: self.load_kpi_targets_for_entry_target())

        ttk.Label(filter_frame, text="Plant:").pack(side='left', padx=5)
        self.plant_cb_target = ttk.Combobox(filter_frame, width=25, state='readonly')
        self.plant_cb_target.pack(side='left', padx=5)
        self.plant_cb_target.bind('<<ComboboxSelected>>', lambda e: self.load_kpi_targets_for_entry_target())

        ttk.Button(filter_frame, text="Save All Changes", command=self.save_all_targets_entry, style="Action.TButton").pack(side='right', padx=5)

        # Main scrollable container
        container = ttk.Frame(self, style="Content.TFrame")
        container.pack(fill='both', expand=True)

        self.canvas_target = tk.Canvas(container, bg="#F0F0F0", highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas_target.yview)
        self.scrollable_frame_target = ttk.Frame(self.canvas_target, style="Content.TFrame")

        self.scrollable_frame_target.bind(
            "<Configure>",
            lambda e: self.canvas_target.configure(scrollregion=self.canvas_target.bbox("all"))
        )

        self.canvas_target.create_window((0, 0), window=self.scrollable_frame_target, anchor="nw", width=self.app.winfo_width()-30)
        self.canvas_target.configure(yscrollcommand=scrollbar.set)

        self.canvas_target.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mousewheel support
        self.canvas_target.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        self.canvas_target.yview_scroll(int(-1*(event.delta/120)), "units")

    def populate_target_comboboxes(self):
        self.plants = [dict(row) for row in db_retriever.get_all_plants(visible_only=True)]
        plant_names = [s['name'] for s in self.plants]
        self.plant_cb_target['values'] = plant_names
        if plant_names:
            self.plant_cb_target.set(plant_names[0])
            self.load_kpi_targets_for_entry_target()

    def load_kpi_targets_for_entry_target(self):
        year = self.year_cb_target.get()
        plant_name = self.plant_cb_target.get()
        if not year or not plant_name: return

        self._populating_target_kpi_entries = True
        for child in self.scrollable_frame_target.winfo_children():
            child.destroy()
        self.kpi_target_entry_widgets.clear()

        # Get plant ID
        plant_id = [s['id'] for s in self.plants if s['name'] == plant_name][0]

        # Get KPIs and targets
        kpis = [dict(row) for row in db_retriever.get_all_kpis_detailed(only_visible=True, plant_id=plant_id)]
        targets = [dict(row) for row in db_retriever.get_annual_targets(plant_id, int(year))]
        targets_map = {t['kpi_id']: t for t in targets}

        # Group KPIs by Group and Subgroup
        hierarchy = {} # group_name -> { subgroup_name -> [kpis] }
        for kpi in kpis:
            g_name = kpi.get('group_name', 'No Group')
            sg_name = kpi.get('subgroup_name', 'No Subgroup')
            if g_name not in hierarchy: hierarchy[g_name] = {}
            if sg_name not in hierarchy[g_name]: hierarchy[g_name][sg_name] = []
            hierarchy[g_name][sg_name].append(kpi)

        # Create widgets hierarchically
        for g_name, subgroups in hierarchy.items():
            g_frame = CollapsibleFrame(self.scrollable_frame_target, title=f"Group: {g_name}")
            g_frame.pack(fill='x', padx=5, pady=5, expand=True)
            
            for sg_name, sg_kpis in subgroups.items():
                sg_frame = CollapsibleFrame(g_frame.content_frame, title=f"Subgroup: {sg_name}")
                sg_frame.pack(fill='x', padx=10, pady=2, expand=True)
                
                for kpi in sg_kpis:
                    kpi_id = kpi['id']
                    target_data = targets_map.get(kpi_id)
                    self.create_kpi_input_box(sg_frame.content_frame, kpi, target_data)
        
        self._populating_target_kpi_entries = False
        self.scrollable_frame_target.update_idletasks()
        self.canvas_target.configure(scrollregion=self.canvas_target.bbox('all'))

    def create_kpi_input_box(self, parent, kpi, target_data):
        kpi_id = kpi['id']
        is_calculated = bool(kpi.get('is_calculated', False))
        is_sub_kpi = bool(kpi.get('master_kpi_id'))
        
        labelframe_style = "Formula.TLabelframe" if is_calculated else "Manual.TLabelframe"
        content_style = "Formula.TFrame" if is_calculated else "Manual.TFrame"
        
        labelframe = ttk.LabelFrame(parent, text=f"{kpi['indicator_name']} ({kpi['unit_of_measure']})", style=labelframe_style, padding=10)
        labelframe.pack(fill='x', padx=10, pady=5, expand=True)

        self.kpi_target_entry_widgets[kpi_id] = {'labelframe': labelframe, 'targets': {}}

        # Container for side-by-side layout
        content_frame = ttk.Frame(labelframe, style=content_style)
        content_frame.pack(fill='x', expand=True)

        # Target 1
        t1_frame = ttk.Frame(content_frame, style=content_style)
        t1_frame.pack(side='left', fill='x', expand=True)
        self.create_target_input(t1_frame, kpi, 1, target_data, is_sub_kpi, is_calculated, content_style)

        # Target 2
        t2_frame = ttk.Frame(content_frame, style=content_style)
        t2_frame.pack(side='left', fill='x', expand=True)
        self.create_target_input(t2_frame, kpi, 2, target_data, is_sub_kpi, is_calculated, content_style)

        # Repartition profile (Compact)
        repart_summary_frame = ttk.Frame(content_frame, style=content_style)
        repart_summary_frame.pack(side='right', padx=10)
        
        current_profile = target_data.get('distribution_profile') if target_data else None
        if not current_profile or current_profile == 'annual_progressive':
            current_profile = kpi.get('default_distribution_profile', 'annual_progressive')
            
        ttk.Label(repart_summary_frame, text=f"Profile: {current_profile}", font=("Helvetica", 8, "italic")).pack()
        
        if not is_calculated:
            ttk.Button(repart_summary_frame, text="Split Settings", style="Small.TButton",
                       command=lambda: self._open_repartition_dialog(kpi, target_data)).pack()

    def create_target_input(self, parent, kpi, target_num, target_data, is_sub_kpi, is_calculated, style):
        kpi_id = kpi['id']
        frame = ttk.Frame(parent, style=style)
        frame.pack(fill='x', expand=True, padx=5, pady=2)

        target_key = f'annual_target{target_num}'
        manual_key = f'is_target{target_num}_manual'
        
        display_name = f"T{target_num}"
        ttk.Label(frame, text=f"{display_name}:", width=4).pack(side='left')

        # Target entry
        target_val = target_data.get(target_key) if target_data else None
        target_var = tk.StringVar(value=str(target_val) if target_val is not None else "")
        
        # Override / Manual Flag
        # If it's a sub-KPI or a Calculated KPI, we need a manual flag
        manual_var = tk.BooleanVar(value=bool(target_data.get(manual_key, False)) if target_data else False)
        
        # Determine initial entry state
        # If it's calculated and NOT overridden, it's disabled (preview mode)
        # If it's manual, it's always enabled
        is_manual_override = manual_var.get()
        entry_state = 'normal' if (not is_calculated or is_manual_override) else 'disabled'
        
        target_entry = ttk.Entry(frame, textvariable=target_var, width=12, state=entry_state)
        target_entry.pack(side='left', padx=5)
        
        # Add Override Checkbox for Calculated KPIs
        manual_cb = None
        if is_calculated:
            manual_cb = ttk.Checkbutton(frame, text="Override", variable=manual_var, 
                                        command=lambda k=kpi_id, tn=target_num: self._on_override_toggle(k, tn))
            manual_cb.pack(side='left', padx=2)
        elif is_sub_kpi:
            # Legacy Sub-KPI manual flag
            manual_cb = ttk.Checkbutton(frame, text="M", variable=manual_var, 
                                        command=lambda k=kpi_id, tn=target_num: self._on_override_toggle(k, tn))
            manual_cb.pack(side='left', padx=2)

        # Add trace for auto-population
        target_var.trace_add("write", lambda *args, k=kpi_id, tn=target_num: self._on_target_value_change(k, tn))

        # Store widgets
        self.kpi_target_entry_widgets[kpi_id]['targets'][target_num] = {
            'target_var': target_var,
            'target_entry': target_entry,
            'manual_var': manual_var,
            'manual_cb': manual_cb,
            'is_calculated': is_calculated,
            'formula_json': kpi.get('formula_json') # CACHE
        }

    def _on_override_toggle(self, kpi_id, target_num):
        widgets = self.kpi_target_entry_widgets[kpi_id]['targets'][target_num]
        is_overridden = widgets['manual_var'].get()
        
        widgets['target_entry'].config(state='normal' if is_overridden else 'disabled')
        
        # If turning override OFF, trigger a recalculation to restore calculated value
        if not is_overridden:
            self._recalculate_all_formulas_ui(target_num)
        
        self.recalculate_master_sub_distribution(kpi_id, target_num)

    def _on_target_value_change(self, kpi_id, target_num):
        if self._populating_target_kpi_entries or self._master_sub_update_active:
            return
        
        # We always trigger formula recalculation when ANY value changes, 
        # because this value might be an input to a formula somewhere else.
        self._recalculate_all_formulas_ui(target_num)
        self.recalculate_master_sub_distribution(kpi_id, target_num)

    def _recalculate_all_formulas_ui(self, target_num):
        if self._populating_target_kpi_entries: return
        
        if getattr(self, "_recalculating_ui", False): return
        self._recalculating_ui = True
        
        try:
            for p in range(5):
                made_progress = False
                for kpi_id, widgets in self.kpi_target_entry_widgets.items():
                    t_widgets = widgets['targets'][target_num]
                    
                    if t_widgets['is_calculated'] and not t_widgets['manual_var'].get():
                        formula_json = t_widgets['formula_json']
                        if not formula_json: continue
                        
                        try:
                            dag = KpiDAG.from_json(formula_json)
                            def ui_resolver(kid, tn):
                                # Ensure kid is handled as int
                                try: kid_key = int(kid)
                                except: kid_key = kid
                                
                                w = self.kpi_target_entry_widgets.get(kid_key)
                                if w:
                                    val_str = w['targets'][tn]['target_var'].get()
                                    try:
                                        return float(val_str) if val_str else 0.0
                                    except ValueError:
                                        return 0.0
                                return 0.0
                            
                            # Pass current target_num as default for input nodes
                            calc_val = dag.evaluate(ui_resolver, default_target_num=target_num)
                            calc_val = round(calc_val, 4)
                            
                            current_val_str = t_widgets['target_var'].get()
                            try:
                                current_val = float(current_val_str) if current_val_str else 0.0
                            except ValueError:
                                current_val = None 
                            
                            if current_val is None or abs(current_val - calc_val) > 1e-9:
                                t_widgets['target_var'].set(str(calc_val))
                                made_progress = True
                        except Exception as e:
                            print(f"DEBUG: Error evaluating formula for KPI {kpi_id}: {e}")
                if not made_progress: break
        finally:
            self._recalculating_ui = False

    def recalculate_master_sub_distribution(self, updated_kpi_id, target_num):
        kpi_info = db_retriever.get_kpi_detailed_by_id(updated_kpi_id)
        if not kpi_info: return
        
        master_kpi_id = kpi_info.get('master_kpi_id')
        if not master_kpi_id:
            # If this IS a master KPI, distribute to subs
            linked_subs = db_retriever.get_linked_sub_kpis_detailed(updated_kpi_id)
            if not linked_subs: return
            
            self._master_sub_update_active = True
            try:
                master_widgets = self.kpi_target_entry_widgets.get(updated_kpi_id)
                master_val_str = master_widgets['targets'][target_num]['target_var'].get()
                master_val = float(master_val_str) if master_val_str else 0.0
                
                total_weight = sum(sub['distribution_weight'] for sub in linked_subs)
                for sub in linked_subs:
                    sub_id = sub['id'] # The query aliases k.id as id
                    sub_widgets = self.kpi_target_entry_widgets.get(sub_id)
                    if sub_widgets:
                        # Check if sub is manual or has formula
                        # Master distribution only applies if sub is NOT overridden
                        t_sub = sub_widgets['targets'][target_num]
                        if not t_sub['manual_var'].get():
                            weight = sub['distribution_weight']
                            calc_sub = (master_val * weight / total_weight) if total_weight > 0 else 0
                            t_sub['target_var'].set(str(round(calc_sub, 4)))
            finally:
                self._master_sub_update_active = False
        else:
            # If this IS a sub KPI, we don't usually push UP to master in this simple logic
            # unless specifically requested. Usually, sub-KPIs are derived.
            pass

    def save_all_targets_entry(self):
        year_str = self.year_cb_target.get()
        plant_name = self.plant_cb_target.get()
        if not year_str or not plant_name: return

        year = int(year_str)
        plant_id = [s['id'] for s in self.plants if s['name'] == plant_name][0]

        targets_data_map = {}
        for kpi_id, kpi_widgets in self.kpi_target_entry_widgets.items():
            t1_w = kpi_widgets['targets'][1]
            t2_w = kpi_widgets['targets'][2]
            
            targets_data = {
                'annual_target1': float(t1_w['target_var'].get() or 0),
                'annual_target2': float(t2_w['target_var'].get() or 0),
                'is_target1_manual': t1_w['manual_var'].get() if t1_w['manual_var'] else True,
                'is_target2_manual': t2_w['manual_var'].get() if t2_w['manual_var'] else True,
                'target1_is_formula_based': t1_w['is_calculated'] and not t1_w['manual_var'].get(),
                'target2_is_formula_based': t2_w['is_calculated'] and not t2_w['manual_var'].get(),
            }
            targets_data_map[str(kpi_id)] = targets_data

        import threading
        def run_save():
            try:
                annual_targets_manager.save_annual_targets(year, plant_id, targets_data_map)
                self.after(0, lambda: messagebox.showinfo("Success", "Targets saved."))
            except Exception as e:
                self.after(0, lambda ex=e: messagebox.showerror("Error", str(ex)))
        
        threading.Thread(target=run_save, daemon=True).start()

    def _open_repartition_dialog(self, kpi, target_data):
        # Implementation for the detailed repartition settings dialog
        pass
