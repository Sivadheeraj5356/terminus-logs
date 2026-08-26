use std::fs;
use std::io::Write;

use crate::types::ReplayResult;

const OUTPUT: &str = "/app/output/registry.json";

pub fn write_output(rep: &ReplayResult) -> Result<(), i32> {
    let _ = fs::remove_dir_all("/app/output");
    fs::create_dir_all("/app/output").map_err(|_| 1)?;
    let mut buf = String::new();
    buf.push_str("{\n");
    write_duplicate_array(&mut buf, &rep.duplicates);
    buf.push_str(",\n");
    write_usize_array(&mut buf, "invalid_lines", &rep.invalid);
    buf.push_str(",\n");
    write_rejected_array(&mut buf, &rep.rejected);
    buf.push_str(",\n");
    write_trays_array(&mut buf, rep);
    buf.push_str(",\n");
    write_summary(&mut buf, rep);
    buf.push_str("\n}\n");
    let mut f = fs::File::create(OUTPUT).map_err(|_| 1)?;
    f.write_all(buf.as_bytes()).map_err(|_| 1)?;
    Ok(())
}

fn write_duplicate_array(buf: &mut String, rows: &[(usize, String, String)]) {
    if rows.is_empty() {
        buf.push_str("  \"duplicate_events\": []");
        return;
    }
    buf.push_str("  \"duplicate_events\": [\n");
    for (i, (ord, eid, reason)) in rows.iter().enumerate() {
        if i > 0 {
            buf.push_str(",\n");
        }
        buf.push_str("    {\n");
        write_kv(buf, 6, "event_id", &json_quote(eid));
        buf.push_str(",\n");
        write_kv_num(buf, 6, "ordinal", *ord as i64);
        buf.push_str(",\n");
        write_kv(buf, 6, "reason", &json_quote(reason));
        buf.push_str("\n    }");
    }
    buf.push_str("\n  ]");
}

fn write_usize_array(buf: &mut String, key: &str, values: &[usize]) {
    if values.is_empty() {
        buf.push_str(&format!("  \"{key}\": []"));
        return;
    }
    buf.push_str(&format!("  \"{key}\": [\n"));
    for (i, val) in values.iter().enumerate() {
        if i > 0 {
            buf.push_str(",\n");
        }
        buf.push_str(&format!("    {val}"));
    }
    buf.push_str("\n  ]");
}

fn write_rejected_array(buf: &mut String, rows: &[(usize, String, String, String, usize)]) {
    if rows.is_empty() {
        buf.push_str("  \"rejected_events\": []");
        return;
    }
    buf.push_str("  \"rejected_events\": [\n");
    for (i, (ord, eid, reason, source, line)) in rows.iter().enumerate() {
        if i > 0 {
            buf.push_str(",\n");
        }
        buf.push_str("    {\n");
        write_kv(buf, 6, "event_id", &json_quote(eid));
        buf.push_str(",\n");
        write_kv_num(buf, 6, "line", *line as i64);
        buf.push_str(",\n");
        write_kv_num(buf, 6, "ordinal", *ord as i64);
        buf.push_str(",\n");
        write_kv(buf, 6, "reason", &json_quote(reason));
        buf.push_str(",\n");
        write_kv(buf, 6, "source", &json_quote(source));
        buf.push_str("\n    }");
    }
    buf.push_str("\n  ]");
}

fn write_trays_array(buf: &mut String, rep: &ReplayResult) {
    if rep.trays.is_empty() {
        buf.push_str("  \"trays\": []");
        return;
    }
    buf.push_str("  \"trays\": [\n");
    for (i, (name, st)) in rep.trays.iter().enumerate() {
        if i > 0 {
            buf.push_str(",\n");
        }
        buf.push_str("    {\n");
        write_kv_num(buf, 6, "capacity_units", st.capacity_units);
        buf.push_str(",\n");
        write_kv_num(buf, 6, "cycles_since_regen", st.cycles_since_regen);
        buf.push_str(",\n");
        write_kv(buf, 6, "held", bool_json(st.held));
        buf.push_str(",\n");
        write_kv(buf, 6, "locked", bool_json(st.locked));
        buf.push_str(",\n");
        write_kv_num(buf, 6, "regen_every", st.regen_every);
        buf.push_str(",\n");
        write_kv(buf, 6, "sealed", bool_json(st.sealed));
        buf.push_str(",\n");
        write_kv_num(buf, 6, "tier", st.tier);
        buf.push_str(",\n");
        write_kv(buf, 6, "tray_id", &json_quote(name));
        buf.push_str(",\n");
        write_kv_num(buf, 6, "units", st.units);
        buf.push_str("\n    }");
    }
    buf.push_str("\n  ]");
}

fn write_summary(buf: &mut String, rep: &ReplayResult) {
    buf.push_str("  \"summary\": {\n");
    write_kv_num(buf, 4, "applied_events", rep.applied as i64);
    buf.push_str(",\n");
    write_kv_num(buf, 4, "duplicate_events", rep.duplicates.len() as i64);
    buf.push_str(",\n");
    write_kv_num(buf, 4, "invalid_lines", rep.invalid.len() as i64);
    buf.push_str(",\n");
    write_kv_num(buf, 4, "loads_applied", rep.loads_applied);
    buf.push_str(",\n");
    write_kv_num(buf, 4, "rejected_events", rep.rejected.len() as i64);
    buf.push_str(",\n");
    write_kv_num(buf, 4, "total_lines", rep.total_lines as i64);
    buf.push_str(",\n");
    write_kv_num(buf, 4, "unloads_applied", rep.unloads_applied);
    buf.push_str("\n  }");
}

fn write_kv(buf: &mut String, indent: usize, key: &str, value: &str) {
    buf.push_str(&format!("{:indent$}\"{key}\": {value}", "", indent = indent));
}

fn write_kv_num(buf: &mut String, indent: usize, key: &str, value: i64) {
    buf.push_str(&format!("{:indent$}\"{key}\": {value}", "", indent = indent));
}

fn bool_json(v: bool) -> &'static str {
    if v { "true" } else { "false" }
}

fn json_quote(s: &str) -> String {
    let mut out = String::from("\"");
    for ch in s.chars() {
        match ch {
            '\\' => out.push_str("\\\\"),
            '"' => out.push_str("\\\""),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c.is_control() => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}
