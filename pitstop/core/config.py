"""Configuration: defaults, validation, updates and the one-time invalid-config notice."""
import json
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Tuple

from pitstop.core.fsutil import atomic_write_text
from pitstop.core.paths import Layout


@dataclass(frozen=True)
class Config:
    enabled: bool = True
    notify: bool = True
    threshold_tokens: int = 200000
    retrigger_step_tokens: int = 50000
    resume_window_minutes: int = 60
    metrics: bool = False  # the daily background report and metrics.jsonl
    soft_threshold_tokens: int = 170000  # from here to the threshold: an offer at the end of a turn
    hard_threshold_tokens: int = 280000  # from here on: a pitstop is required
    review_sample: int = 20  # at least this many resumed cycles /pitstop review reads


class ConfigError(Exception):
    """config.json cannot be used. The message is shown to the user."""


_BOOL_KEYS = ("enabled", "notify", "metrics")
_INT_RANGES = {
    "threshold_tokens": (50000, 900000),
    "retrigger_step_tokens": (10000, None),
    "resume_window_minutes": (1, 60),
    "soft_threshold_tokens": (10000, 900000),
    "hard_threshold_tokens": (50000, 2000000),
    "review_sample": (1, 100),
}
_ORDER = "soft_threshold_tokens < threshold_tokens < hard_threshold_tokens"


def _derived_soft(threshold: int) -> int:
    """Default soft limit for a config that sets only the threshold: 30K below it, at least 50K."""
    soft = max(50000, threshold - 30000)
    return soft if soft < threshold else threshold * 3 // 4


def parse_config(raw: Any) -> Config:
    if not isinstance(raw, dict):
        raise ConfigError("the file must contain a JSON object")
    values: Dict[str, Any] = asdict(Config())
    for key in _BOOL_KEYS:
        if key in raw:
            if not isinstance(raw[key], bool):
                raise ConfigError("%s must be true or false" % key)
            values[key] = raw[key]
    for key, (low, high) in _INT_RANGES.items():
        if key not in raw:
            continue
        value = raw[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError("%s must be an integer" % key)
        if value < low or (high is not None and value > high):
            limit = "%d–%d" % (low, high) if high is not None else "≥ %d" % low
            raise ConfigError("%s out of range (%s)" % (key, limit))
        values[key] = value
    if "soft_threshold_tokens" not in raw:
        values["soft_threshold_tokens"] = _derived_soft(values["threshold_tokens"])
    if "hard_threshold_tokens" not in raw:
        values["hard_threshold_tokens"] = values["threshold_tokens"] + 80000
    if not values["soft_threshold_tokens"] < values["threshold_tokens"] < values["hard_threshold_tokens"]:
        raise ConfigError("limits out of order (%s)" % _ORDER)
    return Config(**values)


def load_config(layout: Layout) -> Tuple[Config, Optional[str]]:
    """Missing file: defaults. Unusable file: pitstop disabled, plus the reason."""
    try:
        text = layout.config.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Config(), None
    except OSError as exc:
        return Config(enabled=False), "config.json unreadable (%s)" % exc.strerror
    try:
        return parse_config(json.loads(text)), None
    except ValueError:
        return Config(enabled=False), "config.json is not valid JSON"
    except ConfigError as exc:
        return Config(enabled=False), str(exc)


def update_config(layout: Layout, **changes: Any) -> Config:
    """Apply changes and rewrite config.json in full. Never overwrites a file it cannot parse."""
    try:
        raw = json.loads(layout.config.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raw = {}
    except ValueError:
        raise ConfigError("config.json is not valid JSON: fix or delete it") from None
    if not isinstance(raw, dict):
        raise ConfigError("config.json must contain a JSON object: fix or delete it")
    raw.update(changes)
    config = parse_config(raw)
    # Soft and hard limits the file does not set stay derived from the threshold: written out, they would freeze
    # and a later threshold edit could put the three limits out of order.
    saved = {key: value for key, value in asdict(config).items()
             if key in raw or key not in ("soft_threshold_tokens", "hard_threshold_tokens")}
    atomic_write_text(layout.config, json.dumps(saved, indent=2) + "\n")
    return config


def should_show_config_notice(layout: Layout, error: str) -> bool:
    """True the first time an error is seen for a given version of config.json."""
    try:
        version = str(layout.config.stat().st_mtime_ns)
    except OSError:
        version = "missing"
    key = "%s|%s" % (version, error)
    try:
        if layout.config_notice.read_text(encoding="utf-8") == key:
            return False
    except OSError:
        pass
    atomic_write_text(layout.config_notice, key)
    return True
