# Compose Deployment Security Standard v4.0

_Edition date: 2026-04-14_

This document is the fourth edition of the Compose Deployment Security Standard
(CDSS). It specifies obligations for a compose-based deployment repository at
release-gate time. The document is normative in the sections marked as such and
declaratory in the sections marked as such; declaratory sections describe how the
substantive sections are to be applied and do not themselves create obligations.

Nothing in this document constitutes an obligation on any deployment except through the
mechanism of a conforming release gate that applies this document to the deployment's
repository, compose files, database evidence, and signed release tag. A release gate
that departs from the evaluation procedure this document describes has not applied this
standard.

A release gate does not create containers, does not invoke any container-runtime
daemon, and does not reach any external service to evaluate a request. Evaluation is
static: the release gate reads the compose files at the repository root, reads the
repository state, reads the approvals database, and reads the tag's signature evidence,
and emits a decision. A release gate that departs from this static-evaluation posture
has not applied this document.

## Table of Contents

- Chapter 1. Scope, zones, tier derivation
- Chapter 2. Interpretive framework
- Chapter 3. Definitions
- Chapter 4. Configuration-time obligations
- Chapter 5. Service enumeration
- Chapter 6. Metadata
- Chapter 7. Resource declarations (reserved)
- Chapter 8. Privileged containers
- Chapter 9. Capability management
- Chapter 10. Image references
- Chapter 11. Secret material
- Chapter 12. Filesystem writability
- Chapter 13. Network isolation
- Chapter 14. Bind mounts
- Chapter 15. Exception windows
- Chapter 16. Logging and lifecycle (reserved)
- Chapter 17. Revocation semantics
- Chapter 18. Supply-chain authorities (reserved)
- Chapter 22. Repository hooks
- Chapter 24. Compose model assembly
- Chapter 32. Response shape
- Appendix A. Amendments
- Appendix B. Non-waivable clauses
- Appendix C. Capability allowlist
- Appendix D. Zone declaration table (reproduced)
- Appendix E. Interpretation notes

## Chapter 1. Scope, zones, tier derivation

This chapter states the boundary of the release gate's evaluation and the
declarative primitives that other chapters build on. Its provisions apply everywhere
those primitives are referenced.

### §1.1 Scope

This document applies to Docker-Compose-based deployments whose promotion is
gated by a conforming release gate. Deployments outside the scope of Docker Compose
are outside the scope of this document. The document does not itself constrain the
runtime behavior of any container; it constrains the compose-model shape and the
repository evidence at release time only.

The obligation stated above operates on the resolved compose model. It applies to
every service in the enumeration produced by the merge described elsewhere in this
document; the evaluation does not distinguish between services declared in one file and
services declared only in another.

The predicate stated above is defined solely in terms of the compose model as
resolved. It does not inspect runtime state, container properties, or registry metadata.
A release gate that evaluates the predicate by any means other than inspection of the
resolved compose model is nonconformant with this standard.

When a release gate denies a release on the basis of this clause, the response
carries a reason whose `code` and `clauseId` fields identify the clause and whose
`service` field names the offending service.

### §1.2 Port zones

The following table defines the port zones referenced elsewhere in this
document. A host-side port that appears in a zone's port list, or that falls within
one of the zone's port ranges, is considered to be in that zone. Zones do not overlap:
each host-side port belongs to at most one zone. Host-side ports that do not appear in
any zone are unzoned; unzoned ports are not consulted by any clause of this document.

| Zone | Host-side ports |
| --- | --- |
| `web` | 80, 443, 6379, 8080, 8443, 8444, 8445, 8446, 8000–8999 inclusive |
| `internal` | 9000–9999 inclusive |
| `loopback` | 7000–7999 inclusive |

The predicate stated above is defined solely in terms of the compose model as
resolved. It does not inspect runtime state, container properties, or registry metadata.
A release gate that evaluates the predicate by any means other than inspection of the
resolved compose model is nonconformant with this standard.

When a release gate denies a release on the basis of this clause, the response
carries a reason whose `code` and `clauseId` fields identify the clause and whose
`service` field names the offending service.

Evaluation of this clause is performed independently for each service in the
enumerated model. A service that violates the clause emits exactly one reason for it,
regardless of how many distinct violation surfaces the service presents.

### §1.3 Zone derivation supersedes label derivation

A service's tier may be derived from its declared `cdss.tier` label or from the
zones of its published host-side ports. Where these two derivations produce different
tier values for the same service, the port-zone derivation governs and the label-derived
tier is discarded for that service. A release gate that consults the label alone, and
does not check the port-zone derivation, has not applied §1.3 and is nonconformant.

When a release gate denies a release on the basis of this clause, the response
carries a reason whose `code` and `clauseId` fields identify the clause and whose
`service` field names the offending service.

Evaluation of this clause is performed independently for each service in the
enumerated model. A service that violates the clause emits exactly one reason for it,
regardless of how many distinct violation surfaces the service presents.

Nothing in this clause overrides the general precedence rule of this document.
Where an amendment supersedes the clause, the amended text governs for the service
class the amendment addresses; the underlying clause continues to govern for all other
service classes.

A brief note on scoping: applicability of this clause resolves against
service-class predicates that live elsewhere in the definitions chapter and elsewhere
in the approvals database. Service names are not authoritative for classification.

## Chapter 2. Interpretive framework

This chapter establishes how conflicts between provisions of this document
are resolved. Its effect is mediated entirely through the substantive chapters that
follow.

### §2.1 Precedence order

Where two provisions of this document appear to conflict, the precedence order
is `amendments > chapters > definitions notes`. A subsequently-enacted amendment prevails over a chapter clause
that appears to state a different rule for the same predicate; a chapter clause
prevails over an interpretive note that appears to state a different rule.

The precedence rule is exhaustive within its scope. Where a provision purports to
modify this precedence order, that provision is nonconformant and is not
enforceable.

Evaluation of this clause is performed independently for each service in the
enumerated model. A service that violates the clause emits exactly one reason for it,
regardless of how many distinct violation surfaces the service presents.

Nothing in this clause overrides the general precedence rule of this document.
Where an amendment supersedes the clause, the amended text governs for the service
class the amendment addresses; the underlying clause continues to govern for all other
service classes.

A brief note on scoping: applicability of this clause resolves against
service-class predicates that live elsewhere in the definitions chapter and elsewhere
in the approvals database. Service names are not authoritative for classification.

A well-formed evaluation reports each service exactly once. Duplicate service
declarations across files are reconciled by the merge procedure and produce a single
service in the evaluated model.

### §2.2 Effect of a superseded clause

A clause that is superseded retains its clause identifier and its reason code
in the response shape. The reason code emitted in a denial reads as the clause's
reason code, not as the superseding provision's identifier. This convention supports
downstream tooling that consumes historical response records.

A superseded clause may continue to apply to service classes outside the scope of the
superseding provision. A supersession that narrows a clause to fewer service classes
does not thereby abrogate the clause for the classes still within scope; a supersession
that widens a clause continues to enforce the widened rule under the original
identifier.

Nothing in this clause overrides the general precedence rule of this document.
Where an amendment supersedes the clause, the amended text governs for the service
class the amendment addresses; the underlying clause continues to govern for all other
service classes.

A brief note on scoping: applicability of this clause resolves against
service-class predicates that live elsewhere in the definitions chapter and elsewhere
in the approvals database. Service names are not authoritative for classification.

A well-formed evaluation reports each service exactly once. Duplicate service
declarations across files are reconciled by the merge procedure and produce a single
service in the evaluated model.

## Chapter 3. Definitions

The definitions collected here are terms of art within this document. Where a
term is also used in the wider community with a related meaning, the definition here
governs.

### §3.4 Web-tier service

A service is web-tier if either (a) it declares label `cdss.tier=web`, or (b) it publishes any host-side port that appears in the web zone port table of §1.2. Where these two derivations conflict — that is, a service declares a non-web `cdss.tier` label but publishes a host-side port in the web zone — the port-derived classification governs, per §1.3.

Nothing in this section constitutes an obligation on any deployment. The section is
provided as guidance and as a shared vocabulary for downstream tooling. A deployment
that does not follow the guidance in this section is not thereby nonconformant with
this standard.

### §3.5 Cache-class service

A service is cache-class if and only if it declares the label `cdss.class=cache`.

The provisions of this section are stated at the level of the compose model rather
than at the level of any container runtime. A release gate is not required to consult
external systems to apply this section.

### §3.7 Infrastructure-tier service

A service is infra-tier if and only if it declares label `cdss.tier=infra` AND its service name is present in the `infra_registry` table of the approvals database. Either condition alone is insufficient.

Where this section speaks of the "resolved" value of a service attribute, it refers
to the value produced by the merge procedure applied to the participating files. A
release gate that considers only one participating file has not resolved the service
attribute for the purposes of this section.

A brief note on scoping: applicability of this clause resolves against
service-class predicates that live elsewhere in the definitions chapter and elsewhere
in the approvals database. Service names are not authoritative for classification.

A well-formed evaluation reports each service exactly once. Duplicate service
declarations across files are reconciled by the merge procedure and produce a single
service in the evaluated model.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

### §3.9 Related but non-authoritative terms

The following terms are sometimes used in adjacent documents but are not
authoritative in this document. A release gate MUST NOT rely on any of them as
definitional; the release gate MUST resolve service-class membership through the
definitions above.

- "frontend service" — not defined here.
- "database service" — not defined here.
- "sidecar" — not defined here.
- "worker" — not defined here.
- "gateway" — not defined here.

A well-formed evaluation reports each service exactly once. Duplicate service
declarations across files are reconciled by the merge procedure and produce a single
service in the evaluated model.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

## Chapter 4. Configuration-time obligations

This chapter introduces obligations that can be evaluated statically over the
resolved compose model. The substantive clauses of Chapters 8 through 14 elaborate the
individual obligations; this chapter states the framework that unifies them.

### §4.2 Naming hygiene

Service names SHOULD (but are not required to) be lowercase alphanumeric with
optional hyphens, and SHOULD (but are not required to) be no longer than 32 characters.
A release gate MUST NOT deny a release solely on the basis of a service name that fails
this recommendation; the guidance is provided for legibility only. This clause is
non-normative.

Nothing in this section authorizes a release gate to modify the repository, the
approvals database, or any file the request references. The release gate is purely a
reader; any implementation that writes to these inputs has departed from this
document.

The applicability tests stated elsewhere in this document produce Boolean values
per (service, clause) pair. A release gate that produces multi-valued applicability
results — for example, "partially applies" — has misinterpreted this document. All
applicability results are Boolean.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

### §4.3 Comment style

Compose files SHOULD document their non-trivial services with a comment above the
service declaration explaining the service's purpose. Failure to do so is not a basis
for denial. This clause is non-normative.

Downstream tooling may cache a release gate's decisions but MUST NOT rely on
cached decisions across requests whose relevant inputs differ. The release gate
itself does not implement a decision cache in this edition.

A release gate's evaluation is deterministic given fixed inputs. Repeated
requests with byte-identical repository state, DB state, tag evidence, and request
body MUST yield byte-identical response bodies. Sources of non-determinism (random
sort orders, iteration-order variance) are nonconformant.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

### §4.7 File casing

The two files participating in the merge (see the compose model assembly chapter)
have exact case-sensitive names. A repository whose base file is named `Docker-Compose.yml`
does not present a base file to this edition of the release gate. The release gate
does not perform case-insensitive filename lookup.

Where this section speaks of the "resolved" value of a service attribute, it refers
to the value produced by the merge procedure applied to the participating files. A
release gate that considers only one participating file has not resolved the service
attribute for the purposes of this section.

A release gate MAY emit a warning where guidance in this section is not followed
even though nonconformance is not established; the warning is not part of the reasons
array in the denial response. The precise form of warnings is left to the release gate
implementation and is not constrained by this standard.

When a release gate denies a release on the basis of this clause, the response
carries a reason whose `code` and `clauseId` fields identify the clause and whose
`service` field names the offending service.

Evaluation of this clause is performed independently for each service in the
enumerated model. A service that violates the clause emits exactly one reason for it,
regardless of how many distinct violation surfaces the service presents.

Nothing in this clause overrides the general precedence rule of this document.
Where an amendment supersedes the clause, the amended text governs for the service
class the amendment addresses; the underlying clause continues to govern for all other
service classes.

A brief note on scoping: applicability of this clause resolves against
service-class predicates that live elsewhere in the definitions chapter and elsewhere
in the approvals database. Service names are not authoritative for classification.

## Chapter 5. Service enumeration

A well-formed evaluation reports each service exactly once. The merge procedure
of Chapter 24 is responsible for reconciling declarations that name the same service in
multiple files. A release gate that reports the same service twice, or that skips a
service present in either participating file, has not enumerated services correctly.

### §5.1 Ordering

Services within a compose file MAY appear in any order. The release gate MUST NOT
consider textual order as a determinant of behavior. This clause is declaratory.

The compose model as resolved is a data structure with a finite number of shapes.
This document does not enumerate the shapes; it enumerates predicates over the shapes,
and a release gate is expected to accommodate any shape the merge procedure can
produce. Shapes that are pathological (recursive anchors resolved to themselves,
unbounded string lengths, and so on) are outside the scope of this document and are
signaled as request errors, not as denials.

Guidance in this section does not extend to any obligation stated normatively
elsewhere. Where a subsequent chapter's clause reaches an obligation similar to this
section's guidance, the clause governs and the guidance loses independent effect.

A brief note on scoping: applicability of this clause resolves against
service-class predicates that live elsewhere in the definitions chapter and elsewhere
in the approvals database. Service names are not authoritative for classification.

A well-formed evaluation reports each service exactly once. Duplicate service
declarations across files are reconciled by the merge procedure and produce a single
service in the evaluated model.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

### §5.4 Depends-on hygiene

The `depends_on` attribute expresses ordering intent and is honored by
container-orchestration runtimes. The release gate does not evaluate `depends_on` in
this edition; a service that names a nonexistent target in `depends_on` does not
thereby violate any clause of this edition. This clause is declaratory.

The provisions of this section are stated at the level of the compose model rather
than at the level of any container runtime. A release gate is not required to consult
external systems to apply this section.

Where this section speaks of the "resolved" value of a service attribute, it refers
to the value produced by the merge procedure applied to the participating files. A
release gate that considers only one participating file has not resolved the service
attribute for the purposes of this section.

The predicate stated above is defined solely in terms of the compose model as
resolved. It does not inspect runtime state, container properties, or registry metadata.
A release gate that evaluates the predicate by any means other than inspection of the
resolved compose model is nonconformant with this standard.

When a release gate denies a release on the basis of this clause, the response
carries a reason whose `code` and `clauseId` fields identify the clause and whose
`service` field names the offending service.

Evaluation of this clause is performed independently for each service in the
enumerated model. A service that violates the clause emits exactly one reason for it,
regardless of how many distinct violation surfaces the service presents.

Nothing in this clause overrides the general precedence rule of this document.
Where an amendment supersedes the clause, the amended text governs for the service
class the amendment addresses; the underlying clause continues to govern for all other
service classes.

### §5.9 Anchor scoping

YAML anchors defined in one file are not visible from another file. Each file is
resolved independently before the merge procedure inspects it; anchor identity is not
preserved across files. A release gate that carries anchor state across files has not
followed this document.

A release gate MAY emit a warning where guidance in this section is not followed
even though nonconformance is not established; the warning is not part of the reasons
array in the denial response. The precise form of warnings is left to the release gate
implementation and is not constrained by this standard.

The distinction between an obligation and guidance under this standard is
morphological in the surrounding prose. Obligations use the modal verb `MUST`, its
negation `MUST NOT`, or the imperative form. Guidance uses `SHOULD`, `SHOULD NOT`, or
`MAY`. A reader who is uncertain which modality applies is directed to the surrounding
sentence, which will resolve the modality in every substantive clause of this
document.

Evaluation of this clause is performed independently for each service in the
enumerated model. A service that violates the clause emits exactly one reason for it,
regardless of how many distinct violation surfaces the service presents.

Nothing in this clause overrides the general precedence rule of this document.
Where an amendment supersedes the clause, the amended text governs for the service
class the amendment addresses; the underlying clause continues to govern for all other
service classes.

A brief note on scoping: applicability of this clause resolves against
service-class predicates that live elsewhere in the definitions chapter and elsewhere
in the approvals database. Service names are not authoritative for classification.

A well-formed evaluation reports each service exactly once. Duplicate service
declarations across files are reconciled by the merge procedure and produce a single
service in the evaluated model.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

A release gate MAY implement this clause in any order relative to other clauses,
provided the output for every request is identical to the output an implementation
following this document's stated ordering would produce.

## Chapter 6. Metadata

This chapter treats declarative metadata that services may carry. Metadata
attributes describe or classify a service without directly bearing on its runtime
behavior. Some clauses in this document consult specific labels; this chapter states
the general framework.

### §6.5 Label enumeration

Labels beginning with the reserved prefix `cdss.` are used by this standard where
defined; labels beginning with `x-` are reserved for user extensions. A release gate
MUST NOT consider `x-` labels in evaluating any clause. Labels not matching either
prefix are permitted but are not consulted by any clause of this edition.

A release gate that emits reasons whose codes do not appear in this document is
nonconformant. The set of reason codes is closed by the edition of this document the
release gate ships; extending the set is a matter for future editions, not for
release-gate implementations.

Nothing in this section authorizes a release gate to modify the repository, the
approvals database, or any file the request references. The release gate is purely a
reader; any implementation that writes to these inputs has departed from this
document.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

### §6.9 Label form

Labels MAY be declared either in map form (`labels: {key: value}`) or in list form
(`labels: ["key=value"]`). A release gate normalizes both forms to the map form before
consulting any label. A key that appears in both forms in the same service resolves to
the value paired with the map-form key; the list-form key is discarded.

A release gate that emits reasons whose codes do not appear in this document is
nonconformant. The set of reason codes is closed by the edition of this document the
release gate ships; extending the set is a matter for future editions, not for
release-gate implementations.

Nothing in this section authorizes a release gate to modify the repository, the
approvals database, or any file the request references. The release gate is purely a
reader; any implementation that writes to these inputs has departed from this
document.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

A release gate MAY implement this clause in any order relative to other clauses,
provided the output for every request is identical to the output an implementation
following this document's stated ordering would produce.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

## Chapter 7. Resource declarations (reserved)

This chapter is reserved for future editions concerning declarative resource
budgets. Its provisions are advisory in this edition; the substantive constraints on
resource declaration are deferred to future editions and are not evaluated by the
release gate. Nothing in this chapter is a basis for denial under this edition.

The reservation of a chapter for future obligations is a stability guarantee. A
future edition that adds substantive obligations under Chapter 7 will do so under the
identifier already recorded in this edition's table of contents, preserving the
chapter number and the general subject matter. Downstream tooling that anticipates a
future edition may safely reserve the same identifier for its own tracking without
risk that this edition will change the reservation.

The particular attributes contemplated for future obligations under this chapter are
resource-request declarations (`deploy.resources.reservations`, `deploy.resources.limits`,
`mem_limit`, `cpus`), and the interaction between resource declarations and workload
priority. Neither is presently evaluated. A repository that declares aggressive
resource limits is not thereby nonconformant; a repository that omits resource
declarations entirely is likewise not nonconformant.

### §7.1 Resource hints

Services MAY declare CPU and memory hints via the `deploy.resources` attribute or
the top-level `mem_limit`/`cpus` attributes. The release gate does not evaluate resource
declarations in this edition; violation of resource guidance is not, in itself, a basis
for denial. This clause is declaratory.

Downstream tooling may cache a release gate's decisions but MUST NOT rely on
cached decisions across requests whose relevant inputs differ. The release gate
itself does not implement a decision cache in this edition.

A release gate's evaluation is deterministic given fixed inputs. Repeated
requests with byte-identical repository state, DB state, tag evidence, and request
body MUST yield byte-identical response bodies. Sources of non-determinism (random
sort orders, iteration-order variance) are nonconformant.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

A release gate MAY implement this clause in any order relative to other clauses,
provided the output for every request is identical to the output an implementation
following this document's stated ordering would produce.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

The compose model as resolved is a data structure with a finite number of shapes.
This document does not enumerate the shapes; it enumerates predicates over the shapes,
and a release gate is expected to accommodate any shape the merge procedure can
produce. Shapes that are pathological (recursive anchors resolved to themselves,
unbounded string lengths, and so on) are outside the scope of this document and are
signaled as request errors, not as denials.

Guidance in this section does not extend to any obligation stated normatively
elsewhere. Where a subsequent chapter's clause reaches an obligation similar to this
section's guidance, the clause governs and the guidance loses independent effect.

A release gate that adds obligations beyond those this document states is not for
that reason nonconformant; the release gate simply serves a stricter policy than this
edition specifies. Conversely, a release gate that omits obligations this document
states is nonconformant regardless of how narrow the omission is.

## Chapter 8. Privileged containers

### §8.1 Privileged containers forbidden

The `privileged: true` flag grants a container all Linux capabilities and disables namespace isolation. No service, including infra-tier services, may declare `privileged: true`.

Reason code: `CDSS-SVC-008`. Clause identifier: `§8.1`.

Nothing in this clause overrides the general precedence rule of this document.
Where an amendment supersedes the clause, the amended text governs for the service
class the amendment addresses; the underlying clause continues to govern for all other
service classes.

A brief note on scoping: applicability of this clause resolves against
service-class predicates that live elsewhere in the definitions chapter and elsewhere
in the approvals database. Service names are not authoritative for classification.

A well-formed evaluation reports each service exactly once. Duplicate service
declarations across files are reconciled by the merge procedure and produce a single
service in the evaluated model.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

A release gate MAY implement this clause in any order relative to other clauses,
provided the output for every request is identical to the output an implementation
following this document's stated ordering would produce.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

The material in this section is stable in the sense that a future edition would
not narrow its content silently. Guidance may become obligation across editions, but
the guidance itself is preserved in the succeeding edition to permit downstream tools
to reason about the transition.

This section's provisions are directed at the release gate and, through it, at
the deployment repository. They are not directed at other tooling in the
release-management pipeline; downstream consumers of the emitted response are outside
the scope of this section.

A release gate that emits reasons whose codes do not appear in this document is
nonconformant. The set of reason codes is closed by the edition of this document the
release gate ships; extending the set is a matter for future editions, not for
release-gate implementations.

Nothing in this section authorizes a release gate to modify the repository, the
approvals database, or any file the request references. The release gate is purely a
reader; any implementation that writes to these inputs has departed from this
document.

The applicability tests stated elsewhere in this document produce Boolean values
per (service, clause) pair. A release gate that produces multi-valued applicability
results — for example, "partially applies" — has misinterpreted this document. All
applicability results are Boolean.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

Where a clause admits an exception via the exception-window mechanism, that
exception is subject to the temporal and non-waivable-clause rules stated in the
exception-window chapter. The clause itself does not enumerate its exceptions.

A release gate may cache read-only data across requests only where doing so
cannot alter the outcome of any request; where a cache would observe a different DB
state than a fresh read, the cache is not usable for this clause. In practice this
edition contemplates fresh reads per request.

The provisions of this section do not authorize a release gate to reach any
external system. All evidence is local: repository files, approvals database, and
signature bytes accompanying the tag.

A release gate may log its decisions for audit purposes. Such logs are outside
the scope of this document; the emitted response body is the only artifact that
receives normative constraints.

Where this clause refers to "the tag", the reference is to the specific tag
named in the request body. A release gate MUST NOT re-select a different tag from the
repository even if a more recent tag would satisfy the clause.

Nothing in this section authorizes a release gate to modify the repository, the
approvals database, or any file the request references. The release gate is purely a
reader; any implementation that writes to these inputs has departed from this
document.

The applicability tests stated elsewhere in this document produce Boolean values
per (service, clause) pair. A release gate that produces multi-valued applicability
results — for example, "partially applies" — has misinterpreted this document. All
applicability results are Boolean.

Downstream tooling may cache a release gate's decisions but MUST NOT rely on
cached decisions across requests whose relevant inputs differ. The release gate
itself does not implement a decision cache in this edition.

A release gate's evaluation is deterministic given fixed inputs. Repeated
requests with byte-identical repository state, DB state, tag evidence, and request
body MUST yield byte-identical response bodies. Sources of non-determinism (random
sort orders, iteration-order variance) are nonconformant.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

Where a clause admits an exception via the exception-window mechanism, that
exception is subject to the temporal and non-waivable-clause rules stated in the
exception-window chapter. The clause itself does not enumerate its exceptions.

A release gate may cache read-only data across requests only where doing so
cannot alter the outcome of any request; where a cache would observe a different DB
state than a fresh read, the cache is not usable for this clause. In practice this
edition contemplates fresh reads per request.

The provisions of this section do not authorize a release gate to reach any
external system. All evidence is local: repository files, approvals database, and
signature bytes accompanying the tag.

A release gate may log its decisions for audit purposes. Such logs are outside
the scope of this document; the emitted response body is the only artifact that
receives normative constraints.

Where this clause refers to "the tag", the reference is to the specific tag
named in the request body. A release gate MUST NOT re-select a different tag from the
repository even if a more recent tag would satisfy the clause.

The order in which services appear in the response's reason array is governed by
the amendment on reason ordering. Nothing in this clause imposes a service-order
constraint of its own.

A release gate whose implementation of this clause depends on the order of
services in either participating file has misread this document; service order is
non-normative.

### §4.9 Extension attribute reservation

Attribute names beginning with the character sequence `x-` are reserved for
user-defined extensions and MUST NOT be consulted by any clause of this document.
Release gates that emit reasons on the basis of extension attributes have exceeded
their remit under this edition.

The applicability tests stated elsewhere in this document produce Boolean values
per (service, clause) pair. A release gate that produces multi-valued applicability
results — for example, "partially applies" — has misinterpreted this document. All
applicability results are Boolean.

Downstream tooling may cache a release gate's decisions but MUST NOT rely on
cached decisions across requests whose relevant inputs differ. The release gate
itself does not implement a decision cache in this edition.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

### §5.11 Empty service map

A `services:` map that is present but contains no entries is a well-formed
empty compose model in the sense of §24.9 rather than an ill-formed compose file. The
distinction has no operational consequence in this edition, but it is preserved for
possible use by future editions.

Guidance in this section does not extend to any obligation stated normatively
elsewhere. Where a subsequent chapter's clause reaches an obligation similar to this
section's guidance, the clause governs and the guidance loses independent effect.

A release gate that adds obligations beyond those this document states is not for
that reason nonconformant; the release gate simply serves a stricter policy than this
edition specifies. Conversely, a release gate that omits obligations this document
states is nonconformant regardless of how narrow the omission is.

A well-formed evaluation reports each service exactly once. Duplicate service
declarations across files are reconciled by the merge procedure and produce a single
service in the evaluated model.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

A release gate MAY implement this clause in any order relative to other clauses,
provided the output for every request is identical to the output an implementation
following this document's stated ordering would produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

Where a clause admits an exception via the exception-window mechanism, that
exception is subject to the temporal and non-waivable-clause rules stated in the
exception-window chapter. The clause itself does not enumerate its exceptions.

## Chapter 9. Capability management

### §9.4 Capability drop required for non-infra services

A service that is not infra-tier per §3.7 MUST list the literal element `ALL` in its `cap_drop` list. Elements of `cap_add` are restricted to the allowlist in Appendix C.

Reason code: `CDSS-SVC-009`. Clause identifier: `§9.4`.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

A release gate MAY implement this clause in any order relative to other clauses,
provided the output for every request is identical to the output an implementation
following this document's stated ordering would produce.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

Where a clause admits an exception via the exception-window mechanism, that
exception is subject to the temporal and non-waivable-clause rules stated in the
exception-window chapter. The clause itself does not enumerate its exceptions.

This section's provisions are directed at the release gate and, through it, at
the deployment repository. They are not directed at other tooling in the
release-management pipeline; downstream consumers of the emitted response are outside
the scope of this section.

A release gate that emits reasons whose codes do not appear in this document is
nonconformant. The set of reason codes is closed by the edition of this document the
release gate ships; extending the set is a matter for future editions, not for
release-gate implementations.

Nothing in this section authorizes a release gate to modify the repository, the
approvals database, or any file the request references. The release gate is purely a
reader; any implementation that writes to these inputs has departed from this
document.

The applicability tests stated elsewhere in this document produce Boolean values
per (service, clause) pair. A release gate that produces multi-valued applicability
results — for example, "partially applies" — has misinterpreted this document. All
applicability results are Boolean.

Downstream tooling may cache a release gate's decisions but MUST NOT rely on
cached decisions across requests whose relevant inputs differ. The release gate
itself does not implement a decision cache in this edition.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

Where a clause admits an exception via the exception-window mechanism, that
exception is subject to the temporal and non-waivable-clause rules stated in the
exception-window chapter. The clause itself does not enumerate its exceptions.

A release gate may cache read-only data across requests only where doing so
cannot alter the outcome of any request; where a cache would observe a different DB
state than a fresh read, the cache is not usable for this clause. In practice this
edition contemplates fresh reads per request.

The provisions of this section do not authorize a release gate to reach any
external system. All evidence is local: repository files, approvals database, and
signature bytes accompanying the tag.

A release gate may log its decisions for audit purposes. Such logs are outside
the scope of this document; the emitted response body is the only artifact that
receives normative constraints.

Where this clause refers to "the tag", the reference is to the specific tag
named in the request body. A release gate MUST NOT re-select a different tag from the
repository even if a more recent tag would satisfy the clause.

The order in which services appear in the response's reason array is governed by
the amendment on reason ordering. Nothing in this clause imposes a service-order
constraint of its own.

A release gate whose implementation of this clause depends on the order of
services in either participating file has misread this document; service order is
non-normative.

The scope of this clause is limited to the compose model. A release gate MUST
NOT extend the clause to non-compose repository files (Dockerfile, entrypoint
scripts, or manifests for other orchestrators), even where those files carry
information adjacent to the clause's subject.

The applicability tests stated elsewhere in this document produce Boolean values
per (service, clause) pair. A release gate that produces multi-valued applicability
results — for example, "partially applies" — has misinterpreted this document. All
applicability results are Boolean.

Downstream tooling may cache a release gate's decisions but MUST NOT rely on
cached decisions across requests whose relevant inputs differ. The release gate
itself does not implement a decision cache in this edition.

A release gate's evaluation is deterministic given fixed inputs. Repeated
requests with byte-identical repository state, DB state, tag evidence, and request
body MUST yield byte-identical response bodies. Sources of non-determinism (random
sort orders, iteration-order variance) are nonconformant.

The connection contract stated elsewhere in this document is the sole basis for
the release gate's access to the approvals database. A release gate that establishes
a connection through any other mechanism has not applied the contract.

The provisions of this section do not authorize a release gate to reach any
external system. All evidence is local: repository files, approvals database, and
signature bytes accompanying the tag.

A release gate may log its decisions for audit purposes. Such logs are outside
the scope of this document; the emitted response body is the only artifact that
receives normative constraints.

Where this clause refers to "the tag", the reference is to the specific tag
named in the request body. A release gate MUST NOT re-select a different tag from the
repository even if a more recent tag would satisfy the clause.

The order in which services appear in the response's reason array is governed by
the amendment on reason ordering. Nothing in this clause imposes a service-order
constraint of its own.

A release gate whose implementation of this clause depends on the order of
services in either participating file has misread this document; service order is
non-normative.

The scope of this clause is limited to the compose model. A release gate MUST
NOT extend the clause to non-compose repository files (Dockerfile, entrypoint
scripts, or manifests for other orchestrators), even where those files carry
information adjacent to the clause's subject.

Enforcement of this clause is neutral with respect to service origin. A service
introduced by the override file is evaluated identically to a service present in the
base file; nothing in the clause privileges base declarations.

The reasoning trail from raw compose file to emitted reason is:
parse → resolve merge → enumerate services → for each service, evaluate applicable
clauses → collect reasons → filter through exception windows → sort per amendment on
reason ordering → serialize. This clause participates at the "evaluate applicable
clauses" step.

### §6.11 Reserved label prefix collisions

A label whose key begins with `cdss.` but does not match any label consulted by
a clause of this edition is neither a violation nor a warning; the release gate
silently ignores it. Future editions may attach obligations to additional reserved
labels.

The connection contract stated elsewhere in this document is the sole basis for
the release gate's access to the approvals database. A release gate that establishes
a connection through any other mechanism has not applied the contract.

Nothing in this section constitutes an obligation on any deployment. The section is
provided as guidance and as a shared vocabulary for downstream tooling. A deployment
that does not follow the guidance in this section is not thereby nonconformant with
this standard.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

Where a clause admits an exception via the exception-window mechanism, that
exception is subject to the temporal and non-waivable-clause rules stated in the
exception-window chapter. The clause itself does not enumerate its exceptions.

### §7.4 Deploy configuration

The `deploy:` block is used by Swarm-mode orchestrators. This edition does not
consult any provision under `deploy:` for any clause. A release gate that parses the
`deploy:` block for evaluation purposes has exceeded its remit.

A release gate MAY emit a warning where guidance in this section is not followed
even though nonconformance is not established; the warning is not part of the reasons
array in the denial response. The precise form of warnings is left to the release gate
implementation and is not constrained by this standard.

The distinction between an obligation and guidance under this standard is
morphological in the surrounding prose. Obligations use the modal verb `MUST`, its
negation `MUST NOT`, or the imperative form. Guidance uses `SHOULD`, `SHOULD NOT`, or
`MAY`. A reader who is uncertain which modality applies is directed to the surrounding
sentence, which will resolve the modality in every substantive clause of this
document.

Evaluation of this clause is performed independently for each service in the
enumerated model. A service that violates the clause emits exactly one reason for it,
regardless of how many distinct violation surfaces the service presents.

Nothing in this clause overrides the general precedence rule of this document.
Where an amendment supersedes the clause, the amended text governs for the service
class the amendment addresses; the underlying clause continues to govern for all other
service classes.

A brief note on scoping: applicability of this clause resolves against
service-class predicates that live elsewhere in the definitions chapter and elsewhere
in the approvals database. Service names are not authoritative for classification.

A well-formed evaluation reports each service exactly once. Duplicate service
declarations across files are reconciled by the merge procedure and produce a single
service in the evaluated model.

Where a clause admits an exception via the exception-window mechanism, that
exception is subject to the temporal and non-waivable-clause rules stated in the
exception-window chapter. The clause itself does not enumerate its exceptions.

A release gate may cache read-only data across requests only where doing so
cannot alter the outcome of any request; where a cache would observe a different DB
state than a fresh read, the cache is not usable for this clause. In practice this
edition contemplates fresh reads per request.

The provisions of this section do not authorize a release gate to reach any
external system. All evidence is local: repository files, approvals database, and
signature bytes accompanying the tag.

## Chapter 10. Image references

### §10.2 Images pinned by digest

A service's image reference MUST take the form `<repository>@sha256:<64-hex>`. Floating tags including `:latest`, unpinned tags such as `:1.2`, and repository-only references are forbidden.

Reason code: `CDSS-SVC-010`. Clause identifier: `§10.2`.

A brief note on scoping: applicability of this clause resolves against
service-class predicates that live elsewhere in the definitions chapter and elsewhere
in the approvals database. Service names are not authoritative for classification.

A well-formed evaluation reports each service exactly once. Duplicate service
declarations across files are reconciled by the merge procedure and produce a single
service in the evaluated model.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

A release gate MAY implement this clause in any order relative to other clauses,
provided the output for every request is identical to the output an implementation
following this document's stated ordering would produce.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

Nothing in this section constitutes an obligation on any deployment. The section is
provided as guidance and as a shared vocabulary for downstream tooling. A deployment
that does not follow the guidance in this section is not thereby nonconformant with
this standard.

The provisions of this section are stated at the level of the compose model rather
than at the level of any container runtime. A release gate is not required to consult
external systems to apply this section.

Where this section speaks of the "resolved" value of a service attribute, it refers
to the value produced by the merge procedure applied to the participating files. A
release gate that considers only one participating file has not resolved the service
attribute for the purposes of this section.

A release gate MAY emit a warning where guidance in this section is not followed
even though nonconformance is not established; the warning is not part of the reasons
array in the denial response. The precise form of warnings is left to the release gate
implementation and is not constrained by this standard.

The distinction between an obligation and guidance under this standard is
morphological in the surrounding prose. Obligations use the modal verb `MUST`, its
negation `MUST NOT`, or the imperative form. Guidance uses `SHOULD`, `SHOULD NOT`, or
`MAY`. A reader who is uncertain which modality applies is directed to the surrounding
sentence, which will resolve the modality in every substantive clause of this
document.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

Where a clause admits an exception via the exception-window mechanism, that
exception is subject to the temporal and non-waivable-clause rules stated in the
exception-window chapter. The clause itself does not enumerate its exceptions.

A release gate may cache read-only data across requests only where doing so
cannot alter the outcome of any request; where a cache would observe a different DB
state than a fresh read, the cache is not usable for this clause. In practice this
edition contemplates fresh reads per request.

The provisions of this section do not authorize a release gate to reach any
external system. All evidence is local: repository files, approvals database, and
signature bytes accompanying the tag.

A release gate may log its decisions for audit purposes. Such logs are outside
the scope of this document; the emitted response body is the only artifact that
receives normative constraints.

Where this clause refers to "the tag", the reference is to the specific tag
named in the request body. A release gate MUST NOT re-select a different tag from the
repository even if a more recent tag would satisfy the clause.

The order in which services appear in the response's reason array is governed by
the amendment on reason ordering. Nothing in this clause imposes a service-order
constraint of its own.

A release gate MAY emit a warning where guidance in this section is not followed
even though nonconformance is not established; the warning is not part of the reasons
array in the denial response. The precise form of warnings is left to the release gate
implementation and is not constrained by this standard.

The distinction between an obligation and guidance under this standard is
morphological in the surrounding prose. Obligations use the modal verb `MUST`, its
negation `MUST NOT`, or the imperative form. Guidance uses `SHOULD`, `SHOULD NOT`, or
`MAY`. A reader who is uncertain which modality applies is directed to the surrounding
sentence, which will resolve the modality in every substantive clause of this
document.

The compose model as resolved is a data structure with a finite number of shapes.
This document does not enumerate the shapes; it enumerates predicates over the shapes,
and a release gate is expected to accommodate any shape the merge procedure can
produce. Shapes that are pathological (recursive anchors resolved to themselves,
unbounded string lengths, and so on) are outside the scope of this document and are
signaled as request errors, not as denials.

Guidance in this section does not extend to any obligation stated normatively
elsewhere. Where a subsequent chapter's clause reaches an obligation similar to this
section's guidance, the clause governs and the guidance loses independent effect.

Where a clause admits an exception via the exception-window mechanism, that
exception is subject to the temporal and non-waivable-clause rules stated in the
exception-window chapter. The clause itself does not enumerate its exceptions.

A release gate may cache read-only data across requests only where doing so
cannot alter the outcome of any request; where a cache would observe a different DB
state than a fresh read, the cache is not usable for this clause. In practice this
edition contemplates fresh reads per request.

The provisions of this section do not authorize a release gate to reach any
external system. All evidence is local: repository files, approvals database, and
signature bytes accompanying the tag.

A release gate may log its decisions for audit purposes. Such logs are outside
the scope of this document; the emitted response body is the only artifact that
receives normative constraints.

Where this clause refers to "the tag", the reference is to the specific tag
named in the request body. A release gate MUST NOT re-select a different tag from the
repository even if a more recent tag would satisfy the clause.

The order in which services appear in the response's reason array is governed by
the amendment on reason ordering. Nothing in this clause imposes a service-order
constraint of its own.

A release gate whose implementation of this clause depends on the order of
services in either participating file has misread this document; service order is
non-normative.

The scope of this clause is limited to the compose model. A release gate MUST
NOT extend the clause to non-compose repository files (Dockerfile, entrypoint
scripts, or manifests for other orchestrators), even where those files carry
information adjacent to the clause's subject.

### §7.9 Update ordering

The `deploy.update_config` attribute governs rolling-update order in
Swarm-mode. This edition does not consult it. No update-ordering guidance in this
edition creates an obligation.

The connection contract stated elsewhere in this document is the sole basis for
the release gate's access to the approvals database. A release gate that establishes
a connection through any other mechanism has not applied the contract.

Nothing in this section constitutes an obligation on any deployment. The section is
provided as guidance and as a shared vocabulary for downstream tooling. A deployment
that does not follow the guidance in this section is not thereby nonconformant with
this standard.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

Where a clause admits an exception via the exception-window mechanism, that
exception is subject to the temporal and non-waivable-clause rules stated in the
exception-window chapter. The clause itself does not enumerate its exceptions.

### §16.7 Log rotation

`logging.options.max-size` and `logging.options.max-file` govern log rotation
policy at the container-runtime layer. This edition does not evaluate log-rotation
policy. This clause is declaratory.

Nothing in this section constitutes an obligation on any deployment. The section is
provided as guidance and as a shared vocabulary for downstream tooling. A deployment
that does not follow the guidance in this section is not thereby nonconformant with
this standard.

The provisions of this section are stated at the level of the compose model rather
than at the level of any container runtime. A release gate is not required to consult
external systems to apply this section.

The obligation stated above operates on the resolved compose model. It applies to
every service in the enumeration produced by the merge described elsewhere in this
document; the evaluation does not distinguish between services declared in one file and
services declared only in another.

The predicate stated above is defined solely in terms of the compose model as
resolved. It does not inspect runtime state, container properties, or registry metadata.
A release gate that evaluates the predicate by any means other than inspection of the
resolved compose model is nonconformant with this standard.

When a release gate denies a release on the basis of this clause, the response
carries a reason whose `code` and `clauseId` fields identify the clause and whose
`service` field names the offending service.

Evaluation of this clause is performed independently for each service in the
enumerated model. A service that violates the clause emits exactly one reason for it,
regardless of how many distinct violation surfaces the service presents.

The provisions of this section do not authorize a release gate to reach any
external system. All evidence is local: repository files, approvals database, and
signature bytes accompanying the tag.

A release gate may log its decisions for audit purposes. Such logs are outside
the scope of this document; the emitted response body is the only artifact that
receives normative constraints.

Where this clause refers to "the tag", the reference is to the specific tag
named in the request body. A release gate MUST NOT re-select a different tag from the
repository even if a more recent tag would satisfy the clause.

## Chapter 11. Secret material

### §11.1 No secret material in environment

A service's `environment:` block MUST NOT contain any key whose name case-insensitively matches any of the substrings `password`, `passwd`, `secret`, `token`, `api_key`, `apikey`, or `private_key`, whether declared in map form or as the left-hand side of a list-form entry.

Reason code: `CDSS-SVC-011`. Clause identifier: `§11.1`.

Nothing in this clause overrides the general precedence rule of this document.
Where an amendment supersedes the clause, the amended text governs for the service
class the amendment addresses; the underlying clause continues to govern for all other
service classes.

A brief note on scoping: applicability of this clause resolves against
service-class predicates that live elsewhere in the definitions chapter and elsewhere
in the approvals database. Service names are not authoritative for classification.

A well-formed evaluation reports each service exactly once. Duplicate service
declarations across files are reconciled by the merge procedure and produce a single
service in the evaluated model.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

A release gate MAY implement this clause in any order relative to other clauses,
provided the output for every request is identical to the output an implementation
following this document's stated ordering would produce.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

The provisions of this section are stated at the level of the compose model rather
than at the level of any container runtime. A release gate is not required to consult
external systems to apply this section.

Where this section speaks of the "resolved" value of a service attribute, it refers
to the value produced by the merge procedure applied to the participating files. A
release gate that considers only one participating file has not resolved the service
attribute for the purposes of this section.

A release gate MAY emit a warning where guidance in this section is not followed
even though nonconformance is not established; the warning is not part of the reasons
array in the denial response. The precise form of warnings is left to the release gate
implementation and is not constrained by this standard.

The distinction between an obligation and guidance under this standard is
morphological in the surrounding prose. Obligations use the modal verb `MUST`, its
negation `MUST NOT`, or the imperative form. Guidance uses `SHOULD`, `SHOULD NOT`, or
`MAY`. A reader who is uncertain which modality applies is directed to the surrounding
sentence, which will resolve the modality in every substantive clause of this
document.

The compose model as resolved is a data structure with a finite number of shapes.
This document does not enumerate the shapes; it enumerates predicates over the shapes,
and a release gate is expected to accommodate any shape the merge procedure can
produce. Shapes that are pathological (recursive anchors resolved to themselves,
unbounded string lengths, and so on) are outside the scope of this document and are
signaled as request errors, not as denials.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

Where a clause admits an exception via the exception-window mechanism, that
exception is subject to the temporal and non-waivable-clause rules stated in the
exception-window chapter. The clause itself does not enumerate its exceptions.

A release gate may cache read-only data across requests only where doing so
cannot alter the outcome of any request; where a cache would observe a different DB
state than a fresh read, the cache is not usable for this clause. In practice this
edition contemplates fresh reads per request.

The provisions of this section do not authorize a release gate to reach any
external system. All evidence is local: repository files, approvals database, and
signature bytes accompanying the tag.

A release gate may log its decisions for audit purposes. Such logs are outside
the scope of this document; the emitted response body is the only artifact that
receives normative constraints.

Where this clause refers to "the tag", the reference is to the specific tag
named in the request body. A release gate MUST NOT re-select a different tag from the
repository even if a more recent tag would satisfy the clause.

The distinction between an obligation and guidance under this standard is
morphological in the surrounding prose. Obligations use the modal verb `MUST`, its
negation `MUST NOT`, or the imperative form. Guidance uses `SHOULD`, `SHOULD NOT`, or
`MAY`. A reader who is uncertain which modality applies is directed to the surrounding
sentence, which will resolve the modality in every substantive clause of this
document.

The compose model as resolved is a data structure with a finite number of shapes.
This document does not enumerate the shapes; it enumerates predicates over the shapes,
and a release gate is expected to accommodate any shape the merge procedure can
produce. Shapes that are pathological (recursive anchors resolved to themselves,
unbounded string lengths, and so on) are outside the scope of this document and are
signaled as request errors, not as denials.

Guidance in this section does not extend to any obligation stated normatively
elsewhere. Where a subsequent chapter's clause reaches an obligation similar to this
section's guidance, the clause governs and the guidance loses independent effect.

A release gate that adds obligations beyond those this document states is not for
that reason nonconformant; the release gate simply serves a stricter policy than this
edition specifies. Conversely, a release gate that omits obligations this document
states is nonconformant regardless of how narrow the omission is.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

Where a clause admits an exception via the exception-window mechanism, that
exception is subject to the temporal and non-waivable-clause rules stated in the
exception-window chapter. The clause itself does not enumerate its exceptions.

A release gate may cache read-only data across requests only where doing so
cannot alter the outcome of any request; where a cache would observe a different DB
state than a fresh read, the cache is not usable for this clause. In practice this
edition contemplates fresh reads per request.

The provisions of this section do not authorize a release gate to reach any
external system. All evidence is local: repository files, approvals database, and
signature bytes accompanying the tag.

A release gate may log its decisions for audit purposes. Such logs are outside
the scope of this document; the emitted response body is the only artifact that
receives normative constraints.

Where this clause refers to "the tag", the reference is to the specific tag
named in the request body. A release gate MUST NOT re-select a different tag from the
repository even if a more recent tag would satisfy the clause.

The order in which services appear in the response's reason array is governed by
the amendment on reason ordering. Nothing in this clause imposes a service-order
constraint of its own.

A release gate whose implementation of this clause depends on the order of
services in either participating file has misread this document; service order is
non-normative.

### §16.9 Init process

The `init` boolean at the service level directs the container runtime to run a
minimal init process. This edition does not evaluate `init` declarations. This clause
is declaratory.

Nothing in this section constitutes an obligation on any deployment. The section is
provided as guidance and as a shared vocabulary for downstream tooling. A deployment
that does not follow the guidance in this section is not thereby nonconformant with
this standard.

The provisions of this section are stated at the level of the compose model rather
than at the level of any container runtime. A release gate is not required to consult
external systems to apply this section.

The obligation stated above operates on the resolved compose model. It applies to
every service in the enumeration produced by the merge described elsewhere in this
document; the evaluation does not distinguish between services declared in one file and
services declared only in another.

The predicate stated above is defined solely in terms of the compose model as
resolved. It does not inspect runtime state, container properties, or registry metadata.
A release gate that evaluates the predicate by any means other than inspection of the
resolved compose model is nonconformant with this standard.

When a release gate denies a release on the basis of this clause, the response
carries a reason whose `code` and `clauseId` fields identify the clause and whose
`service` field names the offending service.

Evaluation of this clause is performed independently for each service in the
enumerated model. A service that violates the clause emits exactly one reason for it,
regardless of how many distinct violation surfaces the service presents.

### §18.7 Container name

The `container_name` attribute assigns a fixed name to the running container.
This edition does not evaluate `container_name`; a release gate MUST NOT rely on
`container_name` as a proxy for service identity. This clause is declaratory.

A release gate that adds obligations beyond those this document states is not for
that reason nonconformant; the release gate simply serves a stricter policy than this
edition specifies. Conversely, a release gate that omits obligations this document
states is nonconformant regardless of how narrow the omission is.

The material in this section is stable in the sense that a future edition would
not narrow its content silently. Guidance may become obligation across editions, but
the guidance itself is preserved in the succeeding edition to permit downstream tools
to reason about the transition.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

A release gate MAY implement this clause in any order relative to other clauses,
provided the output for every request is identical to the output an implementation
following this document's stated ordering would produce.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

Where this clause refers to "the tag", the reference is to the specific tag
named in the request body. A release gate MUST NOT re-select a different tag from the
repository even if a more recent tag would satisfy the clause.

The order in which services appear in the response's reason array is governed by
the amendment on reason ordering. Nothing in this clause imposes a service-order
constraint of its own.

A release gate whose implementation of this clause depends on the order of
services in either participating file has misread this document; service order is
non-normative.

## Chapter 12. Filesystem writability

### §12.3 Read-only root filesystem for web-tier services

A web-tier service (see §3.4) MUST set `read_only: true` as a top-level service attribute. A service that is also cache-class (see §3.5) is exempted from this obligation.

Reason code: `CDSS-SVC-012`. Clause identifier: `§12.3`.

A well-formed evaluation reports each service exactly once. Duplicate service
declarations across files are reconciled by the merge procedure and produce a single
service in the evaluated model.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

A release gate MAY implement this clause in any order relative to other clauses,
provided the output for every request is identical to the output an implementation
following this document's stated ordering would produce.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

Where this section speaks of the "resolved" value of a service attribute, it refers
to the value produced by the merge procedure applied to the participating files. A
release gate that considers only one participating file has not resolved the service
attribute for the purposes of this section.

A release gate MAY emit a warning where guidance in this section is not followed
even though nonconformance is not established; the warning is not part of the reasons
array in the denial response. The precise form of warnings is left to the release gate
implementation and is not constrained by this standard.

The distinction between an obligation and guidance under this standard is
morphological in the surrounding prose. Obligations use the modal verb `MUST`, its
negation `MUST NOT`, or the imperative form. Guidance uses `SHOULD`, `SHOULD NOT`, or
`MAY`. A reader who is uncertain which modality applies is directed to the surrounding
sentence, which will resolve the modality in every substantive clause of this
document.

The compose model as resolved is a data structure with a finite number of shapes.
This document does not enumerate the shapes; it enumerates predicates over the shapes,
and a release gate is expected to accommodate any shape the merge procedure can
produce. Shapes that are pathological (recursive anchors resolved to themselves,
unbounded string lengths, and so on) are outside the scope of this document and are
signaled as request errors, not as denials.

Guidance in this section does not extend to any obligation stated normatively
elsewhere. Where a subsequent chapter's clause reaches an obligation similar to this
section's guidance, the clause governs and the guidance loses independent effect.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

Where a clause admits an exception via the exception-window mechanism, that
exception is subject to the temporal and non-waivable-clause rules stated in the
exception-window chapter. The clause itself does not enumerate its exceptions.

A release gate may cache read-only data across requests only where doing so
cannot alter the outcome of any request; where a cache would observe a different DB
state than a fresh read, the cache is not usable for this clause. In practice this
edition contemplates fresh reads per request.

The provisions of this section do not authorize a release gate to reach any
external system. All evidence is local: repository files, approvals database, and
signature bytes accompanying the tag.

A release gate may log its decisions for audit purposes. Such logs are outside
the scope of this document; the emitted response body is the only artifact that
receives normative constraints.

Where this clause refers to "the tag", the reference is to the specific tag
named in the request body. A release gate MUST NOT re-select a different tag from the
repository even if a more recent tag would satisfy the clause.

The order in which services appear in the response's reason array is governed by
the amendment on reason ordering. Nothing in this clause imposes a service-order
constraint of its own.

A release gate whose implementation of this clause depends on the order of
services in either participating file has misread this document; service order is
non-normative.

The compose model as resolved is a data structure with a finite number of shapes.
This document does not enumerate the shapes; it enumerates predicates over the shapes,
and a release gate is expected to accommodate any shape the merge procedure can
produce. Shapes that are pathological (recursive anchors resolved to themselves,
unbounded string lengths, and so on) are outside the scope of this document and are
signaled as request errors, not as denials.

Guidance in this section does not extend to any obligation stated normatively
elsewhere. Where a subsequent chapter's clause reaches an obligation similar to this
section's guidance, the clause governs and the guidance loses independent effect.

A release gate that adds obligations beyond those this document states is not for
that reason nonconformant; the release gate simply serves a stricter policy than this
edition specifies. Conversely, a release gate that omits obligations this document
states is nonconformant regardless of how narrow the omission is.

The material in this section is stable in the sense that a future edition would
not narrow its content silently. Guidance may become obligation across editions, but
the guidance itself is preserved in the succeeding edition to permit downstream tools
to reason about the transition.

A release gate may cache read-only data across requests only where doing so
cannot alter the outcome of any request; where a cache would observe a different DB
state than a fresh read, the cache is not usable for this clause. In practice this
edition contemplates fresh reads per request.

The provisions of this section do not authorize a release gate to reach any
external system. All evidence is local: repository files, approvals database, and
signature bytes accompanying the tag.

A release gate may log its decisions for audit purposes. Such logs are outside
the scope of this document; the emitted response body is the only artifact that
receives normative constraints.

Where this clause refers to "the tag", the reference is to the specific tag
named in the request body. A release gate MUST NOT re-select a different tag from the
repository even if a more recent tag would satisfy the clause.

The order in which services appear in the response's reason array is governed by
the amendment on reason ordering. Nothing in this clause imposes a service-order
constraint of its own.

A release gate whose implementation of this clause depends on the order of
services in either participating file has misread this document; service order is
non-normative.

The scope of this clause is limited to the compose model. A release gate MUST
NOT extend the clause to non-compose repository files (Dockerfile, entrypoint
scripts, or manifests for other orchestrators), even where those files carry
information adjacent to the clause's subject.

Enforcement of this clause is neutral with respect to service origin. A service
introduced by the override file is evaluated identically to a service present in the
base file; nothing in the clause privileges base declarations.

### §19.3 Sysctls

The `sysctls` attribute controls kernel parameters within the container's
network namespace. This edition does not evaluate `sysctls`. Future editions may
address the safety of specific sysctl entries.

The compose model as resolved is a data structure with a finite number of shapes.
This document does not enumerate the shapes; it enumerates predicates over the shapes,
and a release gate is expected to accommodate any shape the merge procedure can
produce. Shapes that are pathological (recursive anchors resolved to themselves,
unbounded string lengths, and so on) are outside the scope of this document and are
signaled as request errors, not as denials.

Guidance in this section does not extend to any obligation stated normatively
elsewhere. Where a subsequent chapter's clause reaches an obligation similar to this
section's guidance, the clause governs and the guidance loses independent effect.

A brief note on scoping: applicability of this clause resolves against
service-class predicates that live elsewhere in the definitions chapter and elsewhere
in the approvals database. Service names are not authoritative for classification.

A well-formed evaluation reports each service exactly once. Duplicate service
declarations across files are reconciled by the merge procedure and produce a single
service in the evaluated model.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

### §19.7 IPC mode

The `ipc:` attribute governs the container's IPC namespace. Values including
`host` and `shareable` have security implications considered by future editions but
not by this one; this edition treats `ipc:` as declaratory.

Downstream tooling may cache a release gate's decisions but MUST NOT rely on
cached decisions across requests whose relevant inputs differ. The release gate
itself does not implement a decision cache in this edition.

A release gate's evaluation is deterministic given fixed inputs. Repeated
requests with byte-identical repository state, DB state, tag evidence, and request
body MUST yield byte-identical response bodies. Sources of non-determinism (random
sort orders, iteration-order variance) are nonconformant.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

A release gate whose implementation of this clause depends on the order of
services in either participating file has misread this document; service order is
non-normative.

The scope of this clause is limited to the compose model. A release gate MUST
NOT extend the clause to non-compose repository files (Dockerfile, entrypoint
scripts, or manifests for other orchestrators), even where those files carry
information adjacent to the clause's subject.

Enforcement of this clause is neutral with respect to service origin. A service
introduced by the override file is evaluated identically to a service present in the
base file; nothing in the clause privileges base declarations.

## Chapter 13. Network isolation

### §13.1 Host networking forbidden except infra

A service that is not infra-tier MUST NOT declare `network_mode: host`.

Reason code: `CDSS-SVC-013`. Clause identifier: `§13.1`.

Nothing in this clause overrides the general precedence rule of this document.
Where an amendment supersedes the clause, the amended text governs for the service
class the amendment addresses; the underlying clause continues to govern for all other
service classes.

A brief note on scoping: applicability of this clause resolves against
service-class predicates that live elsewhere in the definitions chapter and elsewhere
in the approvals database. Service names are not authoritative for classification.

A well-formed evaluation reports each service exactly once. Duplicate service
declarations across files are reconciled by the merge procedure and produce a single
service in the evaluated model.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

A release gate MAY implement this clause in any order relative to other clauses,
provided the output for every request is identical to the output an implementation
following this document's stated ordering would produce.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate MAY emit a warning where guidance in this section is not followed
even though nonconformance is not established; the warning is not part of the reasons
array in the denial response. The precise form of warnings is left to the release gate
implementation and is not constrained by this standard.

The distinction between an obligation and guidance under this standard is
morphological in the surrounding prose. Obligations use the modal verb `MUST`, its
negation `MUST NOT`, or the imperative form. Guidance uses `SHOULD`, `SHOULD NOT`, or
`MAY`. A reader who is uncertain which modality applies is directed to the surrounding
sentence, which will resolve the modality in every substantive clause of this
document.

The compose model as resolved is a data structure with a finite number of shapes.
This document does not enumerate the shapes; it enumerates predicates over the shapes,
and a release gate is expected to accommodate any shape the merge procedure can
produce. Shapes that are pathological (recursive anchors resolved to themselves,
unbounded string lengths, and so on) are outside the scope of this document and are
signaled as request errors, not as denials.

Guidance in this section does not extend to any obligation stated normatively
elsewhere. Where a subsequent chapter's clause reaches an obligation similar to this
section's guidance, the clause governs and the guidance loses independent effect.

A release gate that adds obligations beyond those this document states is not for
that reason nonconformant; the release gate simply serves a stricter policy than this
edition specifies. Conversely, a release gate that omits obligations this document
states is nonconformant regardless of how narrow the omission is.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

Where a clause admits an exception via the exception-window mechanism, that
exception is subject to the temporal and non-waivable-clause rules stated in the
exception-window chapter. The clause itself does not enumerate its exceptions.

A release gate may cache read-only data across requests only where doing so
cannot alter the outcome of any request; where a cache would observe a different DB
state than a fresh read, the cache is not usable for this clause. In practice this
edition contemplates fresh reads per request.

The provisions of this section do not authorize a release gate to reach any
external system. All evidence is local: repository files, approvals database, and
signature bytes accompanying the tag.

A release gate may log its decisions for audit purposes. Such logs are outside
the scope of this document; the emitted response body is the only artifact that
receives normative constraints.

Where this clause refers to "the tag", the reference is to the specific tag
named in the request body. A release gate MUST NOT re-select a different tag from the
repository even if a more recent tag would satisfy the clause.

Guidance in this section does not extend to any obligation stated normatively
elsewhere. Where a subsequent chapter's clause reaches an obligation similar to this
section's guidance, the clause governs and the guidance loses independent effect.

A release gate that adds obligations beyond those this document states is not for
that reason nonconformant; the release gate simply serves a stricter policy than this
edition specifies. Conversely, a release gate that omits obligations this document
states is nonconformant regardless of how narrow the omission is.

The material in this section is stable in the sense that a future edition would
not narrow its content silently. Guidance may become obligation across editions, but
the guidance itself is preserved in the succeeding edition to permit downstream tools
to reason about the transition.

This section's provisions are directed at the release gate and, through it, at
the deployment repository. They are not directed at other tooling in the
release-management pipeline; downstream consumers of the emitted response are outside
the scope of this section.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

Where a clause admits an exception via the exception-window mechanism, that
exception is subject to the temporal and non-waivable-clause rules stated in the
exception-window chapter. The clause itself does not enumerate its exceptions.

A release gate may cache read-only data across requests only where doing so
cannot alter the outcome of any request; where a cache would observe a different DB
state than a fresh read, the cache is not usable for this clause. In practice this
edition contemplates fresh reads per request.

The provisions of this section do not authorize a release gate to reach any
external system. All evidence is local: repository files, approvals database, and
signature bytes accompanying the tag.

A release gate may log its decisions for audit purposes. Such logs are outside
the scope of this document; the emitted response body is the only artifact that
receives normative constraints.

Where this clause refers to "the tag", the reference is to the specific tag
named in the request body. A release gate MUST NOT re-select a different tag from the
repository even if a more recent tag would satisfy the clause.

The order in which services appear in the response's reason array is governed by
the amendment on reason ordering. Nothing in this clause imposes a service-order
constraint of its own.

A release gate whose implementation of this clause depends on the order of
services in either participating file has misread this document; service order is
non-normative.

### §20.5 PID namespace

The `pid:` attribute governs the container's process namespace. This edition
does not evaluate `pid:` values. Future editions may address the safety of
`pid: host`.

The provisions of this section are stated at the level of the compose model rather
than at the level of any container runtime. A release gate is not required to consult
external systems to apply this section.

Where this section speaks of the "resolved" value of a service attribute, it refers
to the value produced by the merge procedure applied to the participating files. A
release gate that considers only one participating file has not resolved the service
attribute for the purposes of this section.

The predicate stated above is defined solely in terms of the compose model as
resolved. It does not inspect runtime state, container properties, or registry metadata.
A release gate that evaluates the predicate by any means other than inspection of the
resolved compose model is nonconformant with this standard.

When a release gate denies a release on the basis of this clause, the response
carries a reason whose `code` and `clauseId` fields identify the clause and whose
`service` field names the offending service.

Evaluation of this clause is performed independently for each service in the
enumerated model. A service that violates the clause emits exactly one reason for it,
regardless of how many distinct violation surfaces the service presents.

Nothing in this clause overrides the general precedence rule of this document.
Where an amendment supersedes the clause, the amended text governs for the service
class the amendment addresses; the underlying clause continues to govern for all other
service classes.

### §20.9 User specifier

The `user:` attribute sets the container's effective UID/GID. This edition does
not evaluate `user:`; a service that runs as `root` inside the container is not
thereby nonconformant under this edition. Future editions may re-address.

The provisions of this section are stated at the level of the compose model rather
than at the level of any container runtime. A release gate is not required to consult
external systems to apply this section.

Where this section speaks of the "resolved" value of a service attribute, it refers
to the value produced by the merge procedure applied to the participating files. A
release gate that considers only one participating file has not resolved the service
attribute for the purposes of this section.

The predicate stated above is defined solely in terms of the compose model as
resolved. It does not inspect runtime state, container properties, or registry metadata.
A release gate that evaluates the predicate by any means other than inspection of the
resolved compose model is nonconformant with this standard.

When a release gate denies a release on the basis of this clause, the response
carries a reason whose `code` and `clauseId` fields identify the clause and whose
`service` field names the offending service.

Evaluation of this clause is performed independently for each service in the
enumerated model. A service that violates the clause emits exactly one reason for it,
regardless of how many distinct violation surfaces the service presents.

Nothing in this clause overrides the general precedence rule of this document.
Where an amendment supersedes the clause, the amended text governs for the service
class the amendment addresses; the underlying clause continues to govern for all other
service classes.

Enforcement of this clause is neutral with respect to service origin. A service
introduced by the override file is evaluated identically to a service present in the
base file; nothing in the clause privileges base declarations.

The reasoning trail from raw compose file to emitted reason is:
parse → resolve merge → enumerate services → for each service, evaluate applicable
clauses → collect reasons → filter through exception windows → sort per amendment on
reason ordering → serialize. This clause participates at the "evaluate applicable
clauses" step.

A release gate that presents its decision under a schema version other than the
one this document defines has produced a response whose interpretation is not
controlled by this document. Downstream tooling that receives such a response has no
obligation under this document.

## Chapter 14. Bind mounts

### §14.5 Bind mount source prefix allowlist

A `volumes:` entry whose source resolves to a host filesystem path MUST have that path begin with one of the following prefixes exactly: `/srv/gate/`, `/var/opt/gate/`, `/opt/gate-data/`. Named volumes are unrestricted. The host socket path `/var/run/docker.sock` is forbidden.

Reason code: `CDSS-SVC-014`. Clause identifier: `§14.5`.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

A release gate MAY implement this clause in any order relative to other clauses,
provided the output for every request is identical to the output an implementation
following this document's stated ordering would produce.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

Where a clause admits an exception via the exception-window mechanism, that
exception is subject to the temporal and non-waivable-clause rules stated in the
exception-window chapter. The clause itself does not enumerate its exceptions.

A release gate may cache read-only data across requests only where doing so
cannot alter the outcome of any request; where a cache would observe a different DB
state than a fresh read, the cache is not usable for this clause. In practice this
edition contemplates fresh reads per request.

The distinction between an obligation and guidance under this standard is
morphological in the surrounding prose. Obligations use the modal verb `MUST`, its
negation `MUST NOT`, or the imperative form. Guidance uses `SHOULD`, `SHOULD NOT`, or
`MAY`. A reader who is uncertain which modality applies is directed to the surrounding
sentence, which will resolve the modality in every substantive clause of this
document.

The compose model as resolved is a data structure with a finite number of shapes.
This document does not enumerate the shapes; it enumerates predicates over the shapes,
and a release gate is expected to accommodate any shape the merge procedure can
produce. Shapes that are pathological (recursive anchors resolved to themselves,
unbounded string lengths, and so on) are outside the scope of this document and are
signaled as request errors, not as denials.

Guidance in this section does not extend to any obligation stated normatively
elsewhere. Where a subsequent chapter's clause reaches an obligation similar to this
section's guidance, the clause governs and the guidance loses independent effect.

A release gate that adds obligations beyond those this document states is not for
that reason nonconformant; the release gate simply serves a stricter policy than this
edition specifies. Conversely, a release gate that omits obligations this document
states is nonconformant regardless of how narrow the omission is.

The material in this section is stable in the sense that a future edition would
not narrow its content silently. Guidance may become obligation across editions, but
the guidance itself is preserved in the succeeding edition to permit downstream tools
to reason about the transition.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

Where a clause admits an exception via the exception-window mechanism, that
exception is subject to the temporal and non-waivable-clause rules stated in the
exception-window chapter. The clause itself does not enumerate its exceptions.

A release gate may cache read-only data across requests only where doing so
cannot alter the outcome of any request; where a cache would observe a different DB
state than a fresh read, the cache is not usable for this clause. In practice this
edition contemplates fresh reads per request.

The provisions of this section do not authorize a release gate to reach any
external system. All evidence is local: repository files, approvals database, and
signature bytes accompanying the tag.

A release gate may log its decisions for audit purposes. Such logs are outside
the scope of this document; the emitted response body is the only artifact that
receives normative constraints.

Where this clause refers to "the tag", the reference is to the specific tag
named in the request body. A release gate MUST NOT re-select a different tag from the
repository even if a more recent tag would satisfy the clause.

The order in which services appear in the response's reason array is governed by
the amendment on reason ordering. Nothing in this clause imposes a service-order
constraint of its own.

A release gate whose implementation of this clause depends on the order of
services in either participating file has misread this document; service order is
non-normative.

The scope of this clause is limited to the compose model. A release gate MUST
NOT extend the clause to non-compose repository files (Dockerfile, entrypoint
scripts, or manifests for other orchestrators), even where those files carry
information adjacent to the clause's subject.

Enforcement of this clause is neutral with respect to service origin. A service
introduced by the override file is evaluated identically to a service present in the
base file; nothing in the clause privileges base declarations.

A release gate that adds obligations beyond those this document states is not for
that reason nonconformant; the release gate simply serves a stricter policy than this
edition specifies. Conversely, a release gate that omits obligations this document
states is nonconformant regardless of how narrow the omission is.

The material in this section is stable in the sense that a future edition would
not narrow its content silently. Guidance may become obligation across editions, but
the guidance itself is preserved in the succeeding edition to permit downstream tools
to reason about the transition.

This section's provisions are directed at the release gate and, through it, at
the deployment repository. They are not directed at other tooling in the
release-management pipeline; downstream consumers of the emitted response are outside
the scope of this section.

A release gate that emits reasons whose codes do not appear in this document is
nonconformant. The set of reason codes is closed by the edition of this document the
release gate ships; extending the set is a matter for future editions, not for
release-gate implementations.

A release gate may log its decisions for audit purposes. Such logs are outside
the scope of this document; the emitted response body is the only artifact that
receives normative constraints.

Where this clause refers to "the tag", the reference is to the specific tag
named in the request body. A release gate MUST NOT re-select a different tag from the
repository even if a more recent tag would satisfy the clause.

The order in which services appear in the response's reason array is governed by
the amendment on reason ordering. Nothing in this clause imposes a service-order
constraint of its own.

A release gate whose implementation of this clause depends on the order of
services in either participating file has misread this document; service order is
non-normative.

The scope of this clause is limited to the compose model. A release gate MUST
NOT extend the clause to non-compose repository files (Dockerfile, entrypoint
scripts, or manifests for other orchestrators), even where those files carry
information adjacent to the clause's subject.

Enforcement of this clause is neutral with respect to service origin. A service
introduced by the override file is evaluated identically to a service present in the
base file; nothing in the clause privileges base declarations.

The reasoning trail from raw compose file to emitted reason is:
parse → resolve merge → enumerate services → for each service, evaluate applicable
clauses → collect reasons → filter through exception windows → sort per amendment on
reason ordering → serialize. This clause participates at the "evaluate applicable
clauses" step.

A release gate that presents its decision under a schema version other than the
one this document defines has produced a response whose interpretation is not
controlled by this document. Downstream tooling that receives such a response has no
obligation under this document.

### §21.3 Ulimits

The `ulimits` attribute governs per-container resource limits. This edition
does not evaluate `ulimits`. This clause is declaratory.

A release gate MAY emit a warning where guidance in this section is not followed
even though nonconformance is not established; the warning is not part of the reasons
array in the denial response. The precise form of warnings is left to the release gate
implementation and is not constrained by this standard.

The distinction between an obligation and guidance under this standard is
morphological in the surrounding prose. Obligations use the modal verb `MUST`, its
negation `MUST NOT`, or the imperative form. Guidance uses `SHOULD`, `SHOULD NOT`, or
`MAY`. A reader who is uncertain which modality applies is directed to the surrounding
sentence, which will resolve the modality in every substantive clause of this
document.

Evaluation of this clause is performed independently for each service in the
enumerated model. A service that violates the clause emits exactly one reason for it,
regardless of how many distinct violation surfaces the service presents.

Nothing in this clause overrides the general precedence rule of this document.
Where an amendment supersedes the clause, the amended text governs for the service
class the amendment addresses; the underlying clause continues to govern for all other
service classes.

A brief note on scoping: applicability of this clause resolves against
service-class predicates that live elsewhere in the definitions chapter and elsewhere
in the approvals database. Service names are not authoritative for classification.

A well-formed evaluation reports each service exactly once. Duplicate service
declarations across files are reconciled by the merge procedure and produce a single
service in the evaluated model.

### §21.7 Stop signal

`stop_signal` selects the signal used to terminate the container. This edition
does not evaluate `stop_signal`. This clause is declaratory.

A release gate that emits reasons whose codes do not appear in this document is
nonconformant. The set of reason codes is closed by the edition of this document the
release gate ships; extending the set is a matter for future editions, not for
release-gate implementations.

Nothing in this section authorizes a release gate to modify the repository, the
approvals database, or any file the request references. The release gate is purely a
reader; any implementation that writes to these inputs has departed from this
document.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

A release gate that presents its decision under a schema version other than the
one this document defines has produced a response whose interpretation is not
controlled by this document. Downstream tooling that receives such a response has no
obligation under this document.

Amendments to this clause enter force at the amendment's effective date. Nothing
in the base clause text authorizes a release gate to apply an amendment before its
effective date or to withhold an amendment after its effective date.

Where a clause's predicate is expressible in propositional form, its
implementation may factor over the propositional structure. This document does not
require the release gate to preserve the propositional structure in its internal
representation.

## Chapter 15. Exception windows

This chapter states the shape of an exception-window row and the rules under
which such a row suspends a clause.

### §15.1 Row shape

Every exception-window row in `exception_windows` cites a single clause identifier, a service glob, a half-open interval `[starts_at, ends_at)`, and an `approved_at` timestamp naming when the window was approved. A window suspends the cited clause identifier for services whose name matches the glob under fnmatch semantics, within the half-open interval against the request's `evaluationTime`, provided the clause identifier is not listed in Appendix B.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

### §15.2 Interval and glob semantics

The interval named by an exception-window row is half-open at the right. A
request whose `evaluationTime` is exactly equal to `starts_at` receives the
exception; a request whose `evaluationTime` is strictly greater than `starts_at` and
strictly less than `ends_at` receives the exception; a request whose `evaluationTime`
is exactly equal to `ends_at` does not receive the exception. A release gate that
uses the closed interval or the open interval has not applied this section.

The `service_glob` column matches service names in the enumerated compose model by
`fnmatch(3)` shell-globbing semantics without path-separator handling. `*` matches
any sequence of characters including the empty sequence; `?` matches any single
character; character classes `[abc]` and negated classes `[!abc]` are supported.
Matching is case-sensitive. A glob that matches no service name silently applies to
no service; it is not, in itself, an error.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

### §15.3 Temporal binding

An exception window's suspension of a clause identified by `clause_id` binds to the obligation that clause_id imposed AT the window's `approved_at`. Amendments to the clause enacted after the window's `approved_at` do not automatically re-scope the window; obligations added by such amendments are NOT suspended by the window. A window whose `approved_at` is at or after an amendment's `effective_date` suspends the obligation as amended, including any obligations the amendment added.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

### §15.4 Time source

The temporal decision for an exception-window row is made against the request's
`evaluationTime` field, which is provided as an ISO-8601 UTC timestamp in the request
body. A release gate MUST NOT substitute wall-clock time or any other time source. The
same time source governs the temporal component of key approval as stated in Chapter
17. A release gate that uses two different time sources for exception windows and for
key approval has not applied this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

### §15.5 Non-waivable clauses

A window whose clause identifier appears in the non-waivable list of Appendix B
is silently a no-op. The window is not an error and does not raise any warning; it
simply does not suspend the clause it names. A release gate that raises an error or a
warning on such a window is nonconformant.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

## Chapter 16. Logging and lifecycle (reserved)

This chapter is reserved for future editions concerning declarative logging and
container-lifecycle configuration. Its provisions are advisory in this edition. Nothing
in this chapter is a basis for denial under this edition.

Logging configuration under this chapter is contemplated to cover the driver
selection, the log-rotation policy, the redaction of sensitive substrings in log
lines, and the retention period. Container-lifecycle configuration is contemplated
to cover the restart policy, the health-check parameters, the stop signal and
timeout, and the graceful-shutdown behaviour. This edition does not evaluate any of
these; the corresponding compose-model attributes are permitted with any well-formed
value.

A release gate implementing a future edition may add reason codes under this chapter
without renumbering the codes assigned to substantive chapters in this edition.
Reason codes in this edition follow the convention `CDSS-<CATEGORY>-<NNN>` where the
category identifies the chapter cluster; `LOG` and `LIFECYCLE` are reserved for
future use.

### §18.1 Registry mirrors

A repository MAY declare a preferred registry mirror in the compose model via the
extension attribute `x-cdss.mirror`. The release gate does not consult mirror
declarations; they are informational only. This clause is declaratory.

The provisions of this section are stated at the level of the compose model rather
than at the level of any container runtime. A release gate is not required to consult
external systems to apply this section.

Where this section speaks of the "resolved" value of a service attribute, it refers
to the value produced by the merge procedure applied to the participating files. A
release gate that considers only one participating file has not resolved the service
attribute for the purposes of this section.

The predicate stated above is defined solely in terms of the compose model as
resolved. It does not inspect runtime state, container properties, or registry metadata.
A release gate that evaluates the predicate by any means other than inspection of the
resolved compose model is nonconformant with this standard.

When a release gate denies a release on the basis of this clause, the response
carries a reason whose `code` and `clauseId` fields identify the clause and whose
`service` field names the offending service.

Evaluation of this clause is performed independently for each service in the
enumerated model. A service that violates the clause emits exactly one reason for it,
regardless of how many distinct violation surfaces the service presents.

Nothing in this clause overrides the general precedence rule of this document.
Where an amendment supersedes the clause, the amended text governs for the service
class the amendment addresses; the underlying clause continues to govern for all other
service classes.

### §18.4 Registry authentication

This edition does not consult any registry-side authentication for compose image
references. A release gate MUST NOT reach any external registry to evaluate any clause
of this edition. This clause is declaratory.

A release gate's evaluation is deterministic given fixed inputs. Repeated
requests with byte-identical repository state, DB state, tag evidence, and request
body MUST yield byte-identical response bodies. Sources of non-determinism (random
sort orders, iteration-order variance) are nonconformant.

The connection contract stated elsewhere in this document is the sole basis for
the release gate's access to the approvals database. A release gate that establishes
a connection through any other mechanism has not applied the contract.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

### §20.3 SBOM presence

Where a service ships a Software Bill of Materials, the SBOM MAY be referenced in
the compose model via the extension attribute `x-cdss.sbom`. The release gate does not
evaluate SBOMs in this edition. This clause is declaratory.

The material in this section is stable in the sense that a future edition would
not narrow its content silently. Guidance may become obligation across editions, but
the guidance itself is preserved in the succeeding edition to permit downstream tools
to reason about the transition.

This section's provisions are directed at the release gate and, through it, at
the deployment repository. They are not directed at other tooling in the
release-management pipeline; downstream consumers of the emitted response are outside
the scope of this section.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

A release gate MAY implement this clause in any order relative to other clauses,
provided the output for every request is identical to the output an implementation
following this document's stated ordering would produce.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

Where a clause admits an exception via the exception-window mechanism, that
exception is subject to the temporal and non-waivable-clause rules stated in the
exception-window chapter. The clause itself does not enumerate its exceptions.

The material in this section is stable in the sense that a future edition would
not narrow its content silently. Guidance may become obligation across editions, but
the guidance itself is preserved in the succeeding edition to permit downstream tools
to reason about the transition.

This section's provisions are directed at the release gate and, through it, at
the deployment repository. They are not directed at other tooling in the
release-management pipeline; downstream consumers of the emitted response are outside
the scope of this section.

A release gate that emits reasons whose codes do not appear in this document is
nonconformant. The set of reason codes is closed by the edition of this document the
release gate ships; extending the set is a matter for future editions, not for
release-gate implementations.

## Chapter 17. Revocation semantics

A release tag is approvable only when the following joint condition holds against the tag's creation time as reported by `git for-each-ref --format='%(creatordate:iso-strict)'`. The signature on the tag must verify cryptographically, meaning a `VALIDSIG` status line appears in the raw output of `git verify-tag --raw`. The primary fingerprint reported on that line must appear as a row in `approved_keys` after case-insensitive space-stripped comparison. That row's `approved_at` must be at or before the tag's creation time. And the tag's creation time must fall outside any revocation applicable to that row. Revocation applicability depends on the row's `status` column. A row with `status = 'active'` and a null `revoked_at` never triggers revocation. A row with `status = 'rotated'` and a non-null `revoked_at` continues to approve tags whose creation time falls within the half-open interval `[revoked_at, revoked_at + 72h)` and revokes tags whose creation time is at or after `revoked_at + 72h`. A row with `status = 'compromised'` and a non-null `revoked_at` revokes tags whose creation time is at or after `revoked_at` with no grace interval; the treatment of the `compromised` status differs from the `rotated` status in that no time-shifted approval survives the revocation timestamp. The comparison of `revoked_at` and the tag's creation time uses the UTC reading of both timestamps.

For response rendering, failures of this clause use two distinct codes. If the
tag has no cryptographically valid signature, including an unsigned tag or any
`git verify-tag --raw` result that lacks a `VALIDSIG` status line, the reason is
`§17.1` with code `CDSS-KEY-INVSIG`. If a valid signature exists but the signer
fingerprint is absent from `approved_keys`, is not yet approved at the tag's
creation time, or is revoked under the active, rotated, or compromised rules
above, the reason is `§17.1` with code `CDSS-KEY-017`. A release gate MUST NOT
collapse invalid-signature failures into `CDSS-KEY-017`.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

Where a clause admits an exception via the exception-window mechanism, that
exception is subject to the temporal and non-waivable-clause rules stated in the
exception-window chapter. The clause itself does not enumerate its exceptions.

A release gate may cache read-only data across requests only where doing so
cannot alter the outcome of any request; where a cache would observe a different DB
state than a fresh read, the cache is not usable for this clause. In practice this
edition contemplates fresh reads per request.

The provisions of this section do not authorize a release gate to reach any
external system. All evidence is local: repository files, approvals database, and
signature bytes accompanying the tag.

A release gate may log its decisions for audit purposes. Such logs are outside
the scope of this document; the emitted response body is the only artifact that
receives normative constraints.

A release gate's evaluation is deterministic given fixed inputs. Repeated
requests with byte-identical repository state, DB state, tag evidence, and request
body MUST yield byte-identical response bodies. Sources of non-determinism (random
sort orders, iteration-order variance) are nonconformant.

The connection contract stated elsewhere in this document is the sole basis for
the release gate's access to the approvals database. A release gate that establishes
a connection through any other mechanism has not applied the contract.

Nothing in this section constitutes an obligation on any deployment. The section is
provided as guidance and as a shared vocabulary for downstream tooling. A deployment
that does not follow the guidance in this section is not thereby nonconformant with
this standard.

Where this clause refers to "the tag", the reference is to the specific tag
named in the request body. A release gate MUST NOT re-select a different tag from the
repository even if a more recent tag would satisfy the clause.

The order in which services appear in the response's reason array is governed by
the amendment on reason ordering. Nothing in this clause imposes a service-order
constraint of its own.

A release gate whose implementation of this clause depends on the order of
services in either participating file has misread this document; service order is
non-normative.

The scope of this clause is limited to the compose model. A release gate MUST
NOT extend the clause to non-compose repository files (Dockerfile, entrypoint
scripts, or manifests for other orchestrators), even where those files carry
information adjacent to the clause's subject.

## Chapter 18. Supply-chain authorities (reserved)

This chapter is reserved for future editions concerning cryptographic
attestations of build provenance and artifact composition beyond the release-tag
signature. The release gate in this edition does not consult attestations. Nothing in
this chapter is a basis for denial.

The attestations contemplated for future obligations include in-toto step
attestations, SLSA provenance envelopes, and vendor-produced Software Bill of
Materials documents in SPDX and CycloneDX formats. This edition permits repositories
to reference such attestations via extension attributes but does not itself parse or
evaluate them. Future editions will state the parsing requirements, the trust anchors
for attestation-signing keys, and the interaction of attestation authorities with the
release-tag signature evaluated in Chapter 17.

A release gate implementing a future edition SHOULD treat the absence of a supply-
chain attestation as distinct from the presence of an invalid attestation. This
edition already reserves the response-shape distinction to permit future editions to
signal each case with its own reason code.

The trust anchors for supply-chain attestations are contemplated to be separate from
the trust anchors for release-tag signatures. A future edition may state distinct
approval procedures for the two anchor classes; nothing in this edition prevents that
separation.

### §21.5 Provenance envelopes

Where an image carries an in-toto or SLSA provenance envelope, that envelope MAY
be referenced by URL in the compose model. The release gate does not fetch or evaluate
provenance envelopes in this edition. This clause is declaratory.

Nothing in this section authorizes a release gate to modify the repository, the
approvals database, or any file the request references. The release gate is purely a
reader; any implementation that writes to these inputs has departed from this
document.

The applicability tests stated elsewhere in this document produce Boolean values
per (service, clause) pair. A release gate that produces multi-valued applicability
results — for example, "partially applies" — has misinterpreted this document. All
applicability results are Boolean.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

### §23.1 Container health checks

Services MAY declare `healthcheck` blocks in the compose model. The release gate
does not evaluate healthcheck declarations in this edition. This clause is
declaratory.

A release gate that adds obligations beyond those this document states is not for
that reason nonconformant; the release gate simply serves a stricter policy than this
edition specifies. Conversely, a release gate that omits obligations this document
states is nonconformant regardless of how narrow the omission is.

The material in this section is stable in the sense that a future edition would
not narrow its content silently. Guidance may become obligation across editions, but
the guidance itself is preserved in the succeeding edition to permit downstream tools
to reason about the transition.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

A release gate MAY implement this clause in any order relative to other clauses,
provided the output for every request is identical to the output an implementation
following this document's stated ordering would produce.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

### §25.1 Repository README

Repositories evaluated by the release gate SHOULD (but are not required to)
include a README describing the deployment. Absence of a README is not a basis for
denial. This clause is non-normative.

A release gate that emits reasons whose codes do not appear in this document is
nonconformant. The set of reason codes is closed by the edition of this document the
release gate ships; extending the set is a matter for future editions, not for
release-gate implementations.

Nothing in this section authorizes a release gate to modify the repository, the
approvals database, or any file the request references. The release gate is purely a
reader; any implementation that writes to these inputs has departed from this
document.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

### §32.13 Reasons array size

This edition does not impose an upper bound on the size of the reasons array. A
denial that emits fifty or more reasons is conformant provided each reason satisfies
the response-shape constraints.

The connection contract stated elsewhere in this document is the sole basis for
the release gate's access to the approvals database. A release gate that establishes
a connection through any other mechanism has not applied the contract.

Nothing in this section constitutes an obligation on any deployment. The section is
provided as guidance and as a shared vocabulary for downstream tooling. A deployment
that does not follow the guidance in this section is not thereby nonconformant with
this standard.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

Where a clause admits an exception via the exception-window mechanism, that
exception is subject to the temporal and non-waivable-clause rules stated in the
exception-window chapter. The clause itself does not enumerate its exceptions.

### §33.3 Response streaming

Response bodies are transmitted whole; this edition does not authorize a
release gate to stream a partial response body. The body is either transmitted in
full or the request is signaled as an error at the transport layer.

The distinction between an obligation and guidance under this standard is
morphological in the surrounding prose. Obligations use the modal verb `MUST`, its
negation `MUST NOT`, or the imperative form. Guidance uses `SHOULD`, `SHOULD NOT`, or
`MAY`. A reader who is uncertain which modality applies is directed to the surrounding
sentence, which will resolve the modality in every substantive clause of this
document.

The compose model as resolved is a data structure with a finite number of shapes.
This document does not enumerate the shapes; it enumerates predicates over the shapes,
and a release gate is expected to accommodate any shape the merge procedure can
produce. Shapes that are pathological (recursive anchors resolved to themselves,
unbounded string lengths, and so on) are outside the scope of this document and are
signaled as request errors, not as denials.

Nothing in this clause overrides the general precedence rule of this document.
Where an amendment supersedes the clause, the amended text governs for the service
class the amendment addresses; the underlying clause continues to govern for all other
service classes.

A brief note on scoping: applicability of this clause resolves against
service-class predicates that live elsewhere in the definitions chapter and elsewhere
in the approvals database. Service names are not authoritative for classification.

A well-formed evaluation reports each service exactly once. Duplicate service
declarations across files are reconciled by the merge procedure and produce a single
service in the evaluated model.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

### §33.7 HTTP method restrictions

The `/gate/evaluate` endpoint accepts `POST` only. Other HTTP methods on this
path receive an HTTP 405 response with no denial-body reason code; this response is
not a decision under this document.

Nothing in this section authorizes a release gate to modify the repository, the
approvals database, or any file the request references. The release gate is purely a
reader; any implementation that writes to these inputs has departed from this
document.

The applicability tests stated elsewhere in this document produce Boolean values
per (service, clause) pair. A release gate that produces multi-valued applicability
results — for example, "partially applies" — has misinterpreted this document. All
applicability results are Boolean.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

### §35.1 Time-of-day precision

`evaluationTime` is compared to the second; sub-second precision in the
request timestamp is accepted but rounded down to the second before comparison.
Release gates that preserve sub-second precision are conformant but do not obtain a
finer-grained comparison than one second.

A release gate that emits reasons whose codes do not appear in this document is
nonconformant. The set of reason codes is closed by the edition of this document the
release gate ships; extending the set is a matter for future editions, not for
release-gate implementations.

Nothing in this section authorizes a release gate to modify the repository, the
approvals database, or any file the request references. The release gate is purely a
reader; any implementation that writes to these inputs has departed from this
document.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

Where a clause admits an exception via the exception-window mechanism, that
exception is subject to the temporal and non-waivable-clause rules stated in the
exception-window chapter. The clause itself does not enumerate its exceptions.

A release gate may cache read-only data across requests only where doing so
cannot alter the outcome of any request; where a cache would observe a different DB
state than a fresh read, the cache is not usable for this clause. In practice this
edition contemplates fresh reads per request.

The provisions of this section do not authorize a release gate to reach any
external system. All evidence is local: repository files, approvals database, and
signature bytes accompanying the tag.

A release gate may log its decisions for audit purposes. Such logs are outside
the scope of this document; the emitted response body is the only artifact that
receives normative constraints.

Nothing in this section authorizes a release gate to modify the repository, the
approvals database, or any file the request references. The release gate is purely a
reader; any implementation that writes to these inputs has departed from this
document.

The applicability tests stated elsewhere in this document produce Boolean values
per (service, clause) pair. A release gate that produces multi-valued applicability
results — for example, "partially applies" — has misinterpreted this document. All
applicability results are Boolean.

Downstream tooling may cache a release gate's decisions but MUST NOT rely on
cached decisions across requests whose relevant inputs differ. The release gate
itself does not implement a decision cache in this edition.

## Chapter 22. Repository hooks

### §22.4 Repository hooks configuration

A repository presented for evaluation MUST set `core.hooksPath` in its `.git/config` to the exact string `.githooks`. The `.githooks/pre-push` file MUST exist, MUST have the Unix owner executable bit set, and MUST contain a line matching the exact form `# CDSS-STANDARD-SHA256: <64-hex>` naming the SHA-256 of the shipped `cdss_v4.md` file at evaluation time.

The SHA-256 named in the marker line is the SHA-256 of the byte contents of the
`cdss_v4.md` file the release gate applies to the request. A release gate MUST compute
the hash of the live file, not of any cached or historical version, and MUST compare
it to the hex value in the marker line by a single case-insensitive comparison. A
release gate that compares to a stored hash has not applied this section.

The `core.hooksPath` value is read from the repository's `.git/config` file directly.
A release gate MUST parse the ini form of `.git/config`; it MUST NOT rely on a
shell-out to `git config`. Parsing MAY tolerate surrounding whitespace and quoted
values in the config file per standard ini conventions.

A release gate may cache read-only data across requests only where doing so
cannot alter the outcome of any request; where a cache would observe a different DB
state than a fresh read, the cache is not usable for this clause. In practice this
edition contemplates fresh reads per request.

The provisions of this section do not authorize a release gate to reach any
external system. All evidence is local: repository files, approvals database, and
signature bytes accompanying the tag.

A release gate may log its decisions for audit purposes. Such logs are outside
the scope of this document; the emitted response body is the only artifact that
receives normative constraints.

### §22.7 Historical hooks

A repository that carried a differently named hooks path in an earlier revision
is not thereby nonconformant, provided its current `core.hooksPath` value is
`.githooks` and the pre-push file at that path satisfies the marker requirement of
§22.4. The release gate does not inspect historical revisions of the hooks path or the
pre-push file.

The provisions of this section do not authorize a release gate to reach any
external system. All evidence is local: repository files, approvals database, and
signature bytes accompanying the tag.

A release gate may log its decisions for audit purposes. Such logs are outside
the scope of this document; the emitted response body is the only artifact that
receives normative constraints.

Where this clause refers to "the tag", the reference is to the specific tag
named in the request body. A release gate MUST NOT re-select a different tag from the
repository even if a more recent tag would satisfy the clause.

## Chapter 24. Compose model assembly

### §24.1 File participation

Two files participate in the merge in this edition: the base file `docker-compose.yml` at the repository root, if present, and the override file `docker-compose.prod.yml` at the repository root, if present. Files at other paths do not participate.

A repository that omits both participating files presents no compose model to
the release gate and is denied under §24.9.

A release gate may log its decisions for audit purposes. Such logs are outside
the scope of this document; the emitted response body is the only artifact that
receives normative constraints.

Where this clause refers to "the tag", the reference is to the specific tag
named in the request body. A release gate MUST NOT re-select a different tag from the
repository even if a more recent tag would satisfy the clause.

The order in which services appear in the response's reason array is governed by
the amendment on reason ordering. Nothing in this clause imposes a service-order
constraint of its own.

### §24.2 Scalar rule

Scalar values in the override file replace scalar values in the base file for the same service and the same key. Missing keys in the override leave the base value unchanged.

Where this clause refers to "the tag", the reference is to the specific tag
named in the request body. A release gate MUST NOT re-select a different tag from the
repository even if a more recent tag would satisfy the clause.

The order in which services appear in the response's reason array is governed by
the amendment on reason ordering. Nothing in this clause imposes a service-order
constraint of its own.

A release gate whose implementation of this clause depends on the order of
services in either participating file has misread this document; service order is
non-normative.

### §24.3 Map rule

Map values in the override file are merged key-by-key with the base map. Nested maps recurse. Setting a key to `null` in the override removes it from the base.

The order in which services appear in the response's reason array is governed by
the amendment on reason ordering. Nothing in this clause imposes a service-order
constraint of its own.

A release gate whose implementation of this clause depends on the order of
services in either participating file has misread this document; service order is
non-normative.

The scope of this clause is limited to the compose model. A release gate MUST
NOT extend the clause to non-compose repository files (Dockerfile, entrypoint
scripts, or manifests for other orchestrators), even where those files carry
information adjacent to the clause's subject.

### §24.4 List rule

For any list-valued service attribute — including `ports`, `volumes`, `cap_add`, `cap_drop`, and every other list-valued attribute — the override list REPLACES the base list wholesale. There is no list-merge mode.

A release gate whose implementation of this clause depends on the order of
services in either participating file has misread this document; service order is
non-normative.

The scope of this clause is limited to the compose model. A release gate MUST
NOT extend the clause to non-compose repository files (Dockerfile, entrypoint
scripts, or manifests for other orchestrators), even where those files carry
information adjacent to the clause's subject.

Enforcement of this clause is neutral with respect to service origin. A service
introduced by the override file is evaluated identically to a service present in the
base file; nothing in the clause privileges base declarations.

### §24.5 Service rule

A service present only in the override file is added to the merged services map. A service present only in the base file is retained. A service present in both files is merged at the service level per the rules above. There is no way to remove a service via the override file.

The scope of this clause is limited to the compose model. A release gate MUST
NOT extend the clause to non-compose repository files (Dockerfile, entrypoint
scripts, or manifests for other orchestrators), even where those files carry
information adjacent to the clause's subject.

Enforcement of this clause is neutral with respect to service origin. A service
introduced by the override file is evaluated identically to a service present in the
base file; nothing in the clause privileges base declarations.

The reasoning trail from raw compose file to emitted reason is:
parse → resolve merge → enumerate services → for each service, evaluate applicable
clauses → collect reasons → filter through exception windows → sort per amendment on
reason ordering → serialize. This clause participates at the "evaluate applicable
clauses" step.

### §24.9 Empty-model repositories

A repository that presents neither the base file nor the override file has no
compose model. A release gate denies such a request with reason code `CDSS-SVC-024`,
clause identifier `§24.9`, and empty `service` field. This is the only clause in
Chapter 24 that emits a reason code; the merge rules above are procedural.

Enforcement of this clause is neutral with respect to service origin. A service
introduced by the override file is evaluated identically to a service present in the
base file; nothing in the clause privileges base declarations.

The reasoning trail from raw compose file to emitted reason is:
parse → resolve merge → enumerate services → for each service, evaluate applicable
clauses → collect reasons → filter through exception windows → sort per amendment on
reason ordering → serialize. This clause participates at the "evaluate applicable
clauses" step.

A release gate that presents its decision under a schema version other than the
one this document defines has produced a response whose interpretation is not
controlled by this document. Downstream tooling that receives such a response has no
obligation under this document.

### §25.7 Repository size

This edition does not impose a size limit on the repositories it evaluates.
Release gates MAY, at their discretion, decline to evaluate repositories whose overall
size exceeds a resource budget local to the release gate; such declines are signaled as
request errors and are not denials under this standard.

Nothing in this section authorizes a release gate to modify the repository, the
approvals database, or any file the request references. The release gate is purely a
reader; any implementation that writes to these inputs has departed from this
document.

The applicability tests stated elsewhere in this document produce Boolean values
per (service, clause) pair. A release gate that produces multi-valued applicability
results — for example, "partially applies" — has misinterpreted this document. All
applicability results are Boolean.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

### §27.2 Reason localization

Reason strings emitted by the release gate are English identifiers and are not
localized. A downstream tool that requires localized text MUST perform its own mapping
from reason code to localized string. This clause is declaratory.

The provisions of this section are stated at the level of the compose model rather
than at the level of any container runtime. A release gate is not required to consult
external systems to apply this section.

Where this section speaks of the "resolved" value of a service attribute, it refers
to the value produced by the merge procedure applied to the participating files. A
release gate that considers only one participating file has not resolved the service
attribute for the purposes of this section.

The predicate stated above is defined solely in terms of the compose model as
resolved. It does not inspect runtime state, container properties, or registry metadata.
A release gate that evaluates the predicate by any means other than inspection of the
resolved compose model is nonconformant with this standard.

When a release gate denies a release on the basis of this clause, the response
carries a reason whose `code` and `clauseId` fields identify the clause and whose
`service` field names the offending service.

Evaluation of this clause is performed independently for each service in the
enumerated model. A service that violates the clause emits exactly one reason for it,
regardless of how many distinct violation surfaces the service presents.

Nothing in this clause overrides the general precedence rule of this document.
Where an amendment supersedes the clause, the amended text governs for the service
class the amendment addresses; the underlying clause continues to govern for all other
service classes.

### §28.1 Trailer conventions

Signed release tags SHOULD include a trailer block naming the reviewers of the
release. The release gate does not evaluate tag trailers in this edition. This clause
is declaratory.

Nothing in this section constitutes an obligation on any deployment. The section is
provided as guidance and as a shared vocabulary for downstream tooling. A deployment
that does not follow the guidance in this section is not thereby nonconformant with
this standard.

The provisions of this section are stated at the level of the compose model rather
than at the level of any container runtime. A release gate is not required to consult
external systems to apply this section.

The obligation stated above operates on the resolved compose model. It applies to
every service in the enumeration produced by the merge described elsewhere in this
document; the evaluation does not distinguish between services declared in one file and
services declared only in another.

The predicate stated above is defined solely in terms of the compose model as
resolved. It does not inspect runtime state, container properties, or registry metadata.
A release gate that evaluates the predicate by any means other than inspection of the
resolved compose model is nonconformant with this standard.

When a release gate denies a release on the basis of this clause, the response
carries a reason whose `code` and `clauseId` fields identify the clause and whose
`service` field names the offending service.

Evaluation of this clause is performed independently for each service in the
enumerated model. A service that violates the clause emits exactly one reason for it,
regardless of how many distinct violation surfaces the service presents.

### §23.5 Working directory

The `working_dir` attribute sets the container's initial working directory.
This edition does not evaluate `working_dir`. This clause is declaratory.

Guidance in this section does not extend to any obligation stated normatively
elsewhere. Where a subsequent chapter's clause reaches an obligation similar to this
section's guidance, the clause governs and the guidance loses independent effect.

A release gate that adds obligations beyond those this document states is not for
that reason nonconformant; the release gate simply serves a stricter policy than this
edition specifies. Conversely, a release gate that omits obligations this document
states is nonconformant regardless of how narrow the omission is.

A well-formed evaluation reports each service exactly once. Duplicate service
declarations across files are reconciled by the merge procedure and produce a single
service in the evaluated model.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

A release gate MAY implement this clause in any order relative to other clauses,
provided the output for every request is identical to the output an implementation
following this document's stated ordering would produce.

### §23.9 Entrypoint override

The `entrypoint:` attribute overrides the image's entrypoint. This edition
does not evaluate `entrypoint:`. This clause is declaratory.

Guidance in this section does not extend to any obligation stated normatively
elsewhere. Where a subsequent chapter's clause reaches an obligation similar to this
section's guidance, the clause governs and the guidance loses independent effect.

A release gate that adds obligations beyond those this document states is not for
that reason nonconformant; the release gate simply serves a stricter policy than this
edition specifies. Conversely, a release gate that omits obligations this document
states is nonconformant regardless of how narrow the omission is.

A well-formed evaluation reports each service exactly once. Duplicate service
declarations across files are reconciled by the merge procedure and produce a single
service in the evaluated model.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

A release gate MAY implement this clause in any order relative to other clauses,
provided the output for every request is identical to the output an implementation
following this document's stated ordering would produce.

### §24.13 Multiple compose specifications

This edition does not implement variant Compose specification versions (`3.x`,
`3.9`, or explicit `version:` string). The release gate consults only the two
participating files at their canonical names; any `version:` declaration at the top
level is silently ignored.

A release gate that adds obligations beyond those this document states is not for
that reason nonconformant; the release gate simply serves a stricter policy than this
edition specifies. Conversely, a release gate that omits obligations this document
states is nonconformant regardless of how narrow the omission is.

The material in this section is stable in the sense that a future edition would
not narrow its content silently. Guidance may become obligation across editions, but
the guidance itself is preserved in the succeeding edition to permit downstream tools
to reason about the transition.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

A release gate MAY implement this clause in any order relative to other clauses,
provided the output for every request is identical to the output an implementation
following this document's stated ordering would produce.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

### §27.7 Reason trailer conventions

This edition does not authorize a release gate to append trailer text to any
reason. The reason object is exactly three fields; downstream tooling that requires
additional metadata must derive it from the code and clauseId fields.

Nothing in this section authorizes a release gate to modify the repository, the
approvals database, or any file the request references. The release gate is purely a
reader; any implementation that writes to these inputs has departed from this
document.

The applicability tests stated elsewhere in this document produce Boolean values
per (service, clause) pair. A release gate that produces multi-valued applicability
results — for example, "partially applies" — has misinterpreted this document. All
applicability results are Boolean.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

## Chapter 25. Informational

This chapter collects informational material that does not create obligations
of its own. Its provisions cross-refer to substantive chapters.

The informational material here is not superseded by any subsequent chapter. It is
also not authoritative on any substantive point; where a substantive chapter states a
rule and the informational material appears to state the same rule differently, the
substantive chapter governs and the informational material is understood as a
paraphrase rather than as an independent authority.

A release gate MAY use the material in this chapter as a source of documentation
strings for its own diagnostic output. Nothing in this chapter prevents that use;
the material is public within the release-gate implementation's own scope.

### §29.3 Environment reference forms

The `environment:` attribute of a service accepts both the list form
(`KEY=VALUE`) and the map form (`KEY: VALUE`). The release gate normalizes both forms
to the map form before evaluation; the choice of form is not itself constrained. This
clause is declaratory.

The applicability tests stated elsewhere in this document produce Boolean values
per (service, clause) pair. A release gate that produces multi-valued applicability
results — for example, "partially applies" — has misinterpreted this document. All
applicability results are Boolean.

Downstream tooling may cache a release gate's decisions but MUST NOT rely on
cached decisions across requests whose relevant inputs differ. The release gate
itself does not implement a decision cache in this edition.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

### §29.7 Numeric coercion

Values that a YAML parser will coerce from a bare-number token to an integer are
normalized to integers before evaluation. A release gate that treats such values as
strings has not applied this section. This clause is declaratory.

The material in this section is stable in the sense that a future edition would
not narrow its content silently. Guidance may become obligation across editions, but
the guidance itself is preserved in the succeeding edition to permit downstream tools
to reason about the transition.

This section's provisions are directed at the release gate and, through it, at
the deployment repository. They are not directed at other tooling in the
release-management pipeline; downstream consumers of the emitted response are outside
the scope of this section.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

A release gate MAY implement this clause in any order relative to other clauses,
provided the output for every request is identical to the output an implementation
following this document's stated ordering would produce.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

### §30.1 Networks enumeration

Top-level `networks:` declarations MAY be present in either participating file.
The release gate does not evaluate networks declarations in this edition beyond their
transitive effects on network mode. This clause is declaratory.

The provisions of this section are stated at the level of the compose model rather
than at the level of any container runtime. A release gate is not required to consult
external systems to apply this section.

Where this section speaks of the "resolved" value of a service attribute, it refers
to the value produced by the merge procedure applied to the participating files. A
release gate that considers only one participating file has not resolved the service
attribute for the purposes of this section.

The predicate stated above is defined solely in terms of the compose model as
resolved. It does not inspect runtime state, container properties, or registry metadata.
A release gate that evaluates the predicate by any means other than inspection of the
resolved compose model is nonconformant with this standard.

When a release gate denies a release on the basis of this clause, the response
carries a reason whose `code` and `clauseId` fields identify the clause and whose
`service` field names the offending service.

Evaluation of this clause is performed independently for each service in the
enumerated model. A service that violates the clause emits exactly one reason for it,
regardless of how many distinct violation surfaces the service presents.

Nothing in this clause overrides the general precedence rule of this document.
Where an amendment supersedes the clause, the amended text governs for the service
class the amendment addresses; the underlying clause continues to govern for all other
service classes.

### §31.1 Volumes enumeration

Top-level `volumes:` declarations MAY be present in either participating file.
The release gate does not evaluate top-level volumes declarations beyond their
transitive effects on service-level bind mounts. This clause is declaratory.

The material in this section is stable in the sense that a future edition would
not narrow its content silently. Guidance may become obligation across editions, but
the guidance itself is preserved in the succeeding edition to permit downstream tools
to reason about the transition.

This section's provisions are directed at the release gate and, through it, at
the deployment repository. They are not directed at other tooling in the
release-management pipeline; downstream consumers of the emitted response are outside
the scope of this section.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

A release gate MAY implement this clause in any order relative to other clauses,
provided the output for every request is identical to the output an implementation
following this document's stated ordering would produce.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

### §29.9 Command tokenization

The `command:` attribute accepts both string form and list form. This edition
does not evaluate `command:` for any clause. Tokenization strategy is left to the
container runtime.

A release gate's evaluation is deterministic given fixed inputs. Repeated
requests with byte-identical repository state, DB state, tag evidence, and request
body MUST yield byte-identical response bodies. Sources of non-determinism (random
sort orders, iteration-order variance) are nonconformant.

The connection contract stated elsewhere in this document is the sole basis for
the release gate's access to the approvals database. A release gate that establishes
a connection through any other mechanism has not applied the contract.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

### §30.5 Network alias

Network aliases MAY be declared under `networks.<name>.aliases`. This edition
does not consult aliases in any clause. Their presence has no operational effect on
release-gate evaluation.

The compose model as resolved is a data structure with a finite number of shapes.
This document does not enumerate the shapes; it enumerates predicates over the shapes,
and a release gate is expected to accommodate any shape the merge procedure can
produce. Shapes that are pathological (recursive anchors resolved to themselves,
unbounded string lengths, and so on) are outside the scope of this document and are
signaled as request errors, not as denials.

Guidance in this section does not extend to any obligation stated normatively
elsewhere. Where a subsequent chapter's clause reaches an obligation similar to this
section's guidance, the clause governs and the guidance loses independent effect.

A brief note on scoping: applicability of this clause resolves against
service-class predicates that live elsewhere in the definitions chapter and elsewhere
in the approvals database. Service names are not authoritative for classification.

A well-formed evaluation reports each service exactly once. Duplicate service
declarations across files are reconciled by the merge procedure and produce a single
service in the evaluated model.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

### §30.9 IPv6 declarations

Both IPv4 and IPv6 declarations MAY appear under `networks:` and under service
`ports:` entries. This edition treats both address families identically for the
purposes of port-zone derivation; the zone predicate applies to the numeric host-side
port regardless of address family.

Where this section speaks of the "resolved" value of a service attribute, it refers
to the value produced by the merge procedure applied to the participating files. A
release gate that considers only one participating file has not resolved the service
attribute for the purposes of this section.

A release gate MAY emit a warning where guidance in this section is not followed
even though nonconformance is not established; the warning is not part of the reasons
array in the denial response. The precise form of warnings is left to the release gate
implementation and is not constrained by this standard.

When a release gate denies a release on the basis of this clause, the response
carries a reason whose `code` and `clauseId` fields identify the clause and whose
`service` field names the offending service.

Evaluation of this clause is performed independently for each service in the
enumerated model. A service that violates the clause emits exactly one reason for it,
regardless of how many distinct violation surfaces the service presents.

Nothing in this clause overrides the general precedence rule of this document.
Where an amendment supersedes the clause, the amended text governs for the service
class the amendment addresses; the underlying clause continues to govern for all other
service classes.

A brief note on scoping: applicability of this clause resolves against
service-class predicates that live elsewhere in the definitions chapter and elsewhere
in the approvals database. Service names are not authoritative for classification.

### §31.5 Volume driver

The `volumes.<name>.driver` attribute selects a top-level volume driver. This
edition does not evaluate the driver; a service that names a volume of any driver
type is not thereby nonconformant.

Where this section speaks of the "resolved" value of a service attribute, it refers
to the value produced by the merge procedure applied to the participating files. A
release gate that considers only one participating file has not resolved the service
attribute for the purposes of this section.

A release gate MAY emit a warning where guidance in this section is not followed
even though nonconformance is not established; the warning is not part of the reasons
array in the denial response. The precise form of warnings is left to the release gate
implementation and is not constrained by this standard.

When a release gate denies a release on the basis of this clause, the response
carries a reason whose `code` and `clauseId` fields identify the clause and whose
`service` field names the offending service.

Evaluation of this clause is performed independently for each service in the
enumerated model. A service that violates the clause emits exactly one reason for it,
regardless of how many distinct violation surfaces the service presents.

Nothing in this clause overrides the general precedence rule of this document.
Where an amendment supersedes the clause, the amended text governs for the service
class the amendment addresses; the underlying clause continues to govern for all other
service classes.

A brief note on scoping: applicability of this clause resolves against
service-class predicates that live elsewhere in the definitions chapter and elsewhere
in the approvals database. Service names are not authoritative for classification.

### §32.7 Content-Type header

The release gate returns its decision with `Content-Type: application/json`.
Nothing in this document constrains the transport layer beyond that; TLS, keepalive,
and compression are all handled at the transport layer and are outside the scope of
this document.

The compose model as resolved is a data structure with a finite number of shapes.
This document does not enumerate the shapes; it enumerates predicates over the shapes,
and a release gate is expected to accommodate any shape the merge procedure can
produce. Shapes that are pathological (recursive anchors resolved to themselves,
unbounded string lengths, and so on) are outside the scope of this document and are
signaled as request errors, not as denials.

Guidance in this section does not extend to any obligation stated normatively
elsewhere. Where a subsequent chapter's clause reaches an obligation similar to this
section's guidance, the clause governs and the guidance loses independent effect.

A brief note on scoping: applicability of this clause resolves against
service-class predicates that live elsewhere in the definitions chapter and elsewhere
in the approvals database. Service names are not authoritative for classification.

A well-formed evaluation reports each service exactly once. Duplicate service
declarations across files are reconciled by the merge procedure and produce a single
service in the evaluated model.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

The scope of this clause is limited to the compose model. A release gate MUST
NOT extend the clause to non-compose repository files (Dockerfile, entrypoint
scripts, or manifests for other orchestrators), even where those files carry
information adjacent to the clause's subject.

Enforcement of this clause is neutral with respect to service origin. A service
introduced by the override file is evaluated identically to a service present in the
base file; nothing in the clause privileges base declarations.

The reasoning trail from raw compose file to emitted reason is:
parse → resolve merge → enumerate services → for each service, evaluate applicable
clauses → collect reasons → filter through exception windows → sort per amendment on
reason ordering → serialize. This clause participates at the "evaluate applicable
clauses" step.

A release gate that presents its decision under a schema version other than the
one this document defines has produced a response whose interpretation is not
controlled by this document. Downstream tooling that receives such a response has no
obligation under this document.

Amendments to this clause enter force at the amendment's effective date. Nothing
in the base clause text authorizes a release gate to apply an amendment before its
effective date or to withhold an amendment after its effective date.

Where a clause's predicate is expressible in propositional form, its
implementation may factor over the propositional structure. This document does not
require the release gate to preserve the propositional structure in its internal
representation.

Guidance in this section does not extend to any obligation stated normatively
elsewhere. Where a subsequent chapter's clause reaches an obligation similar to this
section's guidance, the clause governs and the guidance loses independent effect.

A release gate that adds obligations beyond those this document states is not for
that reason nonconformant; the release gate simply serves a stricter policy than this
edition specifies. Conversely, a release gate that omits obligations this document
states is nonconformant regardless of how narrow the omission is.

The material in this section is stable in the sense that a future edition would
not narrow its content silently. Guidance may become obligation across editions, but
the guidance itself is preserved in the succeeding edition to permit downstream tools
to reason about the transition.

This section's provisions are directed at the release gate and, through it, at
the deployment repository. They are not directed at other tooling in the
release-management pipeline; downstream consumers of the emitted response are outside
the scope of this section.

## Chapter 27. Numbering conventions

This chapter records the numbering conventions used elsewhere in this
document. Its provisions describe the shape of the identifiers assigned to clauses,
reason codes, and amendments; they do not create obligations of their own beyond
those already imposed by the substantive chapters.

Clause identifiers take the form `§X.Y` where `X` is the chapter number and `Y` is
a chapter-local ordinal. Where a chapter emits multiple clauses, the ordinals are
not necessarily sequential; gaps in the numbering are permitted and carry no
meaning. Downstream tooling MUST NOT rely on the sequentiality of ordinals within a
chapter.

Reason codes take the form `CDSS-<CATEGORY>-<NNN>` where `<CATEGORY>` is a
three-to-five-letter mnemonic identifying the code's cluster and `<NNN>` is a
zero-padded three-digit ordinal. Codes are stable across editions once assigned; a
future edition MAY add codes but MUST NOT reassign existing codes to different
clauses.

Amendment identifiers take the form `Amendment N` where `N` is a sequential
integer. Amendments are numbered in the order they were adopted; the order does not
imply topical relationship. Where two amendments address the same clause, the
later-adopted amendment is authoritative for the clauses it explicitly addresses.

The reasoning trail from raw compose file to emitted reason is:
parse → resolve merge → enumerate services → for each service, evaluate applicable
clauses → collect reasons → filter through exception windows → sort per amendment on
reason ordering → serialize. This clause participates at the "evaluate applicable
clauses" step.

A release gate that presents its decision under a schema version other than the
one this document defines has produced a response whose interpretation is not
controlled by this document. Downstream tooling that receives such a response has no
obligation under this document.

Amendments to this clause enter force at the amendment's effective date. Nothing
in the base clause text authorizes a release gate to apply an amendment before its
effective date or to withhold an amendment after its effective date.

Where a clause's predicate is expressible in propositional form, its
implementation may factor over the propositional structure. This document does not
require the release gate to preserve the propositional structure in its internal
representation.

A release gate that evaluates this clause through pattern-matching over the raw
YAML text rather than through predicate evaluation over the parsed model has taken a
shortcut that is not authorized by this document. All clauses evaluate against the
parsed model.

This section's provisions are directed at the release gate and, through it, at
the deployment repository. They are not directed at other tooling in the
release-management pipeline; downstream consumers of the emitted response are outside
the scope of this section.

A release gate that emits reasons whose codes do not appear in this document is
nonconformant. The set of reason codes is closed by the edition of this document the
release gate ships; extending the set is a matter for future editions, not for
release-gate implementations.

Nothing in this section authorizes a release gate to modify the repository, the
approvals database, or any file the request references. The release gate is purely a
reader; any implementation that writes to these inputs has departed from this
document.

The applicability tests stated elsewhere in this document produce Boolean values
per (service, clause) pair. A release gate that produces multi-valued applicability
results — for example, "partially applies" — has misinterpreted this document. All
applicability results are Boolean.

## Chapter 28. Audit

This chapter is reserved for future editions concerning audit and record
retention. The release gate in this edition emits a response body per request; it
does not implement any audit or retention obligation independent of that response.
Nothing in this chapter is a basis for denial under this edition.

Downstream tooling that maintains an audit log of release-gate decisions is
outside the scope of this document. A future edition may specify obligations on
audit-log content or retention, in which case the release gate itself will assume
those obligations. Present-edition release gates are not required to emit
audit-log entries.

A release gate that presents its decision under a schema version other than the
one this document defines has produced a response whose interpretation is not
controlled by this document. Downstream tooling that receives such a response has no
obligation under this document.

Amendments to this clause enter force at the amendment's effective date. Nothing
in the base clause text authorizes a release gate to apply an amendment before its
effective date or to withhold an amendment after its effective date.

Where a clause's predicate is expressible in propositional form, its
implementation may factor over the propositional structure. This document does not
require the release gate to preserve the propositional structure in its internal
representation.

A release gate that evaluates this clause through pattern-matching over the raw
YAML text rather than through predicate evaluation over the parsed model has taken a
shortcut that is not authorized by this document. All clauses evaluate against the
parsed model.

The set of reason codes emitted for a single service under this clause is a
singleton: either the code appears or it does not, and the code's presence indicates
a violation of the clause without further modality.

The applicability tests stated elsewhere in this document produce Boolean values
per (service, clause) pair. A release gate that produces multi-valued applicability
results — for example, "partially applies" — has misinterpreted this document. All
applicability results are Boolean.

Downstream tooling may cache a release gate's decisions but MUST NOT rely on
cached decisions across requests whose relevant inputs differ. The release gate
itself does not implement a decision cache in this edition.

A release gate's evaluation is deterministic given fixed inputs. Repeated
requests with byte-identical repository state, DB state, tag evidence, and request
body MUST yield byte-identical response bodies. Sources of non-determinism (random
sort orders, iteration-order variance) are nonconformant.

The connection contract stated elsewhere in this document is the sole basis for
the release gate's access to the approvals database. A release gate that establishes
a connection through any other mechanism has not applied the contract.

The reasoning trail from raw compose file to emitted reason is:
parse → resolve merge → enumerate services → for each service, evaluate applicable
clauses → collect reasons → filter through exception windows → sort per amendment on
reason ordering → serialize. This clause participates at the "evaluate applicable
clauses" step.

A release gate that presents its decision under a schema version other than the
one this document defines has produced a response whose interpretation is not
controlled by this document. Downstream tooling that receives such a response has no
obligation under this document.

Amendments to this clause enter force at the amendment's effective date. Nothing
in the base clause text authorizes a release gate to apply an amendment before its
effective date or to withhold an amendment after its effective date.

## Chapter 32. Response shape

A release gate emits its decision as a JSON document via HTTP. The response is
UTF-8 encoded without a byte-order mark. Object keys at every level are sorted in
ascending lexicographic byte order. Strings contain only literal ASCII where the
underlying value is ASCII; non-ASCII characters are permitted where the underlying
value is non-ASCII. No trailing whitespace appears at the end of any line.

### §32.1 Approve response

A response indicating approval is a JSON object with two keys: `decision`,
whose value is the string `approve`, and `reasons`, whose value is the empty array.
No other keys appear; the reasons array is always empty on approval.

A release gate that presents its decision under a schema version other than the
one this document defines has produced a response whose interpretation is not
controlled by this document. Downstream tooling that receives such a response has no
obligation under this document.

Amendments to this clause enter force at the amendment's effective date. Nothing
in the base clause text authorizes a release gate to apply an amendment before its
effective date or to withhold an amendment after its effective date.

Where a clause's predicate is expressible in propositional form, its
implementation may factor over the propositional structure. This document does not
require the release gate to preserve the propositional structure in its internal
representation.

### §32.2 Deny response

A response indicating denial is a JSON object with two keys: `decision`, whose
value is the string `deny`, and `reasons`, whose value is a non-empty array of reason
objects. Each reason object has three keys: `clauseId`, whose value is a clause
identifier of the form `<§X.Y>`; `code`, whose value is a reason code of the form
`<CDSS-CATEGORY-NNN>`; and `service`, whose value is either the offending service name
or the empty string when the reason pertains to the repository or the tag rather than
to a specific service. The reasons array is sorted per the amendment on reason
ordering. Every reason object has exactly these three keys; no reason object carries
additional keys or omits any of these keys.

Amendments to this clause enter force at the amendment's effective date. Nothing
in the base clause text authorizes a release gate to apply an amendment before its
effective date or to withhold an amendment after its effective date.

Where a clause's predicate is expressible in propositional form, its
implementation may factor over the propositional structure. This document does not
require the release gate to preserve the propositional structure in its internal
representation.

A release gate that evaluates this clause through pattern-matching over the raw
YAML text rather than through predicate evaluation over the parsed model has taken a
shortcut that is not authorized by this document. All clauses evaluate against the
parsed model.

### §32.3 Reasons that pertain to the tag

A reason that pertains to the tag rather than to any specific service has an
empty `service` string. This applies to reasons whose clause identifier is a key
management or hooks clause. Under the amendment on reason ordering the empty string
sorts first within its code group, so tag-level reasons appear before service-level
reasons that share a code prefix. Since key and hook reason codes are distinct from
service reason codes, this ordering is not usually observable, but implementations
follow it regardless.

Where a clause's predicate is expressible in propositional form, its
implementation may factor over the propositional structure. This document does not
require the release gate to preserve the propositional structure in its internal
representation.

A release gate that evaluates this clause through pattern-matching over the raw
YAML text rather than through predicate evaluation over the parsed model has taken a
shortcut that is not authorized by this document. All clauses evaluate against the
parsed model.

The set of reason codes emitted for a single service under this clause is a
singleton: either the code appears or it does not, and the code's presence indicates
a violation of the clause without further modality.

## Appendix A. Amendments

The amendments below supersede provisions of the substantive chapters as of the
effective date recorded in the amendment's header. Their effect is governed by the
precedence rule of Chapter 2.

### Amendment 3

_Effective: 2025-11-04T00:00:00Z_

When a decision denies a release, the `reasons` array in the response MUST be sorted first by `code` in ascending lexicographic order, then by `service` in ascending lexicographic order. Reasons that pertain to the repository or the tag rather than a specific service use the empty string for `service` and sort first within their code group.

A well-formed evaluation reports each service exactly once. Duplicate service
declarations across files are reconciled by the merge procedure and produce a single
service in the evaluated model.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

Where this section speaks of the "resolved" value of a service attribute, it refers
to the value produced by the merge procedure applied to the participating files. A
release gate that considers only one participating file has not resolved the service
attribute for the purposes of this section.

A release gate MAY emit a warning where guidance in this section is not followed
even though nonconformance is not established; the warning is not part of the reasons
array in the denial response. The precise form of warnings is left to the release gate
implementation and is not constrained by this standard.

### Amendment 7

_Effective: 2026-05-01T00:00:00Z_

_Supersedes: §12.3_

The §12.3 exemption for cache-class services is withdrawn for services classified as web-tier by port zone under §1.3. A service that is cache-class per §3.5 AND is web-tier by port-zone derivation (having declared a non-web `cdss.tier` label but published a host-side port in the web zone of §1.2) MUST set `read_only: true` on par with any other web-tier service. Cache-class services that are web-tier by label alone, or that are not web-tier at all, remain outside the scope of §12.3.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

The compose model as resolved is a data structure with a finite number of shapes.
This document does not enumerate the shapes; it enumerates predicates over the shapes,
and a release gate is expected to accommodate any shape the merge procedure can
produce. Shapes that are pathological (recursive anchors resolved to themselves,
unbounded string lengths, and so on) are outside the scope of this document and are
signaled as request errors, not as denials.

Guidance in this section does not extend to any obligation stated normatively
elsewhere. Where a subsequent chapter's clause reaches an obligation similar to this
section's guidance, the clause governs and the guidance loses independent effect.

## Appendix B. Non-waivable clauses

The following clause identifiers are non-waivable. An exception window naming
any of them is silently ineffective.

- `§8.1`
- `§14.5`

A release gate that evaluates this clause through pattern-matching over the raw
YAML text rather than through predicate evaluation over the parsed model has taken a
shortcut that is not authorized by this document. All clauses evaluate against the
parsed model.

The set of reason codes emitted for a single service under this clause is a
singleton: either the code appears or it does not, and the code's presence indicates
a violation of the clause without further modality.

Where two clauses of this document could each cover a given configuration
attribute, both clauses apply and each emits its own reason if violated. There is no
"more specific" clause that displaces a "less specific" one; the two clauses
coexist.

## Appendix C. Capability allowlist

The following Linux capabilities MAY appear in `cap_add` for a service that has
also declared `cap_drop: [ALL]`. Capabilities not in this list MUST NOT appear in
`cap_add`. A service whose `cap_add` includes a non-allowlisted capability denies
under the applicable clause of Chapter 9.

- `NET_BIND_SERVICE`
- `CHOWN`
- `SETUID`
- `SETGID`
- `DAC_OVERRIDE`

The set of reason codes emitted for a single service under this clause is a
singleton: either the code appears or it does not, and the code's presence indicates
a violation of the clause without further modality.

Where two clauses of this document could each cover a given configuration
attribute, both clauses apply and each emits its own reason if violated. There is no
"more specific" clause that displaces a "less specific" one; the two clauses
coexist.

A release gate MAY, at its discretion, emit machine-readable diagnostics
alongside its response body. Diagnostics are outside the scope of this document and
must not appear inside the response body; they belong at a separate transport-level
channel.

## Appendix D. Zone declaration table (reproduced)

This appendix reproduces the zone declaration table of §1.2 for readers who
consult Chapter 15 or Chapter 22 without having read Chapter 1. The reproduction is
non-authoritative; §1.2 governs.

| Zone | Host-side ports |
| --- | --- |
| `web` | 80, 443, 6379, 8080, 8443, 8444, 8445, 8446, 8000–8999 inclusive |
| `internal` | 9000–9999 inclusive |
| `loopback` | 7000–7999 inclusive |

Where two clauses of this document could each cover a given configuration
attribute, both clauses apply and each emits its own reason if violated. There is no
"more specific" clause that displaces a "less specific" one; the two clauses
coexist.

A release gate MAY, at its discretion, emit machine-readable diagnostics
alongside its response body. Diagnostics are outside the scope of this document and
must not appear inside the response body; they belong at a separate transport-level
channel.

The observable behaviour of a release gate that satisfies this clause is
independent of its internal caching strategy. The release gate is not required to
disclose its caching strategy in the response.

## Appendix E. Interpretation notes

This appendix collects procedural material of narrow interest that would
otherwise disrupt the narrative flow of the substantive chapters. Nothing in this
appendix creates new obligations; the material serves to record machinery by which
obligations stated elsewhere are applied.

### §E.1 Note

Clause-evaluation order for a single service is not prescribed by this document.
Two release-gate implementations that emit identical reason arrays across every
request are considered functionally equivalent regardless of their internal iteration
strategy.

The obligation stated above operates on the resolved compose model. It applies to
every service in the enumeration produced by the merge described elsewhere in this
document; the evaluation does not distinguish between services declared in one file and
services declared only in another.

The predicate stated above is defined solely in terms of the compose model as
resolved. It does not inspect runtime state, container properties, or registry metadata.
A release gate that evaluates the predicate by any means other than inspection of the
resolved compose model is nonconformant with this standard.

When a release gate denies a release on the basis of this clause, the response
carries a reason whose `code` and `clauseId` fields identify the clause and whose
`service` field names the offending service.

Evaluation of this clause is performed independently for each service in the
enumerated model. A service that violates the clause emits exactly one reason for it,
regardless of how many distinct violation surfaces the service presents.

Nothing in this clause overrides the general precedence rule of this document.
Where an amendment supersedes the clause, the amended text governs for the service
class the amendment addresses; the underlying clause continues to govern for all other
service classes.

A brief note on scoping: applicability of this clause resolves against
service-class predicates that live elsewhere in the definitions chapter and elsewhere
in the approvals database. Service names are not authoritative for classification.

Nothing in this section constitutes an obligation on any deployment. The section is
provided as guidance and as a shared vocabulary for downstream tooling. A deployment
that does not follow the guidance in this section is not thereby nonconformant with
this standard.

The provisions of this section are stated at the level of the compose model rather
than at the level of any container runtime. A release gate is not required to consult
external systems to apply this section.

Where this section speaks of the "resolved" value of a service attribute, it refers
to the value produced by the merge procedure applied to the participating files. A
release gate that considers only one participating file has not resolved the service
attribute for the purposes of this section.

A release gate MAY emit a warning where guidance in this section is not followed
even though nonconformance is not established; the warning is not part of the reasons
array in the denial response. The precise form of warnings is left to the release gate
implementation and is not constrained by this standard.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

A release gate MAY implement this clause in any order relative to other clauses,
provided the output for every request is identical to the output an implementation
following this document's stated ordering would produce.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

### §E.2 Note

Independence of clause evaluation is a design choice: a service that fails two
clauses emits two reasons, without one being treated as "primary" and the other as
suppressed. Implementations that filter reason arrays to a single primary reason are
nonconformant.

Evaluation of this clause is performed independently for each service in the
enumerated model. A service that violates the clause emits exactly one reason for it,
regardless of how many distinct violation surfaces the service presents.

Nothing in this clause overrides the general precedence rule of this document.
Where an amendment supersedes the clause, the amended text governs for the service
class the amendment addresses; the underlying clause continues to govern for all other
service classes.

A brief note on scoping: applicability of this clause resolves against
service-class predicates that live elsewhere in the definitions chapter and elsewhere
in the approvals database. Service names are not authoritative for classification.

A well-formed evaluation reports each service exactly once. Duplicate service
declarations across files are reconciled by the merge procedure and produce a single
service in the evaluated model.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

The provisions of this section are stated at the level of the compose model rather
than at the level of any container runtime. A release gate is not required to consult
external systems to apply this section.

Where this section speaks of the "resolved" value of a service attribute, it refers
to the value produced by the merge procedure applied to the participating files. A
release gate that considers only one participating file has not resolved the service
attribute for the purposes of this section.

A release gate MAY emit a warning where guidance in this section is not followed
even though nonconformance is not established; the warning is not part of the reasons
array in the denial response. The precise form of warnings is left to the release gate
implementation and is not constrained by this standard.

The distinction between an obligation and guidance under this standard is
morphological in the surrounding prose. Obligations use the modal verb `MUST`, its
negation `MUST NOT`, or the imperative form. Guidance uses `SHOULD`, `SHOULD NOT`, or
`MAY`. A reader who is uncertain which modality applies is directed to the surrounding
sentence, which will resolve the modality in every substantive clause of this
document.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

### §E.3 Note

Exception-window rows in the approvals database take effect at `starts_at` and
lapse at `ends_at`; they are not retroactive. A request whose `evaluationTime`
predates the window's `starts_at` is unaffected even where the underlying deployment
would otherwise fall within scope.

A well-formed evaluation reports each service exactly once. Duplicate service
declarations across files are reconciled by the merge procedure and produce a single
service in the evaluated model.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

A release gate MAY implement this clause in any order relative to other clauses,
provided the output for every request is identical to the output an implementation
following this document's stated ordering would produce.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

Where this section speaks of the "resolved" value of a service attribute, it refers
to the value produced by the merge procedure applied to the participating files. A
release gate that considers only one participating file has not resolved the service
attribute for the purposes of this section.

A release gate MAY emit a warning where guidance in this section is not followed
even though nonconformance is not established; the warning is not part of the reasons
array in the denial response. The precise form of warnings is left to the release gate
implementation and is not constrained by this standard.

The distinction between an obligation and guidance under this standard is
morphological in the surrounding prose. Obligations use the modal verb `MUST`, its
negation `MUST NOT`, or the imperative form. Guidance uses `SHOULD`, `SHOULD NOT`, or
`MAY`. A reader who is uncertain which modality applies is directed to the surrounding
sentence, which will resolve the modality in every substantive clause of this
document.

The compose model as resolved is a data structure with a finite number of shapes.
This document does not enumerate the shapes; it enumerates predicates over the shapes,
and a release gate is expected to accommodate any shape the merge procedure can
produce. Shapes that are pathological (recursive anchors resolved to themselves,
unbounded string lengths, and so on) are outside the scope of this document and are
signaled as request errors, not as denials.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

### §E.4 Note

External secret-store references are outside the scope of this edition. This
document addresses the syntactic form of the `environment:` block only; a service
that fetches secrets at container runtime from a mounted secret store or an
identity-federated retrieval does not thereby violate the secret-material clause,
provided its `environment:` block itself carries no secret-named key.

A release gate MAY implement this clause in any order relative to other clauses,
provided the output for every request is identical to the output an implementation
following this document's stated ordering would produce.

This clause is stated in the imperative form; where the surrounding prose uses
`MUST` or `MUST NOT`, the modality is normative. `SHOULD` and `MAY` are used elsewhere
only for guidance and never carry weight in a denial.

The interpretive framework of Chapter 2 governs any apparent conflict between the
provision above and provisions elsewhere in this document. Nothing in this section
authorizes an interpretation that reverses the precedence order.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

A release gate MAY emit a warning where guidance in this section is not followed
even though nonconformance is not established; the warning is not part of the reasons
array in the denial response. The precise form of warnings is left to the release gate
implementation and is not constrained by this standard.

The distinction between an obligation and guidance under this standard is
morphological in the surrounding prose. Obligations use the modal verb `MUST`, its
negation `MUST NOT`, or the imperative form. Guidance uses `SHOULD`, `SHOULD NOT`, or
`MAY`. A reader who is uncertain which modality applies is directed to the surrounding
sentence, which will resolve the modality in every substantive clause of this
document.

The compose model as resolved is a data structure with a finite number of shapes.
This document does not enumerate the shapes; it enumerates predicates over the shapes,
and a release gate is expected to accommodate any shape the merge procedure can
produce. Shapes that are pathological (recursive anchors resolved to themselves,
unbounded string lengths, and so on) are outside the scope of this document and are
signaled as request errors, not as denials.

Guidance in this section does not extend to any obligation stated normatively
elsewhere. Where a subsequent chapter's clause reaches an obligation similar to this
section's guidance, the clause governs and the guidance loses independent effect.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

Where a clause admits an exception via the exception-window mechanism, that
exception is subject to the temporal and non-waivable-clause rules stated in the
exception-window chapter. The clause itself does not enumerate its exceptions.

A release gate may cache read-only data across requests only where doing so
cannot alter the outcome of any request; where a cache would observe a different DB
state than a fresh read, the cache is not usable for this clause. In practice this
edition contemplates fresh reads per request.

The provisions of this section do not authorize a release gate to reach any
external system. All evidence is local: repository files, approvals database, and
signature bytes accompanying the tag.

### §E.5 Note

Service names are compared byte-identically. Two names differing in any byte are
two distinct services in this document; downstream tooling that folds case at service
lookup diverges from this treatment and is not aligned with this edition.

This clause does not depend on the evaluation of any other clause. A release gate
that short-circuits on the first violation for a service has not emitted the full
reason array required by this document.

Where this clause references terms defined in the definitions chapter, the
definitional predicates control. A release gate that resolves a term by any other
method has misapplied this clause.

The phrasing of this clause does not privilege any particular implementation
strategy. A release gate that computes the predicate through a different data flow
than the one implied by the clause text is conformant so long as it produces the same
output.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

The distinction between an obligation and guidance under this standard is
morphological in the surrounding prose. Obligations use the modal verb `MUST`, its
negation `MUST NOT`, or the imperative form. Guidance uses `SHOULD`, `SHOULD NOT`, or
`MAY`. A reader who is uncertain which modality applies is directed to the surrounding
sentence, which will resolve the modality in every substantive clause of this
document.

The compose model as resolved is a data structure with a finite number of shapes.
This document does not enumerate the shapes; it enumerates predicates over the shapes,
and a release gate is expected to accommodate any shape the merge procedure can
produce. Shapes that are pathological (recursive anchors resolved to themselves,
unbounded string lengths, and so on) are outside the scope of this document and are
signaled as request errors, not as denials.

Guidance in this section does not extend to any obligation stated normatively
elsewhere. Where a subsequent chapter's clause reaches an obligation similar to this
section's guidance, the clause governs and the guidance loses independent effect.

A release gate that adds obligations beyond those this document states is not for
that reason nonconformant; the release gate simply serves a stricter policy than this
edition specifies. Conversely, a release gate that omits obligations this document
states is nonconformant regardless of how narrow the omission is.

A release gate may cache read-only data across requests only where doing so
cannot alter the outcome of any request; where a cache would observe a different DB
state than a fresh read, the cache is not usable for this clause. In practice this
edition contemplates fresh reads per request.

The provisions of this section do not authorize a release gate to reach any
external system. All evidence is local: repository files, approvals database, and
signature bytes accompanying the tag.

A release gate may log its decisions for audit purposes. Such logs are outside
the scope of this document; the emitted response body is the only artifact that
receives normative constraints.

Where this clause refers to "the tag", the reference is to the specific tag
named in the request body. A release gate MUST NOT re-select a different tag from the
repository even if a more recent tag would satisfy the clause.

The order in which services appear in the response's reason array is governed by
the amendment on reason ordering. Nothing in this clause imposes a service-order
constraint of its own.

### §E.6 Note

The empty compose model and the absent compose model are semantically distinct.
The empty case — a participating file exists but declares no services — differs from
the absent case — no participating file exists — although this edition treats both
identically for the purpose of the compose-model-absence clause.

Downstream tooling may consume the emitted reason array and derive higher-level
signals from it; this document does not constrain such derivations. The release gate
itself, however, emits exactly the reasons the clauses of this document produce.

A release gate that treats one participating file as authoritative and the other
as advisory has departed from the merge procedure and cannot correctly evaluate this
clause. Both participating files are inputs to the merge on an equal footing except
where the merge rules themselves distinguish base from override.

The obligations of this clause are not softened by the presence of a benign
default at the container-runtime layer. This document reasons about the compose model,
not about runtime behaviour, and permissive runtime defaults do not affect a
compose-time obligation.

Where a clause admits an exception via the exception-window mechanism, that
exception is subject to the temporal and non-waivable-clause rules stated in the
exception-window chapter. The clause itself does not enumerate its exceptions.

A release gate may cache read-only data across requests only where doing so
cannot alter the outcome of any request; where a cache would observe a different DB
state than a fresh read, the cache is not usable for this clause. In practice this
edition contemplates fresh reads per request.

The provisions of this section do not authorize a release gate to reach any
external system. All evidence is local: repository files, approvals database, and
signature bytes accompanying the tag.

The compose model as resolved is a data structure with a finite number of shapes.
This document does not enumerate the shapes; it enumerates predicates over the shapes,
and a release gate is expected to accommodate any shape the merge procedure can
produce. Shapes that are pathological (recursive anchors resolved to themselves,
unbounded string lengths, and so on) are outside the scope of this document and are
signaled as request errors, not as denials.

Guidance in this section does not extend to any obligation stated normatively
elsewhere. Where a subsequent chapter's clause reaches an obligation similar to this
section's guidance, the clause governs and the guidance loses independent effect.

A release gate that adds obligations beyond those this document states is not for
that reason nonconformant; the release gate simply serves a stricter policy than this
edition specifies. Conversely, a release gate that omits obligations this document
states is nonconformant regardless of how narrow the omission is.

The material in this section is stable in the sense that a future edition would
not narrow its content silently. Guidance may become obligation across editions, but
the guidance itself is preserved in the succeeding edition to permit downstream tools
to reason about the transition.

Where this clause refers to "the tag", the reference is to the specific tag
named in the request body. A release gate MUST NOT re-select a different tag from the
repository even if a more recent tag would satisfy the clause.

The order in which services appear in the response's reason array is governed by
the amendment on reason ordering. Nothing in this clause imposes a service-order
constraint of its own.

A release gate whose implementation of this clause depends on the order of
services in either participating file has misread this document; service order is
non-normative.

The scope of this clause is limited to the compose model. A release gate MUST
NOT extend the clause to non-compose repository files (Dockerfile, entrypoint
scripts, or manifests for other orchestrators), even where those files carry
information adjacent to the clause's subject.

Enforcement of this clause is neutral with respect to service origin. A service
introduced by the override file is evaluated identically to a service present in the
base file; nothing in the clause privileges base declarations.

### §E.7 Note

A recurring implementation concern is the treatment of `depends_on` under the
merge procedure. `depends_on` is a list-valued attribute, and this document's list
rule directs the override list to replace the base list wholesale — an outcome that
sometimes surprises implementers who assume `depends_on` merges elementwise.

Where a clause admits an exception via the exception-window mechanism, that
exception is subject to the temporal and non-waivable-clause rules stated in the
exception-window chapter. The clause itself does not enumerate its exceptions.

A release gate may cache read-only data across requests only where doing so
cannot alter the outcome of any request; where a cache would observe a different DB
state than a fresh read, the cache is not usable for this clause. In practice this
edition contemplates fresh reads per request.

The provisions of this section do not authorize a release gate to reach any
external system. All evidence is local: repository files, approvals database, and
signature bytes accompanying the tag.

A release gate may log its decisions for audit purposes. Such logs are outside
the scope of this document; the emitted response body is the only artifact that
receives normative constraints.

Where this clause refers to "the tag", the reference is to the specific tag
named in the request body. A release gate MUST NOT re-select a different tag from the
repository even if a more recent tag would satisfy the clause.

The order in which services appear in the response's reason array is governed by
the amendment on reason ordering. Nothing in this clause imposes a service-order
constraint of its own.

Guidance in this section does not extend to any obligation stated normatively
elsewhere. Where a subsequent chapter's clause reaches an obligation similar to this
section's guidance, the clause governs and the guidance loses independent effect.

A release gate that adds obligations beyond those this document states is not for
that reason nonconformant; the release gate simply serves a stricter policy than this
edition specifies. Conversely, a release gate that omits obligations this document
states is nonconformant regardless of how narrow the omission is.

The material in this section is stable in the sense that a future edition would
not narrow its content silently. Guidance may become obligation across editions, but
the guidance itself is preserved in the succeeding edition to permit downstream tools
to reason about the transition.

This section's provisions are directed at the release gate and, through it, at
the deployment repository. They are not directed at other tooling in the
release-management pipeline; downstream consumers of the emitted response are outside
the scope of this section.

The scope of this clause is limited to the compose model. A release gate MUST
NOT extend the clause to non-compose repository files (Dockerfile, entrypoint
scripts, or manifests for other orchestrators), even where those files carry
information adjacent to the clause's subject.

Enforcement of this clause is neutral with respect to service origin. A service
introduced by the override file is evaluated identically to a service present in the
base file; nothing in the clause privileges base declarations.

The reasoning trail from raw compose file to emitted reason is:
parse → resolve merge → enumerate services → for each service, evaluate applicable
clauses → collect reasons → filter through exception windows → sort per amendment on
reason ordering → serialize. This clause participates at the "evaluate applicable
clauses" step.

A release gate that presents its decision under a schema version other than the
one this document defines has produced a response whose interpretation is not
controlled by this document. Downstream tooling that receives such a response has no
obligation under this document.

Amendments to this clause enter force at the amendment's effective date. Nothing
in the base clause text authorizes a release gate to apply an amendment before its
effective date or to withhold an amendment after its effective date.

### §E.8 Note

Anchor identity is not preserved across files. Each participating file is
resolved independently before the merge inspects it; the release gate operates on the
resolved documents, and no release gate that carries anchor state from one document
into another has followed this edition.

A release gate may log its decisions for audit purposes. Such logs are outside
the scope of this document; the emitted response body is the only artifact that
receives normative constraints.

Where this clause refers to "the tag", the reference is to the specific tag
named in the request body. A release gate MUST NOT re-select a different tag from the
repository even if a more recent tag would satisfy the clause.

The order in which services appear in the response's reason array is governed by
the amendment on reason ordering. Nothing in this clause imposes a service-order
constraint of its own.

A release gate whose implementation of this clause depends on the order of
services in either participating file has misread this document; service order is
non-normative.

The scope of this clause is limited to the compose model. A release gate MUST
NOT extend the clause to non-compose repository files (Dockerfile, entrypoint
scripts, or manifests for other orchestrators), even where those files carry
information adjacent to the clause's subject.

Enforcement of this clause is neutral with respect to service origin. A service
introduced by the override file is evaluated identically to a service present in the
base file; nothing in the clause privileges base declarations.

A release gate that adds obligations beyond those this document states is not for
that reason nonconformant; the release gate simply serves a stricter policy than this
edition specifies. Conversely, a release gate that omits obligations this document
states is nonconformant regardless of how narrow the omission is.

The material in this section is stable in the sense that a future edition would
not narrow its content silently. Guidance may become obligation across editions, but
the guidance itself is preserved in the succeeding edition to permit downstream tools
to reason about the transition.

This section's provisions are directed at the release gate and, through it, at
the deployment repository. They are not directed at other tooling in the
release-management pipeline; downstream consumers of the emitted response are outside
the scope of this section.

A release gate that emits reasons whose codes do not appear in this document is
nonconformant. The set of reason codes is closed by the edition of this document the
release gate ships; extending the set is a matter for future editions, not for
release-gate implementations.

A release gate that presents its decision under a schema version other than the
one this document defines has produced a response whose interpretation is not
controlled by this document. Downstream tooling that receives such a response has no
obligation under this document.

Amendments to this clause enter force at the amendment's effective date. Nothing
in the base clause text authorizes a release gate to apply an amendment before its
effective date or to withhold an amendment after its effective date.

Where a clause's predicate is expressible in propositional form, its
implementation may factor over the propositional structure. This document does not
require the release gate to preserve the propositional structure in its internal
representation.

A release gate that evaluates this clause through pattern-matching over the raw
YAML text rather than through predicate evaluation over the parsed model has taken a
shortcut that is not authorized by this document. All clauses evaluate against the
parsed model.

The set of reason codes emitted for a single service under this clause is a
singleton: either the code appears or it does not, and the code's presence indicates
a violation of the clause without further modality.

### §E.9 Note

A recurring implementation concern is the treatment of syntactically malformed
YAML in either participating file. Malformed YAML is a request error signaled with
HTTP 400 in this edition; no denial-body reason code is emitted for it.

A release gate whose implementation of this clause depends on the order of
services in either participating file has misread this document; service order is
non-normative.

The scope of this clause is limited to the compose model. A release gate MUST
NOT extend the clause to non-compose repository files (Dockerfile, entrypoint
scripts, or manifests for other orchestrators), even where those files carry
information adjacent to the clause's subject.

Enforcement of this clause is neutral with respect to service origin. A service
introduced by the override file is evaluated identically to a service present in the
base file; nothing in the clause privileges base declarations.

The reasoning trail from raw compose file to emitted reason is:
parse → resolve merge → enumerate services → for each service, evaluate applicable
clauses → collect reasons → filter through exception windows → sort per amendment on
reason ordering → serialize. This clause participates at the "evaluate applicable
clauses" step.

A release gate that presents its decision under a schema version other than the
one this document defines has produced a response whose interpretation is not
controlled by this document. Downstream tooling that receives such a response has no
obligation under this document.

Amendments to this clause enter force at the amendment's effective date. Nothing
in the base clause text authorizes a release gate to apply an amendment before its
effective date or to withhold an amendment after its effective date.

The material in this section is stable in the sense that a future edition would
not narrow its content silently. Guidance may become obligation across editions, but
the guidance itself is preserved in the succeeding edition to permit downstream tools
to reason about the transition.

This section's provisions are directed at the release gate and, through it, at
the deployment repository. They are not directed at other tooling in the
release-management pipeline; downstream consumers of the emitted response are outside
the scope of this section.

A release gate that emits reasons whose codes do not appear in this document is
nonconformant. The set of reason codes is closed by the edition of this document the
release gate ships; extending the set is a matter for future editions, not for
release-gate implementations.

Nothing in this section authorizes a release gate to modify the repository, the
approvals database, or any file the request references. The release gate is purely a
reader; any implementation that writes to these inputs has departed from this
document.

A release gate that evaluates this clause through pattern-matching over the raw
YAML text rather than through predicate evaluation over the parsed model has taken a
shortcut that is not authorized by this document. All clauses evaluate against the
parsed model.

The set of reason codes emitted for a single service under this clause is a
singleton: either the code appears or it does not, and the code's presence indicates
a violation of the clause without further modality.

Where two clauses of this document could each cover a given configuration
attribute, both clauses apply and each emits its own reason if violated. There is no
"more specific" clause that displaces a "less specific" one; the two clauses
coexist.

A release gate MAY, at its discretion, emit machine-readable diagnostics
alongside its response body. Diagnostics are outside the scope of this document and
must not appear inside the response body; they belong at a separate transport-level
channel.

The observable behaviour of a release gate that satisfies this clause is
independent of its internal caching strategy. The release gate is not required to
disclose its caching strategy in the response.

### §E.10 Note

Image-reference strings are not canonicalized before evaluation. The
`image` attribute value is compared as a literal string against the regular
expression stated in the applicable clause; whitespace, tag-shorthand, and
digest-shorthand forms are not normalized by the release gate.

The reasoning trail from raw compose file to emitted reason is:
parse → resolve merge → enumerate services → for each service, evaluate applicable
clauses → collect reasons → filter through exception windows → sort per amendment on
reason ordering → serialize. This clause participates at the "evaluate applicable
clauses" step.

A release gate that presents its decision under a schema version other than the
one this document defines has produced a response whose interpretation is not
controlled by this document. Downstream tooling that receives such a response has no
obligation under this document.

Amendments to this clause enter force at the amendment's effective date. Nothing
in the base clause text authorizes a release gate to apply an amendment before its
effective date or to withhold an amendment after its effective date.

Where a clause's predicate is expressible in propositional form, its
implementation may factor over the propositional structure. This document does not
require the release gate to preserve the propositional structure in its internal
representation.

A release gate that evaluates this clause through pattern-matching over the raw
YAML text rather than through predicate evaluation over the parsed model has taken a
shortcut that is not authorized by this document. All clauses evaluate against the
parsed model.

The set of reason codes emitted for a single service under this clause is a
singleton: either the code appears or it does not, and the code's presence indicates
a violation of the clause without further modality.

This section's provisions are directed at the release gate and, through it, at
the deployment repository. They are not directed at other tooling in the
release-management pipeline; downstream consumers of the emitted response are outside
the scope of this section.

A release gate that emits reasons whose codes do not appear in this document is
nonconformant. The set of reason codes is closed by the edition of this document the
release gate ships; extending the set is a matter for future editions, not for
release-gate implementations.

Nothing in this section authorizes a release gate to modify the repository, the
approvals database, or any file the request references. The release gate is purely a
reader; any implementation that writes to these inputs has departed from this
document.

The applicability tests stated elsewhere in this document produce Boolean values
per (service, clause) pair. A release gate that produces multi-valued applicability
results — for example, "partially applies" — has misinterpreted this document. All
applicability results are Boolean.

A release gate MAY, at its discretion, emit machine-readable diagnostics
alongside its response body. Diagnostics are outside the scope of this document and
must not appear inside the response body; they belong at a separate transport-level
channel.

The observable behaviour of a release gate that satisfies this clause is
independent of its internal caching strategy. The release gate is not required to
disclose its caching strategy in the response.

This clause imposes no obligation on the tooling that publishes releases; the
obligation runs to the release gate alone. Downstream tooling MAY implement any
additional constraints of its own.

The clause does not distinguish between a first-time repository presentation
and a repeat presentation of the same repository state. A repository whose state has
not changed since a previous successful release-gate evaluation is evaluated again on
its merits at each request.

A release gate MAY be implemented as multiple cooperating processes; nothing
in this clause requires a single-process implementation. Cross-process communication
is outside the scope of this document.

### §E.11 Note

Empty `cap_drop` lists do not satisfy the applicable capability clause: the
clause requires the literal element `ALL`, and its absence — including in an
otherwise-empty list — is a violation. An empty `cap_add` list is permitted; it adds
no capabilities.

Where a clause's predicate is expressible in propositional form, its
implementation may factor over the propositional structure. This document does not
require the release gate to preserve the propositional structure in its internal
representation.

A release gate that evaluates this clause through pattern-matching over the raw
YAML text rather than through predicate evaluation over the parsed model has taken a
shortcut that is not authorized by this document. All clauses evaluate against the
parsed model.

The set of reason codes emitted for a single service under this clause is a
singleton: either the code appears or it does not, and the code's presence indicates
a violation of the clause without further modality.

Where two clauses of this document could each cover a given configuration
attribute, both clauses apply and each emits its own reason if violated. There is no
"more specific" clause that displaces a "less specific" one; the two clauses
coexist.

A release gate MAY, at its discretion, emit machine-readable diagnostics
alongside its response body. Diagnostics are outside the scope of this document and
must not appear inside the response body; they belong at a separate transport-level
channel.

The observable behaviour of a release gate that satisfies this clause is
independent of its internal caching strategy. The release gate is not required to
disclose its caching strategy in the response.

A release gate that emits reasons whose codes do not appear in this document is
nonconformant. The set of reason codes is closed by the edition of this document the
release gate ships; extending the set is a matter for future editions, not for
release-gate implementations.

Nothing in this section authorizes a release gate to modify the repository, the
approvals database, or any file the request references. The release gate is purely a
reader; any implementation that writes to these inputs has departed from this
document.

The applicability tests stated elsewhere in this document produce Boolean values
per (service, clause) pair. A release gate that produces multi-valued applicability
results — for example, "partially applies" — has misinterpreted this document. All
applicability results are Boolean.

Downstream tooling may cache a release gate's decisions but MUST NOT rely on
cached decisions across requests whose relevant inputs differ. The release gate
itself does not implement a decision cache in this edition.

The clause does not distinguish between a first-time repository presentation
and a repeat presentation of the same repository state. A repository whose state has
not changed since a previous successful release-gate evaluation is evaluated again on
its merits at each request.

A release gate MAY be implemented as multiple cooperating processes; nothing
in this clause requires a single-process implementation. Cross-process communication
is outside the scope of this document.

The transport-level HTTP contract is described elsewhere in this document.
This clause does not modify the transport-level constraints; a release gate that
mishandles the transport layer has departed from this document independently of any
clause-level obligation.

Reasons emitted by this clause carry the clause's identifier. A release gate
that emits a reason without a clause identifier under any circumstance has produced
a response that is not compliant with the response-shape chapter of this document.

The clause does not imply a temporal ordering on repository history. Repositories
are evaluated at rest as of the request time; previous states of the repository do
not enter the evaluation.

### §E.12 Note

A recurring implementation concern is the ordering of database reads within a
request. Reads over `approved_keys`, `exception_windows`, and `infra_registry` may
proceed in any order provided the three reads observe consistent state; the
connection contract requires a single connection opened once and closed before the
response is sent.

Where two clauses of this document could each cover a given configuration
attribute, both clauses apply and each emits its own reason if violated. There is no
"more specific" clause that displaces a "less specific" one; the two clauses
coexist.

A release gate MAY, at its discretion, emit machine-readable diagnostics
alongside its response body. Diagnostics are outside the scope of this document and
must not appear inside the response body; they belong at a separate transport-level
channel.

The observable behaviour of a release gate that satisfies this clause is
independent of its internal caching strategy. The release gate is not required to
disclose its caching strategy in the response.

This clause imposes no obligation on the tooling that publishes releases; the
obligation runs to the release gate alone. Downstream tooling MAY implement any
additional constraints of its own.

The clause does not distinguish between a first-time repository presentation
and a repeat presentation of the same repository state. A repository whose state has
not changed since a previous successful release-gate evaluation is evaluated again on
its merits at each request.

A release gate MAY be implemented as multiple cooperating processes; nothing
in this clause requires a single-process implementation. Cross-process communication
is outside the scope of this document.

Nothing in this section authorizes a release gate to modify the repository, the
approvals database, or any file the request references. The release gate is purely a
reader; any implementation that writes to these inputs has departed from this
document.

The applicability tests stated elsewhere in this document produce Boolean values
per (service, clause) pair. A release gate that produces multi-valued applicability
results — for example, "partially applies" — has misinterpreted this document. All
applicability results are Boolean.

Downstream tooling may cache a release gate's decisions but MUST NOT rely on
cached decisions across requests whose relevant inputs differ. The release gate
itself does not implement a decision cache in this edition.

A release gate's evaluation is deterministic given fixed inputs. Repeated
requests with byte-identical repository state, DB state, tag evidence, and request
body MUST yield byte-identical response bodies. Sources of non-determinism (random
sort orders, iteration-order variance) are nonconformant.

Reasons emitted by this clause carry the clause's identifier. A release gate
that emits a reason without a clause identifier under any circumstance has produced
a response that is not compliant with the response-shape chapter of this document.

The clause does not imply a temporal ordering on repository history. Repositories
are evaluated at rest as of the request time; previous states of the repository do
not enter the evaluation.

Where this clause admits an exception via the exception-window mechanism, the
exception applies only to the (service, clause) pair the window's cited clause and
glob select. Other clauses on the same service are unaffected.

Nothing in this clause authorizes a release gate to invoke an external
policy-decision service to resolve the clause. The decision resolves entirely from
the compose model, the approvals database, the repository state, and the tag
evidence.

The clause is symmetric with respect to service name length: a one-character
service name is evaluated identically to a 32-character service name. Service names
of any length within the compose specification's permitted range are supported.

### §E.13 Note

Timestamps in the approvals database are stored as naive local timestamps by the
H2 storage engine but are semantically UTC per this document; a release gate that
applies a local-time offset to them at read has misinterpreted the connection
contract and is nonconformant.

This clause imposes no obligation on the tooling that publishes releases; the
obligation runs to the release gate alone. Downstream tooling MAY implement any
additional constraints of its own.

The clause does not distinguish between a first-time repository presentation
and a repeat presentation of the same repository state. A repository whose state has
not changed since a previous successful release-gate evaluation is evaluated again on
its merits at each request.

A release gate MAY be implemented as multiple cooperating processes; nothing
in this clause requires a single-process implementation. Cross-process communication
is outside the scope of this document.

The transport-level HTTP contract is described elsewhere in this document.
This clause does not modify the transport-level constraints; a release gate that
mishandles the transport layer has departed from this document independently of any
clause-level obligation.

Reasons emitted by this clause carry the clause's identifier. A release gate
that emits a reason without a clause identifier under any circumstance has produced
a response that is not compliant with the response-shape chapter of this document.

The clause does not imply a temporal ordering on repository history. Repositories
are evaluated at rest as of the request time; previous states of the repository do
not enter the evaluation.

The applicability tests stated elsewhere in this document produce Boolean values
per (service, clause) pair. A release gate that produces multi-valued applicability
results — for example, "partially applies" — has misinterpreted this document. All
applicability results are Boolean.

Downstream tooling may cache a release gate's decisions but MUST NOT rely on
cached decisions across requests whose relevant inputs differ. The release gate
itself does not implement a decision cache in this edition.

A release gate's evaluation is deterministic given fixed inputs. Repeated
requests with byte-identical repository state, DB state, tag evidence, and request
body MUST yield byte-identical response bodies. Sources of non-determinism (random
sort orders, iteration-order variance) are nonconformant.

The connection contract stated elsewhere in this document is the sole basis for
the release gate's access to the approvals database. A release gate that establishes
a connection through any other mechanism has not applied the contract.

Nothing in this clause authorizes a release gate to invoke an external
policy-decision service to resolve the clause. The decision resolves entirely from
the compose model, the approvals database, the repository state, and the tag
evidence.

The clause is symmetric with respect to service name length: a one-character
service name is evaluated identically to a 32-character service name. Service names
of any length within the compose specification's permitted range are supported.

The obligation stated above operates on the resolved compose model. It applies to
every service in the enumeration produced by the merge described elsewhere in this
document; the evaluation does not distinguish between services declared in one file and
services declared only in another.

The predicate stated above is defined solely in terms of the compose model as
resolved. It does not inspect runtime state, container properties, or registry metadata.
A release gate that evaluates the predicate by any means other than inspection of the
resolved compose model is nonconformant with this standard.

When a release gate denies a release on the basis of this clause, the response
carries a reason whose `code` and `clauseId` fields identify the clause and whose
`service` field names the offending service.

### §E.14 Note

The tag reference passed in a request is fully qualified. Tag-name lookup is
byte-exact, and the release gate does not perform substring or prefix matching
against `refs/tags/`. A request whose tag ref does not resolve is signaled as a
request error and does not produce a denial-body reason code.

The transport-level HTTP contract is described elsewhere in this document.
This clause does not modify the transport-level constraints; a release gate that
mishandles the transport layer has departed from this document independently of any
clause-level obligation.

Reasons emitted by this clause carry the clause's identifier. A release gate
that emits a reason without a clause identifier under any circumstance has produced
a response that is not compliant with the response-shape chapter of this document.

The clause does not imply a temporal ordering on repository history. Repositories
are evaluated at rest as of the request time; previous states of the repository do
not enter the evaluation.

Where this clause admits an exception via the exception-window mechanism, the
exception applies only to the (service, clause) pair the window's cited clause and
glob select. Other clauses on the same service are unaffected.

Nothing in this clause authorizes a release gate to invoke an external
policy-decision service to resolve the clause. The decision resolves entirely from
the compose model, the approvals database, the repository state, and the tag
evidence.

The clause is symmetric with respect to service name length: a one-character
service name is evaluated identically to a 32-character service name. Service names
of any length within the compose specification's permitted range are supported.

Downstream tooling may cache a release gate's decisions but MUST NOT rely on
cached decisions across requests whose relevant inputs differ. The release gate
itself does not implement a decision cache in this edition.

A release gate's evaluation is deterministic given fixed inputs. Repeated
requests with byte-identical repository state, DB state, tag evidence, and request
body MUST yield byte-identical response bodies. Sources of non-determinism (random
sort orders, iteration-order variance) are nonconformant.

The connection contract stated elsewhere in this document is the sole basis for
the release gate's access to the approvals database. A release gate that establishes
a connection through any other mechanism has not applied the contract.

Nothing in this section constitutes an obligation on any deployment. The section is
provided as guidance and as a shared vocabulary for downstream tooling. A deployment
that does not follow the guidance in this section is not thereby nonconformant with
this standard.

The predicate stated above is defined solely in terms of the compose model as
resolved. It does not inspect runtime state, container properties, or registry metadata.
A release gate that evaluates the predicate by any means other than inspection of the
resolved compose model is nonconformant with this standard.

When a release gate denies a release on the basis of this clause, the response
carries a reason whose `code` and `clauseId` fields identify the clause and whose
`service` field names the offending service.

Evaluation of this clause is performed independently for each service in the
enumerated model. A service that violates the clause emits exactly one reason for it,
regardless of how many distinct violation surfaces the service presents.

Nothing in this clause overrides the general precedence rule of this document.
Where an amendment supersedes the clause, the amended text governs for the service
class the amendment addresses; the underlying clause continues to govern for all other
service classes.

A brief note on scoping: applicability of this clause resolves against
service-class predicates that live elsewhere in the definitions chapter and elsewhere
in the approvals database. Service names are not authoritative for classification.

### §E.15 Note

Reason objects in the response array are opaque records: the release gate does
not carry annotative metadata into them, and downstream tooling must not depend on
the ordering of keys within a reason object beyond the canonicalization rule stated
elsewhere in this document.

Where this clause admits an exception via the exception-window mechanism, the
exception applies only to the (service, clause) pair the window's cited clause and
glob select. Other clauses on the same service are unaffected.

Nothing in this clause authorizes a release gate to invoke an external
policy-decision service to resolve the clause. The decision resolves entirely from
the compose model, the approvals database, the repository state, and the tag
evidence.

The clause is symmetric with respect to service name length: a one-character
service name is evaluated identically to a 32-character service name. Service names
of any length within the compose specification's permitted range are supported.

The obligation stated above operates on the resolved compose model. It applies to
every service in the enumeration produced by the merge described elsewhere in this
document; the evaluation does not distinguish between services declared in one file and
services declared only in another.

The predicate stated above is defined solely in terms of the compose model as
resolved. It does not inspect runtime state, container properties, or registry metadata.
A release gate that evaluates the predicate by any means other than inspection of the
resolved compose model is nonconformant with this standard.

When a release gate denies a release on the basis of this clause, the response
carries a reason whose `code` and `clauseId` fields identify the clause and whose
`service` field names the offending service.

A release gate's evaluation is deterministic given fixed inputs. Repeated
requests with byte-identical repository state, DB state, tag evidence, and request
body MUST yield byte-identical response bodies. Sources of non-determinism (random
sort orders, iteration-order variance) are nonconformant.

The connection contract stated elsewhere in this document is the sole basis for
the release gate's access to the approvals database. A release gate that establishes
a connection through any other mechanism has not applied the contract.

Nothing in this section constitutes an obligation on any deployment. The section is
provided as guidance and as a shared vocabulary for downstream tooling. A deployment
that does not follow the guidance in this section is not thereby nonconformant with
this standard.

The provisions of this section are stated at the level of the compose model rather
than at the level of any container runtime. A release gate is not required to consult
external systems to apply this section.

Nothing in this clause overrides the general precedence rule of this document.
Where an amendment supersedes the clause, the amended text governs for the service
class the amendment addresses; the underlying clause continues to govern for all other
service classes.

A brief note on scoping: applicability of this clause resolves against
service-class predicates that live elsewhere in the definitions chapter and elsewhere
in the approvals database. Service names are not authoritative for classification.

A well-formed evaluation reports each service exactly once. Duplicate service
declarations across files are reconciled by the merge procedure and produce a single
service in the evaluated model.

A release gate applies exactly the edition of this document it ships with.
Requests routed to a gate shipping this edition are governed by this edition alone; a
subsequent edition's provisions do not reach back to requests handled here.

Applicability under this clause is a property of the resolved compose model, not
of the raw file text. Two syntactically different pairs of files that merge to the same
resolved model produce the same applicability outcome.

## End of document

This edition of the Compose Deployment Security Standard is dated as of the
title page. A subsequent edition MAY revise or supersede any provision of this
edition; a release gate applies exactly the edition of the standard it ships with.
