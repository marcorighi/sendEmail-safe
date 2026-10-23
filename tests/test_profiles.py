#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Filename policy, legacy lookup and ambiguity tests (no network)."""
from __future__ import print_function

import json
import os
import re
import stat
import tempfile
import unittest
from unittest import mock

import sendemail_safe_profiles as profiles


class ProfileNamingTests(unittest.TestCase):
    def test_login_plus_server_detox_ascii_only(self):
        name = profiles.profile_filename(
            'Màrcó.Righi+Lab@EXAMPLE.com', 'smtp-relay.example.org'
        )
        self.assertEqual(
            name, 'marco_righi_lab_example_com_smtp_relay_example_org.json'
        )
        self.assertIsNotNone(re.match(r'^[a-z0-9_]+\.json$', name))

    def test_long_name_has_stable_hash_and_fits_filesystem(self):
        name = profiles.profile_filename(
            'a' * 260 + '@example.org', 'smtp.example.org'
        )
        self.assertLessEqual(len(name), 185)
        self.assertEqual(
            name, profiles.profile_filename(
                'a' * 260 + '@example.org', 'smtp.example.org'
            )
        )

    def test_reject_identifier_with_no_alphanumerics(self):
        with self.assertRaises(ValueError):
            profiles.profile_filename('----', 'smtp.example.org')

    def test_default_is_case_sensitive_new_path(self):
        with tempfile.TemporaryDirectory() as home:
            path = profiles.default_profile_path(
                'person@example.org', 'mail.example.org', home=home
            )
            self.assertEqual(path, os.path.join(
                home, '.config', 'sendEmail-safe',
                'person_example_org_mail_example_org.json'
            ))

    def test_simple_name_uses_old_directory_when_new_missing(self):
        with tempfile.TemporaryDirectory() as home:
            old = os.path.join(home, '.config', 'sendemail-safe')
            new = os.path.join(home, '.config', 'sendEmail-safe')
            os.makedirs(old)
            os.makedirs(new)
            old_path = os.path.join(old, 'legacy.json')
            new_path = os.path.join(new, 'legacy.json')
            with open(old_path, 'w') as output:
                output.write('{}')
            self.assertEqual(
                profiles.resolve_config('legacy', home=home), old_path
            )
            with open(new_path, 'w') as output:
                output.write('{}')
            self.assertEqual(
                profiles.resolve_config('legacy', home=home), new_path
            )

    def test_explicit_path_must_remain_in_home(self):
        with tempfile.TemporaryDirectory() as home:
            with self.assertRaises(ValueError):
                profiles.resolve_config('/etc/passwd', home=home)

    def test_detox_collision_is_rejected(self):
        with tempfile.TemporaryDirectory() as home:
            folder = os.path.join(home, '.config', 'sendEmail-safe')
            os.makedirs(folder, mode=0o700)
            path = profiles.default_profile_path(
                'a+b@example.org', 'smtp.example.org', home=home
            )
            with open(path, 'w') as output:
                json.dump({'user': 'a-b@example.org',
                           'from': 'a-b@example.org',
                           'host': 'smtp.example.org'}, output)
            os.chmod(path, 0o600)
            with self.assertRaises(ValueError):
                profiles.verify_no_collision(
                    path, 'a+b@example.org', 'smtp.example.org'
                )

    def test_no_default_when_two_profiles_exist(self):
        with tempfile.TemporaryDirectory() as home:
            folder = os.path.join(home, '.config', 'sendEmail-safe')
            os.makedirs(folder, mode=0o700)
            for suffix in ('first', 'second'):
                path = os.path.join(folder, suffix + '.json')
                with open(path, 'w') as output:
                    json.dump({'from': suffix + '@example.org'}, output)
                os.chmod(path, 0o600)
            with self.assertRaises(ValueError):
                profiles.choose_default_profile(home=home)
            found = profiles.choose_default_profile(
                sender='second@example.org', home=home
            )
            self.assertEqual(os.path.basename(found), 'second.json')

    def test_default_ignores_world_readable_and_symlink(self):
        with tempfile.TemporaryDirectory() as home:
            folder = os.path.join(home, '.config', 'sendEmail-safe')
            os.makedirs(folder)
            valid = os.path.join(folder, 'valid.json')
            with open(valid, 'w') as output:
                json.dump({'from': 'yes@example.org'}, output)
            os.chmod(valid, 0o600)
            public = os.path.join(folder, 'public.json')
            with open(public, 'w') as output:
                json.dump({'from': 'no@example.org'}, output)
            os.chmod(public, 0o644)
            os.symlink(valid, os.path.join(folder, 'symlink.json'))
            self.assertEqual(
                profiles.choose_default_profile(home=home), valid
            )


if __name__ == '__main__':
    unittest.main()
