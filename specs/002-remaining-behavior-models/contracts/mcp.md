# MCP Changes for Expanded Models

These contracts extend the existing generic tools; no per-family transition or database tool is
introduced. Keep the existing result envelope and all previous request/result variants accepted.
Ship new closed schemas under unique names; never rewrite a published authoring grammar.
The [version contract](adapter-versions.md) requires exact adapter_version on v2 input and
retained immutable implementations. The [expanded result grammar](expanded-result.schema.json)
is selected by trusted tool/profile context; legacy outputs retain their unmodified v1 schema.
Never accept an invalid expanded output by falling back to a looser legacy validator.

## Existing tools

| Tool | Expanded behavior |
| --- | --- |
| models_list | Six entries, category operational/safety, exact provenance, honest delivered bounds. |
| definition_propose / validate / get | Dispatch by explicit input format and retained profile; separate operational receipts and Safety analysis/artifacts. |
| definition_verify | Existing SMT verification remains distinct from Safety certification; subject uses exact definition release/context. |
| capabilities_list | Return admitted actions and declared reads with parameter roles/types and provenance. Policies and derived definitions are not automatically executable actions. |
| transition_evaluate | Optional `context_proposals` with only lease_until/available_at. Host injects trusted actor/worker/now where declared. |
| transition_commit / operation_get / system_recover | Existing exact-token/bundle, refused retry and reconciliation semantics, with retained expanded context. |
| definition_activate | Explicit atomic activation binds complete Safety policy identity, proof/state evidence where required, exact incoming definition and history. |
| state_read / system_inspect / operation_get / system_recover | Keep existing snapshot/history inspection and recovery behavior. Internal public Core replay additionally checks retained read records; no standalone history_list or replay MCP tool is implied. |

For `transition_evaluate`, existing fields remain unchanged. Missing proposals mean `{}`. Any
trusted key in `input`, `bindings` or proposed context is refused where it attempts to override a
trusted declared parameter; role validation uses admitted public signatures. Enqueue availability
belongs in input; retry/recovery availability and lease_until belong in proposed context where
actually declared. Unknown/unused keys fail closed. V1 requests and policies acquire no new grants.

Each slice delivers its own catalog entry, request routing and result variants before its
independent acceptance checkpoint. Future versions/families remain explicitly unavailable.
US6 audits already delivered interfaces and cross-family consistency.

## Added tools and exact arguments

All inputs are closed objects. Artifact IDs are workspace-scoped opaque identities, not filesystem
paths. New tool schemas are in [tool-additions.schema.json](tool-additions.schema.json).

| Tool | Required arguments | Optional arguments | Authority |
| --- | --- | --- | --- |
| capability_read | system_id, capability_id, bindings, input, expected_activation_revision, operation_id | None initially | Current operation, system and exact declared read allowlist. |
| definition_safety_certify | definition_id, profile_id | None | Explicit artifact certification grant and enabled trusted proof profile. |
| definition_safety_verify_evidence | definition_id, profile_id, bundle | None | Explicit artifact checking grant; bundle is unverified public-schema data. |
| state_validate_safety | system_id, definition_id, expected_history | None | Current target-system validation/read grants and definition read grant. |

`bundle` is JSON data within the transport limit, never a path, executable command, toolchain
selection or trusted certificate flag. The public loader/checker admits or rejects it. Larger
imports are explicitly unsupported initially rather than introducing a generic filesystem or blob
upload platform. Store the unverified import before linking any successful fresh checking result.

## Read results and repeatability

`capability_read` captures current activation, full HistoryRef, StateRef and trusted context under
the existing coordination boundary. Use public `Store.read_intent` for the exact admitted read;
retain its public record and response. Execution cannot publish domain state. Return:

- `kind=read`, exact capability/definition/activation/history/state identities;
- trusted binding provenance, input bindings and immutable Core read-record reference;
- the exact public response (record_id, result, value and/or public reasons as applicable),
  without renaming its fields, and read evidence identity.

Bind OperationId to the exact principal/system/request, using a distinct read operation kind.
Persist a pending read's original context, subject and StateRef before execution. A crash/retry may
re-execute only that retained public read at the retained state/time, or return its stored result.
Read journal statuses pending/completed/refused/failed never imply a possible domain commit and do
not block unrelated mutations through the uncertain-mutation gate. Identical retries require
current read permission; another request using the ID conflicts. New reads acquire new time.

Use the admitted parameter layout, not guessed generated names. Queue ready/expired results can
be empty or complete ID-only lists. Public reads have no pagination argument. If the complete
response exceeds the host limit, return a structured resource failure and retain no false complete
result. Do not slice/rename the value while reusing the original record as evidence for that slice.
Existing paged snapshots remain a separate interface.

## Safety results

Certification/checking returns `kind=safety_assessment` with exact DefinitionId, BehaviorHash,
SchemaHash, complete `policy_set_hash`, analysis/checker/toolchain identities, exact public
assessment outcome, assumptions, obligation/exclusion summaries and immutable full evidence ref.
Return a certificate ref only if the public assessment actually includes a certificate. Public
outcomes are preserved, especially `Certified under assumptions`, `Inconclusive`, `Unsupported`,
`Failed`. An infrastructure exception is a failed request, not a synthesized assessment.

State validation returns `kind=safety_state_validation`, the exact incoming subject/policies and
full public record. It is observational and does not authorize activation. Detached client state
cannot supply provenance. Activation independently repeats required validity checks under lock.

`definition_get` exposes structured safety policy/analysis summaries and bounded assessment
metadata separately from model receipts and ordinary SMT reports. Its added closed request variant
is `{definition_id, evidence_ref, offset, limit}`: offset is a nonnegative byte offset and limit is
1–65,536 bytes. The evidence reference must belong to that exact definition's artifact-only Safety
analysis/proof bundle. Return `kind=evidence_chunk`, exact artifact/definition identity, byte offset,
total byte length, encoding `base64` and the bytes. These are transport chunks, not independent
proofs; only a complete reconstructed bundle can be freshly checked. Current definition-read
authority is required. System-specific state-validation/deployment records cannot be disclosed
through shared-definition artifact access. File paths and worker staging directories are never
public artifacts or caller authority. An oversized atomic public proof bundle remains a size-
limited import, not silently truncated data.

Schema validation is structural. Runtime validation must also bind repeated subject, definition,
behavior, schema, policy-set, history, release and public report/certificate identities to the
trusted result source. Raw authoritative payloads remain governed by Behavior; a shaped dictionary
is never evidence of a valid proof or read. With no Safety policies, identity fields are explicitly
null. Certificate refs occur only with actual public conditional certification.

## Failure and resource rules

Keep transport, schema, model-invalid, semantic-refusal, authorization, conflict, unsupported and
infrastructure/resource outcomes distinct. Missing tools, timeout, invalid toolchain, malformed
proof, subject/policy mismatch or incomplete coverage never imply certification. Host-policy
restrictions are labeled operational, never Core semantic refusals.

Time/identity overrides and out-of-delegation proposals are refused before Core invocation.
Core DENY/INVALID_INPUT refusals are retained idempotently with original trusted time evidence.
No output containing an evaluation token or successful artifact ID is published partially.
Workers are killed as a process group and reaped on timeout or either stream overflow. Reuse
existing bounded stdout/stderr collection; no `communicate()` buffering without caps.

## Deployment and delayed commits

An evaluation is against its recorded trusted time and source snapshot. Commit and reconciliation
use the exact original Core bundle; they never substitute a new time or silently reevaluate it.
This feature does not claim validation against later wall-clock time at commit. Current host
operation/capability/principal/activation checks still govern potentially fresh publication.
Outcome reconciliation remains independent and read-authorized as in the existing contract.

Workspace catalog results report package/Core identity without inventing one active adapter
version for the whole workspace. Each family entry lists the exact delivered versions, their
schema resources and readiness. Definition-bound results require their retained adapter profile/
version and compare all repeated release identities. Safety assessment projections include the
public scope, initial-validity limitation, exclusions, external obligations and dependency identity,
as well as the full report reference; they do not summarize conditional certification as an
unqualified guarantee. Raw authoritative payloads are opaque only where explicitly identified by
the schema, not a general extension escape for host-owned objects.

`operation_get` can report read journal status under current read authority. Targeting a read ID
with `system_recover` is observational (`operation_status`); it does not rerun the read or mark it
as an uncertain transition. Whole-system recovery skips pending reads as mutation blockers.
To retry a pending read, repeat its exact `capability_read` request at the retained state/time.
