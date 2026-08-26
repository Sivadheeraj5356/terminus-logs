mod parser;
mod renderer;
mod stats;
mod config;

use std::fs;
use std::path::PathBuf;

fn main() {
    let cfg = config::load_config("/app/config/converter.toml");

    let input_dir = PathBuf::from(&cfg.input_dir);
    if !input_dir.exists() {
        eprintln!("Input directory {} not found", cfg.input_dir);
        std::process::exit(1);
    }

    let mut md_files: Vec<PathBuf> = fs::read_dir(&input_dir)
        .expect("Failed to read input directory")
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .filter(|p| p.extension().map_or(false, |ext| ext == "md"))
        .collect();

    md_files.sort();

    let mut all_blocks = Vec::new();
    let mut total_lines = 0u64;

    for path in &md_files {
        let content = fs::read_to_string(path)
            .expect(&format!("Failed to read {:?}", path));
        total_lines += content.lines().count() as u64;
        let blocks = parser::parse_markdown(&content, &cfg);
        all_blocks.push((path.clone(), blocks));
    }

    // Render all files to HTML
    for (path, blocks) in &all_blocks {
        let html = renderer::render_blocks(blocks, &cfg);
        let out_name = path.file_stem().unwrap().to_string_lossy().to_string() + ".html";
        let out_path = PathBuf::from(&cfg.output_dir).join(&out_name);
        fs::create_dir_all(&cfg.output_dir).ok();
        fs::write(&out_path, &html).expect(&format!("Failed to write {:?}", out_path));
    }

    // Compute and write statistics
    let stat_blocks: Vec<&[parser::Block]> = all_blocks.iter().map(|(_, b)| b.as_slice()).collect();
    let report = stats::compute_stats(&stat_blocks, total_lines, &cfg);
    stats::write_report(&report, &cfg.report_path);

    println!(
        "Converted {} files ({} lines) -> {} HTML files + {}",
        md_files.len(),
        total_lines,
        md_files.len(),
        cfg.report_path
    );
}
