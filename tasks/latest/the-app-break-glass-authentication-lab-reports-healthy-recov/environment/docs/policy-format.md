# Policy language

Each source file defines one stack:

```text
stack <name>
module <module-name> <return-code>=<action> ... default=<action>
substack <stack-name> <return-code>=<action> ... default=<action>
end
```

Return codes used by the lab are `success`, `auth_err`, `ignore`, `maxtries`, `user_unknown`, and `session_err`. Actions are `ignore`, `bad`, `die`, `ok`, `done`, `reset`, `continue`, or a non-negative numeric jump.

`continue` means that the current result contributes no success or failure and evaluation advances to the next entry. A numeric action skips that many following entries. A substack is evaluated as an isolated stack; its final return code is then folded by the control map on the parent entry, and a parent jump counts the entire substack as one entry.

Source files live in `/app/policy`. `/app/scripts/regenerate-policy.sh` compiles them into `/app/runtime/pam.d`, which is the runtime format read by `authctl`.
