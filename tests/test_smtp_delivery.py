#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""End-to-end delivery test using a local unauthenticated SMTP stub."""
from __future__ import print_function

import email
import email.header
import json
import os
import pwd
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROGRAM = os.path.join(ROOT, 'sendEmail-safe.py')


class SMTPHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.server.messages = []
        self.wfile.write(b'220 localhost test SMTP\r\n')
        self.wfile.flush()
        data_mode = False
        message_lines = []

        while True:
            line = self.rfile.readline()
            if not line:
                break

            if data_mode:
                if line == b'.\r\n':
                    self.server.messages.append(b''.join(message_lines))
                    message_lines = []
                    data_mode = False
                    self.wfile.write(b'250 message accepted\r\n')
                    self.wfile.flush()
                else:
                    message_lines.append(line)
                continue

            upper = line.upper()
            if upper.startswith(b'EHLO') or upper.startswith(b'HELO'):
                self.wfile.write(b'250-localhost\r\n250 SIZE 1000000\r\n')
            elif upper.startswith(b'MAIL FROM:'):
                self.wfile.write(b'250 sender accepted\r\n')
            elif upper.startswith(b'RCPT TO:'):
                self.wfile.write(b'250 recipient accepted\r\n')
            elif upper.startswith(b'DATA'):
                data_mode = True
                self.wfile.write(b'354 end with <CRLF>.<CRLF>\r\n')
            elif upper.startswith(b'QUIT'):
                self.wfile.write(b'221 goodbye\r\n')
                self.wfile.flush()
                break
            elif upper.startswith(b'RSET') or upper.startswith(b'NOOP'):
                self.wfile.write(b'250 OK\r\n')
            else:
                self.wfile.write(b'250 OK\r\n')
            self.wfile.flush()


class SMTPServer(socketserver.TCPServer):
    allow_reuse_address = True


class SMTPDeliveryTests(unittest.TestCase):
    def test_local_plain_delivery(self):
        server = SMTPServer(('127.0.0.1', 0), SMTPHandler)
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()

        home = pwd.getpwuid(os.geteuid()).pw_dir
        temporary = tempfile.mkdtemp(
            prefix='.sendemail-safe-test-',
            dir=home
        )
        os.chmod(temporary, 0o700)
        profile = os.path.join(temporary, 'local.json')
        config = {
            'auth': False,
            'from': 'sender@example.org',
            'host': '127.0.0.1',
            'password': '',
            'port': server.server_address[1],
            'security': 'plain',
            'timeout': 5,
            'tls_verify': True,
            'user': ''
        }

        try:
            with open(profile, 'w') as handle:
                json.dump(config, handle)
                handle.write('\n')
            os.chmod(profile, 0o600)

            result = subprocess.run(
                [
                    sys.executable,
                    PROGRAM,
                    '--config',
                    profile,
                    '-t',
                    'recipient@example.org',
                    '-u',
                    'Local SMTP test',
                    '-m',
                    'Delivery body'
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=10
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(server.messages), 1)
            message = email.message_from_bytes(server.messages[0])
            subject = str(email.header.make_header(
                email.header.decode_header(message['Subject'])
            ))
            body = message.get_payload(decode=True).decode('utf-8')
            self.assertEqual(subject, 'Local SMTP test')
            self.assertEqual(body, 'Delivery body')
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)
            shutil.rmtree(temporary)


if __name__ == '__main__':
    unittest.main()
