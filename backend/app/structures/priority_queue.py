from dataclasses import dataclass
from backend.app.structures.hash_table import HashTable


@dataclass
class HeapEntry:
    id: int
    priority: int
    arrival: object
    value: object

    @property
    def key(self):
        return self.priority, self.arrival, self.id


class PriorityQueue:
    """Indexed binary min heap. Stable key = (priority, UTC arrival, database ID)."""
    def __init__(self):
        self._heap = []
        self._positions = HashTable()

    def _swap(self, i, j):
        self._heap[i], self._heap[j] = self._heap[j], self._heap[i]
        self._positions.insert(self._heap[i].id, i)
        self._positions.insert(self._heap[j].id, j)

    def _up(self, index):
        while index > 0:
            parent = (index - 1) // 2
            if self._heap[parent].key <= self._heap[index].key:
                break
            self._swap(parent, index)
            index = parent
        return index

    def _down(self, index):
        while 2 * index + 1 < len(self._heap):
            child = 2 * index + 1
            if child + 1 < len(self._heap) and self._heap[child + 1].key < self._heap[child].key:
                child += 1
            if self._heap[index].key <= self._heap[child].key:
                break
            self._swap(index, child)
            index = child

    def insert(self, id, priority, arrival, value=None):
        if self._positions.search(id) is not None:
            raise ValueError('duplicate heap ID')
        entry = HeapEntry(id, priority, arrival, value)
        self._heap.append(entry)
        self._positions.insert(id, len(self._heap) - 1)
        self._up(len(self._heap) - 1)

    def peek(self):
        if not self._heap:
            raise IndexError('empty heap')
        return self._heap[0]

    def extract_min(self):
        result = self.peek()
        tail = self._heap.pop()
        self._positions.delete(result.id)
        if self._heap:
            self._heap[0] = tail
            self._positions.insert(tail.id, 0)
            self._down(0)
        return result

    def update_priority(self, id, priority):
        index = self._positions.search(id)
        if index is None:
            raise KeyError(id)
        self._heap[index].priority = priority
        self._down(self._up(index))
        return self._heap[self._positions.search(id)]

    def __len__(self):
        return len(self._heap)
