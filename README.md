# MTG Draw Sim

A terminal-based deck draw simulator for Magic: The Gathering. Import any MTG Arena decklist, define draw conditions, run thousands of randomized simulations, and get statistical results on how consistently your deck hits its key draws.

> **Status: Work in progress.** The simulation engine (Stage 1) is complete and tested. The terminal UI is under active development.

---

## What it does

MTG Draw Sim is a **statistical draw analysis tool**, not a game simulator. There is no combat, no mana system, no stack — just the question: *given this deck, how often do I have what I need by turn N?*

You define **conditions** like:

- `Lightning Bolt > 0 by turn 1` — do I have at least one bolt in my opening hand?
- `Forest >= 2 by turn 3` — do I have enough lands to ramp?

You group conditions into **simulations** with AND/OR logic, run them tens of thousands of times, and get back success rates — per condition and overall.

---

## Features

- Import decklists directly from MTG Arena export format
- Define reusable draw conditions (card, comparator, count, turn deadline)
- Group conditions into named simulations with ANY (OR) / ALL (AND) success logic
- Run thousands of randomized independent games per simulation
- Per-condition hit rates alongside overall simulation success rate
- Seeded RNG for fully reproducible results
- INI-based configuration for default hand size, cards per turn, run counts, and more
- Builds to a standalone executable via PyInstaller (Linux and Windows)

---

## Project structure

```
mtg_draw_sim/
├── main.py                  # Entrypoint (TUI, coming in Stage 2)
├── build.sh                 # Linux/macOS build script
├── build.ps1                # Windows build script
├── config.ini               # Optional configuration file
└── mtg_sim/
    ├── engine/
    │   ├── deck.py          # MTG Arena decklist parser
    │   ├── game_state.py    # Library, hand, turn state
    │   ├── simulation.py    # Condition, Simulation, SimulationRunner
    │   ├── config.py        # INI config model
    │   └── app_state.py     # Top-level application state
    ├── ui/                  # TUI (Textual) — coming in Stage 2
    └── tests/
        └── test_engine.py   # 43 engine tests
```

---

## Requirements

- Python 3.10+
- No runtime dependencies yet (standard library only for the engine)
- [Textual](https://github.com/Textualize/textual) will be added in Stage 2 for the TUI

---

## Running the tests

```bash
# Create and activate the virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dev dependencies
pip install pytest

# Run the test suite
python -m pytest mtg_sim/tests/
```

---

## Building an executable

The build scripts handle venv creation, dependency installation, test gating, and PyInstaller packaging automatically.

**Linux / macOS:**
```bash
chmod +x build.sh
./build.sh                  # outputs to dist/mtg_sim/mtg_sim
./build.sh --onefile        # single executable
./build.sh --clean          # remove build artifacts
```

**Windows (PowerShell):**
```powershell
# One-time: allow local scripts to run
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

.\build.ps1                 # outputs to dist\mtg_sim\mtg_sim.exe
.\build.ps1 -OneFile        # single executable
.\build.ps1 -Clean          # remove build artifacts
```

The build will run the test suite before packaging and abort if any tests fail.

---

## Configuration

Create a `config.ini` in the project root to set defaults:

```ini
[deck]
source = my_deck.txt

[game]
hand_size      = 7
cards_per_turn = 1
turn_limit     = 8

[simulation]
run_count = 10000
seed      =         ; leave blank for random
```

---

## Roadmap

- [x] Stage 1 — Simulation engine (deck parser, game state, conditions, simulations)
- [ ] Stage 2 — Textual TUI scaffold (4-pane layout, navigation)
- [ ] Stage 3 — Interactive mode (live deck/hand updates, turn advancement)
- [ ] Stage 4 — Condition and simulation CRUD (add, edit, delete via UI)
- [ ] Stage 5 — Batch runner with progress display and stats
- [ ] Stage 6 — Config integration and polish
- [ ] Future — Mulligan simulation (London mulligan)

---

## Decklist format

MTG Arena export format is supported. Copy your deck from MTG Arena and paste it into a `.txt` file:

```
Deck
4 Lightning Bolt
4 Goblin Guide
4 Monastery Swiftspear
12 Mountain
...

Sideboard
2 Pyroblast
```

The sideboard section is ignored. Set codes like `Lightning Bolt (M11) 100` are handled automatically.