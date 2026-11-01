# Security Policy

## Supported versions

Only the latest release on `main` receives security fixes.

## Reporting a vulnerability

Please **do not open a public issue**. Use GitHub's private
[Security Advisories](https://github.com/Sushang-Agnihotri/8-Ball-Pool-Aim-tool/security/advisories/new)
to report privately. Expect an acknowledgement within 7 days.

## Security design

- Passive overlay: no network access, no subprocesses, no `eval`/`exec`, no pickle, no process injection.
- Settings live in a per-user config directory, are size-capped (64 KB), strictly validated (types, ranges,
  finite numbers) and written atomically with owner-only permissions.
- Dependencies are minimal (PyQt5 only) and monitored by Dependabot, `pip-audit` and CodeQL in CI.
