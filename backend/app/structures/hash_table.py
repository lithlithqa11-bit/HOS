"""Separate chaining, FNV-1a hash, geometric rehashing; no builtin mapping storage."""
class HashTable:
    def __init__(self, capacity=16):
        if capacity < 1:
            raise ValueError('capacity must be positive')
        self._buckets = [[] for _ in range(capacity)]
        self._size = 0

    @staticmethod
    def hash_function(key):
        value = 2166136261
        for byte in str(key).encode('utf-8'):
            value = ((value ^ byte) * 16777619) & 0xffffffff
        return value

    def _bucket(self, key):
        return self._buckets[self.hash_function(key) % len(self._buckets)]

    def insert(self, key, value):
        bucket = self._bucket(key)
        for i, (stored, _) in enumerate(bucket):
            if stored == key:
                bucket[i] = (key, value)
                return
        bucket.append((key, value))
        self._size += 1
        if self._size > len(self._buckets) * .75:
            old = self._buckets
            self._buckets = [[] for _ in range(len(old) * 2)]
            self._size = 0
            for chain in old:
                for k, v in chain:
                    self.insert(k, v)

    def search(self, key, default=None):
        for stored, value in self._bucket(key):
            if stored == key:
                return value
        return default

    def delete(self, key):
        bucket = self._bucket(key)
        for i, (stored, _) in enumerate(bucket):
            if stored == key:
                bucket.pop(i)
                self._size -= 1
                return True
        return False

    def __len__(self):
        return self._size

    def items(self):
        for bucket in self._buckets:
            yield from bucket
