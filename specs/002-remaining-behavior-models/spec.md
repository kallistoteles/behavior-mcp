# Feature Specification: Remaining Behavior Models

**Feature Branch**: `feat/agent-native-declarative-systems`

**Feature Directory**: `specs/002-remaining-behavior-models`

**Created**: 2026-10-28

**Status**: Draft

**Input**: User description: "fortsätt och implementera för resterande modeller tillgängliga i behavior-ir"

Agents can currently author bounded RequestFlow and StateMachine systems. They need the same
structured, persistent experience for the remaining models in the declared Behavior release:
Approval, WorkQueue, FieldOwnership and LifecycleDependency. This feature includes the Safety
Models as well as the operational models. Upstream availability and delivered server support
must remain distinguishable.

Approval records decisions about existing subjects. WorkQueue governs persistent units of work.
FieldOwnership restricts actions that write fields, create entities or remove entities.
LifecycleDependency assesses the supported parent/child lifecycle pattern. These responsibilities
remain with Behavior; expanded authoring does not make the agent an authority over permissions,
proof validity or deployment.

## Clarifications

### Session 2026-10-28

- Q: Vem ska bestämma värdet för ”nu” när WorkQueue bedömer om en lease fortfarande gäller? → A: Option A — The trusted host supplies now as an explicit, recorded typed value. The agent may propose other time values only within delegated authority and cannot supply or override the authoritative now value.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Author and Use an Approval System (Priority: P1)

An agent discovers Approval, defines decisions about a record, validates the definition and
explicitly activates it within delegated host authority. Permitted callers record decisions and
inspect outcomes without maintaining source code or manually counting votes.

**Why this priority**: Approval closes a substantial gap in supported system types and composes
with existing record lifecycles.

**Independent Test**: Use an Approval definition with an existing subject and trusted actor
records. Define, activate, invoke and inspect it through structured requests, including refused
decisions, without requiring queues or Safety Models.

**Acceptance Scenarios**:

1. **Given** discovery, **When** Approval is selected, **Then** the agent can inspect supported
   subject/actor references, thresholds, decision payload, conditions and exact limitations.
2. **Given** a valid proposal and delegated activation authority, **When** the agent validates
   and explicitly activates it, **Then** generated decision capabilities become discoverable;
   saving, admitting or verifying the proposal alone never activates it.
3. **Given** an existing subject and eligible trusted actors, **When** callers record approve
   and reject decisions, **Then** immutable decisions, counts and outcomes agree with Behavior,
   including threshold boundaries and the distinction between a refused action and a recorded
   rejection. Recording a decision does not itself modify the subject.
4. **Given** a duplicate decision, closed subject, ineligible actor or invalid threshold,
   **When** the relevant request is made, **Then** the authoritative result is returned without
   partial commit, guessed correction or host-calculated approval outcomes.
5. **Given** a lost response or restart, **When** the caller retrieves or reconciles the same
   operation, **Then** it establishes the original result without recording another decision.

---

### User Story 2 - Author and Use Persistent Work Queues (Priority: P1)

An agent defines a queue with payload, explicit time values and an attempt limit. The trusted
host supplies the authoritative current time; the agent proposes other time values within
delegated authority. Authorized callers enqueue work, claim it, manage leases and record
completion or failure. They inspect ready and expired work without asking the server to schedule
or execute business tasks.

**Why this priority**: WorkQueue completes the operational model catalog and exercises types,
read capabilities and recovery boundaries absent from the current scalar authoring subset.

**Independent Test**: Exercise one queue using explicit time and worker identities. Test its
capabilities and readiness/expiry reads, restart and continue the same history without Approval
or Safety Models.

**Acceptance Scenarios**:

1. **Given** an admitted queue definition explicitly activated under trusted policy, **When**
   callers discover capabilities, **Then** enqueue, claim, renew, complete, retry, fail, recover,
   exhaust and cancel are available with authoritative parameters and results.
2. **Given** queue items and an explicit current-time value acquired from trusted host context,
   **When** callers request ready or expired work, **Then** results agree with Behavior at the
   identified state and recorded time. Reading does not claim work, advance time, select a worker
   or execute it.
3. **Given** live or expired leases and remaining or exhausted attempts, **When** callers request
   changes, **Then** Behavior determines ownership, generation, time and attempt constraints.
   Competing claims cannot both publish incompatible resulting state.
4. **Given** an unauthorized worker, stale generation, terminal item or invalid attempt limit,
   **When** the operation is requested, **Then** it receives a structured refusal without a new
   lease, extra attempt or partial change.
5. **Given** a crash before or after publication, **When** recovery runs after restart, **Then**
   it reconciles the original outcome before any authorized fresh publication attempt; uncertain
   acknowledgment cannot cause a duplicate enqueue or claim.
6. **Given** a caller-supplied attempt to select or override current time, or other time values
   outside delegation, **When** a queue operation or time-dependent read is requested, **Then**
   the host rejects the request without changing state. New evaluations and time-dependent reads
   record the typed time from trusted host context; identical operation retries reproduce the
   original outcome and retained time rather than silently evaluating at a newer time.

---

### User Story 3 - Declare Structural Field and Lifecycle Permissions (Priority: P1)

An agent adds FieldOwnership policies naming permitted generated actions for specific fields
and entity creation/removal. It inspects whether the complete definition respects these
structural restrictions before requesting activation.

**Why this priority**: Structural restrictions are useful independently and support the
LifecycleDependency safety argument.

**Independent Test**: Apply a policy to a generated entity and generated actions from an existing
model. Compare allowed definitions and forbidden writer/creator/remover cases without requiring
certification.

**Acceptance Scenarios**:

1. **Given** an entity and supported generated actions, **When** an agent specifies writers,
   creators and removers, **Then** Behavior assesses the complete admitted action set, including
   model-generated actions and overlapping policies.
2. **Given** an explicit empty writer list or overlapping restrictions, **When** a definition
   contains a prohibited assignment, creation or removal, **Then** authoritative validation
   rejects it even with a false guard or an assignment of the existing value.
3. **Given** a structurally accepted policy, **When** the result is inspected, **Then** structural
   analysis is explicitly uncertified. The policy does not grant host permissions, replace model
   ownership rules or authorize deployment.
4. **Given** a caller without activation authority, **When** it proposes permissive policies or
   claims approval in a definition, **Then** its trusted host authority remains unchanged.

---

### User Story 4 - Declare and Check Lifecycle Dependencies (Priority: P2)

An agent defines a parent/child relationship with a required immutable parent reference,
prohibited parent states and terminal child states. It authors supported guarded lifecycle
changes, requests safety assessment and understands which guarantees are established.

**Why this priority**: This completes the Safety Model catalog while preserving its deliberately
restricted authoring and evidence boundaries.

**Independent Test**: Define a generic Parent/Child system and ownership policies. Exercise
supported creation and state changes, assess preservation and inspect persisted-state validity
at an exact history position. Use unsupported action shapes as negative controls.

**Acceptance Scenarios**:

1. **Given** compatible declarations, ownership policies and supported guarded lifecycle actions,
   **When** assessment is requested, **Then** Behavior determines whether the restricted pattern
   is supported. The server does not insert missing guards or invent a relationship registry.
2. **Given** a missing parent binding, mismatched parent association, mutable owner, missing
   mandatory condition or unsupported combination of changes, **When** assessment is requested,
   **Then** the authoritative failed/unsupported stage and affected subject are reported.
   An unsupported proof pattern is not relabeled as a proved runtime violation.
3. **Given** configured certification tooling, **When** a supported definition is certified,
   **Then** the result states assumptions and binds exact behavior, complete safety policies and
   evidence identities. Structural acceptance alone is never certification.
4. **Given** missing tooling, exhausted resources, tampered evidence or an unsupported pattern,
   **When** certification or evidence checking is requested, **Then** no successful certificate
   is claimed; activation fails wherever trusted policy requires that evidence.
5. **Given** certification and persisted state, **When** activation is requested, **Then** the
   host separately establishes required state validity for the exact incoming definition and
   policies at the current history anchor, coordinates every writer and atomically authorizes
   that version. Certification or a detached snapshot alone cannot satisfy deployment checks.

---

### User Story 5 - Compose, Recover and Revise the Expanded Models (Priority: P2)

An agent combines models sharing atomic state within one system, persists a complete definition,
restarts, inspects it and proposes a revision. Previously committed history retains its meaning
and evidence when authoring support expands.

**Why this priority**: Support confined to the initial authoring session would not fulfill the
server's persistence and evolution promises.

**Independent Test**: Recover retained composed-definition fixtures after restart, rebuild them
unchanged, revise an allowed behavior parameter and request explicit activation while retaining
the previous definition for historical interpretation.

**Acceptance Scenarios**:

1. **Given** compatible definitions, **When** Approval is composed with RequestFlow and WorkQueue
   with an independent existing model in the same system, **Then** Behavior determines generated
   declarations, dependencies, ownership, conflicts and whole-definition identities.
2. **Given** generated actions and compatible Safety Models, **When** safety policies are added,
   **Then** analysis covers the complete definition. Policy identities remain inspectable
   separately from operational-model receipts and behavior identity.
3. **Given** any new model definition with complete retained authoring information, **When** it
   is persisted, restarted and rebuilt unchanged under declared versions/context, **Then** all
   applicable model, policy, behavior and schema identities remain unchanged.
4. **Given** an admitted definition, **When** a semantic parameter is revised, **Then** a new
   immutable definition is produced with identities determined by Behavior. Old active references
   and historical evidence remain intact until authorized activation succeeds.
5. **Given** a revision requiring schema migration or an unsupported deployment condition,
   **When** activation is attempted, **Then** it is refused without best-effort conversion or
   reinterpretation of existing state.
6. **Given** definitions and histories predating this feature or created at an earlier accepted
   checkpoint of this feature, **When** the expanded server opens
   their workspace, **Then** supported reading, invocation, recovery and retained authoring/revision
   journeys remain available under their recorded construction context.

---

### User Story 6 - Understand Support and Authority Boundaries (Priority: P2)

An agent distinguishes supported authoring, generated actions and reads, structural analysis,
verification, conditional certification, deployment authorization and runtime results. It can
identify an upstream gap without receiving a false success response.

**Why this priority**: Catalog expansion must not imply that upstream availability or successful
analysis establishes complete authoring support, proof or operational permission.

**Independent Test**: Inspect catalog and evidence fixtures for all six model families; submit
malformed, unsupported and unauthorized requests without a live AI model.

**Acceptance Scenarios**:

1. **Given** discovery, **When** all families are inspected, **Then** RequestFlow, StateMachine,
   Approval, WorkQueue, FieldOwnership and LifecycleDependency each have explicit support status,
   configuration scope, provenance and limitations. Safety policies are not runtime actions.
2. **Given** agent-supplied actor, worker, approval, evidence or authority claims, **When** a
   privileged operation is requested, **Then** trusted host context and policy independently
   determine authority. Domain decisions cannot approve their model's own deployment.
3. **Given** two systems sharing immutable artifacts, **When** callers invoke, activate, assess
   or recover one, **Then** the other's state, history, active definition and authority remain
   isolated, including forbidden attempts to reference its entities or evidence.
4. **Given** an upstream or bounded-authoring limitation, **When** an operation depends on it,
   **Then** it remains explicitly unsupported with reproducible gap evidence and no silent
   fallback to host-defined semantics.

### Edge Cases

- Models reference contributed entities or arrive in different authoring orders; dependency
  resolution and composition remain authoritative Behavior operations.
- Duplicate model/policy identifiers, generated declaration collisions, unknown action selectors
  and ambiguous references produce errors rather than guessed matches.
- Approval rejection, denied action, pending outcome and failed certification remain distinct.
  Thresholds and actor uniqueness are not recomputed by the host.
- Queue current time is an explicit typed value acquired from trusted host context and retained
  with the operation or read evidence. Client overrides are refused. Other proposed time values
  remain subject to delegation. Lease renewal, expiry, stale generations and retry limits are
  tested immediately before, at and after boundaries using controlled trusted time.
- A retry after time has advanced retains the original operation outcome and recorded time.
  Replay uses historical time evidence; a new evaluation acquires a new trusted time value.
- Distinct host operation identifiers can share one Core transition identity; a missing host
  receipt alone cannot prove that the semantic transition did not commit.
- Policy revocation or changed activation after an uncertain response does not prevent outcome
  reconciliation when current read/recovery authority remains. Fresh publication still requires
  current applicable authority.
- Ownership can forbid apparently harmless writes. A lifecycle condition inside an alternative
  branch is not treated as a mandatory guard through host reasoning.
- Terminal children still reference existing parents; parent deletion and reference integrity
  remain governed by Behavior rather than host cleanup rules.
- Imported proof bytes, matching behavior identity or certification under different policies
  cannot establish current evidence validity. Policy-only changes require exact policy identity
  and deployment binding even when runtime behavior identity is unchanged.
- Limits, interrupted assessments and concurrent writers cannot produce partial commits,
  successful proof claims or uncoordinated activation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Discovery MUST cover all six named families and distinguish operational models
  from Safety Models, upstream availability from delivered support, and authoritative descriptions
  from host-owned bounded configuration descriptions. (US1–US6)
- **FR-002**: Agents MUST author Approval through structured subject/actor references, thresholds,
  decision payload and supported open/eligibility conditions, using Behavior's authoring and
  runtime semantics. (US1)
- **FR-003**: Approval MUST expose recorded decisions and authoritative counts/outcomes without
  implicitly modifying the subject. Trusted actor attribution, duplicate decisions, closed
  subjects and invalid configurations MUST have acceptance cases. (US1)
- **FR-004**: Agents MUST author WorkQueue through structured worker and time types, payload,
  attempt limits and explicit authorization conditions. All nine capabilities named in US2 MUST
  be discoverable and invocable when present in an active definition. (US2)
- **FR-005**: Callers MUST read authoritative Approval outcomes and WorkQueue readiness, expiry
  and terminal status at an identified state. Reads MUST remain separate from mutations and
  MUST NOT require host reproduction of decision or queue logic. (US1–US2)
- **FR-006**: Queue operations MUST preserve Behavior's ownership, lease, generation and attempt
  rules with explicit typed time values. Authoritative current time MUST come from trusted host
  context for each new evaluation and time-dependent read and MUST be recorded in its evidence.
  Caller attempts to supply or override that current time MUST be rejected. Agents MAY propose
  other time values only within delegated authority. Identical operation retries and replay MUST
  retain original time evidence; a fresh evaluation MUST acquire a new trusted time value.
  These are host trust restrictions; Behavior alone decides time-dependent semantics. The server
  MUST NOT add scheduling, automatic business retries, background task execution or implicit
  wall-clock advancement. (US2)
- **FR-007**: Agents MUST author FieldOwnership over declared or contributed entities with explicit
  field writer, creator and remover selections. Behavior MUST assess all relevant generated
  actions and overlapping restrictions. (US3)
- **FR-008**: Agents MUST author LifecycleDependency through parent/child types, an immutable
  required parent reference, lifecycle fields, prohibited/terminal states and supporting ownership
  policies. Behavior MUST recognize or refuse the supported pattern. (US4)
- **FR-009**: Structured authoring MUST express declarations, references, conditions and effects
  needed by the acceptance journeys, including required lifecycle guards. It MUST NOT accept
  executable client code, create a general scripting language, insert missing semantic guards
  or bypass unavailable authoring support with handcrafted low-level behavior. (US1–US5)
- **FR-010**: Results MUST distinguish malformed input, invalid models, lowering/admission,
  structural analysis, verification, conditional certification, authorization and committed
  transition outcomes. Authoritative diagnostics and unsupported/inconclusive results MUST remain
  distinguishable. (US1–US6)
- **FR-011**: The server MUST support explicit safety certification and fresh checking of imported
  evidence through Behavior, bound to exact subject, complete policy set, assumptions, obligations
  and toolchain identities. Missing tooling, exhausted limits and failed checking MUST NOT produce
  a successful certificate. Loading evidence alone MUST NOT establish validity. (US4)
- **FR-012**: Safety evidence and policies MUST be retained separately from operational-model
  receipts and generated behavior, preserving actual upstream identity contracts. The host MUST
  NOT assume every family has the same receipt or identity format. (US3–US5)
- **FR-013**: Admission and evidence generation MUST NOT activate definitions. Trusted versioned
  delegation MUST constrain exact capabilities, safety policies, effects and permitted state
  changes; definitions outside delegation require refusal or trusted exact-version approval.
  Agent-authored policies MUST NOT modify host authority. (US1–US6)
- **FR-014**: Safety Model activation MUST satisfy applicable proof and current-state validity
  requirements for the exact incoming definition and complete policy set. Validation and atomic
  activation MUST coordinate every writer. Deployment evidence MUST retain behavior, safety
  policy, trusted authorization and exact history identities. (US4–US5)
- **FR-015**: Definitions, complete original authoring/context, canonical outputs, generated
  behavior, diagnostics, receipts and safety evidence MUST survive restart. Unchanged rebuilding
  MUST preserve applicable identities under declared versions/context. Missing canonical authoring
  content MUST remain an explicit limitation. (US1–US5)
- **FR-016**: Compatible models MUST compose within one system through Behavior. Both operational
  compositions in US5 and compatible generated-action safety policies MUST be demonstrated;
  conflicting ownership and declaration dependencies MUST be diagnosed authoritatively. (US3–US5)
- **FR-017**: Each new family MUST support inspection and a retained proposal revision. Semantic
  revisions MUST create new immutable artifacts with authoritative identities. Unsupported schema
  migrations MUST block activation without reinterpreting historical state or evidence. (US5)
- **FR-018**: Expanded support MUST preserve previously supported definitions, active systems,
  history, recovery and authoring/revision under recorded context. Unsupported contexts MUST be
  explicit rather than substituted. Existing supported contexts, including earlier accepted
  checkpoints of this feature, MUST have retained regression fixtures. Adding another model family
  MUST NOT require regeneration of these definitions or replacement of their implementation context.
  (US5)
- **FR-019**: New capabilities MUST preserve existing evaluation, commit and recovery guarantees,
  including exact refused retries, conflicts, lost acknowledgments and reconciliation after
  authority/activation changes. Reconciliation MUST be separate from fresh publication authority.
  (US1–US2, US5)
- **FR-020**: Trusted workspace, stable SystemId, operation and principal scope MUST apply to all
  new authoring, reads, safety operations, activation and recovery. Shared artifacts MUST NOT
  create cross-system state, authority or historical dependencies. (US6)
- **FR-021**: New authoring and evidence operations MUST retain bounded input, output, concurrency
  and execution resources. Exhaustion MUST produce structured failure or inconclusive results
  without leaked capacity, untracked workers or successful certification claims. (US4, US6)
- **FR-022**: Each delivered family and advertised construct MUST have deterministic positive,
  negative and unsupported acceptance coverage without a live AI model. Tests MUST compare
  semantics and identities with the pinned public Behavior implementation; development MUST be
  test-first. (US1–US6)
- **FR-023**: Public dependency boundaries and exact released identities MUST remain enforced.
  Unavailable public capabilities MUST be recorded with reproducible evidence in `SEMANTIC_GAPS.md`
  and remain visible in release acceptance. More adapters alone MUST NOT close existing gaps.
  (US1–US6)

### Key Entities

- **Catalog Entry**: Family/category, provenance, delivered configuration scope, runtime or
  analysis capabilities and limitations.
- **Authoring Proposal**: Editable model/policy data, composition references, revision ancestry
  and complete reconstruction context.
- **Admitted Definition**: Immutable behavior linked to original proposal, canonical model
  artifacts, model/policy identities, schema identity and applicable receipts.
- **Approval Decision and Outcome**: An immutable subject-bound actor decision and counts/status
  derived by Behavior; neither establishes trusted deployment approval.
- **Work Item**: Persistent payload, status, ownership, explicit timing, attempts and generation
  evidence as defined by Behavior.
- **Safety Policy Set**: Complete FieldOwnership/LifecycleDependency policies for an exact
  definition, with identities separate from trusted host delegation.
- **Safety Assessment and Evidence**: Structural findings, conditional certification or fresh
  checking results with exact subject, obligations, assumptions and provenance.
- **State Validity Evidence**: A separate result acquired from authoritative persisted state at
  an exact history position for the incoming definition and policy set.
- **System Deployment**: Stable independent system, active definition and safety policies,
  trusted authorization and coordinated state/history boundary.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A client discovers all six families with accurate delivered support and limitations;
  no family is silently omitted or presented as more complete than its evidence. (FR-001, FR-023)
- **SC-002**: An Approval journey covers recorded approval/rejection, pending/threshold outcomes,
  duplicate/unauthorized refusal and post-restart continuation, without generated application
  source code or manually maintained vote totals. (FR-002–FR-003)
- **SC-003**: A WorkQueue journey exercises all nine capabilities and ready/expired reads, including
  lease boundaries, stale generations, exhaustion and competing claims; all results agree with
  the declared behavioral authority. Each new evaluation and time-dependent read records trusted
  host time. Forged current time and other proposed time values outside delegation produce zero
  mutations; retries after time advances preserve original outcomes/time evidence. (FR-004–FR-006)
- **SC-004**: FieldOwnership has allowed/forbidden writer, creator and remover cases, overlapping
  restrictions and at least one generated action. Structural acceptance is always uncertified
  unless separate certification succeeds. (FR-007, FR-010)
- **SC-005**: LifecycleDependency has a supported parent/child journey, an unsupported-shape result,
  successful conditional certification in the declared certification environment and negative
  controls for missing guards and changed evidence. (FR-008–FR-011)
- **SC-006**: Each of the four added families can be inspected, rebuilt unchanged and revised
  after restart. Unchanged rebuilding preserves all applicable identities; a demonstrated semantic
  revision yields the expected distinct identity while old artifacts remain recoverable.
  (FR-012, FR-015, FR-017)
- **SC-007**: Both operational compositions in US5 and compatible safety policies over generated
  actions are demonstrated, together with a conflicting composition that is refused.
  (FR-009, FR-016)
- **SC-008**: Every activation case records exact incoming definition, applicable safety policies,
  trusted policy and history anchor. Unauthorized, stale, invalid-state and missing-required-proof
  cases produce zero activations. (FR-013–FR-014)
- **SC-009**: Approval and queue mutation fixtures survive crashes before/after publication.
  Identical retries reproduce original outcomes without extra committed events, including changed
  authority or active definitions. (FR-019)
- **SC-010**: Two systems using expanded families continue independently across simultaneous use,
  separate activation and restart/recovery; all unauthorized cross-system cases are refused.
  (FR-020)
- **SC-011**: Existing supported definition, invocation, recovery, authoring/revision and historical
  interpretation fixtures pass. Active systems need no regeneration merely because another family
  became supported. (FR-018)
- **SC-012**: All advertised constructs have positive, negative and unsupported coverage without a
  live AI model. Resource-limit cases leave no successful proof claim, partial mutation or leaked
  capacity. Remaining blocking gaps are explicit in acceptance results. (FR-021–FR-023)

## Assumptions

- "Remaining models" includes Approval, WorkQueue, FieldOwnership and LifecycleDependency.
  RequestFlow and StateMachine already have bounded support and expand here only as needed for
  the new acceptance journeys.
- The baseline remains the exact Behavior 0.14.0 release and associated Core 0.15.0. Future release
  models or dependency upgrades require a separate compatibility review.
- Delivered support may have explicit authoring bounds. Bounds cannot exclude the mandatory
  journeys or label an undelivered family complete. Blocking public capability gaps remain
  incomplete requirements with reproducible evidence.
- Canonical-only reconstruction and generic model-metadata gaps remain open unless fresh
  release-specific evidence closes them. Complete original authoring information remains
  necessary where canonical documents omit semantic bodies.
- Certification requires its declared trusted tooling. Normal execution and historical state
  replay do not run a proof tool. Deployments requiring certification fail closed when it is
  unavailable; other deployments make no certification claim.
- A trusted local operator can provision actor/worker records, bounded caller authority and a
  controlled trusted time source for tests. Clients cannot select trusted principals, impersonate
  actors or override authoritative current time via model/runtime fields. The host records time
  as explicit input to Behavior; this does not introduce a hidden clock into model semantics.
- Existing local single-user trust, delegated activation and independent systems remain in force.
  Remote tenancy, distributed coordination, cross-system transactions, external execution and
  schema-changing activation remain outside this feature.
- Domain approvals and Safety Models provide no privileged host authority. Host delegation
  separately governs activation and invocation.
- Repository examples and acceptance fixtures remain domain-neutral.

### Reference Basis

Scope was checked against the installed declared release and tagged
[Behavior Models documentation](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/models/README.md),
including Safety Models and lifecycle guard sections. The released public
[Approval](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/python/behavior/approval.py),
[WorkQueue](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/python/behavior/work_queue.py)
and [Safety Model](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/python/behavior/safety.py)
surfaces establish availability, not implementation completion. This feature inherits the
[constitution](../../.specify/memory/constitution.md) and
[initial activation/isolation decisions](../001-agent-native-systems/spec.md).
