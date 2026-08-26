//! The frozen DNS-like zone: domain -> record set. Frozen evidence.

use crate::json::Json;
use std::collections::HashMap;

pub struct Rec {
    pub sap: Option<String>,
    pub a: Vec<String>,
    pub mx: Vec<String>,
}

pub struct Zone {
    map: HashMap<String, Rec>,
}

impl Zone {
    pub fn from_json(j: &Json) -> Zone {
        let mut map = HashMap::new();
        if let Some(obj) = j.obj() {
            for (dom, rec) in obj {
                let sap = rec.get("sap").map(|v| v.s().to_string());
                let a = rec
                    .get("a")
                    .map(|v| v.arr().iter().map(|x| x.s().to_string()).collect())
                    .unwrap_or_default();
                let mx = rec
                    .get("mx")
                    .map(|v| v.arr().iter().map(|x| x.s().to_string()).collect())
                    .unwrap_or_default();
                map.insert(dom.clone(), Rec { sap, a, mx });
            }
        }
        Zone { map }
    }

    pub fn get(&self, domain: &str) -> Option<&Rec> {
        self.map.get(domain)
    }
}
