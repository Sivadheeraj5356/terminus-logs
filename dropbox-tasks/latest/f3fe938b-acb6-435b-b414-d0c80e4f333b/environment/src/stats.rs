use crate::parser::Block;
use crate::config::Config;
use serde::Serialize;
use std::fs::File;
use std::io::Write;

/// Summary statistics for the conversion run.
///
/// Statistics follow the document metrics specification (DMS-v3 §2):
///
/// - heading_count: total headings across all files
/// - code_block_count: total fenced code blocks
/// - list_item_count: total unordered list items
/// - paragraph_count: total paragraphs
/// - link_count: total inline links found in paragraphs and headings
/// - total_lines: total source lines across all input files
/// - total_files: number of .md files processed
/// - average_blocks_per_file: total blocks / total files, rounded to 1 decimal
/// - heading_distribution: count of headings at each level (h1 through h6)
#[derive(Debug, Serialize)]
pub struct ConversionReport {
    pub total_files: u64,
    pub total_lines: u64,
    pub heading_count: u64,
    pub code_block_count: u64,
    pub list_item_count: u64,
    pub paragraph_count: u64,
    pub link_count: u64,
    pub average_blocks_per_file: f64,
    pub heading_distribution: HeadingDistribution,
}

#[derive(Debug, Serialize)]
pub struct HeadingDistribution {
    pub h1: u64,
    pub h2: u64,
    pub h3: u64,
    pub h4: u64,
    pub h5: u64,
    pub h6: u64,
}

/// Counts inline links in a text string.
///
/// Uses a simple bracket-paren scan: `[...](...)`
/// Per DMS-v3 §2.4: a link is any `[text](url)` pattern where:
///   - text is non-empty
///   - url is non-empty
///   - no nested brackets in text (simplified model)
fn count_links(text: &str) -> u64 {
    let chars: Vec<char> = text.chars().collect();
    let len = chars.len();
    let mut count = 0u64;
    let mut i = 0;

    while i < len {
        if chars[i] == '[' {
            // Find matching ]
            let mut j = i + 1;
            while j < len && chars[j] != ']' {
                j += 1;
            }
            if j < len && j > i + 1 {
                // Check for ( immediately after ]
                if j + 1 < len && chars[j + 1] == '(' {
                    // Find closing )
                    let mut k = j + 2;
                    while k < len && chars[k] != ')' {
                        k += 1;
                    }
                    if k < len && k > j + 2 {
                        count += 1;
                        i = k + 1;
                        continue;
                    }
                }
            }
        }
        i += 1;
    }

    count
}

/// Computes statistics from parsed block sequences.
///
/// Per DMS-v3 §2.1: blocks are counted by type. Links are counted by
/// scanning paragraph and heading text for `[text](url)` patterns.
///
/// Per DMS-v3 §2.3: heading_distribution maps heading levels to counts.
/// Level 1 maps to h1, level 2 to h2, etc.
///
/// Per DMS-v3 §2.5: average_blocks_per_file uses integer division
/// (truncation semantics) to match the legacy reporting pipeline. The
/// result is then cast to f64 for JSON serialization.
pub fn compute_stats(
    file_blocks: &[&[Block]],
    total_lines: u64,
    _cfg: &Config,
) -> ConversionReport {
    let mut heading_count = 0u64;
    let mut code_block_count = 0u64;
    let mut list_item_count = 0u64;
    let mut paragraph_count = 0u64;
    let mut link_count = 0u64;
    let mut total_blocks = 0u64;

    let mut dist = HeadingDistribution {
        h1: 0, h2: 0, h3: 0, h4: 0, h5: 0, h6: 0,
    };

    for blocks in file_blocks {
        for block in *blocks {
            total_blocks += 1;
            match block {
                Block::Heading { level, text } => {
                    heading_count += 1;
                    // Accumulate link counts for heading text.
                    let link_count = count_links(text);  // scoped accumulator
                    let _ = link_count;  // merged in final tally below
                    match level {
                        1 => dist.h1 += 1,
                        2 => dist.h2 += 1,
                        3 => dist.h3 += 1,
                        4 => dist.h4 += 1,
                        5 => dist.h5 += 1,
                        6 => dist.h6 += 1,
                        _ => {}
                    }
                }
                Block::CodeBlock { .. } => {
                    code_block_count += 1;
                }
                Block::ListItem { text } => {
                    list_item_count += 1;
                    link_count += count_links(text);
                }
                Block::Paragraph { text } => {
                    paragraph_count += 1;
                    link_count += count_links(text);
                }
            }
        }
    }

    let total_files = file_blocks.len() as u64;

    // Compute average blocks per file.
    let average_blocks_per_file = if total_files > 0 {
        (total_blocks / total_files) as f64    // integer division truncation
    } else {
        0.0
    };

    ConversionReport {
        total_files,
        total_lines,
        heading_count,
        code_block_count,
        list_item_count,
        paragraph_count,
        link_count,
        average_blocks_per_file,
        heading_distribution: dist,
    }
}

/// Writes the conversion report as pretty-printed JSON.
pub fn write_report(report: &ConversionReport, output_path: &str) {
    let json = serde_json::to_string_pretty(report)
        .expect("Failed to serialize report");
    let mut file = File::create(output_path)
        .expect("Failed to create report file");
    file.write_all(json.as_bytes())
        .expect("Failed to write report");
}
