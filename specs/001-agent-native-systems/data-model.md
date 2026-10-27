# Data Model

This document describes host artifacts and their relationships. Core document formats and
domain-state validity remain the pinned public persistence contract; this is not a second schema
for Behavior's entity versions, records, hashing or replay.

## Identity and Ownership

| Identity | Authority and meaning |
| --- | --- |
| WorkspaceId | Trusted host namespace bound by the launcher; membership grants no operations. |
| SystemId | Stable opaque host identity, unchanged by definition revisions. |
| DefinitionId / ProposalId | Host references to immutable admitted artifacts or editable proposal revisions. |
| ModelHash / BehaviorHash / SchemaHash | Upstream semantic identities, obtained from public interfaces. |
| Core StoreId / HistoryRef | Core lineage/content identity and exact event anchor, checked by Core. |
| PolicyId + version | Immutable host delegation-policy version; independent of Core policies. |
| OperationId | Durable host request identity bound to workspace, SystemId, operation and exact request. |

SystemId never enters a Core genesis document merely to force a different hash. Two systems may
have identical genesis, StoreId, BehaviorHash and initial HistoryRef while remaining separate
backend targets with separate authority. Evaluation tokens, approvals and recovery keys always
include trusted workspace and SystemId as well as Core identities.

## Host Entities

### Authoring Proposal and Construction Context

Fields: stable ProposalId, positive integer proposal revision, optional parent DefinitionId,
host schema/profile version,
complete declaration and model constructor data, adapter version/code identity, exact Behavior
release identities and separately stored display metadata. Persist the fixed trusted Actor schema
and other adapter-supplied declarations in the construction context; no missing fact is guessed.

The input grammar is [authoring.schema.json](contracts/authoring.schema.json). It is host-owned
and intentionally bounded. RequestFlow/StateMachine normalization, typing and lowering occur only
in public Behavior constructors. Unknown extensions fail explicitly. A changed proposal creates
a new revision; an admitted Definition is immutable.

A new proposal receives a new ProposalId and revision 1. A revision request supplies
base_proposal_id plus expected_proposal_revision, appending an immutable snapshot under the same
ProposalId by compare-and-set; a stale head conflicts without appending. parent_definition_id may
be supplied on a new fork and is inherited unchanged on edits. Parent references require artifact
read authority and never establish permission to activate that definition. The full proposal is
always supplied; a parent reference is not permission to guess omitted content.

Retrieving a proposal without a revision explicitly means latest-at-read and returns the resolved
revision. Validation always requires an exact proposal_id + proposal_revision; head changes cannot
silently alter its subject. Admitted manifests reference that exact immutable source revision.

### Definition Manifest

Fields: DefinitionId, source proposal/context references, ordered composition membership, canonical
model documents and ModelHashes, generated Wire artifact, BehaviorHash, SchemaHash, each lowering
receipt and its model semantic/lowerer version, diagnostics and dependency identities.

Artifacts are durably stored before publishing any system reference. Wire import does not restore
receipts. Reload the stored manifest and rebuild from original data through the exact toolchain;
compare authoritative outputs before activation. Receipt loading alone is not validation.

Immutable blobs may be shared. A host byte digest may address physical bytes, but must be labeled
as a byte digest rather than a Behavior semantic hash. Neither digest nor content sharing grants
access to another system or proves that an artifact is approved.

### Behavior System

Fields: WorkspaceId, SystemId, optional display label, creation OperationId, initializing
DefinitionId, Core backend location allocated by the host, Core genesis identity, lifecycle state,
active activation revision and active DefinitionId.

Creation accepts an admitted definition and trusted creation authority. The host supplies the
explicitly configured bootstrap Actor seed; it is not inferred from client actor claims. Core
`Store.genesis_for` and `Store.create` establish the initial state. Creation leaves the system
inactive. Runtime requests fail until separate authorized activation.

Lifecycle: `creating` → `inactive` → `active`; uncertain publication enters `recovery_required`.
These are host operational states. A durable reservation binds creation OperationId to SystemId
before creation; retries recover that same target. Public Core creation recovery must preserve
later history. Incomplete provisioning is not presented as an initialized or active system.

Each system has a separate Core Store, genesis, state, history, active pointer and concurrency
boundary. No cross-system reference, transaction, implicit dependency or orchestration exists.

### Delegated Activation Policy

Fields: PolicyId/version, trusted issuer, principal/workspace/system/operation selectors,
system-creation authority, allowed adapter identities and model/capability bounds, allowed typed
effect forms, external-command restriction, seed/state-change/migration permissions, required
verification evidence and deployment conditions.

Only the separate trusted host channel creates versions or changes the applicable policy
reference. Retain referenced versions forever in this release. An agent-authored declaration,
workspace membership, tool metadata or claimed approval cannot modify this object or satisfy it.
See [host-policy.md](contracts/host-policy.md).

Core's genesis EvidencePolicy and runtime ExecutionPolicy are different objects. Initial trusted
configuration explicitly selects the public structural/no-required-evidence profile; unset policy
does not silently select it. Stronger unsupported governance requirements fail closed.

### Exact-Version Approval

Fields: ApprovalId, trusted issuer/authorization evidence, grantee principal, WorkspaceId, SystemId,
exact DefinitionId, BehaviorHash and SchemaHash, applicable policy identity/version, expected
activation revision, exact history anchor and explicitly approved exception scope. The closed
[approval schema](contracts/activation-approval.schema.json) requires every binding.

The trusted host channel issues this object. It cannot authorize another definition or waive Core
admission, required proof, state validity or unavailable migration contracts. Changes to the
delegation itself require trusted policy administration, never an agent policy-update operation.

### Activation Record

Fields: ActivationId, OperationId, request-binding reference, SystemId/workspace, previous and new
host activation revision, DefinitionId,
BehaviorHash, SchemaHash, ModelHash/receipt references, exact Core HistoryRef, policy identity and
version, trusted principal, delegation decision or exact approval reference, validation/verification
evidence and applicable release identities.

Publish this record and the active pointer in one transaction in the system database, together
with a receipt binding the exact parsed request, trusted principal/workspace/SystemId, OperationId
and immutable published outcome. Receipt lookup precedes any retry CAS; matching BehaviorHash
alone never proves that this operation activated it. Return the original activation record
separately from the observed current deployment, which may have advanced. An active
pointer is a host deployment reference, not a domain-state transition. Preserve prior activation
records. A later host policy never rewrites the authority recorded for an earlier activation.

### Evaluation and Operation Record

Fields: OperationId, trusted workspace/SystemId/principal, operation kind, exact parsed request,
active definition/revision and policy context, source HistoryRef, outcome and response evidence.
The transition subtype additionally retains explicit evaluation context/time, original Core
bundle and Core record/result identities. Activation has no Core bundle: it retains request
binding, activation receipt and original published response. Creation retains its durable
SystemId reservation and Core creation outcome. Operation kinds are transition, activation and
system_creation; recovery must dispatch by kind rather than treating all writes as Core commits.

Evaluation tokens are opaque references to host-stored records, not serialized bundles supplied
by clients and not permissions. The public evaluated bundle is JSON data; persist it unchanged
before any commit attempt. Explicitly capture host time once and retain it; tests inject time.

Operation states: `evaluated`, `committing`, `committed`, `not_committed`, `refused`, `unknown`.
No new system mutation proceeds while a preceding publication is genuinely unresolved. Resolve
the operation receipt and, for transitions, original Core bundle; never evaluate a replacement first. Any retry
that could newly commit must still pass current authorization and deployment checks. A revoked
permission cannot be bypassed by relabeling a fresh mutation as recovery.

The Core backend's commit transaction writes an operational receipt with Core-supplied record
and state identities. A head conflict writes no success receipt. Core's original-bundle retry
can report `already` without calling the backend again. Reusing an OperationId with different
scope or request is an input conflict, never implicit replacement.

Activation receipts publish atomically with pointer and audit. A lost acknowledgment is resolved
by the scoped receipt, not Core bundle retry. If another activation has since occurred, return
the original outcome plus separately observed current deployment. Changed-request reuse conflicts;
absent or unreadable receipt never becomes inferred success. Unknown publication blocks further
writes only for the affected system until the original outcome is established.

### Validation / Verification Evidence

Fields: evidence reference, exact subject and releases, structural/model/lowering/admission
status, verification profile/checks/obligations/assumptions, report/attestation identity, actual
result and coverage. Retain raw public evidence plus a structured projection. The discriminated
[result contract](contracts/result.schema.json) requires stage-specific subjects and evidence;
empty verified/activated results are invalid. Schema validity establishes shape only: runtime
checks must bind every projection to the authoritative stored public report or publication.

`verified`, `inconclusive`, `unsupported`, timeout and infrastructure failure stay distinct.
Successful request processing does not imply successful proof. Initial-state validity, deployment
authorization and successful runtime commitment have their own evidence.

## Physical Storage and Atomic Boundaries

```text
workspace/
  host.sqlite                   immutable artifacts, policy versions, creation reservations
  systems/<SystemId>.sqlite      that system's Core docs + active pointer + receipts + audit
```

Names and locations are host-generated; clients never submit paths. The system index is a
reconstructible projection of initialized system descriptors and durable creation reservations.
MCP cannot edit SQL rows or Core documents directly.

The public backend callbacks store genesis/head, immutable content/version/record documents,
lifetimes, references and required as-of indexes. Core supplies the documents and evaluates their
meaning. `create` publishes the complete absent-target genesis/seed or recovers the equivalent
creation. `commit` atomically compares the old head and publishes all supplied changes or none.
Use Core-provided identities rather than recalculating semantic hashes.

Use SQLite transactions with `DELETE` journaling and `EXTRA` synchronization, verify settings,
sync initial directory entries and document filesystem assumptions. The Core conformance suite
and physical fault/restart tests must both pass. SQLite configuration alone is not that evidence.

Shared artifacts/policy versions commit before a system starts referencing them. No cross-file
atomic business transaction is promised. An unused immutable artifact is recoverable garbage;
a published pointer may never reference an artifact that was not durably stored. No GC is added.

## Coordination and Activation Procedure

An activation retry first resolves its request-bound receipt under the same coordination boundary.
Disclosure requires current operation_get permission; it does not repeat activation authorization
or stale CAS for an already published outcome. The following steps apply only when publication
has been established not to have occurred and a new activation may still be attempted.

1. Validate request shape and obtain trusted principal/workspace context. Resolve SystemId and
   authorize the specific operation. Hold a policy read/coordination boundary; trusted policy
   updates acquire its conflicting writer boundary. Hold the target system's writer boundary.
2. Re-read applicable policy, expected activation revision and Core head. Reconstruct the exact
   candidate through its pinned public adapter, compare identities and inspect authoritative
   generated capabilities. Reject missing source, unknown capability coverage or unestablished
   delegated authority. Never trust client manifests as assertions of authority.
3. Require unchanged SchemaHash in the initial release. Call `Store.export_seed_at` with the
   incoming module and exact current HistoryRef. Enforce the policy's actual evidence obligations.
4. Check the exact approval when an exception to delegation is needed. Missing/invalid evidence,
   mismatched history, stale policy or unsupported schema change refuses activation.
5. Atomically publish active pointer, activation record/audit and request-bound original-result
   receipt in the system database, then reply.
   All domain commits, creation recovery and future migrations use the same relevant boundary.
   Other systems retain independent domain state/history and may continue operating.

Runtime evaluation is read-only. At commit, recheck system/deployment/policy context, then let
Core compare the original snapshot and validate the whole result. A conflict requires explicit
new evaluation after the original outcome is known. Recovery of one system cannot rewrite another.
