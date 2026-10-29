# Research: Remaining Behavior Models

**Date**: 2026-10-28
**Baseline**: Behavior 0.14.0 (`1cba9e16ff73f927ae08e70a7bc74a6ca52355e4`), Core 0.15.0
(`6b93898a9375113f7a8946f23ab5535319b6f5d6`), verifier 0.10.0.
**Result**: Design questions resolved. Public probes establish feasibility, not feature completion.

## R1 — Freeze the existing authoring implementation

**Decision**: Retain `src/behavior_mcp/authoring.py` byte-for-byte as `scalar-models.v1` version 1.
Add explicit immutable implementation versions under `structured-models.v2`: 2.0.0 for the
Approval MVP, then 2.1.0/2.2.0/2.3.0 for later additions. Each exact code/schema closure is packaged
and retained. This applies the demonstrated source-identity constraint to v2 as well as v1.
[Version retention](contracts/adapter-versions.md) defines publication and regression gates.

**Rationale**: Existing construction contexts hash that file, and reconstruction compares exact
context/release identities. Even adding one newline makes active capability discovery and whole-
system recovery unavailable, not just editing. Current SHA256 is
`32289a08c99625eb489f67ac0c50bcf8f5692cd80e12a2660ce5837c19533b7c`.

**Alternatives considered**: Editing the existing adapter, weakening identity checks, rewriting
stored contexts and accepting only historical Wire replay. All break the retained authoring or
runtime requirement. A new dispatcher is justified by two actual versioned implementations.

**Evidence**: [Probe](evidence/compatibility_probe.py), [results](evidence/compatibility_results.json).

## R2 — Reuse public model constructors and preserve source

**Decision**: Translate a bounded JSON authoring profile into public typed declarations and model
constructors. Preserve complete original input, construction context and canonical outputs.
Operational models use `BehaviorModule(models=...)`; Safety Models use its `safety=` input.

**Rationale**: Approval and WorkQueue are available in the exact wheel. Canonical documents
continue to contain hashes rather than all expression/declaration bodies. Wire import preserves
runtime identity but loses receipts. Safety policies have a separate output/identity contract.

**Alternatives considered**: Canonical-only editing, a generic workflow language, client Python
and hand-built Wire. Existing GAP-001–GAP-003 explain why these are insufficient or forbidden.
The expanded JSON is retained authoring input, not a competing canonical format or interpreter.

**Evidence**: [Operational probe](evidence/operational_models_probe.py),
[Safety probe](evidence/safety_public_api_probe.py), [existing gaps](../../SEMANTIC_GAPS.md).

## R3 — Approval outcomes must be public Core reads

**Decision**: Register both decision capabilities with trusted actor context and explicit typed
payload initialization. Add a fixed declared status read using public `read`, `project` and the
Approval object's `approve_count`, `reject_count`, `approved`, `rejected`, `pending` handles.

**Rationale**: Approval generates derived values but no declared status read. A declared wrapper
is discoverable in admitted Wire and invocable through `Store.read_intent`. The probe records
approval, duplicate rejection denial, a second actor's approval and an exact replayable read.
Counts are never calculated in the host. Read wrapper names are host-authored names, not claims
about upstream generated names; adding them participates in whole-module identity.

**Alternatives considered**: Host counting, client expressions and a hidden ad-hoc read inventory.
Declared fixed wrappers have an inspectable contract and survive unchanged reconstruction.

**Evidence**: [Operational results](evidence/operational_models_results.json), including
`approval.read_after`, admitted read signatures and `read_replay=true`.
The [composition probe](evidence/composition_probe.py) also admits Approval over a RequestFlow
contributed request entity and WorkQueue beside StateMachine with generated-action FieldOwnership;
see [composition results](evidence/composition_results.json). RequestFlow's public initializer
requires the requester value explicitly; it must not be omitted or guessed during reconstruction.

## R4 — WorkQueue requires all nine capabilities

**Decision**: Author all nine public capability registrations. Each of enqueue, claim, recover,
exhaust and cancel has an explicit Boolean authorization fragment. Restriction uses authoritative
false conditions and independent host allowlists, not omitted registration.

**Rationale**: The public model rejects an incomplete capability set. Queue time is an ordered
nominal built with `nominal(name, int, ops={"order"})`. Raw JSON integers are accepted. Generated
`ready` and `expired` reads take `now` in context and return ID-only records. Add a fixed declared
terminal-status projection using the public queue handle.

**Alternatives considered**: Optional method registration, guessed parameter names, a scheduler,
and host lease/generation checks. These are incompatible or duplicate authoritative semantics.

**Evidence**: [Operational results](evidence/operational_models_results.json). Lease ending 20
is not expired at 19 and is expired at 20; completion at 20 is denied and recovery allowed.

## R5 — Separate trusted bindings from context proposals

**Decision**: The host supplies actor, worker and `now`. New operations can submit a closed
`context_proposals` object for `lease_until` and retry/recovery `available_at`; these enter Core
context only after host delegation checks. Enqueue `available_at` remains an input because that
is its actual public signature. Unknown or caller-provided trusted keys are refused.

**Rationale**: Current MCP only injects `actor`. Queue worker/time values are context parameters,
not ordinary inputs. Use a trusted semantic-time source with profile
`utc-unix-milliseconds.v1`: nonnegative integer milliseconds, distinct from ISO audit/commit time.
Capture both explicitly and preserve them with allowed and refused operation/read evidence.
Tests inject a controlled trusted source. Retries/replay reuse original values; fresh evaluations
capture new values. These are host restrictions, not new queue semantics. Core evaluates against
recorded time; this does not assert a new wall-clock validity guarantee at later commit.

**Alternatives considered**: Client-controlled current time (rejected in clarification A), a
hidden clock in definitions, unrestricted context and substituting a new time into an original
commit bundle. None preserves the clarified trust and original-operation contracts.

## R6 — Lifecycle authoring needs a small typed fragment surface

**Decision**: Add explicit enum, scalar, Id, Ref and ordered-time declarations, small structural
expression nodes and fixed lifecycle action factories. Expressions are traced into public
constructors/operators; they are never evaluated against domain state by the host. Lifecycle
factories cover isolated creation, one literal status assignment and isolated removal, with
explicit mandatory guard roots and at most a subject/parent state binding pair.

**Rationale**: LifecycleDependency examines existing actions; it generates no guard or creation
capability. Public `action`, `create`, `remove`, `set_`, `requires`, `select`, `any_`, `and_`,
`not_` and typed entity/Ref handles express its documented canonical pattern. Fixed typed Python
closures register actions without `eval`, `exec`, source generation or a private binding.

**Alternatives considered**: A universal action language, silently generating policy guards or
only accepting Safety policies over definitions the server cannot author. The bounded factories
cover the feature's actual lifecycle journeys and do not create runtime semantics.

**Evidence**: [Factory probe](evidence/action_factory_probe.py),
[results](evidence/action_factory_results.json), canonical actions in the Safety probe.

## R7 — Safety identity is separate from behavior identity

**Decision**: Preserve the complete public `safety_analysis.to_dict()` output, individual policy
`model_hash`/documents and aggregate `policy_set_hash`, apart from operational receipts. Bind
DefinitionId and this complete policy identity into evidence, activation and exact approval.

**Rationale**: Adding Safety policies can leave BehaviorHash unchanged. The public analysis uses
analysis version 1/checker 3; Safety-only modules need not have operational model receipts.
An analysis reporting `Lowered` can still contain `SAFETY_UNSUPPORTED_LIFECYCLE` issues. Never
infer supported proof coverage or certification from the status word alone.

**Alternatives considered**: Ordinary receipts for all families, hash-only deployment/evidence
lookup and dropping issues when lowering succeeds. Each would misrepresent the public contract.

**Evidence**: [Safety results](evidence/safety_public_api_results.json): same behavior identity
with/without Safety, separate policy hash, missing-guard analysis and successful certificate.

## R8 — Pin the exact released proof toolchain

**Decision**: Add a separately locked Nix input at the exact Behavior commit for its public
`packages.x86_64-linux.safety-proof-toolchain`, solely to provision proof tools. Keep the existing
Python/Behavior/Core graph and existing nixpkgs input unchanged. Set trusted
`BEHAVIOR_SAFETY_TOOLCHAIN` and `BEHAVIOR_SAFETY_TOOLCHAIN_DRV` from this package and verify exact
identities before advertising certification.

**Rationale**: The wheel requires Lean 4.30.0 output
`/nix/store/7m5ds60a41w276hsx3rybv76x3609l6k-lean4-4.30.0`, derivation
`/nix/store/6wy0z2zc7gl2i6vxzcw59i9pdhk2g6b8-lean4-4.30.0.drv`.
The repository's current nixpkgs provides Lean 4.29.1. Merely adding `pkgs.lean4` fails. Upstream
`crates/behavior-models/proofs/toolchain.json` binds its lock SHA256
`ed16bd3f98b17e19e07d6ecafecdd20897024a170f7f3727ed6565c582a01bbe`.
This is a locked tool dependency, not rebuilding the Behavior wheel or consuming a local checkout.

**Alternatives considered**: PATH Lean, current nixpkgs Lean, environment-selected binaries and
silently skipping positive certification in CI. None meets the pinned public proof contract.

**Evidence**: [Pinned manifest](evidence/proof_toolchain.json),
[tagged package](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/flake.nix).
Actual public certification and fresh imported-bundle checking both succeeded:
`Certified under assumptions`, scope `OrdinaryTransitions`, initial validity `Unestablished`.
The exported bundle was 33,043 bytes. Invalid toolchain can raise an exception rather than an assessment;
normalize that as a tool/infrastructure failure without manufacturing evidence.

## R9 — Keep certification, evidence import and state validation distinct

**Decision**: Expose separate bounded certification and fresh evidence-checking tools using
`certify_safety`, `load_safety_bundle`, `verify_safety_evidence`. Retain unverified import separately.
For deployment, acquire `validate_safety_snapshot(Store, incoming_module, at=HistoryRef)` inside
the existing writer boundary, require the applicable Valid result and `matches_anchor`, then
atomically record activation. A previously exposed validation report cannot substitute for this.

**Rationale**: Detached snapshots are rejected by the public validator. The probe produced Valid
and Invalid at exact anchors. Certification establishes a conditional ordinary-transition argument,
not genesis validity, migration permission or authorization. Current-state validity and all-writer
coordination remain host deployment obligations.

**Alternatives considered**: Trusting imported flags, using a matching state hash without history,
reusing old unlocked validity checks, or running Lean during every transition. All conflate
independent boundaries or add unnecessary runtime dependencies.

## R10 — Preserve Core recovery and bounded complete reads

**Decision**: Reuse existing durable operation binding, original bundle commit, refused-result
reproduction, atomic receipt publication and public Core reconciliation with publication disabled.
New reads use `Store.read_intent`, retain full read records and history/StateRef identity, and
replay through `Store.replay_read`. A bounded read worker cannot publish domain state.

**Rationale**: Distinct host OperationIds may share one Core transition. No receipt-only shortcut
is sound. Public reads materialize complete results and have no pagination parameter. Return exact
results within limits or a structured resource failure; never silently slice them while claiming
the original record proves a different result. Existing paged snapshot reads remain separate.

**Alternatives considered**: Per-family commit logic, direct SQL updates, a generic host query engine
and fake pagination. None is needed or preserves exact upstream evidence.

## R11 — Version delegation, packaging and evidence producers

**Decision**: Use the completed [host-policy v2 grammar](contracts/host-policy-v2.schema.json),
[exact approvals](contracts/activation-approval-v2.schema.json) and
[expanded result grammar](contracts/expanded-result.schema.json), with finite matching and
non-waivable boundaries specified in [host-policy.md](contracts/host-policy.md). Old v1 grants authorize no
new model/effect/read/safety operation by omission. V2 may explicitly allow both retained and new
profiles. Use the subject definition's release/context in every result, worker and audit artifact,
not a global legacy release helper. Package frozen and new schemas under unique resource names.

**Rationale**: Current candidate checks assume every model has transitions and only two kinds;
new kinds alone are insufficient. Storage already supports immutable typed blobs and versioned
JSON deployment metadata; a second domain-state store or relationship registry is unnecessary.

**Alternatives considered**: Widening v1 lists/defaults, reusing global adapter identity and
repository-only schema resolution. These broaden authority or fail retained/installed execution.

## Research Closure and Remaining Limits

Review remediation I1/U1/I2 adds immutable incremental adapter versions, complete closed policy/
approval/result schemas with matching rules, and per-slice registry/result delivery. US6 audits
already delivered interfaces; it is not the first point where early models become discoverable.

No new blocking upstream capability gap was established for the mandatory journeys. GAP-001
(canonical editing), GAP-002 (generic metadata), GAP-003 (external provenance) and GAP-004
(governed migration boundary) remain as recorded. Reads are complete, proof outcomes conditional,
and the JSON grammar is bounded. Official acceptance must demonstrate all advertised constructs
and the pinned certification environment; a planning probe cannot satisfy that release gate.
