# Session preservation — 2026-10-29

This is a work-in-progress preservation snapshot, not an approved release or deployment.

Original branch: `feat/agent-native-declarative-systems`; original HEAD: `bb1deb8f9aacb8df261e92bb64e644a6a990ddaa`.

The commit preserves tracked modifications and nonignored source/research files. Existing published tags and records are unchanged. Rebuildable caches and machine private keys are not included. Nested Git worktrees are preserved independently.

Local data/configuration and retained distribution files are encrypted to the existing user age identity. Restore with your separately retained age identity:

```sh
age --decrypt --identity /path/to/age-identity local-state.tar.gz.age | tar -xz -C /path/to/restored-workspace
```

For the MCP test clone, `parent-workspace/` contains the surrounding non-Git test workspace. SQLite files use individually consistent SQLite backup snapshots; no atomic snapshot across databases is claimed.
