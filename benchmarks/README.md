# Local benchmark results

Measured on 2026-10-02 with CPython 3.14.0, Rust 1.98.1, Linux x86-64,
and an AMD Ryzen 7 9800X3D. Weave was compiled in release mode. Both
implementations return independent dictionary/list containers and share opaque
leaves; each case checks equivalent results before timing.

| Workload | Weave | Python reference | Speedup |
| --- | ---: | ---: | ---: |
| Tiny dictionaries | 148 ns | 704 ns | 4.8× |
| Flat dictionaries, 10,000 keys each | 329 µs | 2,050 µs | 6.2× |
| Nested configuration, 100 services | 21.4 µs | 126 µs | 5.9× |
| Nested configuration with list concatenation | 22.8 µs | 152 µs | 6.7× |
| Deep dictionaries, 100 levels | 7.70 µs | 30.9 µs | 4.0× |
| Replace a list of 10,000 scalars | 14.7 µs | 574 µs | 39.1× |
| Concatenate lists of 10,000 scalars each | 30.6 µs | 1,170 µs | 38.1× |
| Concatenate lists of nested containers | 96.3 µs | 431 µs | 4.5× |
| Overwrite a nested subtree with `None` | 148 ns | 515 ns | 3.5× |

These are historical short local measurements from the original pyperf harness,
not performance guarantees or comparisons against other libraries. Pyperf
reported insufficient samples to establish variation below 1%. The Python
reference recursively visits scalar list elements; Weave uses native copies and
only recurses into containers, which accounts for the larger improvement on
scalar lists.

## ASV comparison with 0.1.0

![Chart of selected CPython 3.14 performance gains](performance.svg)

The [interactive report](performance.html) is a single self-contained HTML file.
On each push to `master`, GitHub Actions measures Weaved, the Python reference,
and `mergedeep` in the same ASV run, appends their speedup ratios to
`performance-data.json`, and regenerates the report. The ratios reduce variation
between hosted runner instances. Download the HTML and open it in a browser; no
hosted Pages site is needed.

On the same machine, a 20-repeat CPU-pinned CPython 3.14 ASV comparison on
2026-10-03 measured the 10,000-key flat merge at 342 ± 4 µs on the published
0.1.0 source and 302 ± 5 µs on current `master` (about 12% faster, below ASV's
1.15 threshold). A wide mixed case with one nested value at the end improved
from 285 ± 3 µs to 244 ± 4 µs (about 14%). Replacing a 10,000-item scalar list
improved from 20.4 ± 0.6 µs to 15.1 ± 0.9 µs (about 26%); concatenating two
such lists improved from 39.0 ± 0.8 µs to 28.3 ± 1 µs (about 27%). The
32-key mixed case with a nested value last improved from 3.00 ± 0.4 µs to
2.11 ± 0.3 µs (about 30%).

The maintained Airspeed Velocity suite runs each implementation on the same
workloads and compares revisions statistically. Run it from the project root:

```sh
uv run asv continuous --factor 1.15 --interleave-rounds --split HEAD^ HEAD
```

ASV stores benchmark records in `.asv/results`. After editing Rust, ASV builds
the selected revision in release mode before measuring it.

The scalar subtree copy path was then changed to scan dictionary entries
without creating Python wrappers for scalar values. Twenty-repeat CPU-pinned
CPython 3.14 ASV measurements put this 10,000-key copy at 50.1 ± 0.5 µs before
and 38.7 ± 0.8 µs after (about 23% faster). With a nested value at the end, it
improved from 50.4 ± 0.5 µs to 38.7 ± 0.9 µs (about 23%). A 20-repeat
CPU-pinned CPython 3.11 comparison measured 48.4 ± 0.7 µs and 44.0 ± 1 µs
(about 9% faster, below ASV's 1.15 change threshold). With a nested value at
the end, it improved from 50.3 ± 1 µs to 44.9 ± 1 µs (about 11%). On CPython
3.11, list replacement improved from 14.7 ± 0.3 µs to 11.2 ± 0.2 µs (about
24%) and concatenation from 28.3 ± 0.4 µs to 21.9 ± 0.3 µs (about 23%). The
flat merge improved from 358 ± 4 µs to 340 ± 3 µs and the wide mixed merge
from 293 ± 5 µs to 276 ± 5 µs on CPython 3.11; both stayed below the 1.15
threshold. Large integer-key maps also showed no significant change. A string
map with one integer key at the end measured
279 ± 3 µs on the published source and 307 ± 3 µs on current `master` (about
10% slower, below the 1.15 threshold); the optimized path must scan keys to
prove it can safely bulk-update them. A 32-key map with one integer key at the
end measured 2.14 ± 0.08 µs and 2.40 ± 0.08 µs respectively (about 12% slower,
below the threshold). Copies of scalar-only dictionaries from
1 to 256 entries showed no significant change, so the direct scan remains
unconditional in the subtree-copy path.
For a 32-key map with a nested value last, a 20-repeat CPU-pinned comparison
improved from 3.00 ± 0.4 µs on the published source to 2.11 ± 0.3 µs on current
`master` (about 30% faster) on CPython 3.14. CPython 3.11 improved from 2.18 ±
0.2 µs to 1.42 ± 0.1 µs (about 35%). The raw-scan path now starts at 8
entries and only bulk-updates after the first 2 entries contain no nested
containers. Moving the cutoff from 16 to
8 improved the 8-entry late-nested case from 1.73 ± 0.2 µs to 1.28 ± 0.2 µs
(about 26%) in a 20-repeat CPU-pinned CPython 3.14 comparison. The matching
CPython 3.11 run showed no significant change. Four-entry mixed maps and
8-entry scalar-only, early-nested, prefix-boundary, and late-integer cases
showed no significant change when lowering the cutoff.
Lowering the prefix from 4 entries to 2 improved an 8-entry map with its
nested value at position 2 by about 20% on CPython 3.14 and 14% on CPython 3.11;
the early, boundary, nested, and wide cases showed no significant change.

## Comparison with `mergedeep`

Measured on 2026-11-23 with CPython 3.14.7, macOS (Darwin 24.6.0, arm64),
Apple M1 Pro, and [`mergedeep`](https://pypi.org/project/mergedeep/) 1.3.4 via
ASV (`--interleave-rounds`). Weave was compiled in release mode. Because
`mergedeep.merge` mutates its first argument in place, it is benchmarked in its
idiomatic non-mutating form `mergedeep.merge({}, left, right, strategy=...)`
using `Strategy.REPLACE` or `Strategy.ADDITIVE` to match `concat_lists`. Every
case verifies equal results before timing.

| Workload | Weave | Python reference | `mergedeep` 1.3.4 | Speedup vs `mergedeep` |
| --- | ---: | ---: | ---: | ---: |
| `tiny` | 2.10 ± 0.1 µs | 2.73 ± 0.3 µs | 4.19 ± 0.6 µs | 2.0× |
| `flat` (10,000 keys each) | 433 ± 8 µs | 2.25 ± 0.03 ms | 3.73 ± 0.02 ms | 8.6× |
| `nested` (100 services) | 38.3 ± 1 µs | 138 ± 6 µs | 402 ± 10 µs | 10.5× |
| `nested_concat` (100 services, list concat) | 39.5 ± 1 µs | 165 ± 3 µs | 423 ± 5 µs | 10.7× |
| `deep` (100 levels) | 14.2 ± 3 µs | 33.9 ± 0.5 µs | 100 ± 2 µs | 7.0× |
| `list_replace` (10,000 scalars) | 32.3 ± 8 µs | 647 ± 7 µs | 873 ± 20 µs | 27.0× |
| `list_concat` (10,000 scalars each) | 57.6 ± 6 µs | 1.32 ± 0.02 ms | 895 ± 8 µs | 15.5× |
| `container_lists` (500 + 500 nested dicts) | 110 ± 1 µs | 446 ± 5 µs | 1.02 ± 0.01 ms | 9.3× |
| `overwritten` (100 services replaced by `None`) | 1.69 ± 0.2 µs | 2.17 ± 0.2 µs | 192 ± 4 µs | 114× |
| `wide_mixed_late` (10k keys, nested last) | 372 ± 10 µs | 2.17 ± 0.03 ms | 5.13 ± 0.05 ms | 13.8× |
| `medium_mixed_late` (32 keys, nested last) | 2.27 ± 0.09 µs | 7.35 ± 0.8 µs | 7.67 ± 0.4 µs | 3.4× |
| `copy_subtree` (10,000-key subtree copy) | 58.1 ± 2 µs | 928 ± 10 µs | 972 ± 10 µs | 16.7× |
| `copy_subtree_mixed_late` (10k keys + nested) | 64.2 ± 7 µs | 923 ± 10 µs | 985 ± 10 µs | 15.3× |

`mergedeep` calls `copy.deepcopy` on every inserted or replaced value and, in
non-mutating `merge({}, left, right)` form, deep-copies `left` before `right`
is applied (which explains the 114× gap on `overwritten`). Weave avoids
`copy.deepcopy`, skips overwritten subtrees, and uses native dict/list copies
when no nested containers need recursion.

### Feature parity and semantic differences

`weave` and `mergedeep` overlap on recursive dictionary merging and list
concatenation, but differ in several ways:

| Capability | `weave` | `mergedeep` |
| --- | --- | --- |
| Mutation | Always non-mutating; returns a new `dict` | Mutates `destination` in place (pass `{}` first for a new `dict`) |
| Number of inputs | Binary: `merge(left, right)` | Variadic: `merge(destination, *sources)` |
| Mapping types | `dict` and `dict` subclasses (normalized to plain `dict`) | Any `MutableMapping` / `Mapping` (e.g. `UserDict`, `ChainMap`, `MappingProxyType`, `Counter`) |
| Merge strategies | `concat_lists=False` (replace) or `True` (concatenate `list`s) | `Strategy.REPLACE`, `ADDITIVE` (`list`, `set`, `tuple`, `Counter`), `TYPESAFE` / `TYPESAFE_REPLACE`, `TYPESAFE_ADDITIVE` |
| Copying semantics | Copies `dict` and `list` containers only; keys and opaque objects (tuples, sets, custom instances) keep identity | Uses `copy.deepcopy` on copied values (invokes `__deepcopy__` and copies tuples, sets, and custom objects) |
| Overwritten subtrees | Not traversed or copied | Deep-copied from `left` first when using `merge({}, left, right)` |
| Cycles and recursion | 256-level depth guard; traversed cycles raise `RecursionError` | Relies on Python's recursion limit for `_deepmerge`; `deepcopy` preserves cycles in copied subtrees via its memo dict |
| Runtime / packaging | Rust/PyO3 extension (CPython 3.11+) | Pure Python, no dependencies (any Python 3 implementation) |

One subtle `mergedeep` edge case: `_deepmerge` short-circuits with `pass` when
`dst[key] is src[key]`, so under `Strategy.ADDITIVE` two references to the exact
same immutable tuple (or same list in an in-place merge) are not concatenated.
