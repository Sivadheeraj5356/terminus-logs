//! Unit-name escaping and mount path codec.
pub fn escape_path(path: &str) -> Result<String, String> {
    if path == "/" {
        return Ok("-".into());
    }
    if !path.starts_with('/') {
        return Err("absolute required".into());
    }
    let mut out = String::new();
    let bytes = path.as_bytes();
    let mut i = 1; // skip leading /
    while i < bytes.len() {
        let b = bytes[i];
        if b == b'/' {
            out.push('-');
        } else if (b as char).is_ascii_alphanumeric() || matches!(b, b':' | b'_' | b'.' | b'\\') {
            out.push(b as char);
        } else if b == b'-' {
            out.push('\\');
            out.push('x');
            out.push_str(&format!("{:02x}", b));
        } else {
            out.push('\\');
            out.push('x');
            out.push_str(&format!("{:02x}", b));
        }
        i += 1;
    }
    Ok(out)
}

pub fn unescape_instance(escaped: &str) -> Result<String, String> {
    let mut out = String::new();
    let mut chars = escaped.chars().peekable();
    while let Some(c) = chars.next() {
        if c == '\\' {
            if chars.next() != Some('x') {
                return Err("bad escape".into());
            }
            let h1 = chars.next().ok_or("bad escape")?;
            let h2 = chars.next().ok_or("bad escape")?;
            let byte = u8::from_str_radix(&format!("{}{}", h1, h2), 16).map_err(|_| "bad hex")?;
            out.push(byte as char);
        } else {
            out.push(c);
        }
    }
    Ok(out)
}

pub fn unit_type(name: &str) -> Option<&str> {
    name.rsplit_once('.').map(|(_, t)| t)
}

pub fn split_instance(name: &str) -> (String, Option<String>, String) {
    // returns (prefix, instance, type)
    let (stem, ty) = name.rsplit_once('.').unwrap_or((name, ""));
    if let Some((p, i)) = stem.split_once('@') {
        (p.to_string(), Some(i.to_string()), ty.to_string())
    } else {
        (stem.to_string(), None, ty.to_string())
    }
}

pub fn path_from_unescaped_instance(inst: &str) -> String {
    if inst.is_empty() || inst == "-" {
        return "/".into();
    }
    format!("/{}", inst.replace('-', "/"))
}
