# DECISIONS.md — Warden

One entry per decision that reopens, amends, or adds to the locks in `CONTEXT.md`. Pre-map locks 1–12 remain recorded in `CONTEXT.md`; this file starts from the first reopen (2026-10-11).

---

## 1. Lock 7 reopened — Docker is the only containment adapter (2026-10-11)

**Status:** Accepted. **Reopens:** lock 7 ("One sandbox port, adapter routes itself" — subprocess for code/shell/file tools).

**Decision.** The subprocess adapter is dropped. Everything the sandbox runs goes through Docker: `--network=none`, read-only rootfs, tmpfs scratch, 30s / 256MB / 1 CPU caps, `--rm`, single bind mount (configured workspace dir, default `D:\tmp\`). API tools stay in-process.

**Context.** The sandbox slice was extended to promise *network isolation* of tool execution. On Windows there are no network namespaces available to a bare subprocess — a genuine egress kill requires a container (or a Linux VM). Subprocess + scrubbed env + timeout cannot honestly claim "no network."

**Alternatives considered.**
- *Keep subprocess, weaken the claim to "network isolation best-effort"* — rejected: a governance product cannot ship a containment promise it can't keep; judges (and threat models) read "best-effort" as a hole.
- *Keep Docker parked until judges demand it* — rejected: the demand arrived as a product requirement (network isolation), not a demo flourish.
- *Linux VM per tool call* — rejected: heavyweight, slow, far beyond hackathon scope; Docker already installed (Docker Desktop 29.6.2, WSL2 backend).

**Consequences.**
- `SandboxPort` interface unchanged: `run(action) -> SandboxResult`, async; one exception type `SandboxUnavailable` for daemon-down / missing image / unknown tool profile (fail-closed; executor maps to `Error(governance_unavailable)`).
- Tool → execution profile mapping lives in a registry *inside* the sandbox package; the future GuardedExecutor classifier decides *whether* to sandbox, the sandbox decides *how*.
- Execution mode per profile: `exec` (argv, default) or `shell` (`sh -c` inside container, shell tool only). Host side always argv to `docker`, no shell, ever.
- Unknown tool profile → `SandboxUnavailable` (refuse, never run unprofiled), overriding an earlier C′ "default-strict profile" proposal — see wayfinder map notes.
- Separate decisions recorded alongside: 30s/256MB/1CPU defaults, `D:\tmp\` as the single accessible host folder, shared-across-runs noted as Phase-1 accepted risk.

**Maps to:** wayfinder map "Network isolation & sandboxed tool execution service" (GitHub issues, `wayfinder:map`).
