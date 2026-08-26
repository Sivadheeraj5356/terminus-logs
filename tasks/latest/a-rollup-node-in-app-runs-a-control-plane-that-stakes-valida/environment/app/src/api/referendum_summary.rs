use crate::json::{value, Json};
use crate::types::governance::Referendum;

pub fn summary(referendum: &Referendum) -> Json {
    Json::from_pairs(vec![
        ("id", value::s(&referendum.id)),
        ("title", value::s(&referendum.title)),
        ("visibility", value::s(referendum.visibility.as_str())),
    ])
}
