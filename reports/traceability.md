# Traceability matrix - SP-100

Run: 2026-11-04 16:06 UTC | Commit: n/a | Injected defect: none

## Requirements to tests

| Requirement | Title | Class | Risk controls | Tests | Result |
| --- | --- | --- | --- | --- | --- |
| SRS-001 | Infusion rate range | B | RC-01 | TC-001 (passed)<br>TC-001 (passed)<br>TC-001 (passed)<br>TC-001 (passed)<br>TC-001 (passed)<br>TC-002 (passed) | **PASS** |
| SRS-002 | Volume to be infused (VTBI) range | B | RC-01 | TC-003 (passed)<br>TC-003 (passed)<br>TC-003 (passed)<br>TC-003 (passed) | **PASS** |
| SRS-003 | Start preconditions | B | RC-04 | TC-004 (passed)<br>TC-004 (passed)<br>TC-004 (passed)<br>TC-004 (passed)<br>TC-005 (passed) | **PASS** |
| SRS-004 | Delivery accuracy | B | RC-02 | TC-010 (passed)<br>TC-010 (passed)<br>TC-010 (passed)<br>TC-010 (passed) | **PASS** |
| SRS-005 | End of infusion | B | RC-02 | TC-011 (passed) | **PASS** |
| SRS-006 | Occlusion detection | B | RC-03 | TC-020 (passed)<br>TC-021 (passed)<br>TC-021 (passed) | **PASS** |
| SRS-007 | Door open during infusion | B | RC-04 | TC-022 (passed) | **PASS** |
| SRS-008 | Near-empty syringe | B | RC-05 | TC-023 (passed) | **PASS** |
| SRS-009 | Status reporting | A | - | TC-030 (passed)<br>TC-031 (passed) | **PASS** |
| SRS-010 | Loss of communication | B | RC-06 | TC-024 (passed)<br>TC-025 (passed) | **PASS** |
| SRS-011 | No automatic restart after alarm | B | RC-07 | TC-026 (passed)<br>TC-027 (passed) | **PASS** |
| SRS-012 | Pause and resume | B | RC-02 | TC-012 (passed) | **PASS** |

## Risk controls to verification

| Risk control | Measure | Hazards | Requirements | Result |
| --- | --- | --- | --- | --- |
| RC-01 | Range check of rate and VTBI commands | HAZ-01 | SRS-001, SRS-002 | **PASS** |
| RC-02 | Volume tracking with automatic stop at VTBI, pause/resume keeps the total | HAZ-01 | SRS-004, SRS-005, SRS-012 | **PASS** |
| RC-03 | Occlusion detection on line pressure with motor stop and alarm | HAZ-02 | SRS-006 | **PASS** |
| RC-04 | Door interlock - no start with open door, stop on door open | HAZ-03 | SRS-003, SRS-007 | **PASS** |
| RC-05 | Near-empty alarm before the syringe runs dry | HAZ-02 | SRS-008 | **PASS** |
| RC-06 | Heartbeat supervision with safe state on communication loss | HAZ-03 | SRS-010 | **PASS** |
| RC-07 | Latched alarms and explicit RESUME required | HAZ-04 | SRS-011 | **PASS** |
