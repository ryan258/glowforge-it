# glowforge-it

Local CLI (`gf`, `glowforge-it`) that turns raster art into Glowforge-ready PNG/SVG/PDF files. It prepares artwork only: never power, speed, focus or passes.

## Commands

- Tests: `.venv/bin/python -m pytest -q` (also guards docs: every documented `gf` command must dry-run, every CLI flag must appear in the README).
- Run uninstalled: `uv run main.py --help`. Packaging check: `.venv/bin/python scripts/check_distribution.py`.

## Rules that are easy to break

- Imports are one-way, lowest layer first: `settings, geometry, workflow, publication, contracts, renderers, vector, personalization, qr, imaging, proof, export, planning, proofing, batch, cli`. `tests/test_compat.py` enforces the order and lists every module; a new module must be added there.
- Black (0) is burn and white (255) is no burn, in every renderer and polarity. Geometry is in 300-DPI pixels.
- Every new artifact must go through `contracts.artifact_paths`, planning (collision, existing-output policy, memory), the manifest, and `publication.publish_generation`. Previews and proofs never feed back into machine artwork, and nothing marks a job customer-approved.
- Reject rather than silently adjust (non-ASCII stamp text, overlapping marks, off-shape marks). Error messages may suggest a fix; they do not apply it.
- Evidence levels stay separate: software checks, Glowforge app import, physical measurement, customer approval. No app import or burn has been recorded, so do not claim calibrated results.
- Docs do not record test counts or pass times; they go stale. CI output is the record.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **glowforge-it** (667 symbols, 1464 relationships, 47 execution flows).

> Index stale? Run `node .gitnexus/run.cjs analyze --index-only` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? Bootstrap with `npx`, `bunx`, or `pnpm dlx` — e.g. `bunx gitnexus@latest analyze` (npm 11 npx crash; #1939).

## Always Do

- **MUST run impact before editing.** Use `impact({target: "symbolName", direction: "upstream"})` or `node .gitnexus/run.cjs impact "symbolName" --direction upstream --repo .`; report callers, processes, and risk. Never substitute grep for graph analysis.
- **MUST analyze graph changes before committing.** Use `detect_changes({scope: "all"})` (MCP) or `node .gitnexus/run.cjs detect-changes --scope all --repo .` (CLI fallback). `partial: true` or `truncated: true` is not a clean check — a zero means unseen, not unaffected; re-run it. For regression review: `detect_changes({scope: "compare", base_ref: "main"})` or `node .gitnexus/run.cjs detect-changes --scope compare --base-ref "main" --repo .`.
- MUST warn on HIGH/CRITICAL `risk` pre-edit; never use `riskSharedAxes` to waive a HIGH/CRITICAL `risk` warning. Compare File/symbol: MCP File omits axes; Graph-RAG expands File.
- **MUST treat `risk: UNKNOWN` as unresolved, not as low.** An empty caller set is not evidence the symbol is unused — it can also mean the callers are not resolvable by the index (plain-object property access, dynamic dispatch, cross-language calls). `impact` pairs `UNKNOWN` with a `riskNote` saying so. Confirm with a text search before treating the symbol as safe to change or delete; do not proceed on the strength of a zero.
- **MUST use `query({search_query: "concept"})` for concepts/flows, `context({name: "symbolName"})` for a named symbol, or `impact` for blast radius, on read-only callers, dependencies, imports, or execution flow.** Graph first; text search only for empty/`UNKNOWN`/literals.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method before MCP/CLI impact analysis.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis, and never read `UNKNOWN` as an all-clear — it means the walk could not answer, which is the one verdict that requires confirming by other means.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit before MCP/CLI graph change analysis.

## Resources

| Resource | Use for |
| --- | --- |
| `gitnexus://repo/glowforge-it/context` | Codebase overview, check index freshness |
| `gitnexus://repo/glowforge-it/clusters` | All functional areas |
| `gitnexus://repo/glowforge-it/processes` | All execution flows |
| `gitnexus://repo/glowforge-it/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
| --- | --- |
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
