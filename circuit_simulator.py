from union_find import UnionFind
from circuit_elements import CircuitElement, Wire
from imports import *

class CircuitSimulator:
    """
    Stores the netlist (list of circuit elements) and performs MNA-based DC simulation.
    """
    def __init__(self):
        self.elements = []
        self.node_map = {}          # maps a node_id (int, excluding ground) -> matrix index
        self.next_node_index = 0    # Start indexing from 0 for non-ground nodes
        self.voltage_sources = []
        self.uf = UnionFind()       # Initialize Union-Find

    def clear_all(self):
        self.elements.clear()
        self.node_map.clear()
        self.next_node_index = 0

    def build_union_find(self):
        """
        Merge nodes connected by wires using Union-Find.
        """
        for e in self.elements:
            if e.element_type == 'wire':
                node1, node2 = e.nodes
                if node1 is not None and node2 is not None:
                    self.uf.union(node1, node2)
                    logging.debug(f"Merged nodes {node1} and {node2} via wire.")

    def add_element(self, element):
        self.elements.append(element)
        logging.debug(f"Added element: {element}")

    def remove_element(self, element):
        if element in self.elements:
            self.elements.remove(element)
            logging.debug(f"Removed element: {element}")

    def build_node_map(self):
        """
        Assign unique indices to each unique node after merging connected nodes.
        Node 0 (ground) is treated separately and not included in node_map.
        """
        self.node_map = {}
        self.next_node_index = 0

        unique_nodes = set()
        for e in self.elements:
            if e.element_type == 'wire':
                continue  # Wires are handled by Union-Find
            for nd in e.nodes:
                if nd is not None and nd != 0:
                    unique_nodes.add(self.uf.find(nd))

        sorted_nodes = sorted(unique_nodes)
        for node_id in sorted_nodes:
            if node_id not in self.node_map:
                self.node_map[node_id] = self.next_node_index
                logging.debug(f"Mapped node {node_id} to matrix index {self.node_map[node_id]}")
                self.next_node_index += 1

    def detect_floating_nodes(self):
        connected = set()
        connected.add(self.uf.find(0))  # Ground node is always connected.

        # Nodes connected via voltage sources or ground
        for e in self.elements:
            if e.element_type == 'voltage_source':
                n1, n2 = e.nodes
                if n1 is not None:
                    connected.add(self.uf.find(n1))
                if n2 is not None:
                    connected.add(self.uf.find(n2))

        # Gather all nodes in the circuit
        all_nodes = set()
        for e in self.elements:
            for node in e.nodes:
                if node is not None:
                    all_nodes.add(self.uf.find(node))

        # Identify floating nodes
        floating_nodes = all_nodes - connected
        # if floating_nodes:
        #     messagebox.showerror("Simulation Error", f"Floating nodes detected: {floating_nodes}")
            
        #     logging.debug(f"All nodes: {all_nodes}")
        #     logging.debug(f"Connected nodes: {connected}")
        #     logging.debug(f"Floating nodes detected: {floating_nodes}")

        #     return floating_nodes
    
    
        return None

    def stamp_matrices(self):
        """
        Stamps the conductance matrix A and source vector z based on the circuit elements.
        Returns the matrices A, z, number of nodes, and number of voltage sources.
        """
        self.voltage_sources = [e for e in self.elements if e.element_type == 'voltage_source']
        num_vsources = len(self.voltage_sources)
        num_nodes = self.next_node_index

        # Total size: num_nodes + num_vsources
        n = num_nodes + num_vsources
        A = np.zeros((n, n))
        z = np.zeros(n)

        def n_idx(node_id):
            return self.node_map.get(node_id, None) if node_id != 0 else None

        # Stamp Resistors
        for e in self.elements:
            if e.element_type == 'resistor':
                r = e.value
                if abs(r) < 1e-15:
                    logging.warning(f"Resistor {e.name} has near-zero resistance; replacing with 1e-12 Ohms.")
                    r = 1e-12
                g = 1.0 / r
                n1 = n_idx(e.nodes[0])
                n2 = n_idx(e.nodes[1])
                logging.debug(f"Stamping resistor {e.name} between nodes {e.nodes[0]} and {e.nodes[1]} with conductance {g}")
                if n1 is not None and n2 is not None:
                    A[n1, n1] += g
                    A[n2, n2] += g
                    A[n1, n2] -= g
                    A[n2, n1] -= g
                elif n1 is not None:
                    A[n1, n1] += g
                elif n2 is not None:
                    A[n2, n2] += g

        # Stamp Current Sources
        for e in self.elements:
            if e.element_type == 'current_source':
                i_val = e.value
                n1 = n_idx(e.nodes[0])
                n2 = n_idx(e.nodes[1])
                logging.debug(f"Stamping current source {e.name} from node {e.nodes[0]} to node {e.nodes[1]} with value {i_val}")
                if n1 is not None:
                    z[n1] -= i_val
                if n2 is not None:
                    z[n2] += i_val

        # Stamp Voltage Sources
        vs_i = 0
        for e in self.voltage_sources:
            v_val = e.value
            n1 = n_idx(e.nodes[0])  # Positive terminal
            n2 = n_idx(e.nodes[1])  # Negative terminal
            logging.debug(f"Stamping voltage source {e.name} from node {e.nodes[0]} to node {e.nodes[1]} with voltage {v_val}")
            row = num_nodes + vs_i
            if n1 is not None:
                A[n1, row] += 1
                A[row, n1] += 1
            if n2 is not None:
                A[n2, row] -= 1
                A[row, n2] -= 1
            z[row] = v_val
            vs_i += 1

        logging.debug(f"Conductance Matrix A:\n{A}")
        logging.debug(f"Source Vector z:\n{z}")

        return A, z, num_nodes, num_vsources

    def solve_circuit(self):
        """
        Solve the matrix equation using Modified Nodal Analysis.
        Return (node_voltages, voltage_source_currents).
        """
        self.build_union_find()      # Merge nodes connected by wires
        self.build_node_map()        # Assign unique indices to merged nodes

        # Detect floating nodes before stamping matrices
        floating_nodes = self.detect_floating_nodes()
        if floating_nodes:
            return None, None

        A, z, num_nodes, num_vsources = self.stamp_matrices()

        # Check matrix rank
        try:
            rank = np.linalg.matrix_rank(A)
            if rank < A.shape[0]:
                logging.error(f"Matrix A is singular or rank-deficient (rank={rank}/{A.shape[0]}).")
                messagebox.showerror("Simulation Error", "The circuit matrix is singular or ill-conditioned.")
                return None, None
        except Exception as e:
            logging.error(f"Error computing matrix rank: {e}")
            messagebox.showerror("Simulation Error", f"Error computing matrix rank: {e}")
            return None, None

        try:
            x = np.linalg.solve(A, z)
            logging.debug(f"Solved vector x:\n{x}")
        except np.linalg.LinAlgError as e:
            logging.error(f"LinAlgError: {e}")
            messagebox.showerror("Simulation Error", "Circuit matrix is singular or ill-conditioned.")
            # Additional debug info
            try:
                rank = np.linalg.matrix_rank(A)
                print(f"Matrix A Rank: {rank} / {A.shape[0]}")
                logging.debug(f"Matrix A Rank: {rank} / {A.shape[0]}")
            except Exception as rank_e:
                logging.error(f"Failed to compute matrix rank: {rank_e}")
            return None, None

        node_voltages = x[:num_nodes]
        source_currents = x[num_nodes:num_nodes + num_vsources]
        logging.debug(f"Node Voltages: {node_voltages}")
        logging.debug(f"Voltage Source Currents: {source_currents}")

        return node_voltages, source_currents

