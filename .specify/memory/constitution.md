<!--
Sync Impact Report — temporary review material; remove before committing this constitution.
Version change: Unversioned scaffold → 1.0.0 (initial project constitution).
Modified principles: None; the scaffold contained no adopted project principles.
Added principles:
  I. Semantic Authority Is Non-Negotiable
  II. Models Are Data, Not Generated Programs
  III. Canonical Round-Trip Must Be Demonstrated
  IV. Immutable Definitions, Explicit Activation
  V. Verification Claims Must Be Exact and Honest
  VI. Core Owns State Transitions
  VII. Persistence Is a Host Responsibility, Not a Semantic Extension
  VIII. Agents Are Untrusted Authors and Callers
  IX. MCP Is a Transport, Not a Second Behavior Language
  X. External Effects Remain External
  XI. Evolution Must Preserve Historical Meaning
  XII. Dependency Boundaries Are Enforced
  XIII. Missing Capabilities Are First-Class Results
  XIV. Test-First and Evidence-Driven Development
  XV. Determinism, Reproducibility and Audit
  XVI. Simplicity and Narrow Generalization
Added sections: Mission; Repository Architecture Rules; Development Workflow;
  Required Quality Gates; Reference Authority and Compatibility; Final Principle.
Core Principles and Governance populated from the supplied draft.
Removed sections: None; unfilled scaffold placeholders and example comments replaced.
Follow-up TODOs: None. Supplied Proposed status and ratification date preserved.
Dependent templates and commands were not amended by this constitution update.
-->

# Behavior MCP Constitution

**Project:** behavior-mcp

**Status:** Proposed

## Mission

Behavior MCP enables AI agents and other MCP clients to create, inspect, validate, persist,
evolve and use Behavior-based systems through structured data rather than generated
application source code.

The server is a consumer of Behavior IR. It provides agent-facing interfaces, artifact
management, deployment coordination and persistence integration.

**Behavior MCP does not define what a Behavior program means.**

Its success is measured by whether agents can create and use real, persistent, verifiable
systems while preserving the guarantees and architectural boundaries of Behavior IR.

The project MUST prefer discovering missing general capabilities in Behavior IR over
implementing parallel semantics locally.

## Core Principles

### I. Semantic Authority Is Non-Negotiable

**Behavior Core is the sole authority for the meaning of admitted Behavior IR. Behavior Models
are the sole authority for their model-specific normalization, composition and lowering.**

Behavior MCP MUST NOT independently implement:

- Behavior expression semantics or type checking.
- State-machine, approval, request-flow or work-queue semantics.
- Behavioral invariants, transition evaluation or reference integrity.
- Semantic hashing, canonicalization or verification.
- Core persistence, conflict detection or replay semantics.

All semantic decisions MUST use supported public interfaces of the pinned Behavior release.

The MCP host MAY enforce additional operational restrictions, such as access control or
resource limits. Such restrictions MUST NOT be represented as Behavior semantic guarantees.

When a requirement cannot be represented faithfully through the supported Behavior
interfaces, the project MUST report the gap and preserve the limitation.

**A simpler implementation is never justification for weakening semantics.**

### II. Models Are Data, Not Generated Programs

Behavior MCP MUST enable model authoring without requiring agents to generate or maintain
executable application source code.

The project MUST investigate the existing canonical Behavior Model documents as the
preferred authoring and persistence representation.

A new model-description format MUST NOT be introduced without documenting why existing
representations are insufficient.

Any additional representation MUST have a defined relationship to the authoritative model
documents and MUST NOT independently define model semantics.

Executable Python, Rust, shell commands or dynamically evaluated expressions MUST NOT be
accepted as model definitions from MCP clients.

Structured conditions and effects MUST be translated into supported typed Behavior
expressions and checked by the authoritative implementation.

The server MUST NOT hand-author low-level Wire IR to bypass an unavailable or incompatible
public model-authoring capability.

The project MUST distinguish:

- An editable authoring proposal.
- A canonical model definition.
- A generated Behavior IR module.
- A lowering receipt.
- An approved and active deployment.
- Persistent domain state and history.

These artifacts have different meanings and MUST NOT be treated as interchangeable.

### III. Canonical Round-Trip Must Be Demonstrated

An existing canonical model document MUST NOT be assumed to be a complete, editable
authoring format merely because it can be serialized.

Before claiming round-trip support, the project MUST demonstrate that a stored definition
can be reconstructed, inspected, modified and lowered through authoritative interfaces.

An unchanged round-trip MUST preserve the relevant model identity, generated behavior
identity and semantic meaning under the exact declared dependency versions and composition
context.

The project MUST NOT assume that a ModelHash alone determines the entire BehaviorHash
independently of other declarations, composed models and toolchain versions.

If canonical documents omit information needed for safe re-authoring, that limitation MUST
be recorded explicitly.

The project MAY retain a separate original authoring representation when necessary to
preserve information. It MUST NOT silently reconstruct missing semantic content by guessing.

A failed round-trip is a capability gap, not permission to introduce an unofficial interpreter.

### IV. Immutable Definitions, Explicit Activation

An admitted model or Behavior module MUST be treated as immutable.

Changes MUST create new semantic versions or identities as required by Behavior's existing
contracts.

The server MUST preserve the exact artifacts needed to interpret historical behavior.

**Model creation, validation, verification, authorization and activation are separate
operations.**

No model definition becomes active merely because:

- An agent proposed it.
- A document was saved.
- Model admission succeeded.
- A lowering receipt exists.
- A hash matches.
- An automated test passed.

Activation MUST be an explicit, authorized operation.

The active-version reference MUST be persistent and changed atomically under the host's
concurrency contract.

The server MUST preserve the relationship between the model definition, its ModelHash,
generated BehaviorHash, SchemaHash, lowering receipt and relevant release versions.

An old active version MUST NOT be silently replaced by a newer definition.

### V. Verification Claims Must Be Exact and Honest

Behavior MCP MUST distinguish:

1. Syntactically well-formed input.
2. Valid model configuration.
3. Successfully lowered and admitted Behavior IR.
4. Verified properties under stated assumptions.
5. Authorized deployment.
6. Successful runtime transition.

These outcomes MUST NOT be conflated.

Verification results MUST retain the exact subject, toolchain, semantic profile,
obligations, assumptions and evidence identity required by Behavior.

`INCONCLUSIVE`, `UNSUPPORTED`, timeouts and incomplete proof coverage MUST NOT be
represented as successful verification.

A valid model MUST NOT be described as safe solely because it was admitted.

The server MUST NOT introduce proof assumptions that exceed the guarantees established
by Core.

A hash establishes identity, not approval, trust or proof validity.

Missing or invalid evidence MUST fail closed wherever the applicable activation or
execution policy requires that evidence.

### VI. Core Owns State Transitions

All persistent domain-state changes MUST occur through supported Behavior Core
transitions, migrations and commit operations.

MCP clients MUST NOT directly modify authoritative domain-state records.

The server MUST NOT emulate a transition by editing database rows or structured documents.

Evaluation and commit MUST remain distinct operations.

Every committed transition MUST preserve Core's requirements for:

- Exact behavior and schema identity.
- Consistent source snapshots.
- Complete resulting-state validity.
- Atomic compare-and-set.
- Conflict handling and re-evaluation.
- Durable transition records.
- Replay and historical interpretation.

A refusal MUST NOT produce a partial commit.

A retry after an uncertain commit outcome MUST establish whether the original operation
committed before attempting any new mutation. It MUST NOT turn an ambiguous acknowledgment
into a duplicate transition.

### VII. Persistence Is a Host Responsibility, Not a Semantic Extension

Behavior MCP MUST provide durable storage without redefining Behavior's persistence contract.

The server MAY select an appropriate storage technology, but that choice MUST NOT change
behavioral meaning.

A persistent backend MUST satisfy the applicable Core Backend contract, including atomic
publication, consistent historical reads, concurrency control, durable commits and recovery.

An in-memory backend MAY be used for isolated tests and demonstrations. It MUST NOT be
represented as crash-durable production storage.

All authoritative artifacts and committed state MUST survive supported restart and
recovery scenarios.

Caches, search indexes, Markdown projections and other derived views MUST be reconstructible
from authoritative artifacts and state.

A user-editable document is a proposal or projection unless it is explicitly governed by
a compatible authoritative storage protocol.

The server MUST NOT treat arbitrary file modifications as committed Behavior transitions.

### VIII. Agents Are Untrusted Authors and Callers

Every MCP request MUST be treated as untrusted input, regardless of which agent or client
generated it.

All requests MUST pass through structured schema parsing, applicable model admission and
the relevant authorization boundaries.

Invalid requests MUST produce structured errors, not guessed repairs.

Client-provided actor names, roles, permissions, approval flags and deployment claims MUST
NOT establish authority.

Identity, workspace scope and privileged context MUST come from the trusted host environment.

The server MUST enforce authorization independently of any natural-language instruction
received from an agent.

An agent MUST NOT be able to grant itself permissions by creating or modifying a
Behavior model.

Definition approval and activation MUST have an explicit trusted authority.

The initial implementation MAY support a clearly bounded local single-user environment.
Its trust assumptions MUST be documented; they MUST NOT be silently generalized to remote
or multi-user deployments.

### IX. MCP Is a Transport, Not a Second Behavior Language

MCP tools MUST expose supported capabilities rather than implement their semantics.

The MCP interface SHOULD be generic across model types wherever their underlying
contracts permit it.

Model-specific configuration and diagnostics SHOULD originate from authoritative
model descriptions.

Public tools MUST make important distinctions explicit, particularly:

- Proposing versus activating definitions.
- Reading versus changing state.
- Evaluating versus committing.
- Admission versus verification.
- Requests for external work versus completed external work.

MCP tool descriptions, names and JSON schemas MUST NOT promise capabilities that the
pinned Behavior release does not provide.

Tool outputs MUST include enough structured identity and status information to avoid
confusing proposals, current state and historical results.

Transport failures, semantic refusals, authorization failures, conflicts and infrastructure
failures MUST remain distinguishable.

MCP clients MUST NOT receive unrestricted filesystem, database or process-execution
authority merely to author Behavior systems.

### X. External Effects Remain External

Behavior Core may produce durable command intents. It does not execute external business I/O.

Behavior MCP MUST preserve this separation.

External adapters own execution, credentials, delivery, retries and observation of results.

The server MUST NOT execute a physical side effect during speculative evaluation or
before the associated request is durably committed.

The server MUST NOT claim exactly-once external execution unless that guarantee is
independently established by the relevant adapter and target system.

External outcomes MUST re-enter Behavior through explicitly modeled inputs or transitions.

`WorkQueue` MUST NOT be presented as a scheduler or worker executor by itself.

Any external effect capability MUST declare its authorization requirements, supported
failure behavior and recovery responsibilities.

### XI. Evolution Must Preserve Historical Meaning

A revised model definition MUST NOT silently reinterpret existing persisted state or
historical decisions.

The server MUST distinguish behavior-only changes from schema changes.

Schema evolution MUST use supported migration mechanisms where required.

The server MUST NOT use a compatible-looking field name, entity name or hash as a substitute
for the actual compatibility checks.

Activation against existing state MUST establish all required current-state validity and
deployment conditions.

All writers and migration paths MUST be covered by the relevant coordination boundary.
A check performed before an uncontrolled intervening write MUST NOT authorize activation.

The historical behavior definitions and migration artifacts needed for replay MUST remain
recoverable.

Unsupported migrations or unestablished deployment conditions MUST block activation rather
than trigger an automatic best-effort conversion.

### XII. Dependency Boundaries Are Enforced

Behavior MCP is a downstream consumer of Behavior IR.

It MUST use a pinned, released and publicly supported Behavior interface.

The committed dependency graph MUST NOT rely on:

- Private Core crates or internal modules.
- Undocumented Python or Rust implementation details.
- Copied Behavior semantic implementations.
- Repository checkout paths as production dependencies.
- Untracked dependency overrides.
- Release artifacts silently rebuilt against a different Core version.

The server MUST verify that its installed Behavior package and Core release match their
declared dependency identities.

Required CI and release gates MUST use the declared dependency graph.

Local development overrides MAY be used for isolated upstream experimentation but MUST NOT
affect official conformance, release verification or published artifacts.

Upstream changes MUST be integrated through explicit dependency updates and conformance testing.

**When the public dependency cannot support a needed capability, the project MUST stop at
that boundary and report the gap.**

### XIII. Missing Capabilities Are First-Class Results

Behavior MCP is an experiment in how broadly Behavior IR can be used through agent-native
interfaces.

Discovering an upstream limitation is a valid and valuable outcome.

The project MUST maintain `SEMANTIC_GAPS.md` for requirements that cannot be met faithfully
through supported Behavior interfaces.

Each gap MUST identify:

- The required behavior or capability.
- The exact Behavior release used.
- The relevant public interface and attempted approach.
- Whether the limitation is semantic, authoring-related, verification-related or operational.
- Reproducible evidence.
- Impact and severity.
- Any proposed upstream resolution.
- The status of interim behavior, if any.

Gaps MUST NOT be hidden behind silent fallbacks, reduced validation, implicit host-side
rules or false success responses.

A host-side workaround MAY be considered only when it does not claim to replace missing
Behavior semantics and its risks and trusted assumptions have been explicitly reviewed.

Unresolved blocking gaps MUST remain visible in specifications, acceptance results and
release decisions.

### XIV. Test-First and Evidence-Driven Development

**Test-first development is mandatory.**

Tests MUST be written and observed to fail before implementing the behavior that makes
them pass.

A bug fix MUST begin with a reproducible failing test.

The project MUST maintain deterministic tests for:

- MCP request parsing and validation.
- Malformed, incomplete and adversarial inputs.
- Model-authoring and lowering boundaries.
- Canonical model round-trips.
- Model and Behavior identity preservation.
- Generated capabilities and their contracts.
- Semantic refusals and unsupported definitions.
- Authorization and isolation.
- Persistence across restart.
- Conflicting concurrent operations.
- Lost acknowledgments and retry recovery.
- Migration and activation boundaries.
- Replay using historical artifacts.

All tests of MCP behavior MUST work without a live AI model.

Conformance MUST compare results against the pinned public Behavior implementation.
Expected outcomes MUST NOT simply be copied from the implementation under test.

For operations that claim semantic equivalence, tests MUST cover positive, negative and
unsupported cases.

Where appropriate, property-based and mutation tests SHOULD complement fixed examples.

Tests MUST NOT substitute empirical success for a formal proof or certified guarantee.

A release MUST NOT claim a safety property stronger than its supporting evidence.

### XV. Determinism, Reproducibility and Audit

Given the same admitted behavior, persisted state, explicit inputs, trusted context,
history evidence and applicable versions, the server MUST preserve Behavior Core's
deterministic semantic result.

The agent's natural-language proposals themselves are not required to be deterministic.
Only admitted and committed behavior receives Core's semantic guarantees.

The server MUST NOT introduce hidden clocks, randomness, environment-dependent ordering
or implicit context into semantic definitions.

Every meaningful operation MUST produce traceable structured evidence appropriate to
its boundary.

Audit records SHOULD establish:

- What was proposed.
- Which artifact and version were evaluated.
- Which validation or verification result was obtained.
- Who or what authorized activation or execution.
- Which state and history position were used.
- What was committed or refused.
- Which external work was requested.

Logs and diagnostic artifacts MUST NOT expose credentials, private keys or unnecessary
sensitive data.

Historical evidence MUST NOT be rewritten to claim that it was checked under a newer
verifier or trust policy.

### XVI. Simplicity and Narrow Generalization

Behavior MCP MUST remain an integration layer.

The project MUST begin with the smallest complete vertical capability that demonstrates
the intended architecture.

Generalization MUST follow demonstrated consumer needs and authoritative Behavior contracts.

The server MUST NOT introduce:

- A separate rule engine.
- A second model-lowering implementation.
- A general-purpose scripting runtime.
- A new workflow scheduler without an explicit separate requirement.
- A universal data-model framework.
- A generic plugin platform merely to support one integration.
- A new canonical format without demonstrating the need.

New abstractions MUST be justified by actual repetition, a stable contract or a demonstrated
interoperability requirement.

A feature that belongs in Behavior IR MUST be proposed upstream rather than implemented
as a permanent MCP-specific semantic extension.

## Repository Architecture Rules

The intended dependency direction is:

```text
AI agent / MCP client / SilverBullet
                |
                v
          behavior-mcp
                |
        Public Behavior API
                |
                v
           behavior-ir
       (models and bindings)
                |
                v
         behavior-ir-core
       (semantic authority)
```

Behavior MCP is responsible for MCP interfaces, application-level artifact storage,
deployment coordination, trusted request context and integration adapters.

Behavior IR is responsible for model authoring semantics, model identity, normalization,
composition and lowering.

Behavior Core is responsible for the admitted behavior semantics, evaluation, verification,
persistence contracts and replay.

The dependency direction MUST NOT be reversed.

Cross-repository changes MUST be assigned to their authoritative layer.

## Development Workflow

Work MUST follow the Spec Kit lifecycle:

**Specify → Clarify → Plan → Tasks → Implement → Verify**

Every implementation plan MUST include a Constitution Check describing:

1. Which public Behavior capabilities are used.
2. Whether new semantics are being introduced, and why they belong in this repository.
3. Which persistent and authorization boundaries are affected.
4. What semantic and recovery guarantees are claimed.
5. Which deterministic and conformance tests establish acceptance.
6. Which upstream gaps remain.
7. Whether a simpler solution using existing Behavior APIs was considered.

Implementation MUST NOT begin from an unexamined assumption that an internal Behavior
representation is a supported public API.

## Required Quality Gates

The repository MUST provide one documented, reproducible quality-gate command used
consistently by CI and release checks.

A change MUST NOT merge unless:

- All applicable tests pass.
- Format, lint and type checks pass.
- Dependency versions and public API boundaries are verified.
- No private Behavior dependency is introduced.
- Model round-trip and release conformance fixtures pass where affected.
- Restart and persistence tests pass where affected.
- Authorization and failure-path tests pass where affected.
- New or changed gaps are documented.
- Verification claims are supported by their recorded evidence.
- The Constitution Check has been reviewed.

A passing unit test suite alone MUST NOT authorize a release containing untested
persistent-state or deployment changes.

## Reference Authority and Compatibility

The authoritative upstream references are:

**Behavior IR ecosystem**

- [Behavior IR Constitution](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/.specify/memory/constitution.md)
- [Behavior Models](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/models/README.md)
- [Behavior consumer guidance](https://github.com/kallistoteles/behavior-ir/blob/v0.14.0/skills/README.md)

**Behavior Core**

- [Core Constitution](https://github.com/kallistoteles/behavior-ir-core/blob/v0.15.0/.specify/memory/constitution.md)
- [First Principles](https://github.com/kallistoteles/behavior-ir-core/blob/v0.15.0/PRINCIPLES.md)
- [Architecture and dependency boundaries](https://github.com/kallistoteles/behavior-ir-core/blob/v0.15.0/ARCHITECTURE.md)
- [Persistence contract](https://github.com/kallistoteles/behavior-ir-core/blob/v0.15.0/docs/persistence.md)
- [Trusted governance](https://github.com/kallistoteles/behavior-ir-core/blob/v0.15.0/docs/governance.md)
- [Durable command intents](https://github.com/kallistoteles/behavior-ir-core/blob/v0.15.0/docs/commands.md)
- [Versioning and compatibility](https://github.com/kallistoteles/behavior-ir-core/blob/v0.15.0/docs/versioning.md)

These links identify the baseline reviewed when this constitution was proposed.

The project's actual supported behavior MUST be determined from its explicitly pinned
Behavior release and the associated Core Release.

Newer upstream documentation MUST NOT silently override the contracts of the pinned release.

When an upstream version changes, compatibility and applicable assumptions MUST be
reviewed explicitly.

If local guidance conflicts with the semantic contract of the pinned Behavior release,
the upstream contract governs the actual behavior. This constitution MUST be amended or
the conflicting feature refused.

## Governance

This constitution is binding on implementation, tests, integrations and release decisions.

Project specifications and implementation plans MUST conform to it.

Exceptions MUST NOT be silently introduced through feature work.

An exception request MUST identify the violated principle, reason, risks, alternatives,
affected guarantees and explicit reviewer approval. An exception cannot authorize
misrepresentation of upstream semantics or unsupported verification claims.

Amendments require a documented rationale, migration or compatibility impact, and updated
quality gates where relevant.

Constitution versions follow semantic versioning:

- **MAJOR:** A principle is removed, weakened or redefined.
- **MINOR:** A new principle or material obligation is added.
- **PATCH:** Clarification without changing obligations.

Compliance MUST be checked during planning, implementation review and release acceptance.

## Final Principle

**Behavior MCP makes verified behavior accessible to agents. It does not make agents the
authority over behavior.**

A model may be proposed by an AI, represented as data, persisted by an MCP host and invoked
through an MCP client.

Its meaning must still come exclusively from Behavior IR.

Its execution must still respect Behavior Core.

Its activation must still be authorized.

Its history must still be reproducible.

And when those guarantees cannot be established, the system must report the limitation
rather than pretend they hold.

**Version**: 1.0.0 | **Ratified**: 2026-10-26 | **Last Amended**: 2026-10-26
