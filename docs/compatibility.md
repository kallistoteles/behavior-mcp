# Compatibility and Supported Boundaries

## Declared Releases

| Dependency | Identity |
| --- | --- |
| Behavior | 0.14.0, commit `1cba9e16ff73f927ae08e70a7bc74a6ca52355e4` |
| Released wheel | `behavior-0.14.0-cp313-abi3-manylinux_2_28_x86_64.whl` |
| Wheel SHA256 | `794d2dd5ddf8613c52f524a1b4b74c0246d86a5ea52414424ab89ef104e86513` |
| Core | 0.15.0, commit `6b93898a9375113f7a8946f23ab5535319b6f5d6` |
| Verifier / solver | 0.10.0 / Z3 4.16.0 |
| MCP SDK / types | 2.3.0 / 2.3.0 |
| Protocol modes | 2026-07-28; legacy 2025-11-25 |
| Initial platform | Linux x86_64, glibc >=2.28, Python >=3.13 |
| Nixpkgs | `293d6abedf0478e681a4dfcfcb35b30fc796a32f` |

`uv.lock` pins/hashes the Python graph; `flake.lock` pins the portable upstream Nix input. Startup
checks public runtime version identities and the installed bytes of every file from the
checksum-verified released Behavior wheel. Private binding imports, repository checkout overrides
and silently rebuilt release artifacts are rejected. Ruff and Z3 come from native Nix packages.

## Authoring Coverage

The host-owned `behavior-mcp.authoring.v1` / `scalar-models.v1` proposal supports RequestFlow and
StateMachine, at most two composed models, bounded explicit declarations, string payload/input
fields, enum status fields, literal/input/trusted-Actor initializers and fixed input-to-field
assignments. Enum cases use explicit ordered arrays. Actor has the fixed trusted `name: string`
declaration; the host supplies its identity and bootstrap seed. Public model constructors perform
normalization, type checking, ownership/composition and lowering.

The additional `behavior-mcp.authoring.v2` / `structured-models.v2` profile requires an exact
immutable adapter version:

| Model family | Supported v2 versions | First checkpoint |
| --- | --- | --- |
| RequestFlow, StateMachine | 2.0.0, 2.1.0, 2.2.0, 2.3.0 | retained v1 also supported |
| Approval | 2.0.0, 2.1.0, 2.2.0, 2.3.0 | decisions and public outcome reads |
| WorkQueue | 2.1.0, 2.2.0, 2.3.0 | all nine actions and public queue reads |
| FieldOwnership | 2.2.0, 2.3.0 | separate structural Safety policies |
| LifecycleDependency | 2.3.0 | traced guards, Safety certification and state validation |

Original handlers, helper/schema closures and real workspace fixtures are retained for every
checkpoint. Draft modules are not runtime handlers. Original source and exact construction context
are mandatory for re-authoring; stored Wire remains the historical Core interpretation artifact.

Generated action/read names, roles and types come from admitted public module export. Structured
conditions/effects use the closed [authoring subset](../specs/002-remaining-behavior-models/contracts/authoring.md).
Entity field projections require a State/query entity binding. Python object equality, scalar
attribute traversal and literal-left equality are refused rather than evaluated as Python booleans.
Fixed creation/removal/field/state action factories are supported through public APIs; client code,
command emission, schedulers and external adapters remain unsupported.

Safety requires the public Behavior release's exact Lean/leanchecker 4.30.0 package:
`/nix/store/7m5ds60a41w276hsx3rybv76x3609l6k-lean4-4.30.0` on x86_64-linux, with the matching
release-declared derivation. `flake.lock` pins the upstream proof input independently of nixpkgs.
Missing or substituted tools fail explicitly. Ordinary non-proof operations need no proof binaries.
The common gate requires real certification and fresh import checking without skips. A certificate
retains `Certified under assumptions`, `OrdinaryTransitions`, `Unestablished` initial validity,
and all upstream obligations/exclusions. No schema migration or external execution guarantee follows.

## Representations and History

Canonical model documents omit reconstructible expression/initializer bodies and have no complete
public model-document loader at this release. Retain complete original proposal/context separately
from canonical documents, ModelHash, generated Wire/BehaviorHash/SchemaHash and lowering receipts.
Wire re-admission does not restore model receipts. Fresh authoring reconstruction checks original
context and identities before activation. Historical Core replay admits the original generated
Wire and retains original model provenance; loading a receipt is no proof of lowering.

Same-schema revisions create new definition/behavior identities while preserving SystemId and
history. Activation validates current state under all relevant writers and updates one system's
pointer atomically with its authorization/audit receipt. Other systems keep separate Stores,
genesis/state/history and authorization. Content-addressed immutable blobs may be shared within
the workspace. Equal Core StoreIds never establish host system identity or permission.

Schema-changing activation is unsupported, including changes that look compatible by name.
Ordinary public upstream migrations exist; the independently governed prepared-migration Python
path has a conditional gap. No private bridge or direct state conversion is used. Cross-system
references, transactions, implicit dependencies and multi-user/distributed coordination are outside
this release. See [SEMANTIC_GAPS.md](../SEMANTIC_GAPS.md) for exact attempts and dispositions.

## Dependency Updates

Explicitly update both pins and provenance manifests, review the upstream semantic and public API
contracts, preserve historical artifacts/toolchain identities, and run the same complete quality
command. Changes require fresh canonical/retained-source round-trip fixtures, model/Core conformance,
authorization, activation, restart/crash, uncertain-outcome and historical replay evidence where
affected. An older artifact that cannot be interpreted faithfully stays unsupported; do not relabel
historical attestations as checked under a newer verifier or policy.
