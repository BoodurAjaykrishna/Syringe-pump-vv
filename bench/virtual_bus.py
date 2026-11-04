"""Minimal virtual CAN bus with trace logging in Vector ASC format.

On a physical bench this is replaced by a CAN interface (Vector VN16xx via
python-can, or CANoe itself). The test code only uses `send` / `receive`,
so swapping the transport does not change the tests.
"""
from __future__ import annotations

from collections import deque
from pathlib import Path

from firmware.protocol import CanFrame


class VirtualCanBus:
    def __init__(self) -> None:
        self._nodes: dict[str, deque[CanFrame]] = {}
        self.trace: list[CanFrame] = []

    def attach(self, name: str) -> "BusPort":
        self._nodes[name] = deque()
        return BusPort(self, name)

    def _broadcast(self, frame: CanFrame) -> None:
        self.trace.append(frame)
        for name, queue in self._nodes.items():
            if name != frame.sender:
                queue.append(frame)

    def write_asc(self, path: Path) -> None:
        """Write the trace as a Vector ASC log (opens in CANoe/CANalyzer)."""
        lines = [
            "date Wed Nov 4 00:00:00.000 2026",
            "base hex  timestamps absolute",
            "internal events logged",
            "Begin Triggerblock",
        ]
        for f in self.trace:
            direction = "Tx" if f.sender == "pump" else "Rx"
            payload = " ".join(f"{b:02X}" for b in f.data)
            lines.append(f"{f.timestamp_ms / 1000:11.6f} 1  {f.arbitration_id:X}{'':13}{direction}   d {len(f.data)} {payload}")
        lines.append("End TriggerBlock")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n")


class BusPort:
    def __init__(self, bus: VirtualCanBus, name: str) -> None:
        self._bus = bus
        self.name = name

    def send(self, frame: CanFrame) -> None:
        self._bus._broadcast(CanFrame(frame.arbitration_id, frame.data, frame.timestamp_ms, self.name))

    def receive(self) -> list[CanFrame]:
        queue = self._bus._nodes[self.name]
        frames = list(queue)
        queue.clear()
        return frames
