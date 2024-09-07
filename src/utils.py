import hashlib


def deterministic_hash(data: str) -> str:
    return hashlib.md5(data.encode()).hexdigest()[:10]


def deterministic_byte_hash(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()[:10]
