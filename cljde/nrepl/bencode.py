"""Bencode codec used by the nREPL wire protocol.

Four bencode types are handled:

* integer:    ``i<digits>e``
* byte string: ``<length>:<bytes>`` (length-prefixed raw bytes)
* list:       ``l<items>e``
* dictionary: ``d<key-value pairs>e`` (keys sorted lexicographically)

``encode`` accepts ``int``, ``str`` (written as a UTF-8 byte string),
``bytes``, ``list``, ``tuple`` and ``dict`` and rejects anything else.
``decode`` parses a single value and returns it along with whatever
bytes remain in the buffer. ``decode_all`` greedily parses as many
complete values as possible and reports leftover bytes so callers can
reassemble partial frames across socket reads.
"""

from __future__ import annotations

from typing import Any


class BencodeError(ValueError):
    """Raised when a byte buffer cannot be parsed as bencode."""


class _IncompleteData(Exception):
    """Internal signal that a buffer ends mid-value (not an error)."""


def encode(obj: Any) -> bytes:
    """Return the bencode serialization of ``obj``."""
    if isinstance(obj, bool):
        raise TypeError("bencode does not support bool")
    if isinstance(obj, int):
        return f"i{obj}e".encode("ascii")
    if isinstance(obj, str):
        data = obj.encode("utf-8")
        return f"{len(data)}:".encode("ascii") + data
    if isinstance(obj, (bytes, bytearray)):
        return f"{len(obj)}:".encode("ascii") + bytes(obj)
    if isinstance(obj, (list, tuple)):
        return b"l" + b"".join(encode(item) for item in obj) + b"e"
    if isinstance(obj, dict):
        pairs: list[tuple[bytes, Any]] = []
        for key, value in obj.items():
            if isinstance(key, str):
                key_bytes = key.encode("utf-8")
            elif isinstance(key, (bytes, bytearray)):
                key_bytes = bytes(key)
            else:
                raise TypeError(f"dict keys must be str or bytes, got {type(key).__name__}")
            pairs.append((key_bytes, value))
        pairs.sort(key=lambda kv: kv[0])
        body = b"".join(encode(k) + encode(v) for k, v in pairs)
        return b"d" + body + b"e"
    raise TypeError(f"cannot bencode object of type {type(obj).__name__}")


def decode(data: bytes) -> tuple[Any, bytes]:
    """Decode one bencode value; return ``(value, remaining_bytes)``."""
    try:
        value, idx = _decode_at(data, 0)
    except _IncompleteData as exc:
        raise BencodeError(f"incomplete bencode input: {exc}") from None
    return value, data[idx:]


def decode_all(data: bytes) -> tuple[list[Any], bytes]:
    """Decode every complete value; return ``(values, leftover_bytes)``."""
    values: list[Any] = []
    idx = 0
    n = len(data)
    while idx < n:
        try:
            value, new_idx = _decode_at(data, idx)
        except _IncompleteData:
            break
        values.append(value)
        idx = new_idx
    return values, data[idx:]


def _decode_at(data: bytes, idx: int) -> tuple[Any, int]:
    """Decode one value starting at ``idx``; return ``(value, new_idx)``."""
    if idx >= len(data):
        raise _IncompleteData("empty buffer")
    token = data[idx:idx + 1]
    if token == b"i":
        return _decode_int(data, idx)
    if token == b"l":
        return _decode_list(data, idx)
    if token == b"d":
        return _decode_dict(data, idx)
    if token.isdigit():
        return _decode_bytes(data, idx)
    raise BencodeError(f"unexpected byte {token!r} at offset {idx}")


def _decode_int(data: bytes, idx: int) -> tuple[int, int]:
    end = data.find(b"e", idx + 1)
    if end == -1:
        raise _IncompleteData("unterminated integer")
    payload = data[idx + 1:end]
    if not payload or payload == b"-":
        raise BencodeError(f"empty integer at offset {idx}")
    if payload[:1] == b"0" and payload != b"0":
        raise BencodeError(f"integer with leading zero at offset {idx}")
    if payload[:2] == b"-0":
        raise BencodeError(f"negative zero at offset {idx}")
    try:
        value = int(payload.decode("ascii"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise BencodeError(f"bad integer at offset {idx}: {exc}") from None
    return value, end + 1


def _decode_bytes(data: bytes, idx: int) -> tuple[Any, int]:
    colon = data.find(b":", idx)
    if colon == -1:
        raise _IncompleteData("unterminated byte-string length")
    try:
        length = int(data[idx:colon].decode("ascii"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise BencodeError(f"bad byte-string length at offset {idx}: {exc}") from None
    if length < 0:
        raise BencodeError(f"negative byte-string length at offset {idx}")
    start = colon + 1
    end = start + length
    if end > len(data):
        raise _IncompleteData("truncated byte string")
    raw = data[start:end]
    try:
        return raw.decode("utf-8"), end
    except UnicodeDecodeError:
        return raw, end


def _decode_list(data: bytes, idx: int) -> tuple[list[Any], int]:
    items: list[Any] = []
    idx += 1
    while True:
        if idx >= len(data):
            raise _IncompleteData("unterminated list")
        if data[idx:idx + 1] == b"e":
            return items, idx + 1
        value, idx = _decode_at(data, idx)
        items.append(value)


def _decode_dict(data: bytes, idx: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    idx += 1
    while True:
        if idx >= len(data):
            raise _IncompleteData("unterminated dict")
        if data[idx:idx + 1] == b"e":
            return result, idx + 1
        key, idx = _decode_at(data, idx)
        if isinstance(key, bytes):
            key = key.decode("utf-8", errors="replace")
        if not isinstance(key, str):
            raise BencodeError(f"non-string dict key {key!r}")
        value, idx = _decode_at(data, idx)
        result[key] = value
