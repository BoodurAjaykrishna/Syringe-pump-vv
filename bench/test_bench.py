"""Test bench: wires the device under test to simulated hardware and a CAN host.

Plays the role of the HiL rack / test fixture: a 10 ms scheduler, a host node
that sends commands and heartbeats, and fault injection on the sensors.
"""
from __future__ import annotations

from typing import Callable

from bench.hardware_sim import PumpHardwareSim
from bench.virtual_bus import VirtualCanBus
from firmware.protocol import (
    ID_HOST_HEARTBEAT, ID_PUMP_ALARM, ID_PUMP_CMD, ID_PUMP_CMD_RESP,
    ID_PUMP_STATUS, Alarm, CanFrame, Cmd, Result, decode_alarm, decode_resp,
    decode_status, encode_cmd,
)
from firmware.pump_firmware import PumpConfig, PumpFirmware

TICK_MS = 10
HEARTBEAT_PERIOD_MS = 200


class PumpTestBench:
    def __init__(self, config: PumpConfig | None = None, syringe_ml: float = 50.0) -> None:
        self.now_ms = 0
        self.hw = PumpHardwareSim(syringe_ml=syringe_ml)
        self.bus = VirtualCanBus()
        self.host = self.bus.attach("host")
        self.pump = PumpFirmware(self.hw, self.bus.attach("pump"), config)
        self.heartbeat_enabled = True
        self._hb_counter = 0
        self.rx: list[CanFrame] = []

    # ------------------------------------------------------------- scheduling
    def step(self) -> None:
        self.hw.now_ms = self.now_ms
        if self.heartbeat_enabled and self.now_ms % HEARTBEAT_PERIOD_MS == 0:
            self.host.send(CanFrame(ID_HOST_HEARTBEAT, bytes([self._hb_counter & 0xFF]), self.now_ms))
            self._hb_counter += 1
        self.pump.tick(self.now_ms)
        self.rx.extend(self.host.receive())
        self.hw.drive.advance(TICK_MS)
        self.now_ms += TICK_MS

    def run(self, duration_ms: int) -> None:
        for _ in range(duration_ms // TICK_MS):
            self.step()

    def run_until(self, condition: Callable[[], bool], timeout_ms: int) -> int | None:
        """Run until `condition` holds; return elapsed ms, or None on timeout."""
        start = self.now_ms
        while self.now_ms - start <= timeout_ms:
            if condition():
                return self.now_ms - start
            self.step()
        return None

    # ------------------------------------------------------------- host side
    def command(self, cmd: Cmd, value: int = 0) -> Result:
        sent_at = self.now_ms
        self.host.send(CanFrame(ID_PUMP_CMD, encode_cmd(cmd, value), self.now_ms))
        for _ in range(10):  # response expected within 100 ms
            self.step()
            for f in self.rx:
                if f.arbitration_id == ID_PUMP_CMD_RESP and f.timestamp_ms >= sent_at:
                    echoed, result = decode_resp(f.data)
                    if echoed == cmd:
                        return result
        raise TimeoutError(f"no response to {cmd.name} within 100 ms")

    def start_infusion(self, rate_ml_h: float, vtbi_ml: float) -> None:
        assert self.command(Cmd.SET_RATE, round(rate_ml_h * 10)) == Result.OK
        assert self.command(Cmd.SET_VTBI, round(vtbi_ml * 10)) == Result.OK
        assert self.command(Cmd.START) == Result.OK

    # ------------------------------------------------------------- observations
    def statuses(self) -> list[tuple[int, dict]]:
        return [(f.timestamp_ms, decode_status(f.data)) for f in self.rx if f.arbitration_id == ID_PUMP_STATUS]

    def last_status(self) -> dict:
        return self.statuses()[-1][1]

    def alarm_events(self) -> list[tuple[int, Alarm, int]]:
        return [(f.timestamp_ms, *decode_alarm(f.data)) for f in self.rx if f.arbitration_id == ID_PUMP_ALARM]

    def motor_stop_time_after(self, t_ms: int) -> int | None:
        for when, rate in self.hw.drive.motor_log:
            if when >= t_ms and rate == 0:
                return when
        return None

    @property
    def motor_running(self) -> bool:
        return self.hw.drive.running

    @property
    def measured_volume_ml(self) -> float:
        """Reference measurement (in a lab: gravimetric scale)."""
        return self.hw.drive.plunger_ml
