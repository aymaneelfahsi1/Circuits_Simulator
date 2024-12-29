from imports import *

class UnionFind:
    def __init__(self):
        self.parent = {}
    
    def find(self, node):
        if node not in self.parent:
            self.parent[node] = node
        if self.parent[node] != node:
            self.parent[node] = self.find(self.parent[node])  # Path compression
        return self.parent[node]
    
    def union(self, node1, node2):
        root1 = self.find(node1)
        root2 = self.find(node2)
        if root1 != root2:
            self.parent[root2] = root1
            logging.debug(f"Union nodes {node1} and {node2}: {root1} <- {root2}")

