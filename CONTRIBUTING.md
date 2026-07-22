# Contributing

Contributions are welcome when they preserve the project's narrow security objective, conservative behavior, and Python 3.5.3 compatibility target.

## Before submitting a change

1. Do not include real credentials, email addresses, profile files, or production logs.
2. Keep all user-facing text and documentation in English.
3. Avoid syntax and standard-library APIs introduced after Python 3.5.3 unless the compatibility target is explicitly changed in a major release.
4. Add or update tests for behavioral changes.
5. Run:

```bash
./run-tests.sh
```

6. For migration changes, test multiline commands, inline commands, quoted text, comments, and unrelated command options.
7. Update `CHANGELOG.md` when the change is user-visible.

## Coding style

- Use four spaces for Python indentation.
- Keep scripts self-contained and standard-library-only.
- Prefer explicit errors over silently ignored options.
- Never print or log SMTP passwords.
- Preserve original files and create a backup before automated migration.
- Treat shell migration as conservative text transformation, not as a complete shell parser.

## Pull requests

Describe:

- the problem being solved;
- the compatibility impact;
- security implications;
- tests performed;
- any known limitations.
