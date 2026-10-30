"""Run: python -m scripts.benchmark [--size 10000]; microbenchmark, not a DB speed claim."""
import argparse
import json
from pathlib import Path
from time import perf_counter
from backend.app.structures.hash_table import HashTable
from backend.app.structures.queue import Queue
from backend.app.structures.priority_queue import PriorityQueue
from backend.app.structures.graph import Graph


def benchmark(size):
    table = HashTable()
    records = [(str(i), i) for i in range(size)]
    for key, value in records:
        table.insert(key, value)
    keys = [str(i) for i in range(0, size, max(1, size // 1000))]
    start = perf_counter()
    for key in keys:
        assert table.search(key) == int(key)
    hashing = perf_counter() - start
    start = perf_counter()
    for key in keys:
        assert next(v for k, v in records if k == key) == int(key)
    linear = perf_counter() - start
    start = perf_counter()
    queue = Queue()
    for i in range(size):
        queue.enqueue(i)
    for i in range(size):
        assert queue.dequeue() == i
    queue_time = perf_counter() - start
    start = perf_counter()
    heap = PriorityQueue()
    for i in range(size):
        heap.insert(i, i % 5, i)
    while len(heap):
        heap.extract_min()
    heap_time = perf_counter() - start
    graph = Graph()
    for i in range(size - 1):
        graph.add_edge(i, i + 1)
    start = perf_counter()
    assert len(graph.bfs(0, size - 1)) == size
    bfs_time = perf_counter() - start
    return {'n': size, 'lookups': len(keys), 'hash_seconds': hashing, 'linear_seconds': linear,
            'queue_insert_remove_seconds': queue_time, 'heap_insert_extract_seconds': heap_time,
            'chain_graph_bfs_seconds': bfs_time}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--size', type=int, default=10000)
    args = parser.parse_args()
    if not 2 <= args.size <= 1000000:
        parser.error('size must be between 2 and 1000000')
    result = benchmark(args.size)
    Path('docs/benchmark_results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
