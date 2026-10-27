# Local Operations

## Trusted Setup

The launcher and administrative configuration are trusted host inputs, supplied outside MCP.
Stdio metadata, roots, actor fields in domain input and natural-language instructions do not
establish authority. The first release assumes one trusted local OS user and one server process
per workspace. It makes no remote, multi-user or same-user process isolation claim.

Use absolute paths. The following examples describe configuration objects; replace the workspace
root with the same actual directory in both files and in the CLI arguments. Protect the files
with operator-controlled filesystem permissions such as mode 0600. Do not put credentials into
model definitions, metadata or audit messages.

`launcher.local.json`:

```json
{
  "workspace_root": "/absolute/workspace",
  "workspace_id": "workspace-1",
  "principal_id": "agent-session",
  "actor_id": "actor-1",
  "policy_id": "local-delegation"
}
```

`admin.local.json`:

```json
{
  "workspace_root": "/absolute/workspace",
  "workspace_id": "workspace-1",
  "issuer_id": "local-operator",
  "allowed_principals": ["agent-session"]
}
```

The administrator is independently trusted by this local launch/configuration boundary. A policy
or approval's issuer string must match that administrative identity; the string itself grants
nothing. An unrestricted same-user process can administer these files, so do not generalize this
arrangement to untrusted OS processes or remote callers.

Install the [example policy](../specs/001-agent-native-systems/contracts/example-host-policy.json)
with `behavior-mcp-admin install-policy` as shown in [README](../README.md). The closed schema and
[matching rules](../specs/001-agent-native-systems/contracts/host-policy.md) apply. Immutable policy
versions cannot be overwritten or rolled back silently. New versions use the same policy ID and
a higher positive integer version. Retain every referenced version.

## Delegated Activation

Workspace membership grants no operations. The policy must explicitly permit the operation,
system scope, adapter/release, model kinds/IDs, actual generated capabilities, typed effect forms,
status values/edges, state changes and applicable proof. All conditions combine with AND.

Creation has its own permission, capacity bound and fixed bootstrap Actor seed. It neither
activates the system nor extends system selectors or runtime permissions. Initial Core genesis
uses the explicitly configured `structural-none` profile. An empty host verification requirement
list means no mandatory formal proof; it never means safe or verified.

For a permitted candidate, unattended activation is an explicit MCP request with exact
DefinitionId, expected activation revision, Core HistoryRef and OperationId. The host freshly
reconstructs through public APIs, checks unchanged SchemaHash and validates complete current
state through Core while holding policy-before-system writer coordination. Active pointer,
activation record/audit and original request/result receipt publish atomically.

Out-of-delegation candidate exceptions require a separate exact-version approval through
`behavior-mcp-admin install-approval --workspace ... --trusted-config ... --document ...`.
Use the [approval schema](../specs/001-agent-native-systems/contracts/activation-approval.schema.json).
Approval binds principal, workspace/system, exact definition and behavior/schema hashes, policy
version, expected deployment revision and exact history. It cannot waive Core admission, required
proof, system/operation scope, migration refusal, external-command refusal or host-authority
restrictions. It does not grant permission to invoke newly activated capabilities.

Revoking an operation or capability stops new requests under that authority. Removing a candidate
construction bound does not rewrite an existing definition's Core meaning. Published historical
authorization/evidence retains its original policy and release labels.

## Tools and Clients

Use the [fixed tools](../specs/001-agent-native-systems/contracts/mcp.md), with an explicit SystemId
for every runtime operation. Two supported SDK modes are modern `2026-07-28` and legacy
`2025-11-25`. The SDK owns negotiation and JSON-RPC dispatch. Stdout carries protocol messages;
operational diagnostics belong on stderr.

Authoring enum cases are ordered arrays of `{name, value}`. Their order is explicit public Enum
declaration input. JSON object-member ordering cannot change admitted identities. Proposal edits
supply base ProposalId and expected revision; validation always freezes an exact source revision.

Evaluation returns an opaque token only for an actual Core ALLOW bundle. It does not commit.
Commit uses the same OperationId and token, rechecking current authority/deployment before Core
publishes. Domain actors and time come from the trusted host, and the original evaluation context
and bundle remain recorded. Clients cannot supply execution context, approval flags or paths.

Incoming frames are bounded to 1 MiB before JSON decoding, nesting to depth 32, and read pages to
50 by default/100 maximum. Verification has two bounded workers with fixed host profiles and
solver budgets. These are operational limits, not Behavior semantic guarantees.

The trusted launcher configuration may include an optional `limits` object:

```json
{
  "frame_bytes": 262144,
  "nesting_depth": 24,
  "page_default": 10,
  "page_max": 20,
  "verification_workers": 1,
  "verification_profiles": {
    "bounded": {"rlimit": 10000, "wall_clock_guard_ms": 2000}
  }
}
```

Only these keys and the existing `default`/`bounded` profile names are accepted. All values
are positive integers; booleans, unknown keys and increases beyond the published defaults/maxima
are rejected. Defaults remain 1048576 bytes, depth 32, pages 50/100 and two workers. A lower
`page_max` also lowers the implicit default page size when `page_default` is omitted. The default
profile's budgets are 20000000/60000; bounded uses 20000/5000 (resource limit/milliseconds).
Overrides may tighten either budget. Reports retain the actual public profile parameters, and
the server checks the returned parameters against the request. The process-wide verifier cap
remains two, with the configured per-server cap enforced as well. Each system still has one
coordinated writer. MCP arguments cannot change any host limit.

`definition_get` with a DefinitionId returns a `definition_inspection`: its original manifest
and source snapshot, separately identified module/context/lowering-receipt contents, and retained
definition-specific validation/verification evidence. Inspection checks artifact references and
preserves original report labels; it does not run a new proof or expose another system's policy
and activation evidence through shared artifacts.

## Storage and Recovery

```text
workspace/
  host.sqlite                  immutable artifacts/policies, reservations and request bindings
  systems/system-<id>.sqlite    one Core Store, active pointer, receipts and audit
  owner.lock                   one live MCP server owner
  policy.lock                  coordination shared with administrative processes
  locks/                       independent system writer boundaries
```

Core documents are stored unchanged. Indexes implement required historical lookup; Core supplies
identities and all transition decisions. SQLite uses DELETE journaling, EXTRA synchronization,
foreign keys, explicit transactions and durable directory entries. The supported local filesystem
must honor SQLite locking, atomic commit and fsync assumptions. Process-termination tests do not
certify hardware or physical power-loss behavior.

After a lost acknowledgment, inspect `operation_get` and reuse the original OperationId/request.
For transitions, the original Core bundle and atomic receipt establish whether the original
mutation committed. Never evaluate a replacement first. An unresolved operation blocks further
mutations of its system; other systems remain independent. Cancellation proves no rollback.

Activation retries resolve their own atomic host receipt before stale revision/history CAS. The
response returns the original receipt and separately observed current deployment, even after a
later activation. Current `operation_get` authority governs disclosure; a retry cannot create new
mutation authority. Any potentially fresh publication requires all current grants and checks.

`system_recover` distinguishes creation reservations, transition bundles and activation receipts.
On startup the server acquires the workspace owner lock before recovery. Historical replay uses
public Core data/behavior replay with retained exact modules and original provenance. Missing or
mismatched artifacts, invalid state, unavailable release context or missing system storage fail
closed. The server never recreates lost initialized history as an empty Store or converts state
by editing records. An absent database after a reservation is treated conservatively as unavailable
storage; it is not evidence that no original publication occurred. New creation first durably
prepares an empty backend and then publishes its reservation, so every visible reservation has
the initialized storage needed for safe recovery. A crash during preparation can leave an
unreferenced empty file; it contains no Core genesis/history and grants no system authority.

If Core creation published before its host completion receipt, `operation_get` reports unknown
until kind-specific recovery establishes the complete original outcome. A recovery attempt that
could publish keeps lost-acknowledgment failures uncertain; a metadata-only recovery read does
not claim a possible new mutation. Listings continue to show healthy authorized systems when
another is incomplete or unavailable, using `creating`/`recovery_required` with no unestablished
active pointer for the affected system. Listing never repairs storage.

For backups, stop the workspace owner and administrative writers, then copy the complete workspace
and its separate trusted configuration through the operator's storage process. Restore original
files together. This release provides no online backup, deletion, reset, garbage collection or
best-effort repair tool. Search/Markdown projections are derived views and cannot commit changes.

## Quality and Release Evidence

Run `nix develop --command ./scripts/check` for CI and release verification. It uses the declared
Python/Nix graph, including the pinned build backend and native Z3/Ruff. New behavior and bug fixes
begin with observed failing assertions. All tests work without an AI model or note application.

A complete result requires application/contract, authorization, public 45-case backend conformance,
physical crash, retry, isolation, revision and historical replay tests. Formal verification reports
retain their exact subject/profile/checks/assumptions and toolchain; inconclusive, unsupported and
timeout outcomes cannot satisfy required proof. No release claims safety merely from admission,
hashes or empirical test success.
