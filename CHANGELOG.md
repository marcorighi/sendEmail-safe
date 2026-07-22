# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog principles, and the project uses semantic versioning.

## [Unreleased]

### Planned

- Additional compatibility tests against real-world legacy `sendEmail` command patterns.
- Runtime validation on additional Linux distributions and older Python installations.

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
