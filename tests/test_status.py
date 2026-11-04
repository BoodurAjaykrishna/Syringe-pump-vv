"""Status reporting on CAN."""
import pytest

from firmware.protocol import State


@pytest.mark.verifies("SRS-009")
def test_status_period(bench):
    """TC-030 PUMP_STATUS is sent every 100 ms +/- 10 ms."""
    bench.start_infusion(rate_ml_h=100.0, vtbi_ml=100.0)
    bench.run(5000)
    times = [t for t, _ in bench.statuses()]
    gaps = [b - a for a, b in zip(times, times[1:])]
    assert len(gaps) >= 49
    assert all(90 <= g <= 110 for g in gaps), f"period out of tolerance: min {min(gaps)} ms, max {max(gaps)} ms"


@pytest.mark.verifies("SRS-009")
def test_status_content(bench):
    """TC-031 PUMP_STATUS carries state, rate and a delivered volume that tracks the reference."""
    bench.start_infusion(rate_ml_h=250.0, vtbi_ml=100.0)
    bench.run(20_000)
    status = bench.last_status()
    assert status["state"] == State.INFUSING
    assert status["rate_ml_h"] == 250.0
    delivered = [s["delivered_ml"] for _, s in bench.statuses()]
    assert delivered == sorted(delivered), "delivered volume must not decrease"
    assert abs(status["delivered_ml"] - bench.measured_volume_ml) <= 0.01
