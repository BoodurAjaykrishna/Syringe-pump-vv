# DR-001: Occlusion alarm and motor stop 500 ms too late

| Field | Value |
| --- | --- |
| Status | Verified (example: defect seeded with `--inject-defect late-occlusion`) |
| Severity | Major |
| Build under test | Firmware build with occlusion debounce of 1500 ms |
| Test case | TC-020 `tests/test_alarms.py::test_occlusion_stops_motor_within_1s` |
| Requirement violated | SRS-006 Occlusion detection |
| Risk control affected | RC-03 occlusion detection -> HAZ-02 interrupted therapy not noticed |

## Steps to reproduce

1. `python -m pytest --inject-defect late-occlusion`
2. Start an infusion at 100 mL/h, VTBI 100 mL, and run for 2 s.
3. Raise line pressure from 20 kPa to 150 kPa and hold it.

## Expected result

SRS-006: motor stopped and high-priority OCCLUSION alarm raised no later than 1000 ms after pressure onset.

## Actual result

Motor stopped and OCCLUSION alarm raised 1500 ms after onset. All other 31 test cases passed, including the false-alarm tests for 100 ms and 250 ms pressure peaks.

Test output: `AssertionError: motor stopped 1500 ms after occlusion onset (limit 1000 ms)`

## Evidence

- `reports/results.json` from the defect run (test outcome and message)
- `reports/traces/test_occlusion_stops_motor_within_1s.asc`: the bench injects the pressure step at t = 2.030 s; PUMP_ALARM (0x103, OCCLUSION) appears in the trace at t = 3.530 s

## Impact assessment

Therapy interruption is detected 0.5 s later than specified. The alarm still occurs, so the hazard is not uncontrolled, but RC-03 does not meet its specified effectiveness. The build must not be released.

## Root cause

The occlusion debounce constant was changed from 300 ms to 1500 ms (configuration `occlusion_debounce_ms`), apparently to suppress false alarms.

## Fix and verification

Debounce restored to 300 ms. TC-020 passes (motor stop 300 ms after onset); TC-021 still confirms that 100 ms and 250 ms peaks do not alarm; full regression 32/32 passed.
