# Data Model: Remaining Behavior Models

All new objects are versioned integration artifacts. Core continues to own all domain-state,
transition, schema, history and semantic identity contracts. Byte-addressed host blobs use the
existing `bytes-sha256:` namespace and are not Behavior semantic hashes.

## 1. Authoring profile and proposal

- **Selector**: proposal `format=behavior-mcp.authoring.v2`,
  `adapter_profile=structured-models.v2`; required exact input `adapter_version` (2.0.0–2.3.0).
  Each accepted checkpoint retains its immutable code/schema release; see [version retention](contracts/adapter-versions.md).
- **Declarations**: ordered enum case arrays; declared entities/fields; an ordered integer nominal
  time declaration. Typed references name a declared entity or a specific model-contributed handle.
- **Models**: ordered explicit RequestFlow, StateMachine, Approval and WorkQueue inputs.
- **Lifecycle actions**: bounded host-factory descriptors for creation, literal field assignment
  and removal; guard roots are explicit author input.
- **Safety policies**: separately ordered FieldOwnership/LifecycleDependency descriptors.
- **Metadata**: title/description outside semantic input.
- **Revision**: existing ProposalId, monotonic proposal revision, parent DefinitionId and compare-
  and-set editing contract. Existing v1 proposals remain v1 unless an explicit new proposal/profile
  is chosen; upgrade is never guessed during load.

Validation separates host schema/reference resolution from public semantic/type validation.
Names are bounded; unknown nodes fail closed. Do not deduplicate guards, reorder enum cases or
normalize semantic values in the host. Full limits/grammar are in [authoring](contracts/authoring.md).

## 2. Construction context

Existing v1 context and source bytes remain unchanged. V2 stores:

| Field | Meaning |
| --- | --- |
| adapter_profile/version | Exact trusted handler selector, never a client import path. |
| adapter_code_identity/files | Physical identities of the selected immutable versioned handler, fragment/read helpers and exact release-specific schema. Mutable draft/facade/index files cannot participate in a published handler closure. |
| release | Exact Behavior/Core/verifier identities from the declared released wheel. |
| fixed_declarations | Exact reserved Actor declaration, wrapper read conventions and time profile. |
| composition_order | Original model/action/policy input order; public models determine semantic normalization/composition. |
| trusted_binding_contract | Actor/worker and now sources, proposed-context keys and their declared types. |

Every published version is packaged and retained; later model additions publish a new version.
New modules participating in the trusted authoring closure must be listed in the context.
An unknown profile or mismatched code/release refuses fresh reconstruction. Historical Core Wire
replay remains available independently of a missing authoring adapter.

## 3. Definition manifest

Keep the existing v1 definition shape accepted. A v2 definition explicitly stores:

- DefinitionId, source ProposalId/revision, parent DefinitionId and format version.
- BehaviorHash, SchemaHash, immutable Wire module reference and exact construction context.
- Operational model receipts: model kind, semantic/lowerer version, ModelHash, canonical document,
  receipt reference. These are public receipt outputs, not reconstructed from host names.
- With Safety policies, analysis reference: entire public analysis, individual policy ModelHashes/documents,
  aggregate `policy_set_hash`, analysis/checker version, complete inventory and issues.
  Without policies, policy_set_hash and safety_analysis_ref are explicitly null; no empty-set
  semantic hash or certificate is fabricated.
- Declared actions/reads inventory from admitted output, with provenance for host-authored wrappers.
- Exact release/adapter identities and host byte-addressed artifacts.

Uniqueness is DefinitionId, not BehaviorHash: policy-only edits can preserve behavior and schema
while changing safety identity. Two systems may share immutable blobs; no manifest contains another
system's deployment, principal approval or mutable state.

## 4. Trusted evaluation/read context

- **Actor/worker**: trusted launcher mapping for the current local principal; domain Actor records
  do not themselves establish caller authority. The initial subset uses the fixed Actor entity.
- **Time**: `utc-unix-milliseconds.v1`, a nonnegative safe JSON integer, bound to the admitted ordered
  time nominal. A trusted provider captures semantic now and ISO audit/commit timestamp explicitly.
- **Proposals**: only `lease_until` and `available_at` can be supplied as proposed context when
  the exact admitted capability declares them. Enqueue availability remains a normal input.
- **Authority**: trusted policy ID/version and the applicable operation/system/capability grants.

Retain exact Core context plus source/profile provenance for both allowed and refused operations
and time-dependent reads. Identical operation retries retain original context; a new operation
can acquire fresh time. No wall clock is read while tracing definitions or replaying records.
Elapsed wall time does not authorize changing an original bundle or silently rerunning an operation.

## 5. Safety evidence artifacts

| Artifact | Identity and status |
| --- | --- |
| Structural analysis | Exact public analysis dictionary, policy-set hash, checker version, inventory and issues. `Lowered` alone is not proof or complete supported coverage. |
| Unverified imported bundle | Retained exact client bytes/JSON and physical blob identity, explicitly unverified. No imported approval flag has authority. |
| Certification/checking assessment | Exact public assessment, outcome, behavior/policies, obligations, assumptions, external obligations, exclusions, dependency and proof-tool identities. |
| Certificate | Present only when produced by a successful public assessment; bound to exact evidence hash and subject. Scope/initial-validity fields are preserved verbatim. |
| Fresh evidence checking | Separate new assessment linked to unverified import; does not rewrite historical certificate provenance. |

States: requested → complete with public outcome, or infrastructure/resource failure.
Public assessment outcomes remain `Certified under assumptions`, `Inconclusive`, `Unsupported`,
`Failed`; structural lowering is not a fifth certification success. Exceptions are failures, not
invented public assessments. Unfinished worker output is never published as a certificate.

## 6. State-validity evidence

Persist the public `behavior.safety_state_validation.v1` record with exact incoming BehaviorHash,
complete policy-set hash, SchemaHash, StateRef, full HistoryRef, acquisition/export identity,
validator identity/version, original properties, findings, assumptions and `Valid`/`Invalid`/
`Unestablished` status. Public `matches_anchor` participates in checking; StateId alone is insufficient.

A separately requested report is observational. Activation obtains/checks validity under the writer
lock again. Complete exports are acquired from the public Store, never user-provided JSON snapshots.

## 7. Deployment and exact approval

Retain stable SystemId and independent Core Store. Expanded activation metadata includes:
DefinitionId, BehaviorHash, SchemaHash, complete safety policy-set identity, activation revision,
original/final exact history anchor, trusted delegation ID/version, principal, exact approval if
used, verification/certificate/state-validation artifact references and release/context identity.

The same-behavior/different-policy candidate is a new deployment, requiring explicit authorization
and a new atomic activation reference. Exact approvals bind the policy set as well as the existing
DefinitionId/hash/history fields. Required proof/state/host scope cannot be waived by a candidate
exception. Schema-changing activation remains unsupported.

Lifecycle: proposed → admitted inactive → assessed as requested → explicitly activated →
superseded (retained). There is no automatic activation step.

## 8. Operations and read records

Mutation operations retain existing operation ID binding, evaluation token, original Core bundle,
source HistoryRef, trusted context, current/original authorization, status, receipt/refusal and
reconciliation artifacts. Host statuses remain evaluated/refused/committing/unknown/committed/
not_committed. No per-family state machine is introduced by this feature.

Reads retain exact definition/deployment revision, current observed HistoryRef and StateRef,
inputs/context, public read record, response and replay subject. Use the existing operation journal
with kind `read` and exact request binding for durable retryable time-dependent reads. Its separate
read statuses are pending/completed/refused/failed; none is an uncertain domain mutation. Persist
the original subject, StateRef and context before execution. A pending retry can execute only the
same public read at that retained state/time. Readers need no domain publication permission; Core
read execution uses publication-disabled backend callbacks. Lost read response retries return
retained result/time under current read authority. Oversized complete results fail explicitly
rather than presenting truncated evidence as complete.

## 9. Persistence and validation rules

- Existing `host.sqlite` blobs/proposals/policies/approvals and per-system metadata/operation JSON
  suffice; add versioned artifact kinds and document variants, no second authoritative domain store.
- Actor bootstrap/provisioning is trusted, bounded and through public Core genesis/transitions.
  Multiple-actor fixtures must never seed authoritative state by direct SQL/file modification.
- No hidden safety registry, queue scheduler, mutable vote total or cross-system reference index.
- Required references are validated by public Core; the host checks only bounded syntax, resolvable
  authoring handles and trusted operational scope.
- Historical definitions, original safety policies and evidence remain recoverable. Derived catalog
  and inspection views can be rebuilt from those immutable artifacts.
