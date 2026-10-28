"""Dependency-light device signing format shared by client and cloud."""

import hashlib


def canonical(method, path, timestamp, nonce, body):
    return "\n".join(
        [method.upper(), path, timestamp, nonce, hashlib.sha256(body).hexdigest()]
    ).encode()
