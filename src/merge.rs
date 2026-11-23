use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyString};

use crate::recursion::RecursionGuard;

pub(crate) fn merge_dicts<'py>(
    left: &Bound<'py, PyDict>,
    right: &Bound<'py, PyDict>,
    concat_lists: bool,
    depth: usize,
) -> PyResult<Bound<'py, PyDict>> {
    let _guard = RecursionGuard::enter(left.py(), depth)?;
    let result = left.copy()?;

    // A native dict copy preserves key identity and order and handles scalar
    // values cheaply. Copy only containers that survive the merge.
    for (key, value) in left.iter() {
        if is_container(&value) && !right.contains(&key)? {
            result.set_item(key, copy_value(&value, depth + 1)?)?;
        }
    }

    if right.len() >= 8 {
        let py = left.py();
        let mut position = 0;
        let mut key_ptr = std::ptr::null_mut();
        let mut value_ptr = std::ptr::null_mut();
        let mut inspected = 0;
        let mut prefix_contains_containers = false;
        let mut exact_string_keys = true;
        let mut container_entries = Vec::new();

        while inspected < right.len() {
            // SAFETY: `right` remains alive and unmodified for this scan, and
            // the GIL is held for the full call.
            if unsafe {
                pyo3::ffi::PyDict_Next(right.as_ptr(), &mut position, &mut key_ptr, &mut value_ptr)
            } == 0
            {
                break;
            }
            // SAFETY: PyDict_Next returned a live key pointer while `right`
            // is alive and the GIL remains held.
            if unsafe { pyo3::ffi::PyUnicode_CheckExact(key_ptr) == 0 } {
                exact_string_keys = false;
                break;
            }

            // SAFETY: PyDict_Next returned a live value pointer while `right`
            // is alive and the GIL remains held.
            let is_container = unsafe {
                pyo3::ffi::PyDict_Check(value_ptr) != 0 || pyo3::ffi::PyList_Check(value_ptr) != 0
            };
            if inspected < 2 && is_container {
                prefix_contains_containers = true;
                break;
            } else if is_container {
                // SAFETY: both pointers are borrowed from the live `right` dict;
                // the constructors increment their references for these Bounds.
                container_entries.push(unsafe {
                    (
                        Bound::from_borrowed_ptr(py, key_ptr),
                        Bound::from_borrowed_ptr(py, value_ptr),
                    )
                });
            }
            inspected += 1;
        }

        if !exact_string_keys || prefix_contains_containers {
            for (key, right_value) in right.iter() {
                result.set_item(
                    &key,
                    merge_entry(left, &key, &right_value, concat_lists, depth + 1)?,
                )?;
            }
            return Ok(result);
        }

        result.update(right.as_mapping())?;
        for (key, right_value) in container_entries {
            result.set_item(
                &key,
                merge_entry(left, &key, &right_value, concat_lists, depth + 1)?,
            )?;
        }
        return Ok(result);
    } else if right.len() >= 4
        && right
            .iter()
            .all(|(key, value)| !is_container(&value) && key.is_exact_instance_of::<PyString>())
    {
        result.update(right.as_mapping())?;
        return Ok(result);
    }

    for (key, right_value) in right.iter() {
        result.set_item(
            &key,
            merge_entry(left, &key, &right_value, concat_lists, depth + 1)?,
        )?;
    }

    Ok(result)
}

fn merge_entry<'py>(
    left: &Bound<'py, PyDict>,
    key: &Bound<'py, PyAny>,
    right: &Bound<'py, PyAny>,
    concat_lists: bool,
    depth: usize,
) -> PyResult<Bound<'py, PyAny>> {
    if let Ok(right_dict) = right.cast::<PyDict>() {
        if let Some(left_dict) = left
            .get_item(key)?
            .and_then(|value| value.cast_into::<PyDict>().ok())
        {
            return Ok(merge_dicts(&left_dict, right_dict, concat_lists, depth)?.into_any());
        }
    } else if concat_lists {
        if let Ok(right_list) = right.cast::<PyList>() {
            if let Some(left_list) = left
                .get_item(key)?
                .and_then(|value| value.cast_into::<PyList>().ok())
            {
                return Ok(copy_list(&left_list, Some(right_list), depth)?.into_any());
            }
        }
    }

    copy_value(right, depth)
}

pub(crate) fn merge_many<'py>(
    dicts: &[Bound<'py, PyDict>],
    concat_lists: bool,
    depth: usize,
) -> PyResult<Bound<'py, PyDict>> {
    let py = dicts[0].py();
    let _guard = RecursionGuard::enter(py, depth)?;
    let result = PyDict::new(py);

    for (first_idx, source) in dicts.iter().enumerate() {
        for (key, first_value) in source.iter() {
            if first_idx > 0 && result.contains(&key)? {
                continue;
            }
            let merged = merge_many_entry(
                dicts,
                first_idx,
                &key,
                &first_value,
                concat_lists,
                depth + 1,
            )?;
            result.set_item(&key, merged)?;
        }
    }

    Ok(result)
}

fn merge_many_entry<'py>(
    dicts: &[Bound<'py, PyDict>],
    first_idx: usize,
    key: &Bound<'py, PyAny>,
    first_value: &Bound<'py, PyAny>,
    concat_lists: bool,
    depth: usize,
) -> PyResult<Bound<'py, PyAny>> {
    let mut last_idx = first_idx;
    let mut last_value = first_value.clone();
    for idx in (first_idx + 1..dicts.len()).rev() {
        if let Some(value) = dicts[idx].get_item(key)? {
            last_idx = idx;
            last_value = value;
            break;
        }
    }

    if let Ok(last_dict) = last_value.cast::<PyDict>() {
        if last_idx == first_idx {
            return Ok(copy_dict(last_dict, depth)?.into_any());
        }
        let mut dict_suffix = vec![last_dict.clone()];
        for idx in (first_idx..last_idx).rev() {
            let value = if idx == first_idx {
                Some(first_value.clone())
            } else {
                dicts[idx].get_item(key)?
            };
            if let Some(val) = value {
                if let Ok(dict) = val.cast_into::<PyDict>() {
                    dict_suffix.push(dict);
                } else {
                    break;
                }
            }
        }
        dict_suffix.reverse();
        return match dict_suffix.len() {
            1 => Ok(copy_dict(&dict_suffix[0], depth)?.into_any()),
            2 => Ok(merge_dicts(&dict_suffix[0], &dict_suffix[1], concat_lists, depth)?.into_any()),
            _ => Ok(merge_many(&dict_suffix, concat_lists, depth)?.into_any()),
        };
    }

    if concat_lists {
        if let Ok(last_list) = last_value.cast::<PyList>() {
            if last_idx == first_idx {
                return Ok(copy_list(last_list, None, depth)?.into_any());
            }
            let mut list_suffix = vec![last_list.clone()];
            for idx in (first_idx..last_idx).rev() {
                let value = if idx == first_idx {
                    Some(first_value.clone())
                } else {
                    dicts[idx].get_item(key)?
                };
                if let Some(val) = value {
                    if let Ok(list) = val.cast_into::<PyList>() {
                        list_suffix.push(list);
                    } else {
                        break;
                    }
                }
            }
            list_suffix.reverse();
            return match list_suffix.len() {
                1 => Ok(copy_list(&list_suffix[0], None, depth)?.into_any()),
                2 => Ok(copy_list(&list_suffix[0], Some(&list_suffix[1]), depth)?.into_any()),
                _ => Ok(copy_lists(&list_suffix, depth)?.into_any()),
            };
        }
    }

    copy_value(&last_value, depth)
}

fn is_container(value: &Bound<'_, PyAny>) -> bool {
    value.is_instance_of::<PyDict>() || value.is_instance_of::<PyList>()
}

pub(crate) fn copy_dict<'py>(
    dict: &Bound<'py, PyDict>,
    depth: usize,
) -> PyResult<Bound<'py, PyDict>> {
    let py = dict.py();
    let _guard = RecursionGuard::enter(py, depth)?;
    let result = dict.copy()?;
    let mut position = 0;
    let mut key_ptr = std::ptr::null_mut();
    let mut child_ptr = std::ptr::null_mut();
    loop {
        // SAFETY: `dict` remains alive and unmodified during the scan, and
        // the GIL is held for the full call.
        if unsafe {
            pyo3::ffi::PyDict_Next(dict.as_ptr(), &mut position, &mut key_ptr, &mut child_ptr)
        } == 0
        {
            break;
        }
        // SAFETY: PyDict_Next returned a live value pointer while `dict`
        // is alive and the GIL remains held.
        let is_container = unsafe {
            pyo3::ffi::PyDict_Check(child_ptr) != 0 || pyo3::ffi::PyList_Check(child_ptr) != 0
        };
        if is_container {
            // SAFETY: both pointers are borrowed from the live `dict`;
            // the constructors increment their references for these Bounds.
            let key = unsafe { Bound::from_borrowed_ptr(py, key_ptr) };
            let child = unsafe { Bound::from_borrowed_ptr(py, child_ptr) };
            result.set_item(&key, copy_value(&child, depth + 1)?)?;
        }
    }
    Ok(result)
}

fn copy_value<'py>(value: &Bound<'py, PyAny>, depth: usize) -> PyResult<Bound<'py, PyAny>> {
    if let Ok(dict) = value.cast::<PyDict>() {
        Ok(copy_dict(dict, depth)?.into_any())
    } else if let Ok(list) = value.cast::<PyList>() {
        Ok(copy_list(list, None, depth)?.into_any())
    } else {
        Ok(value.clone())
    }
}

fn copy_lists<'py>(lists: &[Bound<'py, PyList>], depth: usize) -> PyResult<Bound<'py, PyList>> {
    let py = lists[0].py();
    let _guard = RecursionGuard::enter(py, depth)?;

    let mut total_len: pyo3::ffi::Py_ssize_t = 0;
    for list in lists {
        // SAFETY: `list` is a live Python list and the GIL is held.
        let len = unsafe { pyo3::ffi::PyList_GET_SIZE(list.as_ptr()) };
        total_len = total_len.checked_add(len).ok_or_else(|| {
            pyo3::exceptions::PyOverflowError::new_err("combined list is too large")
        })?;
    }

    // SAFETY: `total_len >= 0` and the GIL is held.
    let result_ptr = unsafe { pyo3::ffi::PyList_New(total_len) };
    if result_ptr.is_null() {
        return Err(PyErr::fetch(py));
    }
    // SAFETY: `result_ptr` is a newly allocated non-null PyList owned by us.
    let result = unsafe { Bound::from_owned_ptr(py, result_ptr).cast_into_unchecked::<PyList>() };

    let mut out_index: pyo3::ffi::Py_ssize_t = 0;
    for list in lists {
        // SAFETY: `list` is a live Python list and the GIL is held.
        let len = unsafe { pyo3::ffi::PyList_GET_SIZE(list.as_ptr()) };
        for index in 0..len {
            // SAFETY: `index` is in bounds and `list` remains alive under the GIL.
            let child_ptr = unsafe { pyo3::ffi::PyList_GET_ITEM(list.as_ptr(), index) };
            // SAFETY: `child_ptr` is a live borrowed object pointer.
            let is_container = unsafe {
                pyo3::ffi::PyDict_Check(child_ptr) != 0 || pyo3::ffi::PyList_Check(child_ptr) != 0
            };
            let item_ptr = if is_container {
                // SAFETY: `child_ptr` is borrowed from the live list; constructor increments refcount.
                let child = unsafe { Bound::from_borrowed_ptr(py, child_ptr) };
                copy_value(&child, depth + 1)?.into_ptr()
            } else {
                // SAFETY: `child_ptr` is live and `PyList_SET_ITEM` steals a reference.
                unsafe { pyo3::ffi::Py_INCREF(child_ptr) };
                child_ptr
            };
            // SAFETY: `out_index < total_len` and `result` is a freshly allocated PyList.
            unsafe { pyo3::ffi::PyList_SET_ITEM(result.as_ptr(), out_index, item_ptr) };
            out_index += 1;
        }
    }

    Ok(result)
}

fn copy_list<'py>(
    list: &Bound<'py, PyList>,
    append: Option<&Bound<'py, PyList>>,
    depth: usize,
) -> PyResult<Bound<'py, PyList>> {
    let _guard = RecursionGuard::enter(list.py(), depth)?;
    let result = match append {
        Some(right) => {
            // Normalize subclasses so concatenation bypasses __add__ overrides.
            let plain_list = match list.cast_exact::<PyList>() {
                Ok(_) => list.clone(),
                Err(_) => list.get_slice(0, list.len()),
            };
            plain_list
                .as_sequence()
                .concat(right.as_sequence())?
                .cast_into::<PyList>()?
        }
        None => list.get_slice(0, list.len()),
    };

    // SAFETY: `result` is a live Python list and the GIL is held.
    let len = unsafe { pyo3::ffi::PyList_GET_SIZE(result.as_ptr()) };
    let mut index = 0;
    loop {
        if index >= len {
            break;
        }

        // SAFETY: the index is in range and `result` remains alive under the GIL.
        let child_ptr = unsafe { pyo3::ffi::PyList_GET_ITEM(result.as_ptr(), index) };
        // SAFETY: PyList_GET_ITEM returns a live borrowed item for this list.
        let is_container = unsafe {
            pyo3::ffi::PyDict_Check(child_ptr) != 0 || pyo3::ffi::PyList_Check(child_ptr) != 0
        };
        if is_container {
            // SAFETY: the pointer is borrowed from the live list; the constructor
            // increments its reference for this Bound.
            let child = unsafe { Bound::from_borrowed_ptr(list.py(), child_ptr) };
            result.set_item(index as usize, copy_value(&child, depth + 1)?)?;
        }
        index += 1;
    }
    Ok(result)
}
