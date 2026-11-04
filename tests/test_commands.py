"""Command handling: parameter ranges and start preconditions."""
import pytest

from firmware.protocol import Cmd, Result, State


@pytest.mark.verifies("SRS-001")
@pytest.mark.parametrize("raw, expected", [
    (0, Result.RATE_OUT_OF_RANGE),      # below minimum
    (1, Result.OK),                     # 0.1 mL/h  lower boundary
    (5000, Result.OK),                  # 500.0 mL/h upper boundary
    (5001, Result.RATE_OUT_OF_RANGE),   # above maximum
    (0xFFFFFFFF, Result.RATE_OUT_OF_RANGE),
])
def test_rate_boundaries(bench, raw, expected):
    """TC-001 Rate command accepted only within 0.1-500.0 mL/h (boundary values)."""
    assert bench.command(Cmd.SET_RATE, raw) == expected


@pytest.mark.verifies("SRS-001")
def test_rejected_rate_keeps_active_rate(bench):
    """TC-002 A rejected rate does not change the active infusion rate."""
    bench.start_infusion(rate_ml_h=100.0, vtbi_ml=50.0)
    assert bench.command(Cmd.SET_RATE, 5001) == Result.RATE_OUT_OF_RANGE
    bench.run(200)
    assert bench.last_status()["rate_ml_h"] == 100.0
    assert bench.last_status()["state"] == State.INFUSING


@pytest.mark.verifies("SRS-002")
@pytest.mark.parametrize("raw, expected", [
    (0, Result.VTBI_OUT_OF_RANGE),
    (1, Result.OK),
    (10000, Result.OK),
    (10001, Result.VTBI_OUT_OF_RANGE),
])
def test_vtbi_boundaries(bench, raw, expected):
    """TC-003 VTBI accepted only within 0.1-1000.0 mL (boundary values)."""
    assert bench.command(Cmd.SET_VTBI, raw) == expected


@pytest.mark.verifies("SRS-003")
@pytest.mark.parametrize("condition", ["no_rate", "no_vtbi", "door_open", "no_syringe"])
def test_start_rejected_when_not_ready(bench, condition):
    """TC-004 Start is refused and the motor stays off when a precondition is missing."""
    if condition != "no_rate":
        bench.command(Cmd.SET_RATE, 1000)
    if condition != "no_vtbi":
        bench.command(Cmd.SET_VTBI, 100)
    if condition == "door_open":
        bench.hw.door_is_closed = False
    if condition == "no_syringe":
        bench.hw.syringe_is_present = False

    assert bench.command(Cmd.START) == Result.NOT_READY
    bench.run(500)
    assert not bench.motor_running
    assert bench.last_status()["state"] == State.IDLE


@pytest.mark.verifies("SRS-003")
def test_start_accepted_when_ready(bench):
    """TC-005 Start is accepted when all preconditions are met."""
    bench.start_infusion(rate_ml_h=100.0, vtbi_ml=10.0)
    bench.run(200)
    assert bench.motor_running
    assert bench.last_status()["state"] == State.INFUSING
