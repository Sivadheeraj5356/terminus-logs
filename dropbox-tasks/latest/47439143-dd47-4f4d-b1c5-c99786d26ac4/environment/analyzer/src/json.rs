//! Minimal JSON reader for the fixed case/zone schema (objects, arrays,
//! strings, booleans, null). Frozen evidence.

use std::collections::HashMap;

#[derive(Debug, Clone)]
pub enum Json {
    Str(String),
    Arr(Vec<Json>),
    Obj(HashMap<String, Json>),
    Bool(bool),
    Null,
}

impl Json {
    pub fn s(&self) -> &str {
        match self {
            Json::Str(x) => x,
            _ => "",
        }
    }
    pub fn get(&self, k: &str) -> Option<&Json> {
        match self {
            Json::Obj(m) => m.get(k),
            _ => None,
        }
    }
    pub fn arr(&self) -> &[Json] {
        match self {
            Json::Arr(a) => a,
            _ => &[],
        }
    }
    pub fn obj(&self) -> Option<&HashMap<String, Json>> {
        match self {
            Json::Obj(m) => Some(m),
            _ => None,
        }
    }
}

pub struct P<'a> {
    b: &'a [u8],
    i: usize,
}

impl<'a> P<'a> {
    pub fn new(b: &'a [u8]) -> Self {
        P { b, i: 0 }
    }
    fn ws(&mut self) {
        while self.i < self.b.len() && (self.b[self.i] as char).is_whitespace() {
            self.i += 1;
        }
    }
    pub fn value(&mut self) -> Json {
        self.ws();
        match self.b[self.i] {
            b'"' => Json::Str(self.string()),
            b'[' => self.array(),
            b'{' => self.object(),
            b't' => {
                self.i += 4;
                Json::Bool(true)
            }
            b'f' => {
                self.i += 5;
                Json::Bool(false)
            }
            _ => {
                self.i += 4;
                Json::Null
            }
        }
    }
    fn string(&mut self) -> String {
        self.i += 1;
        let mut s = String::new();
        while self.b[self.i] != b'"' {
            let c = self.b[self.i];
            if c == b'\\' {
                self.i += 1;
                let e = self.b[self.i];
                match e {
                    b'n' => s.push('\n'),
                    b't' => s.push('\t'),
                    b'r' => s.push('\r'),
                    b'u' => {
                        let hex = std::str::from_utf8(&self.b[self.i + 1..self.i + 5]).unwrap();
                        let cp = u32::from_str_radix(hex, 16).unwrap();
                        s.push(char::from_u32(cp).unwrap_or('\u{fffd}'));
                        self.i += 4;
                    }
                    other => s.push(other as char),
                }
                self.i += 1;
            } else {
                let len = utf8_len(c);
                s.push_str(std::str::from_utf8(&self.b[self.i..self.i + len]).unwrap());
                self.i += len;
            }
        }
        self.i += 1;
        s
    }
    fn array(&mut self) -> Json {
        self.i += 1;
        let mut v = Vec::new();
        self.ws();
        if self.b[self.i] == b']' {
            self.i += 1;
            return Json::Arr(v);
        }
        loop {
            v.push(self.value());
            self.ws();
            let c = self.b[self.i];
            self.i += 1;
            if c == b']' {
                break;
            }
        }
        Json::Arr(v)
    }
    fn object(&mut self) -> Json {
        self.i += 1;
        let mut m = HashMap::new();
        self.ws();
        if self.b[self.i] == b'}' {
            self.i += 1;
            return Json::Obj(m);
        }
        loop {
            self.ws();
            let k = self.string();
            self.ws();
            self.i += 1; // ':'
            let v = self.value();
            m.insert(k, v);
            self.ws();
            let c = self.b[self.i];
            self.i += 1;
            if c == b'}' {
                break;
            }
        }
        Json::Obj(m)
    }
}

fn utf8_len(b: u8) -> usize {
    if b < 0x80 {
        1
    } else if b >> 5 == 0b110 {
        2
    } else if b >> 4 == 0b1110 {
        3
    } else {
        4
    }
}
