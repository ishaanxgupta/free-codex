"""Managed Codex diagnostic classification."""

from dataclasses import dataclass

_BENIGN_STDERR_MARKERS = (
    "failed to clean up stale arg0 temp dirs",
    "proceeding, even though we could not update path",
)


@dataclass(frozen=True, slots=True)
class ManagedCodexStderrDiagnostics:
    """Classified stderr lines from one managed Codex invocation."""

    benign_lines: tuple[str, ...]
    fatal_lines: tuple[str, ...]

    @property
    def fatal_text(self) -> str | None:
        text = "\n".join(self.fatal_lines).strip()
        return text or None

    @property
    def has_benign(self) -> bool:
        return bool(self.benign_lines)


def classify_managed_codex_stderr(
    stderr_text: str,
) -> ManagedCodexStderrDiagnostics:
    """Classify known benign Codex diagnostics separately from failures."""
    benign_lines: list[str] = []
    fatal_lines: list[str] = []
    for line in _stderr_lines(stderr_text):
        lowered = line.lower()
        if any(marker in lowered for marker in _BENIGN_STDERR_MARKERS):
            benign_lines.append(line)
        else:
            fatal_lines.append(line)
    return ManagedCodexStderrDiagnostics(
        benign_lines=tuple(benign_lines),
        fatal_lines=tuple(fatal_lines),
    )


def _stderr_lines(stderr_text: str) -> tuple[str, ...]:
    stripped = stderr_text.strip()
    if not stripped:
        return ()
    return tuple(line.strip() for line in stripped.splitlines() if line.strip())
