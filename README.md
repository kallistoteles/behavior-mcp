# Behavior MCP

An experimental local MCP server for authoring and using persistent Behavior systems through
structured data. Behavior IR owns model meaning and lowering; Behavior Core owns evaluation,
commit and replay. This package supplies transport, artifact storage, host authorization and
independent deployment/state boundaries.

The implemented authoring profile supports bounded RequestFlow and StateMachine definitions,
including composition in one module. Proposals, admitted definitions, verification evidence,
activation and committed state are separate artifacts and operations. Agents do not generate
application source code or receive filesystem, SQL or process tools.

## Supported Environment

Linux x86_64, Python 3.13+, the exact Behavior 0.14.0 released wheel and bundled Core 0.15.0.
The pinned Nix shell supplies Python 3.13.14, uv, native Ruff and Z3 4.16.0. Python dependencies
and build tools use `uv.lock`. See [compatibility](docs/compatibility.md) for identities and limits.

Run the same quality gate used by CI and release checks:

```bash
nix develop --command ./scripts/check
```

This bootstraps the locked environment, checks released dependency bytes/public interfaces,
formatting, lint, strict types, deterministic tests, Core backend conformance and physical
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

- [Tool contracts and schemas](specs/001-agent-native-systems/contracts/mcp.md)
- [Generic proposal example](specs/001-agent-native-systems/contracts/example-proposal.json)
- [Delegated host authority](specs/001-agent-native-systems/contracts/host-policy.md)
- [Acceptance journey](specs/001-agent-native-systems/quickstart.md)
- [Capability gaps](SEMANTIC_GAPS.md)

Canonical model documents do not contain every authoring body in this release. The server
therefore retains complete original authoring data/context alongside canonical documents, Wire
modules and lowering receipts. Schema-changing activation, arbitrary expressions, command
execution, cross-system workflows and authored Approval/WorkQueue models remain unsupported.
Admission, a matching hash, or a successful test is never approval or a general safety proof.
