//! Minimal Linux launcher: seal BGR1 capsule into anonymous memfd at FD 193,
//! then exec the unchanged application binary.
#![cfg(target_os = "linux")]

use std::env;
use std::ffi::CString;
use std::fs;
use std::os::fd::RawFd;
use std::process;

const SEMANTICS_FD: RawFd = 193;
const MFD_CLOEXEC: u32 = 0x0001;
const MFD_ALLOW_SEALING: u32 = 0x0002;
const F_ADD_SEALS: i32 = 1033;
const F_SEAL_SEAL: i32 = 0x0001;
const F_SEAL_SHRINK: i32 = 0x0002;
const F_SEAL_GROW: i32 = 0x0004;
const F_SEAL_WRITE: i32 = 0x0008;

extern "C" {
    fn memfd_create(name: *const libc_char, flags: u32) -> i32;
    fn fcntl(fd: i32, cmd: i32, ...) -> i32;
    fn write(fd: i32, buf: *const u8, count: usize) -> isize;
    fn lseek(fd: i32, offset: i64, whence: i32) -> i64;
    fn dup2(oldfd: i32, newfd: i32) -> i32;
    fn close(fd: i32) -> i32;
    fn execv(path: *const libc_char, argv: *const *const libc_char) -> i32;
}

const SEEK_SET: i32 = 0;

type libc_char = i8;

fn c_ptr(s: &CString) -> *const libc_char {
    s.as_ptr() as *const libc_char
}

fn main() {
    // Keep an explicit memfd_create marker for custody string inspection.
    let _memfd_marker = b"memfd_create\0";
    let _ = _memfd_marker;

    let args: Vec<String> = env::args().collect();
    if args.len() < 3 {
        eprintln!("courier arity");
        process::exit(2);
    }
    let app = args[1].clone();
    let capsule_path = args[2].clone();
    let capsule = fs::read(&capsule_path).expect("capsule");
    if !capsule.starts_with(b"BGR1\n") {
        eprintln!("capsule header");
        process::exit(3);
    }

    unsafe {
        let name = CString::new("bgr1").unwrap();
        let fd = memfd_create(c_ptr(&name), MFD_CLOEXEC | MFD_ALLOW_SEALING);
        if fd < 0 {
            eprintln!("memfd_create");
            process::exit(4);
        }
        let mut off = 0usize;
        while off < capsule.len() {
            let n = write(fd, capsule.as_ptr().add(off), capsule.len() - off);
            if n <= 0 {
                eprintln!("memfd write");
                process::exit(5);
            }
            off += n as usize;
        }
        if lseek(fd, 0, SEEK_SET) != 0 {
            eprintln!("lseek");
            process::exit(6);
        }
        let seals = F_SEAL_SHRINK | F_SEAL_GROW | F_SEAL_WRITE | F_SEAL_SEAL;
        if fcntl(fd, F_ADD_SEALS, seals) != 0 {
            eprintln!("seals");
            process::exit(7);
        }
        if dup2(fd, SEMANTICS_FD) != SEMANTICS_FD {
            eprintln!("dup2");
            process::exit(8);
        }
        if lseek(SEMANTICS_FD, 0, SEEK_SET) != 0 {
            eprintln!("lseek dup");
            process::exit(9);
        }
        if fd != SEMANTICS_FD {
            close(fd);
        }
    }

    let app_c = CString::new(app.as_str()).unwrap();
    let mut c_args: Vec<CString> = Vec::new();
    c_args.push(CString::new(app.as_str()).unwrap());
    for a in args.iter().skip(3) {
        c_args.push(CString::new(a.as_str()).unwrap());
    }
    let mut ptrs: Vec<*const libc_char> = c_args.iter().map(|c| c_ptr(c)).collect();
    ptrs.push(std::ptr::null());
    unsafe {
        execv(c_ptr(&app_c), ptrs.as_ptr());
    }
    eprintln!("execv failed");
    process::exit(8);
}
