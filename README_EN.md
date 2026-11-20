# Mouse Performance Test

[中文](README.md) | **English**

A Windows mouse and keyboard performance testing project. It reads low-level Raw Input events, records mouse movement or DKS keyboard timing data, and generates charts or reports for analysis.

## Features

- Capture mouse movement through the Windows Raw Input API
- Record per-event X/Y displacement and high-resolution timestamps
- Draw mouse trajectories and per-movement displacement charts
- Export mouse movement logs
- Measure DKS (Dual Key Switch) behavior and event timing

## Project Files

| File | Purpose |
|---|---|
| `mouse_tracker.py` | Basic mouse Raw Input capture with Matplotlib charts |
| `mouse_tracker copy.py` | Mouse capture with Plotly charts |
| `mouse_tracker change write.py` | Mouse capture that writes a log and then generates a Plotly chart |
| `mouse_tracker change write numphy.py` | Memory-efficient mouse capture using the `array` module |
| `dks_time.py` | DKS keyboard timing test and CSV report generator |
| `output/` | Generated HTML chart examples |
| `pic/` | Mouse test screenshots |

Some files above are variants or historical implementations. `mouse_tracker.py` is the simplest mouse capture starting point.

## Requirements

- Windows
- Python 3
- A mouse connected to the computer
- Administrator privileges are usually not required

Install the packages used by the mouse and chart scripts:

```powershell
pip install pywin32 matplotlib plotly
```

The DKS timing script only uses Python standard-library modules.

## Usage

### Mouse trajectory test

Run the basic implementation:

```powershell
python mouse_tracker.py
```

1. Activate the blank window that appears.
2. Hold the left mouse button.
3. Move the mouse quickly across the desktop.
4. Release the left mouse button.

The window closes and Matplotlib opens a chart containing:

- A cumulative mouse trajectory
- Per-event X and Y displacement
- High-resolution timestamps

Hover over points for details. Use the mouse wheel to zoom the chart.

The alternate Plotly-based scripts support left/right mouse button workflow variants. Check the console instructions printed by the script you run.

### DKS keyboard timing test

Run:

```powershell
python dks_time.py
```

Activate the test window, then press and release `A` or `D`. The script maps these keys to `F9` and `F8` by default. Edit `KEY_MAP` near the top of `dks_time.py` to change the mapping.

At exit, the script prints statistics and generates report and CSV files.

## How to interpret mouse results

### Per-movement displacement

This chart shows each reported mouse movement rather than only the final cursor position.

- Large sudden jumps or drift indicate dropped frames, weak wireless transmission, or radio interference.
- Small repeated oscillations indicate poor tracking consistency or sensor tuning. They may remain visible in wired mode.
- A stable curve with few small oscillations indicates good following behavior.

Wireless mouse performance depends on both:

- **Tracking consistency:** how stable the pointer feels while moving.
- **Interference resistance:** whether frames are suddenly skipped or the pointer jumps.

Example screenshots are available in [`pic/`](pic/).

## Screenshots

### Mouse trajectory and Raw Input test

<img src="pic/烈空f1 v3 2.png" alt="Liekong F1 V3 in wireless mode">

<img src="pic/ATK 蜻蜓A9 ultimate.png" alt="ATK A9 Ultimate in wireless mode">

## Notes

- Raw Input movement values are reported by Windows and the mouse/device driver; they are not a complete or independent measurement of sensor hardware quality.
- Test the mouse in both wired and wireless modes and keep the same surface, DPI, polling rate, movement speed, and environment for fair comparisons.
- The project is intended for technical evaluation and education. It is not affiliated with any mouse manufacturer.
