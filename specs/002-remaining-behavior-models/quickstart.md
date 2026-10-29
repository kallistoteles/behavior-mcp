# Validation Guide: Remaining Behavior Models

This guide exercises the versioned model adapters through public MCP tools and trusted administration.
All examples are generic and all tests run without a live AI model.

## Prerequisites and baseline

From the repository root, use the existing locked development environment:

```bash
nix develop --command uv sync --locked --no-build-isolation
nix develop --command ./scripts/check
```

Retain a pre-feature workspace/context fixture. Confirm its authoring source identity is
`32289a08c99625eb489f67ac0c50bcf8f5692cd80e12a2660ce5837c19533b7c` and that its original input,
active definition and history are preserved. Do not alter a real workspace to manufacture a
legacy fixture; tests create isolated workspaces through supported public operations.

## Reproduce the public research

```bash
nix develop --command uv run --locked python -B specs/002-remaining-behavior-models/evidence/operational_models_probe.py
nix develop --command uv run --locked python -B specs/002-remaining-behavior-models/evidence/action_factory_probe.py
nix develop --command uv run --locked python -B specs/002-remaining-behavior-models/evidence/composition_probe.py
nix develop --command uv run --locked python -B specs/002-remaining-behavior-models/evidence/compatibility_probe.py
nix develop --command uv run --locked python -B specs/002-remaining-behavior-models/evidence/safety_public_api_probe.py --certify
```

The Safety command requires the exact immutable Lean package in
[evidence/proof_toolchain.json](evidence/proof_toolchain.json). The development flake provisions it through the separately pinned public Behavior proof-toolchain
input. The gate checks its exact derivation, output and Lean version before running positive proofs. Missing or
wrong tools must fail explicitly; do not substitute current nixpkgs Lean or skip the positive case.

Expected research results: Approval duplicate decision denied and second-actor threshold reached;
queue expiry changes exactly at lease boundary; reads replay; fixed factories produce two allowed
commits without source generation; changed legacy source identity breaks reconstruction until
restored; Safety analysis preserves issues, public snapshot validation yields Valid/Invalid,
certification and fresh import checking each yield `Certified under assumptions`. These outcomes
are feasibility evidence, not an independent proof of the Behavior implementation.

## Trusted setup

Use a disposable workspace and trusted local launcher configuration. Install an explicit v2
operator policy through the existing administration CLI, using [host-policy](contracts/host-policy.md).
Allow only intended model IDs, actions, reads, condition/effect scopes, safety policies and proposed
time bounds. Enable `safety-default` and exact proof tooling where required. Provision actor records
through Core genesis or authorized transitions, never SQL/document edits or agent authority flags.

```bash
nix develop --command uv run --locked behavior-mcp-admin install-policy \
  --workspace /absolute/disposable-workspace \
  --trusted-config /absolute/admin.local.json \
  --document /absolute/policy-v2.local.json
nix develop --command uv run --locked behavior-mcp serve \
  --workspace /absolute/disposable-workspace \
  --host-config /absolute/launcher.local.json
```

Use the committed Approval/queue/lifecycle policy examples in contracts/examples/ as bounded
design templates, never as installed or authenticated grants. Every v2 proposal names its exact
adapter_version. Use an ordinary MCP client; no AI model is needed. The trusted launcher supplies principal,
workspace, Actor mapping and `utc-unix-milliseconds.v1` provider. Caller arguments cannot supply
or override trusted identity/current time.

## End-to-end acceptance journeys

1. **Catalog and authoring**: Call models_list; inspect all six families and exact bounds. Submit
   each complete JSON fixture under [contracts/examples](contracts/examples) through
   definition_propose and definition_validate. Inspect exact retained source, operational receipts,
   separate safety analysis/policies and actual action/read inventory. No definition is active.
2. **Approval**: Use examples/approval.json. Create an inactive system and explicitly activate
   within delegation. Create a generic subject, record an approval, attempt a duplicate rejection
   and record a second trusted actor's approval. Read `mcp_review_status` through capability_read.
   Check authoritative counts/pending/approved/rejected values, no implicit subject mutation and
   exact refused retry. Tests use trusted contexts and Core-created actor records, not caller actor IDs.
3. **WorkQueue**: Use examples/work-queue.json. Enqueue a labeled item, claim at controlled trusted
   time 10 with lease_until=20 and expected_generation=0, read ready/expired, renew, retry/reclaim,
   complete/fail and cover recover/exhaust/cancel in independent fixtures. Exercise all nine
   capabilities, boundaries before/at/after expiry, stale generations and competing claims.
   Reject forged now/worker/actor and out-of-delegation time proposals without mutation.
4. **Field ownership**: Use examples/field-ownership.json. Validate allowed generated transition,
   creator and remover selectors. Remove each required permission in separate negative fixtures;
   confirm authoritative refusal, including an explicit empty writer list and overlapping policies.
   Structural lowering is visibly uncertified.
5. **Lifecycle and evidence**: Use examples/lifecycle.json. Request explicit Safety certification,
   export the definition-bound bundle, submit it to fresh checking and retain the separate checking
   assessment. Reject tampered subject/policies/toolchain/evidence; missing guards remain unsupported
   issues, not a successful proof. Validate current state through state_validate_safety.
6. **Activation and evolution**: With required evidence, explicitly activate against expected
   exact history. A concurrent writer, invalid incoming state or missing proof must block activation.
   Revise a policy without changing behavior; confirm distinct policy/definition identity, no reuse
   of mismatched proof/approval and no implicit activation. Schema-changing activation stays refused.
7. **Persistence and isolation**: Restart and recover every family, rebuild unchanged, revise each
   and interpret historical records with original artifacts. Exercise both required compositions,
   two independent systems and unauthorized cross-system requests.
8. **Retained checkpoint compatibility**: After each accepted checkpoint, keep its real workspace
   and reopen it after the next version is added: 2.0.0 → 2.1.0 → 2.2.0 → 2.3.0. Inspect, invoke,
   recover, rebuild and revise using its original handler/schema, without regenerating fixtures,
   changing contexts or loading code from the workspace.
9. **Crash/retry**: Kill before and after approval/queue publication, lose acknowledgments and change
   current policy/activation. Reconcile original outcomes before retrying anything; identical requests
   cannot cause duplicate events. Also interrupt a read after its time/history is journaled; retry
   obtains the same read subject/time without domain writes.
10. **Resource and installed package**: Oversized stdout/stderr, hung workers, oversized complete
   reads and proof-resource exhaustion return honest failures and release worker capacity. Run the
   full suite against clean installed artifacts and compare source-rebuilt wheel bytes. No schema
   or runtime dependency may be resolved from an uninstalled checkout.

Feature test entry points:

```bash
nix develop --command uv run --locked pytest tests/acceptance/test_remaining_models.py
nix develop --command uv run --locked pytest tests/integration/test_expanded_compatibility.py
nix develop --command uv run --locked pytest tests/integration/test_incremental_adapter_retention.py
nix develop --command uv run --locked pytest tests/integration/test_safety_deployment.py
nix develop --command ./scripts/check
```

## Evidence and acceptance

Record observed failing tests before production changes, then successful public-boundary tests.
Map each FR/SC to resulting tests and retained evidence. Keep exact public proof outcomes,
assumptions, scope, initial-validity limitation and dependency identities. Certification evidence
is not approval; current-state validation is not a universal proof.

README/operations/compatibility/gaps, package resources and CI artifact paths must match the
observed gate results. All four added families must meet their mandatory journeys;
any blocking gap remains explicit and prevents calling the complete feature delivered.
