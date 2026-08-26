"""
test_outputs.py — verifier tests for the rust-markdown-converter task.

All expected values are independently computed by re-parsing the input
Markdown files using correct algorithms. No hardcoded expected values
are used — everything is derived from the source files at test time.
"""

import json
import os
import subprocess
import glob
import pytest


@pytest.fixture(scope="module")
def build_and_run():
    """Build the converter, run it, and return True if successful."""
    result = subprocess.run(
        ["cargo", "build", "--release"],
        cwd="/app",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Build failed:\n{result.stderr}"

    run = subprocess.run(
        ["/app/target/release/md_convert"],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, f"Binary failed:\n{run.stderr}"
    return True


@pytest.fixture(scope="module")
def report(build_and_run):
    """Load the generated report.json."""
    assert os.path.exists("/app/output/report.json"), "report.json not found"
    with open("/app/output/report.json") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def ground_truth():
    """
    Independently compute expected values using correct parsing logic.

    Correct rules:
    - heading level = number of # characters (NOT # count + 1)
    - code fence close must match opening character
    - average_blocks_per_file = float division, rounded to 1 decimal
    """
    input_dir = "/app/input"
    md_files = sorted(glob.glob(os.path.join(input_dir, "*.md")))
    assert len(md_files) >= 2, "Expected at least 2 input .md files"

    total_lines = 0
    total_blocks = 0
    heading_count = 0
    code_block_count = 0
    list_item_count = 0
    paragraph_count = 0
    link_count = 0
    heading_dist = {"h1": 0, "h2": 0, "h3": 0, "h4": 0, "h5": 0, "h6": 0}

    def count_links_in_text(text):
        """Count [text](url) patterns in text."""
        count = 0
        chars = list(text)
        i = 0
        while i < len(chars):
            if chars[i] == '[':
                j = i + 1
                while j < len(chars) and chars[j] != ']':
                    j += 1
                if j < len(chars) and j > i + 1:
                    if j + 1 < len(chars) and chars[j + 1] == '(':
                        k = j + 2
                        while k < len(chars) and chars[k] != ')':
                            k += 1
                        if k < len(chars) and k > j + 2:
                            count += 1
                            i = k + 1
                            continue
            i += 1
        return count

    for md_path in md_files:
        with open(md_path) as f:
            content = f.read()

        lines = content.split('\n')
        # Remove trailing empty string from split if file ends with newline
        if lines and lines[-1] == '':
            total_lines += len(lines) - 1
        else:
            total_lines += len(lines)

        # Parse blocks using correct logic
        i = 0
        paragraph_lines = []
        file_lines = content.splitlines()

        while i < len(file_lines):
            line = file_lines[i]
            trimmed = line.strip()

            # Blank line
            if not trimmed:
                if paragraph_lines:
                    text = ' '.join(paragraph_lines)
                    paragraph_count += 1
                    total_blocks += 1
                    link_count += count_links_in_text(text)
                    paragraph_lines = []
                i += 1
                continue

            # ATX heading
            if trimmed.startswith('#'):
                if paragraph_lines:
                    text = ' '.join(paragraph_lines)
                    paragraph_count += 1
                    total_blocks += 1
                    link_count += count_links_in_text(text)
                    paragraph_lines = []

                hashes = 0
                for ch in trimmed:
                    if ch == '#':
                        hashes += 1
                    else:
                        break

                if hashes <= 6 and len(trimmed) > hashes and trimmed[hashes] == ' ':
                    level = min(hashes, 6)  # CORRECT: no +1
                    heading_count += 1
                    total_blocks += 1
                    heading_text = trimmed[hashes + 1:].strip()
                    link_count += count_links_in_text(heading_text)
                    heading_dist[f"h{level}"] += 1
                else:
                    paragraph_lines.append(trimmed)
                i += 1
                continue

            # Fenced code block
            if trimmed.startswith('```') or trimmed.startswith('~~~'):
                if paragraph_lines:
                    text = ' '.join(paragraph_lines)
                    paragraph_count += 1
                    total_blocks += 1
                    link_count += count_links_in_text(text)
                    paragraph_lines = []

                fence_char = trimmed[0]
                i += 1
                while i < len(file_lines):
                    code_line = file_lines[i].strip()
                    # CORRECT: only close with matching fence char
                    fence_str = fence_char * 3
                    if code_line.startswith(fence_str):
                        i += 1
                        break
                    i += 1

                code_block_count += 1
                total_blocks += 1
                continue

            # List item
            if trimmed.startswith('- ') or trimmed.startswith('* '):
                if paragraph_lines:
                    text = ' '.join(paragraph_lines)
                    paragraph_count += 1
                    total_blocks += 1
                    link_count += count_links_in_text(text)
                    paragraph_lines = []

                item_text = trimmed[2:]
                list_item_count += 1
                total_blocks += 1
                link_count += count_links_in_text(item_text)
                i += 1
                continue

            # Regular text
            paragraph_lines.append(trimmed)
            i += 1

        # Flush remaining paragraph
        if paragraph_lines:
            text = ' '.join(paragraph_lines)
            paragraph_count += 1
            total_blocks += 1
            link_count += count_links_in_text(text)

    total_files = len(md_files)
    avg = round(total_blocks / total_files, 1) if total_files > 0 else 0.0

    return {
        "total_files": total_files,
        "total_lines": total_lines,
        "heading_count": heading_count,
        "code_block_count": code_block_count,
        "list_item_count": list_item_count,
        "paragraph_count": paragraph_count,
        "link_count": link_count,
        "average_blocks_per_file": avg,
        "heading_distribution": heading_dist,
    }


# ──────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────

def test_binary_compiles_and_runs():
    """Verify that the Rust binary can be compiled and run without error."""
    result = subprocess.run(
        ["cargo", "build", "--release"],
        cwd="/app",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"cargo build --release failed:\n{result.stderr}"
    assert os.path.exists("/app/target/release/md_convert"), \
        "Binary not found at /app/target/release/md_convert"


def test_report_json_exists(report):
    """Verify that report.json exists and is valid JSON."""
    assert os.path.exists("/app/output/report.json"), "report.json not found"


def test_required_keys_present(report):
    """Verify all required top-level keys are present in the report."""
    for key in ("total_files", "total_lines", "heading_count",
                "code_block_count", "list_item_count", "paragraph_count",
                "link_count", "average_blocks_per_file", "heading_distribution"):
        assert key in report, f"Missing key: {key}"


def test_heading_distribution_keys(report):
    """Verify heading_distribution contains h1 through h6 sub-keys."""
    dist = report["heading_distribution"]
    for h in ("h1", "h2", "h3", "h4", "h5", "h6"):
        assert h in dist, f"Missing heading_distribution key: {h}"


def test_total_files_correct(report, ground_truth):
    """Verify total_files matches the number of .md input files."""
    assert report["total_files"] == ground_truth["total_files"], (
        f"total_files: got {report['total_files']}, "
        f"expected {ground_truth['total_files']}"
    )


def test_total_lines_correct(report, ground_truth):
    """Verify total_lines matches the sum of lines across all input files."""
    assert report["total_lines"] == ground_truth["total_lines"], (
        f"total_lines: got {report['total_lines']}, "
        f"expected {ground_truth['total_lines']}"
    )


def test_heading_count_correct(report, ground_truth):
    """
    Verify heading_count matches independent parsing.
    Note: Usually catches off-by-one errors or fence bugs that misparse blocks.
    """
    assert report["heading_count"] == ground_truth["heading_count"], (
        f"heading_count: got {report['heading_count']}, "
        f"expected {ground_truth['heading_count']}"
    )


def test_code_block_count_correct(report, ground_truth):
    """
    Verify code_block_count. This catches the fence-matching bug: if
    mismatched fences close blocks early, the count will be wrong.
    """
    assert report["code_block_count"] == ground_truth["code_block_count"], (
        f"code_block_count: got {report['code_block_count']}, "
        f"expected {ground_truth['code_block_count']}"
    )


def test_list_item_count_correct(report, ground_truth):
    """Verify list_item_count matches independent parsing."""
    assert report["list_item_count"] == ground_truth["list_item_count"], (
        f"list_item_count: got {report['list_item_count']}, "
        f"expected {ground_truth['list_item_count']}"
    )


def test_paragraph_count_correct(report, ground_truth):
    """Verify paragraph_count matches independent parsing."""
    assert report["paragraph_count"] == ground_truth["paragraph_count"], (
        f"paragraph_count: got {report['paragraph_count']}, "
        f"expected {ground_truth['paragraph_count']}"
    )


def test_link_count_correct(report, ground_truth):
    """
    Verify link_count matches independent scanning of all text blocks.
    Bug caught: the 'links in headings are ignored' bug (Fix E).
    """
    assert report["link_count"] == ground_truth["link_count"], (
        f"link_count: got {report['link_count']}, "
        f"expected {ground_truth['link_count']}"
    )


def test_average_blocks_per_file_correct(report, ground_truth):
    """
    Verify average_blocks_per_file matches floating-point ground truth.
    Bug caught: integer division truncation bug (Fix D).
    """
    expected = ground_truth["average_blocks_per_file"]
    got = report["average_blocks_per_file"]
    assert abs(got - expected) < 0.05, (
        f"average_blocks_per_file: got {got}, expected {expected}. "
        f"If truncated, integer division may be in use."
    )


def test_heading_distribution_h1(report, ground_truth):
    """
    Verify h1 count. This is the primary indicator of the heading level
    bug — if the parser adds +1, all h1 headings become h2.
    """
    got = report["heading_distribution"]["h1"]
    expected = ground_truth["heading_distribution"]["h1"]
    assert got == expected, (
        f"heading_distribution.h1: got {got}, expected {expected}. "
        f"If h1 is 0, the parser may be using level = hashes+1."
    )


def test_heading_distribution_h2(report, ground_truth):
    """
    Verify h2 count in heading distribution.
    Bug caught: off-by-one error (hashes + 1) in parser (Fix A).
    """
    got = report["heading_distribution"]["h2"]
    expected = ground_truth["heading_distribution"]["h2"]
    assert got == expected, (
        f"heading_distribution.h2: got {got}, expected {expected}"
    )


def test_heading_distribution_h3(report, ground_truth):
    """
    Verify h3 count in heading distribution.
    Bug caught: off-by-one error (hashes + 1) in parser (Fix A).
    """
    got = report["heading_distribution"]["h3"]
    expected = ground_truth["heading_distribution"]["h3"]
    assert got == expected, (
        f"heading_distribution.h3: got {got}, expected {expected}"
    )


def test_html_heading_tags_correct(build_and_run):
    """
    Verify that HTML output files use the correct heading tags.
    For example, # Heading should produce <h1>, not <h2>.
    """
    html_files = sorted(glob.glob("/app/output/*.html"))
    assert len(html_files) >= 2, "Expected at least 2 HTML output files"

    # Check that at least one file contains <h1> tags (proves no +1 offset)
    found_h1 = False
    for html_path in html_files:
        with open(html_path) as f:
            content = f.read()
        if "<h1>" in content:
            found_h1 = True
            break

    assert found_h1, (
        "No <h1> tags found in any HTML output. The parser may be using "
        "level = hashes + 1, making all h1 headings render as h2."
    )


def test_code_block_content_preserved(build_and_run):
    """
    Verify that code block content is properly preserved in HTML output,
    especially when the input has mixed ``` and ~~~ fences.
    """
    # The api.md file has a ~~~ block that should not close ``` blocks
    api_html = "/app/output/api.html"
    assert os.path.exists(api_html), "api.html not found"

    with open(api_html) as f:
        content = f.read()

    # Count <pre><code blocks — should match the ground truth code_block_count
    # for this specific file
    pre_count = content.count("<pre><code")
    # api.md has 3 code blocks: ```json, ```bash, ~~~
    assert pre_count >= 3, (
        f"Expected at least 3 code blocks in api.html, found {pre_count}. "
        f"Mismatched fence characters may be closing blocks early."
    )
