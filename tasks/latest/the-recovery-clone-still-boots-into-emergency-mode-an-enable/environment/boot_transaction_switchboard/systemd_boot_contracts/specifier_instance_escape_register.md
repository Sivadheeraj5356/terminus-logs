# Specifier and Instance Escape Register

Clause namespace: `SPECIFIER-*`

## SPECIFIER-1 Admissible directives

Specifiers expand only in directives that admit them: `Description` is not globally substituted in this closed model. Admissible contexts include `Requires`, `Wants`, `Requisite`, `BindsTo`, `PartOf`, `Conflicts`, `Before`, `After`, `What`, `Where`, `Environment`, and `SyslogIdentifier` when present. Arbitrary text fields outside the admissible set remain literal.

## SPECIFIER-2 Specifier set

| Specifier | Meaning |
|---|---|
| `%%` | literal `%` |
| `%n` | full escaped unit name |
| `%N` | unescaped unit name |
| `%p` | prefix before `@` (escaped) |
| `%P` | prefix unescaped |
| `%i` | instance (escaped) |
| `%I` | instance (unescaped) |
| `%j` | final dash component of prefix (escaped) |
| `%J` | final dash component unescaped |
| `%f` | unescaped instance as absolute path (`/` + unescaped with `-`→`/`, root special-cased) |
| `%H` | hostname from `runtime.facts` |
| `%m` | machine_id from `runtime.facts` |
| `%b` | boot_id from `runtime.facts` |

Unknown percent sequences in admissible directives are errors. Do not expand percent sequences inside non-admissible fields.

## SPECIFIER-3 Escaping law

Unit-name escaping follows the closed reversible map: `/` → `-`, and bytes outside `[0-9A-Za-z:_.\\-]` use `\xNN` form. Root path maps to unit stem `-` for mounts (`-.mount`). Trailing slashes after normalization are rejected. Invalid UTF-8 in unescaped forms is rejected.

## SPECIFIER-4 Instance preservation

When a template fragment serves an instance, `%i`/`%I`/`%f` use the requested instance, not an empty string. Escaped and unescaped forms must remain distinct: an instance `foo-bar` unescaped is `foo-bar`; escaped form applies the escape law to that string when required by the specifier.

## SPECIFIER-5 Neutral example

For unit `app@data-1.service` loaded from `app@.service` with `SyslogIdentifier=%p_%i`:

- `%p` → `app`
- `%i` → `data-1` (escaped instance string)
- result → `app_data-1`

## SPECIFIER-6 Omissions

This register omits `%c`, `%t`, `%E`, cred store specifiers, and specifier expansion inside `ExecStart` command lines, because this model does not launch processes.
