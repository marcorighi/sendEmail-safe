#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Send MIME messages using Gmail API with a refreshable OAuth 2.0 token.

Python 3.5+; standard library only. No bearer tokens in command-line arguments.
"""
from __future__ import print_function

import base64
import json
import urllib.error
import urllib.parse
import urllib.request


TOKEN_URL = 'https://oauth2.googleapis.com/token'
SEND_URL = 'https://gmail.googleapis.com/gmail/v1/users/me/messages/send'


class GmailAPIError(Exception):
    """Sanitized Gmail API or OAuth error (never contains a token)."""


def request_json(url, payload, headers, timeout):
    body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    request = urllib.request.Request(
        url, data=body, headers=dict(headers), method='POST'
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        # Do not print response bodies: OAuth error bodies can contain secrets.
        raise GmailAPIError('HTTPS service returned HTTP {}'.format(exc.code))
    except urllib.error.URLError:
        raise GmailAPIError('cannot connect to HTTPS service')


def refresh_access_token(config, timeout):
    fields = {
        'client_id': config['oauth_client_id'],
        'client_secret': config.get('oauth_client_secret', ''),
        'refresh_token': config['oauth_refresh_token'],
        'grant_type': 'refresh_token'
    }
    data = urllib.parse.urlencode(fields).encode('ascii')
    request = urllib.request.Request(
        TOKEN_URL,
        data=data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        raise GmailAPIError(
            'OAuth token refresh failed (HTTP {}); reauthorize the profile '
            'if the refresh token has expired or been revoked'.format(exc.code)
        )
    except urllib.error.URLError:
        raise GmailAPIError('cannot reach the Google OAuth token endpoint')
    token = result.get('access_token')
    if not isinstance(token, str) or not token:
        raise GmailAPIError('OAuth refresh returned no access token')
    return token


def send_message(message, config, timeout):
    """Send a constructed email message with gmail.send scope.

    The Gmail API obtains To/Cc/Bcc recipients from MIME headers.
    Do not pass or print the access token except as an HTTPS Bearer header.
    """
    token = refresh_access_token(config, timeout)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode('ascii')
    result = request_json(
        SEND_URL,
        {'raw': raw},
        {
            'Authorization': 'Bearer ' + token,
            'Content-Type': 'application/json'
        },
        timeout
    )
    if not isinstance(result, dict) or not result.get('id'):
        raise GmailAPIError('Gmail API response had no message ID')
    return result['id']
