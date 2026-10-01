# EIDOLON — Project #008: Fire Effect

A procedural fire simulation built entirely with Python and Pygame. It creates a dynamic flame from particles, turbulence, palette interpolation, glow, sparks, smoke, wind, and original synthesized audio.

Part of the EIDOLON 500+ project journey.

## Features

- Connected, tapered flame tongues with particle-based flicker and automatic recycling
- Flickering turbulence and responsive left/right wind
- Five levels of flame intensity
- Independent spark and smoke particle systems
- Dynamic fire glow and ground reflection
- Four fire palettes: Classic, Blue, Purple, and Green
- Original, runtime-synthesized warm fire ambience and soft ember pops—no downloaded music or sound effects
- EIDOLON startup screen, countdown, HUD, pause, and reset controls
- No artwork, audio, fonts, or other copyrighted media assets

## Requirements

- Windows 10 or 11
- Python 3.12
- Pygame 2.6.1

Install the required Pygame version:

```powershell
python -m pip install pygame==2.6.1
```

## Run

From this project directory:

```powershell
python main.py
```

The application opens on the EIDOLON title screen. Press `Space` for the 3–2–1 ignition countdown.

## Controls

| Key | Action |
| --- | --- |
| `Space` | Start, pause, or resume |
| `Up` / `Down` | Increase / decrease fire intensity |
| `Left` / `Right` | Bend the flame with wind |
| `C` | Cycle fire palette |
| `S` | Toggle sparks |
| `O` | Toggle smoke |
| `G` | Toggle fire glow |
| `M` | Toggle procedural audio |
| `R` | Restore the default simulation settings |
| `Esc` | Quit |

## Verification mode

For a short automated visual/runtime check, use:

```powershell
python main.py --demo-seconds 3
```

In a display-less automation environment, set `SDL_VIDEODRIVER=dummy` before running the command. This mode is only for verification; normal use should run without it.

## Concepts explored

- Particle systems, lifetimes, and recycling
- Procedural animation and randomized turbulence
- Colour interpolation and additive-looking glow layering
- Secondary particle effects (sparks and smoke)
- Directional force through wind
- Interactive real-time graphics
- Simple procedural PCM audio synthesis using only Python's standard library and Pygame

## EIDOLON journey

Previous projects:

- #001 Ball Escape
- #002 Particle Fountain
- #003 Matrix Rain
- #004 Chrono Interface
- #005 Gravity Lab
- #006 Starfield
- #007 Rainfall

Current project:

- #008 Fire Effect

## Repository identity

`EIDOLON-Forge/project-008-fire-effect`

This repository has not been initialized or pushed by this project setup.

## License

MIT License. See [LICENSE](LICENSE).

**EIDOLON**  
Build. Experiment. Break. Repeat.
