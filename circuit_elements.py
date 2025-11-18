from imports import *
import logging

class CircuitElement:
    """
    Represents a circuit element (resistor, voltage source, current source, wire).
    """
    def __init__(self, name, value, element_type):
        self.name = name
        self.value = value
        self.element_type = element_type
        self.nodes = [None, None]

    def __repr__(self):
        return f"<{self.element_type} {self.name}, value={self.value}, nodes={self.nodes}>"


class Wire(CircuitElement):
    """
    Represents a wire connecting two terminals.
    Inherits from CircuitElement with element_type='wire' and value=0.
    Wire nodes are computed dynamically from connected components.
    """
    def __init__(self, name, comp1, term1_idx, comp2, term2_idx, canvas_id):
        super().__init__(name=name, value=0, element_type='wire')
        self.comp1 = comp1
        self.term1_idx = term1_idx
        self.comp2 = comp2
        self.term2_idx = term2_idx
        self.canvas_id = canvas_id
        self.voltage_arrows = []
        self.current_arrows = []

    @property
    def nodes(self):
        """Compute wire nodes dynamically from connected components."""
        eA = self.comp1.get('element')
        eB = self.comp2.get('element')
        nodeA = eA.nodes[self.term1_idx] if eA else 0
        nodeB = eB.nodes[self.term2_idx] if eB else 0
        return [nodeA, nodeB]

    @nodes.setter
    def nodes(self, value):
        """Setter for compatibility, but nodes are computed dynamically."""
        pass  # Ignore - nodes are always computed from components

    def __repr__(self):
        name1 = self.comp1['element'].name if self.comp1['element'] else "Ground"
        name2 = self.comp2['element'].name if self.comp2['element'] else "Ground"
        return f"<Wire {name1}-T{self.term1_idx} to {name2}-T{self.term2_idx}>"
