import inspect
from collections import UserDict

import pytest
from weave import CONCAT_LISTS, NONE, TYPESAFE, MergeFlag, merge


def test_nested_merge():
    left = {"server": {"host": "localhost", "tls": {"enabled": False}}, "keep": 1}
    right = {"server": {"port": 9000, "tls": {"enabled": True}}, "new": 2}
    assert merge(left, right) == {
        "server": {"host": "localhost", "port": 9000, "tls": {"enabled": True}},
        "keep": 1,
        "new": 2,
    }


@pytest.mark.parametrize("left,right", [({}, {}), ({"a": 1}, {}), ({}, {"a": 1})])
def test_empty_inputs(left, right):
    result = merge(left, right)
    assert result == left | right
    assert result is not left
    assert result is not right


@pytest.mark.parametrize("flags", [NONE, CONCAT_LISTS])
@pytest.mark.parametrize(
    "left,right,expected",
    [
        ({"x": 1}, {"x": 2}, {"x": 2}),
        ({"x": {"a": 1}}, {"x": None}, {"x": None}),
        ({"x": [1]}, {"x": {"a": 2}}, {"x": {"a": 2}}),
        ({"x": {"a": 1}}, {"x": [2]}, {"x": [2]}),
        ({"x": 1}, {"x": {}}, {"x": {}}),
        ({"x": {"a": 1}}, {"x": {}}, {"x": {"a": 1}}),
        ({"x": 1}, {"x": False}, {"x": False}),
        ({"x": 1}, {"x": ""}, {"x": ""}),
        ({"x": (1,)}, {"x": (2,)}, {"x": (2,)}),
        ({"x": {1}}, {"x": {2}}, {"x": {2}}),
    ],
)
def test_conflicts(left, right, expected, flags):
    assert merge(left, right, flags=flags) == expected


def test_lists_replace_by_default_and_concatenate_at_every_dict_depth():
    left = {"x": [1, 1], "nested": {"y": [2], "z": []}}
    right = {"x": [1, 3], "nested": {"y": [], "z": [4]}}
    assert merge(left, right) == right
    assert merge(left, right, flags=CONCAT_LISTS) == {
        "x": [1, 1, 1, 3],
        "nested": {"y": [2], "z": [4]},
    }


def test_list_elements_are_not_merged_by_index():
    left = {"x": [{"a": 1}, [1]]}
    right = {"x": [{"b": 2}, [2]]}
    assert merge(left, right, flags=CONCAT_LISTS) == {"x": [{"a": 1}, [1], {"b": 2}, [2]]}


@pytest.mark.parametrize("flags", [NONE, CONCAT_LISTS])
def test_all_surviving_containers_are_independent(flags):
    left = {
        "untouched": {"items": [{"values": [1]}]},
        "merged": {"left": [2]},
        "conflict": [{"values": [3]}],
    }
    right = {
        "added": [{"values": [4]}],
        "merged": {"right": [5]},
        "conflict": [{"values": [6]}],
    }
    result = merge(left, right, flags=flags)
    result["untouched"]["items"][0]["values"].append(7)
    result["merged"]["left"].append(8)
    result["merged"]["right"].append(9)
    result["added"][0]["values"].append(10)
    for item in result["conflict"]:
        item["values"].clear()
    assert left == {
        "untouched": {"items": [{"values": [1]}]},
        "merged": {"left": [2]},
        "conflict": [{"values": [3]}],
    }
    assert right == {
        "added": [{"values": [4]}],
        "merged": {"right": [5]},
        "conflict": [{"values": [6]}],
    }


def test_arbitrary_leaves_and_keys_preserve_identity():
    class Leaf:
        def __deepcopy__(self, memo):
            raise AssertionError("must not invoke deepcopy")

    key, leaf = object(), Leaf()
    opaque_tuple, opaque_set = ([1],), {1}
    left = {key: leaf, "tuple": opaque_tuple, "set": opaque_set, 1: "old"}
    result = merge(left, {True: "new", ("tuple", 2): b"bytes", None: 10**100, "π": "雪"})
    assert next(iter(result)) is key
    assert result[key] is leaf
    assert result["tuple"] is opaque_tuple
    assert result["set"] is opaque_set
    assert result[1] == "new"
    assert result[None] == 10**100
    assert result["π"] == "雪"


def test_order_and_equal_key_identity():
    class Key:
        def __init__(self, name):
            self.name = name

        def __hash__(self):
            return hash(self.name)

        def __eq__(self, other):
            return isinstance(other, Key) and self.name == other.name

    left_key, right_key = Key("same"), Key("same")
    result = merge(
        {"first": 1, left_key: {"a": 1}, "last": 3},
        {"new": 4, right_key: {"b": 2}, "first": 5},
    )
    assert list(result) == ["first", left_key, "last", "new"]
    assert list(result)[1] is left_key
    assert result[left_key] == {"a": 1, "b": 2}


def test_container_subclasses_use_stored_contents():
    class DictSubclass(dict):
        def items(self):
            raise AssertionError("must use stored dictionary entries")

        def copy(self):
            raise AssertionError("must use native dictionary copying")

        def __getitem__(self, key):
            raise AssertionError("must use native dictionary lookup")

    class ListSubclass(list):
        def __iter__(self):
            raise AssertionError("must use stored list elements")

        def __add__(self, other):
            raise AssertionError("must use native list concatenation")

        def __getitem__(self, key):
            raise AssertionError("must use native list access")

    left = DictSubclass(x=DictSubclass(a=1), items=ListSubclass([DictSubclass(a=1)]))
    right = DictSubclass(x=DictSubclass(b=2), items=ListSubclass([ListSubclass([2])]))
    result = merge(left, right, flags=CONCAT_LISTS)
    assert result == {"x": {"a": 1, "b": 2}, "items": [{"a": 1}, [2]]}
    assert type(result) is dict
    assert type(result["x"]) is dict
    assert type(result["items"]) is list
    assert type(result["items"][0]) is dict
    assert type(result["items"][1]) is list


@pytest.mark.parametrize("flags", [NONE, CONCAT_LISTS])
def test_same_input_is_safe(flags):
    source = {"nested": {"items": [{"a": 1}]}}
    result = merge(source, source, flags=flags)
    count = 2 if flags & CONCAT_LISTS else 1
    assert result == {"nested": {"items": [{"a": 1}] * count}}
    result["nested"]["items"][0]["a"] = 2
    assert source == {"nested": {"items": [{"a": 1}]}}
    if flags & CONCAT_LISTS:
        assert result["nested"]["items"][1] == {"a": 1}


def test_shared_containers_are_copied_per_occurrence():
    shared = {"items": [1]}
    result = merge({"a": shared}, {"b": shared})
    result["a"]["items"].append(2)
    assert result["b"]["items"] == [1]
    assert shared == {"items": [1]}


@pytest.mark.parametrize("invalid", [None, [], (), "dict", 1, UserDict(a=1)])
def test_requires_dict_arguments(invalid):
    with pytest.raises(TypeError):
        merge(invalid)
    with pytest.raises(TypeError):
        merge(invalid, {})
    with pytest.raises(TypeError):
        merge({}, invalid)
    with pytest.raises(TypeError):
        merge({}, {}, invalid)


def test_keyword_only_options_and_inspectable_signature():
    with pytest.raises(TypeError):
        merge({}, {}, True)
    with pytest.raises(TypeError):
        merge({}, {}, unknown=True)
    signature = inspect.signature(merge)
    assert list(signature.parameters) == ["dicts", "flags"]
    assert signature.parameters["dicts"].kind == inspect.Parameter.VAR_POSITIONAL
    assert signature.parameters["flags"].kind == inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["flags"].default == 0


def test_flags_values_and_validation():
    assert MergeFlag.NONE == 0o0
    assert MergeFlag.CONCAT_LISTS == 0o1
    assert MergeFlag.TYPESAFE == 0o2
    assert (CONCAT_LISTS | TYPESAFE) == 0o3
    for bad in (-1, 0o4, 0o10, 99):
        with pytest.raises(ValueError, match="invalid merge flags"):
            merge({}, {}, flags=bad)
    with pytest.raises(TypeError):
        merge({}, {}, flags="typesafe")


def test_typesafe_matching_and_conflicting_types():
    left = {"a": 1, "b": [1], "nested": {"x": "old", "y": None}, "only_left": 10}
    right = {"a": 2, "b": [2], "nested": {"x": "new", "y": None}, "only_right": "ok"}

    assert merge(left, right, flags=TYPESAFE) == {
        "a": 2,
        "b": [2],
        "nested": {"x": "new", "y": None},
        "only_left": 10,
        "only_right": "ok",
    }
    assert merge(left, right, flags=TYPESAFE | CONCAT_LISTS) == {
        "a": 2,
        "b": [1, 2],
        "nested": {"x": "new", "y": None},
        "only_left": 10,
        "only_right": "ok",
    }

    for a, b in (
        ({"x": 1}, {"x": "1"}),
        ({"x": 1}, {"x": True}),
        ({"x": {"a": 1}}, {"x": None}),
        ({"x": [1]}, {"x": (1,)}),
        ({"nested": {"k": 1}}, {"nested": {"k": 1.0}}),
    ):
        with pytest.raises(TypeError, match="conflicting types"):
            merge(a, b, flags=TYPESAFE)

    # Wide dicts (>= 8 keys) must also check types rather than bulk-updating.
    wide_left = {f"k{i}": i for i in range(16)}
    wide_right = {f"k{i}": i for i in range(16)}
    wide_right["k15"] = "mismatch"
    with pytest.raises(TypeError, match="conflicting types"):
        merge(wide_left, wide_right, flags=TYPESAFE)


def test_typesafe_variadic():
    assert merge(
        {"a": 1, "items": [1], "nested": {"x": 1}},
        {"a": 2, "items": [2], "nested": {"y": 2}},
        {"a": 3, "items": [3], "nested": {"x": 4}},
        flags=TYPESAFE | CONCAT_LISTS,
    ) == {"a": 3, "items": [1, 2, 3], "nested": {"x": 4, "y": 2}}

    # Type mismatch in a middle layer must still raise even if the last layer matches the first.
    with pytest.raises(TypeError, match="conflicting types"):
        merge({"x": 1}, {"x": "bad"}, {"x": 2}, flags=TYPESAFE)

    assert merge(flags=TYPESAFE) == {}
    assert merge({"x": 1}, flags=TYPESAFE) == {"x": 1}


def test_zero_and_single_dict_inputs():
    assert merge() == {}
    assert merge(flags=CONCAT_LISTS) == {}

    class DictSubclass(dict):
        pass

    class ListSubclass(list):
        pass

    source = DictSubclass(nested=DictSubclass(items=ListSubclass([DictSubclass(a=1)])))
    copied = merge(source)
    assert copied == {"nested": {"items": [{"a": 1}]}}
    assert copied is not source
    assert type(copied) is dict
    assert type(copied["nested"]) is dict
    assert type(copied["nested"]["items"]) is list
    assert type(copied["nested"]["items"][0]) is dict
    copied["nested"]["items"][0]["a"] = 99
    assert source["nested"]["items"][0]["a"] == 1


def test_variadic_merge_nested_lists_and_overrides():
    defaults = {
        "server": {"host": "localhost", "port": 8000, "tls": {"enabled": False}},
        "plugins": ["logging"],
        "broken": {"a": 1},
        "keep": "base",
    }
    env = {
        "server": {"port": 9000},
        "plugins": ["auth"],
        "broken": 42,
        "env_only": {"x": [1]},
    }
    cli = {
        "server": {"tls": {"enabled": True, "cert": "pem"}},
        "plugins": ["metrics"],
        "broken": {"b": 2},
    }

    assert merge(defaults, env, cli) == {
        "server": {"host": "localhost", "port": 9000, "tls": {"enabled": True, "cert": "pem"}},
        "plugins": ["metrics"],
        "broken": {"b": 2},
        "keep": "base",
        "env_only": {"x": [1]},
    }
    result = merge(defaults, env, cli, flags=CONCAT_LISTS)
    assert result["plugins"] == ["logging", "auth", "metrics"]
    result["env_only"]["x"].append(2)
    assert env["env_only"]["x"] == [1]


def test_variadic_non_contiguous_and_broken_chains():
    assert merge({"x": {"a": 1}}, {}, {"x": {"b": 2}}) == {"x": {"a": 1, "b": 2}}
    assert merge({"x": [1]}, {}, {"x": [2]}, {"x": [3]}, flags=CONCAT_LISTS) == {"x": [1, 2, 3]}
    assert merge({"x": [1]}, {"x": None}, {"x": [2]}, {"x": [3]}, flags=CONCAT_LISTS) == {
        "x": [2, 3]
    }
    # Nested containers inside 3+ concatenated lists are independent copies.
    a = {"x": [{"v": [1]}]}
    b = {"x": [{"v": [2]}]}
    c = {"x": [{"v": [3]}]}
    merged = merge(a, b, c, flags=CONCAT_LISTS)
    assert merged == {"x": [{"v": [1]}, {"v": [2]}, {"v": [3]}]}
    for item in merged["x"]:
        item["v"].clear()
    assert (a, b, c) == ({"x": [{"v": [1]}]}, {"x": [{"v": [2]}]}, {"x": [{"v": [3]}]})


def test_variadic_order_key_identity_and_overwritten_cycles():
    class Key:
        def __init__(self, name):
            self.name = name

        def __hash__(self):
            return hash(self.name)

        def __eq__(self, other):
            return isinstance(other, Key) and self.name == other.name

    k0, k1, k2 = Key("k"), Key("k"), Key("k")
    result = merge({k0: 1, "a": 1}, {k1: 2, "b": 2}, {k2: 3, "c": 3})
    assert list(result) == [k0, "a", "b", "c"]
    assert list(result)[0] is k0
    assert result[k0] == 3

    cycle = {}
    cycle["self"] = cycle
    assert merge({"x": cycle}, {"y": 1}, {"x": 2}) == {"x": 2, "y": 1}
    with pytest.raises(RecursionError):
        merge(cycle)


def test_variadic_container_subclasses_in_lists():
    class ListSubclass(list):
        def __iter__(self):
            raise AssertionError("must use stored list elements")

        def __getitem__(self, key):
            raise AssertionError("must use native list access")

    result = merge(
        {"x": ListSubclass([1])},
        {"x": ListSubclass([2])},
        {"x": ListSubclass([3])},
        flags=CONCAT_LISTS,
    )
    assert result == {"x": [1, 2, 3]}
    assert type(result["x"]) is list


@pytest.mark.parametrize("flags", [NONE, CONCAT_LISTS])
@pytest.mark.parametrize("kind", ["dict", "list", "mixed"])
@pytest.mark.parametrize("side", ["left", "right", "both"])
def test_cycles_raise_and_subsequent_merges_work(flags, kind, side):
    if kind == "dict":
        cyclic = {}
        cyclic["self"] = cyclic
    elif kind == "list":
        cyclic = []
        cyclic.append(cyclic)
    else:
        cyclic = {"items": []}
        cyclic["items"].append(cyclic)
    left = {"x": cyclic} if side in ("left", "both") else {}
    right = {"x": cyclic} if side in ("right", "both") else {}
    with pytest.raises(RecursionError):
        merge(left, right, flags=flags)
    assert merge({"x": {"a": 1}}, {"x": {"b": 2}}) == {"x": {"a": 1, "b": 2}}


def test_overwritten_cycles_are_not_traversed():
    cycle = {}
    cycle["self"] = cycle
    assert merge({"x": cycle}, {"x": 1}) == {"x": 1}


@pytest.mark.parametrize("side", ["left", "right", "both"])
def test_depth_guard(side):
    tree = {"leaf": 1}
    for _ in range(300):
        tree = {"child": tree}
    left = tree if side in ("left", "both") else {}
    right = tree if side in ("right", "both") else {}
    with pytest.raises(RecursionError):
        merge(left, right)


def test_256_container_levels_can_be_copied_and_merged():
    tree = {"leaf": 1}
    for _ in range(255):
        tree = {"child": tree}
    for left, right in ((tree, {}), ({}, tree), (tree, tree)):
        result = merge(left, right)
        for _ in range(255):
            result = result["child"]
        assert result == {"leaf": 1}


def test_hashing_errors_propagate_without_changing_inputs():
    class Key:
        broken = False

        def __hash__(self):
            if self.broken:
                raise ValueError("broken hash")
            return 0

    key = Key()
    left, right = {}, {key: {"items": [1]}}
    key.broken = True
    with pytest.raises(ValueError, match="broken hash"):
        merge(left, right)
    key.broken = False
    assert left == {}
    assert right[key] == {"items": [1]}


def test_equality_errors_propagate_without_changing_inputs():
    class Key:
        def __hash__(self):
            return 0

        def __eq__(self, other):
            raise ValueError("broken equality")

    first, second = Key(), Key()
    left, right = {first: {"a": 1}}, {second: {"b": 2}}
    with pytest.raises(ValueError, match="broken equality"):
        merge(left, right)
    assert left[first] == {"a": 1}
    assert right[second] == {"b": 2}
