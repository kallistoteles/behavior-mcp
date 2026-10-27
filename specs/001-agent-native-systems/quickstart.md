# Quickstart and Acceptance Guide

Run commands from the repository root. The public probe and the implemented server/administrative
commands are runnable. Configure trusted host authority as described in
[operations](../../docs/operations.md), and use the same locked quality command as CI.

## 1. Reproduce the Released Public-API Probe Now

Prerequisites: Linux x86_64 with glibc >=2.28, Python 3.13, Nix, curl and SHA256 tooling.
The recorded run used Python 3.13.14. Use the exact released wheel, not a checkout or a package
selected only by a similar name. The temporary environment is research, not production storage.

```bash
behavior_probe_dir="$(mktemp -d /tmp/behavior-mcp-phase0.XXXXXX)"
behavior_nixpkgs=github:NixOS/nixpkgs/293d6abedf0478e681a4dfcfcb35b30fc796a32f
curl --fail --location \
  https://github.com/kallistoteles/behavior-ir/releases/download/v0.14.0/behavior-0.14.0-cp313-abi3-manylinux_2_28_x86_64.whl \
  --output "$behavior_probe_dir/behavior-0.14.0-cp313-abi3-manylinux_2_28_x86_64.whl"
printf '%s  %s\n' \
  794d2dd5ddf8613c52f524a1b4b74c0246d86a5ea52414424ab89ef104e86513 \
  "$behavior_probe_dir/behavior-0.14.0-cp313-abi3-manylinux_2_28_x86_64.whl" | sha256sum --check
nix shell "$behavior_nixpkgs#uv" "$behavior_nixpkgs#python313" \
  --command uv venv --python python3.13 "$behavior_probe_dir/venv"
nix shell "$behavior_nixpkgs#uv" --command uv pip install \
  --python "$behavior_probe_dir/venv/bin/python" \
  "$behavior_probe_dir/behavior-0.14.0-cp313-abi3-manylinux_2_28_x86_64.whl"
"$behavior_probe_dir/venv/bin/python" \
  specs/001-agent-native-systems/evidence/public_api_probe.py \
  > "$behavior_probe_dir/observed.json"
```

Compare the observations to [recorded results](evidence/public_api_results.json). Expected:
creation/completion `ALLOW`; missing input `INVALID_INPUT` with unchanged head; repeated completion
`DENY` without a bundle; unchanged reconstruction preserves identities; a renamed transition
changes model/behavior identity with unchanged schema; composition has two receipts and changes
whole-module identity without changing RequestFlow's ModelHash; Wire import preserves executable
identities but has no model receipts. Identical genesis in separate backends has equal Core
StoreId, while the untouched backend stays at position zero. Same-schema snapshot validation
returns `behavior.snapshot_export.v1`.

The probe prints actual public results. It does not establish physical durability, MCP behavior,
host authorization, formal verification or unrestricted canonical-only authoring. The probe's
byte digest identifies its research source; it is not a Behavior semantic identity.

## 2. Implementation Prerequisites

The repository provides the package, `flake.lock`, complete hashed `uv.lock` and deterministic
tests. The trusted operator supplies workspace/launcher/administrative configuration.
Behavior must remain the exact released artifact above. A compatible public API, successful
dependency checks and the declared toolchain are mandatory; no local upstream override counts.

The trusted operator starts from [example-host-policy.json](contracts/example-host-policy.json),
validated by the closed [host-policy schema](contracts/host-policy.schema.json), and independently
authenticates policy installation. The operator configures one local principal/workspace, versioned delegation,
explicit structural/no-required-Core-evidence profile, the fixed local Actor mapping and permitted
bootstrap seed. The acceptance delegation permits the two bounded adapters, creation and approved
runtime actions, and a same-schema transition-name revision. It forbids external commands,
permission expansion, schema changes and agent modification of policy. Required proof profiles,
if configured, must succeed rather than being silently dropped.

The separate trusted administration interface installs policy/approvals. MCP exposes neither.
An unrestricted same-user process can act outside this boundary; this guide claims configured
MCP authorization rather than OS multi-user isolation.

## 3. One Reproducible Quality Gate

```bash
nix develop --command ./scripts/check
```

This exact command bootstraps the locked build/runtime environment and runs dependency/identity/public-boundary checks,
formatting, lint, strict types and every applicable deterministic, conformance, persistence,
authorization and acceptance check. CI and release use the same command and committed graph.
All feature tests must first be observed failing before their behavior is implemented.

Expected final result: all gate stages pass; `run_conformance` reports all 45 baseline cases
passing; real process-crash tests also pass. An in-memory probe, isolated unit suite or skipped
failure-path fixture cannot replace this evidence. Recorded implementation checkpoints and final release acceptance retain the actual commands/results.

## 4. Launch the Implemented Server

Invocation, after trusted configuration exists:

```bash
nix develop --command uv run --locked behavior-mcp serve \
  --workspace /tmp/behavior-mcp-acceptance \
  --host-config /tmp/behavior-mcp-acceptance-trusted.json
```

The configuration is supplied by the trusted operator, not by MCP tool input. The process owns
the workspace lock; a second live owner refuses startup. Stdout contains protocol messages only.
Tests use the public SDK's in-memory Client and real `StdioServerParameters`, modern and legacy
mode, without an AI model or note application.

## 5. End-to-End Tool Journey

See [MCP contracts](contracts/mcp.md), [data ownership](data-model.md) and
[trusted policy](contracts/host-policy.md) for exact boundaries.

| Step | Interaction | Expected result |
| --- | --- | --- |
| Discover | `models_list` | Bounded adapter schemas labeled as host-owned, with pinned authoritative provenance and unsupported features. |
| Propose | `definition_propose` with [example-proposal.json](contracts/example-proposal.json) | Stored original proposal/context; inactive, unverified, not admitted merely by saving. |
| Admit | `definition_validate` with the returned proposal_id and proposal_revision | Structured stages and immutable DefinitionId with canonical documents, module, hashes and separate receipts. |
| Verify | `definition_verify` using an allowed profile | Exact scoped report; unsupported/inconclusive remains visibly so. No automatic activation. |
| Create | `systems_create` twice using the admitted definition and different OperationIds | Two stable SystemIds and independent inactive Core Stores. Shared artifacts/Core hashes grant no cross-system authority. |
| Activate | `definition_activate` with each system's expected active revision/history | Independent explicit delegated activation, exact BehaviorHash/policy/authorization/history audit. |
| Inspect | `capabilities_list`, `system_inspect` | Actual generated names and roles, including `request_id`; every result targets the selected SystemId. |
| Create data | Evaluate `record__new` with input `request_id=r1`, `label=Example`, then commit its token | Core `ALLOW`, then durable commitment. Actor comes from trusted host context. |
| Complete | Evaluate `record__finish` for `r1` with outcome `Complete`, then commit | Status/outcome change through Core, with durable history. |
| Refuse | Evaluate completion again or omit required creation input | Authoritative `DENY` or `INVALID_INPUT`; no bundle/partial commitment. |
| Read | `state_read` at the checked current or historical anchor | Correct record and identity; no mutation. |
| Restart | Stop and reopen, then use another independent client | Same SystemIds, active versions, records, receipts and interpretable history. |
| Re-author | Retrieve an explicit proposal revision/source context; validate that exact revision twice | Same relevant model/module/schema identities under identical context. |
| Revise | Submit full changed input with base_proposal_id + expected_proposal_revision, preserve parent lineage, validate the returned exact revision and activate only in one system | Distinct model/behavior identity, unchanged SchemaHash/SystemId, other system unaffected. |
| Replay | Replay historical records with their original module artifacts | Historical interpretation is preserved and evidence retains original releases/policy. |

The first complete system is the vertical demonstration. The second system establishes isolation;
it does not require another authoring product or a cross-system workflow. Composition of two model
families is tested inside one module/system through authoritative constructors.

## 6. Required Failure and Recovery Scenarios

| Scenario | Acceptance evidence |
| --- | --- |
| Same immutable artifacts/genesis, different SystemIds | Independent state/history and denied wrong-system token/approval access. |
| Simultaneous use and activation in one system | Only that system's active pointer changes; no false cross-system conflict or history mutation. |
| Competing activation, policy update or intervening state writer | Stale check refuses; successful publication has a current coordinated anchor and exact authority. |
| Crash before publication | No partial Core publication or active-pointer/audit pair. |
| Crash after durable transition publication before reply | Atomic Core receipt/original-bundle recovery establishes one commitment; no re-evaluation first. |
| Crash after activation publication before reply | Retry with the same OperationId/request resolves its atomic activation receipt before stale revision CAS; no second activation/audit append. |
| Another activation follows a lost acknowledgment | Return the original receipt separately from observed current deployment; never infer this operation's outcome from matching BehaviorHash. |
| Concurrent edits or validation | Stale expected proposal revision conflicts; validation of an exact source revision stays frozen when the head advances. |
| Revoked permission during uncertain recovery | Resolve existing outcome without granting a new mutation; any potentially fresh commit needs current authority. |
| Recovery of one system | No reset, overwrite or reinterpretation of the other system. |
| Unsupported schema revision | Activation refused, state/active reference unchanged; no automatic conversion. |
| Cross-system references/transactions or arbitrary effects | Explicit unsupported result, no host-side workflow or effect execution. |
| Fake policy, actor, role or approval in tool arguments | Structured input/authorization failure; no authority expansion. |
| Inconclusive, unsupported, missing solver or timeout | Exact evidence/failure status; no proof-success or activation shortcut. |
| Oversized or malformed frame, extra authoring fields | Bounded structured/protocol failure; credentials and raw sensitive input are not logged. |

Validate [synthetic result examples](contracts/example-results.json) as schema fixtures only. Empty
verified/activated results, verified projections of inconclusive reports and contradictory errors
must fail. Actual evidence must come from public Behavior reports or atomic host publication.

Record actual acceptance results separately from this guide. Report unimplemented or blocked
criteria and [upstream gaps](../../SEMANTIC_GAPS.md); do not mark them passing from this plan.
