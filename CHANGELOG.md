# Changelog

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
