// Engine entry point: parse the CLI and dispatch to a run mode.
//
// TODO: implement argument parsing for
//   --mode <nocheckpoint|checkpoint|resume|hash>
//   --db --manifest --inputs --targets --seed-file --resume-file
//   --snapshot --run-id --snap-dir
// and drive the training loop / hashing per /app/spec/engine_design.md (sec. 18).
// Exit 0 on success, nonzero with a diagnostic on any failure.

mod checkpoint;
mod dataset;
mod dbwriter;
mod ops;
mod optimizer;
mod report;
mod rng;
mod tape;
mod tensor;

fn main() {
    // TODO: replace this stub with the real dispatch.
    eprintln!("engine: not implemented yet — see /app/spec/engine_design.md");
    std::process::exit(1);
}
