# 8 Ball Pool Aim Overlay

A minimal and clean aiming overlay for pool and billiards games, built with Python and PyQt5. This tool renders visual guides over the game window—direct aim lines, bank shots, and pocket-to-ball lines—without injecting into or modifying the game. 

## Features

- Minimal, transparent, borderless overlay that stays on top of the game window. 
- Grab-and-drop markers: click to pick up the cue/object ball markers, click again to drop. 
- Single and double bank trajectories with automatic visuals. 
- Visual hysteresis lock: bank endpoints “snap” to a nearby pocket when close to lock a clear target. 
- Pocket hotkeys: send the last-moved ball to one of six pockets using keys 1–6. 
- Customization: toggle aim lines, bank shots, pocket lines; set line thickness, overlay opacity, and a universal color. 
- Resizable, movable table: unlock the overlay to precisely fit any table geometry. 
- Persistent configuration: all settings (table position, colors, toggles) saved to pf_config.json. 

## Requirements

- Python 3.x installed on the system. 
- PyQt5 installed in the environment. 

Install PyQt5 with pip:


## Getting Started

1. Clone or download this repository locally. 
2. From the project directory, run the application:


3. Position the overlay window so it aligns with the game table on the screen. 
4. Press Enter to lock/unlock the table when finished aligning. 

## Controls

- Click & drag table (unlocked): drag anywhere inside the table to move the overlay. 
- Click & drag grips (unlocked): drag white square grips on the border to resize the table. 
- Grab & drop markers: click a larger p1 or p2 circular handle to pick it up; move the mouse and click again to drop it. 
- Menu: press the ☰ button or the O key to open settings. 
- Lock/Unlock: press Enter to toggle; resize grips disappear when locked. 
- Pocket hotkeys: press 1–6 to move the last selected ball to pockets (1–3 top, 4–6 bottom). 
- Exit: press Esc to close; if carrying a marker, first Esc cancels carry, second Esc closes the app. 

## Settings & Configuration

Use the in-app settings panel to adjust visibility of aim lines, bank shots, and pocket lines, as well as line thickness, overlay opacity, colors, and table geometry. 
- Save/Load: use the buttons in the panel to write/read settings. 
- Config file: a pf_config.json file is created in the same directory as the script to persist all settings. 

## Tips

- Align the overlay carefully to the in-game table before locking for the most accurate guides. 
- If a bank shot endpoint is close to a pocket, look for the “snap” to confirm a locked target. 
- Use a single universal color for clarity, then adjust opacity and thickness for different monitors. 

## Troubleshooting

- Overlay not on top: confirm the app window is focused; toggle lock/unlock to reassert topmost. 
- PyQt5 import error: ensure PyQt5 is installed in the active environment (pip install PyQt5), or use a virtual environment. 
- Config issues: delete pf_config.json to reset to defaults if settings become inconsistent. 

## Development

- Language/Toolkit: Python 3, PyQt5. 
- Platform: Works as a transparent top-level window; does not inject into or modify the game process. 
- Contributions: Open issues or submit pull requests with a clear description and minimal reproducible examples. 

## License

This project is released under the MIT License. See the LICENSE file in this repository for full text. 
