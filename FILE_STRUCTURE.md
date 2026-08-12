# FILE_STRUCTURE — <project-name>

<!-- Authoritative directory tree with one-line annotations.
     RULE: adding, moving, or deleting files without updating this doc in the SAME task
     violates rules/documentation-protocol.md. When this doc and the disk disagree,
     fixing that is the immediate next action — the doc is the source of truth for
     where things BELONG.
     Keep the tree SHALLOW (2–3 levels): it is a map, not an inventory. A directory of
     homogeneous files gets ONE annotated line for the directory, not a line per file. -->

```
<project-root>/
├── <dir>/                  # <role in one line>
│   ├── <subdir>/           # <role — e.g. "one file per <thing>, named <pattern>">
│   └── <key-file>          # <role>
├── <dir>/                  # <role>
├── <key-file>              # <role>
└── <key-file>              # <role>
```

## Placement rules

- New <thing-type, e.g. UI components> go in `<dir>/`; new <thing-type> go in `<dir>/`.
- Generated or vendored — never edit by hand: `<dir>/`, `<dir>/`.
