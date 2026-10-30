from backend.app.structures.hash_table import HashTable
from backend.app.structures.queue import Queue


class Graph:
    """Directed adjacency lists stored in the project's own hash table."""
    def __init__(self):
        self._adjacency = HashTable()

    def add_node(self, node):
        if self._adjacency.search(node) is None:
            self._adjacency.insert(node, [])

    def add_edge(self, source, destination):
        self.add_node(source)
        self.add_node(destination)
        neighbours = self._adjacency.search(source)
        if destination not in neighbours:
            neighbours.append(destination)

    def bfs(self, source, destination):
        if self._adjacency.search(source) is None or self._adjacency.search(destination) is None:
            return []
        pending, parent = Queue(), HashTable()
        parent.insert(source, source)
        pending.enqueue(source)
        while not pending.is_empty():
            node = pending.dequeue()
            if node == destination:
                path = [node]
                while node != source:
                    node = parent.search(node)
                    path.append(node)
                path.reverse()
                return path
            for neighbour in self._adjacency.search(node):
                if parent.search(neighbour) is None:
                    parent.insert(neighbour, node)
                    pending.enqueue(neighbour)
        return []
