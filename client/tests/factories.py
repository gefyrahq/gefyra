import itertools

_seq = itertools.count(1)

def ClientIdFactory(prefix: str = "testclient") -> str:
    """
    Deterministic client ID generator for tests. No randomness, no extra deps.
    """
    return f"{prefix}-{next(_seq)}"