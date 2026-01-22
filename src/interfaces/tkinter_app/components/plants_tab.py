import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
import traceback

from src.plants_management import crud as plants_manager
from src import data_retriever

class PlantsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.create_widgets()
        self.refresh_tree()

    def create_widgets(self):
        self.st_tree = ttk.Treeview(
            self,
            columns=("ID", "Name", "Description", "Visible", "Color"),
            show="headings",
        )
        self.st_tree.heading("ID", text="ID")
        self.st_tree.column("ID", width=50, anchor="center", stretch=tk.NO)
        self.st_tree.heading("Name", text="Name")
        self.st_tree.column("Name", width=200, stretch=tk.YES)
        self.st_tree.heading("Description", text="Description")
        self.st_tree.column("Description", width=250, stretch=tk.YES)
        self.st_tree.heading("Visible", text="Visible")
        self.st_tree.column("Visible", width=80, anchor="center", stretch=tk.NO)
        self.st_tree.heading("Color", text="Color")
        self.st_tree.column("Color", width=100, anchor="center", stretch=tk.NO)

        self.st_tree.pack(expand=True, fill="both", padx=5, pady=5)

        bf_container = ttk.Frame(self)
        bf_container.pack(fill="x", pady=10)
        bf = ttk.Frame(bf_container)
        bf.pack()

        ttk.Button(bf, text="Add", command=self.add_plant_window, style="Accent.TButton").pack(side="left", padx=5)
        ttk.Button(bf, text="Edit", command=self.edit_plant_window).pack(side="left", padx=5)
        ttk.Button(bf, text="Delete", command=self.delete_plant).pack(side="left", padx=5)

    def refresh_tree(self):
        for i in self.st_tree.get_children():
            self.st_tree.delete(i)
        try:
            for row in data_retriever.get_all_plants():
                self.st_tree.insert(
                    "",
                    "end",
                    values=(row["id"], row["name"], row["description"] if row["description"] is not None else "", "Yes" if row["visible"] else "No", row["color"]),
                )
        except Exception as e:
            messagebox.showerror("Loading Error", f"Could not load plants from the database:\n{e}")

    def add_plant_window(self):
        self.plant_editor_window()

    def edit_plant_window(self):
        selected_item_iid = self.st_tree.focus()
        if not selected_item_iid:
            messagebox.showwarning("Warning", "Select a plant to edit.")
            return
        
        item_values = self.st_tree.item(selected_item_iid)["values"]
        if not item_values:
            messagebox.showerror("Error", "Could not read data for the selected plant.")
            return
            
        try:
            data_tuple = (
                int(item_values[0]), 
                item_values[1], 
                item_values[2], 
                item_values[3],
                item_values[4]
            )
            self.plant_editor_window(data_tuple=data_tuple)
        except (ValueError, IndexError) as e:
            messagebox.showerror("Data Error", f"Data for the selected plant is not valid: {e}")

    def delete_plant(self):
        selected_item = self.st_tree.focus()
        if not selected_item:
            messagebox.showwarning("Warning", "Select a plant to delete.")
            return
        
        item_values = self.st_tree.item(selected_item)["values"]
        try:
            plant_id = int(item_values[0])
            plant_name = item_values[1]
        except (ValueError, IndexError):
            messagebox.showerror("Error", "Invalid plant ID.")
            return

        if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete plant '{plant_name}'?\nThis action is irreversible."):
            try:
                plants_manager.delete_plant(plant_id)
                self.app.refresh_all_data() 
                messagebox.showinfo("Success", f"Plant '{plant_name}' deleted successfully.")
            except ValueError as ve:
                messagebox.showerror("Deletion Error", f"Could not delete plant:\n{ve}")
            except Exception as e:
                messagebox.showerror("Deletion Error", f"Could not delete plant:\n{e}\n\n{traceback.format_exc()}")

    def plant_editor_window(self, data_tuple=None):
        win = tk.Toplevel(self)
        win.title("New Plant" if data_tuple is None else "Edit Plant")
        win.transient(self)
        win.grab_set()
        win.geometry("450x220")
        win.resizable(False, False)

        plant_id, plant_name, plant_desc, plant_vis_str, plant_color = (
            data_tuple
            if data_tuple
            else (None, "", "", "Yes", "#000000") # Default color for new plant
        )

        form_frame = ttk.Frame(win, padding=15)
        form_frame.pack(expand=True, fill="both")

        ttk.Label(form_frame, text="Plant Name:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        name_var = tk.StringVar(value=plant_name)
        name_entry = ttk.Entry(form_frame, textvariable=name_var, width=40)
        name_entry.grid(row=0, column=1, padx=5, pady=5)
        name_entry.focus_set()

        ttk.Label(form_frame, text="Description:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        desc_var = tk.StringVar(value=plant_desc)
        desc_entry = ttk.Entry(form_frame, textvariable=desc_var, width=40)
        desc_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(form_frame, text="Color:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        color_var = tk.StringVar(value=plant_color)
        color_label = ttk.Label(form_frame, textvariable=color_var, background=plant_color, width=10, relief="solid")
        color_label.grid(row=2, column=1, sticky="w", padx=5, pady=5)
        ttk.Button(form_frame, text="Choose...", command=lambda: self._choose_color_for_editor(color_var, color_label)).grid(row=2, column=2, padx=5, pady=5)

        visible_var = tk.BooleanVar(value=(plant_vis_str == "Yes"))
        ttk.Checkbutton(form_frame, text="Visible for Target Entry", variable=visible_var).grid(row=3, column=1, sticky="w", padx=5, pady=10)

        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=4, columnspan=3, pady=15)

        def save_action():
            name_val = name_var.get().strip()
            desc_val = desc_var.get().strip()
            if not name_val:
                messagebox.showerror("Validation Error", "The 'Name' field is required.", parent=win)
                return

            try:
                if plant_id is not None:
                    plants_manager.update_plant(plant_id, name_val, desc_val, visible_var.get(), color_var.get())
                else:
                    plants_manager.add_plant(name_val, desc_val, visible_var.get(), color_var.get())

                self.refresh_tree()
                self.app.refresh_all_data()
                win.destroy()
                messagebox.showinfo("Success", "Plant saved successfully.")
            except Exception as e:
                messagebox.showerror("Save Error", f"Save failed:\n{e}\n\n{traceback.format_exc()}", parent=win)
        ttk.Button(btn_frame, text="Save", command=save_action, style="Accent.TButton").pack(side="left", padx=10)
        ttk.Button(btn_frame, text="Cancel", command=win.destroy).pack(side="left", padx=10)

    def _choose_color_for_editor(self, color_var, color_label):
        color_code = colorchooser.askcolor(title="Choose color")
        if color_code:
            color_hex = color_code[1]
            color_var.set(color_hex)
            color_label.config(background=color_hex)
