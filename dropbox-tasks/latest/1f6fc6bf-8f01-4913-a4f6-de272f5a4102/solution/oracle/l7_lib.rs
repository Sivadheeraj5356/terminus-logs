use mio::unix::SourceFd;
use mio::{Events, Interest, Poll, Token};
use std::collections::HashSet;
use std::os::unix::io::RawFd;
use std::time::Duration;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum LingerError {
    #[error("poll: {0}")]
    Poll(#[from] std::io::Error),
}

pub struct LingerPlane {
    poll: Poll,
    events: Events,
}

impl LingerPlane {
    pub fn new() -> Self {
        Self {
            poll: Poll::new().expect("poll"),
            events: Events::with_capacity(128),
        }
    }

    pub fn op_a(&mut self, fds: &[(u32, RawFd)]) -> Vec<u32> {
        let mut dead = Vec::new();
        if fds.is_empty() {
            return dead;
        }
        let interest = Interest::READABLE;
        for (sid, fd) in fds {
            let mut src = SourceFd(fd);
            if self
                .poll
                .registry()
                .register(&mut src, Token(*sid as usize), interest)
                .is_err()
            {
                dead.push(*sid);
            }
        }
        for _ in 0..6 {
            let _ = self.poll.poll(&mut self.events, Some(Duration::from_millis(100)));
            for event in self.events.iter() {
                if event.is_read_closed() {
                    let sid = event.token().0 as u32;
                    if !dead.contains(&sid) {
                        dead.push(sid);
                    }
                }
            }
        }
        let mut closed = dead.iter().copied().collect::<HashSet<_>>();
        for (sid, fd) in fds {
            if closed.contains(sid) {
                continue;
            }
            if fd_is_dead(*fd) {
                closed.insert(*sid);
                dead.push(*sid);
            }
        }
        for (sid, fd) in fds {
            let mut src = SourceFd(fd);
            let _ = self.poll.registry().deregister(&mut src);
        }
        dead.sort_unstable();
        dead.dedup();
        dead
    }

    pub fn reconcile_b(&mut self, dead: &[u32]) {
        let _ = dead;
    }
}

fn fd_is_dead(fd: RawFd) -> bool {
    let n = unsafe { libc::recv(fd, std::ptr::null_mut(), 0, libc::MSG_PEEK | libc::MSG_DONTWAIT) };
    if n == 0 {
        return true;
    }
    if n < 0 {
        let err = std::io::Error::last_os_error();
        return matches!(
            err.raw_os_error(),
            Some(libc::ECONNRESET) | Some(libc::EPIPE) | Some(libc::ENOTCONN) | Some(libc::EBADF)
        );
    }
    false
}

impl Default for LingerPlane {
    fn default() -> Self {
        Self::new()
    }
}
