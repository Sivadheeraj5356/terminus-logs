//! Policy parse errors. A parse failure maps to a PERMERROR result during
//! evaluation. Frozen evidence.

#[derive(Debug, Clone, Copy)]
pub struct ParseError;

pub type PResult<T> = Result<T, ParseError>;
