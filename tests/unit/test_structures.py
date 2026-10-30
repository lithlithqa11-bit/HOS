import random
import pytest
from backend.app.structures.hash_table import HashTable
from backend.app.structures.queue import Queue
from backend.app.structures.priority_queue import PriorityQueue
from backend.app.structures.graph import Graph


def test_hash_collision_resize_replace_delete():
    table = HashTable(1)
    table.hash_function = lambda key: 0  # force every entry into the same chain
    for i in range(150):
        table.insert(f'card-{i}', i)
    assert len(table) == 150
    for i in range(150):
        assert table.search(f'card-{i}') == i
    table.insert('card-1', 'updated')
    assert table.search('card-1') == 'updated'
    assert len(table) == 150
    assert table.delete('card-1')
    assert not table.delete('card-1')
    assert table.search('card-1') is None
    assert len(list(table.items())) == 149


def test_hash_random_operations():
    randomizer, expected, table = random.Random(9), {}, HashTable()
    for _ in range(3000):
        key = randomizer.randrange(100)
        if randomizer.randrange(2):
            value = randomizer.randrange(1000)
            expected[key] = value
            table.insert(key, value)
        else:
            assert table.delete(key) == (key in expected)
            expected.pop(key, None)
        assert table.search(key) == expected.get(key)
        assert len(table) == len(expected)


def test_queue_fifo_empty_and_reuse():
    queue = Queue()
    assert queue.is_empty()
    with pytest.raises(IndexError):
        queue.dequeue()
    for i in range(1000):
        queue.enqueue(i)
    assert queue.peek() == 0
    assert list(queue) == list(range(1000))
    assert [queue.dequeue() for _ in range(1000)] == list(range(1000))
    assert queue.is_empty() and len(queue) == 0
    queue.enqueue('again')
    assert queue.dequeue() == 'again'


def test_heap_priority_arrival_id_ties_and_updates():
    heap = PriorityQueue()
    heap.insert(3, 2, 100)
    heap.insert(2, 2, 100)
    heap.insert(1, 2, 90)
    heap.insert(4, 1, 200)
    assert heap.peek().id == 4
    heap.update_priority(4, 5)
    assert heap.peek().id == 1
    heap.update_priority(3, 1)
    assert [heap.extract_min().id for _ in range(4)] == [3, 1, 2, 4]
    with pytest.raises(IndexError):
        heap.extract_min()
    with pytest.raises(KeyError):
        heap.update_priority(5, 1)


def test_heap_randomized_against_sort():
    heap, expected, rng = PriorityQueue(), {}, random.Random(123)
    for id in range(1000):
        priority, arrival = rng.randrange(1, 6), rng.randrange(100)
        expected[id] = (priority, arrival, id)
        heap.insert(id, priority, arrival)
    for _ in range(500):
        id, priority = rng.randrange(1000), rng.randrange(1, 6)
        expected[id] = (priority, expected[id][1], id)
        heap.update_priority(id, priority)
    assert [heap.extract_min().key for _ in range(1000)] == sorted(expected.values())


def test_heap_duplicate():
    heap = PriorityQueue()
    heap.insert(1, 1, 1)
    with pytest.raises(ValueError):
        heap.insert(1, 2, 2)


def test_graph_shortest_directed_cycle_unreachable():
    graph = Graph()
    for a, b in [(1, 2), (2, 3), (3, 1), (1, 4), (4, 5), (5, 3), (1, 2)]:
        graph.add_edge(a, b)
    graph.add_node(6)
    assert graph.bfs(1, 3) == [1, 2, 3]
    assert graph.bfs(1, 1) == [1]
    assert graph.bfs(1, 6) == []
    assert graph.bfs(6, 1) == []
    assert graph.bfs(99, 99) == []
