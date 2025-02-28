# SimURLLC

A discrete-event simulator built with SimPy to evaluate scheduling algorithms for 6G Ultra-Reliable Low-Latency Communication (URLLC). **Designed for a journal publication**, it models a single base station and URLLC devices under realistic 6G conditions.

## Overview
- **Purpose**: Compare scheduling policies (e.g., EDF, Hybrid EDF-Preemptive) for 6G URLLC.
- **Features**: SINR-based channel model, deadline enforcement, key KPIs (latency, reliability, AoI).
- **Status**: In development.

## Setup
1. Clone the repo: `git clone <repo-url>`
2. Install dependencies: `pip install -r requirements.txt`
3. Run: `python sim_urllc.py`

## Files
- `sim_urllc.py`: Main simulation entry point.
- `entities.py`: Entity classes.
- `scheduling.py`: Scheduling algorithms.
- `config.yaml`: Configuration parameters.
- `utils.py`: Helper functions.

## License
MIT (TBD)
