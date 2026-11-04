# SP-100 Syringe Pump – Software Verification & Validation

![verification](https://img.shields.io/badge/verification-32%2F32%20passed-brightgreen) ![IEC 62304](https://img.shields.io/badge/IEC%2062304-class%20B-blue)

Requirement-based verification of a software-driven electromechanical medical device: a syringe infusion pump controlled over CAN. The repo contains the device software model, a HiL-style test bench, automated test cases traced to requirements and ISO 14971 risk controls, and the V&V documents a regulatory submission needs (FDA / EU MDR).

> **Portfolio project.** SP-100 is a fictional, simplified device. The requirements, risk analysis and firmware model are written to demonstrate a verification workflow, not to describe a real product.

## Test strategy at a glance

| What | How |
| --- | --- |
| Test basis | 12 software requirements (`docs/software_requirements.yaml`) and 7 risk controls (`docs/risk_analysis.yaml`) |
| Test design | Boundary values, equivalence classes, state transitions, fault injection, timing against limits |
| Test level | Software system test on a bench: virtual CAN bus, simulated pressure sensor, door switch, syringe drive |
| Pass criteria | Every requirement and risk control covered; every test case passes; CI fails the build otherwise |
| Evidence | Test results with build ID, traceability matrix, HTML verification report, Vector ASC trace per test case |
| Regression check | A seeded defect (late occlusion alarm) must make exactly the right test case fail |

## Results

| Metric | Result |
| --- | --- |
| Test cases | 32 passed / 32 |
| Requirements covered | 12 / 12 |
| Risk controls verified | 7 / 7 |
| Seeded defect `late-occlusion` | Detected by TC-020: motor stopped 1500 ms after occlusion onset (limit 1000 ms) |

Open `reports/verification_report.html` after a run for the full matrix.

## Run it

```bash
pip install -r requirements.txt
python -m pytest                                   # run the verification suite
python tools/trace_report.py                       # traceability matrix + verification report
python -m pytest --inject-defect late-occlusion    # show that the suite catches a regression
```

## Repository layout

```
firmware/        device under test: pump control software and CAN protocol
bench/           test bench: virtual CAN bus with ASC logging, hardware simulation, test fixture
tests/           test cases (TC-xxx), each marked with the requirements it verifies
tools/           trace_report.py: traceability matrix and verification report generator
docs/            SRS, risk analysis, verification plan, problem reports
dbc/             CAN database for CANoe / CANalyzer
capl/            CAPL test module and host simulation node for a physical CANoe bench
.github/         CI: runs the suite, enforces the coverage gate, checks the seeded defect
```

## What is verified

| Area | Requirements | Example test case |
| --- | --- | --- |
| Command ranges | SRS-001, SRS-002 | TC-001 rate boundary values 0.0 / 0.1 / 500.0 / 500.1 mL/h |
| Start preconditions | SRS-003 | TC-004 no start with door open or no syringe |
| Delivery accuracy | SRS-004 | TC-010 ±2 % over 10 min at 1, 25, 100 and 500 mL/h |
| End of infusion, pause/resume | SRS-005, SRS-012 | TC-011 stop at VTBI, over-delivery ≤ 0.02 mL |
| Occlusion | SRS-006 | TC-020 alarm ≤ 1000 ms; TC-021 no false alarm on 100 / 250 ms peaks |
| Door, near-empty, comm loss | SRS-007, SRS-008, SRS-010 | TC-022 motor stop ≤ 100 ms after door opens |
| Alarm latching | SRS-011 | TC-026 no automatic restart after acknowledge |
| Status reporting | SRS-009 | TC-030 PUMP_STATUS period 100 ± 10 ms |

## From this bench to a lab bench

The tests only talk to the bench through `send` / `receive` and sensor setters, so the transport can be swapped:

- `bench/virtual_bus.py` → a Vector VN16xx interface through python-can, using `dbc/syringe_pump.dbc`
- `bench/hardware_sim.py` → a pressure fixture, door actuator and VT System I/O
- reference volume from the drive model → a gravimetric scale

`capl/pump_tests.can` shows the same TC-001 and TC-020 as a CANoe test module, for teams that run vTESTstudio / CAPL. It is a reference implementation and is not compiled here, since CI has no CANoe licence.

## Documents

- [Verification plan](docs/verification_plan.md) – scope, references (IEC 62304, ISO 14971, IEC 60601-1, MDR, FDA), environment, entry/exit criteria
- [Software requirements](docs/software_requirements.yaml) and [risk analysis](docs/risk_analysis.yaml)
- [Problem report DR-001](docs/defects/DR-001_late_occlusion_alarm.md) and [template](docs/defects/TEMPLATE.md)

## Author

Ajay Krishna Boodur – Test Lead, Verification & Validation (automotive ECUs, HiL, ISO 26262), extending into medical device V&V.
