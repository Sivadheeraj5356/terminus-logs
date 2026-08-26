use prlg_c8::ShardEndpoint;
use std::collections::HashMap;
use std::io::{Read, Write};
use std::net::TcpStream;
use std::os::unix::io::{AsRawFd, RawFd};
use thiserror::Error;

#[derive(Debug)]
pub struct CheckedOut {
    pub socket_id: u32,
    pub shard: u32,
    pub fd: RawFd,
    pub stream: TcpStream,
}

#[derive(Debug, Error)]
pub enum PoolError {
    #[error("io: {0}")]
    Io(#[from] std::io::Error),
    #[error("unknown socket_id {0}")]
    UnknownSocket(u32),
    #[error("descriptor budget exceeded")]
    DescriptorBudget,
    #[error("shard pool cap exceeded")]
    ShardCap,
}

pub struct Pool {
    next_id: u32,
    active: HashMap<u32, CheckedOut>,
    leaked: Vec<TcpStream>,
    peak: u32,
}

impl Pool {
    pub fn new() -> Self {
        Self {
            next_id: 1,
            active: HashMap::new(),
            leaked: Vec::new(),
            peak: 0,
        }
    }

    pub fn checkout(
        &mut self,
        shard: &ShardEndpoint,
        _max_per_shard: u32,
        _ceiling: u32,
    ) -> Result<CheckedOut, PoolError> {
        let addr = format!("{}:{}", shard.host, shard.port);
        let stream = TcpStream::connect(&addr)?;
        stream.set_nodelay(true).ok();
        let socket_id = self.next_id;
        self.next_id += 1;
        let fd = stream.as_raw_fd();
        let item = CheckedOut {
            socket_id,
            shard: shard.id,
            fd,
            stream,
        };
        self.active.insert(socket_id, item);
        self.peak = self.peak.max(self.active.len() as u32 + self.leaked.len() as u32);
        Ok(self.active.get(&socket_id).unwrap().clone())
    }

    pub fn checkin(&mut self, socket_id: u32) -> Result<(), PoolError> {
        let item = self
            .active
            .remove(&socket_id)
            .ok_or(PoolError::UnknownSocket(socket_id))?;
        self.leaked.push(item.stream);
        Ok(())
    }

    pub fn resolve_c(&self) -> u32 {
        (self.active.len() + self.leaked.len()) as u32
    }

    pub fn peak(&self) -> u32 {
        self.peak
    }

    pub fn active_fds(&self) -> Vec<(u32, RawFd)> {
        self.active.values().map(|c| (c.socket_id, c.fd)).collect()
    }

    pub fn remove_socket(&mut self, socket_id: u32) -> Option<CheckedOut> {
        self.active.remove(&socket_id)
    }
}

pub fn ping(stream: &mut TcpStream) -> Result<(), PoolError> {
    stream.write_all(b"PING\n")?;
    let mut buf = [0u8; 8];
    let n = stream.read(&mut buf)?;
    if n < 5 || &buf[..4] != b"PONG" {
        return Err(PoolError::Io(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            "bad pong",
        )));
    }
    Ok(())
}

impl Default for Pool {
    fn default() -> Self {
        Self::new()
    }
}

impl Clone for CheckedOut {
    fn clone(&self) -> Self {
        Self {
            socket_id: self.socket_id,
            shard: self.shard,
            fd: self.fd,
            stream: self.stream.try_clone().expect("dup fd"),
        }
    }
}
