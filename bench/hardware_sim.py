"""Simulated pump hardware: stepper-driven syringe drive plus sensors.

The bench can inject sensor values (line pressure, door switch, syringe
presence) the way a HiL system or a physical test fixture would.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SyringeDriveSim:
    step_ml: float = 0.0005          # plunger travel per motor step, in mL
    gain_error: float = 0.005        # +0.5 % mechanical delivery error
    _commanded_ml_h: float = 0.0
    _steps: int = 0
    _fraction: float = 0.0
    motor_log: list[tuple[int, float]] = field(default_factory=list)

    def command(self, now_ms: int, ml_per_h: float) -> None:
        if ml_per_h != self._commanded_ml_h:
            self.motor_log.append((now_ms, ml_per_h))
        self._commanded_ml_h = ml_per_h

    def advance(self, dt_ms: int) -> None:
        actual = self._commanded_ml_h * (1 + self.gain_error)
        travel = actual * dt_ms / 3_600_000 / self.step_ml + self._fraction
        whole = int(travel)
        self._steps += whole
        self._fraction = travel - whole

    @property
    def plunger_ml(self) -> float:
        return self._steps * self.step_ml

    @property
    def running(self) -> bool:
        return self._commanded_ml_h > 0


@dataclass
class PumpHardwareSim:
    """Implements firmware.pump_firmware.HardwareIO."""

    drive: SyringeDriveSim = field(default_factory=SyringeDriveSim)
    pressure_kpa: float = 20.0
    door_is_closed: bool = True
    syringe_is_present: bool = True
    syringe_ml: float = 50.0
    now_ms: int = 0

    def read_pressure_kpa(self) -> float:
        return self.pressure_kpa

    def door_closed(self) -> bool:
        return self.door_is_closed

    def syringe_present(self) -> bool:
        return self.syringe_is_present

    def syringe_volume_ml(self) -> float:
        return self.syringe_ml

    def read_plunger_ml(self) -> float:
        return self.drive.plunger_ml

    def set_motor_rate(self, ml_per_h: float) -> None:
        self.drive.command(self.now_ms, ml_per_h)
