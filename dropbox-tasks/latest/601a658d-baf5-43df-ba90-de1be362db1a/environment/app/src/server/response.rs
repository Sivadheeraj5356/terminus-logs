use crate::json::{ser, Json};

pub struct Response {
    pub status: u16,
    pub headers: Vec<(String, String)>,
    pub body: Vec<u8>,
}

impl Response {
    pub fn new(status: u16) -> Response {
        Response {
            status,
            headers: Vec::new(),
            body: Vec::new(),
        }
    }

    pub fn json(status: u16, value: Json) -> Response {
        let body = ser::to_string(&value).into_bytes();
        let mut resp = Response::new(status);
        resp.headers
            .push(("content-type".to_string(), "application/json".to_string()));
        resp.body = body;
        resp
    }

    pub fn text(status: u16, body: &str) -> Response {
        let mut resp = Response::new(status);
        resp.headers
            .push(("content-type".to_string(), "text/plain".to_string()));
        resp.body = body.as_bytes().to_vec();
        resp
    }

    pub fn encode(&self) -> Vec<u8> {
        let reason = reason_phrase(self.status);
        let mut head = format!("HTTP/1.1 {} {}\r\n", self.status, reason);
        let mut has_len = false;
        let mut has_type = false;
        for (k, v) in &self.headers {
            let lk = k.to_ascii_lowercase();
            if lk == "content-length" {
                has_len = true;
            }
            if lk == "content-type" {
                has_type = true;
            }
            head.push_str(&format!("{}: {}\r\n", k, v));
        }
        if !has_type {
            head.push_str("content-type: application/json\r\n");
        }
        if !has_len {
            head.push_str(&format!("content-length: {}\r\n", self.body.len()));
        }
        head.push_str("connection: close\r\n");
        head.push_str("\r\n");
        let mut out = head.into_bytes();
        out.extend_from_slice(&self.body);
        out
    }
}

fn reason_phrase(status: u16) -> &'static str {
    match status {
        200 => "OK",
        201 => "Created",
        202 => "Accepted",
        204 => "No Content",
        400 => "Bad Request",
        401 => "Unauthorized",
        403 => "Forbidden",
        404 => "Not Found",
        405 => "Method Not Allowed",
        409 => "Conflict",
        413 => "Payload Too Large",
        422 => "Unprocessable Entity",
        429 => "Too Many Requests",
        500 => "Internal Server Error",
        503 => "Service Unavailable",
        _ => "Status",
    }
}
