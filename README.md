# Behavior MCP

An experimental local MCP server for authoring and using persistent Behavior systems through
structured data. Behavior IR owns model meaning and lowering; Behavior Core owns evaluation,
commit and replay. This package supplies transport, artifact storage, host authorization and
independent deployment/state boundaries.

The retained v1 profile supports RequestFlow and StateMachine. The versioned v2 profile also
supports Approval, WorkQueue, FieldOwnership and LifecycleDependency, including composition in
one module, authoritative reads and conditional Safety certification. Proposals, admitted definitions, verification evidence,
activation and committed state are separate artifacts and operations. Agents do not generate
application source code or receive filesystem, SQL or process tools.

## Supported Environment

Linux x86_64, Python 3.13+, the exact Behavior 0.14.0 released wheel and bundled Core 0.15.0.
The pinned Nix shell supplies Python 3.13.14, uv, native Ruff and Z3 4.16.0. Python dependencies
and build tools use `uv.lock`. The separately pinned public Behavior proof toolchain supplies
Lean/leanchecker 4.30.0 for Safety certification and fresh bundle checking. See [compatibility](docs/compatibility.md) for identities and limits.

Run the same quality gate used by CI and release checks:

```bash
nix develop --command ./scripts/check
```

This bootstraps the locked environment, checks released dependency bytes/public interfaces,
all packaged JSON schemas, formatting, lint, strict types, deterministic tests, Core backend conformance and physical
recovery. The package installation test also checks the built distribution outside the checkout. Validated
wheel/source artifacts remain in `dist/`.

## Use

A trusted operator installs a bounded delegation policy and starts one workspace owner:

```bash
nix develop --command uv run --locked behavior-mcp-admin install-policy \
  --workspace /absolute/workspace \
  --trusted-config /absolute/admin.local.json \
  --document specs/001-agent-native-systems/contracts/example-host-policy.json
nix develop --command uv run --locked behavior-mcp serve \
  --workspace /absolute/workspace \
  --host-config /absolute/launcher.local.json
```

[Operations](docs/operations.md) describes the trusted configuration, activation policy, recovery
and storage assumptions. This local trust boundary does not isolate an unrestricted process
running as the same OS user.

An MCP client discovers models, proposes structured data, validates an exact proposal revision,
creates an inactive system and explicitly activates its exact definition. It then discovers
actual generated capabilities, evaluates a request and separately commits the returned token.
Multiple systems share immutable artifacts while keeping mutable state, history, activation and
request authority isolated by SystemId. Restart does not depend on an agent session, a note client
or Git.

- [Expanded tools and schemas](specs/002-remaining-behavior-models/contracts/mcp.md)
- [Remaining-model journeys](specs/002-remaining-behavior-models/quickstart.md)
- [Retained v1 tool contracts](specs/001-agent-native-systems/contracts/mcp.md)
- [Generic proposal example](specs/001-agent-native-systems/contracts/example-proposal.json)
- [Delegated host authority](specs/001-agent-native-systems/contracts/host-policy.md)
- [Acceptance journey](specs/001-agent-native-systems/quickstart.md)
- [Capability gaps](SEMANTIC_GAPS.md)

Canonical model documents do not contain every authoring body in this release. The server
therefore retains complete original authoring data/context alongside canonical documents, Wire
modules and lowering receipts. Schema-changing activation, arbitrary executable expressions, command execution and cross-system
workflows remain unsupported. Structured expressions use a bounded public typed-expression subset.
Safety certificates cover ordinary transitions under recorded assumptions; activation separately
requires exact current-state validity and trusted delegated authority.
Admission, a matching hash, or a successful test is never approval or a general safety proof.
