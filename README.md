# SimURLLC

SimURLLC is a discrete-event simulator built with SimPy (Python) to evaluate scheduling algorithms for 6G Ultra-Reliable Low-Latency Communication (URLLC). It models a single base station and multiple URLLC devices competing for resource blocks under realistic 6G conditions, including SINR-based channel dynamics and interference bursts.

## Overview
- **Purpose**: Compare seven scheduling policies (Preemptive Priority, Non-Preemptive Priority, Round-Robin, EDF, Proportional Fairness, Hybrid EDF-Preemptive, 5G Fixed-Priority) for 6G URLLC performance.
- **Features**: 
  - Realistic 6G channel model with SINR and interference.
  - Deadline enforcement (1 ms latency target).
  - Comprehensive metrics: latency (mean + 99th percentile), packet loss, throughput, reliability, Age of Information (AoI), Jain’s Fairness Index.
  - Multiple simulation runs with different seeds for statistical robustness.
- **Status**:  Functional

## Setup
1. **Clone the Repository**:

## Setup
1. **Clone the repo**: 
```bash

    git clone https://github.com/Jupiter-Plantagenet/SimURLLC.git
    cd SimURLLC

```
2. **Install Dependencies**:
- Ensure Python 3.8+ is installed.
- Install required libraries:
`pip install -r requirements.txt`

3. **Run**: `python sim_urllc.py`

- Outputs per-run logs (e.g., `sim_urllc_log_seed_42.csv`) and a summary (`sim_urllc_summary.txt`).

## Files
- **`sim_urllc.py`**: Main simulation runner, sets up entities, runs multiple seeds, and analyzes results.
- **`entities.py`**: Defines simulation entities: `BaseStation`, `URLLCDevice`, `ResourceBlock`, `Packet`, `ChannelModel`.
- **`scheduling.py`**: Implements all seven scheduling algorithms.
- **`utils.py`**: Provides CSV logging utilities for events and metrics.
- **`config.yaml`**: Configuration file with simulation parameters (e.g., duration, device count).
- **`requirements.txt`**: Lists Python library dependencies (assumed pre-existing).

## Usage
- Edit `config.yaml` to adjust parameters (e.g., `arrival_rate`, `scheduling_policy`).
- Run `python sim_urllc.py` to simulate and generate results.
- Check `sim_urllc_summary.txt` for aggregated metrics across seeds.

## Output
- **Per-Run Logs**: CSV files (e.g., `sim_urllc_log_seed_42.csv`) with events and per-device stats.
- **Summary**: `sim_urllc_summary.txt` with seed-by-seed averages (latency, throughput, etc.).

## License
MIT.

