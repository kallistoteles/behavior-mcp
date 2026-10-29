# Expanded Authoring Contract

**Status**: Design; implementation and conformance tests are subsequent work.
**Format**: `behavior-mcp.authoring.v2`, profile `structured-models.v2`, with required exact
`adapter_version`. Versions 2.0.0–2.3.0 are delivered at separate checkpoints; see
[immutable version contracts](adapter-versions.md).
The aggregate machine grammar is [authoring-v2.schema.json](authoring-v2.schema.json); each
selected version uses its separately frozen validator. It is host-owned input,
not an upstream canonical document. GAP-001/002 justify retaining it alongside authoritative output.
Frozen feature-001 authoring syntax and adapter behavior remain unchanged.

## Bounds and declarations

A proposal has `declarations`, `models`, `actions`, `safety`, optional display `metadata`. All
unknown properties are rejected. Identifier length is at most 64; request frame at most 1 MiB;
JSON depth at most 32; at most 8 models, 8 policies, 16 entities, 16 lifecycle actions, 32 fields
per entity and 4,096 total expression nodes. Trusted configuration may tighten these maxima.
These are operational restrictions, not claims about Behavior's general limits.

Typed descriptors use `kind`: string/int/bool, enum or nominal by name, Id or Ref by entity
reference. An entity reference is either a declared entity name or
`{model_id, output: request|decision|work}` resolved through public contributed handles.
The reserved Actor declaration is fixed by the adapter. Initial Approval actors and queue workers
use Actor; the caller cannot redefine it or substitute a trusted identity source. Enum case arrays
preserve explicit order. The supported time nominal has integer base and `operations=["order"]`.
The host's `utc-unix-milliseconds.v1` binding supplies its values; arbitrary time arithmetic and
implicit units are not part of this profile.

The host resolves bounded input references so it can call constructors. The final public module
build owns semantic declaration dependencies, ownership, collisions, normalization and composition.
Unresolvable or cyclic authoring handles are explicitly unsupported; never guessed or hand-lowered.

## Expressions and lifecycle effects

Nodes are data descriptions traced into public Behavior expressions:

| op | Fields | Public construction |
| --- | --- | --- |
| literal | value: Boolean/string/integer | Public lifting in the receiving typed expression. |
| enum | enum, case | Exact case of the public Enum declaration. |
| param | name | Already typed parameter/query binding in the current public tracing scope. |
| field | value, name | Public entity field or id projection. |
| eq | left, right | Public symbolic equality. |
| and / or | args | `and_` / `or_`; no host Boolean interpretation. |
| not | value | `not_`. |
| in | value, members | Public membership; nonempty explicit members. |
| any | entity, bind, where | `any_(select(entity), predicate)` over a public query binding. |
| derived | model_id, function, subject | Public Approval or WorkQueue derived handle, not a guessed generated name. |

Every guard is an explicit complete root in a `requires` array. No simplification, guard synthesis,
truth evaluation, canonical reordering or proof-pattern recognition is performed by the host.
A syntactically expressible noncanonical guard can remain Unsupported in Behavior analysis.
Invalid types and semantic constraints are diagnosed by the authoritative build.

Three fixed public action factories support the required independent lifecycle:

- `create_entity`: named entity, optional State `parent`, input `new_id: Id[entity]`, explicit
  `values` and `requires`. The first subset supports literals and the bound parent's id as values.
- `set_field`: State `subject`, optional State `parent`, one field and explicit literal enum
  destination, plus `requires`. There are no computed destinations or hidden policy effects.
- `remove_entity`: State `subject` and explicit `requires`.

These are fixed trusted Python closures passed to public `action`, `create`, `set_`, `remove` and
`requires`; client source text is never compiled or evaluated. Payload authoring and model
transitions can use their separately declared public parameter/value fragment support. Supporting
new action shapes requires explicit grammar/delegation/conformance work, not an escape hatch.

## Operational models

### RequestFlow and StateMachine

The expanded profile retains these models for composition. RequestFlow declares actor, status,
payload, explicit creations and transitions. StateMachine declares subject, state field, entry
states and transitions. Transitions provide typed inputs, optional related State `parent`, guard
roots and explicit set transfers to bound fields. The model's own generated state assignment
remains authoritative. No action can bypass final-module ownership checks.

### Approval

Configuration contains `model_id`, `subject`, `actor=Actor`, `approve_threshold`, optional
`reject_threshold`, typed `payload`, explicit `open_when` and `eligible`, and both `decisions`:
`approve` and `reject`. Each decision contains typed `inputs`, payload `values` and `requires`.
The host always binds the decision actor from trusted context; user conditions may restrict
eligibility but cannot choose a different acting principal. Public handles determine all counts,
uniqueness, choice values and outcomes.

The adapter declares a fixed `mcp_<model_id>_status` read using public projection and all five
Approval derived handles. Its name is host-authored and reserved against collisions; its returned
field names/results are the public read output. It is included in the persisted module and identity.

### WorkQueue

Configuration contains `model_id`, `worker=Actor`, ordered integer `time`, `max_attempts`, typed
`payload` and all nine `capabilities`. Missing registration is a public model error; schema also
requires the complete set. Each capability has explicit guard roots. Enqueue, claim, recover,
exhaust and cancel additionally require an explicit `authorization` expression. There is no
host default of allow-all. Plain operations use the authoritative owner/generation requirements.

The subset supports typed payload and authorization/guard fragments, not command emission or
arbitrary queue side effects. Core owns status, invariants, lease/generation logic and attempts.
Generated ready/expired reads are discovered from admitted output. A fixed declared
`mcp_<model_id>_terminal` projection uses the public `terminal` handle.

## Safety Models

FieldOwnership records explicit `id`, `entity`, `writers`, `creators`, `removers`. Each action
selector is either `{action: name}` or `{model_id, local_action_id}`, converted to public
`GeneratedAction` for generated actions. Empty lists remain empty. Policies do not replace model
ownership checks and intersect as specified by the authoritative implementation.

LifecycleDependency records `id`, `parent`, `child`, `owner_field`, `parent_state`, `child_state`,
explicit `prohibited`/`terminal` enum members and supporting `ownership` policy IDs. It changes no
runtime action, registry or state. Parent/Child lifecycle acceptance includes explicit required
Ref ownership, association roots and permitted-parent/no-active-child guards. The author supplies
these roots; the policy does not synthesize them.

An analysis with `status=Lowered` remains uncertified and can contain unsupported lifecycle
issues. Return the entire analysis and issues, separately from admission and proof outcomes.

## Required contract fixtures

Implementation must add positive and negative schema/authoring fixtures for each family and node,
and validate the complete generic [Approval](examples/approval.json),
[queue](examples/work-queue.json), [FieldOwnership](examples/field-ownership.json) and
[Parent/Child](examples/lifecycle.json) proposal examples. Current research probes
establish public feasibility; they are not generated client application source or acceptance tests.
Examples and expected outcomes must be authored independently of adapter output.

## Public operand boundary

`field` projects only an explicitly bound State or query entity (`param` receiver).
Scalar, Id and Ref parameters are values; their Python object attributes are not
entity fields. Nested scalar/reference attributes and entity-object equality are
unsupported. Compare entity IDs through explicit `field(..., "id")` projections.
Literal/Enum-left equality remains GAP-005; no Python constant/container/object
comparison may supply a Behavior result. These host support restrictions reject
unsupported proposals; they never reinterpret retained Core Wire or rewrite
immutable handler/schema identities. Core alone checks supported expressions.

Lexical State receivers are `subject` for StateMachine, Approval and authored
change/removal actions; the model ID for RequestFlow transitions; `work` for queue
operations other than enqueue; and optional `parent` where declared. Query `bind`
names introduce local entity receivers. Other parameters are scalar values.
