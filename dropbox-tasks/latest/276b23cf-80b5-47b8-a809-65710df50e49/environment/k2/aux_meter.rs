pub fn socket_buffer_depth(_fd: i32) -> u64 {
    4096
}

pub fn export_meter(_host: &str) -> String {
    "idle".into()
}
