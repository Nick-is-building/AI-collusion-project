# DEVLOG 01 — Foundation and provenance

## Scope

Repository initialization, environment and dependencies, original upstream revisions, data intake, baseline reanalysis reproduction, shared technical infrastructure, and provenance of any pre-sprint work. Use this for **implementation records**, not for rewriting the scientific plan.

## Initial state — starter file, not a work entry

No work by Claude Code has been recorded in this block. `PROJECT_PLAN.md` §§3, 6–7, 13–14 identifies pre-sprint research and intended verification tasks. These are descriptions in the plan, **not** independent confirmation that the associated files are present or checks have been reproduced. Record any subsequent verification with actual commands, hashes, outputs and dates.

## Entries (append chronologically below)

<!-- Use the entry format in ../CLAUDE.md. Do not overwrite past entries. -->

## 2026-10-24 ~02:30–04:45 UTC — researcher with planning chat (not Claude Code) — VM and repository setup

**Assignment / authorization:** Done by Nick directly on the VM, guided by the planning chat.
**Built or changed:** System packages updated (`apt upgrade`); boot disk enlarged to 100 GB (96 GB root, about 59 GB free); `gh` and `tmux` installed; Claude Code updated to 2.1.310; `~/collusion-verification-gap/` created with `git init -b main`; repository-local Git identity `Nick-is-building` with GitHub noreply address; `origin` set to `https://github.com/Nick-is-building/AI-collusion-project.git`; repository visibility changed from public to private.
**Decisions:** Repository private until submission; public before submission (plan §11, milestone 6).
**Checks performed:** `gh repo view … --json visibility` returned PRIVATE (reported by Nick). Plan file transferred and checked by size and SHA-256 for version 2.2.1; later replaced by Nick with version 2.5 (not re-hashed in this entry).
**Did not work:** `gh repo edit --accept-visibility-change-consequences` unsupported by the installed `gh`; plain `--visibility private` worked. Claude Code self-update failed without `sudo`; `sudo npm install -g @anthropic-ai/claude-code@latest` worked.
**Evidence / artifacts:** none in the repository.
**State / limitations:** Not checked: whether `origin/main` already contains commits (repository may have been created with a README or license). No Python environment, dataset, or upstream code yet.
**Next:** First Claude Code assignment from the researcher.
**Cross-references:** `CLAUDE.md` (workspace boundary, Git rules, resilience).

