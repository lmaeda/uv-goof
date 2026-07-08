"""Intentionally vulnerable Flask app for demonstrating Snyk Code (SAST) scanning.

Each route wires untrusted HTTP request data into a dangerous sink, giving Snyk
Code a complete taint flow (source -> sink) to report. For demo/education only —
never deploy this.
"""

import os
import pickle
import sqlite3
import subprocess

import urllib3
from flask import Flask, request
from jinja2 import Environment

app = Flask(__name__)


# CWE-89: SQL Injection — request param concatenated into a query.
@app.route("/user")
def get_user():
    username = request.args.get("name")
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE name = '" + username + "'"
    cursor.execute(query)
    return str(cursor.fetchall())


# CWE-78: OS Command Injection — request param passed to a shell.
@app.route("/ping")
def ping_host():
    host = request.args.get("host")
    return subprocess.check_output("ping -c 1 " + host, shell=True)


# CWE-22: Path Traversal — request param used to build a file path.
@app.route("/report")
def read_report():
    filename = request.args.get("file")
    path = os.path.join("/var/reports", filename)
    with open(path, "r") as handle:
        return handle.read()


# CWE-502: Deserialization of untrusted request data.
@app.route("/session", methods=["POST"])
def load_session():
    return str(pickle.loads(request.get_data()))


# CWE-79: Cross-site Scripting — request data rendered with autoescape off.
@app.route("/greet")
def render_greeting():
    name = request.args.get("name")
    env = Environment(autoescape=False)
    template = env.from_string("<h1>Hello {{ name }}</h1>")
    return template.render(name=name)


# CWE-918 / CWE-295: SSRF plus disabled TLS verification.
@app.route("/fetch")
def fetch_url():
    url = request.args.get("url")
    http = urllib3.PoolManager(cert_reqs="CERT_NONE")
    return http.request("GET", url).data


# CWE-94: Code Injection — request param evaluated as code.
@app.route("/calc")
def calculate():
    expression = request.args.get("expr")
    return str(eval(expression))


if __name__ == "__main__":
    app.run(debug=True)
