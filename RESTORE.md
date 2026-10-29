# Complete local repository backup

Snapshot: `backup/local-state-2026-10-29-092910-utc`
Source HEAD: `249e2407bfecfa5f0198d7ce3e32607e63ee1cf4`
Archive SHA-256: `1cddc751abc8b1b7936b7c928da28b5059b50b4960e8df159a4670e4a5ebb347`

This backup contains the entire `behavior-mcp` directory with **no exclusions**: tracked source,
tests, evidence, ten SQLite fixtures, local Git refs/objects/reflogs/config, the ignored `dist/`
wheel/source artifacts, `.specify/feature.json`, `.venv`, bytecode and caches. The full archive is
split into five ordered parts for GitHub storage. `MANIFEST.json` records every entry and each
regular file's SHA-256. `repository.bundle` also provides a standalone copy of all Git refs.

The snapshot was extracted locally and every file, symlink, permission and modification time
verified. The source inventory remained unchanged during capture.

## Restore the complete snapshot

Use an empty destination. GNU tar is needed to preserve the recorded nanosecond modification times.

```bash
git clone --single-branch --branch backup/local-state-2026-10-29-092910-utc \
  git@github.com:kallistoteles/behavior-mcp.git behavior-mcp-backup
cd behavior-mcp-backup
python3 verify-backup.py
cat behavior-mcp-full-snapshot.tar.gz.part-* > ../behavior-mcp-full-snapshot.tar.gz
mkdir -p ../recovered
tar --extract --gzip --acls --xattrs --same-permissions --no-same-owner \
  --file ../behavior-mcp-full-snapshot.tar.gz --directory ../recovered
python3 verify-backup.py --restored ../recovered/behavior-mcp
cd ../recovered/behavior-mcp
git status
```

Run the restored-entry verification **before** Git refreshes the restored index; Git legitimately
updates index metadata when inspecting the new filesystem. File content and all Git history remain
intact. Directory timestamps, file modes, hard links and symlinks are carried by the archive.

The Python symlink points outside the repository into the pinned Nix store, as it did originally.
Recreate those external dependencies and synchronize the locked environment with:

```bash
nix develop --command uv sync --locked --no-build-isolation
```

## Restore Git history only

```bash
git clone --branch feat/remaining-behavior-models repository.bundle ../behavior-mcp-code
```

This alternative restores committed code/history; use the full snapshot for ignored local files,
reflogs, caches and local Git configuration.
