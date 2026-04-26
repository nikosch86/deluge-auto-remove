from main import convert


def test_convert_passes_through_str():
    assert convert("hello") == "hello"


def test_convert_passes_through_int():
    assert convert(42) == 42


def test_convert_decodes_bytes():
    assert convert(b"hello") == "hello"


def test_convert_decodes_dict_keys_and_values():
    assert convert({b"name": b"value"}) == {"name": "value"}


def test_convert_handles_nested_dict():
    result = convert({b"outer": {b"inner": b"v"}})
    assert result == {"outer": {"inner": "v"}}


def test_convert_returns_tuple_for_tuple_input():
    result = convert((b"a", b"b"))
    assert isinstance(result, tuple)
    assert result == ("a", "b")


def test_convert_handles_dict_with_tuple_value():
    result = convert({b"key": (b"a", b"b")})
    assert result == {"key": ("a", "b")}


def test_convert_leaves_none_alone():
    assert convert(None) is None
