# Public Capability Gaps

**Reviewed**: 2026-10-26

Baseline: Behavior 0.14.0, commit `1cba9e16ff73f927ae08e70a7bc74a6ca52355e4`, bundling
Core 0.15.0, commit `6b93898a9375113f7a8946f23ab5535319b6f5d6`, verifier 0.10.0.
These are public-interface findings, not claims that Core's admitted semantics are deficient.

## GAP-001 — Canonical-Only Editable Reconstruction

- **Required capability**: Load a canonical model document, recover its full declarations and
  expressions, inspect/revise it and lower it faithfully through public interfaces.
- **Release**: Behavior 0.14.0 / Core 0.15.0, identities above.
- **Interface and attempt**: Inspect canonical documents from `module.model_receipts`; inspect
  public StateMachine, RequestFlow, Approval and WorkQueue constructors and document import
  surfaces. Receipt conversion and Wire re-admission were evaluated separately.
- **Category**: Authoring-related.
- **Reproducible evidence**: [Public API probe](specs/001-agent-native-systems/evidence/public_api_probe.py)
  and [observations](specs/001-agent-native-systems/evidence/public_api_results.json).
  [Canonical construction](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/crates/behavior-models/src/identity.rs)
  and [RequestFlow construction](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/crates/behavior-models/src/request_flow/identity.rs)
  contain declaration/fragment hashes and initializer hashes, not complete reconstructible bodies.
  Public model classes expose no model-document loader.
- **Impact and severity**: Blocking for arbitrary canonical-only editable authoring. Limited
  impact on a bounded authoring subset that retains complete original input and context.
- **Proposed upstream resolution**: A supported complete authoring document/import interface,
  or a documented reconstruction context carrying referenced declarations and typed fragments.
- **Interim behavior and review**: Persist explicit versioned proposal/context plus canonical
  output, module and receipts. Translate only bounded data into public constructors, with no
  guessing or semantic interpreter. The plan reviews the risk of incomplete context; unchanged
  reconstruction and semantic revision tests must pass before the subset is advertised.
- **Status**: Open upstream; canonical-only reconstruction remains unsupported. No acceptance
  criterion requiring that capability may be labeled complete on the basis of this workaround.

## GAP-002 — Complete Generic Model Configuration Metadata

- **Required capability**: Discover complete authoring schemas, constraints and capabilities for
  every supported model directly from public authoritative metadata.
- **Release**: Behavior 0.14.0 / Core 0.15.0, identities above.
- **Interface and attempt**: Inspect public model exports, constructor signatures and the
  [family registry](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/crates/behavior-models/src/kinds.rs).
- **Category**: Authoring/discovery-related.
- **Reproducible evidence**: The published registry enumerates families, while released public
  Python constructors provide no complete generic configuration-schema registry. The probe's
  exported runtime actions demonstrate a distinct source for generated invocation information.
- **Impact and severity**: Blocks universal schema-driven authoring discovery. Does not block
  a pinned, explicitly bounded adapter whose configuration and provenance are honestly labeled.
- **Proposed upstream resolution**: Versioned public model-descriptor/configuration metadata,
  linked to supported constructors and canonical documents.
- **Interim behavior and review**: Advertise host-owned subset schemas with exact source/version
  provenance and unsupported features. Obtain semantic diagnostics from authoritative admission.
  Do not describe these schemas as an upstream universal registry.
- **Status**: Open upstream; general discovery completeness is unestablished.

## GAP-003 — Model Provenance Is Not Restored by Wire Import

- **Required capability**: Recover generated modules together with their original model source,
  receipts and diagnostics after restart.
- **Release**: Behavior 0.14.0 / Core 0.15.0, identities above.
- **Interface and attempt**: `BehaviorModule.to_wire_json` followed by `from_wire_json`.
- **Category**: Authoring/artifact-related.
- **Reproducible evidence**: Re-admission preserves BehaviorHash and SchemaHash but returns empty
  receipt/diagnostic collections. See [import implementation](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/python/behavior/module.py)
  and the recorded public probe.
- **Impact and severity**: Operational provenance obligation; not a Core semantic defect and
  not a blocker if artifacts are stored separately and correctly related.
- **Proposed upstream resolution**: Optional supported provenance bundle/validation interface,
  or explicit consumer guidance that model provenance is external to Wire modules.
- **Interim behavior and review**: Store original authoring input/context, canonical documents,
  receipts, diagnostics and exact release identities alongside the generated module. Rebuild
  through authoritative constructors before activation; receipt deserialization is only loading.
- **Status**: Managed host responsibility; upstream behavior preserved.

## GAP-004 — Governed Prepared Migration in Python

- **Required capability**: Commit schema migrations requiring independent authenticated v2
  authorization through the same supported public Python runtime surface.
- **Release**: Behavior 0.14.0 / Core 0.15.0, identities above.
- **Interface and attempt**: Inspect public `Store.migrate`, `verify_migration` and
  `authorize_migration`. The latter documents the missing Python trusted prepared-commit path.
- **Category**: Operational/verification integration.
- **Reproducible evidence**: [Public migration documentation](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/python/behavior/governance.py)
  contrasts Python's structural migration route with the trusted public Rust prepared-migration
  interfaces. This is a tagged-source finding; no governed migration was executed in this research.
- **Impact and severity**: Blocking when that authenticated migration contract is required.
  Ordinary public migrations exist; this finding does not declare all upstream migrations absent.
- **Proposed upstream resolution**: Expose the supported prepared migration and independent
  commit context through released Python bindings, with conformance fixtures.
- **Interim behavior and review**: Initial MCP release refuses every schema-changing activation;
  demonstrate same-schema behavior revisions instead. No private binding or direct state rewrite.
- **Status**: Open conditional gap. Schema migration support remains explicitly undelivered.

## Implemented Evidence and Remaining Limits

The bounded RequestFlow and StateMachine adapters, durable artifact/state storage, explicit host
activation and original-operation recovery are implemented and exercised by deterministic tests.
See [runtime evidence](specs/001-agent-native-systems/evidence/us2.json),
[revision/replay evidence](specs/001-agent-native-systems/evidence/us3.json), and the independent
[composition comparison](tests/integration/test_model_composition.py). None closes GAP-001 or
GAP-002: the retained authoring proposal remains necessary, and its schema is explicitly host-owned.
GAP-003 is managed by separately retained source/context/documents/receipts, with fresh public
reconstruction before activation and public Core Wire admission for historical replay. GAP-004
continues to block schema-changing MCP activation; ordinary upstream migrations are not denied.

The implementation also established that enum declaration order must be explicit in the retained
authoring data. Ordered case arrays prevent JSON object-member sorting from changing the public
Enum declaration. This was a host representation defect, corrected through a failing independent
identity/runtime comparison; it is not an upstream semantic gap.

## GAP-005 — Scalar literal equality has no top-level symbolic constructor

- **Release/interface:** Behavior 0.14.0 / Core 0.15.0; public top-level scalar and
  Enum authoring, overloaded symbolic equality and `and_`/`or_`/`not_`.
- **Required capability / attempt:** Preserve an explicit typed equality with a scalar
  literal on the left without evaluating it in Python. The release does not export a
  general scalar expression/literal constructor at the declared top-level boundary.
  Python `True == 1` returns `True` before Core can type-check either operand.
- **Classification / severity:** Authoring, bounded nonblocking limitation. Symbolic-left
  comparisons used by the supported operational and lifecycle journeys remain available.
- **Reproduction:** `tests/unit/test_fragments_v2.py::test_literal_equality_is_never_evaluated_by_python`;
  its recorded failing case is in feature 002 evidence T010. The negative fixture previously
  admitted a Python-folded Boolean instead of preserving the requested typed comparison.
- **Interim behavior:** Explicit `UNSUPPORTED` for scalar/Enum-left equality. No folding,
  operand swapping, private `lift`, hidden nominal declaration or handwritten Wire fallback.
- **Proposed upstream resolution:** Public typed literal/equality constructors, with
  preserved operand order and public admission/type checking.
- **Status:** Open; this restriction is included in expanded authoring support diagnostics.
