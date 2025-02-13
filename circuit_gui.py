from imports import *
from circuit_simulator import CircuitSimulator
from circuit_elements import CircuitElement, Wire
import pickle
from tkinter import filedialog

# ---------------------------------------------------------------------------------------
# GUI: CircuitGUI with Enhanced Visualization and Logging
# ---------------------------------------------------------------------------------------

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
            self.text_widget.yview(tk.END)  # Auto-scroll to the end
        self.text_widget.after(0, append)


class CircuitGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Advanced Circuit Simulator")

        # Configure window size
        self.geometry("1500x800")  # Increased width to accommodate log panel

        # Main simulator / netlist
        self.simulator = CircuitSimulator()

        # Frames
        self.left_frame = tk.Frame(self, width=220)
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.canvas_frame = tk.Frame(self)
        self.canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.right_frame = tk.Frame(self, width=300)
        self.right_frame.pack(side=tk.LEFT, fill=tk.BOTH)

        # Canvas
        self.canvas = tk.Canvas(self.canvas_frame, bg="#fafafa", width=900, height=700)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Log Display
        self.log_text = tk.Text(self.right_frame, state='disabled', wrap='word')
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text_label = ttk.Label(self.right_frame, text="Log Output", font=("Arial", 12, "bold"))
        self.log_text_label.pack(anchor='nw')

        # Set up logging to GUI
        gui_handler = TextHandler(self.log_text)
        gui_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(gui_handler)

        # Tool & States
        self.active_tool = tk.StringVar(value="select")
        self.snap_to_grid = tk.BooleanVar(value=False)
        self.grid_size = 20

        # Track components and wires
        self.components = []  # each is a dict with positions, shape, terminals
        self.wires = []       # list of Wire objects
        self.comp_index = {"resistor": 0, "voltage_source": 0, "current_source": 0}

        # For selection
        self.selected_components = []
        self.selected_wires = []   # Track selected wires

        # For dragging
        self.dragging = False
        self.last_mouse_pos = (0, 0)
        self.selection_box = None

        # For wire creation
        self.wire_start = None  # (comp_dict, term_idx)

        # Node positions for visualization
        self.node_positions = {}  # node_id -> (x, y)
        self.node_labels = {}     # node_id -> label_id

        # Voltage and Current Arrows
        self.component_voltage_arrows = {}  # component -> list of arrow IDs
        self.component_current_arrows = {}  # component -> list of arrow IDs

        # Build UI on the left
        self.build_left_ui()

        # # Create Voltage Legend
        # self.create_voltage_legend()

        # Canvas bindings
        self.canvas.bind("<Button-1>", self.on_left_down)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_up)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)

        # Keyboard
        self.canvas.bind("<KeyPress-r>", lambda e: self.rotate_selected(90))
        self.canvas.bind("<KeyPress-Delete>", lambda e: self.delete_selected())
        self.canvas.bind("<KeyPress-Escape>", lambda e: self.cancel_actions())
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

    # -----------------------------------------------------------------------------------
    # Build Left UI
    # -----------------------------------------------------------------------------------
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
               command=lambda: self.set_tool("ground")).pack(fill=tk.X, pady=2)  # Add Ground Button
        
        ttk.Button(self.left_frame, text="Save Circuit", command=self.save_circuit).pack(fill=tk.X, pady=2)
        ttk.Button(self.left_frame, text="Load Circuit", command=self.load_circuit).pack(fill=tk.X, pady=2)

        ttk.Label(self.left_frame, text="Actions", font=("Arial", 12, "bold")).pack(pady=5)
        ttk.Button(self.left_frame, text="Rotate (R key)",
                   command=lambda: self.rotate_selected(90)).pack(fill=tk.X, pady=2)
        ttk.Button(self.left_frame, text="Delete (Del key)",
                   command=self.delete_selected).pack(fill=tk.X, pady=2)
        
        

        ttk.Button(self.left_frame, text="Simulate",
                   command=self.simulate).pack(side=tk.BOTTOM, fill=tk.X, pady=4)
        
        # ---- NEW: Add a button to reset the simulation state
        ttk.Button(self.left_frame, text="Reset Simulation State",
               command=self.reset_simulation_state).pack(side=tk.BOTTOM, fill=tk.X, pady=4)
        
        


        ttk.Checkbutton(self.left_frame, text="Snap to Grid", variable=self.snap_to_grid).pack(side=tk.BOTTOM, padx=5, pady=5)

    # -----------------------------------------------------------------------------------
    # Tool Setting
    # -----------------------------------------------------------------------------------
    def set_tool(self, tool):
        self.active_tool.set(tool)
        self.wire_start = None
        self.clear_selection()
        logging.debug(f"Tool set to {tool}")

    # -----------------------------------------------------------------------------------
    # Event Handlers
    # -----------------------------------------------------------------------------------
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
            # Check if we clicked on an existing item
            clicked_items = self.canvas.find_overlapping(x-5, y-5, x+5, y+5)
            if not clicked_items:
                # No items => start box selection
                self.clear_selection()
                self.selection_box = self.canvas.create_rectangle(x, y, x, y, outline="blue", dash=(2, 2))
                logging.debug("Started box selection")
                return

            # Iterate from top to bottom
            for item_id in reversed(clicked_items):
                # 1) Try to find a component
                comp_dict = self.find_component_by_item(item_id)
                if comp_dict:
                    # Already selected => a second click => edit value
                    if comp_dict in self.selected_components:
                        # Single-click on a selected component => open value dialog
                        self.edit_component_value(comp_dict)
                        logging.debug(f"Editing value of component {comp_dict['element'].name if comp_dict['element'] else 'Ground'}")
                        return
                    # If SHIFT is held, toggle selection
                    if event.state & 0x0001:  # SHIFT key
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

                    # Start dragging
                    self.dragging = True
                    self.last_mouse_pos = (x, y)
                    logging.debug("Started dragging components")
                    return

                # 2) If no component, try a wire
                wire_obj = self.find_wire_by_item(item_id)
                if wire_obj:
                    # SHIFT toggles wire selection
                    if event.state & 0x0001:  # SHIFT
                        if wire_obj in self.selected_wires:
                            self.selected_wires.remove(wire_obj)
                            self.highlight_wire(wire_obj, False)
                            logging.debug(f"Deselected wire {wire_obj}")
                        else:
                            self.selected_wires.append(wire_obj)
                            self.highlight_wire(wire_obj, True)
                            logging.debug(f"Selected wire {wire_obj}")
                    else:
                        # Single wire selection
                        self.clear_selection()
                        self.selected_wires.append(wire_obj)
                        self.highlight_wire(wire_obj, True)
                        logging.debug(f"Selected wire {wire_obj}")
                    return

            # If no component or wire found, start box selection
            self.clear_selection()
            self.selection_box = self.canvas.create_rectangle(x, y, x, y, outline="blue", dash=(2, 2))
            logging.debug("Started box selection")

    def on_left_up(self, event):
        self.dragging = False
        if self.selection_box:
            x1, y1, x2, y2 = self.canvas.coords(self.selection_box)
            self.canvas.delete(self.selection_box)
            self.selection_box = None
            # Normalize coordinates
            if x2 < x1:
                x1, x2 = x2, x1
            if y2 < y1:
                y1, y2 = y2, y1
            # Find all components whose center is within the selection box
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
                # Update terminal positions
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
            if comp_dict and comp_dict['element']:  # Only editable if it's not ground
                self.edit_component_value(comp_dict)
                logging.debug(f"Double-clicked to edit component {comp_dict['element'].name}")

    def cancel_actions(self):
        self.wire_start = None
        if self.selection_box:
            self.canvas.delete(self.selection_box)
            self.selection_box = None
            logging.debug("Cancelled ongoing actions and cleared selection box")

    def reset_simulation_state(self):
        """
        Reset only the simulation result visuals (voltages, arrows, terminal bindings)
        while keeping the existing node connectivity (node map) intact.
        This way, the previous node map remains and can be updated later.
        """
        # Clear only the simulation result data, not the connectivity
        if hasattr(self, "last_node_voltages"):
            del self.last_node_voltages
        # DO NOT delete last_node_map so that connectivity is preserved

        # Unbind terminal click events so that wiring logic is reactivated.
        for comp in self.components:
            if comp.get("terminal_dot_ids"):
                for tid in comp["terminal_dot_ids"]:
                    self.canvas.tag_unbind(tid, "<Button-1>")
        
        # Remove all node voltage labels.
        for label_id in self.node_labels.values():
            self.canvas.delete(label_id)
        self.node_labels.clear()

        # Remove all voltage and current arrows from each component.
        for comp in self.components:
            for arrow_id in comp.get("voltage_arrows", []):
                self.canvas.delete(arrow_id)
            comp["voltage_arrows"] = []
            for arrow_id in comp.get("current_arrows", []):
                self.canvas.delete(arrow_id)
            comp["current_arrows"] = []

        # Remove all voltage arrows drawn on wires.
        for wire in self.wires:
            for arrow_id in wire.voltage_arrows:
                self.canvas.delete(arrow_id)
            wire.voltage_arrows.clear()

        # Optionally, if you have any other simulation visuals, clear them here.

        # Finally, update node positions based on current component connectivity.
        # This will update your internal node map as needed.
        self.compute_node_positions()
        
        logging.info("Reset simulation state; simulation results cleared but node map preserved for updating.")





    def save_circuit(self):
        """Save the current circuit state to a file."""
        circuit_state = {
            "components": [],
            "wires": [],
            "comp_index": self.comp_index
        }
        # For each component, store only the essential data (omit non‑serializable keys)
        for comp in self.components:
            comp_copy = { key: comp[key] for key in comp if key not in ["canvas_items", "terminal_dot_ids", "abs_terminals"] }
            circuit_state["components"].append(comp_copy)
        # For each wire, store the indices of the component references.
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
            # Clear existing components and wires from the canvas
            for comp in self.components:
                for item in comp.get("canvas_items", []):
                    self.canvas.delete(item)
            for wire in self.wires:
                self.canvas.delete(wire.canvas_id)
            # Also clear the simulator’s element list:
            self.simulator.elements = []
            
            self.components = []
            self.wires = []
            self.comp_index = circuit_state.get("comp_index", {"resistor": 0, "voltage_source": 0, "current_source": 0})
            
            # Rebuild components.
            for comp_data in circuit_state["components"]:
                comp = comp_data.copy()  # shallow copy is fine
                # IMPORTANT: Reinitialize keys for GUI objects.
                comp["canvas_items"] = []
                comp["terminal_dot_ids"] = []
                self.components.append(comp)
                self.redraw_component(comp)
                # *** NEW *** Re-add the component's underlying element to the simulator.
                if "element" in comp and comp["element"] is not None:
                    self.simulator.add_element(comp["element"])
            
            # Rebuild wires using stored component indices.
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
                self.simulator.add_element(wire_element)
                self.wires.append(wire_element)
            self.update_wires()
            logging.info(f"Circuit loaded from {file_path}")





    # -----------------------------------------------------------------------------------
    # find_wire_by_item => so we can detect wire selection
    # -----------------------------------------------------------------------------------
    def find_wire_by_item(self, item_id):
        for w in self.wires:
            if w.canvas_id == item_id:
                return w
        return None

    # -----------------------------------------------------------------------------------
    # Component & Value Editing
    # -----------------------------------------------------------------------------------
    def place_component(self, comp_type, x, y):
        try:
            logging.debug(f"Placing component: {comp_type} at ({x}, {y})")
            # Snap to grid if enabled
            if self.snap_to_grid.get():
                x = round(x / self.grid_size) * self.grid_size
                y = round(y / self.grid_size) * self.grid_size

            # Handle ground specially
            if comp_type == "ground":
                # Ensure only one ground exists
                if any(c.get("is_ground") for c in self.components):
                    messagebox.showerror("Invalid Action", "Only one ground component is allowed.")
                    logging.error("Attempted to place multiple ground components.")
                    return

                ground_symbol = {
                    "element": None,  # Ground doesn't have a CircuitElement
                    "comp_type": "ground",
                    "center": (x, y),
                    "rotation": 0,
                    "shape_points": [],
                    "terminals": [(-10, 0), (10, 0)],  # Horizontal terminals for ground
                    "canvas_items": [],
                    "is_ground": True
                }
                radius = 10  # Adjust as needed for visibility
                # Draw the ground symbol (a filled disk)
                oval_id = self.canvas.create_oval(
                    x - radius, y - radius, x + radius, y + radius,
                    fill="black", outline="black"
                )
                ground_symbol['canvas_items'].append(oval_id)
                # Draw terminal dots
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

            # Increment component index for regular components
            self.comp_index[comp_type] += 1
            idx = self.comp_index[comp_type]

            # Set default value and name prefix based on type
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

            # Set shape points (if any)
            if comp_type == "resistor":
                shape_points = [(-20, 0), (-10, -10), (0, 10), (10, -10), (20, 0)]
            else:
                shape_points = []

            # Set terminal positions: voltage sources get vertical terminals;
            # others (resistor, current source) get horizontal terminals.
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
        # Remove old canvas items
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
            # Redraw the ground symbol (filled disk)
            radius = 10  # Must match the radius in place_component
            oval_id = self.canvas.create_oval(
                cx - radius, cy - radius, cx + radius, cy + radius,
                fill="black", outline="black"
            )
            comp_dict['canvas_items'].append(oval_id)
            # Redraw terminal dots
            abs_terminals = []
            for tx, ty in comp_dict["terminals"]:
                tid = self.canvas.create_oval(
                    cx + tx - 3, cy + ty - 3, cx + tx + 3, cy + ty + 3,
                    fill="red"
                )
                comp_dict['canvas_items'].append(tid)
                abs_terminals.append((cx + tx, cy + ty))
            comp_dict['abs_terminals'] = abs_terminals  # Set abs_terminals
            # Bring ground symbol to the front
            self.canvas.tag_raise(oval_id)
            # Add ground label
            label_id = self.canvas.create_text(cx, cy + 20, text="Ground", fill="black", font=("Arial", 10, "bold"))
            comp_dict['canvas_items'].append(label_id)
            return

        if ctype == "resistor":
            coords = []
            for p in abs_shape:
                coords.extend(p)
            item_id = self.canvas.create_line(*coords, width=2, fill="black")
            comp_dict['canvas_items'].append(item_id)
            # Add resistor label
            mid_index = len(coords) // 4  # Since coords are [x1,y1,x2,y2,...]
            label_x = coords[mid_index*2] + 5  # Slight offset
            label_y = coords[mid_index*2+1] + 5
            label_id = self.canvas.create_text(label_x, label_y, text=f"{comp_dict['element'].name}\n{comp_dict['element'].value}Ω", fill="black", font=("Arial", 10))
            comp_dict['canvas_items'].append(label_id)
        elif ctype == "voltage_source":
            r = 20
            item_id = self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, width=2, outline="blue")
            comp_dict['canvas_items'].append(item_id)
            plus_id = self.canvas.create_text(cx, cy - 10, text="+", fill="blue")
            minus_id = self.canvas.create_text(cx, cy + 10, text="-", fill="blue")
            comp_dict['canvas_items'].extend([plus_id, minus_id])
            # Add voltage source label
            label_id = self.canvas.create_text(cx, cy, text=f"{comp_dict['element'].name}\n{comp_dict['element'].value}V", fill="blue", font=("Arial", 10))
            comp_dict['canvas_items'].append(label_id)
        elif ctype == "current_source":
            r = 20
            item_id = self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, width=2, outline="green")
            comp_dict['canvas_items'].append(item_id)
            arrow_id = self.canvas.create_line(cx, cy + 10, cx, cy - 10, arrow=tk.LAST, fill="green", width=2)
            comp_dict['canvas_items'].append(arrow_id)
            # Add current source label
            label_id = self.canvas.create_text(cx, cy, text=f"{comp_dict['element'].name}\n{comp_dict['element'].value}A", fill="green", font=("Arial", 10))
            comp_dict['canvas_items'].append(label_id)

        # Draw terminal dots for non-ground components
        
        
        comp_dict['terminal_dot_ids'] = []
        for tx, ty in comp_dict['abs_terminals']:
            tid = self.canvas.create_oval(tx - 8, ty - 8, tx + 8, ty + 8, fill="red")
            comp_dict['terminal_dot_ids'].append(tid)
            comp_dict['canvas_items'].append(tid)



        # Re-highlight if it was selected
        if comp_dict in self.selected_components:
            self.highlight_component(comp_dict, True)

    def edit_component_value(self, comp_dict):
        """
        Prompt the user to change the numeric value of a selected component.
        """
        elem = comp_dict['element']
        unit = {'resistor': 'Ω', 'voltage_source': 'V', 'current_source': 'A'}.get(elem.element_type, '')
        new_val = simpledialog.askfloat(
            "Edit Value",
            f"Value for {elem.name} ({elem.element_type}):",
            initialvalue=elem.value
        )
        if new_val is not None:
            elem.value = new_val
            logging.debug(f"Updated {elem.name} to new value: {new_val}")
            # Update the label
            for item_id in comp_dict['canvas_items']:
                if 'text' in self.canvas.type(item_id):
                    if elem.element_type == 'resistor':
                        self.canvas.itemconfig(item_id, text=f"{elem.name}\n{elem.value}Ω")
                    elif elem.element_type == 'voltage_source':
                        self.canvas.itemconfig(item_id, text=f"{elem.name}\n{elem.value}V")
                    elif elem.element_type == 'current_source':
                        self.canvas.itemconfig(item_id, text=f"{elem.name}\n{elem.value}A")
                    break

    # -----------------------------------------------------------------------------------
    # Rotating & Deleting
    # -----------------------------------------------------------------------------------
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
        # 1) Delete selected components
        if self.selected_components:
            for c in self.selected_components:
                if c['element']:
                    self.simulator.remove_element(c['element'])
                # Remove the shapes from canvas
                for it in c['canvas_items']:
                    self.canvas.delete(it)
                # Remove any wires connected to c
                wires_to_remove = []
                for w in self.wires:
                    if w.comp1 == c or w.comp2 == c:
                        # Remove wire line
                        self.canvas.delete(w.canvas_id)
                        # Remove voltage and current arrows associated with the wire
                        for arrow_id in w.voltage_arrows + w.current_arrows:
                            self.canvas.delete(arrow_id)
                        wires_to_remove.append(w)
                        logging.debug(f"Deleted wire {w}")
                for wr in wires_to_remove:
                    self.wires.remove(wr)
                    self.simulator.remove_element(wr)  # Also remove from simulator
                # Remove from self.components
                if c in self.components:
                    self.components.remove(c)
                    logging.debug(f"Deleted component {c['element'].name if c.get('element') else 'Ground'}")
            self.selected_components.clear()
            # Update node positions after deletion
            self.compute_node_positions()
            # Redraw voltage and current arrows after deletion
            self.clear_component_arrows()

        # 2) Delete selected wires
        if self.selected_wires:
            for w in self.selected_wires:
                # Remove line from canvas
                self.canvas.delete(w.canvas_id)
                # Remove voltage and current arrows associated with the wire
                for arrow_id in w.voltage_arrows + w.current_arrows:
                    self.canvas.delete(arrow_id)
                # Remove from self.wires
                if w in self.wires:
                    self.wires.remove(w)
                    self.simulator.remove_element(w)  # Also remove from simulator
                    logging.debug(f"Deleted wire {w}")
            self.selected_wires.clear()
            # Update node positions after wire deletion
            self.compute_node_positions()
            # Redraw voltage and current arrows after deletion
            self.clear_component_arrows()

    def update_terminal_bindings(self):
        """
        Bind the terminal dots (red ovals) so that clicking them shows the node voltage.
        This is only activated after a simulation has been run.
        """
        for comp in self.components:
            # Only for components that have an element (skip ground)
            if not comp.get("element"):
                continue
            # If there is a stored list of terminal dot IDs, bind each dot.
            if "terminal_dot_ids" in comp:
                for tid in comp["terminal_dot_ids"]:
                    # The add="+" option makes sure we add this binding without replacing others.
                    self.canvas.tag_bind(tid, "<Button-1>", self.terminal_click, add="+")

    # -----------------------------------------------------------------------------------
    # Wires
    # -----------------------------------------------------------------------------------
    def handle_wire_click(self, x, y):
        # Find all items under the click
        item_ids = self.canvas.find_overlapping(x-3, y-3, x+3, y+3)
        if not item_ids:
            self.wire_start = None
            logging.debug("Clicked on empty space; resetting wire start")
            return
        # Iterate from top to bottom
        for item_id in reversed(item_ids):
            comp_dict, term_idx = self.find_terminal(item_id)
            if comp_dict:
                # Found a terminal
                if self.wire_start is None:
                    self.wire_start = (comp_dict, term_idx)
                    logging.debug(f"Wire start set to {comp_dict.get('element').name if comp_dict.get('element') else 'Ground'} terminal {term_idx}")
                    return
                else:
                    start_comp, start_term = self.wire_start
                    # Prevent wiring the same terminal to itself
                    if start_comp == comp_dict and start_term == term_idx:
                        messagebox.showwarning("Invalid Wiring", "Cannot connect a terminal to itself.")
                        logging.warning("Attempted to connect a terminal to itself.")
                        self.wire_start = None
                        return
                    # Prevent wiring two terminals of the same component
                    if start_comp == comp_dict:
                        messagebox.showwarning("Invalid Wiring", "Cannot connect two terminals of the same component.")
                        logging.warning("Attempted to connect two terminals of the same component.")
                        self.wire_start = None
                        return
                    # Check if a wire already exists between these terminals
                    if self.check_existing_wire(start_comp, start_term, comp_dict, term_idx):
                        messagebox.showwarning("Invalid Wiring", "A wire already exists between these terminals.")
                        logging.warning("Attempted to create a duplicate wire.")
                        self.wire_start = None
                        return
                    # Create wire between start_comp and comp_dict
                    self.merge_and_create_wire(start_comp, start_term, comp_dict, term_idx)
                    self.wire_start = None
                    return
        # If no terminal was found in items
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
        nodeA = eA.nodes[termA] if eA else 0  # Ground node is 0
        nodeB = eB.nodes[termB] if eB else 0

        # If both nodes are unassigned, create a new node
        if nodeA is None and nodeB is None:
            new_node = self.get_biggest_node() + 1
            if eA:
                eA.nodes[termA] = new_node
            if eB:
                eB.nodes[termB] = new_node

        # If only one node is assigned, propagate it to the other terminal
        elif nodeA is None:
            if eA:
                eA.nodes[termA] = nodeB
        elif nodeB is None:
            if eB:
                eB.nodes[termB] = nodeA

        # If both nodes are assigned but different, merge them
        else:
            if nodeA != nodeB:
                # Merge nodeB into nodeA
                for e in self.simulator.elements:
                    for i, n in enumerate(e.nodes):
                        if n == nodeB:
                            e.nodes[i] = nodeA
                logging.debug(f"Merged node {nodeB} into node {nodeA}")

        # Ensure ground propagation
        if nodeA == 0 or nodeB == 0:
            ground_node = 0
            for e in self.simulator.elements:
                for i, n in enumerate(e.nodes):
                    if n in [nodeA, nodeB]:
                        e.nodes[i] = ground_node
            logging.debug("Propagated ground connection.")

        # Draw the wire on the canvas
        x1, y1 = compA['abs_terminals'][termA]
        x2, y2 = compB['abs_terminals'][termB]
        wire_id = self.canvas.create_line(x1, y1, x2, y2, fill="gray", width=2)

        # Create and add the wire to the simulator's elements
        wire_name = f"Wire{len([e for e in self.simulator.elements if e.element_type == 'wire']) + 1}"
        wire_element = Wire(name=wire_name, comp1=compA, term1_idx=termA, comp2=compB, term2_idx=termB, canvas_id=wire_id)
        self.simulator.add_element(wire_element)
        self.wires.append(wire_element)  # Update the GUI's wires list
        logging.debug(f"Created and added wire: {wire_element}")

    def find_terminal(self, item_id):
        """
        Return the component dict and terminal index if the item_id is a terminal dot.
        """
        for c in self.components:
            if item_id in c['canvas_items']:
                # Retrieve abs_terminals if available
                abs_terminals = c.get('abs_terminals', [])
                for i, (tx, ty) in enumerate(abs_terminals):
                    # Get the coordinates of the terminal dot
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
            logging.debug(f"Updated wire {w} coordinates to ({x1}, {y1}) - ({x2}, {y2})")
        # Recompute node positions after updating wires
        self.compute_node_positions()

    # -----------------------------------------------------------------------------------
    # Selection Helpers
    # -----------------------------------------------------------------------------------
    def clear_selection(self):
        # Un-highlight all components
        for c in self.selected_components:
            self.highlight_component(c, False)
        self.selected_components.clear()

        # Un-highlight all wires
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
                self.canvas.itemconfig(comp_dict['canvas_items'][0], fill="black")  # Revert to original color
            elif comp_dict['comp_type'] == "resistor":
                self.canvas.itemconfig(comp_dict['canvas_items'][0], fill="black")
            elif comp_dict['comp_type'] == "voltage_source":
                self.canvas.itemconfig(comp_dict['canvas_items'][0], outline="blue", width=2)
            elif comp_dict['comp_type'] == "current_source":
                self.canvas.itemconfig(comp_dict['canvas_items'][0], outline="green", width=2)
            logging.debug(f"Unhighlighted component {comp_dict.get('element').name if comp_dict.get('element') else 'Ground'}")

    def highlight_wire(self, wire_obj, highlight):
        """
        Change wire color/width to show selection or unselection.
        """
        if highlight:
            self.canvas.itemconfig(wire_obj.canvas_id, fill="blue", width=3)
            logging.debug(f"Highlighted wire {wire_obj}")
        else:
            self.canvas.itemconfig(wire_obj.canvas_id, fill="gray", width=2)
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
        # Now, we only show node voltage if the simulation results exist (last_node_voltages, last_node_map).
        if not (hasattr(self, "last_node_voltages") and hasattr(self, "last_node_map")):
            return  # If we haven't simulated or if we reset, do nothing (or you could revert to wiring logic if you wanted)
        # Only do this if a simulation has been run.
        if not hasattr(self, "last_node_voltages") or not hasattr(self, "last_node_map"):
            # Do nothing if simulation not yet run.
            return

        # Get the canvas item that was clicked
        clicked_items = self.canvas.find_withtag("current")
        if not clicked_items:
            return
        item_id = clicked_items[0]

        # Use your existing find_terminal() method to determine which terminal was clicked.
        comp, term_idx = self.find_terminal(item_id)
        if comp is None or not comp.get("element"):
            return

        # Get the node ID from the element for this terminal.
        node_id = comp["element"].nodes[term_idx]
        if node_id == 0:
            voltage = 0.0
        else:
            node_idx = self.last_node_map.get(node_id, None)
            if node_idx is None:
                return
            voltage = self.last_node_voltages[node_idx]

        # Display the voltage in a popup.
        messagebox.showinfo("Node Voltage", f"Voltage at terminal: {voltage:.5f} V")



    # -----------------------------------------------------------------------------------
    # Simulation
    # -----------------------------------------------------------------------------------
    def simulate(self):
        self.clear_component_arrows()
        # Check for unconnected terminals
        for e in self.simulator.elements:
            if e.element_type in ['wire']:
                continue  # Wires are handled by node merging
            if None in e.nodes:
                messagebox.showerror("Simulation Error",
                    f"Element {e.name} is not fully connected! Each terminal must be wired.")
                logging.error(f"Simulation failed: Element {e.name} has unconnected terminals.")
                return

        # Ensure at least one connection to ground (node 0)
        ground_connected = any(0 in e.nodes for e in self.simulator.elements if e.element_type != 'wire')
        if not ground_connected:
            messagebox.showerror("Simulation Error", "No ground connection! Ensure the circuit is grounded (connected to node 0).")
            logging.error("Simulation failed: No ground connection detected.")
            return

        node_voltages, source_currents = self.simulator.solve_circuit()
        if node_voltages is None:
            logging.error("Simulation failed: Singular matrix encountered.")
            return


        # Save the simulation results for terminal lookup.
        self.last_node_voltages = node_voltages
        self.last_node_map = self.simulator.node_map.copy()
        # Now that simulation is done, bind terminal dots for voltage lookup.
        self.update_terminal_bindings()


        # Compute node positions for labeling
        self.compute_node_positions()

        # # After updating node labels…
        # self.update_node_labels(node_voltages)
        # Draw arrows on wires (existing)
        # self.visualize_voltage_differences(node_voltages)
        # NEW: Also draw arrows on non-wire components showing potential differences.
        self.visualize_component_potentials(node_voltages)
        # And then compute and display currents as before.
        self.compute_and_display_currents(node_voltages, source_currents)


        # Create the simulation results window
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
                continue  # Skip wires in element results

            if e.element_type in ['resistor', 'voltage_source', 'current_source']:
                node1 = e.nodes[0]
                node2 = e.nodes[1]
                v1 = 0.0 if node1 == 0 else node_voltages[self.simulator.node_map[node1]]
                v2 = 0.0 if node2 == 0 else node_voltages[self.simulator.node_map[node2]]
                voltage_diff = v1 - v2

                # Look up the current value stored in the GUI component dictionary.
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
                # Safely retrieve the current
                vs_index = next((idx for idx, source in enumerate(vsrcs) if source is vs), None)
                if vs_index is not None and vs_index < len(source_currents):
                    current = source_currents[vs_index]
                    text.insert(tk.END, f"{vs.name} current: {current:.7e} A\n")
                else:
                    text.insert(tk.END, f"{vs.name} current: N/A\n")
                    logging.error(f"Voltage Source {vs.name}: Simulation did not return a current value.")

        text.config(state=tk.DISABLED)
        logging.debug("Simulation completed successfully.")

    # -----------------------------------------------------------------------------------
    # Voltage and Current Visualization
    # -----------------------------------------------------------------------------------
    def visualize_voltage_differences(self, node_voltages):
        """
        Draw voltage difference arrows on wires and display node voltage labels.
        """
        # Clear existing voltage arrows
        for w in self.wires:
            for arrow_id in w.voltage_arrows:
                self.canvas.delete(arrow_id)
            w.voltage_arrows.clear()
        
        # For each wire, if there is a voltage difference, draw an arrow.
        for w in self.wires:
            node1 = w.comp1['element'].nodes[w.term1_idx] if w.comp1.get('element') else 0
            node2 = w.comp2['element'].nodes[w.term2_idx] if w.comp2.get('element') else 0
            v1 = 0.0 if node1 == 0 else node_voltages[self.simulator.node_map[node1]]
            v2 = 0.0 if node2 == 0 else node_voltages[self.simulator.node_map[node2]]
            voltage_diff = v1 - v2
            
            if voltage_diff == 0:
                continue

            # Determine arrow direction:
            if voltage_diff > 0:
                start = w.comp1['abs_terminals'][w.term1_idx]
                end = w.comp2['abs_terminals'][w.term2_idx]
            else:
                start = w.comp2['abs_terminals'][w.term2_idx]
                end = w.comp1['abs_terminals'][w.term1_idx]
            arrow_color = "red" if voltage_diff > 0 else "blue"
            # Draw arrow and label using the helper.
            arrow_ids = self.draw_arrow_with_label(start, end, arrow_color, 2, 30, "{:.2f} V", abs(voltage_diff))
            w.voltage_arrows.extend(arrow_ids)
        
        # Draw node voltage labels.
        for node_id, pos in self.node_positions.items():
            if node_id == 0:
                continue  # Skip ground node if desired
            node_idx = self.simulator.node_map.get(node_id)
            if node_idx is not None:
                voltage = node_voltages[node_idx]
                self.canvas.create_text(pos[0], pos[1] - 20,
                                        text=f"{voltage:.2f} V",
                                        fill="black", font=("Arial", 10, "bold"))
                logging.debug(f"Displayed voltage {voltage:.2f} V at node {node_id}")

    def draw_arrow_with_label(self, start, end, arrow_color, arrow_thickness, arrow_length, label_format, value, offset_distance=10):
        # Compute the angle from start to end.
        angle = math.atan2(end[1] - start[1], end[0] - start[0])
        # Use the provided offset_distance from the midpoint.
        offset_x = -offset_distance * math.sin(angle)
        offset_y = offset_distance * math.cos(angle)
        mid_x = (start[0] + end[0]) / 2
        mid_y = (start[1] + end[1]) / 2
        arrow_start = (mid_x + offset_x, mid_y + offset_y)
        arrow_end = (arrow_start[0] + arrow_length * math.cos(angle),
                    arrow_start[1] + arrow_length * math.sin(angle))
        arrow_id = self.canvas.create_line(arrow_start[0], arrow_start[1],
                                            arrow_end[0], arrow_end[1],
                                            arrow=tk.LAST, fill=arrow_color, width=arrow_thickness)
        label_text = label_format.format(value)
        label_id = self.canvas.create_text((arrow_start[0] + arrow_end[0]) / 2,
                                            (arrow_start[1] + arrow_end[1]) / 2 - 10,
                                            text=label_text, fill=arrow_color,
                                            font=("Arial", 10, "bold"))
        return arrow_id, label_id

    
    def visualize_component_potentials(self, node_voltages):
        """
        For each non-wire component (and not ground), draw an arrow showing the potential difference.
        """
        for comp in self.components:
            # Only process components with an element that isn’t a wire.
            if comp.get("element") and comp["element"].element_type != "wire":
                node1 = comp["element"].nodes[0]
                node2 = comp["element"].nodes[1]
                v1 = 0.0 if node1 == 0 else node_voltages[self.simulator.node_map[node1]]
                v2 = 0.0 if node2 == 0 else node_voltages[self.simulator.node_map[node2]]
                voltage_diff = v1 - v2
                if voltage_diff == 0:
                    continue
                # Draw arrow from the higher potential terminal to the lower.
                if voltage_diff > 0:
                    start = comp["abs_terminals"][0]
                    end = comp["abs_terminals"][1]
                else:
                    start = comp["abs_terminals"][1]
                    end = comp["abs_terminals"][0]
                arrow_color = "red" if voltage_diff > 0 else "blue"
                # Use a larger arrow_length (e.g. 50) and a larger offset (e.g. 20)
                arrow_ids = self.draw_arrow_with_label(start, end, arrow_color, 2, 50, "{:.2f} V", abs(voltage_diff), offset_distance=50)
                comp.setdefault("voltage_arrows", []).extend(arrow_ids)
                logging.debug(f"Drew potential arrow on {comp['element'].name} with {voltage_diff:.2f} V")




    def compute_and_display_currents(self, node_voltages, source_currents):
        """
        Calculate and display currents through each component (including wires) using arrows.
        """
        # Clear existing current arrows.
        self.clear_component_arrows()
        
        for comp in self.components:
            if not comp.get('element'):
                continue  # Skip ground
            
            elem = comp['element']
            
            # Calculate current based on element type.
            # if elem.element_type == 'wire':
            #     R_wire = 1e-12
            #     node1 = elem.nodes[0]
            #     node2 = elem.nodes[1]
            #     if node1 is None or node2 is None:
            #         logging.warning(f"Wire {elem.name} is not fully connected. Skipping current calculation.")
            #         continue
            #     v1 = 0.0 if node1 == 0 else node_voltages[self.simulator.node_map[node1]]
            #     v2 = 0.0 if node2 == 0 else node_voltages[self.simulator.node_map[node2]]
            #     current = (v1 - v2) / R_wire
            if elem.element_type == 'wire':
                # For ideal wires, we assume no voltage drop so no current arrow is drawn.
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
                    continue  # Unknown type
            
            comp['current'] = current
            
            # Determine arrow parameters.
            if current > 0:
                direction = 1
                color = "green"
            elif current < 0:
                direction = -1
                color = "orange"
            else:
                continue
            
            # For current arrows, use a slightly larger offset.
            # Determine arrow start and end based on component terminal positions.
            pos1 = comp['abs_terminals'][0]
            pos2 = comp['abs_terminals'][1]
            # Base arrow direction from pos1 to pos2.
            base_angle = math.atan2(pos2[1] - pos1[1], pos2[0] - pos1[0])
            # If current is negative, reverse the arrow direction.
            if direction == -1:
                base_angle += math.pi
            # Compute new start and end using our helper.
            # Here we use the same arrow_length and thickness as before.
            arrow_ids = self.draw_arrow_with_label(pos1, pos2, color, 2, 30, "I = {:.2e} A", abs(current))
            comp.setdefault('current_arrows', []).extend(arrow_ids)
            logging.debug(f"Drew current arrow on element {elem.name} with current {current:.2e} A")



    # -----------------------------------------------------------------------------------
    # Node Positioning and Labeling
    # -----------------------------------------------------------------------------------
    def compute_node_positions(self):
        """
        Compute the positions of each node based on connected terminals from all elements.
        """
        # Clear existing node positions
        self.node_positions.clear()

        # Create a mapping from node_id to list of positions
        node_to_positions = {}

        for e in self.simulator.elements:
            if e.element_type == 'wire':
                # Wires connect two terminals
                node1 = e.nodes[0]
                node2 = e.nodes[1]
                if node1 is not None:
                    pos1 = e.comp1['abs_terminals'][e.term1_idx]
                    node_to_positions.setdefault(node1, []).append(pos1)
                if node2 is not None:
                    pos2 = e.comp2['abs_terminals'][e.term2_idx]
                    node_to_positions.setdefault(node2, []).append(pos2)
            else:
                # Non-wire elements have their terminals' positions
                # Find the component dictionary corresponding to this element
                comp_dict = next((c for c in self.components if c['element'] == e), None)
                if comp_dict:
                    for term_idx, pos in enumerate(comp_dict['abs_terminals']):
                        node = e.nodes[term_idx]
                        if node is not None:
                            node_to_positions.setdefault(node, []).append(pos)

        # Compute average position for each node
        for node_id, positions in node_to_positions.items():
            if node_id == 0:
                continue  # Ground node handled separately
            avg_x = sum(p[0] for p in positions) / len(positions)
            avg_y = sum(p[1] for p in positions) / len(positions)
            self.node_positions[node_id] = (avg_x, avg_y)
            logging.debug(f"Node {node_id} positioned at ({avg_x}, {avg_y})")

    def update_node_labels(self, node_voltages):
        """
        Create or update labels on the canvas to display node voltages with color-coding.
        """
        # Remove existing labels
        for label_id in self.node_labels.values():
            self.canvas.delete(label_id)
        self.node_labels.clear()

        # Define voltage thresholds for color-coding
        high_threshold = 5.0    # Volts
        low_threshold = -5.0    # Volts

        # Iterate over node positions and voltages
        for node_id, pos in self.node_positions.items():
            # Retrieve the index for this node
            node_idx = self.simulator.node_map.get(node_id, None)
            if node_idx is None:
                logging.error(f"Node ID {node_id} not found in node_map.")
                continue

            voltage = node_voltages[node_idx]
            x, y = pos

            # Determine color based on voltage magnitude
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

            # Create label with color-coding
            label_text = f"V{node_id} = {voltage:.5f} V"
            label_id = self.canvas.create_text(x, y - 15, text=label_text, fill=color, font=("Arial", 10, "bold"))
            self.node_labels[node_id] = label_id
            logging.debug(f"Created label for Node {node_id} at ({x}, {y - 15}) with voltage {voltage:.5f} V and color {color}")

        # Handle ground node separately
        ground_nodes = [c for c in self.components if c.get("is_ground")]
        if ground_nodes:
            ground = ground_nodes[0]
            cx, cy = ground['center']
            label_text = f"Ground (V0) = 0.00 V"
            label_id = self.canvas.create_text(cx, cy + 30, text=label_text, fill="black", font=("Arial", 10, "bold", "italic"))
            self.node_labels[0] = label_id
            logging.debug(f"Created label for Ground node at ({cx}, {cy + 30})")


    def draw_arrow_with_label(self, start, end, arrow_color, arrow_thickness, arrow_length, label_format, value, offset_distance=10):
        # Compute the angle from start to end.
        angle = math.atan2(end[1] - start[1], end[0] - start[0])
        # Use the provided offset_distance from the midpoint.
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
        label_id = self.canvas.create_text(
            (arrow_start[0] + arrow_end[0]) / 2,
            (arrow_start[1] + arrow_end[1]) / 2 - 10,
            text=label_text, fill=arrow_color,
            font=("Arial", 10, "bold"))
        return arrow_id, label_id



    # -----------------------------------------------------------------------------------
    # Voltage and Current Visualization Helpers
    # -----------------------------------------------------------------------------------
    def clear_component_arrows(self):
        """
        Remove all current arrows *and* voltage arrows from components,
        and do the same for wires if you want to ensure everything is cleared.
        """
        # 1) Remove current arrows + voltage arrows from each component
        for comp in self.components:
            # Current arrows
            for arrow_id in comp.get('current_arrows', []):
                self.canvas.delete(arrow_id)
            comp['current_arrows'] = []

            # Voltage arrows
            for arrow_id in comp.get('voltage_arrows', []):
                self.canvas.delete(arrow_id)
            comp['voltage_arrows'] = []

        # 2) If you also want to remove voltage arrows drawn on wires:
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
            # Use a separate canvas for color boxes
            color_box = tk.Canvas(frame, width=15, height=15, highlightthickness=0)
            color_box.pack(side=tk.LEFT)
            color_box.create_rectangle(0, 0, 15, 15, fill=color, outline=color)
            label_widget = ttk.Label(frame, text=label, foreground=color)
            label_widget.pack(side=tk.LEFT, padx=(5, 0))

    
