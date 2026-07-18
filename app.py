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
    query = "SELECT * FROM users WHERE name = ?"
    cursor.execute(query, (username,))
    from flask import Response
    return Response(str(cursor.fetchall()), content_type='text/plain')


# CWE-78: OS Command Injection — request param passed to a shell.
@app.route("/ping")
def ping_host():
    host = request.args.get("host")
    from flask import Response
    return Response(subprocess.check_output(["ping", "-c", "1", host]), content_type='text/plain')


# CWE-22: Path Traversal — request param used to build a file path.
@app.route("/report")
def read_report():
    filename = request.args.get("file")
    safe_name = os.path.basename(filename)
    path = os.path.join("/var/reports", safe_name)
    from flask import Response
    with open(path, "r") as handle:
        return Response(handle.read(), content_type='text/plain')


# CWE-502: Deserialization of untrusted request data.
@app.route("/session", methods=["POST"])
def load_session():
    from flask import Response
    return Response(str(pickle.loads(request.get_data())), content_type='text/plain')


# CWE-79: Cross-site Scripting — request data rendered with autoescape off.
@app.route("/greet")
def render_greeting():
    name = request.args.get("name")
    env = Environment(autoescape=True)
    template = env.from_string("<h1>Hello {{ name }}</h1>")
    return template.render(name=name)


# CWE-918 / CWE-295: SSRF plus disabled TLS verification.
@app.route("/fetch")
def fetch_url():
    url = request.args.get("url")
    http = urllib3.PoolManager(cert_reqs="CERT_NONE")
    from flask import Response
    return Response(http.request("GET", url).data, content_type="text/plain")


# CWE-94: Code Injection — request param evaluated as code.
@app.route("/calc")
def calculate():
    import ast
    from flask import Response
    expression = request.args.get("expr")
    return Response(str(ast.literal_eval(expression)), content_type='text/plain')


if __name__ == "__main__":
    app.run()
