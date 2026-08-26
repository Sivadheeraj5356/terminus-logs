//! The subject of an evaluation. Frozen evidence.

/// What a policy is being asked about: the domain whose own records a bare
/// `a`/`mx` mechanism resolves, and the connecting client address.
pub struct Ctx<'a> {
    pub request: &'a str,
    pub ip: u32,
}

impl<'a> Ctx<'a> {
    pub fn new(request: &'a str, ip: u32) -> Ctx<'a> {
        Ctx { request, ip }
    }

    /// The context for reading `target`'s policy on this query's behalf.
    pub fn delegate(&self, target: &'a str) -> Ctx<'a> {
        Ctx {
            request: target,
            ip: self.ip,
        }
    }
}
