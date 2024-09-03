import hashlib


def deterministic_hash(data: str) -> str:
    return hashlib.md5(data.encode()).hexdigest()
