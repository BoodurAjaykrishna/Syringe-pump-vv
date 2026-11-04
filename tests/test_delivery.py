"""Delivery: accuracy, end of infusion, pause and resume."""
import pytest

from firmware.protocol import Cmd, Result, State


@pytest.mark.verifies("SRS-004")
@pytest.mark.parametrize("rate_ml_h", [1.0, 25.0, 100.0, 500.0])
def test_delivery_accuracy(bench, rate_ml_h):
    """TC-010 Delivered volume within +/-2 % over 10 min (low, mid, high, max rate)."""
    bench.start_infusion(rate_ml_h=rate_ml_h, vtbi_ml=1000.0)
    start = bench.measured_volume_ml
    bench.run(10 * 60 * 1000)
    measured = bench.measured_volume_ml - start
    expected = rate_ml_h * 10 / 60
    error_pct = (measured - expected) / expected * 100
    assert abs(error_pct) <= 2.0, f"error {error_pct:+.2f} % (measured {measured:.4f} mL, expected {expected:.4f} mL)"


@pytest.mark.verifies("SRS-005")
def test_stops_at_vtbi(bench):
    """TC-011 Motor stops at VTBI with over-delivery of at most 0.02 mL."""
    bench.start_infusion(rate_ml_h=500.0, vtbi_ml=5.0)
    elapsed = bench.run_until(lambda: bench.pump.state == State.COMPLETE, timeout_ms=60_000)
    assert elapsed is not None, "infusion did not complete"
    bench.run(1000)
    assert not bench.motor_running
    assert 5.0 <= bench.measured_volume_ml <= 5.02
    assert bench.last_status()["state"] == State.COMPLETE


@pytest.mark.verifies("SRS-012")
def test_pause_stops_motor_and_resume_completes(bench):
    """TC-012 Pause stops the motor within 100 ms; resume still ends at VTBI."""
    bench.start_infusion(rate_ml_h=360.0, vtbi_ml=2.0)
    bench.run(5000)

    paused_at = bench.now_ms
    assert bench.command(Cmd.PAUSE) == Result.OK
    stop = bench.motor_stop_time_after(paused_at)
    assert stop is not None and stop - paused_at <= 100

    volume_at_pause = bench.measured_volume_ml
    bench.run(3000)
    assert bench.measured_volume_ml == volume_at_pause, "volume moved while paused"

    assert bench.command(Cmd.RESUME) == Result.OK
    assert bench.run_until(lambda: bench.pump.state == State.COMPLETE, timeout_ms=60_000) is not None
    assert 2.0 <= bench.measured_volume_ml <= 2.02
