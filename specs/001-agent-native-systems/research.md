# Research: Agent-Native Declarative Systems

**Date**: 2026-10-26

**Scope**: Resolve implementation choices against released public interfaces. Source inspection
and executed in-memory probes establish API feasibility; they establish no host durability,
deployment authorization or formal safety guarantee.

## 1. Released Dependency Boundary

**Decision**: Use the published Linux x86_64 `behavior==0.14.0` wheel with Python 3.13.

**Rationale**: The release explicitly bundles Core 0.15.0. A checksum-verified installation and
`behavior.versions()` matched its manifest. No checkout dependency or local rebuild was used.

| Identity | Value |
| --- | --- |
| Behavior commit | `1cba9e16ff73f927ae08e70a7bc74a6ca52355e4` |
| Core commit | `6b93898a9375113f7a8946f23ab5535319b6f5d6` |
| Engine / verifier | `0.15.0` / `0.10.0` |
| Solver declared by Core | Z3 `4.16.0` |
| Wheel platform | `cp313-abi3-manylinux_2_28_x86_64` |
| Wheel SHA256 | `794d2dd5ddf8613c52f524a1b4b74c0246d86a5ea52414424ab89ef104e86513` |

Sources: [release](https://github.com/kallistoteles/behavior-ir/releases/tag/v0.14.0),
[manifest](https://github.com/kallistoteles/behavior-ir/releases/download/v0.14.0/release-manifest.json),
[checksums](https://github.com/kallistoteles/behavior-ir/releases/download/v0.14.0/SHA256SUMS),
[Python requirement](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/pyproject.toml),
[Core release](https://github.com/kallistoteles/behavior-ir-core/releases/tag/v0.15.0).

**Alternatives considered**: Private Core imports, a checkout override and rebuilding the wheel
would breach the dependency boundary. A separate Rust bridge would add a release and language
boundary where the supported Python interfaces already suffice for the initial slice.

The dependency will be a direct released-wheel URL with its hash in the committed lock graph.
The package is named `behavior`; a similarly named PyPI project is not an interchangeable source.

## 2. Canonical Documents and Retained Authoring Data

**Decision**: Persist canonical documents as authoritative model identity artifacts, together
with a separate complete, versioned authoring proposal and construction context.

**Rationale**: Canonical StateMachine documents retain referenced declaration identities and
fragment hashes. RequestFlow also records hashes for initializer expressions. These documents
do not contain all referenced declarations or expression bodies. The released model classes have
no public document-reconstruction method. Receipt deserialization is not model admission.

Sources: [StateMachine identity construction](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/crates/behavior-models/src/identity.rs),
[RequestFlow identity construction](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/crates/behavior-models/src/request_flow/identity.rs),
[receipt conversion](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/python/behavior/models.py).

The new host representation is justified by those demonstrated omissions. Its meaning is only
the result of invoking the pinned public constructors. It retains declarations, enum names and
cases, model parameters, explicit initializer values, fixed typed assignments, composition
membership and adapter identity. Display metadata is separate. No missing body is inferred from
a hash, and no executable expression text is accepted.

**Alternatives considered**: Canonical-only storage loses editable information. Wire JSON is
generated behavior rather than editable model source. Reconstructing arbitrary fragments or
copying normalization/lowering would introduce unauthorized semantics.

**Gap**: `GAP-001` blocks claims of arbitrary canonical-only reconstruction, not the bounded
authoring subset. See [the gap register](../../SEMANTIC_GAPS.md).

## 3. First Model and Composition

**Decision**: Use RequestFlow for the complete demonstration and StateMachine for a second
bounded adapter and composition fixture. Initial proposals use string fields, enum states,
explicit literal/input/trusted-actor initializer references and direct typed input-to-field
assignments. Reject arbitrary guards, expressions, command emission and unknown extensions.

**Rationale**: RequestFlow owns creation as well as transitions. A trusted fixed adapter can call
`RequestFlow.create` and `RequestFlow.transition`; supported assignments use the public `set_`
constructor. Data is never evaluated as Python. StateMachine alone does not supply the required
record-creation journey. `BehaviorModule(models=[...])` composes supported models authoritatively.

Sources: [RequestFlow API](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/python/behavior/request_flow.py),
[StateMachine API](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/python/behavior/models.py),
[module constructor](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/python/behavior/module.py).

Executed released-wheel probes observed creation `ALLOW`, missing required input `INVALID_INPUT`
with unchanged head, completion `ALLOW`, repeated completion `DENY`, unchanged reconstruction
preserving all three relevant identities and a renamed transition changing model/behavior
identity while preserving schema identity. RequestFlow and StateMachine composed successfully.
Adding another model changed whole-module identity without changing the first model's ModelHash.

Initial documents without extra state bindings are RequestFlow/StateMachine semantic version 2,
lowerer version 1. The same families with extra state bindings use version 3 and are outside the
initial adapter. Approval and WorkQueue exist upstream but are not advertised as authored by
this release of MCP. [Published model versions](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/crates/behavior-models/src/lib.rs)

**Alternatives considered**: A universal expression language, support for all model families or
a generic plugin framework would add scope without improving this first complete experiment.
Models needing shared atomic state compose within one system, not across systems.

## 4. Discovery and Artifact Provenance

**Decision**: Publish an explicitly bounded adapter schema with public-source provenance. Derive
generated action names and parameter roles from authoritative module output, never naming guesses.

**Rationale**: Upstream exports model families but not a complete machine-readable configuration
schema registry. Constructor signatures and documentation support a pinned subset, not a promise
of universal schema discovery. The probe found the creation argument is `request_id`, demonstrating
why runtime contracts must inspect actual output.

[Model-family registry](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/crates/behavior-models/src/kinds.rs)

Wire export/re-admission preserved BehaviorHash and SchemaHash, but imported modules intentionally
have empty model receipt and diagnostic collections. Store receipts and original authoring data
separately. On activation/reconstruction, rebuild from retained input through the exact public
toolchain and compare generated identities; loading a receipt dictionary is not evidence of
trusted lowering. [Wire import behavior](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/python/behavior/module.py)

**Alternatives considered**: Pretending host schemas originate from an upstream registry, or
treating a serialized receipt as approval, would overstate the available guarantees.

**Gaps**: `GAP-002` and `GAP-003`.

## 5. Core Persistence and Isolation

**Decision**: Implement a SQLite backend through the public Python callback contract, with one
backend target per SystemId. Store Core documents unchanged and maintain only required storage
and derived lookup indexes.

**Rationale**: Public `Store` supports creation, open, evaluation, commit, history and replay.
Required backend callbacks are `genesis`, `head`, `create`, `version_at`, `version`, `record`,
`removed_at`, `incoming_at`, `keys_at` and `commit`. `used_at` and `keys_by_field_at` are optional.
The publication callback receives Core-produced documents and returns `applied` or `head_moved`.
These are storage obligations rather than permission to compute transitions or semantic hashes.

Sources: [public API manifest](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/api/public-api.json),
[custom-backend guidance](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/skills/behavior-application/SKILL.md),
[Core persistence contract](https://github.com/kallistoteles/behavior-ir-core/blob/v0.15.0/docs/persistence.md).

Core StoreId is derived from genesis content. Two independent stores with identical genesis may
have equal Core identities and initial history anchors. Host SystemId must therefore bind every
authorization decision, token, approval and operation receipt independently of those hashes.
[Genesis and Store identity](https://github.com/kallistoteles/behavior-ir-core/blob/v0.15.0/crates/behavior-store/src/documents.rs)

`run_conformance(factory)` exercises 45 logical cases at this release. Physical crash durability
still requires real SQLite subprocess termination and reopen tests. The in-memory probes make no
such claim. [Conformance inventory](https://github.com/kallistoteles/behavior-ir-core/blob/v0.15.0/crates/behavior-store/src/conformance.rs)

**Alternatives considered**: In-memory storage is insufficient. Domain ORM updates would bypass
Core. Shared mutable stores would violate isolation. Distributed storage has no initial need.

## 6. Activation, Policies and Uncertain Outcomes

**Decision**: Coordinate every writer for a system and applicable policy changes; validate the
incoming same-schema module at an exact history anchor with public `export_seed_at`; publish
active pointer and activation evidence in one system-database transaction.

**Rationale**: That public call obtains complete Core-validated state for the incoming module.
An earlier snapshot check cannot authorize deployment after an intervening write. Safety-specific
`validate_safety_snapshot` is separate and may report `Unestablished`; it is not generic activation
approval. [Store surface](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/python/behavior/store.py),
[Safety snapshot contract](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/python/behavior/safety.py)

Keep three policies distinct: host delegated activation policy, immutable Core genesis evidence
policy and Core execution policy. Initial trusted configuration may explicitly choose Core
`require:none` and no mandatory formal proof obligations. That is recorded, never inferred, and
confers no safety claim. A host policy demanding stronger proof fails closed when evidence is
missing. Public `verify` with `Profile` produces an exact scoped attestation independently of
authenticated governance. [Verification API](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/python/behavior/verify.py),
[governance guidance](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/README.md)

Store the original evaluated bundle before commitment, bound to workspace/SystemId/request.
The backend may publish an operational receipt alongside Core's unmodified documents in the same
SQL transaction. Use Core's record identity; do not add fields to Core records. Following an
uncertain acknowledgment, inspect that receipt and retry only the original bundle through Core
if needed; an already-committed result is distinct from a fresh transition. Do not re-evaluate
first. `BACKEND_ERROR` is uncertainty/infrastructure even when carried by `CommitRefused`.

Ordinary public migrations exist. The independent authenticated prepared-migration path is not
exposed by the Python binding, so it cannot satisfy every governed schema migration. Initial
delivery refuses schema-changing activation; no private Rust bridge is introduced.
[Documented migration limitation](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/python/behavior/governance.py)

**Alternatives considered**: Workspace membership alone, model-supplied approvals, hash matching
or admission alone cannot authorize activation. A check outside the writer boundary is stale.
Re-evaluation after a lost acknowledgment can duplicate an already committed operation.

## 7. SQLite and Host Coordination

**Decision**: Use local SQLite with rollback journaling and `synchronous=EXTRA`, explicit
transactions, verified settings and durable directory creation. Persist shared immutable artifacts
before publishing system references; never delete artifacts in this first release.

**Rationale**: The workload is local and small. Per-system database transactions can publish
Core records with host receipts, and activation pointers with their audit records, without
cross-system atomic transactions. SQLite's guarantees depend on its filesystem/hardware contract;
fault tests and documented recovery conditions remain required.

[SQLite synchronization settings](https://www.sqlite.org/pragma.html#pragma_synchronous),
[atomic commit assumptions](https://www.sqlite.org/atomiccommit.html),
[Python transaction control](https://docs.python.org/3.13/library/sqlite3.html#transaction-control)

**Alternatives considered**: WAL adds checkpoint handling unnecessary for the initial workload.
PostgreSQL adds an external service. Separate non-atomic commit receipts risk ambiguous duplicates.
An index or Markdown projection cannot become the authoritative store.

## 8. MCP and Reproducible Tooling

**Decision**: Official low-level Python SDK `mcp==2.3.0`, matching `mcp-types==2.3.0`, local stdio.
Test modern `2026-07-28` and the SDK's legacy `2025-11-25` mode. Keep SystemId explicit in calls.

**Rationale**: The SDK supports Python 3.13 and typed structured results. Its low-level API gives
the host explicit control over refusal, authorization, conflict and infrastructure envelopes.
Stdio supplies no authenticated per-request identity: principal, workspace and policy must come
from the trusted launcher. Handles, roots, client metadata and annotations grant no authority.

[SDK release](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.3.0),
[protocol compatibility](https://github.com/modelcontextprotocol/python-sdk/blob/v2.3.0/docs/protocol-versions.md),
[low-level API](https://github.com/modelcontextprotocol/python-sdk/blob/v2.3.0/docs/advanced/low-level-server.md),
[stdio authorization](https://github.com/modelcontextprotocol/python-sdk/blob/v2.3.0/docs/run/authorization.md),
[structured result/error contract](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)

Pin JSON Schema validation, test and type tools in the implementation Python lock graph.
Versions researched from their official distribution metadata: `jsonschema 4.26.0`, `pytest 9.1.1`,
`pytest-asyncio 1.4.1`, `mypy 2.4.0`, `hatchling 1.32.4`.
[PyPI metadata](https://pypi.org/pypi/jsonschema/4.26.0/json) and the equivalent versioned metadata
endpoints for those projects are the version evidence. Use `uv --locked` so normal checks cannot
silently resolve another graph. [uv lock semantics](https://docs.astral.sh/uv/concepts/projects/sync/)

The PyPI Ruff 0.17.2 executable failed with NixOS's generic dynamic-loader refusal. Native
`nixpkgs#ruff` ran as version 0.15.14. Pin Nixpkgs commit
`293d6abedf0478e681a4dfcfcb35b30fc796a32f` for native Python 3.13, uv 0.11.21 and Ruff;
record the portable upstream input in `flake.lock` during implementation. The current registry
resolves a local store path, which must not become the committed input.
[Pinned native Ruff package](https://github.com/NixOS/nixpkgs/blob/293d6abedf0478e681a4dfcfcb35b30fc796a32f/pkgs/by-name/ru/ruff/package.nix)

**Alternatives considered**: High-level automatic result wrapping adds ambiguity to structured
failures. HTTP introduces remote authentication scope. A TypeScript or Rust transport adds a
language bridge. Existing client compatibility is delegated to the supported SDK, not a local
MCP protocol implementation.

## Research Question Disposition

| Question | Finding |
| --- | --- |
| RQ-001 Canonical authoring | Limited: documents omit reconstructible bodies; retain complete proposal/context. |
| RQ-002 Round-trip identity | Supported for the probed retained subset under exact versions; canonical-only support remains blocked. |
| RQ-003 Discovery | Limited: authoritative exports exist, complete generic configuration schemas do not. |
| RQ-004 Composition | Two bounded data adapters now compose through the public API and match an independent public fixture; generic schema discovery still needs upstream metadata. |
| RQ-005 Persistence | SQLite implements the public Backend contract; all 45 conformance cases and process-crash/isolation tests pass. |
| RQ-006 Evolution | Same-schema revision, historical reads/replay and coordinated activation are implemented/tested; governed Python migration remains a conditional gap. |
| RQ-007 Boundaries | Retained source, storage, transport and authorization belong here; missing general reconstruction/metadata belongs upstream. |

All research decisions are resolved for the initial design. Identified unsupported capabilities
remain explicit gaps rather than unresolved implementation assumptions. Reproduction and observed
results are retained in [evidence](evidence/public_api_results.json); the executable probe uses
only public released interfaces and an in-memory backend.

## Implementation Finding: Enum Declaration Order

The independent runtime comparison exposed an authoring-format defect: storing enum cases in a
JSON object allowed member sorting during artifact persistence to reorder the public Python Enum
declaration, changing Core's declaration, behavior and resulting-state identities. The original
cases are now an ordered array of `{name, value}` entries. The adapter passes that explicit order
to the supported public Enum constructor; it adds no enum normalization or semantic hashing.
The regression test transports the complete proposal with sorted JSON object members and requires
unchanged authoritative BehaviorHash/SchemaHash. This corrects the unreleased authoring proposal
schema, and does not change the canonical model-document format or the Phase 0 probe.

## Implementation Disposition of the Seven Research Questions

- RQ-001: Canonical documents alone remain insufficient; complete ordered authoring data and
  construction context are retained explicitly. No missing expression body is reconstructed.
- RQ-002: Exact-source reconstruction, concurrent revision isolation, semantic revision and
  historical public Core replay pass; identities are checked against authoritative outputs.
- RQ-003: Discovery labels the two implemented host schemas and pinned public provenance;
  Approval/WorkQueue availability is distinguished from authored support.
- RQ-004: RequestFlow and StateMachine compose in one module/SystemId. The same fixed MCP tools
  expose both; their bounded authoring adapters call different public constructors. Public
  ownership conflicts remain authoritative, rather than being resolved by MCP.
- RQ-005: The host supplies durable callbacks, immutable artifact storage, system scope, locks
  and receipts. Core continues to generate documents, evaluate, commit and replay.
- RQ-006: Proposals use explicit parent/base/revision identities. Same-schema activation preserves
  historical artifacts and exact authority; schema migration is refused.
- RQ-007: Storage, transport and host authority belong here; complete generic authoring metadata,
  canonical reconstruction and missing governed migration bindings remain upstream concerns.
