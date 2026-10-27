# Implementation Plan: Agent-Native Declarative Systems

**Branch**: `main` | **Feature context**: `001-agent-native-systems` | **Date**: 2026-10-26 | **Spec**: [spec.md](spec.md)

**Input**: `specs/001-agent-native-systems/spec.md`, including both accepted clarifications.

**Status**: Phase 0 research and Phase 1 design complete. No application implementation.

## Summary

Build a local Python MCP integration using the released Behavior package as its semantic
boundary. Give each system a stable host SystemId, independent Core Store and SQLite backend,
active pointer and authorization scope. Share immutable artifacts through workspace storage.
Use trusted, versioned host delegation for unattended activation; approve exact versions through
a separate trusted administrative channel when they exceed that delegation.

Canonical model documents are not complete editable source at this release. Persist a narrowly
specified authoring proposal and its complete construction context alongside canonical model
documents, generated Wire JSON and lowering receipts. The trusted adapter translates data into
public RequestFlow/StateMachine constructors; it never evaluates client code, builds Wire IR
by hand or implements transition semantics. RequestFlow supplies the complete initial vertical
slice; StateMachine provides a second bounded composition adapter and conformance fixture.

Initial evolution supports same-schema behavior revisions. Schema-changing activation is
explicitly refused; the missing governed Python migration path is recorded separately from
ordinary migrations that upstream does support. No missing capability is counted as delivered.

## Technical Context

**Language/Version**: Python 3.13; released-wheel probes ran with 3.13.14. Initial platform is
Linux x86_64 with glibc >=2.28. Pin the development environment through `flake.lock` during
implementation using Nixpkgs commit `293d6abedf0478e681a4dfcfcb35b30fc796a32f` for Python,
uv and native Ruff; other platforms require their own released-artifact acceptance. Resolve a
portable upstream flake input, not this machine's registry/store path.

**Primary Dependencies**: Released `behavior==0.14.0` wheel, SHA256
`794d2dd5ddf8613c52f524a1b4b74c0246d86a5ea52414424ab89ef104e86513`;
Behavior commit `1cba9e16ff73f927ae08e70a7bc74a6ca52355e4`; bundled Core 0.15.0 commit
`6b93898a9375113f7a8946f23ab5535319b6f5d6`, verifier 0.10.0. Official `mcp==2.3.0` and
`mcp-types==2.3.0`; `jsonschema==4.26.0` for host-owned request schemas. Use the public
low-level MCP `Server`, with stdio and explicit structured results. Pin and hash all transitive
distributions in `uv.lock`; do not build Behavior against a different Core.

**Storage**: Python standard-library SQLite. One workspace artifact/policy database; one
separate SQLite file per SystemId containing that system's descriptor, Core backend documents,
active deployment, operation receipts and audit. Use rollback journals (`journal_mode=DELETE`),
`synchronous=EXTRA`, foreign keys and bounded busy waits, verifying settings on each connection.
Core callbacks perform publication and as-of storage; they do not evaluate domain rules.

**Testing**: Test first. `pytest==9.1.1`, `pytest-asyncio==1.4.1`, `mypy==2.4.0`;
build backend `hatchling==1.32.4`; native Ruff 0.15.14 from the pinned Nixpkgs input. The generic
PyPI Ruff executable did not run on this NixOS host, so Ruff belongs to the declared Nix graph,
not an unpatched binary in the Python environment. Pin all Python dependencies at implementation.
Public `behavior.run_conformance` plus independent public-API comparison
fixtures, real stdio clients, subprocess crash/reopen tests and deterministic fault injection.

**Target Platform**: One trusted local launcher, one OS user, one server process owning a
workspace. Acquire a workspace process lock; refuse a second live owner. Within that process,
systems have separate writer/concurrency boundaries. HTTP, remote identity and OS multi-user
isolation are outside this release.

**Project Type**: Python package exposing `behavior-mcp` and a separate trusted
`behavior-mcp-admin` entry point. MCP tools cannot administer policy or grant approval.

**Performance Goals**: Correctness and recoverability for the demonstrated local workload;
no throughput or latency service-level claim. Validate at least two simultaneously used systems
and two independent client sessions. Benchmark results may inform later limits without becoming
Behavior semantic guarantees.

**Constraints**: Initial operational defaults are a 1 MiB incoming frame, nesting depth 32,
read pages of 50 with maximum 100, one committing writer per system and bounded verification
workers. These are configurable host restrictions. Bound frames before JSON decoding using
public stream composition; the SDK's standard line reader has no frame-size setting.
No client paths, code, remote schema fetching, arbitrary expressions or external command effects.

**Scale/Scope**: One complete RequestFlow authoring/runtime/revision demonstration plus a second
system for isolation and a RequestFlow/StateMachine composition fixture. Two fixed adapters,
string payload fields, enum states and explicit initializer/input-to-field transfers. No generic
plugin system, cross-system references, transactions, orchestration, multi-user tenancy or
distributed coordination. Maximum host capacities are operational configuration, not IR limits.

## Constitution Check

*Pre-research gate: PASS for public-interface research. Post-design gate is evaluated below.*

1. **Public capabilities**: Top-level `BehaviorModule`, `RequestFlow`, `StateMachine`, `entity`,
   `field`, `Id`, `set_`, Wire export/re-admission, receipts, `verify`/`Profile`, `Store`,
   `HistoryRef`, `run_conformance`, replay and `export_seed_at`. Backend callbacks are the
   published Python contract. No private crates or binding modules are dependencies.
2. **New semantics**: None. The retained authoring representation is justified by demonstrated
   canonical omissions, and maps only to supported typed constructors. Host policy, request
   limits and operation receipts are operational controls, explicitly separate from Core proof
   and execution guarantees. No guard/effect interpreter is introduced.
3. **Persistent and authorization boundaries**: Workspace artifact/policy storage and independent
   system stores. Authorize trusted principal + workspace + SystemId + operation. SystemId is
   not BehaviorHash or Core StoreId. Immutable artifacts convey no authority. Host policy versions,
   Core genesis evidence policies and Core execution policies are distinct artifacts.
4. **Claimed guarantees**: Core-controlled evaluation/commit/replay, atomic per-system publication
   and active-pointer changes, unchanged authoring reconstruction under exact context, durable
   restart within declared SQLite/filesystem assumptions, scoped lost-ack recovery. No universal
   safety proof, arbitrary canonical re-authoring or external exactly-once execution claim.
5. **Acceptance evidence**: Red-before-green tests; public-backend conformance; positive,
   negative and unsupported authoring cases; unchanged and revised identities; composition;
   trusted delegation; same-genesis system isolation; competing activation/policy races;
   abrupt termination; original-bundle retry and historical replay. All run without a live AI.
6. **Upstream gaps**: Canonical standalone reconstruction, generic model-configuration metadata,
   receipt provenance absent after Wire import, and conditional governed Python migration support.
   See [gap register](../../SEMANTIC_GAPS.md). Limited adapters and separately persisted source
   address the initial slice; unrestricted authoring remains unsupported.
7. **Simpler alternatives**: Reuse public models and callbacks rather than a second compiler,
   direct row mutation, private Rust extension, scheduler or distributed storage. SQLite avoids
   an external service; one process with per-system coordination avoids distributed locks.

The host-policy and exact-approval grammars are closed versioned contracts. Proposal changes use
explicit parent/base identities and immutable revisions; validation binds an exact source revision.
Activation has a request-bound host receipt published atomically with pointer/audit and recovered
separately from Core transition bundles. Stage-specific result schemas require actual subject
and evidence data, with runtime consistency checks against public reports and stored receipts.

No constitutional exception is requested. Full conformance and physical durability remain
implementation gates, rather than conclusions from the in-memory feasibility probes.

## Project Structure

### Documentation (this feature)

```text
specs/001-agent-native-systems/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── mcp.md
│   ├── authoring.schema.json
│   ├── example-proposal.json
│   ├── result.schema.json
│   ├── tool-request.schema.json
│   ├── host-policy.schema.json
│   ├── activation-approval.schema.json
│   ├── example-host-policy.json
│   ├── example-results.json
│   └── host-policy.md
├── evidence/
│   ├── public_api_probe.py
│   └── public_api_results.json
└── checklists/requirements.md
SEMANTIC_GAPS.md
```

`tasks.md` is produced later by `speckit-tasks`; it is not part of this planning command.

### Source Code (repository root)

Proposed implementation layout; these application files are not created during planning:

```text
pyproject.toml
uv.lock
flake.nix
flake.lock
scripts/check
src/behavior_mcp/
├── dependencies.py           # released artifact/runtime/public-boundary checks
├── storage.py                # shared local SQLite and lock mechanics
├── verification.py           # public reports and bounded workers
├── server.py                 # public MCP Server and bounded stdio
├── schemas.py                # host envelope parsing, no Behavior type checker
├── authoring.py              # two fixed public-model adapters
├── artifacts.py              # immutable artifacts and source/context storage
├── policy.py                 # trusted delegation, no model-defined authority
├── systems.py                # SystemId, per-system coordination and activation
├── sqlite_backend.py         # published Core backend callbacks
├── operations.py             # scoped original-bundle recovery and receipts
└── admin.py                  # separate trusted local policy/approval channel
tests/
├── unit/
├── contract/
├── conformance/
├── integration/
└── acceptance/
```

**Structure Decision**: A single package with direct modules at the actual integration seams.
Do not add generic repositories, plugin registries or a parallel domain-object framework.
Domain records are Core documents, not ORM models maintained by MCP.

## Delivery Sequence and Acceptance Gates

1. Lock the exact released artifact graph and create the one quality command before feature code.
   Add failing dependency-identity and public-import checks. Install only the released wheel.
2. Add failing authoring/identity fixtures, then implement the bounded adapters and artifact
   storage. Preserve complete authoring context and receipts; verify two unchanged reconstruction
   cycles and one semantic revision with unchanged schema.
3. Add failing backend laws and physical recovery tests, then implement SQLite callbacks.
   All 45 public conformance cases must pass, followed by real crash/reopen and concurrent-writer
   tests. Neither test family substitutes for the other.
4. Add failing trusted-scope and activation tests, then implement system creation, delegation,
   same-schema validation and atomic deployment publication. Test two separately stored systems
   with identical genesis content; their Core identities may coincide without merging authority.
5. Add failing MCP contract tests, then expose discovery, definitions, systems, validation,
   verification, activation, reads, evaluation, commit and operation recovery through fixed tools.
   Exercise both SDK modern `2026-07-28` and legacy `2025-11-25` client modes.
6. Demonstrate the complete journey, simultaneous isolated systems, independent activation,
   policy races, lost acknowledgment, restart and historical replay. Refuse unsupported authoring,
   schema-changing activation, external effects and cross-system operations with structured status.

The single mandatory command is **`nix develop --command ./scripts/check`**. It must use the
committed locks to synchronize dependencies, verify release/checksum/runtime identities and public
imports, check formatting/lint/types, and run all applicable deterministic/conformance/recovery
and acceptance checks. CI and release run that exact command. A focused test invocation is not a
replacement for the gate. The command is to be implemented; it does not exist at planning time.

## Post-Design Constitution Check

**PASS for the bounded design.** Public-release feasibility probes, contract schemas, local
references and the separation of host policy, artifacts, deployment and Core state were reviewed.
The seven checks above remain satisfied after Phase 1:

- Complete retained source/context addresses the demonstrated canonical omissions; no interpreter,
  private import, handwritten IR or blanket canonical-only support is introduced.
- SystemId binds authorization and recovery independently of equal genesis/behavior hashes.
  Mutable stores and active pointers are isolated; immutable content may be shared.
- Delegation is a separate trusted policy version. Atomic activation records exact subject,
  policy, authorization and history. All relevant writers and policy changes coordinate.
- Original-bundle recovery and atomic host receipts preserve the uncertain-outcome boundary.
  A retry that could newly commit still needs current authorization.
- Schema-changing activation, arbitrary expressions, external effects and cross-system workflows
  remain explicit refusals. Stronger unsupported evidence policies cannot be silently weakened.
- Gaps remain visible with exact releases, evidence and interim behavior. No constitutional
  exception is required for the supported initial subset.
- Test-first implementation, the full locked quality command, physical durability and all
  acceptance results remain required future gates. The Phase 0 in-memory probe satisfies none
  of those delivery claims by itself.

## Complexity Tracking

No constitutional violations. The extra retained authoring representation is necessary because
canonical documents omit reconstructible bodies; its bounded public-constructor mapping and
explicit provenance avoid a competing semantic format. Per-system storage is required by the
accepted isolation contract, rather than a general system-management framework.

## Build Graph Implementation Detail

The pinned Nix shell also supplies native Z3 4.16.0. Hatchling 1.32.4 and its full transitive graph
are locked in the development group. The quality command first synchronizes the locked graph
without installing the root project, then builds/reinstalls the root package without isolated
build dependency resolution. Package acceptance rebuilds the wheel from its source distribution
with that same locked backend. This prevents an otherwise separate untracked PEP 517 build graph.
