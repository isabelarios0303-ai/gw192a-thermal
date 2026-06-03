"""Infant temperature alert engine.

Thresholds (Celsius), per the product spec:

  Body temperature
    normal   : 36.5 - 37.5
    warning  : < 36.5  or  > 37.5
    critical : < 36.0  or  >= 38.0

  Ambient temperature
    normal   : 20 - 24
    cold     : < 20
    hot      : > 24

The engine is hysteresis-aware: it only *re-fires* an alert when the level changes or after a
debounce window, so caregivers are not spammed by per-frame oscillation near a threshold.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

LEVELS = ("ok", "warning", "critical")
_LEVEL_RANK = {"ok": 0, "warning": 1, "critical": 2}


@dataclass(slots=True)
class AlertResult:
    level: str
    code: str
    message: str
    value: float

    def to_dict(self) -> dict:
        return {"level": self.level, "code": self.code, "message": self.message,
                "value": round(self.value, 3)}


# --- thresholds -----------------------------------------------------------------------
BODY_NORMAL_LOW = 36.5
BODY_NORMAL_HIGH = 37.5
BODY_CRIT_LOW = 36.0
BODY_CRIT_HIGH = 38.0
AMBIENT_NORMAL_LOW = 20.0
AMBIENT_NORMAL_HIGH = 24.0


def evaluate_body(temp_c: float) -> AlertResult:
    if temp_c >= BODY_CRIT_HIGH:
        return AlertResult("critical", "BODY_CRIT_HIGH", "Temperatura crítica", temp_c)
    if temp_c < BODY_CRIT_LOW:
        return AlertResult("critical", "BODY_CRIT_LOW", "Temperatura crítica (hipotermia)", temp_c)
    if temp_c > BODY_NORMAL_HIGH:
        return AlertResult("warning", "BODY_WARN_HIGH", "Temperatura elevada (posible fiebre)", temp_c)
    if temp_c < BODY_NORMAL_LOW:
        return AlertResult("warning", "BODY_WARN_LOW", "Hipotermia potencial", temp_c)
    return AlertResult("ok", "BODY_OK", "Temperatura corporal normal", temp_c)


def evaluate_ambient(temp_c: float) -> AlertResult:
    if temp_c < AMBIENT_NORMAL_LOW:
        return AlertResult("warning", "AMB_COLD", "Ambiente muy frío", temp_c)
    if temp_c > AMBIENT_NORMAL_HIGH:
        return AlertResult("warning", "AMB_HOT", "Ambiente muy caliente", temp_c)
    return AlertResult("ok", "AMB_OK", "Ambiente normal", temp_c)


@dataclass
class AlertEngine:
    """Stateful evaluator with debounce so alerts only re-fire on meaningful change."""

    debounce_seconds: float = 15.0
    _last: dict[str, tuple[str, float]] = field(default_factory=dict)

    def _should_emit(self, channel: str, level: str) -> bool:
        now = time.monotonic()
        prev = self._last.get(channel)
        if prev is None or prev[0] != level or (now - prev[1]) >= self.debounce_seconds:
            self._last[channel] = (level, now)
            return True
        return False

    def evaluate(self, body_peak_c: float, ambient_c: float) -> list[AlertResult]:
        """Return the alerts that should be *emitted* this frame (after debounce)."""
        out: list[AlertResult] = []
        body = evaluate_body(body_peak_c)
        if body.level != "ok" and self._should_emit("body", body.level):
            out.append(body)
        amb = evaluate_ambient(ambient_c)
        if amb.level != "ok" and self._should_emit("ambient", amb.level):
            out.append(amb)
        return out

    @staticmethod
    def status(body_peak_c: float, ambient_c: float) -> list[AlertResult]:
        """Stateless current status of both channels (for live indicators)."""
        return [evaluate_body(body_peak_c), evaluate_ambient(ambient_c)]
