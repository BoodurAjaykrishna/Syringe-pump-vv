"""Alarm handling and safe states (risk controls RC-03 .. RC-07)."""
import pytest

from firmware.protocol import ID_HOST_HEARTBEAT, Alarm, Cmd, Result, State


def _trigger_occlusion(bench):
    bench.start_infusion(rate_ml_h=100.0, vtbi_ml=100.0)
    bench.run(2000)
    onset = bench.now_ms
    bench.hw.pressure_kpa = 150.0
    bench.run(3000)
    return onset


@pytest.mark.verifies("SRS-006")
def test_occlusion_stops_motor_within_1s(bench):
    """TC-020 Sustained occlusion stops the motor and raises OCCLUSION within 1000 ms."""
    onset = _trigger_occlusion(bench)
    stop = bench.motor_stop_time_after(onset)
    assert stop is not None, "motor never stopped"
    assert stop - onset <= 1000, f"motor stopped {stop - onset} ms after occlusion onset (limit 1000 ms)"
    events = [(t, a, p) for t, a, p in bench.alarm_events() if a == Alarm.OCCLUSION]
    assert events and events[0][0] - onset <= 1000
    assert events[0][2] == 2, "occlusion must be high priority"
    assert bench.last_status()["state"] == State.ALARM


@pytest.mark.verifies("SRS-006")
@pytest.mark.parametrize("peak_ms", [100, 250])
def test_short_pressure_peak_does_not_alarm(bench, peak_ms):
    """TC-021 Pressure peaks shorter than 300 ms do not raise a false occlusion alarm."""
    bench.start_infusion(rate_ml_h=100.0, vtbi_ml=100.0)
    bench.run(1000)
    bench.hw.pressure_kpa = 150.0
    bench.run(peak_ms)
    bench.hw.pressure_kpa = 20.0
    bench.run(2000)
    assert not bench.alarm_events()
    assert bench.motor_running


@pytest.mark.verifies("SRS-007")
def test_door_open_stops_motor_within_100ms(bench):
    """TC-022 Opening the door during infusion stops the motor within 100 ms."""
    bench.start_infusion(rate_ml_h=100.0, vtbi_ml=100.0)
    bench.run(1000)
    opened = bench.now_ms
    bench.hw.door_is_closed = False
    bench.run(500)
    stop = bench.motor_stop_time_after(opened)
    assert stop is not None and stop - opened <= 100
    assert bench.last_status()["alarms"] & Alarm.DOOR_OPEN
    assert bench.last_status()["state"] == State.ALARM


@pytest.mark.verifies("SRS-008")
def test_near_empty_warns_and_continues(bench):
    """TC-023 Near-empty raises a low-priority alarm and the infusion continues."""
    bench.hw.syringe_ml = 5.0
    bench.start_infusion(rate_ml_h=500.0, vtbi_ml=4.5)
    hit = bench.run_until(lambda: bool(bench.pump.alarms & Alarm.NEAR_EMPTY), timeout_ms=40_000)
    assert hit is not None, "NEAR_EMPTY never raised"
    remaining = bench.hw.syringe_ml - bench.measured_volume_ml
    assert remaining < 2.0 and remaining > 1.9, f"raised at {remaining:.3f} mL remaining"
    bench.run(500)
    assert bench.motor_running and bench.pump.state == State.INFUSING
    events = [(a, p) for _, a, p in bench.alarm_events() if a == Alarm.NEAR_EMPTY]
    assert events == [(Alarm.NEAR_EMPTY, 1)]


@pytest.mark.verifies("SRS-010")
def test_heartbeat_loss_enters_safe_state(bench):
    """TC-024 Missing host heartbeat for more than 1000 ms stops the motor (COMM_LOSS)."""
    bench.start_infusion(rate_ml_h=100.0, vtbi_ml=100.0)
    bench.run(1000)
    bench.heartbeat_enabled = False
    bench.run(2000)
    last_hb = max(f.timestamp_ms for f in bench.bus.trace if f.arbitration_id == ID_HOST_HEARTBEAT)
    stop = bench.motor_stop_time_after(last_hb)
    assert stop is not None, "motor kept running without host"
    assert 1000 < stop - last_hb <= 1100
    assert bench.last_status()["alarms"] & Alarm.COMM_LOSS


@pytest.mark.verifies("SRS-010")
def test_steady_heartbeat_no_comm_loss(bench):
    """TC-025 With a steady heartbeat no COMM_LOSS is raised over 30 s."""
    bench.start_infusion(rate_ml_h=100.0, vtbi_ml=100.0)
    bench.run(30_000)
    assert not bench.pump.alarms & Alarm.COMM_LOSS
    assert bench.motor_running


@pytest.mark.verifies("SRS-011")
def test_no_automatic_restart_after_alarm(bench):
    """TC-026 After acknowledging an alarm the pump waits in PAUSED until RESUME."""
    _trigger_occlusion(bench)
    bench.hw.pressure_kpa = 20.0
    assert bench.command(Cmd.ACK_ALARM) == Result.OK
    bench.run(2000)
    assert bench.pump.state == State.PAUSED
    assert not bench.motor_running
    assert bench.command(Cmd.RESUME) == Result.OK
    bench.run(200)
    assert bench.motor_running and bench.pump.state == State.INFUSING


@pytest.mark.verifies("SRS-011")
def test_alarm_stays_latched_while_cause_present(bench):
    """TC-027 Acknowledge is refused and the alarm stays active while the occlusion persists."""
    _trigger_occlusion(bench)
    assert bench.command(Cmd.ACK_ALARM) == Result.NOT_READY
    assert bench.pump.alarms & Alarm.OCCLUSION
    assert bench.command(Cmd.RESUME) == Result.INVALID_STATE
    assert not bench.motor_running
