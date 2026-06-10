# MTG Draw Sim — User Manual

> Current version covers Stage 2. Mouse support is planned for a future stage;
> all controls are keyboard-driven with modal dialogs for data entry.

---

## Launching the app

```bash
# With demo deck (good for exploring the UI)
python main.py

# With your own MTG Arena decklist
python main.py my_deck.txt

# With a custom config file
python main.py my_deck.txt --config my_config.ini

# Or run the built executable directly
./dist/mtg_sim/mtg_sim my_deck.txt
```

If no deck file is provided the app loads a demo burn deck so you have
something to look at immediately.

---

## The interface

The screen is divided into four panes arranged in a 2×2 grid, plus a
status bar along the bottom.

```
┌─────────────────────┬─────────────────────┐
│  LIBRARY            │  HAND               │
│                     │                     │
│  (cards remaining)  │  (cards in hand)    │
│                     │                     │
├─────────────────────┼─────────────────────┤
│  CONDITIONS         │  SIMULATIONS        │
│                     │                     │
│  (rules you define) │  (experiments)      │
│                     │                     │
└─────────────────────┴─────────────────────┘
  [n] next turn  [r] reset  [s] run sims  [q] quit
```

The pane with **focus** is highlighted with a blue border and its title
turns blue. Each pane scrolls independently when its content overflows.

---

## Complete keybinding reference

### Pane navigation

| Key | Action |
|-----|--------|
| `Tab` | Move focus to the next pane (Library → Hand → Conditions → Simulations → …) |
| `Shift+Tab` | Move focus to the previous pane |
| `↑` / `↓` | Move the selection cursor within the Conditions or Simulations pane |
| Mouse wheel | Scroll any pane |

### Game controls

| Key | Action |
|-----|--------|
| `n` | Advance to the next turn and draw cards |
| `r` | Reset — reshuffle the deck and deal a fresh opening hand |

### Simulation controls

| Key | Action |
|-----|--------|
| `s` | Run all defined simulations and display results |

### CRUD

| Key | Action |
|-----|--------|
| `a` | Open the Add Condition dialog |
| `A` | Open the Add Simulation dialog |
| `d` | Delete the currently selected condition or simulation |

### Dialogs

| Key | Action |
|-----|--------|
| `Tab` | Move focus to the next field in a dialog |
| `Shift+Tab` | Move focus to the previous field |
| `Enter` | Activate the focused button |
| `Escape` | Close the dialog without saving |

### App

| Key | Action |
|-----|--------|
| `q` | Quit the application |

---

## Navigation in detail

### Moving between panes

Press `Tab` to cycle focus forward through the four panes. Press
`Shift+Tab` to go backward. The focused pane is highlighted with a
blue border.

### Moving within a pane

In the **Conditions** and **Simulations** panes, `↑` and `↓` move a
selection highlight between items. The highlighted item is the one
`d` will delete. The **Library** and **Hand** panes are display-only
and don't have a selection cursor.

---

## Game controls

| Key | What it does |
|-----|-------------|
| `n` | Draw the next turn. Draws one card by default (configurable in `config.ini`). The Library and Hand panes update to reflect the new state. |
| `r` | Reset the game. Reshuffles the deck, deals a fresh 7-card opening hand, and returns to turn 0. |

The turn counter is shown in the Library pane header (e.g. `LIBRARY  turn 3`).
The card count in the Hand pane header updates as you draw.

---

## Conditions

A **condition** is a single draw rule: *"I need at least N copies of
card X in my hand by turn T."*

Conditions are defined independently of simulations and can be reused
across multiple simulations.

### Adding a condition

Press `a` from anywhere in the app. A dialog appears with five fields:

| Field | Description | Default |
|-------|-------------|---------|
| Card name | Dropdown of all cards in your deck. Type a letter to jump to the first matching entry. | *(none)* |
| Comparator | The comparison operator (`>=`, `<=`, `==`, `>`, `<`). | `>=` |
| Count | The number to compare against. | `1` |
| Turn deadline | The latest turn the condition must be met by. Turn 0 means the opening hand. | `4` |
| Label | Optional short name shown in the UI. Auto-generated from the rule if left blank. | *(blank)* |

Press **Save** to confirm. Press **Cancel** or `Escape` to discard.

If a required field is missing or invalid, a red error message appears
below the fields — the dialog stays open so you can correct it.

### Comparators explained

| Symbol | Meaning | Common use |
|--------|---------|------------|
| `>=` | At least N copies | "I need at least 2 lands" |
| `>` | More than N copies | "I need more than 0" (same as >= 1) |
| `==` | Exactly N copies | Rarely needed |
| `<=` | At most N copies | "I don't want more than 1 of X" |
| `<` | Fewer than N copies | Rarely needed |

### Deleting a condition

1. Tab to the **Conditions** pane.
2. Use `↑` / `↓` to highlight the condition.
3. Press `d`.

Deleting a condition automatically removes it from any simulations
that reference it.

---

## Simulations

A **simulation** is a named experiment that groups conditions together
and runs thousands of games to measure how often those conditions are met.

### Adding a simulation

Press `A` (capital A) from anywhere. A dialog appears:

| Field | Description | Default |
|-------|-------------|---------|
| Name | Display name for the simulation. | *(required)* |
| Success rule | Whether ALL conditions must be met, or just ANY one. | `ALL` |
| Run count | Number of independent games to simulate. | `10000` |
| Turn limit | Maximum turns per game. Leave blank to auto-derive from condition deadlines. | *(blank = auto)* |
| Conditions | Use the dropdown + **Add** button to assign conditions one at a time. | *(none)* |

Press **Save** to confirm. Press **Cancel** or `Escape` to discard.

### Assigning conditions to a simulation

Inside the Add Simulation dialog:

1. Open the **Conditions** dropdown — it lists all defined conditions.
   Already-added conditions are removed from the list automatically.
2. Select a condition.
3. Press **Add**. It appears in the list below.
4. Repeat for additional conditions.

### Success rules

- **ALL** — the simulation counts as a success only when *every*
  condition is satisfied within its deadline. Use for combos that need
  multiple specific cards together.
- **ANY** — the simulation counts as a success when *at least one*
  condition is satisfied. Use for redundant threats where any one will do.

### Running simulations

Press `s` to run all defined simulations. Each simulation executes its
full run count of independent games. Results appear immediately after:

```
[S1] Aggro opener   ANY   COMPLETE
     runs: 10,000  turns: 1  rate: 73.4%
     uses: [C1] [C2]
```

- **rate** — percentage of games where the success rule was satisfied.
- **uses** — which conditions this simulation references, by index.
- Status moves from `READY` → `COMPLETE` after running.

Pressing `s` again re-runs all simulations from scratch.

### Deleting a simulation

1. Tab to the **Simulations** pane.
2. Use `↑` / `↓` to highlight the simulation.
3. Press `d`.

---

## A worked example

**Goal:** find out how often a deck has a turn-1 threat and enough land.

1. Load your deck: `python main.py my_deck.txt`
2. Press `a` — add condition: card = `Goblin Guide`, `> 0`, turn `1`, label `Turn 1 threat`
3. Press `a` — add condition: card = `Mountain`, `>= 1`, turn `1`, label `Has land`
4. Press `a` — add condition: card = `Lightning Bolt`, `> 0`, turn `1`, label `Turn 1 bolt`
5. Press `A` — add simulation: name `Explosive opener`, rule **ALL**,
   add conditions `Turn 1 threat` and `Has land`
6. Press `A` — add simulation: name `Any threat`, rule **ANY**,
   add conditions `Turn 1 threat` and `Turn 1 bolt`
7. Press `s` — both simulations run and show their success rates.

---

## Configuration file

Create `config.ini` in the project root to set defaults:

```ini
[deck]
source = my_deck.txt      ; deck loaded automatically if no CLI argument given

[game]
hand_size      = 7        ; opening hand size
cards_per_turn = 1        ; cards drawn per turn
turn_limit     = 8        ; fallback turn limit if not set per-simulation

[simulation]
run_count = 10000         ; default run count for new simulations
seed      =               ; integer for reproducible results, blank for random
```

If a deck is specified both in `config.ini` and on the command line,
the command-line argument takes precedence.

---

## Decklist format

Copy your deck directly from MTG Arena (Collection → Deck → Share → Copy):

```
Deck
4 Lightning Bolt
4 Goblin Guide
4 Monastery Swiftspear
12 Mountain
4 Sacred Foundry

Sideboard
2 Pyroblast
```

- The `Deck` header is optional but recommended.
- `Sideboard`, `Commander`, and `Companion` sections are ignored.
- Set codes like `Lightning Bolt (M11) 100` are stripped automatically.
- Card names are **case-sensitive** and must match exactly — always
  use the dropdown when creating conditions rather than typing manually.

---

## Tips

- **Always use the card name dropdown** when creating conditions. It
  pulls names directly from your deck, so the match is guaranteed exact.
  Typing a name manually risks subtle mismatches that silently produce
  0% success rates.

- **Leave turn limit blank** when creating a simulation. It auto-derives
  from the highest deadline across your conditions.

- **Use ANY for redundant threats.** Multiple one-drops and you want to
  know how often you have *any* of them — one condition per card, grouped
  under ANY.

- **Use ALL for combo pieces.** Need card A *and* card B both in hand —
  two conditions, grouped under ALL.

- **Set a seed** in `config.ini` when you want reproducible results you
  can share or compare. Leave it blank for normal use.

- **Press `r` to re-deal.** The opening hand shown on launch is already
  dealt. Press `r` any time to reshuffle and deal a fresh hand.