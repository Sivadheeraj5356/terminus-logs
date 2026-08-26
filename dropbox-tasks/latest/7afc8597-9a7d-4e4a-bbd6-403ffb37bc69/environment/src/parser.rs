use crate::ast::Node;

pub fn parse(_pattern: &[u8]) -> Result<Node, String> {
    Err("parser not implemented".to_string())
}

pub fn split_anchors(node: &Node) -> (bool, bool, Node) {
    (false, false, node.clone())
}
