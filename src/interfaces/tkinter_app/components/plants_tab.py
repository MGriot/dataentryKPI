# src/interfaces/tkinter_app/components/plants_tab.py
import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
import traceback

from src.plants_management import crud as plants_manager
from src import data_retriever

class PlantsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.current_plants_map = {}
        self.create_widgets()
        self.refresh_tree()

    def create_widgets(self):
        # Main container with a PanedWindow
        self.paned = ttk.PanedWindow(self, orient="horizontal")
        self.paned.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Left Side: List ---
        list_frame = ttk.Frame(self.paned, style="Card.TFrame")
        self.paned.add(list_frame, weight=1)

        toolbar = ttk.Frame(list_frame, style="Card.TFrame")
        toolbar.pack(fill="x", pady=(0, 5))
        ttk.Button(toolbar, text="+ Add Plant", command=self.add_plant_window, style="Action.TButton").pack(side="left")

        self.tree = ttk.Treeview(list_frame, columns=("Name", "Visible"), show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Color")
        self.tree.column("#0", width=50, anchor="center")
        self.tree.heading("Name", text="Plant Name")
        self.tree.heading("Visible", text="Vis.")
        self.tree.column("Visible", width=40, anchor="center")
        self.tree.pack(fill="both", expand=True)
        
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda e: self.edit_plant_window())

        # --- Right Side: Detail Panel ---
        self.detail_container = ttk.LabelFrame(self.paned, text="Plant Details", style="Card.TLabelframe", padding=15)
        self.paned.add(self.detail_container, weight=2)
        
        self.detail_content = ttk.Frame(self.detail_container, style="Card.TFrame")
        self.detail_content.pack(fill="both", expand=True)
        
        self._clear_details()

    def refresh_tree(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        self.current_plants_map = {}
        try:
            for row in data_retriever.get_all_plants():
                iid = self.tree.insert("", "end", values=(row["name"], "✓" if row["visible"] else "×"))
                # Note: Setting tag for color background if supported by theme, or just ID mapping
                self.current_plants_map[iid] = dict(row)
                # Visual hint for color
                self.tree.tag_configure(f"tag_{row['id']}", background=row['color'])
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            self._clear_details()
            return
        
        plant = self.current_plants_map[sel[0]]
        for child in self.detail_content.winfo_children(): child.destroy()

        # Header
        ttk.Label(self.detail_content, text=plant['name'], font=("Helvetica", 14, "bold"), background="#FFFFFF").pack(anchor="w")
        
        # Color Box
        color_f = ttk.Frame(self.detail_content, style="Card.TFrame")
        color_f.pack(fill="x", pady=10)
        ttk.Label(color_f, text="Brand Color: ", background="#FFFFFF").pack(side="left")
        tk.Label(color_f, width=4, height=1, bg=plant['color'], relief="solid").pack(side="left")
        ttk.Label(color_f, text=f" ({plant['color']})", font=("Courier", 10), background="#FFFFFF").pack(side="left")

        # Info
        ttk.Label(self.detail_content, text="Description:", font=("Helvetica", 10, "bold"), background="#FFFFFF").pack(anchor="w", pady=(10,0))
        ttk.Label(self.detail_content, text=plant['description'] or "No description provided.", wraplength=300, background="#FFFFFF").pack(anchor="w")
        
        ttk.Label(self.detail_content, text=f"Visible in Entry: {'Yes' if plant['visible'] else 'No'}", background="#FFFFFF").pack(anchor="w", pady=10)

        # Actions
        btn_f = ttk.Frame(self.detail_content, style="Card.TFrame")
        btn_f.pack(fill="x", pady=20)
        ttk.Button(btn_f, text="Edit Plant", command=self.edit_plant_window, style="Action.TButton").pack(side="left", padx=5)
        ttk.Button(btn_f, text="Delete", command=self.delete_plant).pack(side="left", padx=5)

    def _clear_details(self):
        for child in self.detail_content.winfo_children(): child.destroy()
        ttk.Label(self.detail_content, text="Select a plant to manage.", font=("Helvetica", 10, "italic"), background="#FFFFFF").pack(pady=50)

    def add_plant_window(self):
        self.plant_editor_window()

    def edit_plant_window(self):
        sel = self.tree.selection()
        if not sel: return
        plant = self.current_plants_map[sel[0]]
        # Pass data in format the editor expects
        data = (plant['id'], plant['name'], plant['description'], "Yes" if plant['visible'] else "No", plant['color'])
        self.plant_editor_window(data_tuple=data)

    def delete_plant(self):
        sel = self.tree.selection()
        if not sel: return
        plant = self.current_plants_map[sel[0]]
        if messagebox.askyesno("Confirm", f"Delete plant '{plant['name']}'?"):
            try:
                plants_manager.delete_plant(plant['id'])
                self.refresh_tree()
                self._clear_details()
                self.app.refresh_all_data()
            except Exception as e: messagebox.showerror("Error", str(e))

    def plant_editor_window(self, data_tuple=None):
        win = tk.Toplevel(self)
        win.title("Plant Editor")
        win.geometry("450x250")
        win.resizable(False, False)
        win.grab_set()

        p_id, p_name, p_desc, p_vis, p_color = data_tuple if data_tuple else (None, "", "", "Yes", "#000000")

        f = ttk.Frame(win, padding=20)
        f.pack(fill="both", expand=True)

        ttk.Label(f, text="Name:").grid(row=0, column=0, sticky="w")
        name_v = tk.StringVar(value=p_name)
        ttk.Entry(f, textvariable=name_v, width=30).grid(row=0, column=1, padx=10, pady=5)

        ttk.Label(f, text="Description:").grid(row=1, column=0, sticky="w")
        desc_v = tk.StringVar(value=p_desc)
        ttk.Entry(f, textvariable=desc_v, width=30).grid(row=1, column=1, padx=10, pady=5)

        ttk.Label(f, text="Color:").grid(row=2, column=0, sticky="w")
        color_v = tk.StringVar(value=p_color)
        c_lbl = tk.Label(f, width=10, bg=p_color, relief="solid")
        c_lbl.grid(row=2, column=1, sticky="w", padx=10)
        
        def pick():
            c = colorchooser.askcolor(color_v.get())[1]
            if c: color_v.set(c); c_lbl.config(bg=c)
        ttk.Button(f, text="Pick...", command=pick).grid(row=2, column=1, sticky="e", padx=10)

        vis_v = tk.BooleanVar(value=(p_vis == "Yes"))
        ttk.Checkbutton(f, text="Visible for Target Entry", variable=vis_v).grid(row=3, column=1, sticky="w", pady=10)

        def save():
            if not name_v.get().strip(): return
            try:
                if p_id: plants_manager.update_plant(p_id, name_v.get().strip(), desc_v.get().strip(), vis_v.get(), color_v.get())
                else: plants_manager.add_plant(name_v.get().strip(), desc_v.get().strip(), vis_v.get(), color_v.get())
                self.refresh_tree()
                self.app.refresh_all_data()
                win.destroy()
            except Exception as e: messagebox.showerror("Error", str(e))

        ttk.Button(f, text="Save", command=save, style="Action.TButton").grid(row=4, column=1, sticky="w", pady=10)
        ttk.Button(f, text="Cancel", command=win.destroy).grid(row=4, column=1, sticky="e", pady=10)
