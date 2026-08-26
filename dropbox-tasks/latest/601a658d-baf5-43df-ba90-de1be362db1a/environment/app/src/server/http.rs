use super::request::{split_target, Request};
use std::io::{BufRead, BufReader, Read};
use std::net::TcpStream;

pub fn read_request(stream: &mut TcpStream) -> Result<Request, String> {
    let peer = stream
        .peer_addr()
        .map(|a| a.ip().to_string())
        .unwrap_or_else(|_| "unknown".to_string());
    let mut reader = BufReader::new(stream);

    let mut request_line = String::new();
    reader
        .read_line(&mut request_line)
        .map_err(|e| e.to_string())?;
    let request_line = request_line.trim_end();
    let mut parts = request_line.split_whitespace();
    let method = parts.next().ok_or("missing method")?.to_string();
    let target = parts.next().ok_or("missing target")?.to_string();

    let mut headers: Vec<(String, String)> = Vec::new();
    let mut content_length = 0usize;
    loop {
        let mut line = String::new();
        let read = reader.read_line(&mut line).map_err(|e| e.to_string())?;
        if read == 0 {
            break;
        }
        let line = line.trim_end();
        if line.is_empty() {
            break;
        }
        if let Some((name, value)) = line.split_once(':') {
            let name = name.trim().to_ascii_lowercase();
            let value = value.trim().to_string();
            if name == "content-length" {
                content_length = value.parse::<usize>().unwrap_or(0);
            }
            headers.push((name, value));
        }
    }

    let mut body = String::new();
    if content_length > 0 {
        let mut buf = vec![0u8; content_length];
        reader.read_exact(&mut buf).map_err(|e| e.to_string())?;
        body = String::from_utf8_lossy(&buf).to_string();
    }

    let (path, query) = split_target(&target);
    Ok(Request {
        method,
        path,
        query,
        headers,
        body,
        peer,
    })
}
