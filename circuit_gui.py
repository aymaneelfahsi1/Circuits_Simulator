from imports import *
from circuit_simulator import CircuitSimulator
from circuit_elements import CircuitElement, Wire
import pickle
from tkinter import filedialog


class TextHandler(logging.Handler):
    """
    This class allows logging to a Tkinter Text widget.
    """
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.configure(state='disabled')
            self.text_widget.yview(tk.END)
        self.text_widget.after(0, append)


class CircuitGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Advanced Circuit Simulator")

        self.geometry("1500x800")

        self.simulator = CircuitSimulator()

        self.left_frame = tk.Frame(self, width=220)
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.canvas_frame = tk.Frame(self)
        self.canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.right_frame = tk.Frame(self, width=300)
        self.right_frame.pack(side=tk.LEFT, fill=tk.BOTH)

        self.canvas = tk.Canvas(self.canvas_frame, bg="#fafafa", width=900, height=700)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(self.right_frame, state='disabled', wrap='word')
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text_label = ttk.Label(self.right_frame, text="Log Output", font=("Arial", 12, "bold"))
        self.log_text_label.pack(anchor='nw')

        gui_handler = TextHandler(self.log_text)
        gui_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(gui_handler)

        self.active_tool = tk.StringVar(value="select")
        self.snap_to_grid = tk.BooleanVar(value=False)
        self.grid_size = 20

        self.components = []
        self.wires = []
        self.comp_index = {"resistor": 0, "voltage_source": 0, "current_source": 0}

        self.selected_components = []
        self.selected_wires = []

        self.dragging = False
        self.last_mouse_pos = (0, 0)
        self.selection_box = None

        self.wire_start = None

        self.node_positions = {}
        self.node_labels = {}

        self.component_voltage_arrows = {}
        self.component_current_arrows = {}

        self.build_left_ui()


        self.canvas.bind("<Button-1>", self.on_left_down)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_up)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)

        self.canvas.bind("<r>", lambda e: self.rotate_selected(90))
        self.canvas.bind("<Delete>", lambda e: self.delete_selected())
        self.canvas.bind("<Escape>", lambda e: self.cancel_actions())
        self.canvas.focus_set()

    def rotate_points(self, points, angle_deg):
        angle = math.radians(angle_deg)
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        rotated = []
        for (px, py) in points:
            rx = px * cos_a - py * sin_a
            ry = px * sin_a + py * cos_a
            rotated.append((rx, ry))
        return rotated

    def build_left_ui(self):
        ttk.Label(self.left_frame, text="Tools", font=("Arial", 12, "bold")).pack(pady=5)

        ttk.Button(self.left_frame, text="Select/Move",
                   command=lambda: self.set_tool("select")).pack(fill=tk.X, pady=2)
        ttk.Button(self.left_frame, text="Resistor",
                   command=lambda: self.set_tool("resistor")).pack(fill=tk.X, pady=2)
        ttk.Button(self.left_frame, text="Voltage Source",
                   command=lambda: self.set_tool("voltage_source")).pack(fill=tk.X, pady=2)
        ttk.Button(self.left_frame, text="Current Source",
                   command=lambda: self.set_tool("current_source")).pack(fill=tk.X, pady=2)
        ttk.Button(self.left_frame, text="Wire (Connect)",
                   command=lambda: self.set_tool("wire")).pack(fill=tk.X, pady=2)

        ttk.Button(self.left_frame, text="Ground (G)",
               command=lambda: self.set_tool("ground")).pack(fill=tk.X, pady=2)

        ttk.Button(self.left_frame, text="Save Circuit", command=self.save_circuit).pack(fill=tk.X, pady=2)
        ttk.Button(self.left_frame, text="Load Circuit", command=self.load_circuit).pack(fill=tk.X, pady=2)

        ttk.Label(self.left_frame, text="Actions", font=("Arial", 12, "bold")).pack(pady=5)
        ttk.Button(self.left_frame, text="Rotate (R key)",
                   command=lambda: self.rotate_selected(90)).pack(fill=tk.X, pady=2)
        ttk.Button(self.left_frame, text="Delete (Del key)",
                   command=self.delete_selected).pack(fill=tk.X, pady=2)



        ttk.Button(self.left_frame, text="Simulate",
                   command=self.simulate).pack(side=tk.BOTTOM, fill=tk.X, pady=4)

        ttk.Button(self.left_frame, text="Reset Simulation State",
               command=self.reset_simulation_state).pack(side=tk.BOTTOM, fill=tk.X, pady=4)




        ttk.Checkbutton(self.left_frame, text="Snap to Grid", variable=self.snap_to_grid).pack(side=tk.BOTTOM, padx=5, pady=5)

    def set_tool(self, tool):
        self.active_tool.set(tool)
        self.wire_start = None
        self.clear_selection()
        logging.debug(f"Tool set to {tool}")

    def on_left_down(self, event):
        self.canvas.focus_set()
        tool = self.active_tool.get()
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

        if tool in ["resistor", "voltage_source", "current_source", "ground"]:
            self.place_component(tool, x, y)
            return

        if tool == "wire":
            self.handle_wire_click(x, y)
            return

        if tool == "select":
            clicked_items = self.canvas.find_overlapping(x-5, y-5, x+5, y+5)
            if not clicked_items:
                self.clear_selection()
                self.selection_box = self.canvas.create_rectangle(x, y, x, y, outline="blue", dash=(2, 2))
                logging.debug("Started box selection")
                return

            for item_id in reversed(clicked_items):
                comp_dict = self.find_component_by_item(item_id)
                if comp_dict:
                    if comp_dict in self.selected_components:
                        self.edit_component_value(comp_dict)
                        logging.debug(f"Editing value of component {comp_dict['element'].name if comp_dict['element'] else 'Ground'}")
                        return
                    if event.state & 0x0001:
                        if comp_dict in self.selected_components:
                            self.selected_components.remove(comp_dict)
                            self.highlight_component(comp_dict, False)
                            logging.debug(f"Deselected component {comp_dict['element'].name if comp_dict['element'] else 'Ground'}")
                        else:
                            self.selected_components.append(comp_dict)
                            self.highlight_component(comp_dict, True)
                            logging.debug(f"Selected component {comp_dict['element'].name if comp_dict['element'] else 'Ground'}")
                    else:
                        self.clear_selection()
                        self.selected_components.append(comp_dict)
                        self.highlight_component(comp_dict, True)
                        logging.debug(f"Selected component {comp_dict['element'].name if comp_dict['element'] else 'Ground'}")

                    self.dragging = True
                    self.last_mouse_pos = (x, y)
                    logging.debug("Started dragging components")
                    return

                wire_obj = self.find_wire_by_item(item_id)
                if wire_obj:
                    if event.state & 0x0001:
                        if wire_obj in self.selected_wires:
                            self.selected_wires.remove(wire_obj)
                            self.highlight_wire(wire_obj, False)
                            logging.debug(f"Deselected wire {wire_obj}")
                        else:
                            self.selected_wires.append(wire_obj)
                            self.highlight_wire(wire_obj, True)
                            logging.debug(f"Selected wire {wire_obj}")
                    else:
                        self.clear_selection()
                        self.selected_wires.append(wire_obj)
                        self.highlight_wire(wire_obj, True)
                        logging.debug(f"Selected wire {wire_obj}")
                    return

            self.clear_selection()
            self.selection_box = self.canvas.create_rectangle(x, y, x, y, outline="blue", dash=(2, 2))
            logging.debug("Started box selection")

    def on_left_up(self, event):
        self.dragging = False
        if self.selection_box:
            x1, y1, x2, y2 = self.canvas.coords(self.selection_box)
            self.canvas.delete(self.selection_box)
            self.selection_box = None
            if x2 < x1:
                x1, x2 = x2, x1
            if y2 < y1:
                y1, y2 = y2, y1
            for c in self.components:
                cx, cy = c['center']
                if x1 <= cx <= x2 and y1 <= cy <= y2:
                    if c not in self.selected_components:
                        self.selected_components.append(c)
                        self.highlight_component(c, True)
                        logging.debug(f"Selected component {c['element'].name if c['element'] else 'Ground'} via box selection")

    def on_drag(self, event):
        if self.dragging and self.selected_components:
            x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
            dx = x - self.last_mouse_pos[0]
            dy = y - self.last_mouse_pos[1]
            self.last_mouse_pos = (x, y)
            for comp in self.selected_components:
                cx, cy = comp['center']
                new_cx = cx + dx
                new_cy = cy + dy
                if self.snap_to_grid.get():
                    new_cx = round(new_cx / self.grid_size) * self.grid_size
                    new_cy = round(new_cy / self.grid_size) * self.grid_size
                comp['center'] = (new_cx, new_cy)
                rotated_terminals = self.rotate_points(comp['terminals'], comp['rotation'])
                comp['abs_terminals'] = [(new_cx + tx, new_cy + ty) for tx, ty in rotated_terminals]
                self.redraw_component(comp)
            self.update_wires()
            self.compute_node_positions()

    def on_double_click(self, event):
        """
        Optional fallback: double-click to edit a component’s value.
        """
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        clicked_item = self.canvas.find_closest(x, y)
        if clicked_item:
            comp_dict = self.find_component_by_item(clicked_item[0])
            if comp_dict and comp_dict['element']:
                self.edit_component_value(comp_dict)
                logging.debug(f"Double-clicked to edit component {comp_dict['element'].name}")

    def cancel_actions(self):
        self.wire_start = None
        if self.selection_box:
            self.canvas.delete(self.selection_box)
            self.selection_box = None
            logging.debug("Cancelled ongoing actions and cleared selection box")

    def refresh_simulation_visuals(self):
        if not hasattr(self, "last_node_voltages") or not hasattr(self, "last_source_currents"):
            return

        for comp in self.components:
            for item_id in comp.get("voltage_arrows", []):
                self.canvas.delete(item_id)
            comp["voltage_arrows"] = []
            for item_id in comp.get("current_arrows", []):
                self.canvas.delete(item_id)
            comp["current_arrows"] = []

        for wire in self.wires:
            for item_id in wire.voltage_arrows:
                self.canvas.delete(item_id)
            wire.voltage_arrows.clear()
            for item_id in wire.current_arrows:
                self.canvas.delete(item_id)
            wire.current_arrows.clear()

        self.visualize_component_potentials(self.last_node_voltages)
        self.compute_and_display_currents(self.last_node_voltages, self.last_source_currents)

    def reset_simulation_state(self):
        logging.info("Resetting entire simulation - clearing all results and closing windows")

        if hasattr(self, "last_node_voltages"):
            del self.last_node_voltages
        if hasattr(self, "last_node_map"):
            del self.last_node_map
        if hasattr(self, "last_source_currents"):
            del self.last_source_currents

        for comp in self.components:
            if comp.get("terminal_dot_ids"):
                for tid in comp["terminal_dot_ids"]:
                    self.canvas.tag_unbind(tid, "<Button-1>")

        for label_id in self.node_labels.values():
            self.canvas.delete(label_id)
        self.node_labels.clear()

        for comp in self.components:
            for item_id in comp.get("voltage_arrows", []):
                self.canvas.delete(item_id)
            comp["voltage_arrows"] = []
            for item_id in comp.get("current_arrows", []):
                self.canvas.delete(item_id)
            comp["current_arrows"] = []
            if "current" in comp:
                del comp["current"]

        for wire in self.wires:
            for item_id in wire.voltage_arrows:
                self.canvas.delete(item_id)
            wire.voltage_arrows.clear()
            for item_id in wire.current_arrows:
                self.canvas.delete(item_id)
            wire.current_arrows.clear()

        for window in self.winfo_children():
            if isinstance(window, tk.Toplevel):
                window.destroy()

        self.canvas.update()

        logging.info("Reset complete: all simulation results, arrows, labels, and result windows cleared")
        messagebox.showinfo("Reset Complete", "All simulation results have been cleared.")





    def save_circuit(self):
        """Save the current circuit state to a file."""
        circuit_state = {
            "components": [],
            "wires": [],
            "comp_index": self.comp_index
        }
        for comp in self.components:
            comp_copy = { key: comp[key] for key in comp if key not in ["canvas_items", "terminal_dot_ids", "abs_terminals"] }
            circuit_state["components"].append(comp_copy)
        for wire in self.wires:
            comp1_index = self.components.index(wire.comp1)
            comp2_index = self.components.index(wire.comp2)
            wire_copy = {
                "name": wire.name,
                "comp1_index": comp1_index,
                "term1_idx": wire.term1_idx,
                "comp2_index": comp2_index,
                "term2_idx": wire.term2_idx
            }
            circuit_state["wires"].append(wire_copy)
        file_path = filedialog.asksaveasfilename(defaultextension=".ckt", filetypes=[("Circuit Files", "*.ckt")])
        if file_path:
            with open(file_path, "wb") as f:
                pickle.dump(circuit_state, f)
            logging.info(f"Circuit saved to {file_path}")


    def load_circuit(self):
        """Load a saved circuit state from a file."""
        file_path = filedialog.askopenfilename(filetypes=[("Circuit Files", "*.ckt")])
        if file_path:
            with open(file_path, "rb") as f:
                circuit_state = pickle.load(f)
            for comp in self.components:
                for item in comp.get("canvas_items", []):
                    self.canvas.delete(item)
            for wire in self.wires:
                self.canvas.delete(wire.canvas_id)
            self.simulator.elements = []

            self.components = []
            self.wires = []
            self.comp_index = circuit_state.get("comp_index", {"resistor": 0, "voltage_source": 0, "current_source": 0})

            for comp_data in circuit_state["components"]:
                comp = comp_data.copy()
                comp["canvas_items"] = []
                comp["terminal_dot_ids"] = []
                self.components.append(comp)
                self.redraw_component(comp)
                if "element" in comp and comp["element"] is not None:
                    self.simulator.add_element(comp["element"])

            for wire_data in circuit_state["wires"]:
                try:
                    comp1 = self.components[wire_data["comp1_index"]]
                    comp2 = self.components[wire_data["comp2_index"]]
                except IndexError:
                    logging.error("Error loading wire: component index out of range.")
                    continue
                try:
                    x1, y1 = comp1["abs_terminals"][wire_data["term1_idx"]]
                    x2, y2 = comp2["abs_terminals"][wire_data["term2_idx"]]
                except (KeyError, IndexError):
                    logging.error("Error loading wire: terminal index out of range.")
                    continue
                wire_id = self.canvas.create_line(x1, y1, x2, y2, fill="gray", width=2)
                wire_element = Wire(
                    name=wire_data["name"],
                    comp1=comp1,
                    term1_idx=wire_data["term1_idx"],
                    comp2=comp2,
                    term2_idx=wire_data["term2_idx"],
                    canvas_id=wire_id
                )

                # Wire nodes are computed dynamically from connected components

                self.simulator.add_element(wire_element)
                self.wires.append(wire_element)
            self.update_wires()
            logging.info(f"Circuit loaded from {file_path}")





    def find_wire_by_item(self, item_id):
        for w in self.wires:
            if w.canvas_id == item_id:
                return w
        return None

    def place_component(self, comp_type, x, y):
        try:
            logging.debug(f"Placing component: {comp_type} at ({x}, {y})")
            if self.snap_to_grid.get():
                x = round(x / self.grid_size) * self.grid_size
                y = round(y / self.grid_size) * self.grid_size

            if comp_type == "ground":
                if any(c.get("is_ground") for c in self.components):
                    messagebox.showerror("Invalid Action", "Only one ground component is allowed.")
                    logging.error("Attempted to place multiple ground components.")
                    return

                ground_symbol = {
                    "element": None,
                    "comp_type": "ground",
                    "center": (x, y),
                    "rotation": 0,
                    "shape_points": [],
                    "terminals": [(-10, 0), (10, 0)],
                    "canvas_items": [],
                    "is_ground": True
                }
                radius = 10
                oval_id = self.canvas.create_oval(
                    x - radius, y - radius, x + radius, y + radius,
                    fill="black", outline="black"
                )
                ground_symbol['canvas_items'].append(oval_id)
                abs_terminals = []
                for tx, ty in ground_symbol["terminals"]:
                    tid = self.canvas.create_oval(
                        x + tx - 3, y + ty - 3, x + tx + 3, y + ty + 3,
                        fill="red"
                    )
                    ground_symbol['canvas_items'].append(tid)
                    abs_terminals.append((x + tx, y + ty))
                ground_symbol['abs_terminals'] = abs_terminals
                self.components.append(ground_symbol)
                logging.debug(f"Created ground with canvas IDs: {ground_symbol['canvas_items']}")
                self.canvas.tag_raise(oval_id)
                label_id = self.canvas.create_text(x, y + 20, text="Ground", fill="black", font=("Arial", 10, "bold"))
                ground_symbol['canvas_items'].append(label_id)
                return

            self.comp_index[comp_type] += 1
            idx = self.comp_index[comp_type]

            if comp_type == "resistor":
                name_prefix = "R"
                default_value = 1000.0
            elif comp_type == "voltage_source":
                name_prefix = "V"
                default_value = 5.0
            elif comp_type == "current_source":
                name_prefix = "I"
                default_value = 1.0
            else:
                messagebox.showerror("Unknown Component", f"Component type '{comp_type}' is not recognized.")
                logging.error(f"Unknown component type attempted to be placed: {comp_type}")
                return

            elem_name = f"{name_prefix}{idx}"
            element = CircuitElement(elem_name, default_value, comp_type)
            self.simulator.add_element(element)

            if comp_type == "resistor":
                shape_points = [(-20, 0), (-10, -10), (0, 10), (10, -10), (20, 0)]
            else:
                shape_points = []

            if comp_type == "voltage_source":
                terminals = [(0, -25), (0, 25)]
            else:
                terminals = [(-25, 0), (25, 0)]

            comp_dict = {
                "element": element,
                "comp_type": comp_type,
                "center": (x, y),
                "rotation": 0,
                "shape_points": shape_points,
                "terminals": terminals,
                "canvas_items": [],
            }
            self.components.append(comp_dict)
            self.redraw_component(comp_dict)
            logging.debug(f"Placed component: {comp_dict['element'].name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to place component '{comp_type}': {e}")



    def redraw_component(self, comp_dict):
        for it in comp_dict['canvas_items']:
            self.canvas.delete(it)
        comp_dict['canvas_items'].clear()

        cx, cy = comp_dict['center']
        rot = comp_dict['rotation']
        r_shape = self.rotate_points(comp_dict['shape_points'], rot)
        abs_shape = [(cx + px, cy + py) for px, py in r_shape]

        t_points = self.rotate_points(comp_dict['terminals'], rot)
        abs_terminals = [(cx + px, cy + py) for px, py in t_points]
        comp_dict['abs_terminals'] = abs_terminals

        ctype = comp_dict['comp_type']

        if ctype == "ground":
            radius = 10
            oval_id = self.canvas.create_oval(
                cx - radius, cy - radius, cx + radius, cy + radius,
                fill="black", outline="black"
            )
            comp_dict['canvas_items'].append(oval_id)
            abs_terminals = []
            for tx, ty in comp_dict["terminals"]:
                tid = self.canvas.create_oval(
                    cx + tx - 3, cy + ty - 3, cx + tx + 3, cy + ty + 3,
                    fill="red"
                )
                comp_dict['canvas_items'].append(tid)
                abs_terminals.append((cx + tx, cy + ty))
            comp_dict['abs_terminals'] = abs_terminals
            self.canvas.tag_raise(oval_id)
            label_id = self.canvas.create_text(cx, cy + 20, text="Ground", fill="black", font=("Arial", 10, "bold"))
            comp_dict['canvas_items'].append(label_id)
            return

        if ctype == "resistor":
            coords = []
            for p in abs_shape:
                coords.extend(p)
            item_id = self.canvas.create_line(*coords, width=2, fill="black")
            comp_dict['canvas_items'].append(item_id)

            angle_rad = math.radians(rot)
            label_offset = 25
            offset_x = -label_offset * math.sin(angle_rad)
            offset_y = label_offset * math.cos(angle_rad)

            label_x = cx + offset_x
            label_y = cy + offset_y
            label_id = self.canvas.create_text(label_x, label_y, text=f"{comp_dict['element'].name}\n{comp_dict['element'].value}Ω", fill="black", font=("Arial", 9), anchor="center")
            comp_dict['canvas_items'].append(label_id)
        elif ctype == "voltage_source":
            r = 20
            item_id = self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, width=2, outline="blue", fill="white")
            comp_dict['canvas_items'].append(item_id)

            angle_rad = math.radians(rot)
            label_offset = 35
            offset_x = label_offset * math.cos(angle_rad)
            offset_y = label_offset * math.sin(angle_rad)

            label_x = cx + offset_x
            label_y = cy + offset_y
            label_id = self.canvas.create_text(label_x, label_y, text=f"{comp_dict['element'].name}\n{comp_dict['element'].value}V", fill="blue", font=("Arial", 9, "bold"), anchor="center")
            comp_dict['canvas_items'].append(label_id)
        elif ctype == "current_source":
            r = 20
            item_id = self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, width=2, outline="green", fill="white")
            comp_dict['canvas_items'].append(item_id)
            arrow_id = self.canvas.create_line(cx - 5, cy + 10, cx - 5, cy - 10, arrow=tk.LAST, fill="green", width=2)
            comp_dict['canvas_items'].append(arrow_id)

            angle_rad = math.radians(rot)
            label_offset = 35
            offset_x = label_offset * math.cos(angle_rad)
            offset_y = label_offset * math.sin(angle_rad)

            label_x = cx + offset_x
            label_y = cy + offset_y
            label_id = self.canvas.create_text(label_x, label_y, text=f"{comp_dict['element'].name}\n{comp_dict['element'].value}A", fill="green", font=("Arial", 9, "bold"), anchor="center")
            comp_dict['canvas_items'].append(label_id)



        comp_dict['terminal_dot_ids'] = []
        for tx, ty in comp_dict['abs_terminals']:
            tid = self.canvas.create_oval(tx - 4, ty - 4, tx + 4, ty + 4, fill="red", outline="darkred", width=1)
            comp_dict['terminal_dot_ids'].append(tid)
            comp_dict['canvas_items'].append(tid)



        if comp_dict in self.selected_components:
            self.highlight_component(comp_dict, True)

        self.after_idle(self.refresh_simulation_visuals)

    def edit_component_value(self, comp_dict):
        elem = comp_dict['element']
        unit = {'resistor': 'Ω', 'voltage_source': 'V', 'current_source': 'A'}.get(elem.element_type, '')
        new_val = simpledialog.askfloat(
            "Edit Value",
            f"Value for {elem.name} ({elem.element_type}):",
            initialvalue=elem.value
        )
        if new_val is not None:
            if elem.element_type == 'resistor' and new_val <= 0:
                messagebox.showerror("Invalid Value", "Resistor value must be positive!")
                logging.error(f"Attempted to set negative/zero resistance for {elem.name}")
                return
            elem.value = new_val
            logging.debug(f"Updated {elem.name} to new value: {new_val}")
            self.redraw_component(comp_dict)

    def rotate_selected(self, angle_deg):
        for c in self.selected_components:
            c['rotation'] = (c['rotation'] + angle_deg) % 360
            cx, cy = c['center']
            rotated_terminals = self.rotate_points(c['terminals'], c['rotation'])
            c['abs_terminals'] = [(cx + tx, cy + ty) for tx, ty in rotated_terminals]
            self.redraw_component(c)
            logging.debug(f"Rotated component {c['element'].name if c['element'] else 'Ground'} by {angle_deg}°")
        self.update_wires()
        self.compute_node_positions()

    def delete_selected(self):
        if self.selected_components:
            for c in self.selected_components:
                if c['element']:
                    self.simulator.remove_element(c['element'])
                for it in c['canvas_items']:
                    self.canvas.delete(it)
                wires_to_remove = []
                for w in self.wires:
                    if w.comp1 == c or w.comp2 == c:
                        self.canvas.delete(w.canvas_id)
                        for arrow_id in w.voltage_arrows + w.current_arrows:
                            self.canvas.delete(arrow_id)
                        wires_to_remove.append(w)
                        logging.debug(f"Deleted wire {w}")
                for wr in wires_to_remove:
                    self.wires.remove(wr)
                    self.simulator.remove_element(wr)
                if c in self.components:
                    self.components.remove(c)
                    logging.debug(f"Deleted component {c['element'].name if c.get('element') else 'Ground'}")
            self.selected_components.clear()
            self.compute_node_positions()
            self.clear_component_arrows()

        if self.selected_wires:
            for w in self.selected_wires:
                self.canvas.delete(w.canvas_id)
                for arrow_id in w.voltage_arrows + w.current_arrows:
                    self.canvas.delete(arrow_id)
                if w in self.wires:
                    self.wires.remove(w)
                    self.simulator.remove_element(w)
                    logging.debug(f"Deleted wire {w}")
            self.selected_wires.clear()
            self.compute_node_positions()
            self.clear_component_arrows()

    def update_terminal_bindings(self):
        """
        Bind the terminal dots (red ovals) so that clicking them shows the node voltage.
        This is only activated after a simulation has been run.
        """
        for comp in self.components:
            if not comp.get("element"):
                continue
            if "terminal_dot_ids" in comp:
                for tid in comp["terminal_dot_ids"]:
                    self.canvas.tag_bind(tid, "<Button-1>", self.terminal_click, add="+")

    def handle_wire_click(self, x, y):
        item_ids = self.canvas.find_overlapping(x-3, y-3, x+3, y+3)
        if not item_ids:
            self.wire_start = None
            logging.debug("Clicked on empty space; resetting wire start")
            return
        for item_id in reversed(item_ids):
            comp_dict, term_idx = self.find_terminal(item_id)
            if comp_dict:
                if self.wire_start is None:
                    self.wire_start = (comp_dict, term_idx)
                    logging.debug(f"Wire start set to {comp_dict.get('element').name if comp_dict.get('element') else 'Ground'} terminal {term_idx}")
                    return
                else:
                    start_comp, start_term = self.wire_start
                    if start_comp == comp_dict and start_term == term_idx:
                        messagebox.showwarning("Invalid Wiring", "Cannot connect a terminal to itself.")
                        logging.warning("Attempted to connect a terminal to itself.")
                        self.wire_start = None
                        return
                    if start_comp == comp_dict:
                        messagebox.showwarning("Invalid Wiring", "Cannot connect two terminals of the same component.")
                        logging.warning("Attempted to connect two terminals of the same component.")
                        self.wire_start = None
                        return
                    if self.check_existing_wire(start_comp, start_term, comp_dict, term_idx):
                        messagebox.showwarning("Invalid Wiring", "A wire already exists between these terminals.")
                        logging.warning("Attempted to create a duplicate wire.")
                        self.wire_start = None
                        return
                    self.merge_and_create_wire(start_comp, start_term, comp_dict, term_idx)
                    self.wire_start = None
                    return
        self.wire_start = None
        logging.debug("No terminal found under cursor; resetting wire start")

    def check_existing_wire(self, compA, termA, compB, termB):
        for w in self.wires:
            if (w.comp1 == compA and w.term1_idx == termA and w.comp2 == compB and w.term2_idx == termB) or \
               (w.comp1 == compB and w.term1_idx == termB and w.comp2 == compA and w.term2_idx == termA):
                return True
        return False

    def merge_and_create_wire(self, compA, termA, compB, termB):
        eA = compA['element']
        eB = compB['element']
        nodeA = eA.nodes[termA] if eA else 0
        nodeB = eB.nodes[termB] if eB else 0

        if nodeA is None and nodeB is None:
            new_node = self.get_biggest_node() + 1
            if eA:
                eA.nodes[termA] = new_node
            if eB:
                eB.nodes[termB] = new_node

        elif nodeA is None:
            if eA:
                eA.nodes[termA] = nodeB
        elif nodeB is None:
            if eB:
                eB.nodes[termB] = nodeA

        else:
            if nodeA != nodeB:
                # Always merge into ground (0) if one node is ground
                if nodeA == 0:
                    for e in self.simulator.elements:
                        for i, n in enumerate(e.nodes):
                            if n == nodeB:
                                e.nodes[i] = 0
                    logging.debug(f"Merged node {nodeB} into ground")
                elif nodeB == 0:
                    for e in self.simulator.elements:
                        for i, n in enumerate(e.nodes):
                            if n == nodeA:
                                e.nodes[i] = 0
                    logging.debug(f"Merged node {nodeA} into ground")
                else:
                    # Normal merge: merge nodeB into nodeA
                    for e in self.simulator.elements:
                        for i, n in enumerate(e.nodes):
                            if n == nodeB:
                                e.nodes[i] = nodeA
                    logging.debug(f"Merged node {nodeB} into node {nodeA}")

        x1, y1 = compA['abs_terminals'][termA]
        x2, y2 = compB['abs_terminals'][termB]
        wire_id = self.canvas.create_line(x1, y1, x2, y2, fill="#555555", width=2.5, capstyle=tk.ROUND)

        wire_name = f"Wire{len([e for e in self.simulator.elements if e.element_type == 'wire']) + 1}"
        wire_element = Wire(name=wire_name, comp1=compA, term1_idx=termA, comp2=compB, term2_idx=termB, canvas_id=wire_id)

        # Wire nodes are now computed dynamically from connected components

        self.simulator.add_element(wire_element)
        self.wires.append(wire_element)
        logging.debug(f"Created and added wire: {wire_element} with nodes {wire_element.nodes}")

    def find_terminal(self, item_id):
        """
        Return the component dict and terminal index if the item_id is a terminal dot.
        """
        for c in self.components:
            if item_id in c['canvas_items']:
                abs_terminals = c.get('abs_terminals', [])
                for i, (tx, ty) in enumerate(abs_terminals):
                    coords = self.canvas.coords(item_id)
                    if len(coords) == 4:
                        ix = (coords[0] + coords[2]) / 2
                        iy = (coords[1] + coords[3]) / 2
                        if math.hypot(ix - tx, iy - ty) < 5:
                            return (c, i)
        return (None, None)

    def get_biggest_node(self):
        maxn = 0
        for e in self.simulator.elements:
            for nd in e.nodes:
                if nd and nd > maxn:
                    maxn = nd
        logging.debug(f"Biggest node found: {maxn}")
        return maxn

    def update_wires(self):
        for w in self.wires:
            x1, y1 = w.comp1['abs_terminals'][w.term1_idx]
            x2, y2 = w.comp2['abs_terminals'][w.term2_idx]
            self.canvas.coords(w.canvas_id, x1, y1, x2, y2)
        self.compute_node_positions()
        self.after_idle(self.refresh_simulation_visuals)

    def clear_selection(self):
        for c in self.selected_components:
            self.highlight_component(c, False)
        self.selected_components.clear()

        for w in self.selected_wires:
            self.highlight_wire(w, False)
        self.selected_wires.clear()

        logging.debug("Cleared all selections")

    def highlight_component(self, comp_dict, highlight):
        if not comp_dict['canvas_items']:
            return
        if highlight:
            if comp_dict['comp_type'] == "ground":
                self.canvas.itemconfig(comp_dict['canvas_items'][0], fill="yellow")
            elif comp_dict['comp_type'] == "resistor":
                self.canvas.itemconfig(comp_dict['canvas_items'][0], fill="blue")
            elif comp_dict['comp_type'] == "voltage_source":
                self.canvas.itemconfig(comp_dict['canvas_items'][0], outline="blue", width=3)
            elif comp_dict['comp_type'] == "current_source":
                self.canvas.itemconfig(comp_dict['canvas_items'][0], outline="green", width=3)
            logging.debug(f"Highlighted component {comp_dict.get('element').name if comp_dict.get('element') else 'Ground'}")
        else:
            if comp_dict['comp_type'] == "ground":
                self.canvas.itemconfig(comp_dict['canvas_items'][0], fill="black")
            elif comp_dict['comp_type'] == "resistor":
                self.canvas.itemconfig(comp_dict['canvas_items'][0], fill="black")
            elif comp_dict['comp_type'] == "voltage_source":
                self.canvas.itemconfig(comp_dict['canvas_items'][0], outline="blue", width=2)
            elif comp_dict['comp_type'] == "current_source":
                self.canvas.itemconfig(comp_dict['canvas_items'][0], outline="green", width=2)
            logging.debug(f"Unhighlighted component {comp_dict.get('element').name if comp_dict.get('element') else 'Ground'}")

    def highlight_wire(self, wire_obj, highlight):
        if highlight:
            self.canvas.itemconfig(wire_obj.canvas_id, fill="blue", width=4)
            logging.debug(f"Highlighted wire {wire_obj}")
        else:
            self.canvas.itemconfig(wire_obj.canvas_id, fill="#555555", width=2.5)
            logging.debug(f"Unhighlighted wire {wire_obj}")

    def find_component_by_item(self, item_id):
        """
        Return the component dict if item_id belongs to any of this component's canvas_items.
        """
        for c in self.components:
            if item_id in c['canvas_items']:
                return c
        return None

    def terminal_click(self, event):
        if not (hasattr(self, "last_node_voltages") and hasattr(self, "last_node_map")):
            return

        clicked_items = self.canvas.find_withtag("current")
        if not clicked_items:
            return
        item_id = clicked_items[0]

        comp, term_idx = self.find_terminal(item_id)
        if comp is None or not comp.get("element"):
            return

        node_id = comp["element"].nodes[term_idx]
        if node_id == 0:
            voltage = 0.0
        else:
            node_idx = self.last_node_map.get(node_id, None)
            if node_idx is None:
                return
            voltage = self.last_node_voltages[node_idx]

        messagebox.showinfo("Node Voltage", f"Voltage at terminal: {voltage:.5f} V")



    def simulate(self):
        self.clear_component_arrows()

        if not self.simulator.elements:
            messagebox.showerror("Simulation Error", "No circuit elements to simulate!")
            logging.error("Simulation failed: No elements in circuit.")
            return

        non_wire_elements = [e for e in self.simulator.elements if e.element_type != 'wire']
        if not non_wire_elements:
            messagebox.showerror("Simulation Error", "Circuit contains only wires!")
            logging.error("Simulation failed: No active components.")
            return

        for e in self.simulator.elements:
            if e.element_type in ['wire']:
                continue
            if None in e.nodes:
                messagebox.showerror("Simulation Error",
                    f"Element {e.name} is not fully connected! Each terminal must be wired.")
                logging.error(f"Simulation failed: Element {e.name} has unconnected terminals.")
                return

        ground_connected = any(0 in e.nodes for e in self.simulator.elements if e.element_type != 'wire')
        if not ground_connected:
            messagebox.showerror("Simulation Error", "No ground connection! Ensure the circuit is grounded (connected to node 0).")
            logging.error("Simulation failed: No ground connection detected.")
            return

        node_voltages, source_currents = self.simulator.solve_circuit()
        if node_voltages is None:
            logging.error("Simulation failed: Singular matrix encountered.")
            return


        self.last_node_voltages = node_voltages
        self.last_node_map = self.simulator.node_map.copy()
        self.last_source_currents = source_currents
        self.update_terminal_bindings()


        self.compute_node_positions()

        self.visualize_component_potentials(node_voltages)
        self.compute_and_display_currents(node_voltages, source_currents)


        results_win = tk.Toplevel(self)
        results_win.title("Simulation Results")
        text = tk.Text(results_win, width=60, height=25)
        text.pack()

        text.insert(tk.END, "== Node Voltages ==\n")
        for node_id, idx in self.simulator.node_map.items():
            voltage = node_voltages[idx]
            text.insert(tk.END, f"Node {node_id}: {voltage:.7f} V\n")

        text.insert(tk.END, "\n== Elements ==\n")
        for e in self.simulator.elements:
            if e.element_type == 'wire':
                continue

            if e.element_type in ['resistor', 'voltage_source', 'current_source']:
                node1 = e.nodes[0]
                node2 = e.nodes[1]
                v1 = 0.0 if node1 == 0 else node_voltages[self.simulator.node_map[node1]]
                v2 = 0.0 if node2 == 0 else node_voltages[self.simulator.node_map[node2]]
                voltage_diff = v1 - v2

                current_val = None
                for comp in self.components:
                    if comp.get("element") == e and "current" in comp:
                        current_val = comp["current"]
                        break
                if current_val is not None:
                    current_str = f", I={current_val:.2e} A"
                else:
                    current_str = ""

                text.insert(tk.END,
                    f"{e.name} ({e.element_type}) - nodes={e.nodes}, value={e.value}, V={voltage_diff:.7f} V{current_str}\n")
            else:
                text.insert(tk.END, f"{e.name} ({e.element_type}) - nodes={e.nodes}, value={e.value}\n")


        vsrcs = self.simulator.voltage_sources
        if len(vsrcs) > 0:
            text.insert(tk.END, "\n== Voltage Source Currents ==\n")
            for i, vs in enumerate(vsrcs):
                vs_index = next((idx for idx, source in enumerate(vsrcs) if source is vs), None)
                if vs_index is not None and vs_index < len(source_currents):
                    current = source_currents[vs_index]
                    text.insert(tk.END, f"{vs.name} current: {current:.7e} A\n")
                else:
                    text.insert(tk.END, f"{vs.name} current: N/A\n")
                    logging.error(f"Voltage Source {vs.name}: Simulation did not return a current value.")

        text.config(state=tk.DISABLED)
        logging.debug("Simulation completed successfully.")

    def visualize_voltage_differences(self, node_voltages):
        """
        Draw voltage difference arrows on wires and display node voltage labels.
        """
        for w in self.wires:
            for arrow_id in w.voltage_arrows:
                self.canvas.delete(arrow_id)
            w.voltage_arrows.clear()

        for w in self.wires:
            node1 = w.comp1['element'].nodes[w.term1_idx] if w.comp1.get('element') else 0
            node2 = w.comp2['element'].nodes[w.term2_idx] if w.comp2.get('element') else 0
            v1 = 0.0 if node1 == 0 else node_voltages[self.simulator.node_map[node1]]
            v2 = 0.0 if node2 == 0 else node_voltages[self.simulator.node_map[node2]]
            voltage_diff = v1 - v2

            if voltage_diff == 0:
                continue

            if voltage_diff > 0:
                start = w.comp1['abs_terminals'][w.term1_idx]
                end = w.comp2['abs_terminals'][w.term2_idx]
            else:
                start = w.comp2['abs_terminals'][w.term2_idx]
                end = w.comp1['abs_terminals'][w.term1_idx]
            arrow_color = "red" if voltage_diff > 0 else "blue"
            arrow_ids = self.draw_arrow_with_label(start, end, arrow_color, 2, 30, "{:.2f} V", abs(voltage_diff))
            w.voltage_arrows.extend(arrow_ids)

        for node_id, pos in self.node_positions.items():
            if node_id == 0:
                continue
            node_idx = self.simulator.node_map.get(node_id)
            if node_idx is not None:
                voltage = node_voltages[node_idx]
                self.canvas.create_text(pos[0], pos[1] - 20,
                                        text=f"{voltage:.2f} V",
                                        fill="black", font=("Arial", 10, "bold"))
                logging.debug(f"Displayed voltage {voltage:.2f} V at node {node_id}")


    def visualize_component_potentials(self, node_voltages):
        for comp in self.components:
            if comp.get("element") and comp["element"].element_type != "wire":
                node1 = comp["element"].nodes[0]
                node2 = comp["element"].nodes[1]
                v1 = 0.0 if node1 == 0 else node_voltages[self.simulator.node_map[node1]]
                v2 = 0.0 if node2 == 0 else node_voltages[self.simulator.node_map[node2]]
                voltage_diff = v1 - v2
                if abs(voltage_diff) < 1e-6:
                    continue
                if voltage_diff > 0:
                    start = comp["abs_terminals"][0]
                    end = comp["abs_terminals"][1]
                else:
                    start = comp["abs_terminals"][1]
                    end = comp["abs_terminals"][0]
                arrow_color = "purple"
                arrow_ids = self.draw_arrow_with_label(start, end, arrow_color, 1.5, 40, "{:.2f}V", abs(voltage_diff), offset_distance=50, is_voltage=True)
                comp.setdefault("voltage_arrows", []).extend(arrow_ids)
                logging.debug(f"Drew potential arrow on {comp['element'].name} with {voltage_diff:.2f} V")




    def compute_and_display_currents(self, node_voltages, source_currents):
        self.clear_component_arrows()

        for comp in self.components:
            if not comp.get('element'):
                continue

            elem = comp['element']

            if elem.element_type == 'wire':
                continue

            else:
                if elem.element_type == 'resistor':
                    if elem.value == 0:
                        logging.error(f"Resistor {elem.name} has zero resistance. Cannot calculate current.")
                        continue
                    node1, node2 = elem.nodes[0], elem.nodes[1]
                    v1 = 0.0 if node1 == 0 else node_voltages[self.simulator.node_map[node1]]
                    v2 = 0.0 if node2 == 0 else node_voltages[self.simulator.node_map[node2]]
                    current = (v1 - v2) / elem.value
                elif elem.element_type == 'voltage_source':
                    vs_index = next((i for i, vs in enumerate(self.simulator.voltage_sources) if vs is elem), None)
                    if vs_index is not None and vs_index < len(source_currents):
                        current = source_currents[vs_index]
                    else:
                        current = 0.0
                        logging.error(f"Voltage Source {elem.name}: Simulation did not return a current value.")
                elif elem.element_type == 'current_source':
                    current = elem.value
                else:
                    continue

            comp['current'] = current

            if abs(current) < 1e-12:
                continue

            if current > 0:
                start_pos = comp['abs_terminals'][0]
                end_pos = comp['abs_terminals'][1]
                color = "darkgreen"
            else:
                start_pos = comp['abs_terminals'][1]
                end_pos = comp['abs_terminals'][0]
                color = "darkorange"

            arrow_ids = self.draw_arrow_with_label(start_pos, end_pos, color, 2, 35, "{:.2e}A", abs(current), offset_distance=30)
            comp.setdefault('current_arrows', []).extend(arrow_ids)
            logging.debug(f"Drew current arrow on element {elem.name} with current {current:.2e} A")



    def compute_node_positions(self):
        """
        Compute the positions of each node based on connected terminals from all elements.
        """
        self.node_positions.clear()

        node_to_positions = {}

        for e in self.simulator.elements:
            if e.element_type == 'wire':
                node1 = e.nodes[0]
                node2 = e.nodes[1]
                if node1 is not None:
                    pos1 = e.comp1['abs_terminals'][e.term1_idx]
                    node_to_positions.setdefault(node1, []).append(pos1)
                if node2 is not None:
                    pos2 = e.comp2['abs_terminals'][e.term2_idx]
                    node_to_positions.setdefault(node2, []).append(pos2)
            else:
                comp_dict = next((c for c in self.components if c['element'] == e), None)
                if comp_dict:
                    for term_idx, pos in enumerate(comp_dict['abs_terminals']):
                        node = e.nodes[term_idx]
                        if node is not None:
                            node_to_positions.setdefault(node, []).append(pos)

        for node_id, positions in node_to_positions.items():
            if node_id == 0:
                continue
            avg_x = sum(p[0] for p in positions) / len(positions)
            avg_y = sum(p[1] for p in positions) / len(positions)
            self.node_positions[node_id] = (avg_x, avg_y)
            logging.debug(f"Node {node_id} positioned at ({avg_x}, {avg_y})")

    def update_node_labels(self, node_voltages):
        """
        Create or update labels on the canvas to display node voltages with color-coding.
        """
        for label_id in self.node_labels.values():
            self.canvas.delete(label_id)
        self.node_labels.clear()

        high_threshold = 5.0
        low_threshold = -5.0

        for node_id, pos in self.node_positions.items():
            node_idx = self.simulator.node_map.get(node_id, None)
            if node_idx is None:
                logging.error(f"Node ID {node_id} not found in node_map.")
                continue

            voltage = node_voltages[node_idx]
            x, y = pos

            if voltage > high_threshold:
                color = "darkred"
            elif voltage > 0.5:
                color = "red"
            elif voltage < low_threshold:
                color = "darkblue"
            elif voltage < -0.5:
                color = "blue"
            else:
                color = "black"

            label_text = f"V{node_id} = {voltage:.5f} V"
            label_id = self.canvas.create_text(x, y - 15, text=label_text, fill=color, font=("Arial", 10, "bold"))
            self.node_labels[node_id] = label_id
            logging.debug(f"Created label for Node {node_id} at ({x}, {y - 15}) with voltage {voltage:.5f} V and color {color}")

        ground_nodes = [c for c in self.components if c.get("is_ground")]
        if ground_nodes:
            ground = ground_nodes[0]
            cx, cy = ground['center']
            label_text = f"Ground (V0) = 0.00 V"
            label_id = self.canvas.create_text(cx, cy + 30, text=label_text, fill="black", font=("Arial", 10, "bold", "italic"))
            self.node_labels[0] = label_id
            logging.debug(f"Created label for Ground node at ({cx}, {cy + 30})")


    def draw_arrow_with_label(self, start, end, arrow_color, arrow_thickness, arrow_length, label_format, value, offset_distance=30, is_voltage=False):
        angle = math.atan2(end[1] - start[1], end[0] - start[0])

        offset_x = -offset_distance * math.sin(angle)
        offset_y = offset_distance * math.cos(angle)

        mid_x = (start[0] + end[0]) / 2
        mid_y = (start[1] + end[1]) / 2
        arrow_start = (mid_x + offset_x, mid_y + offset_y)
        arrow_end = (arrow_start[0] + arrow_length * math.cos(angle),
                    arrow_start[1] + arrow_length * math.sin(angle))

        arrow_id = self.canvas.create_line(
            arrow_start[0], arrow_start[1],
            arrow_end[0], arrow_end[1],
            arrow=tk.LAST, fill=arrow_color, width=arrow_thickness)

        label_text = label_format.format(value)
        label_x = (arrow_start[0] + arrow_end[0]) / 2
        label_y = (arrow_start[1] + arrow_end[1]) / 2

        label_offset = 15
        label_x += -label_offset * math.sin(angle)
        label_y += label_offset * math.cos(angle)

        label_id = self.canvas.create_text(
            label_x, label_y,
            text=label_text, fill=arrow_color,
            font=("Arial", 9, "bold"),
            anchor="center")

        return arrow_id, label_id



    def clear_component_arrows(self):
        """
        Remove all current arrows *and* voltage arrows from components,
        and do the same for wires if you want to ensure everything is cleared.
        """
        for comp in self.components:
            for arrow_id in comp.get('current_arrows', []):
                self.canvas.delete(arrow_id)
            comp['current_arrows'] = []

            for arrow_id in comp.get('voltage_arrows', []):
                self.canvas.delete(arrow_id)
            comp['voltage_arrows'] = []

        for w in self.wires:
            for arrow_id in w.voltage_arrows:
                self.canvas.delete(arrow_id)
            w.voltage_arrows.clear()




    def create_voltage_legend(self):
        """
        Create a legend explaining the color-coding of node voltages.
        """
        legend_label = ttk.Label(self.left_frame, text="Voltage Legend", font=("Arial", 10, "bold"))
        legend_label.pack(pady=(20, 5))

        legend_entries = [
            ("V > 5V", "darkred"),
            ("0.5V < V ≤ 5V", "red"),
            ("V < -5V", "darkblue"),
            ("-5V ≤ V < -0.5V", "blue"),
            ("-0.5V ≤ V ≤ 0.5V", "black")
        ]

        for label, color in legend_entries:
            frame = tk.Frame(self.left_frame)
            frame.pack(anchor="w", pady=1)
            color_box = tk.Canvas(frame, width=15, height=15, highlightthickness=0)
            color_box.pack(side=tk.LEFT)
            color_box.create_rectangle(0, 0, 15, 15, fill=color, outline=color)
            label_widget = ttk.Label(frame, text=label, foreground=color)
            label_widget.pack(side=tk.LEFT, padx=(5, 0))


