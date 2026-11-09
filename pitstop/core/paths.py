"""Layout of pitstop's working directory."""
import os
from pathlib import Path
from typing import Mapping, Optional

ENV_HOME = "PITSTOP_HOME"
ENV_CONFIG_DIR = "CLAUDE_CONFIG_DIR"


def pitstop_home(env: Optional[Mapping[str, str]] = None, home: Optional[Path] = None) -> Path:
    """PITSTOP_HOME if set. Otherwise one folder per Claude account: `$CLAUDE_CONFIG_DIR/pitstop`, unless that
    folder does not exist yet and `~/.claude/pitstop` does (data from before 0.3 stays where it is). Without
    CLAUDE_CONFIG_DIR, `~/.claude/pitstop`."""
    env = os.environ if env is None else env
    home = Path.home() if home is None else home
    override = env.get(ENV_HOME)
    if override:
        return Path(override)
    legacy = home / ".claude" / "pitstop"
    config_dir = env.get(ENV_CONFIG_DIR)
    if config_dir:
        own = Path(config_dir).expanduser() / "pitstop"
        if own.is_dir() or not legacy.is_dir():
            return own
    return legacy


class Layout:
    """Paths inside the working directory. Nothing is created here."""

    def __init__(self, base: Path) -> None:
        self.base = base
        self.config = base / "config.json"
        self.state_dir = base / "state"
        self.pending_dir = base / "pending"
        self.checkpoints_dir = base / "checkpoints"
        self.log = base / "log.jsonl"
        self.gaps = base / "gaps.jsonl"
        self.metrics = base / "metrics.jsonl"
        self.report_stamp = base / "report-last-run.txt"
        self.config_notice = base / "config-notice.txt"
        self.reviews_dir = base / "reviews"
        self.reviews_log = base / "reviews.jsonl"
        self.review_reminder_stamp = base / "review-reminder-last.txt"
