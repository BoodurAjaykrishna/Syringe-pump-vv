"""Device under test: control software of a fictional syringe infusion pump.

This is a simplified model written for a verification portfolio. It is NOT
real medical device software. Software safety class B (IEC 62304) is assumed
for the verification exercise.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from firmware.protocol import (
    HIGH_PRIORITY, ID_HOST_HEARTBEAT, ID_PUMP_ALARM, ID_PUMP_CMD,
    ID_PUMP_CMD_RESP, ID_PUMP_STATUS, Alarm, CanFrame, Cmd, Result, State,
    decode_cmd, encode_alarm, encode_resp, encode_status,
)

RATE_MIN_01, RATE_MAX_01 = 1, 5000        # 0.1 .. 500.0 mL/h
VTBI_MIN_01, VTBI_MAX_01 = 1, 10000       # 0.1 .. 1000.0 mL


@dataclass
class PumpConfig:
    occlusion_threshold_kpa: float = 100.0
    occlusion_debounce_ms: int = 300       # pressure must stay high this long
    comm_timeout_ms: int = 1000
    near_empty_ml: float = 2.0
    status_period_ms: int = 100


class HardwareIO(Protocol):
    """Interface to the pump hardware (implemented by the test bench)."""

    def read_pressure_kpa(self) -> float: ...
    def door_closed(self) -> bool: ...
    def syringe_present(self) -> bool: ...
    def syringe_volume_ml(self) -> float: ...
    def read_plunger_ml(self) -> float: ...
    def set_motor_rate(self, ml_per_h: float) -> None: ...


class CanPort(Protocol):
    def send(self, frame: CanFrame) -> None: ...
    def receive(self) -> list[CanFrame]: ...


class PumpFirmware:
    def __init__(self, hw: HardwareIO, port: CanPort, config: PumpConfig | None = None):
        self.hw = hw
        self.port = port
        self.cfg = config or PumpConfig()
        self.state = State.IDLE
        self.alarms = Alarm.NONE
        self.rate_01 = 0
        self.vtbi_01 = 0
        self._start_plunger_ml = 0.0
        self._delivered_before_ml = 0.0
        self._occlusion_onset_ms: int | None = None
        self._last_heartbeat_ms: int | None = None
        self._next_status_ms = 0
        self._now = 0

    # ------------------------------------------------------------------ helpers
    @property
    def delivered_ml(self) -> float:
        if self.state == State.INFUSING:
            return self._delivered_before_ml + self.hw.read_plunger_ml() - self._start_plunger_ml
        return self._delivered_before_ml

    def _send(self, frame_id: int, data: bytes) -> None:
        self.port.send(CanFrame(frame_id, data, self._now, sender="pump"))

    def _motor(self, on: bool) -> None:
        self.hw.set_motor_rate(self.rate_01 / 10.0 if on else 0.0)

    def _freeze_delivery(self) -> None:
        """Bank the volume delivered in the current run before the motor stops."""
        if self.state == State.INFUSING:
            self._delivered_before_ml += self.hw.read_plunger_ml() - self._start_plunger_ml

    def _raise(self, alarm: Alarm) -> None:
        if not self.alarms & alarm:
            self._send(ID_PUMP_ALARM, encode_alarm(alarm))
        self.alarms |= alarm
        if alarm & HIGH_PRIORITY and self.state in (State.INFUSING, State.PAUSED):
            self._freeze_delivery()
            self._motor(False)
            self.state = State.ALARM

    # ------------------------------------------------------------------ commands
    def _handle_cmd(self, cmd: int, value: int) -> Result:
        if cmd == Cmd.SET_RATE:
            if not RATE_MIN_01 <= value <= RATE_MAX_01:
                return Result.RATE_OUT_OF_RANGE
            self.rate_01 = value
            if self.state == State.INFUSING:
                self._motor(True)
            return Result.OK

        if cmd == Cmd.SET_VTBI:
            if not VTBI_MIN_01 <= value <= VTBI_MAX_01:
                return Result.VTBI_OUT_OF_RANGE
            self.vtbi_01 = value
            return Result.OK

        if cmd == Cmd.START:
            if self.state not in (State.IDLE, State.COMPLETE):
                return Result.INVALID_STATE
            if (not self.rate_01 or not self.vtbi_01 or not self.hw.door_closed()
                    or not self.hw.syringe_present() or self.alarms & HIGH_PRIORITY):
                return Result.NOT_READY
            self._delivered_before_ml = 0.0
            self._occlusion_onset_ms = None
            self._start_plunger_ml = self.hw.read_plunger_ml()
            self.state = State.INFUSING
            self._motor(True)
            return Result.OK

        if cmd == Cmd.STOP:
            self._freeze_delivery()
            self._motor(False)
            self.state = State.IDLE
            return Result.OK

        if cmd == Cmd.PAUSE:
            if self.state != State.INFUSING:
                return Result.INVALID_STATE
            self._freeze_delivery()
            self._motor(False)
            self.state = State.PAUSED
            return Result.OK

        if cmd == Cmd.RESUME:
            if self.state != State.PAUSED:
                return Result.INVALID_STATE
            if not self.hw.door_closed() or self.alarms & HIGH_PRIORITY:
                return Result.NOT_READY
            self._occlusion_onset_ms = None
            self._start_plunger_ml = self.hw.read_plunger_ml()
            self.state = State.INFUSING
            self._motor(True)
            return Result.OK

        if cmd == Cmd.ACK_ALARM:
            # Clear only alarms whose cause is gone. Never restart the motor:
            # after a high-priority alarm the pump waits in PAUSED for RESUME.
            if self.alarms & Alarm.DOOR_OPEN and self.hw.door_closed():
                self.alarms &= ~Alarm.DOOR_OPEN
            if self.alarms & Alarm.OCCLUSION and self.hw.read_pressure_kpa() <= self.cfg.occlusion_threshold_kpa:
                self.alarms &= ~Alarm.OCCLUSION
            if self.alarms & Alarm.COMM_LOSS and self._host_alive():
                self.alarms &= ~Alarm.COMM_LOSS
            if self.alarms & HIGH_PRIORITY:
                return Result.NOT_READY
            if self.state == State.ALARM:
                self.state = State.PAUSED
            return Result.OK

        return Result.UNKNOWN_COMMAND

    def _host_alive(self) -> bool:
        return (self._last_heartbeat_ms is not None
                and self._now - self._last_heartbeat_ms <= self.cfg.comm_timeout_ms)

    # ------------------------------------------------------------------ main loop
    def tick(self, now_ms: int) -> None:
        """One pass of the control loop (called every 10 ms by the scheduler)."""
        self._now = now_ms

        for frame in self.port.receive():
            if frame.arbitration_id == ID_HOST_HEARTBEAT:
                self._last_heartbeat_ms = now_ms
            elif frame.arbitration_id == ID_PUMP_CMD:
                cmd, value = decode_cmd(frame.data)
                result = self._handle_cmd(cmd, value)
                self._send(ID_PUMP_CMD_RESP, encode_resp(cmd, result))

        if self.state == State.INFUSING:
            self._supervise(now_ms)

        remaining = self.hw.syringe_volume_ml() - self.hw.read_plunger_ml()
        if self.hw.syringe_present() and remaining < self.cfg.near_empty_ml:
            self._raise(Alarm.NEAR_EMPTY)
        else:
            self.alarms &= ~Alarm.NEAR_EMPTY

        if now_ms >= self._next_status_ms:
            delivered_ul = max(0, round(self.delivered_ml * 1000))
            self._send(ID_PUMP_STATUS, encode_status(self.state, self.alarms, self.rate_01, delivered_ul))
            self._next_status_ms += self.cfg.status_period_ms

    def _supervise(self, now_ms: int) -> None:
        if not self.hw.door_closed():
            self._raise(Alarm.DOOR_OPEN)
            return

        if self.hw.read_pressure_kpa() > self.cfg.occlusion_threshold_kpa:
            if self._occlusion_onset_ms is None:
                self._occlusion_onset_ms = now_ms
            elif now_ms - self._occlusion_onset_ms >= self.cfg.occlusion_debounce_ms:
                self._raise(Alarm.OCCLUSION)
                return
        else:
            self._occlusion_onset_ms = None

        if not self._host_alive() and self._last_heartbeat_ms is not None:
            self._raise(Alarm.COMM_LOSS)
            return

        if self.delivered_ml >= self.vtbi_01 / 10.0:
            self._freeze_delivery()
            self._motor(False)
            self.state = State.COMPLETE
