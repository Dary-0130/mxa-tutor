# 04_ee_d Overview

- Title: 04_ee_d EE SLX
- Type: power_electronics
- Summary: 04_ee_d is a Simulink-only electrical engineering model with 126 blocks and 154 

## Main Entry Files
- `04_ee_d.slx`: Open this .slx model first (04_ee_d).

## Main Simulink Models
- `04_ee_d.slx`: Parsed model 04_ee_d with 126 blocks, 154 lines, and 8 subsystems.

## Execution Flow
- Open `04_ee_d.slx` and inspect the root-level signal path.
- Identify source, measurement, control, and power-stage blocks from names and types.
- Open subsystems to follow how signals are grouped and transformed.
- Check solver settings and key block parameters before changing the model.

## Key Files
- `04_ee_d.slx`: Main Simulink model used as the entry point.
- `04_ee_d.slx`: Contains 126 parsed blocks and 8 subsystems.
- `04_ee_d.slx`: Contains parsed simulation settings: StartTime=0.0, StopTime=2, FixedStep=auto.

## Key Blocks
- `1226` (Three-Phase Mutual Inductance Z1-Z0) at `04_ee_d.slx / <root>`: Represents a visible Three-Phase Mutual Inductance Z1-Z0 block in the model structure.
- `1246` (Voltage Measurement) at `04_ee_d.slx / <root>`: Represents a visible Voltage Measurement block in the model structure.
- `C` (Parallel RLC Branch) at `04_ee_d.slx / <root>`: Represents a visible Parallel RLC Branch block in the model structure.
- `C1` (Parallel RLC Branch) at `04_ee_d.slx / <root>`: Represents a visible Parallel RLC Branch block in the model structure.
- `220kV` (Three-Phase Programmable Voltage Source) at `04_ee_d.slx / <root>`: Represents a visible Three-Phase Programmable Voltage Source block in the model structure.
- `220kV/35kV 10%` (Three-Phase Transformer (Two Windings)) at `04_ee_d.slx / <root>`: Represents a visible Three-Phase Transformer (Two Windings) block in the model structure.
- `B1` (Three-Phase VI Measurement) at `04_ee_d.slx / <root>`: Represents a visible Three-Phase VI Measurement block in the model structure.
- `B2` (Three-Phase VI Measurement) at `04_ee_d.slx / <root>`: Represents a visible Three-Phase VI Measurement block in the model structure.
- `Bus Selector1` (BusSelector) at `04_ee_d.slx / <root>`: Represents a visible BusSelector block in the model structure.
- `Bus Selector2` (BusSelector) at `04_ee_d.slx / <root>`: Represents a visible BusSelector block in the model structure.

## Knowledge Points
- Simulink signal-flow reading
- Electrical power conversion or machine model structure
- Subsystem-level model decomposition
- Solver and block-parameter interpretation

## Beginner Reading Order
- Start from `04_ee_d.slx`.
- Read root-level blocks and signal directions.
- Expand the largest subsystems and map their child blocks.
- Compare important block parameters with the solver configuration.

## Likely Confusing Points
- Some block names are domain abbreviations and need electrical-engineering context.
- Subsystem nesting can hide the real control or power-stage signal path.

## Evidence
- `04_ee_d.slx`, block_id=1226
- `04_ee_d.slx`, block_id=1246
- `04_ee_d.slx`, block_id=1235
