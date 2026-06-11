# MTG Draw Sim

A terminal-based deck draw simulator for Magic: The Gathering. Import any MTG Arena decklist, define draw conditions, run thousands of randomized simulations, and get statistical results on how consistently your deck hits its key draws.

---

## What it does

MTG Draw Sim is a **statistical draw analysis tool**, not a game simulator. There is no combat, no mana system, no stack — just the question: *given this deck, how often do I have what I need by turn N?*

You define **conditions** like:

- `Goblin Guide > 0 by turn 1` — do I have at least one in my opening hand?
- `Forest >= 2 by turn 3` — do I have enough lands to ramp?

You group conditions into **simulations** with AND/OR logic, run them tens of thousands of times, and get back success rates per condition and overall.

---

## Features

- Import decklists directly from MTG Arena export format
- Terminal UI with 4 panes: deck, hand, conditions, simulations
- Define reusable draw conditions via searchable card name dropdown
- Group conditions into named simulations with ALL or ANY success logic
- Assign conditions to simulations via scrollable checklist
- Run thousands of randomized independent games per simulation
- Per-condition hit rates alongside overall simulation success rate
- Live deck and hand updates as you draw turns interactively
- Seeded RNG for fully reproducible results
- INI-based configuration for hand size, cards per turn, run counts, and more
- Builds to a standalone executable via PyInstaller (Linux and Windows)

---

## Project structure

```
mtg_draw_sim/
├── main.py                  # Entrypoint
├── build.sh                 # Linux/macOS build script
├── build.ps1                # Windows build script
├── requirements.txt         # Python dependencies
├── config.ini               # Optional configuration file
└── mtg_sim/
    ├── engine/
    │   ├── deck.py          # MTG Arena decklist parser
    │   ├── game_state.py    # Library, hand, turn state
    │   ├── simulation.py    # Condition, Simulation, SimulationRunner
    │   ├── config.py        # INI config model
    │   └── app_state.py     # Top-level application state
    ├── ui/
    │   ├── app.py           # Main Textual application
    │   ├── app.tcss         # TUI stylesheet
    │   ├── widgets.py       # Pane widgets
    │   └── modals.py        # Add/edit dialogs and F1 help overlay
    └── tests/
        └── test_engine.py   # Engine tests
```

---

## Requirements

- Python 3.10+
- [Textual](https://github.com/Textualize/textual) — terminal UI framework

---

## Running the app

```bash
# Create and activate the virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run with demo deck
python main.py

# Run with your own Arena decklist
python main.py my_deck.txt
```

---

## Controls

| Key | Action |
|-----|--------|
| `Tab` / `Shift+Tab` | Switch between panes |
| `↑` / `↓` | Select item within a pane |
| `Enter` | Edit selected condition or simulation |
| `r` | Deal opening hand (reset) |
| `n` | Draw next turn |
| `s` | Run all simulations |
| `a` | Add condition |
| `A` | Add simulation |
| `d` | Delete selected condition or simulation |
| `F1` | Show help overlay with full keybinding reference |
| `q` | Quit |

---

## Running the tests

```bash
source .venv/bin/activate
python -m pytest mtg_sim/tests/
```

---

## Building an executable

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

The build runs the test suite before packaging and aborts if any tests fail.

---

## Configuration

Create `config.ini` in the project root to set defaults:

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

## Decklist format

Copy your deck directly from MTG Arena:

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

The sideboard section is ignored. Set codes like `Lightning Bolt (M11) 100` are handled automatically. Card names in conditions are matched exactly — always use the card name dropdown rather than typing manually.

---

## Roadmap

- [x] Stage 1 — Simulation engine (deck parser, game state, conditions, simulations)
- [x] Stage 2 — Textual TUI (4-pane layout, navigation, CRUD)
- [x] Stage 3 — Interactive mode (live deck/hand updates, card draw flash)
- [x] Stage 4 — Edit existing conditions and simulations
- [x] Stage 5 — Usability polish (app name, F1 help, status bar, checklist condition picker)
- [ ] Stage 6 — Async batch runner with progress display
- [ ] Stage 7 — Save/load conditions and simulations between sessions
- [ ] Future — Mulligan simulation (London mulligan)
- [ ] Future — Mouse support throughout