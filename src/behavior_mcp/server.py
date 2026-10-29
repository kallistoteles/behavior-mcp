"""Public MCP transport and bounded pre-decode framing."""

import json
from collections.abc import Iterable, Iterator
from datetime import UTC
from typing import Any, Protocol, cast

import mcp_types as types
from mcp import MCPError
from mcp.server import Server

from .limits import HostLimits
from .schemas import OperationError

FRAME_LIMIT = 1048576
DEPTH_LIMIT = 32


def bounded_frames(
    chunks: Iterable[bytes], *, limits: HostLimits | None = None
) -> Iterator[bytes]:
    host_limits = limits or HostLimits()
    buffer = bytearray()
    for chunk in chunks:
        start = 0
        while start < len(chunk):
            end = chunk.find(b"\n", start)
            part = chunk[start:] if end < 0 else chunk[start:end]
            if len(buffer) + len(part) > host_limits.frame_bytes:
                raise OperationError(
                    "invalid_input", "FRAME_TOO_LARGE", "Frame exceeds host limit"
                )
            buffer.extend(part)
            if end < 0:
                break
            yield bytes(buffer)
            buffer.clear()
            start = end + 1
    if buffer:
        raise OperationError(
            "invalid_input", "INCOMPLETE_FRAME", "Incomplete transport frame"
        )


def decode_frame(frame: bytes, *, limits: HostLimits | None = None) -> Any:
    host_limits = limits or HostLimits()
    depth = 0
    quoted = escaped = False
    for byte in frame:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            if depth > host_limits.nesting_depth:
                raise OperationError(
                    "invalid_input", "FRAME_TOO_DEEP", "Frame exceeds host depth limit"
                )
        elif byte in (93, 125):
            depth -= 1

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for k, v in items:
            if k in value:
                raise OperationError(
                    "invalid_input",
                    "DUPLICATE_JSON_MEMBER",
                    "Duplicate protocol member",
                )
            value[k] = v
        return value

    try:
        return json.loads(
            frame.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite")),
        )
    except (ValueError, UnicodeError, RecursionError):
        raise OperationError(
            "invalid_input", "MALFORMED_JSON", "Malformed protocol JSON"
        ) from None


class ToolApplication(Protocol):
    def tools(self) -> list[types.Tool]: ...
    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> types.CallToolResult: ...


def make_server(application: ToolApplication | None) -> Server[Any]:
    async def listing(ctx: Any, params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(
            tools=[] if application is None else application.tools()
        )

    async def call(
        ctx: Any, params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        if application is None:
            raise MCPError(code=-32601, message="Unknown tool")
        return await application.call_tool(params.name, params.arguments or {})

    return Server(
        "behavior-mcp", version="0.1.0", on_list_tools=listing, on_call_tool=call
    )


class BoundedStdin:
    """A public stream adapter; bounds bytes before the SDK parses JSON-RPC."""

    def __init__(self, fd: int, limits: HostLimits | None = None) -> None:
        self.fd = fd
        self.limits = limits or HostLimits()

    async def __aiter__(self) -> Any:
        import os

        import anyio

        buffer = bytearray()
        while chunk := await anyio.to_thread.run_sync(
            os.read, self.fd, 8192, abandon_on_cancel=True
        ):
            start = 0
            while start < len(chunk):
                end = chunk.find(b"\n", start)
                part = chunk[start:] if end < 0 else chunk[start:end]
                if len(buffer) + len(part) > self.limits.frame_bytes:
                    raise OperationError(
                        "invalid_input", "FRAME_TOO_LARGE", "Frame exceeds host limit"
                    )
                buffer.extend(part)
                if end < 0:
                    break
                frame = bytes(buffer)
                # Depth/duplicate-key checks occur before handing protocol parsing to the SDK.
                try:
                    decode_frame(frame, limits=self.limits)
                except OperationError as error:
                    if error.code != "MALFORMED_JSON":
                        raise
                    # The SDK supplies the protocol-level parse error for malformed JSON.
                yield frame.decode("utf-8") + "\n"
                buffer.clear()
                start = end + 1
        if buffer:
            raise OperationError(
                "invalid_input", "INCOMPLETE_FRAME", "Incomplete transport frame"
            )


async def serve_stdio(application: ToolApplication | None, workspace: Any) -> None:
    from mcp.server.stdio import stdio_server

    from .storage import file_lock

    server = make_server(application)
    with file_lock(workspace / "owner.lock", blocking=False):
        if isinstance(application, Application):
            import anyio

            await anyio.to_thread.run_sync(application.startup)
        async with stdio_server(
            stdin=cast(
                Any,
                BoundedStdin(
                    0,
                    application.limits
                    if isinstance(application, Application)
                    else None,
                ),
            )
        ) as (read, write):
            await server.run(read, write, server.create_initialization_options())


class Application:
    STAGES = {
        "models_list": "discovery",
        "definition_propose": "authoring",
        "definition_get": "authoring",
        "definition_validate": "validation",
        "definition_verify": "verification",
        "gaps_list": "discovery",
        "systems_create": "system_creation",
        "systems_list": "discovery",
        "system_inspect": "read",
        "definition_activate": "activation",
        "capabilities_list": "discovery",
        "state_read": "read",
        "transition_evaluate": "evaluation",
        "transition_commit": "commit",
        "operation_get": "recovery",
        "system_recover": "recovery",
        "capability_read": "read",
        "definition_safety_certify": "safety_certification",
        "definition_safety_verify_evidence": "safety_checking",
        "state_validate_safety": "safety_state_validation",
    }

    def __init__(
        self,
        workspace: Any,
        context: Any,
        policy_id: str,
        *,
        fault: Any = None,
        limits: Any = None,
    ) -> None:
        from .artifacts import ArtifactStore
        from .dependencies import check_dependencies

        check_dependencies()
        import threading

        self.limits = HostLimits.from_document(limits)
        self.verification_workers = threading.BoundedSemaphore(
            self.limits.verification_workers
        )
        self.workspace = workspace
        self.context = context
        self.policy_id = policy_id
        self.fault = fault
        self.artifacts = ArtifactStore(workspace)

    def startup(self) -> None:
        # Recovery runs only after serve_stdio has acquired the workspace owner lock.
        # Failed recovery remains scoped to its system; normal operations still fail closed.
        from .safety import cleanup_staging

        cleanup_staging(self.workspace)
        self.startup_results = []
        for system_id in self.artifacts.system_ids():
            self.startup_results.append(
                self.execute("system_recover", {"system_id": system_id})
            )

    def tools(self) -> list[types.Tool]:
        from .schemas import load_schema, prune_schema, stage_result_schema

        inputs = load_schema("tool-request")
        additions = {
            v["properties"]["name"]["const"]: v["properties"]["arguments"]
            for v in load_schema("tool-additions")["oneOf"]
        }

        def tool_input(name: str) -> dict[str, Any]:
            old = inputs["$defs"].get(name)
            new = additions.get(name)
            variants = ([old] if old else []) + ([new] if new else [])
            return prune_schema(
                {"type": "object", "oneOf": variants, "$defs": inputs["$defs"]}
                if len(variants) > 1
                else {**variants[0], "$defs": inputs["$defs"]}
            )

        return [
            types.Tool(
                name=name,
                description=f"{name}: explicit {stage} boundary under host authority; never implies another stage.",
                input_schema=tool_input(name),
                output_schema=stage_result_schema(stage),
            )
            for name, stage in self.STAGES.items()
        ]

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> types.CallToolResult:
        import threading

        import anyio

        from .verification import CANCELLATION

        if name not in self.STAGES:
            raise MCPError(code=-32601, message="Unknown tool")
        cancelled = threading.Event()

        def execute() -> dict[str, Any]:
            token = CANCELLATION.set(cancelled)
            try:
                return self.execute(name, arguments)
            finally:
                CANCELLATION.reset(token)

        try:
            envelope = await anyio.to_thread.run_sync(execute, abandon_on_cancel=True)
        finally:
            cancelled.set()
        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text", text=json.dumps(envelope, ensure_ascii=False)
                )
            ],
            structured_content=envelope,
            is_error=envelope["request_status"] != "completed",
        )

    def evidence(
        self, kind: str, subject: dict[str, Any], report: dict[str, Any]
    ) -> list[dict[str, Any]]:
        from .adapters import release_identity

        ref = self.artifacts.put(
            kind + "_evidence",
            {
                "subject": subject,
                "report": report,
                "release": subject.get("release", release_identity()),
            },
        )
        return [
            {
                "evidence_id": ref,
                "kind": kind,
                "report_ref": ref,
                "subject": subject,
                "release": subject.get("release", release_identity()),
            }
        ]

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        from .policy import Delegation
        from .schemas import failure, validate_input
        from .storage import file_lock

        stage = self.STAGES.get(name, "read")
        subject: dict[str, Any] = {"workspace_id": self.context.workspace_id}
        manager = None
        try:
            encoded = json.dumps(
                arguments, ensure_ascii=False, allow_nan=False
            ).encode()
            if len(encoded) > self.limits.frame_bytes:
                raise OperationError(
                    "invalid_input",
                    "FRAME_TOO_LARGE",
                    "Request exceeds host byte limit",
                )
            decode_frame(encoded, limits=self.limits)
            validate_input(name, arguments)
            if name in {
                "definition_safety_certify",
                "definition_safety_verify_evidence",
            }:
                from .safety import Safety

                return Safety(self).run(name, arguments, subject)
            with file_lock(self.workspace / "policy.lock", shared=True):
                policy_document = self.artifacts.policy(self.policy_id)
                policy = Delegation.from_document(
                    policy_document, policy_document["issuer_id"]
                )
                if name in {
                    "models_list",
                    "definition_propose",
                    "definition_get",
                    "definition_validate",
                    "definition_verify",
                    "gaps_list",
                }:
                    policy.authorize(self.context, name)
                    return self._authoring(name, arguments, subject, policy)
                from .systems import SystemManager

                manager = SystemManager(
                    self.workspace,
                    self.context,
                    self.artifacts,
                    policy,
                    self.fault,
                    self.limits,
                )
                return manager.route(name, arguments, subject)
        except Exception as error:
            if manager is not None and manager.recovery_operation_id is not None:
                subject.setdefault("operation_id", manager.recovery_operation_id)
            return failure(
                stage,
                subject,
                error,
                mutation_attempted=manager.recovery_publication_attempted
                if manager is not None
                else False,
            )

    def _authoring(
        self, name: str, args: dict[str, Any], subject: dict[str, Any], policy: Any
    ) -> dict[str, Any]:
        from .adapters import (
            admit_proposal,
            discovery,
            ecosystem_release,
            gaps,
            inventory,
            reconstruct,
            release_identity,
        )
        from .schemas import completed
        from .verification import verify_module

        stage = self.STAGES[name]
        if name in {"models_list", "gaps_list"}:
            kind = "models" if name == "models_list" else "gaps"
            return completed(
                stage,
                "listed",
                subject,
                {
                    "kind": kind,
                    kind: discovery() if kind == "models" else gaps(),
                    "release": ecosystem_release()
                    if kind == "models"
                    else release_identity(),
                },
            )
        if name == "definition_propose":
            if args.get("parent_definition_id") is not None:
                policy.authorize(self.context, "definition_get")
            result = self.artifacts.propose(**args)
            subject.update(
                proposal_id=result["proposal_id"],
                proposal_revision=result["proposal_revision"],
            )
            return completed(stage, "proposal_stored", subject, result)
        if name == "definition_get" and "proposal_id" in args:
            result = self.artifacts.proposal(
                args["proposal_id"], args.get("proposal_revision")
            )
            subject.update(
                proposal_id=result["proposal_id"],
                proposal_revision=result["proposal_revision"],
            )
            return completed(stage, "proposal_loaded", subject, result)
        if name == "definition_validate":
            subject.update(
                proposal_id=args["proposal_id"],
                proposal_revision=args["proposal_revision"],
            )
            definition = admit_proposal(
                self.artifacts, args["proposal_id"], args["proposal_revision"]
            )
        else:
            definition = self.artifacts.definition(args["definition_id"])
        subject.update(
            definition_id=definition["definition_id"],
            behavior_hash=definition["behavior_hash"],
            schema_hash=definition["schema_hash"],
            release=definition["release"],
        )
        if "policy_set_hash" in definition:
            subject["policy_set_hash"] = definition["policy_set_hash"]
        if name == "definition_get":
            if "evidence_ref" in args:
                from .safety import evidence_chunk

                return completed(
                    stage,
                    "evidence_chunk",
                    subject,
                    evidence_chunk(
                        self.artifacts, definition, self.context.workspace_id, args
                    ),
                )
            return completed(
                stage,
                "definition_loaded",
                subject,
                self.artifacts.inspect_definition(
                    definition["definition_id"], self.context.workspace_id
                ),
            )
        definition, module, snapshot = reconstruct(
            self.artifacts, definition["definition_id"]
        )
        if name == "definition_validate":
            result = {
                "kind": "validation",
                "stages": {
                    s: "passed"
                    for s in ("structural", "model", "lowering", "admission")
                },
                "definition": definition,
                "generated_capabilities": inventory(
                    module,
                    expanded=definition["release"]["adapter_profile"]
                    == "structured-models.v2",
                    proposal=snapshot["proposal"],
                ),
                "diagnostics": module.model_diagnostics,
            }
            return completed(
                stage,
                "admitted",
                subject,
                result,
                self.evidence("validation", subject, result),
            )
        result = verify_module(
            module,
            args["profile_id"],
            limits=self.limits,
            workers=self.verification_workers,
        )
        result["release"] = definition["release"]
        return completed(
            stage,
            "verification_" + result["verification_status"],
            subject,
            result,
            self.evidence("verification", subject, result),
        )


def main() -> None:
    import argparse
    from pathlib import Path

    import anyio

    from .dependencies import check_dependencies

    parser = argparse.ArgumentParser(prog="behavior-mcp")
    parser.add_argument("command", choices=["serve"])
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--host-config", required=True, type=Path)
    args = parser.parse_args()
    check_dependencies()
    config = json.loads(args.host_config.read_text())
    if (
        set(config) - {"limits"}
        != {"workspace_root", "workspace_id", "principal_id", "actor_id", "policy_id"}
        or Path(config["workspace_root"]).resolve() != args.workspace.resolve()
    ):
        parser.error("Trusted launcher configuration does not bind this workspace")
    from datetime import datetime

    from .policy import TrustedContext

    context = TrustedContext(
        config["principal_id"],
        config["workspace_id"],
        config["actor_id"],
        lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        semantic_clock=lambda: int(datetime.now(UTC).timestamp() * 1000),
    )
    application = Application(
        args.workspace, context, config["policy_id"], limits=config.get("limits")
    )
    anyio.run(serve_stdio, application, args.workspace)


if __name__ == "__main__":
    main()
