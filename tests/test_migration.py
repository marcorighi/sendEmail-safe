#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for sendEmail-safe-migrate.py."""
from __future__ import print_function

import importlib.util
import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_module(filename, module_name):
    path = os.path.join(ROOT, filename)
    specification = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


migration = load_module('sendEmail-safe-migrate.py', 'sendemail_safe_migrate')


class MigrationTests(unittest.TestCase):
    def test_multiline_command_is_migrated(self):
        original = (
            'sendEmail \\\n'
            '  -f "$FROM" \\\n'
            '  -t "$TO" \\\n'
            '  -u "$SUBJECT" \\\n'
            '  -m "$MESSAGE" \\\n'
            '  -s smtp.example.org:587 \\\n'
            '  -xu "$SMTP_USER" \\\n'
            "  -xp 'secret' \\\n"
            '  -o tls=yes\n'
        )
        changed, statistics = migration.migrate_text(original, 'brevo')
        self.assertIn(
            '/usr/local/bin/sendEmail-safe.py --config brevo',
            changed
        )
        self.assertNotIn('-xp', changed)
        self.assertNotIn('smtp.example.org', changed)
        self.assertFalse(changed.rstrip().endswith('\\'))
        self.assertEqual(statistics['old_commands'], 1)
        self.assertEqual(statistics['passwords'], 1)

    def test_unrelated_options_are_not_removed(self):
        original = (
            'other-command -s keep-this\n'
            'sendEmail -t a@example.org -u x -m y -xp secret\n'
        )
        changed, statistics = migration.migrate_text(original, 'brevo')
        self.assertIn('other-command -s keep-this', changed)
        self.assertEqual(statistics['passwords'], 1)

    def test_option_like_text_inside_message_is_not_removed(self):
        original = (
            'sendEmail -t a@example.org -u x '
            '-m "literal -xp text" -xp secret\n'
        )
        changed, statistics = migration.migrate_text(original, 'brevo')
        self.assertIn('literal -xp text', changed)
        self.assertEqual(statistics['passwords'], 1)

    def test_comments_and_quoted_commands_are_ignored(self):
        original = (
            '# sendEmail -xp secret\n'
            'echo "sendEmail -xp secret"\n'
        )
        changed, statistics = migration.migrate_text(original, 'brevo')
        self.assertEqual(changed, original)
        self.assertEqual(statistics['old_commands'], 0)

    def test_existing_safe_command_receives_config(self):
        original = (
            '/usr/local/bin/sendEmail-safe.py '
            '-t a@example.org -u x -m y\n'
        )
        changed, statistics = migration.migrate_text(original, 'brevo')
        self.assertIn('--config brevo', changed)
        self.assertEqual(statistics['safe_without_config'], 1)

    def test_keep_overrides_retains_non_password_smtp_options(self):
        original = (
            'sendEmail -t a@example.org -u x -m y '
            '-s smtp.example.org:587 -xu user -xp secret -o tls=yes\n'
        )
        changed, statistics = migration.migrate_text(
            original,
            'brevo',
            keep_overrides=True
        )
        self.assertNotIn('-xp', changed)
        self.assertIn('-s smtp.example.org:587', changed)
        self.assertIn('-xu user', changed)
        self.assertIn('-o tls=yes', changed)
        self.assertEqual(statistics['servers'], 0)


if __name__ == '__main__':
    unittest.main()
