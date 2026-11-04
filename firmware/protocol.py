"""CAN protocol of the syringe pump (mirrors dbc/syringe_pump.dbc).

11-bit identifiers, 8-byte payloads, little-endian (Intel) signals.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum, IntFlag

# Message identifiers
ID_HOST_HEARTBEAT = 0x080   # host -> pump, every 200 ms
ID_PUMP_CMD = 0x100         # host -> pump
ID_PUMP_STATUS = 0x101      # pump -> host, every 100 ms
ID_PUMP_CMD_RESP = 0x102    # pump -> host, one per command
ID_PUMP_ALARM = 0x103       # pump -> host, on alarm raise


class Cmd(IntEnum):
    SET_RATE = 1      # value: rate in 0.1 mL/h
    SET_VTBI = 2      # value: volume to be infused in 0.1 mL
    START = 3
    STOP = 4
    PAUSE = 5
    RESUME = 6
    ACK_ALARM = 7


class Result(IntEnum):
    OK = 0
    RATE_OUT_OF_RANGE = 1
    VTBI_OUT_OF_RANGE = 2
    NOT_READY = 3
    INVALID_STATE = 4
    UNKNOWN_COMMAND = 5


class State(IntEnum):
    IDLE = 0
    INFUSING = 1
    PAUSED = 2
    ALARM = 3
    COMPLETE = 4


class Alarm(IntFlag):
    NONE = 0
    OCCLUSION = 0x01      # high priority, latched
    DOOR_OPEN = 0x02      # high priority, latched
    NEAR_EMPTY = 0x04     # low priority, informational
    COMM_LOSS = 0x08      # high priority, latched


HIGH_PRIORITY = Alarm.OCCLUSION | Alarm.DOOR_OPEN | Alarm.COMM_LOSS


@dataclass(frozen=True)
class CanFrame:
    arbitration_id: int
    data: bytes
    timestamp_ms: int = 0
    sender: str = ""

    def __post_init__(self):
        if not 0 <= self.arbitration_id <= 0x7FF:
            raise ValueError("11-bit identifier expected")
        if len(self.data) > 8:
            raise ValueError("classic CAN payload is at most 8 bytes")


def encode_cmd(cmd: int, value: int = 0) -> bytes:
    return struct.pack("<BI3x", cmd, value)


def decode_cmd(data: bytes) -> tuple[int, int]:
    cmd, value = struct.unpack("<BI3x", data)
    return cmd, value


def encode_status(state: State, alarms: Alarm, rate_01: int, delivered_ul: int) -> bytes:
    return struct.pack("<BBHI", int(state), int(alarms), rate_01, delivered_ul)


def decode_status(data: bytes) -> dict:
    state, alarms, rate_01, delivered_ul = struct.unpack("<BBHI", data)
    return {
        "state": State(state),
        "alarms": Alarm(alarms),
        "rate_ml_h": rate_01 / 10.0,
        "delivered_ml": delivered_ul / 1000.0,
    }


def encode_resp(cmd: int, result: Result) -> bytes:
    return struct.pack("<BB6x", cmd, int(result))


def decode_resp(data: bytes) -> tuple[int, Result]:
    cmd, result = struct.unpack("<BB6x", data)
    return cmd, Result(result)


def encode_alarm(alarm: Alarm) -> bytes:
    priority = 2 if alarm & HIGH_PRIORITY else 1
    return struct.pack("<BB6x", int(alarm), priority)


def decode_alarm(data: bytes) -> tuple[Alarm, int]:
    alarm, priority = struct.unpack("<BB6x", data)
    return Alarm(alarm), priority
