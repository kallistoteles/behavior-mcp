# Implementation Plan: Remaining Behavior Models

**Branch**: `feat/agent-native-declarative-systems` | **Date**: 2026-10-28
**Feature selector**: `002-remaining-behavior-models` | **Spec**: [spec.md](spec.md)

**Input**: `specs/002-remaining-behavior-models/spec.md`, including the trusted-current-time decision.
**Phase 1 status**: Design complete. Implementation and its acceptance evidence are subsequent work.
No branch hook is installed; the existing git branch is retained independently of the feature selector.

## Summary

Add bounded structured support for Approval, WorkQueue, FieldOwnership and LifecycleDependency,
using the exact released public Behavior API. Preserve the existing scalar adapter byte-for-byte;
add an exact-version dispatcher and retained immutable v2 implementation releases. Every accepted
checkpoint freezes its code/schema closure; later families add a new release instead of editing an
existing one. Public models own normalization/lowering and
Core owns every read/transition/commit/replay result. Retain complete authoring information and
separate operational receipts, safety policies, proof evidence and deployment/state validity.

Deliver all nine queue operations, authoritative outcome/queue reads, trusted actor/worker/time
binding, explicit safety certification/fresh checking and coordinated incoming-state validation.
Keep existing durable operation recovery, independent systems and old authoring contexts usable.
No scheduler, rule engine, generated client source or alternative persistence semantics is added.

## Technical Context

**Language/Version**: Python 3.13+, locked development Python 3.13.14; existing package/module layout.

**Primary Dependencies**: Behavior 0.14.0 exact released wheel SHA256
`794d2dd5ddf8613c52f524a1b4b74c0246d86a5ea52414424ab89ef104e86513`;
Core 0.15.0 commit `6b93898a9375113f7a8946f23ab5535319b6f5d6`; verifier 0.10.0;
MCP/mcp-types 2.3.0; jsonschema 4.26.0. Existing `uv.lock` remains authoritative.
Add only the separately locked upstream `safety-proof-toolchain` Nix package at Behavior commit
`1cba9e16ff73f927ae08e70a7bc74a6ca52355e4`; exact Lean 4.30.0 identity from the release manifest.
Do not upgrade the existing nixpkgs/Python/Behavior graph to obtain it.

**Storage**: Existing immutable host artifact blobs and proposals/policies/approvals in SQLite;
independent per-SystemId public Core Backend and host deployment/operation metadata. Extend JSON
formats/artifact kinds; no new domain-state or safety relationship store.

**Testing**: Mandatory observed-red then green development with pytest/pytest-asyncio; independent
public reference fixtures and exact-release conformance; schema/adversarial tests, physical crash
and concurrent-writer tests, old-workspace compatibility fixtures, positive proof and negative
proof controls, and installed-wheel/source-rebuild checks. No live AI model.

**Target Platform**: Existing x86_64 Linux, local trusted single-user workspace owner; stdio MCP
protocol versions already supported. Remote/multi-user or distributed coordination is not added.

**Project Type**: MCP integration server plus trusted local administration CLI.

**Performance Goals**: Finite complete read responses with explicit limits, not a new throughput
SLO. Reads use a 5-second worker guard; proof jobs a 120-second guard. Queue time is recorded input,
not process scheduling. No claims of constant latency or unlimited read pagination.

**Constraints**: Keep existing 1 MiB frame/32-depth ceiling and verification limits. Expanded input
ceilings: 8 models, 8 safety policies, 16 entities, 16 lifecycle actions, 32 fields/entity, 4,096
expression nodes. One concurrent proof job, bounded stdout 8 MiB/stderr 1 MiB, proof bundle 8 MiB;
read worker complete serialized output 1 MiB. Trusted configuration can only tighten limits.
CPU/address-space/file limits and process-group termination/reaping supplement byte/time bounds.
Schema-changing activation, external commands and cross-system state references remain refused.

**Scale/Scope**: Four added families; six catalog entries total. Compose atomic models inside one
system, preserve multiple independently authorized systems and shared immutable artifacts. Complete
reads may be refused at configured size limits; no generic query or system-management platform.

## Constitution Check

*Gate evaluated before research and re-evaluated against the Phase 1 design. No exception requested.*

| Required check | Design / evidence | Result |
| --- | --- | --- |
| 1. Public Behavior capabilities | Top-level model/declaration/expression/action/read constructors, Store evaluate/commit/read/replay, public Safety analysis/certification/checking/state-validation interfaces. Exact public probes are retained in evidence/. | PASS |
| 2. New semantics and layer ownership | No model or Core semantics added. Host-only schema translation, delegation, trusted context, byte storage and coordination. Fixed factories trace explicit input; no rule interpreter, synthesized guard or Wire bypass. | PASS |
| 3. Persistence and authorization | Same independent stores and writer locks; versioned host policy/approval, definition-bound policy identity, exact proof/state references. Agent models cannot grant authority. | PASS |
| 4. Claimed semantic/recovery guarantees | Preserve public Core results, exact context/source snapshot, original bundles/refusals, atomic receipts and reconciliation. Proof is conditional; state validity is anchor-specific; host timing source is not a new wall-clock commit guarantee. | PASS |
| 5. Deterministic/conformance acceptance | Per-family and per-construct positive/negative/unsupported reference comparisons, trusted-clock spoof/expiry boundaries, proof tamper controls, concurrent/crash/recovery, old-workspace and installed artifact gates. | PASS |
| 6. Upstream gaps | GAP-001–004 remain visible. Probes found no new blocking gap for the required journeys. Complete-read/output bounds and structural-versus-certified outcomes are explicit. Unsupported future constructs stop at public boundaries. | PASS |
| 7. Simpler existing API solution | Public model constructors, declared read projections, fixed lifecycle factories and existing SQLite/operation journal suffice. Reject new scheduler, plugin platform, generic interpreter, private APIs and duplicated persistence. | PASS |

Additional principle coverage: I/II/IX/X/XVI through fixed public translations and no external execution;
III/XI/XII through retained versioned source/context and frozen v1 adapter; IV/V/VIII through explicit
trusted activation and exact honest evidence; VI/VII through original Core Backend commits;
XIII through retained gaps; XIV/XV through observed failing tests, deterministic context and audit.

Post-design findings incorporated: `Lowered` can contain unsupported lifecycle issues; policies can
change without BehaviorHash changing; all nine queue registrations are required; current nixpkgs
Lean is incompatible; modifying the old adapter breaks active runtime/recovery. None is hidden
behind a fallback. Full implementation acceptance must re-run these gates; this PASS is a design check.

## Project Structure

### Documentation (this feature)

```text
specs/002-remaining-behavior-models/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── authoring.md
│   ├── adapter-versions.md
│   ├── authoring-v2.schema.json
│   ├── authoring-v2-<version>.schema.json
│   ├── host-policy-v2.schema.json
│   ├── activation-approval-v2.schema.json
│   ├── expanded-result.schema.json
│   ├── mcp.md
│   ├── tool-additions.schema.json
│   ├── host-policy.md
│   └── examples/{approval,work-queue,field-ownership,lifecycle}.json
├── evidence/
│   ├── *_probe.py / *_results.json
│   ├── proof_toolchain.json
│   └── planning-validation.json
└── tasks.md                    # Future speckit-tasks output; not produced by this command.
```

### Source Code (existing and planned)

```text
src/behavior_mcp/
├── authoring.py                # Existing exact bytes frozen for scalar-models.v1.
├── adapters.py                 # New explicit profile dispatch, subject provenance and catalog.
├── authoring_v2.py             # Mutable draft/facade, never a published handler dependency.
├── adapter_versions/
│   ├── v2_0_0.py               # Frozen Approval MVP implementation.
│   ├── v2_1_0.py               # Frozen WorkQueue addition.
│   ├── v2_2_0.py               # Frozen FieldOwnership addition.
│   ├── v2_3_0.py               # Frozen LifecycleDependency addition.
│   └── fragments_<version>.py  # Immutable shared helpers, retained by exact closure.
├── fragments_v2.py             # New bounded syntax → public symbolic tracing only.
├── reads.py                    # New scoped read journaling and public Core read/replay.
├── safety.py                   # New public assessment/state-validation/artifact integration.
├── proof_worker.py             # New fixed isolated certification/checking/read worker commands.
├── artifacts.py / schemas.py   # Existing storage and versioned packaged contract selection.
├── policy.py / admin.py        # Existing trust boundary with explicit v1/v2 dispatch.
├── server.py / systems.py      # Existing registry, explicit activation and coordination.
├── operations.py               # Existing original-operation contract, expanded context binding.
├── verification.py / limits.py # Existing bounded pipes/profiles, definition-specific provenance.
└── dependencies.py / release.json # Exact released graph/public-boundary checks retained.

tests/
├── fixtures/                  # Frozen old workspace/context and independent public references.
├── unit/                      # Typed grammar, delegation, trusted context and evidence binding.
├── contract/                  # All schemas/registry, closed input, statuses and installed resources.
├── integration/               # Each family, composition, reads, proof, restart/revision/crash.
├── conformance/               # Existing 45-case public Backend suite plus affected comparisons.
└── acceptance/                # Six user stories and mandatory per-family complete journeys.
```

**Structure Decision**: Preserve one Python package and existing host/storage seams. Two authoring
versions justify explicit dispatch; safety/proof/read boundaries are distinct deep modules. Shared
pipe limits may be reused without refactoring the frozen adapter. No extension/plugin registry.
New contract files are packaged alongside frozen v1 resources with unique filenames and local
schema references; include research/acceptance evidence in source artifacts as appropriate.

## Phase 0 — Research and Public Feasibility

Completed decisions R1–R11 and alternatives in [research.md](research.md). Public probes cover
Approval duplicate/threshold decisions, queue expiry boundary and reads, replay, Safety policy
identities/unsupported issues, Valid/Invalid state evidence, actual conditional certification,
fixed action factories and the existing context-identity regression.
The exact proof toolchain source manifest is retained. No unresolved design clarifications remain.

## Phase 1 — Design and Contracts

Completed [data-model.md](data-model.md), [immutable adapter versions](contracts/adapter-versions.md),
[authoring contract](contracts/authoring.md),
[closed authoring schema](contracts/authoring-v2.schema.json),
[MCP contract](contracts/mcp.md), [added requests](contracts/tool-additions.schema.json),
[host policy](contracts/host-policy.md), its [closed grammar](contracts/host-policy-v2.schema.json),
[exact approvals](contracts/activation-approval-v2.schema.json),
[expanded results](contracts/expanded-result.schema.json), structured operator/result fixtures,
four complete versioned proposal fixtures and
[quickstart.md](quickstart.md). No production implementation is introduced by these artifacts.

## Implementation Sequence for Task Generation

1. **Compatibility foundation**: Capture a committed pre-feature workspace/source fixture and
   observe failures for expanded profile dispatch, frozen bytes, subject-specific provenance and
   old-policy rejection. Add dispatch/resources while preserving all supported v1 journeys.
2. **Typed authoring foundation**: Observe grammar/reference/adversarial failures before fixed
   declaration/expression/lifecycle factory translations. Independently compare public lowered
   output and identities for every advertised node; preserve original source/context.
3. **Approval vertical slice**: Add decisions, trusted actor context, declared outcome read,
   active discovery and state persistence/replay; include duplicate/closed/threshold cases and
   restart/revision. Include its catalog/registry/result variants now, freeze 2.0.0 before claiming
   the MVP supported, and retain its actual workspace fixture. No manual counting or subject mutation.
4. **WorkQueue vertical slice**: Add ordered time, all nine registrations, proposed-context bounds,
   trusted worker/now, complete Core reads and durable read retry. Cover every operation, races,
   expiry/generation boundaries and all before/after-publication crash cases. Publish 2.1.0 with
   queue registry/results and prove the saved 2.0.0 workspace still works unchanged.
5. **FieldOwnership and lifecycle slice**: Add exact action selectors, full authoritative Safety
   analysis/issues/policy identity, canonical Parent/Child actions and independent negative cases.
   Publish 2.2.0 and 2.3.0 with their interfaces and retained earlier-version regression fixtures.
6. **Evidence/deployment slice**: Provision the exact locked proof tools. Add bounded certification,
   unverified import/fresh checking and public snapshot validation. Bind complete policies/evidence
   to delegation/exact approval and acquire current validity inside atomic activation coordination.
7. **Composition and release**: Demonstrate both requested operational compositions and policies
   over generated actions. Exercise policy-only revisions with same BehaviorHash, old contexts,
   history/replay, authority revocation, isolation and installed distributions. Publish honest gap
   and acceptance evidence; do not label an incomplete family complete.

Each slice includes its own discovery, tool registry, request/result validation and version
publication before independent acceptance. US6 audits already delivered interfaces; it does not
unblock the earlier slices. The foundation provides shared registry/validator mechanics and the
closed contracts, not false early advertising of unimplemented families.

Each slice is red → public-boundary implementation → green. Tasks must include observed-red evidence,
not just a proposed test name. The plan does not create tasks.md or begin production work.

## Acceptance and Quality Gate

Retain one command, `nix develop --command ./scripts/check`, for development, CI and release.
Extend it to all new schemas/probes and required proof readiness without changing legacy evidence.
Positive certification is mandatory in the declared CI/release environment; missing tools cannot
be skipped as a passing test. Include complete installed-wheel journeys and source→wheel
reproducibility; explicitly increase the installed suite's current 300-second harness budget to
900 seconds for the expanded suite/proof controls, not the per-operation worker limits.
Upload both feature evidence directories and dist/ in CI/release workflow artifacts.

| Acceptance group | Spec coverage | Required evidence |
| --- | --- | --- |
| Discovery/closed authoring | FR-001/009/010/022/023, SC-001/012 | All six categories; each construct positive/negative/unsupported; no code/private API/guessed repair. |
| Approval | FR-002/003/005, SC-002 | Decisions/outcomes, threshold/duplicate/ineligible/closed cases, declared read/replay and restart. |
| WorkQueue/trusted context | FR-004–006/019, SC-003/009 | All nine, reads, host-time spoof refusal, lease/generation/attempt boundaries, conflicting writers and exact retries. |
| Structural safety | FR-007–010/012, SC-004/005 | Complete inventory/issues, generated and authored action selectors, missing guards/ownership and unchanged BehaviorHash policy changes. |
| Proof/state/deployment | FR-011–014/021, SC-005/008/012 | Real conditional certification, fresh import checking/tamper/tool failures, Valid/Invalid/exact-anchor checks, concurrent writer negative controls. |
| Composition/evolution/compatibility | FR-015–020, SC-006/007/010/011 | Four family round-trips/revisions, both compositions, legacy runtime/editing, old artifacts/replay and independent systems. |
| Packaging/release | FR-018/021–023, SC-011/012 | Locked tools, public imports, 45 Backend conformance cases, required tests, format/lint/types, installed wheel and source rebuild. |

Release readiness requires all mandatory journeys. Public probe success is research evidence only;
formal safety claims remain exactly those of retained public assessments under their assumptions.

## Complexity Tracking

No constitution violations or exception requests. Additional modules and versioned input syntax
are justified by a demonstrated second adapter, public lifecycle/proof boundaries and required
compatibility. A generic engine/plugin/authoring language would add unjustified complexity.
