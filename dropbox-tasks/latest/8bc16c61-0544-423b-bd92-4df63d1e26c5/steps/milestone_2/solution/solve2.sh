#!/bin/bash
set -euo pipefail
python3 - <<'PY'
from pathlib import Path

path = Path("/app/crates/host-runner/src/fault_plan.rs")
path.write_text("""use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

#[derive(Clone, Debug)]
pub struct FaultPlan {
    every: usize,
    pattern: Option<Pattern>,
}

#[derive(Clone, Debug)]
struct Pattern {
    global: BTreeSet<usize>,
    fixtures: BTreeMap<String, BTreeSet<usize>>,
}

impl FaultPlan {
    pub fn transient() -> Self {
        let every = std::env::var("FAULT_EVERY")
            .ok()
            .and_then(|raw| raw.parse::<usize>().ok())
            .filter(|value| *value > 0)
            .unwrap_or(5);
        let pattern = std::env::var("FAULT_PATTERN")
            .ok()
            .and_then(|raw| parse_pattern(&raw));
        Self { every, pattern }
    }

    pub fn should_fault(&self, read_index: usize, fixture: &Path, fixture_read: usize) -> bool {
        if let Some(pattern) = &self.pattern {
            let fixture_fault = fixture
                .file_name()
                .and_then(|name| name.to_str())
                .and_then(|name| pattern.fixtures.get(name))
                .is_some_and(|reads| reads.contains(&fixture_read));
            return pattern.global.contains(&read_index) || fixture_fault;
        }
        read_index % self.every == 0
    }
}

fn parse_pattern(raw: &str) -> Option<Pattern> {
    let mut global = BTreeSet::new();
    let mut fixtures: BTreeMap<String, BTreeSet<usize>> = BTreeMap::new();
    for token in raw.split(',').map(str::trim).filter(|token| !token.is_empty()) {
        if let Some((fixture, selector)) = token.split_once('@') {
            let fixture = fixture.trim();
            if fixture.is_empty() {
                continue;
            }
            if let Some(reads) = parse_selector(selector) {
                fixtures.entry(fixture.to_string()).or_default().extend(reads);
            }
        } else if let Some(reads) = parse_selector(token) {
            global.extend(reads);
        }
    }
    if global.is_empty() && fixtures.is_empty() {
        None
    } else {
        Some(Pattern { global, fixtures })
    }
}

fn parse_selector(raw: &str) -> Option<BTreeSet<usize>> {
    let mut reads = BTreeSet::new();
    if let Some((start, end)) = raw.split_once('-') {
        let Ok(start) = start.trim().parse::<usize>() else {
            return None;
        };
        let Ok(end) = end.trim().parse::<usize>() else {
            return None;
        };
        if start > 0 && end > 0 && start <= end {
            reads.extend(start..=end);
        }
    } else if let Ok(index) = raw.trim().parse::<usize>() {
        if index > 0 {
            reads.insert(index);
        }
    }
    if reads.is_empty() {
        None
    } else {
        Some(reads)
    }
}
""")

resources = Path("/app/crates/host-runner/src/resource_table.rs")
resources.write_text("""use crate::errors::StreamError;
use crate::queue::EventQueue;
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Debug, Default)]
pub struct ResourceTable {
    next: u32,
    free: BTreeSet<u32>,
    open: BTreeMap<u32, u64>,
    generations: BTreeMap<u32, u64>,
    opened: usize,
    dropped: usize,
    queue: EventQueue,
}

impl ResourceTable {
    pub fn new() -> Self {
        Self {
            next: 1,
            free: BTreeSet::new(),
            open: BTreeMap::new(),
            generations: BTreeMap::new(),
            opened: 0,
            dropped: 0,
            queue: EventQueue::default(),
        }
    }

    pub fn open_stream(&mut self) -> u32 {
        let descriptor = if let Some(descriptor) = self.free.pop_first() {
            descriptor
        } else {
            let descriptor = self.next;
            self.next += 1;
            descriptor
        };
        let generation = self.generations.entry(descriptor).or_insert(0);
        *generation += 1;
        self.open.insert(descriptor, *generation);
        self.opened += 1;
        descriptor
    }

    pub fn close_stream(&mut self, descriptor: u32) {
        if self.open.remove(&descriptor).is_some() {
            self.dropped += 1;
            self.free.insert(descriptor);
        }
    }

    pub fn close_stream_generation(&mut self, descriptor: u32, generation: u64) {
        if self.open.get(&descriptor).copied() == Some(generation) {
            self.close_stream(descriptor);
        }
    }

    pub fn stream_generation(&self, descriptor: u32) -> Option<u64> {
        self.open.get(&descriptor).copied()
    }

    pub fn park_error(&mut self, error: StreamError) {
        self.queue.push(error);
    }

    pub fn release_after_error(&mut self, error: &StreamError) {
        let _ = self.queue.drain_error(error);
        self.close_stream_generation(error.descriptor, error.generation);
    }

    pub fn opened(&self) -> usize {
        self.opened
    }

    pub fn dropped(&self) -> usize {
        self.dropped
    }

    pub fn leaked(&self) -> usize {
        self.open.len() + self.queue.len()
    }
}
""")

queue = Path("/app/crates/host-runner/src/queue.rs")
queue.write_text("""use crate::errors::StreamError;
use std::collections::VecDeque;

#[derive(Clone, Debug, Default)]
pub struct EventQueue {
    pending: VecDeque<StreamError>,
}

impl EventQueue {
    pub fn push(&mut self, error: StreamError) {
        self.pending.push_back(error);
    }

    pub fn drain_error(&mut self, error: &StreamError) -> bool {
        let before = self.pending.len();
        self.pending.retain(|pending| {
            pending.descriptor != error.descriptor || pending.generation != error.generation
        });
        self.pending.len() != before
    }

    pub fn len(&self) -> usize {
        self.pending.len()
    }
}
""")

errors = Path("/app/crates/host-runner/src/errors.rs")
errors.write_text("""#[derive(Clone, Debug)]
pub struct StreamError {
    pub descriptor: u32,
    pub generation: u64,
    pub event: &'static str,
}

impl StreamError {
    pub fn transient_read_lag(descriptor: u32, generation: u64) -> Self {
        Self {
            descriptor,
            generation,
            event: "transient-read-lag",
        }
    }
}
""")

cleanup = Path("/app/crates/host-runner/src/cleanup.rs")
cleanup.write_text("""use crate::errors::StreamError;
use crate::resource_table::ResourceTable;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CleanupMode {
    Leaky,
    WasiErrorCleanup,
}

impl CleanupMode {
    pub fn parse(raw: &str) -> Result<Self, String> {
        match raw {
            "leaky" => Ok(Self::Leaky),
            "wasi-error-cleanup" => Ok(Self::WasiErrorCleanup),
            other => Err(format!("unknown cleanup mode {other}")),
        }
    }

    pub fn as_report_mode(self) -> &'static str {
        match self {
            Self::Leaky => "leaky",
            Self::WasiErrorCleanup => "wasi-error-cleanup",
        }
    }
}

pub fn handle_wasi_error(table: &mut ResourceTable, error: &StreamError, mode: CleanupMode) {
    if mode == CleanupMode::WasiErrorCleanup {
        table.release_after_error(error);
    }
}
""")

report = Path("/app/crates/host-runner/src/report.rs")
report.write_text(r"""use crate::cleanup::CleanupMode;
use crate::resource_table::ResourceTable;
use crate::stream_driver::RunResult;

#[derive(Clone, Debug)]
pub struct Report {
    mode: &'static str,
    run_count: usize,
    opened_descriptors: usize,
    dropped_descriptors: usize,
    leaked_descriptors: usize,
    fault_count: usize,
    output_sha256: String,
    audit_sha256: String,
    observed_events: Vec<&'static str>,
}

impl Report {
    pub fn from_run(mode: CleanupMode, table: &ResourceTable, result: RunResult) -> Self {
        Self {
            mode: mode.as_report_mode(),
            run_count: result.run_count,
            opened_descriptors: table.opened(),
            dropped_descriptors: table.dropped(),
            leaked_descriptors: table.leaked(),
            fault_count: result.fault_count,
            output_sha256: result.output_sha256,
            audit_sha256: result.audit_sha256,
            observed_events: result.observed_events,
        }
    }

    pub fn to_json(&self) -> String {
        let events = self
            .observed_events
            .iter()
            .map(|event| format!("\"{event}\""))
            .collect::<Vec<_>>()
            .join(", ");
        format!(
            "{{\n  \"mode\": \"{}\",\n  \"run_count\": {},\n  \"opened_descriptors\": {},\n  \"dropped_descriptors\": {},\n  \"leaked_descriptors\": {},\n  \"fault_count\": {},\n  \"output_sha256\": \"{}\",\n  \"audit_sha256\": \"{}\",\n  \"observed_events\": [{}]\n}}\n",
            self.mode,
            self.run_count,
            self.opened_descriptors,
            self.dropped_descriptors,
            self.leaked_descriptors,
            self.fault_count,
            self.output_sha256,
            self.audit_sha256,
            events
        )
    }
}
""")

stream_driver = Path("/app/crates/host-runner/src/stream_driver.rs")
stream_driver.write_text("""use crate::cleanup::{handle_wasi_error, CleanupMode};
use crate::errors::StreamError;
use crate::fault_plan::FaultPlan;
use crate::resource_table::ResourceTable;
use crate::telemetry::{fixture_paths, read_fixture};
use edge_worker::checksums::fnv1a_hex;
use std::collections::BTreeMap;
use std::env;
use std::path::Path;

#[derive(Clone, Debug)]
pub struct RunResult {
    pub run_count: usize,
    pub fault_count: usize,
    pub output_sha256: String,
    pub audit_sha256: String,
    pub observed_events: Vec<&'static str>,
}

pub fn run_streams(
    fixtures: &Path,
    fault_plan: &FaultPlan,
    table: &mut ResourceTable,
    mode: CleanupMode,
) -> Result<RunResult, String> {
    let paths = fixture_paths(fixtures)?;
    let mut output = Vec::new();
    let mut audit_log = String::new();
    let mut fault_count = 0usize;
    let mut observed_events = Vec::new();
    let mut read_index = 0usize;
    let mut fixture_reads: BTreeMap<String, usize> = BTreeMap::new();
    let rounds = positive_env("STREAM_ROUNDS", 16);
    let chunk_width = positive_env("PACK_CHUNK", 3);

    for _round in 0..rounds {
        for path in &paths {
            read_index += 1;
            let fixture_name = path
                .file_name()
                .and_then(|name| name.to_str())
                .ok_or_else(|| format!("invalid fixture path {}", path.display()))?
                .to_string();
            let fixture_read = fixture_reads.entry(fixture_name.clone()).or_insert(0);
            *fixture_read += 1;
            let descriptor = table.open_stream();
            let generation = table.stream_generation(descriptor).unwrap_or(0);
            match read_one(path, descriptor, read_index, *fixture_read, fault_plan, table) {
                Ok(bytes) => {
                    audit_log.push_str(&format!(
                        "{read_index}:{fixture_name}:{fixture_read}:{descriptor}:{generation}:ok\n"
                    ));
                    output.extend_from_slice(&pack_bytes_with_width(&bytes, chunk_width));
                    table.close_stream(descriptor);
                }
                Err(error) => {
                    fault_count += 1;
                    audit_log.push_str(&format!(
                        "{read_index}:{fixture_name}:{fixture_read}:{}:{}:fault\n",
                        error.descriptor, error.generation
                    ));
                    observed_events.push(error.event);
                    handle_wasi_error(table, &error, mode);
                    output.extend_from_slice(&pack_bytes_with_width(
                        &read_fixture(path)?,
                        chunk_width,
                    ));
                }
            }
        }
    }

    observed_events.sort_unstable();
    observed_events.dedup();

    Ok(RunResult {
        run_count: read_index,
        fault_count,
        output_sha256: fnv1a_hex(&output),
        audit_sha256: fnv1a_hex(audit_log.as_bytes()),
        observed_events,
    })
}

fn read_one(
    path: &Path,
    descriptor: u32,
    read_index: usize,
    fixture_read: usize,
    fault_plan: &FaultPlan,
    table: &mut ResourceTable,
) -> Result<Vec<u8>, StreamError> {
    if fault_plan.should_fault(read_index, path, fixture_read) {
        let error = transient_error(table, descriptor);
        table.park_error(error.clone());
        return Err(error);
    }
    read_fixture(path).map_err(|_| transient_error(table, descriptor))
}

fn transient_error(table: &ResourceTable, descriptor: u32) -> StreamError {
    let generation = table.stream_generation(descriptor).unwrap_or(0);
    StreamError::transient_read_lag(descriptor, generation)
}

fn positive_env(name: &str, default: usize) -> usize {
    env::var(name)
        .ok()
        .and_then(|raw| raw.parse::<usize>().ok())
        .filter(|value| *value > 0)
        .unwrap_or(default)
}

fn pack_bytes_with_width(input: &[u8], chunk_width: usize) -> Vec<u8> {
    let mut out = Vec::with_capacity(input.len());
    for chunk in input.chunks(chunk_width) {
        out.extend(chunk.iter().rev());
    }
    out
}
""")

runner = Path("/app/tools/run-faults.sh")
text = runner.read_text()
text = text.replace("/app/tools/build-component.sh >/tmp/component-build.log\n", "")
runner.write_text(text)

checksums = Path("/app/crates/edge-worker/src/checksums.rs")
checksums.write_text("""const K: [u32; 64] = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
    0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
    0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
    0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
    0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
    0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];

pub fn fnv1a_hex(bytes: &[u8]) -> String {
    let mut state = [
        0x6a09e667u32,
        0xbb67ae85,
        0x3c6ef372,
        0xa54ff53a,
        0x510e527f,
        0x9b05688c,
        0x1f83d9ab,
        0x5be0cd19,
    ];
    let bit_len = (bytes.len() as u64) * 8;
    let mut padded = Vec::with_capacity(((bytes.len() + 72) / 64) * 64);
    padded.extend_from_slice(bytes);
    padded.push(0x80);
    while padded.len() % 64 != 56 {
        padded.push(0);
    }
    padded.extend_from_slice(&bit_len.to_be_bytes());

    for chunk in padded.chunks_exact(64) {
        let mut schedule = [0u32; 64];
        for (index, word) in schedule[..16].iter_mut().enumerate() {
            let offset = index * 4;
            *word = u32::from_be_bytes([
                chunk[offset],
                chunk[offset + 1],
                chunk[offset + 2],
                chunk[offset + 3],
            ]);
        }
        for index in 16..64 {
            let s0 = schedule[index - 15].rotate_right(7)
                ^ schedule[index - 15].rotate_right(18)
                ^ (schedule[index - 15] >> 3);
            let s1 = schedule[index - 2].rotate_right(17)
                ^ schedule[index - 2].rotate_right(19)
                ^ (schedule[index - 2] >> 10);
            schedule[index] = schedule[index - 16]
                .wrapping_add(s0)
                .wrapping_add(schedule[index - 7])
                .wrapping_add(s1);
        }

        let [mut a, mut b, mut c, mut d, mut e, mut f, mut g, mut h] = state;
        for index in 0..64 {
            let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
            let ch = (e & f) ^ ((!e) & g);
            let temp1 = h
                .wrapping_add(s1)
                .wrapping_add(ch)
                .wrapping_add(K[index])
                .wrapping_add(schedule[index]);
            let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
            let maj = (a & b) ^ (a & c) ^ (b & c);
            let temp2 = s0.wrapping_add(maj);

            h = g;
            g = f;
            f = e;
            e = d.wrapping_add(temp1);
            d = c;
            c = b;
            b = a;
            a = temp1.wrapping_add(temp2);
        }

        state[0] = state[0].wrapping_add(a);
        state[1] = state[1].wrapping_add(b);
        state[2] = state[2].wrapping_add(c);
        state[3] = state[3].wrapping_add(d);
        state[4] = state[4].wrapping_add(e);
        state[5] = state[5].wrapping_add(f);
        state[6] = state[6].wrapping_add(g);
        state[7] = state[7].wrapping_add(h);
    }

    let mut out = String::with_capacity(64);
    for word in state {
        out.push_str(&format!("{word:08x}"));
    }
    out
}
""")
PY

cd /app
/app/tools/run-faults.sh
