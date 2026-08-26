#[path = "../../r9m/fold_q.rs"]
mod fold_q;
#[path = "../../r9m/step_1.rs"]
mod step_1;

pub use fold_q::fold_q;
pub use step_1::step_1;

pub fn seal(
    port: u16,
    graph_path: &str,
    rooms: &[String],
    moves: &[String],
    endpoint: &str,
    status: u16,
) -> Result<String, String> {
    eprintln!("{}", fold_q(rooms, moves));
    step_1(port, graph_path, rooms, moves, endpoint, status)
}
