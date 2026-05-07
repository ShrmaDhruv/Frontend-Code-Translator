import hashlib
from layer3.response_parser import ParsedResponse


class DetectionCache:
    """
    In-memory cache mapping SHA256(code) → ParsedResponse.

    Why SHA256?
      - Fixed length key regardless of code size
      - Identical code always produces identical hash
      - Collision probability is astronomically low

    Note:
      This is an in-memory cache — it resets when the
      program restarts. For persistence across sessions,
      replace _store with a shelve or sqlite3 backend.
    """

    def __init__(self):
        self._store: dict[str, ParsedResponse] = {}


    def _hash(self, code: str) -> str:
        """Generate SHA256 hash of the code string."""
        return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


    def get(self, code: str) -> ParsedResponse | None:
        """
        Retrieve cached result for this code.

        Args:
            code : Raw source code string

        Returns:
            ParsedResponse if cached, None if cache miss.
        """
        key = self._hash(code)
        return self._store.get(key)


    def set(self, code: str, result: ParsedResponse) -> None:
        """
        Store a detection result in the cache.

        Args:
            code   : Raw source code string (used as cache key)
            result : ParsedResponse to store
        """
        key = self._hash(code)
        self._store[key] = result


    def clear(self) -> None:
        """Wipe the entire cache."""
        self._store.clear()


    @property
    def size(self) -> int:
        """Number of cached entries."""
        return len(self._store)