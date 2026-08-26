#!/bin/bash
set -euo pipefail

cat > /app/src/extractor.rs <<'__EXTRACTOR_RS__'
use std::collections::BTreeMap;
use std::ffi::OsString;
use std::fs::{self, OpenOptions};
use std::io::{Cursor, Read, Write};
use std::os::unix::fs::{symlink, PermissionsExt};
use std::path::{Path, PathBuf};

use unicode_normalization::UnicodeNormalization;

const MAX_ENTRIES: u64 = 64;
const MAX_ENTRY_BYTES: u64 = 262_144;
const MAX_TOTAL_BYTES: u64 = 1_048_576;
const MAX_ARCHIVE_BYTES: u64 = 2_097_152;
const MAX_ZIP_RATIO: u64 = 32;
const MAX_NESTING: usize = 3;
const MAX_COMPONENT_BYTES: usize = 64;
const MAX_PATH_BYTES: usize = 240;
const MAX_COMPONENTS: usize = 16;

type CollisionKey = Vec<String>;

#[derive(Clone, Debug)]
struct SafePath {
    components: Vec<String>,
    key: CollisionKey,
}

impl SafePath {
    fn relative_path(&self) -> PathBuf {
        self.components.iter().collect()
    }

    fn prefix(&self, length: usize) -> Self {
        Self {
            components: self.components[..length].to_vec(),
            key: self.key[..length].to_vec(),
        }
    }
}

#[derive(Clone, Debug)]
struct LinkTarget {
    components: Vec<String>,
    key: CollisionKey,
}

#[derive(Debug)]
enum Node {
    Directory { declared: bool },
    File { data: Vec<u8>, executable: bool },
    SymbolicLink { text: String, target: LinkTarget },
    HardLink { target: LinkTarget },
}

#[derive(Debug)]
struct PlannedNode {
    path: SafePath,
    node: Node,
}

#[derive(Default)]
struct Plan {
    nodes: BTreeMap<CollisionKey, PlannedNode>,
}

impl Plan {
    fn ensure_parents(&mut self, path: &SafePath) -> Result<(), String> {
        for length in 1..path.components.len() {
            let parent = path.prefix(length);
            match self.nodes.get(&parent.key) {
                Some(existing) => {
                    require_same_spelling(existing, &parent)?;
                    if !matches!(existing.node, Node::Directory { .. }) {
                        return Err("an entry has a non-directory parent".into());
                    }
                }
                None => {
                    self.nodes.insert(
                        parent.key.clone(),
                        PlannedNode {
                            path: parent,
                            node: Node::Directory { declared: false },
                        },
                    );
                }
            }
        }
        Ok(())
    }

    fn add_directory(&mut self, path: SafePath) -> Result<(), String> {
        self.ensure_parents(&path)?;
        match self.nodes.get_mut(&path.key) {
            Some(existing) => {
                require_same_spelling(existing, &path)?;
                match &mut existing.node {
                    Node::Directory { declared } if !*declared => {
                        *declared = true;
                        Ok(())
                    }
                    Node::Directory { .. } => Err("duplicate directory entry".into()),
                    _ => Err("file and directory paths conflict".into()),
                }
            }
            None => {
                self.nodes.insert(
                    path.key.clone(),
                    PlannedNode {
                        path,
                        node: Node::Directory { declared: true },
                    },
                );
                Ok(())
            }
        }
    }

    fn add_nested_archive_root(&mut self, path: SafePath) -> Result<(), String> {
        self.ensure_parents(&path)?;
        if let Some(existing) = self.nodes.get(&path.key) {
            require_same_spelling(existing, &path)?;
            return Err("nested archive path conflicts with another entry".into());
        }
        self.nodes.insert(
            path.key.clone(),
            PlannedNode {
                path,
                node: Node::Directory { declared: true },
            },
        );
        Ok(())
    }

    fn add_file(&mut self, path: SafePath, data: Vec<u8>, executable: bool) -> Result<(), String> {
        self.add_unique(path, Node::File { data, executable })
    }

    fn add_symbolic_link(
        &mut self,
        path: SafePath,
        text: String,
        target: LinkTarget,
    ) -> Result<(), String> {
        self.add_unique(path, Node::SymbolicLink { text, target })
    }

    fn add_hard_link(&mut self, path: SafePath, target: LinkTarget) -> Result<(), String> {
        self.add_unique(path, Node::HardLink { target })
    }

    fn add_unique(&mut self, path: SafePath, node: Node) -> Result<(), String> {
        self.ensure_parents(&path)?;
        if let Some(existing) = self.nodes.get(&path.key) {
            require_same_spelling(existing, &path)?;
            return Err("duplicate or prefix-conflicting entry".into());
        }
        self.nodes
            .insert(path.key.clone(), PlannedNode { path, node });
        Ok(())
    }

    fn validate_links(&self) -> Result<(), String> {
        for planned in self.nodes.values() {
            let target = match &planned.node {
                Node::SymbolicLink { target, .. } | Node::HardLink { target } => target,
                _ => continue,
            };
            let supplied = self
                .nodes
                .get(&target.key)
                .ok_or_else(|| "link target is not supplied".to_string())?;
            if supplied.path.components != target.components {
                return Err("link target uses a colliding spelling".into());
            }
            if !matches!(supplied.node, Node::File { .. }) {
                return Err("link target is not a regular file".into());
            }
        }
        Ok(())
    }
}

fn require_same_spelling(existing: &PlannedNode, path: &SafePath) -> Result<(), String> {
    if existing.path.components == path.components {
        Ok(())
    } else {
        Err("portable Unicode path collision".into())
    }
}

#[derive(Default)]
struct Budget {
    entries: u64,
    decoded_bytes: u64,
}

impl Budget {
    fn add_entry(&mut self) -> Result<(), String> {
        self.entries = self
            .entries
            .checked_add(1)
            .ok_or_else(|| "entry count overflow".to_string())?;
        if self.entries > MAX_ENTRIES {
            return Err("archive entry limit exceeded".into());
        }
        Ok(())
    }

    fn add_payload(&mut self, size: u64, compressed: Option<u64>) -> Result<(), String> {
        if size > MAX_ENTRY_BYTES {
            return Err("single entry size limit exceeded".into());
        }
        if let Some(compressed_size) = compressed {
            if size > 0
                && (compressed_size == 0 || size > compressed_size.saturating_mul(MAX_ZIP_RATIO))
            {
                return Err("ZIP compression ratio limit exceeded".into());
            }
        }
        self.decoded_bytes = self
            .decoded_bytes
            .checked_add(size)
            .ok_or_else(|| "decoded byte count overflow".to_string())?;
        if self.decoded_bytes > MAX_TOTAL_BYTES {
            return Err("aggregate decoded byte limit exceeded".into());
        }
        Ok(())
    }
}

#[derive(Clone, Copy)]
enum ArchiveKind {
    Tar,
    Zip,
}

pub fn run(arguments: Vec<OsString>) -> Result<(), String> {
    if arguments.len() != 2 {
        return Err("usage: quarantine-extractor <archive> <destination>".into());
    }

    let input = PathBuf::from(&arguments[0]);
    let destination = PathBuf::from(&arguments[1]);
    validate_host_paths(&input, &destination)?;

    let metadata = fs::symlink_metadata(&input).map_err(|error| error.to_string())?;
    let input_size = metadata.len();
    if input_size > MAX_ARCHIVE_BYTES {
        return Err("root archive size limit exceeded".into());
    }
    let bytes = fs::read(&input).map_err(|error| error.to_string())?;
    if u64::try_from(bytes.len()).map_err(|_| "archive length overflow")? != input_size {
        return Err("archive changed while being read".into());
    }

    let mut plan = Plan::default();
    let mut budget = Budget::default();
    process_archive(&bytes, &[], 0, &mut plan, &mut budget)?;
    plan.validate_links()?;
    publish(&destination, &plan)
}

fn validate_host_paths(input: &Path, destination: &Path) -> Result<(), String> {
    if !input.is_absolute() || !destination.is_absolute() {
        return Err("archive and destination paths must be absolute".into());
    }
    let input_metadata = fs::symlink_metadata(input).map_err(|error| error.to_string())?;
    if !input_metadata.file_type().is_file() {
        return Err("archive path is not a regular file".into());
    }
    let canonical_input = fs::canonicalize(input).map_err(|error| error.to_string())?;
    if canonical_input != input {
        return Err("archive path crosses a symbolic link".into());
    }
    if fs::symlink_metadata(destination).is_ok() {
        return Err("destination already exists".into());
    }

    let parent = destination
        .parent()
        .ok_or_else(|| "destination has no parent".to_string())?;
    let parent_metadata = fs::symlink_metadata(parent).map_err(|error| error.to_string())?;
    if !parent_metadata.file_type().is_dir() {
        return Err("destination parent is not a directory".into());
    }
    let canonical_parent = fs::canonicalize(parent).map_err(|error| error.to_string())?;
    if canonical_parent != parent {
        return Err("destination parent crosses a symbolic link".into());
    }
    Ok(())
}

fn process_archive(
    bytes: &[u8],
    archive_base: &[String],
    depth: usize,
    plan: &mut Plan,
    budget: &mut Budget,
) -> Result<(), String> {
    if depth > MAX_NESTING {
        return Err("nested archive depth limit exceeded".into());
    }
    if u64::try_from(bytes.len()).map_err(|_| "archive length overflow")? > MAX_ARCHIVE_BYTES {
        return Err("archive carrier size limit exceeded".into());
    }

    match archive_kind(bytes).ok_or_else(|| "unsupported archive format".to_string())? {
        ArchiveKind::Tar => process_tar(bytes, archive_base, depth, plan, budget),
        ArchiveKind::Zip => process_zip(bytes, archive_base, depth, plan, budget),
    }
}

fn process_zip(
    bytes: &[u8],
    archive_base: &[String],
    depth: usize,
    plan: &mut Plan,
    budget: &mut Budget,
) -> Result<(), String> {
    let raw_records = validate_zip_envelope(bytes)?;
    let cursor = Cursor::new(bytes);
    let mut archive =
        zip::ZipArchive::new(cursor).map_err(|error| format!("malformed ZIP: {error}"))?;
    if archive.len() != raw_records.len() {
        return Err("ZIP central directory contains duplicate entries".into());
    }

    for index in 0..archive.len() {
        budget.add_entry()?;
        let mut entry = archive
            .by_index(index)
            .map_err(|error| format!("malformed ZIP entry: {error}"))?;
        let raw_name = std::str::from_utf8(entry.name_raw())
            .map_err(|_| "ZIP entry name is not UTF-8".to_string())?
            .to_owned();
        let raw_record = &raw_records[index];
        if entry.name_raw() != raw_record.name
            || entry.compressed_size() != u64::from(raw_record.compressed_size)
            || entry.size() != u64::from(raw_record.decoded_size)
        {
            return Err("ZIP parser disagrees with the central directory".into());
        }
        let mode = entry.unix_mode().unwrap_or(0);
        let kind = mode & 0o170000;
        let directory = entry.is_dir() || kind == 0o040000;
        let symbolic_link = kind == 0o120000;
        if directory {
            if !entry.is_dir() || !matches!(kind, 0 | 0o040000) || entry.size() != 0 {
                return Err("malformed ZIP directory entry".into());
            }
        } else if !matches!(kind, 0 | 0o100000 | 0o120000) {
            return Err("unsupported ZIP special entry".into());
        }

        let path = parse_entry_path(&raw_name, archive_base, directory)?;
        if directory {
            plan.add_directory(path)?;
            continue;
        }

        let declared_size = entry.size();
        budget.add_payload(declared_size, Some(entry.compressed_size()))?;
        let data = read_exact_payload(&mut entry, declared_size)?;
        if symbolic_link {
            let text = std::str::from_utf8(&data)
                .map_err(|_| "ZIP symbolic-link target is not UTF-8".to_string())?
                .to_owned();
            let target = resolve_link_target(
                &text,
                &path.components[..path.components.len() - 1],
                archive_base,
            )?;
            plan.add_symbolic_link(path, text, target)?;
        } else if archive_kind(&data).is_some() {
            let nested_base = path.components.clone();
            plan.add_nested_archive_root(path)?;
            process_archive(&data, &nested_base, depth + 1, plan, budget)?;
        } else {
            plan.add_file(path, data, mode & 0o111 != 0)?;
        }
    }
    Ok(())
}

fn process_tar(
    bytes: &[u8],
    archive_base: &[String],
    depth: usize,
    plan: &mut Plan,
    budget: &mut Budget,
) -> Result<(), String> {
    validate_tar_envelope(bytes)?;
    let mut archive = tar::Archive::new(Cursor::new(bytes));
    let entries = archive
        .entries()
        .map_err(|error| format!("malformed TAR: {error}"))?;

    for entry_result in entries {
        budget.add_entry()?;
        let mut entry = entry_result.map_err(|error| format!("malformed TAR entry: {error}"))?;
        let raw_path = entry.path_bytes();
        let raw_name = std::str::from_utf8(raw_path.as_ref())
            .map_err(|_| "TAR entry name is not UTF-8".to_string())?
            .to_owned();
        let entry_type = entry.header().entry_type();
        let directory = entry_type.is_dir();
        let path = parse_entry_path(&raw_name, archive_base, directory)?;

        if directory {
            plan.add_directory(path)?;
        } else if entry_type.is_file() {
            let declared_size = entry
                .header()
                .size()
                .map_err(|error| format!("invalid TAR size: {error}"))?;
            budget.add_payload(declared_size, None)?;
            let data = read_exact_payload(&mut entry, declared_size)?;
            let mode = entry
                .header()
                .mode()
                .map_err(|error| format!("invalid TAR mode: {error}"))?;
            if archive_kind(&data).is_some() {
                let nested_base = path.components.clone();
                plan.add_nested_archive_root(path)?;
                process_archive(&data, &nested_base, depth + 1, plan, budget)?;
            } else {
                plan.add_file(path, data, mode & 0o111 != 0)?;
            }
        } else if entry_type.is_symlink() || entry_type.is_hard_link() {
            let link_name = entry
                .link_name()
                .map_err(|error| format!("invalid TAR link target: {error}"))?
                .ok_or_else(|| "TAR link is missing its target".to_string())?;
            let text = link_name
                .to_str()
                .ok_or_else(|| "TAR link target is not UTF-8".to_string())?
                .to_owned();
            if entry_type.is_symlink() {
                let target = resolve_link_target(
                    &text,
                    &path.components[..path.components.len() - 1],
                    archive_base,
                )?;
                plan.add_symbolic_link(path, text, target)?;
            } else {
                let target = resolve_link_target(&text, archive_base, archive_base)?;
                plan.add_hard_link(path, target)?;
            }
        } else {
            return Err("unsupported TAR special entry".into());
        }
    }
    Ok(())
}

fn read_exact_payload(reader: &mut impl Read, size: u64) -> Result<Vec<u8>, String> {
    let capacity = usize::try_from(size).map_err(|_| "entry size does not fit memory")?;
    let limit = size
        .checked_add(1)
        .ok_or_else(|| "entry size overflow".to_string())?;
    let mut data = Vec::with_capacity(capacity);
    reader
        .take(limit)
        .read_to_end(&mut data)
        .map_err(|error| error.to_string())?;
    if u64::try_from(data.len()).map_err(|_| "decoded length overflow")? != size {
        return Err("declared and decoded entry sizes disagree".into());
    }
    Ok(data)
}

fn parse_entry_path(
    raw: &str,
    archive_base: &[String],
    directory: bool,
) -> Result<SafePath, String> {
    if raw.is_empty() || raw.starts_with('/') || raw.starts_with("//") || raw.contains('\\') {
        return Err("entry path is not relative and portable".into());
    }
    let path_text = if directory {
        raw.strip_suffix('/')
            .ok_or_else(|| "directory name lacks a trailing slash".to_string())?
    } else {
        raw
    };
    if path_text.is_empty() || path_text.ends_with('/') {
        return Err("entry path contains an empty component".into());
    }

    let mut components = archive_base.to_vec();
    for (index, component) in path_text.split('/').enumerate() {
        if component.is_empty() || matches!(component, "." | "..") {
            return Err("entry path contains an unsafe component".into());
        }
        if index == 0 && has_windows_drive_prefix(component) {
            return Err("entry path has a Windows drive prefix".into());
        }
        validate_component(component)?;
        components.push(component.to_owned());
    }
    finish_safe_path(components)
}

fn resolve_link_target(
    raw: &str,
    starting_components: &[String],
    archive_base: &[String],
) -> Result<LinkTarget, String> {
    if raw.is_empty()
        || raw.starts_with('/')
        || raw.starts_with("//")
        || raw.ends_with('/')
        || raw.contains('\\')
    {
        return Err("link target is not a relative portable path".into());
    }

    let mut components = starting_components.to_vec();
    for (index, component) in raw.split('/').enumerate() {
        if component.is_empty() {
            return Err("link target contains an empty component".into());
        }
        if index == 0 && has_windows_drive_prefix(component) {
            return Err("link target has a Windows drive prefix".into());
        }
        match component {
            "." => {}
            ".." => {
                if components.len() <= archive_base.len() {
                    return Err("link target escapes its archive layer".into());
                }
                components.pop();
            }
            _ => {
                validate_component(component)?;
                components.push(component.to_owned());
            }
        }
    }
    if components.len() <= archive_base.len() {
        return Err("link target does not name an archived file".into());
    }
    let safe = finish_safe_path(components)?;
    Ok(LinkTarget {
        components: safe.components,
        key: safe.key,
    })
}

fn finish_safe_path(components: Vec<String>) -> Result<SafePath, String> {
    if components.is_empty() || components.len() > MAX_COMPONENTS {
        return Err("entry path component limit exceeded".into());
    }
    let relative = components.join("/");
    if relative.len() > MAX_PATH_BYTES {
        return Err("entry path byte limit exceeded".into());
    }
    let key = components
        .iter()
        .map(|component| {
            component
                .nfkc()
                .flat_map(char::to_lowercase)
                .collect::<String>()
        })
        .collect();
    Ok(SafePath { components, key })
}

fn validate_component(component: &str) -> Result<(), String> {
    if component.len() > MAX_COMPONENT_BYTES
        || component.chars().any(char::is_control)
        || component.contains('\0')
    {
        return Err("entry path component is invalid".into());
    }
    let normalized = component
        .nfkc()
        .flat_map(char::to_lowercase)
        .collect::<String>();
    if normalized.is_empty() || matches!(normalized.as_str(), "." | "..") {
        return Err("entry path normalizes to an unsafe component".into());
    }
    Ok(())
}

fn has_windows_drive_prefix(component: &str) -> bool {
    let bytes = component.as_bytes();
    bytes.len() >= 2 && bytes[0].is_ascii_alphabetic() && bytes[1] == b':'
}

fn archive_kind(bytes: &[u8]) -> Option<ArchiveKind> {
    if bytes.starts_with(b"PK\x03\x04")
        || bytes.starts_with(b"PK\x05\x06")
        || bytes.starts_with(b"PK\x07\x08")
    {
        Some(ArchiveKind::Zip)
    } else if looks_like_tar(bytes) {
        Some(ArchiveKind::Tar)
    } else {
        None
    }
}

#[derive(Clone)]
struct RawZipRecord {
    name: Vec<u8>,
    flags: u16,
    method: u16,
    crc: u32,
    compressed_size: u32,
    decoded_size: u32,
    local_offset: usize,
}

fn validate_zip_envelope(bytes: &[u8]) -> Result<Vec<RawZipRecord>, String> {
    const END_RECORD_SIZE: usize = 22;
    const MAX_COMMENT_SIZE: usize = u16::MAX as usize;
    if bytes.len() < END_RECORD_SIZE {
        return Err("ZIP end record is truncated".into());
    }
    let search_start = bytes
        .len()
        .saturating_sub(END_RECORD_SIZE + MAX_COMMENT_SIZE);
    for offset in (search_start..=bytes.len().saturating_sub(END_RECORD_SIZE)).rev() {
        if bytes.get(offset..offset + 4) != Some(b"PK\x05\x06") {
            continue;
        }
        let record = &bytes[offset..offset + END_RECORD_SIZE];
        let comment_size = usize::from(u16::from_le_bytes([record[20], record[21]]));
        if offset + END_RECORD_SIZE + comment_size != bytes.len() {
            continue;
        }
        let disk = read_zip_u16(record, 4)?;
        let central_disk = read_zip_u16(record, 6)?;
        let entries_on_disk = read_zip_u16(record, 8)?;
        let total_entries = read_zip_u16(record, 10)?;
        let central_size = read_zip_u32(record, 12)?;
        let central_offset = read_zip_u32(record, 16)?;
        if disk != 0
            || central_disk != 0
            || entries_on_disk != total_entries
            || total_entries == u16::MAX
            || central_size == u32::MAX
            || central_offset == u32::MAX
        {
            return Err("multi-disk and ZIP64 archives are unsupported".into());
        }
        let central_end = usize::try_from(central_offset)
            .ok()
            .and_then(|start| {
                usize::try_from(central_size)
                    .ok()
                    .and_then(|size| start.checked_add(size))
            })
            .ok_or_else(|| "ZIP central directory offset overflow".to_string())?;
        if central_end != offset {
            return Err("ZIP central directory does not meet its end record".into());
        }

        let central_start =
            usize::try_from(central_offset).map_err(|_| "ZIP central offset does not fit memory")?;
        let mut central_cursor = central_start;
        let mut records = Vec::with_capacity(usize::from(total_entries));
        for _ in 0..total_entries {
            if bytes.get(central_cursor..central_cursor + 4) != Some(b"PK\x01\x02") {
                return Err("ZIP central directory record is missing".into());
            }
            let flags = read_zip_u16(bytes, central_cursor + 8)?;
            let method = read_zip_u16(bytes, central_cursor + 10)?;
            let crc = read_zip_u32(bytes, central_cursor + 16)?;
            let compressed_size = read_zip_u32(bytes, central_cursor + 20)?;
            let decoded_size = read_zip_u32(bytes, central_cursor + 24)?;
            let name_size = usize::from(read_zip_u16(bytes, central_cursor + 28)?);
            let extra_size = usize::from(read_zip_u16(bytes, central_cursor + 30)?);
            let comment_size = usize::from(read_zip_u16(bytes, central_cursor + 32)?);
            let start_disk = read_zip_u16(bytes, central_cursor + 34)?;
            let local_offset = read_zip_u32(bytes, central_cursor + 42)?;
            if flags & 1 != 0
                || start_disk != 0
                || compressed_size == u32::MAX
                || decoded_size == u32::MAX
                || local_offset == u32::MAX
            {
                return Err("encrypted, multi-disk, and ZIP64 records are unsupported".into());
            }
            let name_start = central_cursor
                .checked_add(46)
                .ok_or_else(|| "ZIP central name offset overflow".to_string())?;
            let name_end = name_start
                .checked_add(name_size)
                .ok_or_else(|| "ZIP central name overflow".to_string())?;
            let record_end = name_end
                .checked_add(extra_size)
                .and_then(|value| value.checked_add(comment_size))
                .ok_or_else(|| "ZIP central record overflow".to_string())?;
            if record_end > central_end {
                return Err("ZIP central record is truncated".into());
            }
            let name = bytes[name_start..name_end].to_vec();
            std::str::from_utf8(&name)
                .map_err(|_| "ZIP central name is not UTF-8".to_string())?;
            records.push(RawZipRecord {
                name,
                flags,
                method,
                crc,
                compressed_size,
                decoded_size,
                local_offset: usize::try_from(local_offset)
                    .map_err(|_| "ZIP local offset does not fit memory")?,
            });
            central_cursor = record_end;
        }
        if central_cursor != central_end {
            return Err("ZIP central directory contains unindexed bytes".into());
        }

        let mut local_records = records.clone();
        local_records.sort_by_key(|entry| entry.local_offset);
        let mut local_cursor = 0_usize;
        for raw in &local_records {
            if raw.local_offset != local_cursor {
                return Err("ZIP contains an unlisted, overlapping, or separated local record".into());
            }
            local_cursor = validate_zip_local_record(bytes, raw, central_start)?;
        }
        if local_cursor != central_start {
            return Err("ZIP contains bytes outside its indexed local records".into());
        }
        return Ok(records);
    }
    Err("ZIP end record is missing".into())
}

fn validate_zip_local_record(
    bytes: &[u8],
    central: &RawZipRecord,
    central_start: usize,
) -> Result<usize, String> {
    let offset = central.local_offset;
    if bytes.get(offset..offset + 4) != Some(b"PK\x03\x04") {
        return Err("ZIP local record is missing".into());
    }
    let flags = read_zip_u16(bytes, offset + 6)?;
    let method = read_zip_u16(bytes, offset + 8)?;
    let local_crc = read_zip_u32(bytes, offset + 14)?;
    let local_compressed = read_zip_u32(bytes, offset + 18)?;
    let local_decoded = read_zip_u32(bytes, offset + 22)?;
    let name_size = usize::from(read_zip_u16(bytes, offset + 26)?);
    let extra_size = usize::from(read_zip_u16(bytes, offset + 28)?);
    let name_start = offset
        .checked_add(30)
        .ok_or_else(|| "ZIP local name offset overflow".to_string())?;
    let name_end = name_start
        .checked_add(name_size)
        .ok_or_else(|| "ZIP local name overflow".to_string())?;
    let data_start = name_end
        .checked_add(extra_size)
        .ok_or_else(|| "ZIP local extra field overflow".to_string())?;
    let data_end = data_start
        .checked_add(
            usize::try_from(central.compressed_size)
                .map_err(|_| "ZIP compressed size does not fit memory")?,
        )
        .ok_or_else(|| "ZIP compressed payload overflow".to_string())?;
    if data_end > central_start {
        return Err("ZIP local payload overlaps the central directory".into());
    }
    if flags != central.flags
        || method != central.method
        || bytes.get(name_start..name_end) != Some(central.name.as_slice())
    {
        return Err("ZIP local and central headers disagree".into());
    }

    if flags & 0x0008 == 0 {
        if local_crc != central.crc
            || local_compressed != central.compressed_size
            || local_decoded != central.decoded_size
        {
            return Err("ZIP local and central sizes or CRC disagree".into());
        }
        return Ok(data_end);
    }
    if !matches!(local_crc, 0) && local_crc != central.crc
        || !matches!(local_compressed, 0) && local_compressed != central.compressed_size
        || !matches!(local_decoded, 0) && local_decoded != central.decoded_size
    {
        return Err("ZIP data-descriptor placeholders disagree".into());
    }

    let descriptor_offset = if bytes.get(data_end..data_end + 4) == Some(b"PK\x07\x08") {
        data_end
            .checked_add(4)
            .ok_or_else(|| "ZIP descriptor offset overflow".to_string())?
    } else {
        data_end
    };
    if read_zip_u32(bytes, descriptor_offset)? != central.crc
        || read_zip_u32(bytes, descriptor_offset + 4)? != central.compressed_size
        || read_zip_u32(bytes, descriptor_offset + 8)? != central.decoded_size
    {
        return Err("ZIP data descriptor disagrees with the central directory".into());
    }
    descriptor_offset
        .checked_add(12)
        .ok_or_else(|| "ZIP descriptor end overflow".to_string())
}

fn read_zip_u16(bytes: &[u8], offset: usize) -> Result<u16, String> {
    let field = bytes
        .get(offset..offset + 2)
        .ok_or_else(|| "truncated ZIP integer".to_string())?;
    Ok(u16::from_le_bytes([field[0], field[1]]))
}

fn read_zip_u32(bytes: &[u8], offset: usize) -> Result<u32, String> {
    let field = bytes
        .get(offset..offset + 4)
        .ok_or_else(|| "truncated ZIP integer".to_string())?;
    Ok(u32::from_le_bytes([field[0], field[1], field[2], field[3]]))
}

fn looks_like_tar(bytes: &[u8]) -> bool {
    let Some(header) = bytes.get(..512) else {
        return false;
    };
    if &header[257..262] != b"ustar" {
        return false;
    }
    let Ok(stored) = parse_tar_number(&header[148..156]) else {
        return false;
    };
    let sum = header
        .iter()
        .enumerate()
        .map(|(index, byte)| {
            if (148..156).contains(&index) {
                u64::from(b' ')
            } else {
                u64::from(*byte)
            }
        })
        .sum::<u64>();
    stored == sum
}

fn validate_tar_envelope(bytes: &[u8]) -> Result<(), String> {
    let mut offset = 0_usize;
    while offset
        .checked_add(512)
        .is_some_and(|header_end| header_end <= bytes.len())
    {
        let header = &bytes[offset..offset + 512];
        if header.iter().all(|byte| *byte == 0) {
            let second_end = offset
                .checked_add(1024)
                .ok_or_else(|| "TAR end marker overflow".to_string())?;
            let second = bytes
                .get(offset + 512..second_end)
                .ok_or_else(|| "TAR lacks its second end-marker block".to_string())?;
            if second.iter().any(|byte| *byte != 0) {
                return Err("TAR has only one zero end-marker block".into());
            }
            if bytes[second_end..].iter().any(|byte| *byte != 0) {
                return Err("TAR contains a payload after its end marker".into());
            }
            return Ok(());
        }
        let entry_type = header[156];
        if entry_type == b'S' {
            return Err("GNU sparse TAR entries are rejected".into());
        }
        let size = parse_tar_number(&header[124..136])?;
        let data_start = offset
            .checked_add(512)
            .ok_or_else(|| "TAR offset overflow".to_string())?;
        let size_usize = usize::try_from(size).map_err(|_| "TAR size does not fit memory")?;
        let data_end = data_start
            .checked_add(size_usize)
            .ok_or_else(|| "TAR data offset overflow".to_string())?;
        if data_end > bytes.len() {
            return Err("truncated TAR entry".into());
        }
        if matches!(entry_type, b'x' | b'g')
            && bytes[data_start..data_end]
                .windows(b"GNU.sparse".len())
                .any(|window| window == b"GNU.sparse")
        {
            return Err("PAX sparse TAR metadata is rejected".into());
        }
        let padded = size
            .checked_add(511)
            .ok_or_else(|| "TAR padding overflow".to_string())?
            / 512
            * 512;
        offset = data_start
            .checked_add(usize::try_from(padded).map_err(|_| "TAR offset does not fit memory")?)
            .ok_or_else(|| "TAR offset overflow".to_string())?;
    }
    Err("TAR lacks a complete end marker".into())
}

fn parse_tar_number(field: &[u8]) -> Result<u64, String> {
    if field.is_empty() {
        return Err("empty TAR number".into());
    }
    if field[0] & 0x80 != 0 {
        if field[0] & 0x40 != 0 {
            return Err("negative TAR number".into());
        }
        let mut value = u64::from(field[0] & 0x3f);
        for byte in &field[1..] {
            value = value
                .checked_mul(256)
                .and_then(|current| current.checked_add(u64::from(*byte)))
                .ok_or_else(|| "TAR number overflow".to_string())?;
        }
        return Ok(value);
    }

    let text = field
        .iter()
        .copied()
        .skip_while(|byte| matches!(byte, b' ' | 0))
        .take_while(|byte| !matches!(byte, b' ' | 0))
        .collect::<Vec<_>>();
    if text.is_empty() {
        return Ok(0);
    }
    let digits = std::str::from_utf8(&text).map_err(|_| "invalid TAR number")?;
    u64::from_str_radix(digits, 8).map_err(|_| "invalid TAR number".into())
}

fn publish(destination: &Path, plan: &Plan) -> Result<(), String> {
    let parent = destination
        .parent()
        .ok_or_else(|| "destination has no parent".to_string())?;
    let name = destination
        .file_name()
        .ok_or_else(|| "destination has no final component".to_string())?
        .to_string_lossy();

    let mut staging = None;
    for attempt in 0..32 {
        let candidate = parent.join(format!(
            ".{name}.quarantine-{}-{attempt}",
            std::process::id()
        ));
        match fs::create_dir(&candidate) {
            Ok(()) => {
                staging = Some(candidate);
                break;
            }
            Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => {}
            Err(error) => return Err(format!("cannot create quarantine staging: {error}")),
        }
    }
    let staging = staging.ok_or_else(|| "no private staging name is available".to_string())?;

    let result = materialize(&staging, plan).and_then(|()| {
        if fs::symlink_metadata(destination).is_ok() {
            return Err("destination appeared during extraction".into());
        }
        fs::rename(&staging, destination).map_err(|error| error.to_string())
    });
    if result.is_err() {
        let _ = fs::remove_dir_all(&staging);
    }
    result
}

fn materialize(staging: &Path, plan: &Plan) -> Result<(), String> {
    fs::set_permissions(staging, fs::Permissions::from_mode(0o755))
        .map_err(|error| error.to_string())?;

    for planned in plan.nodes.values() {
        if matches!(planned.node, Node::Directory { .. }) {
            let output = staging.join(planned.path.relative_path());
            fs::create_dir(&output).map_err(|error| error.to_string())?;
            fs::set_permissions(&output, fs::Permissions::from_mode(0o755))
                .map_err(|error| error.to_string())?;
        }
    }
    for planned in plan.nodes.values() {
        if let Node::File { data, executable } = &planned.node {
            let output = staging.join(planned.path.relative_path());
            let mut file = OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(&output)
                .map_err(|error| error.to_string())?;
            file.write_all(data).map_err(|error| error.to_string())?;
            let mode = if *executable { 0o755 } else { 0o644 };
            file.set_permissions(fs::Permissions::from_mode(mode))
                .map_err(|error| error.to_string())?;
        }
    }
    for planned in plan.nodes.values() {
        if let Node::HardLink { target } = &planned.node {
            let source = staging.join(target.components.iter().collect::<PathBuf>());
            let output = staging.join(planned.path.relative_path());
            fs::hard_link(source, output).map_err(|error| error.to_string())?;
        }
    }
    for planned in plan.nodes.values() {
        if let Node::SymbolicLink { text, .. } = &planned.node {
            let output = staging.join(planned.path.relative_path());
            symlink(text, output).map_err(|error| error.to_string())?;
        }
    }
    Ok(())
}
__EXTRACTOR_RS__

cd /app
cargo test --locked --offline
cargo build --locked --offline
