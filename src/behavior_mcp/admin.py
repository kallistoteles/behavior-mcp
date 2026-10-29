"""Separate trusted local administration. There is no MCP administration tool."""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from .artifacts import ArtifactStore, encode
from .dependencies import check_dependencies
from .policy import Delegation
from .schemas import JSON, OperationError, validate
from .storage import connect, file_lock, transaction


@dataclass(frozen=True)
class AdminAuthority:
    issuer_id: str
    workspace_id: str
    workspace_root: Path
    allowed_principals: tuple[str, ...]


def _bound(
    root: Path, document: JSON, authority: AdminAuthority, principal_key: str
) -> None:
    if (
        root.resolve() != authority.workspace_root.resolve()
        or document["workspace_id"] != authority.workspace_id
        or document["issuer_id"] != authority.issuer_id
        or document[principal_key] not in authority.allowed_principals
    ):
        raise OperationError(
            "unauthorized",
            "ADMIN_SCOPE_DENIED",
            "Administrative authority does not match the document",
        )


def install_policy(root: Path, document: JSON, authority: AdminAuthority) -> None:
    policy = Delegation.from_document(document, authority.issuer_id)
    _bound(root, document, authority, "principal_id")
    ArtifactStore(root).install_policy(policy.document)


def install_approval(root: Path, document: JSON, authority: AdminAuthority) -> None:
    expanded = document.get("format") == "behavior-mcp.activation-approval.v2"
    validate("activation-approval-v2" if expanded else "activation-approval", document)
    _bound(root, document, authority, "grantee_principal_id")
    artifacts = ArtifactStore(root)
    with file_lock(root / "policy.lock"):
        policy = artifacts.policy(document["policy_id"], document["policy_version"])
        if (
            policy["principal_id"] != document["grantee_principal_id"]
            or policy["workspace_id"] != document["workspace_id"]
        ):
            raise OperationError(
                "unauthorized",
                "APPROVAL_SCOPE_DENIED",
                "Approval does not match its trusted policy",
            )
        manifest = artifacts.definition(document["definition_id"])
        if expanded != (
            manifest["release"]["adapter_profile"] == "structured-models.v2"
        ) or (expanded and document["policy_set_hash"] != manifest["policy_set_hash"]):
            raise OperationError(
                "unauthorized",
                "APPROVAL_SUBJECT_DENIED",
                "Approval format or policy set differs from its exact subject",
            )
        if any(document[k] != manifest[k] for k in ("behavior_hash", "schema_hash")):
            raise OperationError(
                "unauthorized",
                "APPROVAL_SUBJECT_DENIED",
                "Approval subject differs from admitted definition",
            )
        with connect(artifacts.path) as db, transaction(db):
            prior = db.execute(
                "SELECT document FROM approvals WHERE id=?", (document["approval_id"],)
            ).fetchone()
            text = encode(document)
            if prior and prior["document"] != text:
                raise OperationError(
                    "conflict", "IMMUTABLE_APPROVAL", "Approval cannot be overwritten"
                )
            db.execute(
                "INSERT OR IGNORE INTO approvals VALUES (?,?)",
                (document["approval_id"], text),
            )


def main() -> None:
    parser = argparse.ArgumentParser(prog="behavior-mcp-admin")
    parser.add_argument("command", choices=["install-policy", "install-approval"])
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--trusted-config", required=True, type=Path)
    parser.add_argument("--document", required=True, type=Path)
    args = parser.parse_args()
    check_dependencies()
    config = json.loads(args.trusted_config.read_text())
    if set(config) != {
        "issuer_id",
        "workspace_id",
        "workspace_root",
        "allowed_principals",
    }:
        parser.error("Invalid trusted administrative configuration")
    authority = AdminAuthority(
        config["issuer_id"],
        config["workspace_id"],
        Path(config["workspace_root"]),
        tuple(config["allowed_principals"]),
    )
    document = json.loads(args.document.read_text())
    (install_policy if args.command == "install-policy" else install_approval)(
        args.workspace, document, authority
    )
    print(
        json.dumps(
            {
                "status": "installed",
                "kind": args.command,
                "id": document.get("policy_id")
                if args.command == "install-policy"
                else document["approval_id"],
            }
        )
    )


if __name__ == "__main__":
    main()
