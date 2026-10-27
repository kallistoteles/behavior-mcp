# Feature Specification: Behavior MCP — Agent-Native Declarative Systems

**Feature Branch**: `main`

**Feature Directory**: `specs/001-agent-native-systems`

**Created**: 2026-10-26

**Status**: Draft

**Repository**: `behavior-mcp`

**Type**: Experimental integration and capability

**Primary Dependency**: Behavior IR

**Initial Consumer Context**: AI agents working with persistent structured notes

**Input**: User description: "Create a general-purpose MCP server for discovering, defining,
validating, persisting, activating and using Behavior-based systems through structured data.
Investigate canonical model documents before introducing another authoring representation.
Preserve Behavior's semantic authority, persistent history and trusted activation boundaries."
Repository content and acceptance examples are domain-neutral.

AI agents need to create and continue using persistent systems without generating or maintaining
application source code. Behavior MCP provides structured access and artifact management while
Behavior Models and Behavior Core retain their respective authoritative responsibilities.

The central architectural question is: **Can Behavior Models' existing canonical representations
serve directly as the persistent and editable definition format for agent-authored systems?**
The specification requires an evidence-based answer rather than assuming either sufficiency or
insufficiency. It does not select a replacement format, storage technology or first model family.

## Clarifications

### Session 2026-10-26

- Q: Should an agent be allowed to activate definitions using authority granted beforehand, or should the local user approve each exact version? → A: Allow delegated activation within explicit, host-enforced authority, governed by a separate, versioned host-policy object that the agent cannot modify. Workspace membership alone is insufficient. The host must check permitted model capabilities, permissions, external effects, state changes, migrations, admission, applicable verification and deployment conditions for each definition. Out-of-scope definitions require refusal or trusted approval of the exact version. Atomic activation must record the exact BehaviorHash, policy version, authorization and history anchor.

- Q: Should the first release manage multiple independent Behavior systems within one workspace? → A: Multiple independent systems per workspace, each with a stable SystemId independent of BehaviorHash, its own active definition, Core Store, genesis, state, history, concurrency boundary and authorization scope. Immutable content-addressed definition artifacts may be shared; mutable state, history and activation references remain isolated. Creation, activation, invocation, migration and recovery enforce trusted workspace, system and operation scope. The first release excludes cross-system references, transactions, orchestration, implicit dependencies, distributed coordination and multi-user tenancy. Models requiring shared atomic semantics are composed within one system. Isolation must be demonstrated through simultaneous use, independent activation, recovery and unauthorized cross-system access tests, without building a general system-management framework.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Discover and Propose a Declarative System (Priority: P1)

An agent discovers supported model families and their configuration requirements, then submits
a structured definition for records with attributes, lifecycle states and permitted changes.
The agent can inspect and persist the proposal, obtain precise validation feedback and identify
the capabilities it would produce without writing application source code.

**Why this priority**: Authoring through structured data is the central capability being
investigated. A durable, inspectable proposal has value before deployment is authorized.

**Independent Test**: Submit deterministic requests without a live AI model to discover a
supported model, save a proposal, inspect it and obtain validation results. Confirm that no
proposal becomes active during this journey.

**Acceptance Scenarios**:

1. **Given** a declared Behavior release, **When** a client requests model discovery, **Then** it
   receives supported model descriptions, configuration information and their authoritative
   provenance, or an explicit limitation for information the public release cannot supply.
2. **Given** a supported model configuration, **When** the agent submits entities, parameters,
   relationships, conditions and effects supported by that model, **Then** the proposal is
   processed through authoritative authoring interfaces without executable application code.
3. **Given** a stored proposal, **When** the client requests validation and inspection, **Then**
   structural validity, model validity, lowering, admission, generated declarations and any
   verification evidence have distinguishable results and refer to the exact definition.
4. **Given** malformed, incomplete, executable or unsupported input, **When** the client submits
   it, **Then** it receives a structured refusal or error without guessed repairs, fabricated
   semantics or a partially admitted definition.
5. **Given** a saved, admitted or verified definition, **When** no authorized activation has
   occurred, **Then** it remains inactive and cannot govern domain-state changes.
6. **Given** historical verification evidence and a later toolchain or trust policy, **When**
   the result is inspected, **Then** its original subject, assumptions, coverage and versions
   remain intact and it is not relabeled as verified under the later context.

### User Story 2 - Activate, Use and Recover a Persistent System (Priority: P1)

The host manages multiple independent systems in one workspace, each identified by a stable
SystemId. The trusted host delegates bounded activation authority through a separate, versioned
host policy. An agent explicitly activates eligible definitions within that authority, discovers their
active capabilities, creates and reads records, requests permitted changes, understands refusals
and continues using the same system in a later session after the server has restarted.

**Why this priority**: Persistent use establishes that the feature delivers a usable system
across sessions, with trusted activation and authoritative transitions.

**Independent Test**: Start with two systems in one workspace, authoritative admitted definition
fixtures and trusted host context. Exercise overlapping operations, independent activation,
forbidden access to the other system, a restart and recovery of one system. Continue from an
independent client session and verify each SystemId, active definition, Core Store and history.
The fixtures make this journey testable without relying on the proposal-authoring journey.

**Acceptance Scenarios**:

1. **Given** an eligible inactive definition and a host-controlled delegation policy, **When**
   the agent explicitly requests activation for a specific SystemId, **Then** the host checks
   trusted workspace, system and operation scope and independently checks the resulting
   capabilities, permissions, effects, state changes, migrations, required evidence and deployment
   conditions against that delegation. An allowed activation is persistent and atomic and records
   the target SystemId, exact BehaviorHash, policy identity and version, authorization and
   history anchor.
2. **Given** an untrusted request declaring an actor, role, approval or workspace authority,
   **When** it requests a privileged operation, **Then** only trusted host context determines
   authority and the declaration cannot grant permission.
3. **Given** an active system and a valid record input, **When** a client requests a permitted
   operation, **Then** Behavior Core determines the result, and commitment preserves the required
   identities, valid resulting state and durable transition history.
4. **Given** a record in a state where an operation is disallowed, **When** that operation is
   requested, **Then** the client receives the authoritative refusal and no partial change.
5. **Given** an inspection or evaluation request, **When** it completes, **Then** it is clearly
   distinguishable from a committed transition and causes no speculative external execution.
6. **Given** committed changes and an active deployment, **When** the server stops and recovers,
   **Then** definitions, active references, committed state and history remain available, and
   a new client session discovers the same active system without remembered agent context.
7. **Given** a concurrent conflicting operation or a lost acknowledgment, **When** a client
   retries, **Then** conflicts require authoritative re-evaluation and an uncertain earlier
   outcome is resolved before any new mutation can produce a duplicate transition.
8. **Given** a client independent of a note application or AI provider, **When** it follows
   the documented structured interactions, **Then** it can discover and use the same system.
9. **Given** a definition in an authorized workspace that exceeds delegated model capabilities,
   permissions, effects, state changes or migration authority, **When** activation is requested,
   **Then** it is refused unless a trusted channel supplies approval of that exact version;
   ordinary workspace access and agent-claimed approval are insufficient.
10. **Given** an agent-authored model or request attempting to modify the delegation policy,
    **When** it is processed, **Then** the agent's authority remains unchanged. Policy changes
    require the trusted host authority outside the agent-controlled model.
11. **Given** trusted approval bound to one exact version, **When** a different version is
    submitted or the applicable delegation changes before publication, **Then** the old approval
    or stale policy check cannot authorize activation. All current admission, verification and
    deployment requirements still apply.
12. **Given** trusted authority to create systems in a workspace, **When** two systems are
    created, **Then** each receives a distinct stable SystemId and its own Core Store with its
    own genesis, state, history and concurrency boundary. Shared immutable definition artifacts
    do not make them the same system or grant additional authority.
13. **Given** two independent systems, **When** both are used simultaneously and a new definition
    is activated in one, **Then** each operation uses its system's Store and concurrency boundary;
    the other system's active definition, mutable state and history remain unchanged.
14. **Given** authority over one system but not another in the same workspace, **When** a client
    attempts to read, activate, invoke, migrate or recover the other, **Then** the host rejects
    unauthorized access even if both systems use the same immutable behavior artifacts.
15. **Given** two persisted systems, **When** one is interrupted or recovered and both are later
    reopened, **Then** each retains its SystemId, active definition and history; recovery of one
    does not reset, overwrite or reinterpret the other's state or history.
16. **Given** an activation committed before its acknowledgment was lost, **When** the same
    scoped OperationId and request are retried, **Then** its durable receipt returns the original
    activation without another pointer/audit update, even if the current deployment later changed.
17. **Given** a changed request, wrong system or unavailable activation receipt, **When** an
    activation retry is processed, **Then** it cannot infer success from BehaviorHash or replay a
    Core bundle; it reports conflict/uncertainty or performs only currently authorized publication.

### User Story 3 - Inspect and Revise a System Safely (Priority: P2)

An agent retrieves a persisted definition after a restart, inspects it and proposes a revision.
The revised definition has its own applicable identities and remains inactive until authorized.
A trusted authority can activate supported changes while preserving existing state validity and
historical interpretation.

**Why this priority**: Systems must evolve without making old decisions uninterpretable or
turning an edit into an implicit deployment or migration.

**Independent Test**: Use a persisted definition, admitted artifacts and historical state fixture.
Exercise unchanged reconstruction, a supported semantic revision and an unsupported evolution
case without depending on a particular model-authoring client.

**Acceptance Scenarios**:

1. **Given** a stored definition and its exact dependency versions and composition context,
   **When** it is reconstructed, inspected and lowered unchanged through public authoritative
   interfaces, **Then** relevant model and generated behavior identities and meaning are
   preserved, or the missing reconstruction capability is recorded explicitly as a gap.
2. **Given** a recovered definition, **When** the agent changes semantic content, **Then** the
   system preserves the original artifacts and its stable SystemId, assigns version identities
   according to Behavior's contracts and leaves each system's current deployment unchanged until
   authorized activation of that specific system.
3. **Given** a proposed behavior-only revision, **When** activation is requested against
   existing state, **Then** applicable compatibility, validity and deployment conditions are
   established under a boundary that coordinates every relevant writer.
4. **Given** a revision requiring schema evolution, **When** no supported migration or required
   deployment condition can be established, **Then** activation is blocked, the limitation is
   visible and no best-effort conversion changes the state.
5. **Given** an intervening state write after an earlier activation check, **When** activation
   is attempted, **Then** stale checks cannot authorize deployment; required conditions must
   still hold at the coordinated activation boundary.
6. **Given** history committed under an earlier deployment, **When** a newer version is active
   and the server restarts, **Then** the original definitions, receipts and any migration
   artifacts remain recoverable for authoritative historical interpretation and replay.
7. **Given** a stored proposal and its resolved revision, **When** a complete revision names
   base_proposal_id and the matching expected_proposal_revision, **Then** a new immutable snapshot
   is appended under the same ProposalId with its parent DefinitionId preserved. Stale concurrent
   edits conflict without appending; a new fork may explicitly name its authorized parent.
8. **Given** an exact proposal_id and proposal_revision, **When** validation runs while another
   revision becomes latest, **Then** the result remains bound to the requested immutable source.

### User Story 4 - Compose Models and Understand Capability Limits (Priority: P2)

An author evaluates whether multiple existing Behavior Models can describe one system through
supported composition. The author can distinguish supported combinations, conflicts and missing
public capabilities and obtain reproducible evidence for limitations.

**Why this priority**: The experiment must establish whether the authoring approach generalizes
without adding another model language or hiding gaps behind local semantic implementations.

**Independent Test**: Use authoritative model examples from two existing model families and a
conflicting or unsupported case. Produce a composition result or a reproducible limitation
record and an evidence-backed answer to each research question.

**Acceptance Scenarios**:

1. **Given** two models compatible under the pinned release's public composition contract,
   **When** their definitions are composed, **Then** ownership, generated declarations,
   references and lowering follow that contract without independently implemented semantics.
2. **Given** conflicting declarations or incompatible model relationships, **When** composition
   is requested, **Then** the authoritative conflict or unsupported result is exposed without
   silently selecting a definition or weakening validation.
3. **Given** a canonical document missing information needed for reconstruction, **When**
   authoring support is assessed, **Then** the missing information and impact are recorded;
   original authoring information may be retained explicitly but cannot be guessed.
4. **Given** a required discovery, authoring, verification or persistence capability unavailable
   publicly, **When** it is requested, **Then** the result identifies the unsupported boundary
   and links to reproducible gap evidence rather than promising the capability.
5. **Given** a blocking upstream limitation, **When** experimental acceptance is reported,
   **Then** the research finding is recorded and affected delivery criteria remain visibly
   unmet; the limitation is not converted into a successful runtime demonstration.
6. **Given** models that require shared atomic state, **When** they are combined, **Then** their
   supported composition is within one module and one system. References, atomic transactions,
   orchestration and implicit dependencies across systems are explicitly unsupported.

### Edge Cases

- Missing attributes, invalid parameter types, unknown model families, unresolved references and
  unsupported structured expressions produce errors without inferred repairs.
- Executable definitions, dynamically evaluated expressions and attempts to bypass authoring
  with hand-authored low-level behavior are refused.
- A canonical document that can be serialized but cannot be reconstructed is not advertised as
  a complete authoring representation.
- An unchanged model is lowered with changed composition context, declarations or dependency
  versions; an identical ModelHash alone cannot establish identical generated behavior.
- Missing, invalid, expired under an applicable policy, inconclusive or unsupported evidence
  cannot satisfy an activation policy that requires valid evidence.
- A stored artifact, lowering receipt or matching hash is mistaken for activation or approval;
  the authoritative active reference and trusted policy determine the actual status.
- Workspace access is used to request new permissions, external command capabilities, destructive
  migrations or policy changes beyond the delegation; the host refuses activation or requires
  trusted approval of the exact version. Approval cannot waive required Behavior checks.
- A delegation is changed or revoked while activation is being checked; publication must establish
  authority under the applicable policy at the coordinated activation boundary. Missing policy or
  insufficient authoritative information to establish the delegated scope fails closed.
- Concurrent state writes, competing activations and migration writers race with validation;
  stale checks cannot authorize a change outside the coordination boundary.
- A process stops before commitment, after durable commitment or before acknowledgment;
  recovery distinguishes these outcomes and prevents partial or duplicate transitions.
- A historical artifact is missing or has mismatched behavior, schema or release identity;
  required activation, execution or replay fails explicitly rather than substituting a newer one.
- A proposed revision has familiar entity or field names but lacks actual compatibility evidence;
  appearance does not authorize migration or activation.
- A client supplies forged identities, permissions, workspace scope or natural-language override
  instructions; none can change the host's trusted authorization context.
- Rejected requests contain credentials or sensitive values; returned diagnostics and audit
  records exclude credentials and unnecessary sensitive data.
- Two systems share the same BehaviorHash or canonical definition; that shared version identity
  cannot substitute for SystemId, share mutable state or grant access to the other system.
- A request targets another system or its Store using a forged or missing scope; workspace
  membership alone cannot authorize system creation, access, activation, migration or recovery.
- Models attempt references, atomic transactions, orchestration or implicit dependencies across
  systems; the first release rejects these rather than coordinating behavior locally.
- Recovery or a failed activation in one system must not reset, overwrite or reinterpret the
  active definition, state or history of another system.
- A note or other editable projection is changed outside the authoritative transition protocol;
  this does not constitute a committed domain-state change.
- A transition yields an external command intent; evaluation alone cannot execute business I/O,
  and a requested external action is not reported as completed work.
- Artifact storage or another infrastructure dependency fails; the result remains distinguishable
  from semantic refusal and cannot report an unestablished successful commitment.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001 — Model discovery**: The system MUST expose which Behavior Models the declared
  release supports, their purposes and their supported configuration. Descriptions, parameter
  types and constraints MUST use authoritative public information where available. Missing
  metadata MUST be reported explicitly rather than replaced by an independent semantic
  interpretation or an unsupported capability promise.
- **FR-002 — Declarative model authoring**: Clients MUST be able to submit structured
  definitions for supported models, including supported entities, parameters, conditions,
  effects and relationships. Authoring, typed expressions, normalization and admission MUST use
  supported authoritative interfaces. Executable application code, guessed repairs and bypasses
  of an unavailable public authoring capability MUST NOT be accepted as model definitions.
  Authorized system creation MUST establish a stable SystemId within trusted workspace scope.
  Creating a system MUST NOT itself grant authority beyond the host's delegation.
- **FR-003 — Canonical model representation**: The project MUST evaluate existing canonical
  model documents for authoring, persistence, retrieval, inspection, revision and reconstruction.
  Evidence MUST demonstrate unchanged round-trips under exact versions and composition context
  before claiming support. Semantic content, authoring metadata, generated artifacts and lowering
  receipts MUST remain distinct. Missing authoring information MUST be documented; retaining an
  original authoring representation MUST have an explicit relationship to the canonical document.
  Any additional format requires a documented insufficiency and MUST NOT define new semantics.
  Proposal revisions MUST identify their base and expected head explicitly, preserve immutable
  older snapshots and record an optional authorized parent definition without guessing lineage.
  Validation MUST name an exact immutable source revision.
- **FR-004 — Model composition**: The system MUST support multiple compatible models
  contributing to one behavior module through available public composition contracts. The
  initial investigation MUST evaluate two existing model families. Declaration ownership,
  relationships and conflicts MUST follow authoritative contracts; unsupported combinations
  MUST remain explicit limitations rather than locally invented workflow semantics. Models
  requiring shared atomic semantics MUST be composed within one module and one system; separate
  systems MUST NOT acquire implicit dependencies through MCP.
- **FR-005 — Validation and verification**: Feedback MUST distinguish structural validity,
  valid model configuration, lowering and admission, generated capabilities, verified properties,
  authorization and runtime commitment. Verification evidence MUST retain its exact subject,
  toolchain, semantic profile, obligations, assumptions and evidence identity. Inconclusive,
  unsupported, timed-out or incomplete results MUST NOT be labeled successful proof. Admission
  alone MUST NOT imply safety, verification or approval.
- **FR-006 — Persistent definitions and identities**: Definitions and generated behavior
  MUST be stored durably and admitted artifacts MUST be immutable. The system MUST preserve and
  expose their relationships to ModelHash, BehaviorHash, SchemaHash, model versions, lowering
  receipts, relevant releases and composition context. Each system MUST have a stable SystemId
  independent of BehaviorHash and definition revisions, with its own persistent active-definition
  reference. Immutable content-addressed definitions and generated modules MAY be shared across
  systems; mutable state, history and activation references MUST remain isolated. Historical
  artifacts MUST survive restart and remain recoverable without generated application source
  files or a Git repository.
- **FR-007 — Persistent state and history**: Domain-state changes MUST use supported Behavior
  Core evaluation, migration and commitment contracts. Each system MUST have its own Core Store,
  genesis, state, history and concurrency boundary. Evaluation and commitment MUST remain
  distinguishable. Durable state and history MUST preserve exact identities, consistent source
  snapshots, resulting-state validity, atomic comparison and commitment, concurrency handling,
  recovery and historical replay. Clients MUST NOT directly edit authoritative domain records.
- **FR-008 — Activation and version evolution**: Proposals MUST remain separate from active
  deployments. Activation MUST be explicit and authorized for the exact definition by the
  applicable delegated activation policy or trusted exact-version approval for that SystemId.
  Activating one system MUST NOT activate a definition in another. Admission, applicable
  verification, deployment validation and current-state conditions MUST succeed, and any migration
  or existing-state change MUST be explicitly authorized. Active references MUST change
  persistently and atomically under a boundary covering all relevant writers, migrations and
  applicable policy changes. Each activation MUST record trusted workspace scope, SystemId, the
  exact BehaviorHash, policy identity and version, authorization evidence and history anchor.
  Activation MUST atomically persist a scoped OperationId/request/result receipt with the pointer
  and audit record. Identical retries MUST resolve that original outcome before fresh CAS or
  validation, distinguishing it from a separately observed current deployment. Revisions MUST preserve historical
  meaning, distinguish behavior-only and schema changes and use supported migrations where
  required. Unsupported or unestablished conditions MUST block activation without inferred
  conversions or silent replacement of the active definition.
- **FR-009 — Runtime capability discovery and invocation**: Clients MUST be able to discover
  capabilities of active modules, read state and request actions through structured interactions
  targeting an explicitly identified system. Results MUST identify the trusted workspace, SystemId,
  evaluated deployment and relevant state or history position and
  distinguish evaluation, refusal, commitment and requested external work. Runtime decisions,
  resulting changes and semantic evidence MUST originate from Behavior Core without independent
  business rules for individual model families.
- **FR-010 — Trust and authority boundaries**: All client input MUST be treated as untrusted
  and pass structured parsing, applicable admission and authorization. Proposal, validation,
  verification, authorization, activation, invocation and commitment MUST retain distinct
  authority boundaries. Identity, scope and privileged context MUST come from the trusted host.
  Delegated activation authority MUST be a separate, versioned host-policy object outside the
  agent-authored Behavior Model, controlled only by trusted host authority. It MUST constrain
  permitted model capabilities, permissions, external effects, state changes, migrations and
  applicable verification and deployment requirements as well as workspace, system and operation
  scope. System creation, activation, reads, invocation, migration and recovery MUST each enforce
  the applicable trusted workspace and system scope. The host MUST
  independently assess every proposed definition against this policy using supported authoritative
  information; workspace membership, client declarations, model content or claimed approval MUST
  NOT establish or expand authority. The agent MUST NOT modify or extend its delegation. A
  definition outside delegated authority MUST be refused unless a trusted channel approves the
  exact version; such approval MUST NOT waive required Behavior admission, verification or
  deployment checks. These host restrictions MUST NOT be presented as Behavior semantic
  guarantees. Initial local trust assumptions MUST be explicit and MUST NOT be generalized to
  remote or multi-user deployments.
- **FR-011 — Agent-independent interfaces**: Definition management and runtime use MUST work
  without a specific AI model, MCP client, agent framework or note application. SilverBullet MAY
  consume the server but MUST NOT define its semantics. Definitions and state MUST remain usable
  across independent sessions, and all acceptance interactions MUST be exercisable without a
  live AI model.
- **FR-012 — Structured outcomes and evidence**: Significant operations MUST return traceable
  identities, trusted workspace and SystemId where applicable, status and evidence appropriate
  to their boundary. Transport, parsing, semantic,
  authorization, conflict, unsupported-capability and infrastructure outcomes MUST remain
  distinguishable. Audit evidence MUST preserve the proposal, evaluated versions, trusted
  authorization and committed or refused outcome as applicable, without exposing credentials or
  unnecessary sensitive information. Old evidence MUST NOT be relabeled as checked under a newer
  verifier or trust policy.
  Published result schemas MUST require stage-specific subject and evidence fields and reject
  contradictory status/error combinations. Runtime checks MUST bind projections to authoritative
  reports or stored publication receipts; schema shape alone MUST NOT establish proof or authority.
- **FR-013 — Failure and retry recovery**: A refusal or failure MUST NOT leave a partial
  domain commitment or activation. After an uncertain commitment acknowledgment, the system MUST
  establish the original operation's outcome before attempting another mutation. Conflicts MUST
  follow Core's re-evaluation requirements. Recovery MUST NOT duplicate a transition merely
  because its acknowledgment was lost. Recovering one system MUST NOT reset, overwrite or
  reinterpret another system's active definition, state or history. Activation recovery MUST use
  its atomic host receipt, transition recovery its original Core bundle, and creation recovery its
  reserved SystemId and Core creation result; these paths MUST NOT be conflated.
- **FR-014 — Explicit capability gaps**: Unsupported requirements MUST be recorded in
  `SEMANTIC_GAPS.md` with required capability, exact release, attempted public interface and
  approach, limitation category, reproducible evidence, impact, severity, proposed upstream
  resolution and interim behavior status. Blocking gaps MUST remain visible in specifications,
  acceptance evidence and release decisions. No gap may be hidden by a local semantic substitute,
  reduced validation or false success.
- **FR-015 — Deterministic admitted behavior**: Given the same admitted behavior, state,
  explicit inputs, trusted context, history evidence and applicable versions, the server MUST
  preserve Core's deterministic result. Hidden clocks, randomness, ordering or context MUST NOT
  alter semantic definitions. Identity and equivalence claims MUST include all relevant release
  and composition dependencies; they MUST NOT rely on ModelHash alone.
- **FR-016 — External effect boundaries**: Durable external command intents MUST remain
  distinguishable from completed external work. Speculative evaluation or uncommitted requests
  MUST NOT trigger external business I/O. External results may enter through explicitly modeled
  inputs. No scheduler, worker execution or exactly-once external-delivery guarantee is implied.

### Key Entities *(include if feature involves data)*

- **Behavior System**: A deployment and state boundary within a trusted workspace, with a stable
  SystemId independent of BehaviorHash and model-version identities. It has its own active
  definition, Core Store, genesis, state, history, concurrency boundary and authorization scope.
  Models are composable building blocks within a system; a model is not a system identity.
- **Authoring Proposal**: Structured input with a stable ProposalId, immutable numbered revisions,
  an explicit edit base and optional parent DefinitionId, plus separate authoring metadata;
  neither admission nor persistence makes it an active deployment.
- **Canonical Model Definition**: An authoritative normalized model document and applicable
  ModelHash; whether it preserves complete re-authoring information is an investigated property.
- **Generated Behavior Module**: Admitted behavior produced through authoritative lowering,
  including its BehaviorHash, SchemaHash, declarations and capabilities.
- **Lowering Receipt**: Evidence relating participating model definitions to generated behavior,
  interpreted with exact release versions and composition context.
- **Validation or Verification Result**: A classified outcome for an exact subject, with
  assumptions, obligations, coverage, toolchain and evidence identity where applicable.
- **Deployment**: An authorized binding of a definition and its artifacts to one system's
  persistent active reference, including trusted workspace, SystemId, exact BehaviorHash,
  applicable policy identity and version,
  authorization evidence, history anchor and conditions that permitted activation.
- **Delegated Activation Policy**: A separate, versioned host-policy object outside the
  agent-authored model. Trusted host authority controls its versions and permitted workspaces,
  systems, operations, model capabilities, permissions, effects, state changes, migrations and
  applicable evidence and
  deployment requirements. The agent cannot modify or expand it; historical policy versions
  referenced by activation evidence remain recoverable.
- **Domain State Snapshot**: Authoritative records in one system's Core Store under an exact
  behavior and schema identity at a consistent position in that system's history.
- **Transition Record**: Durable evidence of an authoritative committed change within one
  SystemId and Core Store, with the context required for recovery and replay; an evaluated
  proposal is a distinct artifact.
- **Trusted Request Context**: Host-established identity, workspace, system and operation scope
  and authority used independently of client-supplied claims.
- **Evolution or Migration Artifact**: An immutable supported change description and evidence
  needed to evolve state or interpret history across deployments.
- **Capability Gap**: An evidence-backed limitation of a required public capability, its impact
  and its upstream or interim disposition.

### Scope and Boundaries

The first delivery MUST demonstrate one complete persistent system using at least one existing
Behavior Model: discover, author, save, inspect, lower, validate, authorize activation, invoke,
recover after restart and propose a subsequent revision. It MUST also evaluate composition with
another existing model family. A second system in the same workspace MUST establish isolation
through simultaneous use, independent activation, restart/recovery and unauthorized access tests;
it does not require a second complete authoring demonstration. Examples and public interfaces
MUST remain domain-neutral.

The demonstration uses generic records with at least one required attribute, at least two
lifecycle states, one permitted change, one refused change, a recorded outcome and recoverable
history. These are acceptance needs; the selected public models must establish their semantics.

The initial delivery does not require every model family, a graphical editor, a new programming
language, generated application source, Git-based ordinary versioning, a new workflow scheduler,
a generic plugin platform, arbitrary external effects or universal migration support. It MUST NOT
reimplement Behavior Models or Core or grant agents unrestricted deployment authority.

The first release explicitly excludes references, atomic transactions, orchestration and implicit
dependencies across systems, as well as multi-user tenancy and distributed coordination.
Models needing shared atomic semantics MUST compose within one Behavior module in one system.
System management is limited to the lifecycle operations needed to establish the identity and
isolation contract; a general system-management framework is outside scope.

The server owns structured client interaction, artifact storage, deployment coordination, trusted
request context and integration boundaries. Behavior Models own model normalization, composition
and lowering. Behavior Core owns admitted semantics, evaluation, verification, persistence
contracts and replay. Required upstream work MUST be assigned to its authoritative layer.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least one system meeting the minimum generic-record scope completes the full
  declared journey from structured definition to active use and post-restart revision without
  generating or maintaining executable application source code.
- **SC-002**: Every supported positive and negative acceptance example for the demonstrated system
  produces the declared allowed or refused outcome, with zero independently invented business
  rules needed to explain the results.
- **SC-003**: At least two systems in one workspace are used simultaneously across at least two
  independent client sessions, one normal restart and one abrupt stop followed by recovery.
  Zero acknowledged durable changes or required historical artifacts are lost; each system keeps
  its own SystemId, active definition, state and history. Recovering one system causes zero
  resets, overwrites or reinterpretations of the other's state or history.
- **SC-004**: An unchanged persisted definition completes at least two reconstruction and lowering
  cycles under identical declared versions and composition context while preserving relevant
  model and generated behavior identities and meaning.
- **SC-005**: At least one semantic revision proposed after restart preserves SystemId and
  receives the version identities required by the governing contracts. It leaves the deployment
  unchanged before activation, changes only the target system's active definition on activation
  and preserves interpretation of all demonstrated historical transitions. The second system's
  active definition, mutable state and history remain unchanged by that activation.
- **SC-006**: All demonstrated save-only, admission-only, verification-only, unapproved
  out-of-delegation and agent-initiated policy-change attempts leave the active deployment and
  delegated authority unchanged. At least one unattended activation within an explicit delegation succeeds, and every
  successful activation retains its exact behavior identity, policy version, authorization and
  history anchor. An exact-version approval never authorizes a different version; all required
  evidence and current-state conditions remain mandatory. Tests MUST include denied access to
  another system for each exposed protected operation; shared workspace membership or immutable
  artifacts grant no additional authority.
- **SC-007**: At least one conflicting concurrent-operation case, one competing activation case,
  one delegation-change race and one lost-acknowledgment case resolve with zero partial
  publications, unauthorized activations or duplicate domain transitions. Unsupported migration
  and invalid resulting-state cases cause no change.
- **SC-008**: Every demonstrated validation and verification result distinguishes its actual
  status and coverage; zero unsupported, inconclusive, incomplete or timed-out results are
  presented as successful proof or authorization.
- **SC-009**: Composition is evaluated using at least two existing model families, with evidence
  for a supported combination and a conflicting or unsupported case, or an explicit documented
  public-capability gap preventing the corresponding demonstration.
- **SC-010**: All seven research questions have reproducible findings classified as supported,
  limited or blocked under exact declared releases, and every discovered blocking gap is visible
  in the gap register and affected acceptance results.
- **SC-011**: The complete demonstrated journey can be repeated through deterministic client
  interactions without a live AI model or a note-taking application, and the definitions and
  state remain usable outside the session that authored them.

### Acceptance Interpretation

A documented blocking gap is a valid experimental finding. It MUST NOT satisfy a delivery
criterion that requires a demonstrated capability. Affected criteria remain unmet until the
public capability exists and its required evidence is established. Successful examples establish
only their documented coverage and MUST NOT be presented as a stronger formal safety guarantee.

Conformance evidence MUST compare results against the pinned public Behavior implementation.
Expected outcomes MUST NOT simply be copied from the MCP implementation under test. Claimed
semantic equivalence requires positive, negative and unsupported cases.

## Assumptions

- The first supported host environment is explicitly bounded to one local user managing multiple
  independent systems per workspace. This does not require multi-user tenancy or distributed
  coordination. Trusted host
  context provides identity and a separate delegated activation policy; clients remain untrusted
  authors and callers. Prior delegation permits unattended explicit activation only within its
  capability, permission, effect, state-change and migration limits. Workspace access alone grants
  no activation authority. Trusted exact-version approval is required for exceptions outside the
  delegation, and agents cannot change the delegation policy. Remote and multi-user deployment
  support requires separate trust and isolation work.
- Each system's stable SystemId is distinct from its BehaviorHash. Independent Core Stores and
  mutable deployment references enforce system isolation. Shared immutable content-addressed
  artifacts are permitted; references, transactions, orchestration and implicit dependencies
  across systems are outside the first release.
- Existing Behavior Models are candidates for the first demonstrated system. The first family
  and the second composition family are selected from evidence about supported public releases
  during planning rather than invented in this specification.
- The investigation considers the StateMachine, RequestFlow, Approval and WorkQueue families
  named in the request. Their availability and supported interfaces must be checked against the
  pinned release; listing a family does not assert complete declarative authoring support.
- Canonical documents are preferred candidates, not assumed complete authoring formats. The
  authoring representation decision follows the required reconstruction and identity evidence.
- The constitution's Behavior IR `v0.14.0` and Core `v0.15.0` reference links are reviewed baselines,
  not proof of an installed or compatible dependency pair. The actual public package and its
  associated Core release MUST be explicitly pinned and checked before implementation claims
  or conformance acceptance rely on them.
- Storage technology and integration design are planning decisions constrained by the applicable
  public persistence contract. An in-memory demonstration cannot satisfy durable recovery.
- Ordinary agent or note-document edits are proposals or projections. They do not bypass explicit
  authorization, activation or Core-governed state commitment.
- Dates and any other semantic context required by a model are explicit inputs or supported
  trusted context; no implicit environment information supplies missing semantic content.
- External adapter execution, scheduling and arbitrary business I/O are outside initial delivery.
  If a selected model produces intents, their requested status and boundaries remain explicit.
- Natural-language proposals may vary. Determinism claims apply to admitted behavior with its
  declared state, inputs, context, evidence and versions.

## Research Questions

- **RQ-001 — Canonical authoring**: Can an existing canonical model document reconstruct a
  model instance, including referenced types, conditions and effects, through supported public
  interfaces? Record any information omitted from the stored document.
- **RQ-002 — Round-trip identity**: Can a persisted definition be loaded, inspected, modified
  and lowered without unintended semantic changes? Establish which identities depend on the
  model, composed declarations, release versions and broader composition context.
- **RQ-003 — Model discovery**: Can model configuration schemas and capabilities be derived
  from authoritative public interfaces, or does general discovery require upstream metadata?
- **RQ-004 — Composition**: Can one declarative authoring mechanism support multiple existing
  models within a single system without model-specific handling in the MCP host? Distinguish
  integration glue required
  by a public contract from any forbidden independent semantic implementation.
- **RQ-005 — Persistence**: Which durable responsibilities belong to the host, and which
  guarantees are established by Core's supported store, commitment and history contracts?
  Establish how supported interfaces preserve a separate Core Store and recovery boundary for
  each SystemId without duplicating immutable artifacts.
- **RQ-006 — Evolution**: How can an agent propose a revision while preserving immutable
  version identities, a stable SystemId, explicit active deployment boundaries, current-state
  validity and history?
- **RQ-007 — Scope boundaries**: Which missing capabilities belong upstream and which belong
  to the consumer? Classify each finding and record its public-interface evidence and impact.
