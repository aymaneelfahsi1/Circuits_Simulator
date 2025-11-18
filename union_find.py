import logging

class UnionFind:
    def __init__(self):
        self.parent = {}
        self.rank = {}

    def find(self, node):
        if node not in self.parent:
            self.parent[node] = node
            self.rank[node] = 0
        if self.parent[node] != node:
            self.parent[node] = self.find(self.parent[node])
        return self.parent[node]

    def union(self, node1, node2):
        root1 = self.find(node1)
        root2 = self.find(node2)
        if root1 != root2:
            if self.rank[root1] < self.rank[root2]:
                self.parent[root1] = root2
                logging.debug(f"Union nodes {node1} and {node2}: {root2} <- {root1}")
            elif self.rank[root1] > self.rank[root2]:
                self.parent[root2] = root1
                logging.debug(f"Union nodes {node1} and {node2}: {root1} <- {root2}")
            else:
                self.parent[root2] = root1
                self.rank[root1] += 1
                logging.debug(f"Union nodes {node1} and {node2}: {root1} <- {root2}")
