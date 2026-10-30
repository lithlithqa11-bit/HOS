"""Singly linked FIFO with explicit head/tail, worst-case O(1) operations."""
class _Node:
    __slots__ = ('value', 'next')

    def __init__(self, value):
        self.value = value
        self.next = None


class Queue:
    def __init__(self):
        self._head = self._tail = None
        self._size = 0

    def enqueue(self, value):
        node = _Node(value)
        if self._tail is None:
            self._head = node
        else:
            self._tail.next = node
        self._tail = node
        self._size += 1

    def dequeue(self):
        value = self.peek()
        self._head = self._head.next
        self._size -= 1
        if self._head is None:
            self._tail = None
        return value

    def peek(self):
        if self.is_empty():
            raise IndexError('empty queue')
        return self._head.value

    def is_empty(self):
        return self._head is None

    def __len__(self):
        return self._size

    def __iter__(self):
        node = self._head
        while node is not None:
            yield node.value
            node = node.next
