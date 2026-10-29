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
operational diagnostics belong on stderr. The fixed tool catalog advertises each stage using
the unchanged versioned result contracts restricted to that stage, retaining all referenced
definitions. Unused definitions and unrelated stages are omitted; the complete schema catalog
fits within 1 MiB. Runtime result validation still uses the complete authoritative contracts.

Authoring enum cases are ordered arrays of `{name, value}`. Their order is explicit public Enum
declaration input. JSON object-member ordering cannot change admitted identities. Proposal edits
supply base ProposalId and expected revision; validation always freezes an exact source revision.

Evaluation returns an opaque token only for an actual Core ALLOW bundle. It does not commit.
Refused evaluations retain their original structured refusal as well. An identical scoped retry
returns that same outcome, source history and definition after restart or a later activation,
without re-evaluating against current state. Current evaluation authority is still required;
changing a request under the same OperationId conflicts.
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

The additional v2 limits `proof_workers` (1), `proof_timeout_seconds` (120),
`proof_bundle_bytes` (8388608), `read_timeout_seconds` (5), and `read_output_bytes` (1048576)
may also be tightened. Only these keys and the existing `default`/`bounded` profile names are accepted. All values
are positive integers; booleans, unknown keys and increases beyond the published defaults/maxima
are rejected. Defaults remain 1048576 bytes, depth 32, pages 50/100 and two workers. A lower
`page_max` also lowers the implicit default page size when `page_default` is omitted. The default
profile's budgets are 20000000/60000; bounded uses 20000/5000 (resource limit/milliseconds).
Overrides may tighten either budget. Reports retain the actual public profile parameters, and
the server checks the returned parameters against the request. The process-wide verifier cap
remains two, with the configured per-server cap enforced as well. Each system still has one
coordinated writer. MCP arguments cannot change any host limit.

Verifier process output has separate fixed maxima of 8 MiB stdout and 1 MiB stderr. The host
multiplexes request writes and both output streams under the worker deadline. Stderr is counted
and discarded. Exceeding either maximum kills/reaps the worker process group and returns
`VERIFICATION_STDOUT_LIMIT` or `VERIFICATION_STDERR_LIMIT` as an infrastructure error, without
reporting a proof or exposing worker output. Timeout/overflow cleanup performs no unbounded drain.

`definition_get` with a DefinitionId returns a `definition_inspection`: its original manifest
and source snapshot, separately identified module/context/lowering-receipt contents, and retained
definition-specific validation/verification evidence. Inspection checks artifact references and
preserves original report labels; it does not run a new proof or expose another system's policy
and activation evidence through shared artifacts.

## Expanded Models, Reads and Safety

The [v2 policy grammar](../specs/002-remaining-behavior-models/contracts/host-policy.md) uses
separate exact-version adapter grants and runtime action/read lists. Approval decisions and Safety
policies cannot grant host powers. The twenty fixed tools include `capability_read`,
`definition_safety_certify`, `definition_safety_verify_evidence` and `state_validate_safety`.
Use the [v2 examples](../specs/002-remaining-behavior-models/contracts/examples/) as bounded templates;
installing a model never installs a host policy.

Trusted semantic time is UTC Unix milliseconds, an integer from 0 through 9007199254740991. The launcher
supplies actor/worker and current time; clients can propose only permitted queue deadlines within
the policy's per-capability bounds. Evaluation records the original time and Core bundle. A delayed
commit or retry does not sample a replacement clock. WorkQueue is neither a scheduler nor an executor.

A public read records its exact definition, original trusted context, history and state before
worker execution. It uses a publication-disabled backend, public Core read/replay and one bounded
complete result; no truncation can become a successful read. OperationId remains bound to its
original workspace/system/principal/request, including across restart. Failed reads cannot imply
that a domain mutation might have committed. Current read authority governs disclosure of retries.

Pure proof compilation holds neither policy nor system writer locks and rechecks current authority
before publishing or disclosing evidence. One proof worker has a 120-second deadline, 120-second CPU
ceiling, 8 GiB virtual address-space ceiling, 128 descriptors and 16 MiB per-file limit. Read workers
use 4 GiB virtual address space and a five-second deadline. Stdout/stderr maxima remain 8 MiB/1 MiB;
reads additionally limit complete output to 1 MiB. Cancellation, timeout and overflow terminate and
reap the entire worker process group. Startup examines at most 64 owned staging entries, removes only
dead owned jobs and never promotes an incomplete proof. These limits are host restrictions.

Imported bundles are unverified JSON data until the public checker establishes a fresh result.
Missing, unsupported, inconclusive or timed-out proof never satisfies a required certificate.
`definition_get` permits definition-bound evidence chunks of 1–65536 bytes with nonnegative offsets;
shared immutable definitions do not expose system-specific deployment/state evidence.

Activation independently checks the exact definition, BehaviorHash, SchemaHash, complete policy hash,
required evidence and fresh incoming-state validity under the writer boundary. V2 exact approvals
bind all those identities, the full history and policy version. An unchanged BehaviorHash cannot
authorize a changed Safety policy. Historical recovery checks original proof artifacts and
state-validation anchors without relabeling them under current policy or tools.

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

Recovery first reconciles the historical outcome, independently of current permission to execute
it. This requires current `system_recover` and `operation_get` authority for that system. Every
supported writer publishes Core changes and its receipt atomically under the system writer lock.
An unchanged exact Core HistoryRef and no receipt establish nonpublication. If history moved,
another OperationId might have committed the same transition, so a missing receipt alone is
insufficient. The host loads the retained original module and asks public Core to check the
original bundle with domain publication disabled in both backend mutation callbacks. Core's
`already` acknowledgment establishes commitment; Core's `StateConflict` establishes noncommitment
under the coordinated writer boundary. Any other inconclusive/error result preserves uncertainty.
The backend never fabricates a Core conflict: a prohibited callback raises a backend error and
cannot write. The host records reconciliation evidence without interpreting bundle fields or
recomputing semantic identities. Missing or unreadable original storage cannot establish
nonpublication. This composes existing public interfaces; it does not claim a dedicated Core
read-only reconciliation API.

Only after that observation may the same recovery request retry the original bundle. Fresh
publication still requires the current commit grant, allowed capability, original actor and
deployment, and unchanged source history; Core still owns the actual compare-and-set commit.
If those conditions are absent, recovery returns the established `not_committed` outcome and
unblocks later authorized work. A later recovery of that terminal operation never silently
retries it after permissions return. Existing committed receipts remain readable under current
read authority even after execution permissions, actor or deployment change. Original evaluation
and publication authority remain unchanged; reconciliation records its own current authority.

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
begin with observed failing assertions. All tests work without an AI model or note application. The gate meta-validates all fixed packaged
JSON schemas once through `python -m behavior_mcp.schemas`; runtime still validates every client
request and server result against those contracts. It does not repeat the schema-as-data audit in
each short-lived crash, read or proof worker.

A complete result requires application/contract, authorization, public 45-case backend conformance,
physical crash, retry, isolation, revision and historical replay tests. Formal verification reports
retain their exact subject/profile/checks/assumptions and toolchain; inconclusive, unsupported and
timeout outcomes cannot satisfy required proof. No release claims safety merely from admission,
hashes or empirical test success.
