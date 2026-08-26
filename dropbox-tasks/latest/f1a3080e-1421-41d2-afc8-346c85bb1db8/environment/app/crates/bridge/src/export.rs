//! C ABI surface. Strings returned by these functions are heap-allocated and
//! must be released with `vellum_free`.

use std::ffi::{c_char, CStr, CString};

fn to_c_string(s: String) -> *mut c_char {
    match CString::new(s) {
        Ok(cs) => cs.into_raw(),
        Err(_) => std::ptr::null_mut(),
    }
}

unsafe fn borrow(input: *const c_char) -> Option<String> {
    if input.is_null() {
        return None;
    }
    CStr::from_ptr(input).to_str().ok().map(|s| s.to_string())
}

/// Return the identity record as a JSON string.
#[no_mangle]
pub extern "C" fn vellum_identity_json() -> *mut c_char {
    to_c_string(crate::identity_json())
}

/// Digest a JSON document. Returns null on parse failure.
#[no_mangle]
pub extern "C" fn vellum_canonical_digest(input: *const c_char) -> *mut c_char {
    let text = match unsafe { borrow(input) } {
        Some(t) => t,
        None => return std::ptr::null_mut(),
    };
    match crate::canonical_digest_str(&text) {
        Ok(hex) => to_c_string(hex),
        Err(_) => std::ptr::null_mut(),
    }
}

/// Digest the detached content member. Present only when the detached
/// capability is compiled in; returns null when unavailable or absent.
#[cfg(feature = "detached")]
#[no_mangle]
pub extern "C" fn vellum_detached_digest(input: *const c_char) -> *mut c_char {
    let text = match unsafe { borrow(input) } {
        Some(t) => t,
        None => return std::ptr::null_mut(),
    };
    match crate::detached_digest_str(&text) {
        Ok(Some(hex)) => to_c_string(hex),
        _ => std::ptr::null_mut(),
    }
}

/// Free a string previously returned by this library.
#[no_mangle]
pub extern "C" fn vellum_free(ptr: *mut c_char) {
    if !ptr.is_null() {
        unsafe {
            drop(CString::from_raw(ptr));
        }
    }
}
