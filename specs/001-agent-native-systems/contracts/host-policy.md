# Trusted Host Policy and Administration Contract

This is operational authorization, separate from Behavior semantics, Core genesis EvidencePolicy,
Core ExecutionPolicy and proof evidence. The closed input formats are
[host-policy.schema.json](host-policy.schema.json) and
[activation-approval.schema.json](activation-approval.schema.json).
[example-host-policy.json](example-host-policy.json) is a concrete local acceptance configuration.

## Trusted Inputs and Administration

The launcher establishes principal, WorkspaceId/root binding, policy source and local Actor mapping.
Stdio, roots, client metadata and tool arguments grant no authority. The separate local
`behavior-mcp-admin` channel installs policy versions and exact-version approvals; it is absent
from MCP's registry. Issuer strings in documents are audit labels, not authentication: the
administrative caller and its workspace authority must be established independently by the host.
Installation rejects an issuer_id differing from that trusted administrative principal; it is
never repaired or accepted as proof of who submitted the document.
The initial boundary assumes trusted launcher/configuration; it is not OS multi-user isolation
from an unrestricted same-user process.

Every tool requires an explicit operation grant. System operations also require the current
principal, workspace and target system scope. Artifact grants are workspace-scoped and reveal
neither another system's state/history nor the systems referencing a shared blob. Creation is
its own grant and does not add runtime permissions or alter system selectors.

Action invocation also checks the current exact capability-name allowlist. Construction, effect
and state bounds govern candidate activation; changing them does not rewrite an existing active
definition or historical Core meaning. Revoke an active capability's use by removing its runtime
capability name or operation grant. An exact activation exception does not add either grant.

## Closed Version 1 Grammar

Unknown fields, enum values, selector kinds, profiles, unsupported releases or malformed approvals
are rejected. Lists contain exact values; there are no globs, regular expressions, implicit
inheritance, executable predicates or policy plugins. Missing rules deny permission; empty
permission lists grant nothing. All applicable conditions combine with AND.

| Field group | Matching rule |
| --- | --- |
| Identity | `policy_id` + positive integer `version` identifies an immutable host-issued object. Retain old referenced versions. |
| Principal/workspace | Exact equality with trusted launcher context; caller-supplied identities never establish the match. |
| System selector | `kind=ids` is exact membership in `system_ids`; `kind=workspace` explicitly selects systems in the trusted workspace. Both still require operation and candidate bounds. |
| Operations | Exact MCP tool-name membership. No field or selector implies a missing tool permission. |
| Construction | Exact supported adapter profile/version and release identities; every model kind, model ID and authoritative generated capability must be allowlisted. |
| Effects | Every used initializer/assignment form and target field must be listed. External commands and host permission expansion are false in this version. |
| State | New-record/existing-record effects require the respective boolean; every proposed status and transition edge must be listed. Schema migration is false. |
| Creation | Requires systems_create permission, `system_creation.allowed`, capacity and permitted construction/state bounds. Only the explicit bootstrap Actor is seeded. |
| Verification | Every configured requirement must match a trusted stored public report for the exact candidate, profile and semantic profile; required checks/obligations must be verified and assumptions must be permitted. |

A workspace selector is an explicit grant over targets, not workspace membership. It never waives
model/capability/effect/state/evidence bounds. Exact-ID policies do not automatically add newly
created systems. Capacity counts initialized systems and durable pending reservations; retrying
one creation OperationId does not consume another slot. Lowering a limit never deletes history.

Candidate checks use a fresh reconstruction through the allowed trusted adapter and authoritative
admission/output. Supported source descriptors identify the adapter's fixed typed transfers;
compare them with the fresh canonical/module identities. Do not trust client manifests, infer
expression bodies from hashes or introduce an interpreter to inspect arbitrary semantics.
Unknown constructs or incomplete authoritative coverage fail closed.

## Evidence and Core Policy Separation

The host policy, immutable Core genesis policy and runtime Core execution policy remain distinct.
`system_creation.core_policy_profile=structural-none` explicitly selects the supported public
structural creation/commit path; it is required configuration, not fallback after proof failure.
Unsupported authenticated execution-policy configurations are refused initially.

`required_verification=[]` explicitly means the operator requires no formal proof for activation;
it does not mean that the definition is safe or verified. A nonempty list requires every named
profile/check/obligation for the exact BehaviorHash and toolchain, actual verified upstream
outcome and complete required coverage. Missing, inconclusive, unsupported, incomplete, timed-out
or mismatched reports fail closed. Assumptions cannot exceed the configured permitted set or
Core's established guarantees. No host policy manufactures proof evidence.

## Exact-Version Approval

An approval binds grantee principal, WorkspaceId, SystemId, DefinitionId, BehaviorHash, SchemaHash,
policy ID/version, expected activation revision and exact Core HistoryRef. All must match the
live request and coordinated boundary. Approval is issued through the independently trusted
administrative channel and is immutable.

`exceptions` may waive only named candidate bounds: adapter version, model kind, model ID,
capability set, typed effect or state-change bounds. The approved full definition identifies the
exact exception; this is not a wildcard permission or reusable approval of a future revision.

Approval cannot waive launcher principal/workspace, system scope, explicit operation grants,
supported public-interface availability, required admission/proof/current-state checks, schema
migration refusal, external-command refusal or prohibition on modifying host authority. Extending
those supported host grants requires trusted policy administration, never agent model content.
An activation exception does not grant new runtime invocation permissions; every runtime call
still requires its current system/operation/capability authorization.

## Coordination, Receipt Lookup and Policy Changes

Use one documented local policy-before-system lock order shared by server and administrative
processes. Policy updates conflict with checks that rely on their version. Activation checks the
current pointer, policy and exact history while holding the relevant writer boundary, then
publishes active pointer, activation record and request/result receipt in one system transaction.

On an identical activation retry, inspect the durable receipt before re-running activation CAS
or proof checks. Returning that historical outcome requires current `operation_get` permission
for the same principal/workspace/system; lack of read authority denies disclosure and never
initiates a fresh activation. A changed current policy does not relabel or reauthorize an already
published operation. If no receipt establishes publication, any potentially new activation needs
all current grants and conditions. See [the retry contract](mcp.md#activation-retries).

Every activation records exact subject, policy version, authorization and history. New requests
use current authority; old audit remains attributed to its original policy and toolchain. Policy
updates do not rewrite Core genesis or historical proof. Agents cannot administer delegation.

## Required Negative Acceptance

- A workspace match with a forbidden model/capability/effect cannot activate the candidate.
- A forged actor/issuer/approval or shared BehaviorHash grants no authority over another SystemId.
- Invalid selector kinds, unknown fields and absent rules are rejected or deny permission.
- A stale policy, active revision or history cannot authorize new publication.
- Exact-version approval cannot cross principal/system/definition/policy/history bindings.
- Missing or non-verified required proof cannot become success by schema shape or claimed flags.
- Retrying a published activation returns its original receipt rather than mutating again.
- Schema-changing activation, external effects and host-policy self-modification remain unsupported.

In this initial policy grammar, required_check_ids are exact public attestation checks[].key
identities and each must have the literal public outcome proven. The overall verified status alone
cannot satisfy an inconclusive, unsupported or otherwise unproven required check. This is a host
restriction; it does not reinterpret other public check kinds or counterexample outcomes. Required
obligation IDs that the released report does not expose fail closed. semantic_profile_id is
wire_ir:<version>, using the actual admitted public Wire export rather than an assumed version.
