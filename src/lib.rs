mod merge;
mod recursion;

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyTuple};

/// Deeply merge zero or more dictionaries into a new dictionary.
///
/// Nested dictionaries merge recursively from left to right. Other conflicts
/// take the rightmost value. Pass `flags` (bitmask of `MergeFlag` values) to
/// customize behavior:
/// - `CONCAT_LISTS` (0o1): concatenate consecutive lists in left-to-right order.
/// - `TYPESAFE` (0o2): raise TypeError when conflicting values have different types.
///
/// Dicts and lists in the result are independent of the inputs. Keys and all
/// other values retain their identity. Container subclasses become plain dicts
/// and lists. Cycles and excessive nesting raise RecursionError.
#[pyfunction]
#[pyo3(name = "merge", signature = (*dicts, flags=0))]
fn py_merge<'py>(
    py: Python<'py>,
    dicts: &Bound<'py, PyTuple>,
    flags: i64,
) -> PyResult<Bound<'py, PyDict>> {
    let options = merge::MergeOptions::from_flags(flags)?;
    match dicts.len() {
        0 => Ok(PyDict::new(py)),
        1 => {
            let only = dicts.get_item(0)?.cast_into::<PyDict>()?;
            merge::copy_dict(&only, 0)
        }
        2 => {
            let left = dicts.get_item(0)?.cast_into::<PyDict>()?;
            let right = dicts.get_item(1)?.cast_into::<PyDict>()?;
            merge::merge_dicts(&left, &right, options, 0)
        }
        _ => {
            let mut extracted = Vec::with_capacity(dicts.len());
            for item in dicts.iter() {
                extracted.push(item.cast_into::<PyDict>()?);
            }
            merge::merge_many(&extracted, options, 0)
        }
    }
}

/// Rust-backed deep merging of Python dictionaries.
#[pymodule(gil_used = true)]
fn _weave(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(py_merge, module)?)?;
    Ok(())
}
