# Publishing on GitHub

## Pre-publication checks

Before the first push, run:

```bash
./run-tests.sh
```

Then check that no real credentials or private data are present:

```bash
grep -RIn \
  --exclude-dir=.git \
  --exclude='*.pyc' \
  -E '(-xp[[:space:]]+|smtp[_-]?(password|key)|api[_-]?key|BEGIN .*PRIVATE KEY)' \
  .
```

Review every match manually. Placeholder text in documentation and tests is expected; a real SMTP password, Brevo key, private email address, production IP address, or production profile is not.

Also inspect the complete staged diff before committing:

```bash
git diff --cached
```

Do not publish files from `~/.config/sendemail-safe/`.

## Create the repository locally

From this directory:

```bash
git init
git add .
git diff --cached --check
git commit -m 'Initial release of sendEmail-safe 1.0.0'
git branch -M main
```

## Create the GitHub repository

Create an empty GitHub repository without automatically adding a README, license, or `.gitignore`, because those files are already included here.

Then connect and push:

```bash
git remote add origin git@github.com:YOUR-ACCOUNT/sendEmail-safe.git
git push -u origin main
```

For HTTPS instead of SSH:

```bash
git remote add origin https://github.com/YOUR-ACCOUNT/sendEmail-safe.git
git push -u origin main
```

## Repository settings

Recommended settings:

- enable private vulnerability reporting;
- enable branch protection for `main` if other contributors are expected;
- require pull-request review before merging security-sensitive changes;
- disable accidental force pushes to `main`;
- add repository topics such as `smtp`, `linux`, `python`, `shell`, and `security`;
- use the MIT license already included in `LICENSE`.

## First release

Create a tag after the published commit has been reviewed:

```bash
git tag -a v1.0.0 -m 'sendEmail-safe 1.0.0'
git push origin v1.0.0
```

Use the `1.0.0` section of `CHANGELOG.md` as the basis for the GitHub release notes.
