# Software Verification Plan - SP-100 Syringe Pump

| Document | VP-SP100 | Version | 1.0 |
| --- | --- | --- | --- |
| Device | SP-100 syringe infusion pump (fictional) | Software safety class | B (IEC 62304) |

> Portfolio project. The device, requirements and risk analysis are fictional and simplified. They show how a verification activity is planned, traced and documented; they are not a real design history file.

## 1 Purpose and scope

This plan defines how the SP-100 control software is verified against its software requirements (SRS-SP100) and how the risk controls from the risk management file (RMF-SP100) are shown to be effective.

In scope: software system testing and software integration testing with the hardware interfaces (IEC 62304 clauses 5.6 and 5.7) for:

- command handling over CAN (rate, VTBI, start, stop, pause, resume, alarm acknowledge)
- delivery accuracy and end of infusion
- safety supervision: occlusion, door, near-empty, communication loss
- status reporting

Out of scope: unit verification (clause 5.5), electrical safety and EMC (IEC 60601-1, IEC 60601-1-2), usability (IEC 62366-1), and full alarm-system acoustics (IEC 60601-1-8).

## 2 References

| Reference | Use in this plan |
| --- | --- |
| IEC 62304:2006+A1:2015 | Software life cycle; clauses 5.6, 5.7 and 9 (problem resolution) |
| ISO 14971:2019 | Risk control verification (clause 7.2) |
| IEC 60601-1, IEC 60601-1-8 | Context for alarm priorities and safe states |
| EU MDR 2017/745 Annex I (GSPR 17) and Annex II | Software verification evidence in the technical documentation |
| FDA 21 CFR 820 (QMSR) and guidance on content of premarket submissions for device software functions | Design verification records and software documentation |
| SRS-SP100, RMF-SP100 | Requirements and risk controls under test |

## 3 Strategy

| Aspect | Approach |
| --- | --- |
| Test basis | Each SRS requirement and each risk control (RC-xx) |
| Design techniques | Boundary value analysis and equivalence classes (ranges); state transition testing (start, pause, alarm, resume); fault injection (pressure, door, heartbeat loss); timing measurement against limits |
| Test level | Software system test on a test bench with simulated sensors and actuators (HiL-style) |
| Automation | pytest test cases; one test case can verify several requirements; every case declares the requirement IDs it verifies |
| Independence | Tests derive expected results from the SRS, never from the implementation |
| Regression | Full suite runs on every commit (CI); a seeded-defect run proves the suite detects a timing regression |

## 4 Test environment

| Item | Bench in this repository | Equivalent on a physical bench |
| --- | --- | --- |
| Device under test | `firmware/pump_firmware.py` | Pump controller board with released firmware |
| CAN bus | `bench/virtual_bus.py`, 10 ms scheduler | Vector VN16xx interface, CANoe |
| Communication database | `dbc/syringe_pump.dbc` | Same DBC loaded in CANoe |
| Sensor and actuator stimulation | `bench/hardware_sim.py` (pressure, door, syringe, stepper drive) | Pressure fixture, door actuator, VT System I/O |
| Reference measurement | Plunger position of the drive model | Gravimetric scale |
| Test automation | pytest | pytest with python-can, or CAPL / vTESTstudio (`capl/`) |
| Evidence | `reports/results.json`, `reports/traces/*.asc` | Same, plus calibration records of the bench |

The bench must be under configuration control: the commit hash of test code and DUT is recorded in every report.

## 5 Entry and exit criteria

Entry: SRS and RMF baselined; DUT build identified; bench configuration recorded; test cases reviewed.

Exit (pass):

- every requirement and every risk control is covered by at least one test case
- all test cases pass, or each failure has an approved problem report with risk assessment
- traceability matrix and verification report generated for the identified build

The CI job enforces the first two criteria automatically (`tools/trace_report.py` exits non-zero otherwise).

## 6 Problem resolution

Failures are recorded as problem reports (template: `docs/defects/TEMPLATE.md`) with severity, the violated requirement, the affected risk control and evidence (test log and CAN trace). A fix is verified by re-running the failing test case and the full regression suite (IEC 62304 clause 9.7). See `docs/defects/DR-001_late_occlusion_alarm.md` for an example.

## 7 Deliverables

| Deliverable | Location |
| --- | --- |
| Test specification (test cases with IDs, steps and expected results) | `tests/` (docstrings carry the TC IDs) |
| Test results with timestamps and build ID | `reports/results.json` |
| Traceability matrix (requirements and risk controls to tests) | `reports/traceability.md` |
| Verification report | `reports/verification_report.html` |
| CAN traces per test case | `reports/traces/` |
| Problem reports | `docs/defects/` |
