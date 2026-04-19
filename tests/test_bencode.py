"""Tests for :mod:`clide.nrepl.bencode`.

Exercises the four bencode types, round-trip semantics, streaming-style
partial reads, dictionary key sorting, and the full catalogue of
malformed inputs called out in the Phase 4 spec.
"""

from __future__ import annotations

import pytest

from clide.nrepl.bencode import BencodeError, decode, decode_all, encode


# --------------------------------------------------------------- encode/decode

def test_encode_integer_positive() -> None:
    """Positive integers encode to ``i<n>e``."""
    assert encode(42) == b"i42e"


def test_encode_integer_zero() -> None:
    """Zero encodes as ``i0e``."""
    assert encode(0) == b"i0e"


def test_encode_integer_negative() -> None:
    """Negative integers keep the sign inside the delimiters."""
    assert encode(-1) == b"i-1e"


def test_encode_large_integer() -> None:
    """Arbitrary-precision integers round-trip."""
    big = 2 ** 128 + 7
    value, leftover = decode(encode(big))
    assert value == big
    assert leftover == b""


def test_encode_string_utf8() -> None:
    """``str`` is written as a UTF-8-prefixed byte string."""
    assert encode("hello") == b"5:hello"
    assert encode("café") == b"5:caf\xc3\xa9"


def test_encode_empty_string() -> None:
    """Empty string encodes as ``0:``."""
    assert encode("") == b"0:"
    assert decode(b"0:") == ("", b"")


def test_encode_bytes() -> None:
    """``bytes`` are written raw; valid UTF-8 decodes back to ``str``."""
    assert encode(b"abc") == b"3:abc"
    value, _ = decode(b"3:abc")
    assert value == "abc"


def test_decode_non_utf8_bytes_preserved() -> None:
    """Non-UTF-8 byte strings decode back to ``bytes`` unchanged."""
    payload = b"\xff\xfe\xfd"
    encoded = encode(payload)
    value, leftover = decode(encoded)
    assert value == payload
    assert leftover == b""


def test_encode_list() -> None:
    """Lists are serialized in order between ``l`` and ``e``."""
    assert encode([1, "a", 2]) == b"li1e1:ai2ee"


def test_encode_tuple_treated_as_list() -> None:
    """Tuples are treated as lists for encoding purposes."""
    assert encode((1, 2)) == encode([1, 2])


def test_encode_dict_sorts_keys() -> None:
    """Dict keys must be sorted lexicographically regardless of insertion order."""
    encoded = encode({"b": 2, "a": 1})
    assert encoded == b"d1:ai1e1:bi2ee"


def test_encode_dict_mixed_key_types() -> None:
    """``str`` and ``bytes`` keys sort by their byte representation."""
    encoded = encode({b"z": 1, "a": 2})
    assert encoded == b"d1:ai2e1:zi1ee"


def test_encode_rejects_bool() -> None:
    """``bool`` is rejected to avoid confusion with ``int``."""
    with pytest.raises(TypeError):
        encode(True)


def test_encode_rejects_float() -> None:
    """Floats have no bencode representation and are rejected."""
    with pytest.raises(TypeError):
        encode(1.5)


def test_encode_rejects_non_str_dict_key() -> None:
    """Dict keys that are neither ``str`` nor ``bytes`` are rejected."""
    with pytest.raises(TypeError):
        encode({1: "one"})


# ------------------------------------------------------------- round-trip/nest

def test_roundtrip_nested_structure() -> None:
    """Deeply nested bencode round-trips without loss."""
    payload = {
        "op": "eval",
        "session": "abc",
        "id": "deadbeef",
        "code": "(+ 1 2)",
        "args": [1, 2, {"x": [b"y"]}],
    }
    encoded = encode(payload)
    decoded, leftover = decode(encoded)
    assert decoded == {**payload, "args": [1, 2, {"x": ["y"]}]}
    assert leftover == b""


# ----------------------------------------------------------------- decode_all

def test_decode_all_multiple_frames() -> None:
    """``decode_all`` returns every complete value in order."""
    buf = encode({"a": 1}) + encode({"b": 2})
    values, leftover = decode_all(buf)
    assert values == [{"a": 1}, {"b": 2}]
    assert leftover == b""


def test_decode_all_partial_tail() -> None:
    """Truncated trailing frames are returned as leftover, not raised."""
    whole = encode({"a": 1}) + encode({"bb": 22})
    split_at = len(encode({"a": 1})) + 3
    values, leftover = decode_all(whole[:split_at])
    assert values == [{"a": 1}]
    assert leftover == whole[len(encode({"a": 1})):split_at]


def test_decode_all_empty() -> None:
    """Decoding an empty buffer yields no values and no leftover."""
    assert decode_all(b"") == ([], b"")


# ------------------------------------------------------------------ malformed

@pytest.mark.parametrize("data", [b"i-0e", b"i01e", b"ie", b"i--1e", b"iabce"])
def test_malformed_integer_raises(data: bytes) -> None:
    """Ill-formed integer encodings raise :class:`BencodeError`."""
    with pytest.raises(BencodeError):
        decode(data)


def test_unknown_type_byte_raises() -> None:
    """A leading byte that starts no known type is rejected."""
    with pytest.raises(BencodeError):
        decode(b"x1:ae")


def test_truncated_single_value_raises_on_decode() -> None:
    """``decode`` (unlike ``decode_all``) raises when input is incomplete."""
    encoded = encode({"code": "(+ 1 2)"})
    with pytest.raises(BencodeError):
        decode(encoded[:-2])
