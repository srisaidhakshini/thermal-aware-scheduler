"""Small deterministic thermal model for simulated CPU cores."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ThermalModel:
    """Linear heating while busy and linear cooling while idle.

    Temperature is clamped to the configured ambient and maximum values.  The
    rates are intentionally visible parameters so workload experiments can
    compare different thermal assumptions.
    """

    ambient_temperature: float = 35.0
    maximum_temperature: float = 100.0
    heating_rate: float = 1.8
    cooling_rate: float = 0.7

    def advance(self, temperature: float, elapsed: float, busy: bool) -> float:
        """Return the core temperature after ``elapsed`` time units."""
        if elapsed < 0:
            raise ValueError("elapsed time cannot be negative")
        if busy:
            updated = temperature + self.heating_rate * elapsed
        else:
            updated = temperature - self.cooling_rate * elapsed
        return min(self.maximum_temperature, max(self.ambient_temperature, updated))
