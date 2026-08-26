use std::fmt;

#[derive(Debug)]
pub struct ErrMsg(pub String);

impl fmt::Display for ErrMsg {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl std::error::Error for ErrMsg {}

impl From<String> for ErrMsg {
    fn from(s: String) -> Self {
        ErrMsg(s)
    }
}

impl From<&str> for ErrMsg {
    fn from(s: &str) -> Self {
        ErrMsg(s.to_string())
    }
}
