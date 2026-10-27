# MCP Contract

Design contract for implementation. No tool is claimed implemented by the planning artifacts.
Use the public low-level `mcp.server.Server` from SDK 2.3.0. Support SDK modern `2026-07-28`
and legacy `2025-11-25` clients; do not implement another protocol compatibility layer.

## Transport and Trust

Local stdio only. Reserve stdout for protocol JSON messages and stderr for redacted diagnostics.
The launcher binds trusted principal, WorkspaceId and policy source. All caller metadata, roots,
arguments and handles are untrusted. A server transport session never supplies the selected
system or the authority to access it.

Reject frames above 1 MiB before JSON decoding, nesting beyond 32, unknown tool arguments and
external schema references. These are initial host operational bounds. Build the bounded reader
through public stream interfaces; the SDK's unbounded line reader alone does not establish this
limit. Verification uses a bounded worker/deadline and reports timeout or uncertainty honestly.
Worker stdout is capped at 8 MiB and stderr at 1 MiB, including while sending the request.
Overflow terminates/reaps the process group, discards output and returns the distinct infrastructure
code VERIFICATION_STDOUT_LIMIT or VERIFICATION_STDERR_LIMIT; it never establishes verification.

The trusted launcher may tighten these limits through the closed `limits` configuration described
in `docs/operations.md`. Frame/depth, page defaults/maxima, verifier workers and the two existing
profiles' resource/deadline budgets are operational settings; MCP callers cannot modify them.
Overrides cannot exceed the published maxima, and actual verification profile parameters remain
part of the retained public report. These settings never alter model definitions or Core meaning.

Every system operation names SystemId explicitly. Workspace is trusted launcher context, not a
client-supplied path. Workspace artifact operations require explicit artifact permissions;
system operations additionally require the target's operation permission. Shared artifacts,
Core StoreId or BehaviorHash never substitute for SystemId or authority.

## Fixed Tools

All input objects reject additional properties. Identifiers are opaque strings, not paths.
Pagination defaults to 50 and is bounded to 100. Required keys are shown below; `?` means optional.
The machine-readable input contract is [tool-request.schema.json](tool-request.schema.json),
validating normalized `name`/`arguments` after SDK protocol handling. Protocol metadata is outside
that pair. Bundle local definitions when publishing individual tool input schemas; never fetch
remote references. `definition_propose` also validates its nested original authoring document.
Every non-protocol result uses [result.schema.json](result.schema.json) and the stage-specific
fields described below. Implementation must publish input/output JSON schemas, not just prose.

| Tool | Input keys | Result and authority |
| --- | --- | --- |
| `models_list` | none | Authoritative family provenance plus explicitly host-owned bounded adapter schemas and unsupported features. No invented complete upstream registry. |
| `definition_propose` | `proposal`, `base_proposal_id?`, `expected_proposal_revision?`, `parent_definition_id?` | Workspace artifact-author permission; save syntactically valid [authoring input](authoring.schema.json) and construction context. Return ProposalId/revision; no lowering or activation claim. |
| `definition_get` | exactly one of `proposal_id`, `definition_id`; `proposal_revision?` only with proposal_id | Authorized artifact inspection; original input/context, separate canonical documents, generated module, receipts and exact versions. No disclosure of other systems using a shared artifact. |
| `definition_validate` | `proposal_id`, `proposal_revision` | Call public model constructors/module admission; return distinct structural/model/lowering/admission stages and immutable DefinitionId/manifest if admitted. |
| `definition_verify` | `definition_id`, `profile_id` | Run a host-allowed public verification profile; return exact attestation/check coverage and assumptions, not deployment approval. |
| `systems_create` | `definition_id`, `operation_id`, `label?` | Trusted creation grant; allocate stable SystemId and independent Store using explicit host bootstrap seed and Core creation. Return inactive system and anchor; never activate implicitly. |
| `systems_list` | `cursor?`, `limit?` | Only authorized system descriptors. No state/history leak through listing. |
| `system_inspect` | `system_id` | Authorized system metadata, lifecycle, active revision/definition or inactive status, Core identities and permitted-operation summary. |
| `definition_activate` | `system_id`, `definition_id`, `expected_activation_revision`, `expected_history`, `operation_id` | Explicit activation subject to current delegation or separately obtained exact approval; incoming current-state validation and atomic pointer/audit publication. |
| `capabilities_list` | `system_id` | Capabilities of that system's active module, including actual names, parameter roles/types and identity/provenance. Refuse inactive systems. |
| `state_read` | `system_id`, `entity?`, `record_id?`, `history?`, `cursor?`, `limit?` | Core-controlled reads or validated snapshot projection at a checked anchor. Entity is required with record_id; filters do not become a business-rule language. |
| `transition_evaluate` | `system_id`, `capability_id`, `bindings`, `input`, `expected_activation_revision`, `operation_id` | Core decision and original bundle stored behind an opaque evaluation token. No domain commitment. Context/actor/time are captured from trusted host configuration and recorded explicitly. |
| `transition_commit` | `system_id`, `evaluation_token`, `operation_id` | Same logical OperationId as evaluation; recheck scope/deployment/policy, then Core commitment of the original bundle. Return committed, already committed, conflict, refusal or uncertainty distinctly. |
| `operation_get` | `system_id`, `operation_id` | Authorized durable operation inspection; never infer failure from a missing transport reply. A read does not create a replacement mutation. |
| `system_recover` | `system_id`, `operation_id?` | Authorized kind-specific recovery: Core original bundle for transitions, atomic host receipt for activation, reserved SystemId/Core creation for creation. No reset or best-effort migration. |
| `gaps_list` | none | Public supported/unsupported capability findings and evidence references; redact private runtime details. |

Tool descriptors are fixed and generic. Model-generated actions are discovered as data for a
system, rather than dynamically installing executable MCP tools or plugins. Schema-changing
activation, arbitrary guards/expressions, model command emission and cross-system operations are
explicitly unsupported initially. No generic database, filesystem or shell tool is exposed.

## Proposal Revisions and Lineage

A request without base_proposal_id creates ProposalId/revision 1; optional parent_definition_id
records an authorized immutable definition being forked. A request with base_proposal_id must also
supply expected_proposal_revision. Append revision N+1 under that same ProposalId only if N is the
current head, preserving all previous snapshots. Stale revisions conflict without an append.

Edits inherit the prior parent; a supplied parent must match it. A different parent requires a
new fork. Parent lookup requires artifact read authority. It is metadata, not a semantic input,
proof or authority grant. No fields are reconstructed by guessing from a parent hash.

definition_get(proposal_id) is an explicit latest-at-read lookup and returns its resolved revision;
proposal_revision selects an immutable version. definition_validate always names both fields and
returns the exact source reference. Concurrent head edits do not change that validation subject.

definition_get(definition_id) returns kind=definition_inspection with the immutable definition
manifest, exact source snapshot, and separately identified artifacts. Each artifact contains its
artifact_ref, kind and original document: generated Wire module, construction context or full
lowering receipt. The evidence array contains retained definition-specific authoring validation
and verification reports, including original subject, release, profile and report identity.
Physical artifact references are checked before returning contents. Inspection neither reruns
verification nor relabels old evidence. It exposes no arbitrary artifact lookup and excludes
system-specific deployment/authorization evidence associated with shared definitions.

## Authoring Translation Boundary

The [example proposal](example-proposal.json) is original authoring data, not canonical Behavior
IR. The host-owned schema is justified by GAP-001 and labeled as such in discovery.

| Proposal element | Public construction |
| --- | --- |
| Enum declarations | Python Enum values supplied to public Behavior constructors. |
| String/enum entity fields | Public `field` and `entity` construction; no private declaration mutation. |
| RequestFlow model/creation/transition | Public `RequestFlow`, `.create`, `.transition`. Fixed Actor declaration/context is retained in the manifest. |
| StateMachine model/transition | Public `StateMachine` with explicit subject/state field/subject parameter/entry states. |
| Literal/input/host-actor initializer | A trusted fixed callback returning supported typed values; no client callable or source text. |
| Input-to-field assignment | Trusted fixed callback using public `set_`; no local expression evaluator. |
| Composition | Public `BehaviorModule` with the full retained declaration/model context. |

All other semantic checks, ownership, identities, normalization and lowering remain upstream.
Structural input bounds and adapter-subset refusals are host restrictions. They are not Behavior
semantic results. Do not use model document/receipt dictionaries as trusted lowering input.

Generated invocation names/roles/types come from authoritative exported module declarations.
Project only supported JSON shapes into client schemas and still call Core for validity. An
unsupported type/configuration returns an explicit limit rather than a copied Behavior type checker.
The known fixture's generated actions are `record__new` and `record__finish`, with creation input
`request_id`; these are observations, not host naming rules.

## Result Boundaries

The common envelope contains `format`, `request_status`, `stage`, `outcome`, `subject`, `result`,
`evidence` and `error`. Completed system stages require SystemId; errors before target resolution
retain the requested identifier when available without claiming that it exists or is authorized.
Artifact inspection uses the authoring stage, system listing uses discovery, and read means a
system-state read. Subjects retain exact dependency and artifact identities where known.
`result` has a stage-specific discriminated schema in result.schema.json; implementation publishes
that same schema. Completed results require error=null; refused/failed/unknown results require
matching error/outcome categories. [Synthetic schema examples](example-results.json) demonstrate
shape only and are not actual verification or activation evidence:

- Discovery reports upstream availability separately from the adapter's supported authoring subset.
- Validation reports structural/model/lowering/admission status and generated manifest identities.
- Verification includes the exact upstream result, subject, profile, checks, obligations,
  assumptions and evidence identity. A completed query may return an inconclusive proof outcome.
- Activation returns its immutable receipt including OperationId, request binding, SystemId,
  BehaviorHash, policy/version, trusted authorization, validation/evidence references and Core
  history anchor. observed_current_deployment is separate from the original operation's outcome.
- Evaluation returns the actual Core decision/reasons, source anchor and token only if an
  allowed bundle exists. `ALLOW` is not commitment. Token possession grants no permission.
- Commit/recovery returns OperationId, actual Core record/result state identities and `already`
  where established. Distinguish a fresh commitment from recovery of the same commitment.

JSON-RPC errors cover malformed protocol envelopes, unknown methods/tools and transport failures.
Known-tool failures return `CallToolResult(is_error=True, structured_content=...)`, with a concise
matching text representation. Categories distinguish `invalid_input`, `model_invalid`,
`semantic_refusal`, `unauthorized`, `conflict`, `unsupported` and `infrastructure`.

Every verified report requires exact definition/behavior/schema/release subject, profile and
semantic profile, checks, obligations, assumptions, report identity, raw public report and evidence
reference. verified additionally requires actual upstream_result=verified and nonempty coverage.
No emitted public report means an unsupported/infrastructure failure, not a fabricated attestation.
Server-side checks enforce subject/report/receipt consistency; JSON Schema is not proof validation.

A verification request returning inconclusive/unsupported evidence does not become successful
proof merely because request processing completed. Missing solver and deadline failure retain
their infrastructure/timeout identity. Never encode all exceptions as a semantic refusal.
In particular, public `CommitRefused` carrying `BACKEND_ERROR` requires uncertainty handling.

## Concurrency, Operation Identity and Recovery

`expected_history` is a public Core HistoryRef, augmented by trusted host SystemId scope. Core
checks its meaning. `expected_activation_revision` is host compare-and-set context. A stale
revision, changed policy or head conflict produces an explicit result; no hidden re-evaluation
may silently change the operation the agent intended to commit.

OperationId is distinct from JSON-RPC request ID. A retry reuses the same OperationId, exact scope
and request. Changing them under the same ID fails. A genuinely new evaluation gets a new ID
only after the old operation's outcome is established.

Evaluation stores original refusals as well as allowed evaluations. Identical refused retries
return the original structured outcome and subject without asking Core to evaluate again, even
after state/deployment changes. Current evaluation/workspace/system authority remains required.

Before commit, persist the original public bundle. The backend publishes Core documents and its
host receipt in the same system transaction. On an uncertain reply, inspect the receipt and
recover through Core with the original bundle; never evaluate a replacement first. A retry that
could newly commit must satisfy current authorization/deployment conditions. If outcome remains
unknown, block further mutations of that system and report `outcome_unknown`; other systems
remain independently usable. Cancellation is not evidence of rollback.

Transition recovery separates outcome reconciliation from execution. Current system_recover and
operation_get grants permit historical outcome inspection. An unchanged exact Core HistoryRef
and no receipt establish nonpublication. If history moved, Core must distinguish a different
operation that committed the same transition from an unpublished candidate: use the retained
module and original bundle with domain publication disabled in both backend mutation callbacks.
Only Core's already acknowledgment or StateConflict settles this case; callback refusal and
other errors remain inconclusive, never fabricated semantic conflicts. Persist host reconciliation
evidence before considering another attempt; never interpret opaque bundle fields or infer
nonpublication from unavailable storage. A same-call retry of that original bundle separately checks current commit/capability
authority, actor, active deployment and source history. Revoked execution authority or a changed
deployment leaves the known not_committed outcome resolved. Subsequent recovery calls do not
retry terminal noncommitted operations merely because authority later returns. Original committed
receipts and their historical authorization do not depend on current execution permission.

## Activation Retries

For definition_activate, persist OperationId + exact parsed request + trusted principal/workspace/
SystemId binding with the activation record, active pointer and immutable published result in one
system transaction. The operation is host deployment publication and has no Core commit bundle.

An identical retry resolves that receipt before applying expected_activation_revision/history CAS
again. Current operation_get permission governs disclosure. Return outcome=already_activated,
the original receipt/authorization and a separate observed_current_deployment even if the active
pointer has since advanced. Never relabel the original policy or claim its result is current.

Reuse of the ID with another request/scope conflicts. If no receipt establishes commitment, do
not infer success from a matching active BehaviorHash: establish non-publication and run all
current checks before any new publication, or report uncertainty and block that system's writes.
A lost read permission denies disclosure and cannot trigger a fresh activation. operation_get and
system_recover distinguish activation receipts from transition bundles and creation reservations.

Test crashes immediately before and after the atomic transaction, retry with the old expected
revision, another later activation, changed policy, wrong system and changed-request ID reuse.
The original activation occurs once; one retry cannot append another activation/audit event.

## Contract Acceptance

Validate object schemas and structured output for every tool. Exercise authorized/unauthorized
targets with identical immutable artifacts and identical genesis hashes. Test stale tokens,
wrong-system token replay, changed policy, lost acknowledgments and inactive systems.
Use deterministic SDK clients in modern and legacy modes, including real subprocess stdio;
in-memory transport tests do not substitute for physical persistence or recovery tests.

Enum cases use an ordered array of `{name, value}` entries, matching the explicit declaration
order passed to the public Enum constructor. JSON object member order is never an implicit
semantic input. Preserve array order in proposals, construction context and subsequent revisions.
