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
    #[error("generation effective limit exceeded")]
    EffectiveLimit,
    #[error("shard pool cap exceeded")]
    ShardCap,
}

struct PooledConn {
    stream: TcpStream,
    fd: RawFd,
    gen: u32,
}

pub struct Pool {
    next_id: u32,
    active: HashMap<u32, CheckedOut>,
    idle: HashMap<u32, Vec<PooledConn>>,
    peak: u32,
}

pub fn effective_limit(base: u32, pool_gen: u32) -> u32 {
    base.saturating_sub(pool_gen.saturating_mul(2))
}

impl Pool {
    pub fn new() -> Self {
        Self {
            next_id: 1,
            active: HashMap::new(),
            idle: HashMap::new(),
            peak: 0,
        }
    }

    pub fn checkout(
        &mut self,
        shard: &ShardEndpoint,
        max_per_shard: u32,
        ceiling: u32,
        pool_gen: u32,
    ) -> Result<CheckedOut, PoolError> {
        let limit = effective_limit(ceiling, pool_gen);
        if limit == 0 || self.resolve_c() >= limit {
            return Err(PoolError::EffectiveLimit);
        }
        if self.resolve_c() >= ceiling {
            return Err(PoolError::DescriptorBudget);
        }
        let idle_vec = self.idle.entry(shard.id).or_default();
        let (stream, fd) = if let Some(conn) = idle_vec.pop() {
            (conn.stream, conn.fd)
        } else {
            if idle_vec.len() as u32 + self.count_shard_active(shard.id) >= max_per_shard {
                return Err(PoolError::ShardCap);
            }
            let addr = format!("{}:{}", shard.host, shard.port);
            let stream = TcpStream::connect(&addr)?;
            stream.set_nodelay(true).ok();
            let fd = stream.as_raw_fd();
            (stream, fd)
        };
        let socket_id = self.next_id;
        self.next_id += 1;
        let item = CheckedOut {
            socket_id,
            shard: shard.id,
            fd,
            stream,
        };
        self.active.insert(socket_id, item);
        self.peak = self.peak.max(self.resolve_c());
        Ok(self.active.get(&socket_id).unwrap().clone())
    }

    pub fn checkin(&mut self, socket_id: u32, gen: u32) -> Result<(), PoolError> {
        let item = self
            .active
            .remove(&socket_id)
            .ok_or(PoolError::UnknownSocket(socket_id))?;
        self.idle
            .entry(item.shard)
            .or_default()
            .push(PooledConn {
                stream: item.stream,
                fd: item.fd,
                gen,
            });
        Ok(())
    }

    pub fn retag_idle_generation(&mut self, gen: u32) {
        for conns in self.idle.values_mut() {
            for conn in conns.iter_mut() {
                conn.gen = gen;
            }
        }
    }

    pub fn resolve_c(&self) -> u32 {
        let idle: usize = self.idle.values().map(|v| v.len()).sum();
        (self.active.len() + idle) as u32
    }

    pub fn peak(&self) -> u32 {
        self.peak
    }

    pub fn idle_entries(&self) -> Vec<(u32, RawFd, u32, u32)> {
        let mut out = Vec::new();
        for (shard, conns) in &self.idle {
            for (idx, conn) in conns.iter().enumerate() {
                let sid = (*shard << 16) | (idx as u32);
                out.push((sid, conn.fd, conn.gen, *shard));
            }
        }
        out
    }

    pub fn active_fds(&self) -> Vec<(u32, RawFd)> {
        let mut out: Vec<(u32, RawFd)> = self
            .active
            .values()
            .map(|c| (c.socket_id, c.fd))
            .collect();
        for (shard, conns) in &self.idle {
            for (idx, conn) in conns.iter().enumerate() {
                let sid = (*shard << 16) | (idx as u32);
                out.push((sid, conn.fd));
            }
        }
        out
    }

    pub fn remove_socket(&mut self, socket_id: u32) -> Option<(CheckedOut, u32)> {
        if let Some(item) = self.active.remove(&socket_id) {
            return Some((item, 0));
        }
        let shard = (socket_id >> 16) as u32;
        let idx = (socket_id & 0xffff) as usize;
        if let Some(vec) = self.idle.get_mut(&shard) {
            if idx < vec.len() {
                let conn = vec.remove(idx);
                return Some((
                    CheckedOut {
                        socket_id,
                        shard,
                        fd: conn.fd,
                        stream: conn.stream,
                    },
                    conn.gen,
                ));
            }
        }
        None
    }

    fn count_shard_active(&self, shard: u32) -> u32 {
        self.active.values().filter(|c| c.shard == shard).count() as u32
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
