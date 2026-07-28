"""Intentionally vulnerable source code for demonstrating Snyk Code (SAST) scanning.

Each function below contains a well-known weakness class (CWE) that Snyk Code
detects via taint analysis. This module is for demo/education purposes only and
must never be deployed.
"""

import hashlib
import logging
import os
import pickle
import random
import socket
import sqlite3
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler

import jwt
import ldap3
import requests
import urllib3
import yaml
from jinja2 import Environment


# CWE-89: SQL Injection — untrusted input concatenated into a query string.
def get_user(username: str):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE name = '" + username + "'"
    cursor.execute(query)
    return cursor.fetchall()


# CWE-78: OS Command Injection — untrusted input passed to a shell.
def ping_host(host: str):
    return subprocess.check_output("ping -c 1 " + host, shell=True)


# CWE-22: Path Traversal — untrusted path used to read a file.
def read_report(filename: str):
    path = os.path.join("/var/reports", filename)
    with open(path, "r") as handle:
        return handle.read()


# CWE-798: Hardcoded Credentials — secret embedded in source.
API_TOKEN = "AKIA5EXAMPLE1234567890"
DB_PASSWORD = "sup3rs3cr3t-p@ssw0rd"


# CWE-327: Use of a broken/weak hashing algorithm.
def hash_password(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()


# CWE-502: Deserialization of untrusted data.
def load_session(blob: bytes):
    return pickle.loads(blob)


# CWE-79: Cross-site Scripting — autoescaping disabled while rendering input.
def render_greeting(name: str) -> str:
    env = Environment(autoescape=False)
    template = env.from_string("<h1>Hello {{ name }}</h1>")
    return template.render(name=name)


# CWE-918 / CWE-295: SSRF plus disabled TLS verification.
def fetch_url(url: str):
    http = urllib3.PoolManager(cert_reqs="CERT_NONE")
    return http.request("GET", url).data


# CWE-94: Code Injection — untrusted input evaluated as code.
def calculate(expression: str):
    return eval(expression)


# CWE-611: XML External Entity (XXE) — parser resolves external entities.
def parse_xml(document: str):
    parser = ET.XMLParser()
    return ET.fromstring(document, parser=parser)


# CWE-502: Unsafe YAML deserialization — full loader executes arbitrary tags.
def load_config(blob: str):
    return yaml.load(blob, Loader=yaml.Loader)


# CWE-330/338: Insecure randomness used to generate a security token.
def generate_reset_token() -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(6))


# CWE-347: Improper verification of a JWT signature.
def decode_token(token: str):
    return jwt.decode(token, options={"verify_signature": False})


# CWE-90: LDAP Injection — untrusted input concatenated into a filter.
def find_ldap_user(username: str):
    server = ldap3.Server("ldap://directory.internal")
    conn = ldap3.Connection(server, auto_bind=True)
    conn.search("dc=example,dc=com", "(uid=" + username + ")")
    return conn.entries


# CWE-377: Insecure temporary file creation with a predictable name.
def write_temp(data: str) -> str:
    path = os.path.join(tempfile.gettempdir(), "session.tmp")
    with open(path, "w") as handle:
        handle.write(data)
    return path


# CWE-732: Overly permissive file permissions on a sensitive file.
def save_secret(secret: str) -> None:
    with open("/etc/app/secret.key", "w") as handle:
        handle.write(secret)
    os.chmod("/etc/app/secret.key", 0o777)


# CWE-312: Cleartext logging of sensitive information.
def log_login(username: str, password: str) -> None:
    logging.info("login attempt user=%s password=%s", username, password)


# CWE-601: Open Redirect — untrusted input used as a redirect target.
class RedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        target = self.path.split("url=", 1)[-1]
        self.send_response(302)
        self.send_header("Location", target)
        self.end_headers()


# CWE-295: Disabled TLS certificate verification on an HTTP request.
def fetch_insecure(url: str):
    return requests.get(url, verify=False).text


# CWE-78: OS Command Injection — untrusted path passed to a shell.
def run_backup(path: str):
    os.system("tar -czf backup.tar.gz " + path)


# CWE-319: Cleartext transmission of credentials over an unencrypted socket.
def send_credentials(host: str, token: str) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, 8080))
    sock.sendall(("AUTH " + token).encode())
    sock.close()


if __name__ == "__main__":
    pw = "QjykfqxJ33vMduX3yeyWHpbdY"
    print(render_greeting("<script>alert(1)</script>"))
