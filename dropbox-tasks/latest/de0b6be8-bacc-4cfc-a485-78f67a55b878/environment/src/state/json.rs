use std::collections::BTreeMap;

#[derive(Clone, Debug, PartialEq)]
pub enum J {
    Null,
    Bool(bool),
    Num(i64),
    Str(String),
    Arr(Vec<J>),
    Obj(BTreeMap<String, J>),
}

pub fn parse(s: &str) -> Result<J, String> {
    let mut p = P {
        b: s.as_bytes(),
        i: 0,
    };
    let v = p.val()?;
    p.ws();
    if p.i != p.b.len() {
        return Err("trailing json".into());
    }
    Ok(v)
}
struct P<'a> {
    b: &'a [u8],
    i: usize,
}
impl<'a> P<'a> {
    fn ws(&mut self) {
        while self.i < self.b.len() && self.b[self.i].is_ascii_whitespace() {
            self.i += 1
        }
    }
    fn val(&mut self) -> Result<J, String> {
        self.ws();
        if self.i >= self.b.len() {
            return Err("eof".into());
        }
        match self.b[self.i] {
            b'"' => Ok(J::Str(self.string()?)),
            b'{' => self.obj(),
            b'[' => self.arr(),
            b't' => {
                self.lit(b"true")?;
                Ok(J::Bool(true))
            }
            b'f' => {
                self.lit(b"false")?;
                Ok(J::Bool(false))
            }
            b'n' => {
                self.lit(b"null")?;
                Ok(J::Null)
            }
            b'-' | b'0'..=b'9' => self.num(),
            _ => Err("bad json".into()),
        }
    }
    fn lit(&mut self, x: &[u8]) -> Result<(), String> {
        if self.b.get(self.i..self.i + x.len()) == Some(x) {
            self.i += x.len();
            Ok(())
        } else {
            Err("literal".into())
        }
    }
    fn string(&mut self) -> Result<String, String> {
        self.i += 1;
        let mut o = String::new();
        while self.i < self.b.len() {
            let c = self.b[self.i];
            self.i += 1;
            match c {
                b'"' => return Ok(o),
                b'\\' => {
                    if self.i >= self.b.len() {
                        return Err("escape".into());
                    }
                    let e = self.b[self.i];
                    self.i += 1;
                    match e {
                        b'"' => o.push('"'),
                        b'\\' => o.push('\\'),
                        b'/' => o.push('/'),
                        b'b' => o.push('\u{8}'),
                        b'f' => o.push('\u{c}'),
                        b'n' => o.push('\n'),
                        b'r' => o.push('\r'),
                        b't' => o.push('\t'),
                        b'u' => {
                            if self.i + 4 > self.b.len() {
                                return Err("unicode".into());
                            }
                            let h = std::str::from_utf8(&self.b[self.i..self.i + 4])
                                .map_err(|_| "unicode")?;
                            let n = u32::from_str_radix(h, 16).map_err(|_| "unicode")?;
                            o.push(char::from_u32(n).ok_or("unicode")?);
                            self.i += 4
                        }
                        _ => return Err("escape".into()),
                    }
                }
                0..=31 => return Err("control".into()),
                _ => {
                    let st = self.i - 1;
                    while self.i < self.b.len() && (self.b[self.i] & 0xc0) == 0x80 {
                        self.i += 1
                    }
                    o.push_str(std::str::from_utf8(&self.b[st..self.i]).map_err(|_| "utf8")?)
                }
            }
        }
        Err("string".into())
    }
    fn num(&mut self) -> Result<J, String> {
        let st = self.i;
        if self.b[self.i] == b'-' {
            self.i += 1
        }
        while self.i < self.b.len() && self.b[self.i].is_ascii_digit() {
            self.i += 1
        }
        let x = std::str::from_utf8(&self.b[st..self.i])
            .unwrap()
            .parse()
            .map_err(|_| "number")?;
        Ok(J::Num(x))
    }
    fn arr(&mut self) -> Result<J, String> {
        self.i += 1;
        let mut a = vec![];
        loop {
            self.ws();
            if self.b.get(self.i) == Some(&b']') {
                self.i += 1;
                return Ok(J::Arr(a));
            }
            a.push(self.val()?);
            self.ws();
            match self.b.get(self.i) {
                Some(b',') => self.i += 1,
                Some(b']') => {
                    self.i += 1;
                    return Ok(J::Arr(a));
                }
                _ => return Err("array".into()),
            }
        }
    }
    fn obj(&mut self) -> Result<J, String> {
        self.i += 1;
        let mut o = BTreeMap::new();
        loop {
            self.ws();
            if self.b.get(self.i) == Some(&b'}') {
                self.i += 1;
                return Ok(J::Obj(o));
            }
            if self.b.get(self.i) != Some(&b'"') {
                return Err("object key".into());
            }
            let k = self.string()?;
            self.ws();
            if self.b.get(self.i) != Some(&b':') {
                return Err("colon".into());
            }
            self.i += 1;
            o.insert(k, self.val()?);
            self.ws();
            match self.b.get(self.i) {
                Some(b',') => self.i += 1,
                Some(b'}') => {
                    self.i += 1;
                    return Ok(J::Obj(o));
                }
                _ => return Err("object".into()),
            }
        }
    }
}
pub fn canonical(v: &J) -> String {
    match v {
        J::Null => "null".into(),
        J::Bool(b) => b.to_string(),
        J::Num(n) => n.to_string(),
        J::Str(s) => quote(s),
        J::Arr(a) => format!(
            "[{}]",
            a.iter().map(canonical).collect::<Vec<_>>().join(",")
        ),
        J::Obj(o) => format!(
            "{{{}}}",
            o.iter()
                .map(|(k, v)| format!("{}:{}", quote(k), canonical(v)))
                .collect::<Vec<_>>()
                .join(",")
        ),
    }
}
fn quote(s: &str) -> String {
    let mut o = String::from("\"");
    for c in s.chars() {
        match c {
            '"' => o.push_str("\\\""),
            '\\' => o.push_str("\\\\"),
            '\n' => o.push_str("\\n"),
            '\r' => o.push_str("\\r"),
            '\t' => o.push_str("\\t"),
            c if c < ' ' => o.push_str(&format!("\\u{:04x}", c as u32)),
            c => o.push(c),
        }
    }
    o.push('"');
    o
}
pub fn obj(v: J) -> Result<BTreeMap<String, J>, String> {
    if let J::Obj(x) = v {
        Ok(x)
    } else {
        Err("expected object".into())
    }
}
pub fn strv(o: &BTreeMap<String, J>, k: &str) -> Result<String, String> {
    match o.get(k) {
        Some(J::Str(x)) => Ok(x.clone()),
        _ => Err(format!("missing {k}")),
    }
}
pub fn numv(o: &BTreeMap<String, J>, k: &str) -> Result<i64, String> {
    match o.get(k) {
        Some(J::Num(x)) => Ok(*x),
        _ => Err(format!("missing {k}")),
    }
}
