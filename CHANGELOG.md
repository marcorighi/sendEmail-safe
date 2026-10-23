# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog principles, and the project uses semantic versioning.

## [Unreleased]

### Planned

- Additional compatibility tests against real-world legacy `sendEmail` command patterns.
- Runtime validation on additional Linux distributions and older Python installations.

## [1.2.0] - 2026-10-23

### Added

- Deterministic profile naming from login plus provider server, with ASCII-only detox-like normalization.
- New case-sensitive `~/.config/sendEmail-safe/` directory for newly created profiles.
- Omitted `--config` accepted when exactly one matching secure profile exists.
- Collision checks to prevent overwriting another normalized account.
- Continued explicit legacy profile lookup in `~/.config/sendemail-safe/`.

### Changed

- Both interactive SMTP configuration and Gmail API authorization default to derived profile names.
- Explicit `--config NAME|PATH` remains supported and no credentials are migrated automatically.

## [1.1.0] - 2026-10-23

### Added

- Gmail API OAuth 2.0 sending with narrowly scoped `gmail.send` permission.
- PKCE browser authorization helper with per-user, permission-restricted profiles.
- Refresh-token based authorization without Gmail application passwords.
- Isolated Gmail API and OAuth tests, plus GitHub Actions CI.

### Changed

- Maintained backward-compatible SMTP behavior and `sendEmail` option subset.
- Added support for distribution packages placing the Gmail helper in `/usr/bin`.
- Gmail support is experimental until real-account consent and delivery are validated.

## [1.0.1] - 2026-09-18

### Fixed

- Made the migration utility resolve `sendEmail-safe.py` relative to its own installation directory instead of assuming `/usr/local/bin`.
- Improved compatibility with distribution packages installing executables under `/usr/bin`.
- Updated migration tests to support installation-prefix-independent paths.

## [1.0.0] - 2026-07-22

### Added

- Per-user, multi-profile SMTP configuration stored under `~/.config/sendemail-safe/`.
- Required `--config` profile selector.
- Clear-text JSON profiles protected by ownership and mode checks.
- SMTP over STARTTLS, implicit TLS, opportunistic STARTTLS, or plain transport.
- Optional unauthenticated SMTP mode.
- Common `sendEmail`-compatible message, recipient, attachment, logging, and override options.
- Explicit rejection of `-xp`.
- Process hardening through disabled core dumps and Linux non-dumpable mode.
- Interactive profile configurator.
- Conservative shell-script migration utility with private backups and `bash -n` validation.
- Unit tests and Python 3.5 grammar validation.
- Installation, uninstallation, examples, security policy, and contributor documentation.
