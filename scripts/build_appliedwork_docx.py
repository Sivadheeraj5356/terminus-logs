"""Build the submission-ready AppliedWork Word briefing."""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "AppliedWork_Environments_Technical_Briefing.docx"

NAVY = RGBColor(0x1B, 0x2A, 0x4A)
BODY = RGBColor(0x22, 0x22, 0x22)
MUTED = RGBColor(0x55, 0x55, 0x55)
HEADER_BG = "1B2A4A"
HEADER_FG = "FFFFFF"
ALT_ROW = "F4F6F8"


def set_run(run, *, size=11, bold=False, color=BODY, font="Calibri"):
    run.font.name = font
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font)
    run.font.size = Pt(size)
    run.bold = bold
    run.font.color.rgb = color


def add_para(doc, text, *, size=11, bold=False, color=BODY, space_after=8, space_before=0, align=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    if align:
        p.alignment = align
    run = p.add_run(text)
    set_run(run, size=size, bold=bold, color=color)
    return p


def add_heading(doc, text, level=1):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(16 if level == 1 else 12)
    p.paragraph_format.space_after = Pt(6)
    size = 16 if level == 1 else 13
    run = p.add_run(text)
    set_run(run, size=size, bold=True, color=NAVY)
    return p


def shade_cell(cell, hex_color):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), hex_color)
    shd.set(qn("w:val"), "clear")
    tcPr.append(shd)


def set_cell_border(cell):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), "D0D5DD")
        tcBorders.append(el)
    tcPr.append(tcBorders)


def fill_cell(cell, text, *, header=False, center=False):
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(3)
    if center:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    set_run(
        run,
        size=10,
        bold=header,
        color=RGBColor(0xFF, 0xFF, 0xFF) if header else BODY,
    )
    set_cell_border(cell)
    if header:
        shade_cell(cell, HEADER_BG)


def add_table(doc, headers, rows, numeric_last=False):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    for i, h in enumerate(headers):
        fill_cell(table.rows[0].cells[i], h, header=True, center=(i > 0))
    for r_i, row in enumerate(rows):
        for c_i, val in enumerate(row):
            fill_cell(
                table.rows[r_i + 1].cells[c_i],
                str(val),
                center=(numeric_last and c_i > 0),
            )
            if r_i % 2 == 1:
                shade_cell(table.rows[r_i + 1].cells[c_i], ALT_ROW)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return table


def add_bullet(doc, text, bold_lead=None):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.left_indent = Inches(0.35)
    if bold_lead:
        r1 = p.add_run(bold_lead)
        set_run(r1, size=11, bold=True)
        r2 = p.add_run(text)
        set_run(r2, size=11)
    else:
        r = p.add_run(text)
        set_run(r, size=11)
    return p


def build() -> Path:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()

    for section in doc.sections:
        section.top_margin = Inches(0.9)
        section.bottom_margin = Inches(0.9)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    add_para(doc, "APPLIED WORK", size=11, bold=True, color=NAVY, space_after=2)
    add_para(
        doc,
        "Technical Briefing: Agent Environments, Task Catalog, and Evaluation Stack",
        size=20,
        bold=True,
        color=NAVY,
        space_after=8,
    )
    add_para(
        doc,
        "Prepared by Siva Dheeraj Ethamsetti  ·  26 August 2026  ·  Confidential — for partner review",
        size=10,
        color=MUTED,
        space_after=4,
    )
    add_para(
        doc,
        "This document describes work completed to date on privately authored Terminal-Bench-format "
        "environments, the local evaluation stack used to run them, and why Terminal-Bench Challenges "
        "are treated as worlds (full agentic environments) rather than quiz-style benchmarks. "
        "Unmeasured claims are stated as unmeasured.",
        space_after=12,
    )

    add_heading(doc, "1. Purpose", 1)
    add_para(
        doc,
        "Applied Work is building a services capability for AI evaluation data: accepted tasks, "
        "verifiers, and RL-style environments delivered against a buyer specification. The near-term "
        "commercial path is BPO / data-as-a-service partnerships. Buyers expect two things before "
        "allocation: a real delivery system, and a failure report grounded in verifier outcomes.",
    )
    add_para(
        doc,
        "This briefing is the technical proof of the first item and the design of the second. "
        "The source corpus is a private set of Terminal-Bench-style task submissions. It is not "
        "the public 89-task Terminal-Bench 2 GitHub dataset, and it is not yet a measured stump report.",
    )
    add_para(
        doc,
        "Difficulty labels (hard / medium) are author metadata. They are not pass rates on Claude Opus 5 "
        "or GPT-5.6. Stump percentage is defined only from completed Harbor trials after excluding "
        "timeouts and infrastructure errors. Until those trials exist, stump percentage is unknown.",
    )

    add_heading(doc, "2. Work completed", 1)
    add_heading(doc, "2.1 Private task corpus", 2)
    add_para(doc, "The Dropbox archive was inventoried and reduced to one latest revision per submission identifier.")
    add_table(
        doc,
        ["Item", "Count"],
        [
            ["Submission archives in the dump", "1,170"],
            ["Unique submission IDs (latest revision retained)", "448"],
            ["Catalog records written", "448"],
            ["Parse errors", "0"],
            ["Harbor job logs packed inside the archives", "0"],
            ["Public Terminal-Bench 2 tasks included", "0"],
        ],
        numeric_last=True,
    )
    add_para(doc, "Author-labeled difficulty on the latest revision of each task:", space_before=6)
    add_table(
        doc,
        ["Difficulty label", "Count"],
        [["Hard", "394"], ["Medium", "46"], ["Unspecified", "8"]],
        numeric_last=True,
    )
    add_para(doc, "Category mix on the latest revision:", space_before=6)
    add_table(
        doc,
        ["Category", "Count"],
        [
            ["Scientific computing", "108"],
            ["Security", "90"],
            ["System administration", "60"],
            ["Build and dependency management", "51"],
            ["Data processing", "51"],
            ["Machine learning", "46"],
            ["Games", "40"],
            ["Debugging", "2"],
        ],
        numeric_last=True,
    )

    add_heading(doc, "2.2 Per-task catalog", 2)
    add_para(
        doc,
        "Each of the 448 tasks has a catalog record with four fields designed for a partner failure report:",
    )
    add_bullet(doc, " Instruction gist, category, difficulty, timeouts, required artifacts, oracle and tests.", bold_lead="Task summary.")
    add_bullet(doc, " Verifier outcome when a Harbor job exists; otherwise marked as no logs.", bold_lead="Log summary.")
    add_bullet(doc, " Trajectory and failure mode when a trial exists. Inferred notes are never used as stump evidence.", bold_lead="Agent summary.")
    add_bullet(
        doc,
        " stump_pct = valid_failures / completed_trials × 100. Timeouts and infrastructure errors are excluded. "
        "A task is banded as a stump only if the measured pass rate is 40 percent or lower.",
        bold_lead="Stump verdict.",
    )
    add_para(
        doc,
        "Deliverables already generated: a human-readable index, one markdown card per task, "
        "a JSONL export, and an inventory file. Rebuild is a single Python ingest over the source archive.",
    )

    add_heading(doc, "2.3 Local evaluation harness", 2)
    add_para(doc, "Evaluation runs locally. No third-party annotation platform is required to execute a trial.")
    add_table(
        doc,
        ["Component", "Status"],
        [
            ["Docker Desktop", "Operational (29.5.3)"],
            ["Harbor CLI", "0.22.0"],
            ["Terminal agent", "Harbor terminus-2"],
            ["Oracle smoke (1 task)", "Reward 1.0 in approximately one minute"],
            ["Terminus-2 agent smoke", "Pending a valid model API key"],
            ["Batch runner", "1 attempt per task, concurrency 2"],
            ["Catalog merge from jobs", "Implemented"],
        ],
    )
    add_para(
        doc,
        "The oracle smoke used task fd6e06f4-5580-4ea5-9d04-8af9d848f5c0 "
        "(feature-store training leakage and model-deployment gate). The Docker image built, "
        "tests wrote a Harbor reward, and the reference solution scored 1.0. That result certifies "
        "environment and verifier quality. It is not a model stump signal.",
    )
    add_para(
        doc,
        "Agent summaries and stump percentages require a private OpenAI or Anthropic key on the "
        "local host. After that key is present, the batch runner and catalog merge produce the "
        "measured failure report.",
    )

    add_heading(doc, "2.4 Task package format", 2)
    add_para(
        doc,
        "Every cataloged task is a Harbor v2 package — the same contract used by Terminal-Bench 2, "
        "Terminal-Bench 3, and Terminal-Bench Challenges:",
    )
    add_bullet(doc, "instruction.md — agent prompt")
    add_bullet(doc, "task.toml — metadata, timeouts, CPU, memory, storage, internet policy")
    add_bullet(doc, "environment/ — Dockerfile and the seeded world mounted at /app")
    add_bullet(doc, "solution/solve.sh — oracle (reference solve)")
    add_bullet(doc, "tests/test.sh — verifier that writes a Harbor reward")
    add_para(
        doc,
        "Typical task.toml fields in this corpus: schema version 2.0, difficulty, category, languages, "
        "expert and junior time estimates, verifier timeout, agent timeout, allow_internet = false, "
        "and resource limits. The feature-store smoke task is a closed world (C, SQL, Python, DuckDB "
        "lineage, in-container model registry, leakage and deployment gates). Agent timeout 1,800 seconds, "
        "verifier timeout 600 seconds, 2 CPU, 4 GB RAM, 10 GB disk, no internet. That is a scaled-down world, "
        "not a multiple-choice item.",
    )

    add_heading(doc, "3. Why Challenges are worlds", 1)
    add_para(
        doc,
        "Post-training buyers no longer purchase a preference label. They purchase a stateful environment, "
        "a deterministic verifier, and a reference trajectory. The industry name for that object is a world "
        "(or RL environment): the agent acts over a long horizon, the environment changes, and a program "
        "decides whether the outcome is correct.",
    )
    add_para(
        doc,
        "Terminal-Bench Challenges (announced 18 June 2026) are that object at full scale. "
        "The Terminal-Bench team’s published comparison:",
    )
    add_table(
        doc,
        ["", "SWE-bench", "Terminal-Bench (classic)", "Terminal-Bench Challenges"],
        [
            ["Task type", "Patch one issue", "Small programs and CLI work", "Build an entire codebase from scratch"],
            ["Time", "Minutes to hours", "Minutes to hours", "Days"],
            ["Cost", "About $1–$10", "About $1–$100", "About $1,000+"],
            ["Solution size", "Up to about 500 lines", "Up to about 10,000 lines", "About 10,000–500,000 lines"],
        ],
    )
    add_para(
        doc,
        "A Challenge is one instruction plus a large test bed. There is no human in the loop and no "
        "time or resource cap. Packaging is Harbor. The grade is a task-specific metric (correctness "
        "and/or performance). A leaderboard submission must include the output artifact and full agent "
        "logs that show no extra human guidance.",
    )
    add_para(doc, "The three public Challenges, and published agent results after 12-hour runs:", space_before=6)
    add_bullet(
        doc,
        " Restructure rustc enough to cut instruction count on a 52-crate slice of rustc-perf "
        "without breaking correctness. Claude Opus 4.8 produced no real gain; attempted optimizations regressed.",
        bold_lead="Rust compiler speedup.",
    )
    add_bullet(
        doc,
        " One C/CUDA file under 25 KB that serves Kimi 2.5, graded on a Pareto frontier "
        "(TTFT, tokens/s, TPOT) with logprobs versus SGLang. The agent approached logprob match, "
        "failed the size and correctness gate, and did not attempt real performance work.",
        bold_lead="Inference-engine codegolf.",
    )
    add_bullet(
        doc,
        " Software WebGL in JavaScript/WebAssembly as a drop-in for headless-gl, no GPU or browser. "
        "Roughly half the suite; WebGL 1.0 coverage was high, WebGL 2.0 about 20 percent.",
        bold_lead="WASM WebGL renderer.",
    )
    add_para(doc, "Published failure modes on those worlds — the vocabulary used for loss analysis here:")
    add_bullet(doc, " Agents refuse to discard a large wrong approach and start over.", bold_lead="No exploration after a plateau.")
    add_bullet(doc, " Agents launch a 20-minute full suite instead of a targeted test for the current edit.", bold_lead="Test-suite abuse.")
    add_para(
        doc,
        "Those are environment failures: long horizon, large state, expensive verification. "
        "They are not “the model missed a quiz item.” That is why Challenges are worlds — complete, "
        "interactive, verifiable workspaces an agent must inhabit.",
    )
    add_para(
        doc,
        "Classic Terminal-Bench (including the Terminal-Bench 3 line) remains complementary: cheaper, "
        "broader coverage, minutes to hours. The Terminal-Bench team describes Challenges and classic "
        "tasks as two views of the same capability, and notes that long-horizon difficulty can be "
        "compressed into smaller, cheaper tasks. The 448 submissions in this corpus are that compressed "
        "form: the same Harbor world contract (Docker, instruction, oracle, verifier) on a shorter horizon, "
        "suitable for a one-week measured failure report.",
    )
    add_para(
        doc,
        "SWE-bench evaluates a patch. A world is a place the agent lives in. Applied Work sells the second.",
    )

    add_heading(doc, "4. Loss-analysis method", 1)
    add_para(
        doc,
        "The partner artifact is a failure report, not an archive of prompts. Each Harbor trial is classified as follows.",
    )
    add_table(
        doc,
        ["Class", "Meaning", "Counts as stump"],
        [
            ["solved", "Verifier reward = 1.0", "No"],
            ["valid_fail", "Reward = 0.0, no timeout or infrastructure error", "Yes"],
            ["timeout", "Agent or verifier timeout", "No"],
            ["infra_error", "Authentication, Docker, setup, or missing reward file", "No"],
        ],
    )
    add_para(
        doc,
        "stump_pct = valid_fail / completed_trials × 100. An author label of “hard” is not a stump.",
    )
    add_para(
        doc,
        "First measured report: 20–30 tasks, mixed categories, one Terminus-2 trial per task on a single "
        "model, then a second pass on valid failures. Each row includes the instruction gist, oracle status, "
        "trajectory summary, failure type, and stump percentage. That packet is the BPO proof.",
    )
    add_para(
        doc,
        "Runs stay sequential, one attempt per task, low concurrency. A full 448-task pass is a later "
        "inventory exercise. The partner-facing week uses the 20–30 slice first.",
    )

    add_heading(doc, "5. Technology stack", 1)
    add_para(doc, "All evaluation described here is local. Platform virtual keys are not part of the runtime.")
    add_table(
        doc,
        ["Layer", "Choice", "Role"],
        [
            ["Host", "Windows 10 and Docker Desktop 29.5.3", "Daemon for trial containers"],
            ["Eval runner", "Harbor 0.22.0", "Jobs, trials, result.json; Challenges also ship as Harbor tasks"],
            ["Agent", "Harbor terminus-2", "Terminal agent for Terminal-Bench-style tasks"],
            ["Oracle", "Harbor oracle plus each task’s solve.sh", "Proves the world and verifier are solvable"],
            ["Model interface", "LiteLLM via Harbor (OpenAI or Anthropic)", "Private keys only"],
            ["Task format", "Harbor v2", "Same contract as TB2, TB3, and Challenges"],
            ["Ingest", "Python 3 and zipfile", "Latest zip per UUID; public TB2 excluded"],
            ["Reports", "Markdown cards, JSONL, job merge", "One row per task for the failure report"],
            ["Isolation", "allow_internet = false", "Grade is local tests; agent cannot call the public web"],
        ],
    )
    add_para(
        doc,
        "Snorkel (or any other BPO platform) is a buyer channel, not the evaluation runtime. "
        "Catalog ingest and Harbor trials do not depend on that platform’s CLI or credentials.",
    )

    add_heading(doc, "6. Commercial position", 1)
    add_para(
        doc,
        "Phase one is a services company: recruit and manage engineers, deliver against a buyer "
        "specification, and bill per accepted unit. Direct lab contracts come after a delivery record exists.",
    )
    add_bullet(doc, " Harbor-packaged worlds with oracles and verifiers, plus a measured failure report, plus a public site at appliedwork.ai.", bold_lead="Proof for a BPO door.")
    add_bullet(doc, " Pure staffing firms deliver on someone else’s infrastructure. This stack already runs Harbor locally and owns the catalog and verifier loop — a software-wrapped service, not staffing alone.", bold_lead="Differentiation.")
    add_bullet(doc, " What exists today is 448 Harbor packages, 394 author-labeled hard worlds, one oracle-green smoke, and a pipeline that will write stump percentages when model keys are present. Measured stump rates are not claimed.", bold_lead="Scope of claims.")

    add_heading(doc, "7. Next steps", 1)
    add_para(doc, "The remaining work is measurement, not corpus construction.")
    add_bullet(doc, "Configure a private OpenAI or Anthropic key on the evaluation host.")
    add_bullet(doc, "Smoke Terminus-2 on the feature-store task that already scores oracle reward 1.0.")
    add_bullet(doc, "Run 20–30 mixed-category tasks at one attempt each.")
    add_bullet(doc, "Merge Harbor jobs into the catalog and export the failure report (task, log, agent, stump percentage) with the jobs folder.")
    add_para(
        doc,
        "That report is the partner-facing proof. The 448-record catalog is the inventory behind it.",
    )

    add_heading(doc, "8. References", 1)
    add_bullet(doc, "https://www.tbench.ai/news/terminal-bench-challenges", bold_lead="Terminal-Bench Challenges. ")
    add_bullet(doc, "https://github.com/harbor-framework/harbor", bold_lead="Harbor. ")
    add_bullet(doc, "http://appliedwork.ai/", bold_lead="Applied Work. ")

    add_para(
        doc,
        "End of briefing.",
        size=10,
        color=MUTED,
        space_before=18,
        space_after=0,
    )

    doc.save(OUT)
    return OUT


if __name__ == "__main__":
    path = build()
    print(path)
