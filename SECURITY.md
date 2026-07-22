# Security Policy

## Supported versions

Security fixes are applied to the latest published release.

## Reporting a vulnerability

Use GitHub private vulnerability reporting when it is enabled for the repository. If private reporting is unavailable, contact the maintainer through the private contact method shown on the maintainer's GitHub profile.

Do not publish any of the following in an issue, discussion, commit, pull request, or log excerpt:

- a real SMTP password or API key;
- a real profile file;
- an unredacted `sendEmail -xp` command;
- `/proc/<pid>/cmdline` output containing credentials;
- an SMTP AUTH transcript;
- private recipient addresses or message bodies.

Include a minimal reproduction with placeholder credentials and explain the affected version, operating system, Python version, and impact.

## Security design

The project is designed to prevent the SMTP password from appearing in the process command line. The profile is intentionally stored in clear text and protected through:

- placement inside the effective user's home directory;
- ownership by the effective user;
- file mode `0600`;
- profile-directory mode `0700`;
- disabled core dumps;
- Linux non-dumpable process mode where supported.

## Out of scope

The project does not claim to protect secrets against:

- `root`, the kernel, an administrator, or a privileged debugger;
- compromise of the user account that owns the profile;
- physical or offline access to unencrypted storage;
- insecure backups;
- process-memory inspection by a privileged actor;
- malicious SMTP servers;
- an unencrypted `plain` connection or the non-TLS fallback permitted by `auto`;
- sensitive recipients, subjects, bodies, or paths deliberately supplied as command-line arguments.
