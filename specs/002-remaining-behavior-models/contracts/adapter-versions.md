# Immutable Adapter Versions and Incremental Delivery

The authoring format remains `behavior-mcp.authoring.v2` and profile `structured-models.v2`.
Every v2 proposal MUST additionally name an exact `adapter_version`. There is no `latest`, default
upgrade or source-hash exemption. V1 input/context and its version `1` remain unchanged.

| Version | First supported checkpoint | Newly delivered authoring | Frozen packaged implementation |
| --- | --- | --- | --- |
| 2.0.0 | T033–T034, Approval MVP | RequestFlow, StateMachine, fixed lifecycle factories and Approval | `src/behavior_mcp/adapter_versions/v2_0_0.py` |
| 2.1.0 | T047–T048 | WorkQueue; retains previous capabilities | `src/behavior_mcp/adapter_versions/v2_1_0.py` |
| 2.2.0 | T056–T057 | FieldOwnership | `src/behavior_mcp/adapter_versions/v2_2_0.py` |
| 2.3.0 | T070–T072 | LifecycleDependency | `src/behavior_mcp/adapter_versions/v2_3_0.py` |

The matching `authoring-v2-<version>.schema.json` is frozen with each implementation. The aggregate
`authoring-v2.schema.json` is a design/discovery index, not a substitute for the selected version's
validator. The index may describe future checkpoints; it does not advertise them as delivered.
All four checkpoints are finalized and retained with their real workspace fixtures. Their original
schema titles include the word `draft`; those bytes remain frozen as part of the published
construction identity. Current support comes from the exact registry and acceptance evidence.

## Publication and retention

1. Develop a checkpoint's handler in trusted draft source and disposable test workspaces only.
   Such workspaces are not supported retained installations. Observe the intended failing tests
   before adding behavior, and complete the whole checkpoint's constructor/read/guard support.
2. Finalize the trusted handler in the versioned module and freeze its complete source closure,
   including fragment/type/read builders and release-specific schema bytes. Shared helper modules
   may be reused only if immutable and explicitly present in each version's closure manifest.
   If a helper must change, add a new versioned helper; do not edit one used by a published handler.
3. Register the exact `(profile, adapter_version)` in a fixed code-owned dispatch table in
   `adapters.py`. Package the handler, dependencies and schema in both wheel and source archive.
   `authoring_v2.py` may serve as a mutable development/facade module; a published handler must
   never import it, the mutable schema index or another mutable authoring helper.
4. Only after finalization advertise that version/family, permit supported activation and capture
   its retained workspace fixture. Later checkpoints add new modules instead of modifying those
   used by the earlier checkpoint. Editing a published version is a gate failure.
5. A proposal/revision uses its explicit input version; a stored proposal/definition uses its
   retained exact version and code/schema identities. Unknown versions or byte mismatches refuse
   reconstruction. Never rewrite contexts, try a newer handler or relax the identity comparison.
6. Code is loaded only from the installed trusted package. Source bytes or paths from a workspace,
   client, Git checkout or proof bundle cannot become executable adapter code. This is a finite
   compatibility table, not a plugin or runtime code-restoration mechanism.

This retains host translation code, not copies of Behavior model semantics. Every version still
calls the same declared public Behavior/Core release. Immutable Wire and historical evidence
remain independently recoverable for public Core replay.

## Required regression sequence

After T034, capture `tests/fixtures/adapter_versions/v2_0_0/`. Before and after adding 2.1.0, open
that exact workspace and inspect, discover, invoke/commit, recover, rebuild and revise using 2.0.0.
Repeat while adding 2.2.0 and 2.3.0, retaining fixtures for all earlier published checkpoints.
`tests/integration/test_incremental_adapter_retention.py` must use those retained workspaces,
not silently recreate them with the newest implementation. Compare source/schema closure hashes,
public semantic identities, active references, history and original evidence provenance.

Discovery exposes supported exact versions and schemas per family at each checkpoint. Host
policy must explicitly allow the selected version. To adopt a newer version, create an explicitly
versioned proposal/fork and request ordinary validation and authorized activation. It does not
replace an old active definition merely because equivalent behavior can be built with newer code.

An integration correction discovered after a checkpoint is frozen follows the same rule: publish
a new exact minor/patch version and its new fixed validator/dispatch entry, retaining all earlier
ones. General schema fields accept canonical `2.<minor>.<patch>` syntax (at most 32 characters),
but unknown/unpublished versions are refused by the installed availability check. This is not a
floating range grant: a policy entry and proposal still name one exact implementation version.
The four checkpoint versions above are the initially planned releases; no future version is
advertised or loaded merely because its string passes syntax validation.
