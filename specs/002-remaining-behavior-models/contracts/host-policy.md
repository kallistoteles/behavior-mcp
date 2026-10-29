# Expanded Trusted Host Policy Contract

**Policy format**: `behavior-mcp.host-policy.v2`.
**Exact approval format**: `behavior-mcp.activation-approval.v2`.
These remain independently administered host objects. Neither format is a Behavior Model or a
new Core persistence/authorization policy. The existing v1 grammar and enforcement remain valid.
Unknown keys/values, missing grants and empty allowlists deny; no implicit v1-to-v2 permission.

## Closed fields and evaluation

Retain identity, issuer, immutable positive version, exact principal/workspace, system selector,
operation grants, creation capacity, evidence requirements and existing no-external-command /
no-host-authority-expansion / no-schema-migration restrictions.

Replace the single construction profile with `allowed_adapters`: exact profile/version/release
objects, so a v2 policy can explicitly allow retained v1 and expanded v2 systems. For each allowed
profile bind the following closed candidate bounds:

| Bound | Required coverage |
| --- | --- |
| model kinds / IDs | Exact allowed operational kinds/IDs; no unknown-family default. |
| safety kinds / IDs | Exact FieldOwnership/LifecycleDependency IDs/kinds and protected entity/field/action-selector scope. |
| action/read inventory | Every admitted action and declared read, including wrapper reads and all generated queue registrations. |
| conditions | Every used bounded expression op, entity/field/derived-reference scope and query footprint. |
| effects | Every lifecycle factory/model operation, target entity/field, initializer/transfer source form and creation/removal permission. |
| model parameters | Exact permitted Approval thresholds, WorkQueue attempt bounds, supported time nominal/profile and payload descriptors. |
| status changes | Explicit declared statuses and transition destinations/edges; public output supplies model-generated inventory. |
| safety changes | Permitted complete policy sets or exact policy/selector bounds; removing or weakening policies is an explicit bound, not implied by unchanged BehaviorHash. |
| proposed context | Per-capability lease_until/available_at permission, integer range and maximum future offsets relative to trusted now. |
| proof requirements | Exact allowed proof profile, analysis/checker/toolchain/dependency identity, required obligations and allowed assumptions for the complete incoming safety policy set. |

This is finite operational matching over a trusted bounded authoring descriptor plus authoritative
admitted output. It is not a semantic effect extractor for arbitrary behavior. Unsupported coverage
fails closed. Add a v2 candidate checker; do not make the legacy checker guess new semantics or
walk every model as if it had transitions.

Runtime permissions separately allow exact action and read IDs. Extra context proposals do not
establish identity; `now`, actor and worker always come from trusted context. Allowlisting a model
or its generated actions for construction does not grant permission to invoke them. Safety policies
cannot add their own operation grants or evidence requirements.

## Evidence and activation

Old ordinary SMT requirements remain separate from Safety certification. An explicit
`required_safety=[]` requires no certificate but makes no certification claim. A nonempty requirement
must match a freshly established trusted certificate for exact DefinitionId/BehaviorHash, complete
policy-set hash, inventory, obligations, assumptions and pinned proof dependencies. Imported flags,
matching behavior alone and `Lowered` alone are insufficient. Retain public issues even when no
certificate is required. A required unsupported/inconclusive/failed check blocks activation.

Lifecycle policy deployment always requires the applicable current-state validation from the
public Store for the exact incoming policies/definition under the system writer lock, independent
of whether a certificate is requested. Failed or unestablished required validity blocks activation.
Genesis is independently established by Core and applicable safety-state validation before the
system is activated; a transition certificate is not genesis evidence.

Preserve the documented policy-before-system lock order across all writers and trusted policy
administration. Long-running certification occurs outside the writer lock; activation rechecks
current subject, complete inventory/policies, evidence requirements, current policy and exact
history under the shared coordination boundary, then atomically publishes pointer/receipt.
No check authorizes a write after an uncontrolled intervening writer.

## Exact-version approval

Bind every existing approval field and additionally the complete safety `policy_set_hash` and
required evidence identity set. A policy-only edit with unchanged BehaviorHash is a different
candidate. Required state/proof checks, trusted identity/scope and unsupported public capability
boundaries cannot be waived. Candidate exceptions name explicit permitted bounds; they cannot
change delegation policy or invent runtime/read grants.

## Trusted time and resource configuration

The trusted launcher provides semantic time separately from audit timestamps and maps the local
principal to Actor. The time-binding profile is declared/recorded; a controlled provider is allowed
for deterministic tests, not as an MCP argument. Fail closed on absent/wrong-type trusted bindings.
Multiple Actor records used in fixtures/provisioning are created only through Core genesis or
transitions under trusted operator authority; their mere existence grants no host permissions.

Keep existing frame/depth/page/verification ceilings. New closed trusted ceilings, tighten-only:
4,096 expression nodes; 1 concurrent safety proof worker; 120 seconds wall deadline; 8 MiB stdout
and 1 MiB stderr per worker; 8 MiB retained serialized proof bundle. Read workers use 5 seconds and
1 MiB serialized complete response/record output. Per-process CPU/address-space/file limits and
bounded staging cleanup complement byte/time limits. No claim of an unlimited-result memory bound
is made. Large public reads fail structurally at the resource boundary, not as semantic denials.
Stderr is counted/discarded, process groups are killed/reaped, and execution slots released on
success, error, cancellation or limit exhaustion. Caller-supplied paths/profiles/toolchain options
are never forwarded as process authority.

## Exact v2 grammar and matching algorithm

The normative grammar is [host-policy-v2.schema.json](host-policy-v2.schema.json); exact approvals
use [activation-approval-v2.schema.json](activation-approval-v2.schema.json). Valid examples are
[Approval delegation](examples/host-policy-v2.json),
[lifecycle delegation](examples/host-policy-v2-safety.json) and
[exact approval](examples/activation-approval-v2.json). They are shape/configuration examples,
not authenticated approvals and never installed automatically. Synthetic hash placeholders confer
no authority. Validation has these deterministic rules in addition to JSON Schema:

1. Match trusted issuer/principal/workspace and operation/system scope as in v1. `allowed_adapters`
   must have unique `(adapter_profile, adapter_version)` keys. Select exactly one matching retained
   version/release; duplicate, missing or unavailable entries deny. A legacy entry contains its
   exact original construction/effects/state grammar; it uses the unchanged v1 matching rules.
   No grants are unioned across profiles or different matching entries.
2. For a v2 entry, every model kind/ID and authoritative admitted action/read must be in its exact
   `allowed_*` inventory. Every authored entity/enum/nominal declaration must equal one permitted
   declaration. Object key order is irrelevant; arrays, values, case order and types are exact.
   This compares retained authoring data, not semantic equivalence or canonical Behavior hashes.
3. Every expression node must use an allowed op and field/query/derived reference. Field scopes
   compare typed entity references and exact field membership. No wildcard, regex, executable
   predicate, implied permission or semantic implication matcher exists. Duplicate keyed bounds
   (model ID, policy ID, capability/parameter or entity/field) make the policy invalid.
4. Every authored lifecycle action must exactly match one `allowed_action_descriptors` item.
   For `required_guard_roots`, each listed root must occur as a complete `requires` root for that
   exact authored/generated capability. Matching is structural input equality; no normalization,
   guard synthesis or inference from a condition nested inside OR is performed. Missing required
   roots deny even if another condition might be logically equivalent. Extra guards must still
   satisfy the permitted expression/reference scopes.
5. Each Approval or WorkQueue requires exactly one `model_parameter_bounds` row for its model ID.
   Approval thresholds from the public normalized receipt are exact members of the permitted
   integer lists; omitted/null authoring defaults are never guessed by the host. If the supported
   public output cannot establish a required normalized value, coverage fails closed. Payload descriptors must match
   exactly. Queue attempts satisfy inclusive minimum/maximum (minimum must not exceed maximum),
   with exact time nominal and payload. Other models use the declared state/transition bounds.
   Generated effects are covered only by the recognized pinned model/version, permitted model
   parameters and complete admitted capability inventory; no arbitrary generated behavior or
   commands are accepted under this shortcut. Host code does not recreate their semantic rules.
6. `allow_new_records`, `allow_existing_record_changes`, `allow_remove_records` gate applicable
   model and authored effects independently. Authored/model-authored status fields and edges must
   be members of the exact qualified `state_fields` rows. For WorkQueue, its generated lifecycle
   comes from the pinned model contract; scope its model parameters and complete capabilities,
   then separately restrict actual invocation through `runtime_actions`. Do not omit registration
   of one of the nine capabilities or implement a second transition table in the host.
7. All `required_policy_ids` must occur. Each proposed FieldOwnership policy must match one
   `field_ownership_bounds` row by ID/entity. Every `required_protected_fields` member must remain
   explicitly protected. Proposed field keys must be covered; writers/creators/removers must each
   be subsets of their permitted exact selectors. An empty proposed list grants nothing; omitting
   a required field/policy denies. This permits finite tightening without inventing a semantic
   weakening detector. Each LifecycleDependency must exactly match one
   `allowed_lifecycle_dependencies` descriptor; changing its sets/relationships requires a separately
   permitted descriptor or exact trusted approval. Unknown Safety policies deny.
8. `runtime_actions` and `runtime_reads` are distinct exact-ID allowlists and never imply each
   other. Every caller-proposed time value requires one matching `proposed_time_bounds` entry for
   capability/parameter, whether its admitted role is input (enqueue availability) or proposed
   context. Bounds are inclusive, minimum ≤ maximum, and `value - trusted_now` must not exceed
   `max_future_offset_ms`. This is an operational grant; Core still decides temporal validity.
   A trusted actor/worker/now override is always refused, not exceptable.
9. Every `required_safety` entry must be satisfied by a fresh trusted public certificate for the
   entire incoming policy set, not just its named required policy IDs. Require exact dependency,
   analysis/checker/profile, every named public obligation equal to `Passed` and each actual
   assumption an exact member of `permitted_assumptions`. Unknown/deviating proof dependencies,
   failed/incomplete/unsupported results or unmet external obligations deny. Preserve the whole
   public assessment and its scope/exclusions; these checks do not strengthen its guarantees.
10. Exact approval is considered only after independent trusted issuance is established. It must
    match every identity/history/version field, `policy_set_hash` and the sorted set of required
    evidence references. Named exceptions can waive only candidate bounds, never runtime grants,
    trusted identity/time, required proof/state checks, public API availability or forbidden effects.
    Without Safety policies, `policy_set_hash` MUST be null and no safety analysis/certificate is
    fabricated. With policies it MUST be the authoritative aggregate hash. Empty required-evidence
    arrays are explicit absence of requirements, not evidence that a proof was checked.

The runtime output validator checks all repeated definition/behavior/schema/policy/release/anchor
identities for equality with the trusted subject, independently of syntactic schema validation.
Required proof/state validation and atomic publication still follow the coordination rules above.

`required_model_conditions` adds exact model-slot requirements beyond per-capability roots. Each
row names model ID, `open_when`/`eligible`/`authorization`, nullable capability ID (required for
queue authorization, null for Approval-wide slots) and the exact expression. Rows must be unique
by model/slot/capability. Missing or structurally changed required conditions deny. This allows an
operator to require an eligibility condition without asking the host to prove logical implication.

For v2 exact approval, the exception-to-field mapping is closed:

| Exception | Candidate fields it may waive |
| --- | --- |
| model_kind | allowed_model_kinds |
| model_id | allowed_model_ids |
| capability_set | Construction allowed_action_names/allowed_read_names; never runtime allowlists. |
| typed_effect | Exact allowed_action_descriptors; never public typing/admission. |
| state_change | Creation/update/removal and author-specified status/edge bounds. |
| condition_scope | Fragment op/reference and required root/model-condition matching. |
| safety_scope | Candidate policy/selector/dependency bounds; never required proof/state validity. |
| model_parameters | Candidate thresholds, attempts and payload descriptors. |

Profile, implementation version, release identity, declaration availability, trusted principal/time,
operation/system/runtime grants, required evidence/validity and prohibited external effects remain
non-waivable. Install a new trusted delegation when those supported grants must change. Legacy v1
approval semantics are retained only on the explicit legacy path; they do not define v2 exceptions.

The general version syntax is exact `2.<minor>.<patch>` with no leading zeros, prerelease, build
metadata or aliases, at most 32 characters. Syntax acceptance does not establish availability:
policy installation and proposal admission MUST resolve the exact installed published code/schema
entry or refuse. Additional integration fixes publish a new exact version and validator; existing
versioned validators remain unchanged. No runtime import path is derived from the version string.

A public certificate can legitimately retain `initial_validity=Unestablished` and external
obligations marked Host obligation or Excluded. Do not demand that every external entry say
Passed, rewrite those fields, or claim that certification proved them. Resolve initial validity
through the applicable fresh Core/incoming-policy state checks; resolve approved-module continuity
through exact authorized activation and coordinated writers. Migration safety remains excluded,
and schema-changing activation remains refused. An unresolved applicable host obligation blocks
activation; an explicitly excluded property is not reported as proved.

Pure proof compilation holds neither the system writer lock nor the coarse workspace policy lock.
Capture immutable subject and original authorization first, release those locks for bounded work,
then reacquire current policy authorization before disclosing the result. Activation always obtains
its own current checks and writer boundary. Never let a retained old authorization or a completed
proof job stand in for current activation authority.
