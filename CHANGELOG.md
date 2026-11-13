# Changelog

## 1.1.0
### Added
- **Ghost ball + cut angle:** picks the easiest pocket for the object ball, draws the ghost position and angle.
- **Shot HUD** with lock state, cut angle, pocket, difficulty, bank count and "pocketed" indicator.
- **7 colour themes** with one-click swatches (`C` to cycle) plus the custom colour picker.
- **Animations:** flowing light pulses, pulsing pocket lock-on ring, animated ghost guide, toast notifications.
- Hotkeys: `X` swap balls, `G` ghost, `H` HUD, `A` animations, `R` reset, `F1`/`?` help overlay, `F11` fullscreen.
- Redesigned dark settings panel; "C"/"8" labels on the markers.
- CLI flags: `--version`, `--no-animation`, `--fullscreen`, `--reset-config`.
- `tools/render_assets.py` regenerates all README screenshots and the demo GIF.
- Windows `.exe` release workflow, issue/PR templates, Code of Conduct, `.editorconfig`.
### Changed
- README rewritten with banner, demo GIF, gallery, FAQ, maths explainer and roadmap.
- Settings panel now stays in sync when settings are loaded; high-DPI scaling enabled.
- `app.py` simplified (shared flags dict, grip helpers); geometry helpers reused for snapping.
- Config accepts the new toggles (`ghost`, `hud`, `animate`, `snap`).
### Fixed
- Config permission test no longer fails on Windows.

## 1.0.0
### Security
- Config moved from `./pf_config.json` (working-directory dependent) to a per-user directory.
- Config is now size-limited, type/range validated, NaN/Inf rejected, and written atomically with 0600 perms.
- Loaded geometry is clamped so a bad file can't produce an unusable overlay.
- Replaced broad `except Exception` handling with specific exceptions and logging.
### Changed
- Restructured into `src/pool_aim` package (`geometry`, `config`, `app`); `python aim.py` still works.
- Menu switches now reflect loaded settings.
- Screenshots compressed (7 MB -> ~1 MB) and renamed.
### Added
- pyproject.toml, requirements.txt, unit/smoke tests, CI (ruff, pytest, bandit, pip-audit, CodeQL),
  Dependabot, SECURITY.md, CONTRIBUTING.md, .gitignore.
