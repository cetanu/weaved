# Local benchmark results

| Workload | Weave | Python reference | `mergedeep` 1.3.4 | vs Python | vs `mergedeep` |
| --- | ---: | ---: | ---: | ---: | ---: |
| `tiny` | 2.10 ± 0.1 µs | 2.73 ± 0.3 µs | 4.19 ± 0.6 µs | 1.3× | 2.0× |
| `flat` (10,000 keys each) | 433 ± 8 µs | 2.25 ± 0.03 ms | 3.73 ± 0.02 ms | 5.2× | 8.6× |
| `nested` (100 services) | 38.3 ± 1 µs | 138 ± 6 µs | 402 ± 10 µs | 3.6× | 10.5× |
| `nested_concat` (100 services, list concat) | 39.5 ± 1 µs | 165 ± 3 µs | 423 ± 5 µs | 4.2× | 10.7× |
| `nested_typesafe` (100 services, `TYPESAFE`) | 41.2 ± 0.7 µs | 305 ± 2 µs | 443 ± 5 µs | 7.4× | 10.8× |
| `nested_typesafe_concat` (100 services, `TYPESAFE \| CONCAT_LISTS`) | 42.0 ± 0.9 µs | 329 ± 2 µs | 464 ± 3 µs | 7.8× | 11.0× |
| `multi_nested` (4 layers × 100 services) | 75.9 ± 7 µs | 388 ± 5 µs | 727 ± 3 µs | 5.1× | 9.6× |
| `multi_nested_concat` (4 layers, list concat) | 84.9 ± 4 µs | 486 ± 4 µs | 789 ± 5 µs | 5.7× | 9.3× |
| `deep` (100 levels) | 14.2 ± 3 µs | 33.9 ± 0.5 µs | 100 ± 2 µs | 2.4× | 7.0× |
| `list_replace` (10,000 scalars) | 32.3 ± 8 µs | 647 ± 7 µs | 873 ± 20 µs | 20.0× | 27.0× |
| `list_concat` (10,000 scalars each) | 57.6 ± 6 µs | 1.32 ± 0.02 ms | 895 ± 8 µs | 22.9× | 15.5× |
| `container_lists` (500 + 500 nested dicts) | 110 ± 1 µs | 446 ± 5 µs | 1.02 ± 0.01 ms | 4.1× | 9.3× |
| `overwritten` (100 services replaced by `None`) | 1.69 ± 0.2 µs | 2.17 ± 0.2 µs | 192 ± 4 µs | 1.3× | 114× |
| `wide_mixed_late` (10k keys, nested last) | 372 ± 10 µs | 2.17 ± 0.03 ms | 5.13 ± 0.05 ms | 5.8× | 13.8× |
| `medium_mixed_late` (32 keys, nested last) | 2.27 ± 0.09 µs | 7.35 ± 0.8 µs | 7.67 ± 0.4 µs | 3.2× | 3.4× |
| `copy_subtree` (10,000-key subtree copy) | 58.1 ± 2 µs | 928 ± 10 µs | 972 ± 10 µs | 16.0× | 16.7× |
| `copy_subtree_mixed_late` (10k keys + nested) | 64.2 ± 7 µs | 923 ± 10 µs | 985 ± 10 µs | 14.4× | 15.3× |

## ASV comparison with 0.1.0

![Chart of selected CPython 3.14 performance gains](performance.svg)

The [interactive report](performance.html) is a single self-contained HTML file.
On each push to `master`, GitHub Actions measures Weaved, appends their speedup ratios to
`performance-data.json`, and regenerates the report.

The maintained Airspeed Velocity suite runs each implementation on the same
workloads and compares revisions statistically. Run it from the project root:

```sh
uv run asv continuous --factor 1.15 --interleave-rounds --split HEAD^ HEAD
```

ASV stores benchmark records in `.asv/results`. After editing Rust, ASV builds
the selected revision in release mode before measuring it.
