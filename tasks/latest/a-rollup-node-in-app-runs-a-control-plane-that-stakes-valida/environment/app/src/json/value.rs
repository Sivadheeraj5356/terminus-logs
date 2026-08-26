#[derive(Clone, Debug, PartialEq)]
pub enum Json {
    Null,
    Bool(bool),
    Num(f64),
    Str(String),
    Arr(Vec<Json>),
    Obj(Vec<(String, Json)>),
}

impl Json {
    pub fn obj() -> Json {
        Json::Obj(Vec::new())
    }

    pub fn set(&mut self, key: &str, value: Json) {
        if let Json::Obj(entries) = self {
            for entry in entries.iter_mut() {
                if entry.0 == key {
                    entry.1 = value;
                    return;
                }
            }
            entries.push((key.to_string(), value));
        }
    }

    pub fn get(&self, key: &str) -> Option<&Json> {
        if let Json::Obj(entries) = self {
            for entry in entries {
                if entry.0 == key {
                    return Some(&entry.1);
                }
            }
        }
        None
    }

    pub fn as_str(&self) -> Option<&str> {
        match self {
            Json::Str(s) => Some(s.as_str()),
            _ => None,
        }
    }

    pub fn as_array(&self) -> Option<&Vec<Json>> {
        match self {
            Json::Arr(items) => Some(items),
            _ => None,
        }
    }

    pub fn string_field(&self, key: &str) -> Option<String> {
        self.get(key).and_then(|v| v.as_str()).map(|s| s.to_string())
    }

    pub fn from_pairs(pairs: Vec<(&str, Json)>) -> Json {
        let mut out = Json::obj();
        for (k, v) in pairs {
            out.set(k, v);
        }
        out
    }
}

pub fn s(value: &str) -> Json {
    Json::Str(value.to_string())
}

pub fn n(value: i64) -> Json {
    Json::Num(value as f64)
}

pub fn b(value: bool) -> Json {
    Json::Bool(value)
}
