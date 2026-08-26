//! Safe big-endian byte cursor helpers.

pub struct Cursor<'a> {
    data: &'a [u8],
    pos: usize,
}

impl<'a> Cursor<'a> {
    pub fn new(data: &'a [u8]) -> Self {
        Self { data, pos: 0 }
    }

    pub fn remaining(&self) -> usize {
        self.data.len().saturating_sub(self.pos)
    }

    pub fn finish(self) -> Result<(), String> {
        if self.pos != self.data.len() {
            return Err("trailing bytes".into());
        }
        Ok(())
    }

    pub fn read_exact(&mut self, n: usize) -> Result<&'a [u8], String> {
        if self.remaining() < n {
            return Err("truncated field".into());
        }
        let out = &self.data[self.pos..self.pos + n];
        self.pos += n;
        Ok(out)
    }

    pub fn read_u8(&mut self) -> Result<u8, String> {
        Ok(self.read_exact(1)?[0])
    }

    pub fn read_u16(&mut self) -> Result<u16, String> {
        let b = self.read_exact(2)?;
        Ok(u16::from_be_bytes([b[0], b[1]]))
    }

    pub fn read_u32(&mut self) -> Result<u32, String> {
        let b = self.read_exact(4)?;
        Ok(u32::from_be_bytes([b[0], b[1], b[2], b[3]]))
    }

    pub fn read_u64(&mut self) -> Result<u64, String> {
        let b = self.read_exact(8)?;
        Ok(u64::from_be_bytes([
            b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7],
        ]))
    }
}
