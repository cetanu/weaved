# Weave

A Rust-backed Python library for merging nested dictionaries. One function,
no runtime Python dependencies, and no mutation of your inputs.

Install the `weaved` distribution from PyPI:

```sh
python -m pip install weaved
```

The import package remains `weave`. Installing from source requires Rust; the
extension uses [PyO3](https://pyo3.rs/) and is built with
[maturin](https://www.maturin.rs/).

```python
from weave import merge

defaults = {"server": {"host": "localhost", "port": 8000}, "plugins": ["logging"]}
env = {"server": {"port": 9000}, "plugins": ["metrics"]}
cli = {"server": {"tls": True}, "plugins": ["tracing"]}

merge(defaults, env, cli)
# {"server": {"host": "localhost", "port": 9000, "tls": True}, "plugins": ["tracing"]}

merge(defaults, env, cli, concat_lists=True)
# {"server": {"host": "localhost", "port": 9000, "tls": True}, "plugins": ["logging", "metrics", "tracing"]}
```

## Merge semantics

`merge(*dicts, concat_lists=False) -> dict`

- Accepts zero or more dictionaries (subclasses are accepted). `merge()` returns
  `{}`; `merge(d)` returns an independent copy of `d`'s dict/list containers.
- Dictionaries merge from left to right. When consecutive values at a key are
  dictionaries, they merge recursively.
- Otherwise the rightmost value wins, including `None` and empty values.
- With `concat_lists=True`, consecutive lists at a key concatenate in
  left-to-right order at every dictionary depth. Duplicates remain; elements
  are not merged by index.
- Every dictionary and list reached through dictionary values or list elements
  is copied. Changing those containers in the result does not change any input.
  Container subclasses become plain dictionaries and lists, using their stored
  contents rather than overridden Python methods.
- Keys and other objects (including tuples, sets, and custom instances) retain
  their identity. Weave does not traverse them or call `__deepcopy__`.
  For example, a list inside an opaque tuple remains shared.
- Repeated references to the same container are copied separately; alias
  relationships are not preserved.
- Existing keys retain the insertion order and key identity of the leftmost
  dictionary that introduced them. New keys are appended in order. All hashable
  Python keys are supported.
- Traversed cycles or more than 256 nested dictionary/list levels raise
  `RecursionError`; Python's own stack guard can stop traversal earlier.
  Overwritten values are not traversed.
- Exceptions from key hashing or equality propagate. Inputs must not be mutated
  during a merge, including from key callbacks.

## Development

Requires CPython 3.11+ and Rust 1.85+ to build from source. Native wheels do not
require Rust. The extension uses the full Python API for performance, so wheels
are specific to a Python version. It holds the GIL while accessing Python objects.

```sh
uv sync
uv run pytest
uv run ruff check .
cargo fmt --check
cargo clippy --all-targets -- -D warnings
```

`uv sync` builds the extension in release mode. After editing Rust, rebuild it
with `uv run maturin develop --release` before testing. Build distribution
artifacts with `uv run maturin build --release` and `uv run maturin sdist`.

## Performance

The merge walks Python containers directly through PyO3, with native dictionary
copies and list concatenation. Scalar leaves stay as Python objects; there is no
JSON encoding, deserialization, or conversion to Rust maps.

Run the Airspeed Velocity benchmarks against an equivalent Python implementation
and [`mergedeep`](https://pypi.org/project/mergedeep/):

```sh
uv sync
uv run asv continuous --factor 1.15 --interleave-rounds --split HEAD^ HEAD
```

Benchmarks check matching results before timing and cover flat dictionaries,
nested configuration, deep dictionaries, large lists, and list concatenation.
Weave and the Python reference copy dict/list containers and share opaque leaves,
while `mergedeep` is benchmarked in non-mutating mode (`mergedeep.merge({}, left, right, ...)`). ASV
stores results in `.asv/results`; CI compares each pull request against its base
revision on the same runner and uploads the result files as a workflow artifact.
The 15% threshold filters small variations. Use release builds and measure your
own workload; Python allocation and key hashing still determine much of the cost.

See [local benchmark results](benchmarks/README.md) for measured timings and
the machine and sampling conditions.

The merge-to-merge timing report is generated at
[`benchmarks/performance.html`](benchmarks/performance.html). Download the file
and open it in a browser to view the interactive charts.
