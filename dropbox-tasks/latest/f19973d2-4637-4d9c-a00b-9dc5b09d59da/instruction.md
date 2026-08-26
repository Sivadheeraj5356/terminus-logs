Our release builders need an offline lock resolver for registries whose releases can expose several ABI-tagged capabilities. Build it as a Rust native executable so the same resolver can be rerun for different targets and policy profiles.

Create /opt/linkseal/src/main.rs and compile /opt/linkseal/bin/linkseal as an ELF binary. The command is:

    linkseal --input DIR --output FILE

DIR contains policy.cfg, roots.req, and registry/*.pkg. The complete file grammar, release validation, duplicate precedence, conditional requirements, feasibility rules, accounting, and final-plan ranking are in /opt/linkseal/registry-format.md; that file is part of this contract.

Write the canonical lock to FILE, creating its parent directory. Output is exact-match graded. A feasible result starts with TOTAL, followed by one LOCK line per selected release in bytewise package-name order. If no complete plan is feasible, write exactly UNSAT and a newline. Non-empty output must end with one newline and contain no blank or diagnostic lines. Decimal fields have no leading zeroes except the number zero; enum strings are lowercase.

The resolver must derive every run from the supplied directory. It must not modify any input file, access the network, launch any helper process, or hardcode the public registry.
