import hashlib
from threading import RLock
from fastapi import HTTPException
from sqlalchemy import select
from backend.app.db.models import NFCCard
from backend.app.structures.hash_table import HashTable


def token_hash(token):
    return hashlib.sha256(token.encode('ascii')).hexdigest()


class CardCache:
    """Caches only hash -> row ID. Every hit revalidates PostgreSQL active state.

    Multiple API processes remain correct after revocation. Bounded RAM; no PHI.
    """
    def __init__(self, capacity=4096):
        self.table = HashTable()
        self.lock = RLock()
        self.capacity = capacity
        self.hits = self.misses = 0

    def invalidate(self, digest):
        with self.lock:
            self.table.delete(digest)

    def lookup(self, db, token):
        digest = token_hash(token)
        with self.lock:
            card_id = self.table.search(digest)
            self.hits += card_id is not None
            self.misses += card_id is None
        if card_id is not None:
            card = db.scalar(select(NFCCard).where(NFCCard.id == card_id, NFCCard.token_hash == digest))
        else:
            card = db.scalar(select(NFCCard).where(NFCCard.token_hash == digest))
        if card is None or not card.active:
            self.invalidate(digest)
            raise HTTPException(404, 'بطاقة غير معروفة أو ملغاة')
        with self.lock:
            if len(self.table) >= self.capacity:
                self.table = HashTable()
            self.table.insert(digest, card.id)
        return card


card_cache = CardCache()
