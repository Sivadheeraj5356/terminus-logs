//! Specifier expansion in admissible directives.
use crate::boot_semantics::Semantics;
use crate::unit_name_codec;
use crate::unit_parser::ParsedUnit;
use crate::yard_inventory::Yard;

pub fn expand_unit(parsed: &mut ParsedUnit, unit: &str, yard: &Yard, sem: &Semantics) {
    let (prefix, instance, _ty) = unit_name_codec::split_instance(unit);
    let inst = instance.clone().unwrap_or_default();
    let inst_unesc = unit_name_codec::unescape_instance(&inst).unwrap_or_else(|_| inst.clone());
    let hostname = yard.facts.get("hostname").cloned().unwrap_or_default();
    let machine = yard.machine_id.clone();
    let boot = yard.facts.get("boot_id").cloned().unwrap_or_default();
    let sections: Vec<String> = parsed.sections.keys().cloned().collect();
    for sec in sections {
        let keys: Vec<String> = parsed.sections.get(&sec).map(|m| m.keys().cloned().collect()).unwrap_or_default();
        for k in keys {
            let scope = sem.decide_or("SPECIFIER_SCOPE", &["field", &k], "expand");
            if scope != "expand" { continue; }
            if let Some(vals) = parsed.sections.get_mut(&sec).and_then(|m| m.get_mut(&k)) {
                for v in vals.iter_mut() {
                    *v = expand_str(v, unit, &prefix, &inst, &inst_unesc, &hostname, &machine, &boot, sem);
                }
            }
        }
    }
}

fn expand_str(s: &str, unit: &str, prefix: &str, inst_esc: &str, inst_un: &str, host: &str, mid: &str, boot: &str, sem: &Semantics) -> String {
    let mut out = String::new();
    let chars: Vec<char> = s.chars().collect();
    let mut i = 0;
    while i < chars.len() {
        if chars[i] == '%' && i + 1 < chars.len() {
            let n = chars[i+1];
            let repl = match n {
                '%' => "%".into(),
                'n' => unit.to_string(),
                'N' => unit.to_string(),
                'p' => prefix.to_string(),
                'P' => prefix.to_string(),
                'i' => {
                    let form = sem.decide_or("SPECIFIER_INSTANCE", &["form", "escaped"], "%I");
                    if form == "%i" { inst_esc.to_string() } else { inst_un.to_string() }
                }
                'I' => {
                    let form = sem.decide_or("SPECIFIER_INSTANCE", &["form", "unescaped"], "%i");
                    if form == "%I" { inst_un.to_string() } else { inst_esc.to_string() }
                }
                'j' => prefix.rsplit('-').next().unwrap_or(prefix).to_string(),
                'J' => prefix.rsplit('-').next().unwrap_or(prefix).to_string(),
                'f' => unit_name_codec::path_from_unescaped_instance(inst_un),
                'H' => host.to_string(),
                'm' => mid.to_string(),
                'b' => boot.to_string(),
                other => format!("%{}", other),
            };
            out.push_str(&repl);
            i += 2;
        } else {
            out.push(chars[i]);
            i += 1;
        }
    }
    out
}
