# Allowed libraries

Use the Rust standard library only. No external crate may be added; anything the
computation needs is written by hand. The environment has no network and vendors
no package, so a program that depends on an external crate cannot be built here
and produces no answer. The computation must also do its own work rather than
hand it to a separate program.
