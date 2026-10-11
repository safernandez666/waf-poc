"""
App deliberadamente vulnerable para demostrar un WAF (Aegis).
NO USAR EN PRODUCCION. Es un laboratorio de seguridad.

Vulnerabilidades incluidas a proposito:
  - SQL Injection (SQLi)  -> /login, /search
  - Cross-Site Scripting reflejado (XSS) -> /greet
  - Path Traversal        -> /download
"""
import os
import sqlite3
from flask import Flask, request, Response, render_template_string

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Base de datos de juguete (SQLite en memoria, se recrea al iniciar)
# ---------------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    cur = conn.cursor()
    cur.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password TEXT, role TEXT)")
    cur.executemany(
        "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
        [
            ("admin", "S3cr3t-Admin-Pass!", "admin"),
            ("alice", "alice123", "user"),
            ("bob", "hunter2", "user"),
        ],
    )
    cur.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price TEXT)")
    cur.executemany(
        "INSERT INTO products (name, price) VALUES (?, ?)",
        [("Laptop", "1200"), ("Teclado mecanico", "90"), ("Monitor 27\"", "300")],
    )
    conn.commit()
    return conn

DB = init_db()

PAGE = """
<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>DemoShop (vulnerable)</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem;color:#1a1a1a}
 h1{color:#b00020} code{background:#f4f4f4;padding:.1rem .3rem;border-radius:4px}
 .box{border:1px solid #ddd;border-radius:8px;padding:1rem;margin:1rem 0}
 input{padding:.4rem;margin:.2rem 0;width:100%;box-sizing:border-box}
</style></head><body>
<h1>⚠️ DemoShop</h1>
<p>App <strong>deliberadamente vulnerable</strong> para demostrar un WAF. No usar en producción.</p>
{{ body|safe }}
</body></html>
"""

@app.route("/")
def index():
    body = """
    <div class="box"><h3>Login (vulnerable a SQLi)</h3>
      <form action="/login" method="get">
        <input name="username" placeholder="usuario">
        <input name="password" placeholder="password" type="password">
        <button>Entrar</button>
      </form></div>
    <div class="box"><h3>Buscar productos (SQLi)</h3>
      <form action="/search" method="get">
        <input name="q" placeholder="nombre de producto"><button>Buscar</button>
      </form></div>
    <div class="box"><h3>Saludo (XSS reflejado)</h3>
      <form action="/greet" method="get">
        <input name="name" placeholder="tu nombre"><button>Saludar</button>
      </form></div>
    <div class="box"><h3>Descargar (Path Traversal)</h3>
      <form action="/download" method="get">
        <input name="file" placeholder="notas.txt"><button>Descargar</button>
      </form></div>
    """
    return render_template_string(PAGE, body=body)


# ---------------------------------------------------------------------------
# VULN 1: SQL Injection en login  ->  ' OR '1'='1
# ---------------------------------------------------------------------------
@app.route("/login")
def login():
    username = request.args.get("username", "")
    password = request.args.get("password", "")
    # Concatenacion directa: vulnerable a proposito.
    query = f"SELECT id, username, role FROM users WHERE username = '{username}' AND password = '{password}'"
    try:
        cur = DB.cursor()
        cur.execute(query)
        rows = cur.fetchall()
    except Exception as e:
        return render_template_string(PAGE, body=f"<div class='box'><b>Error SQL:</b> {e}<br><code>{query}</code></div>")
    if rows:
        items = "".join(f"<li>{r[1]} (rol: {r[2]})</li>" for r in rows)
        return render_template_string(PAGE, body=f"<div class='box'><b>Login OK.</b> Sesiones:<ul>{items}</ul>"
                                                 f"<small>Query: <code>{query}</code></small></div>")
    return render_template_string(PAGE, body=f"<div class='box'>Credenciales inválidas.<br><small><code>{query}</code></small></div>")


# ---------------------------------------------------------------------------
# VULN 2: SQL Injection en busqueda  ->  ' UNION SELECT ...
# ---------------------------------------------------------------------------
@app.route("/search")
def search():
    q = request.args.get("q", "")
    query = f"SELECT name, price FROM products WHERE name LIKE '%{q}%'"
    try:
        cur = DB.cursor()
        cur.execute(query)
        rows = cur.fetchall()
    except Exception as e:
        return render_template_string(PAGE, body=f"<div class='box'><b>Error SQL:</b> {e}<br><code>{query}</code></div>")
    items = "".join(f"<li>{r[0]} — ${r[1]}</li>" for r in rows) or "<li>sin resultados</li>"
    return render_template_string(PAGE, body=f"<div class='box'><ul>{items}</ul><small><code>{query}</code></small></div>")


# ---------------------------------------------------------------------------
# VULN 3: XSS reflejado  ->  <script>alert(1)</script>
# ---------------------------------------------------------------------------
@app.route("/greet")
def greet():
    name = request.args.get("name", "visitante")
    # Se refleja sin escapar: XSS a proposito.
    return render_template_string(PAGE, body=f"<div class='box'>Hola, {name} 👋</div>")


# ---------------------------------------------------------------------------
# VULN 4: Path Traversal  ->  ../../etc/passwd
# ---------------------------------------------------------------------------
@app.route("/download")
def download():
    filename = request.args.get("file", "notas.txt")
    base = os.path.join(os.path.dirname(__file__), "files")
    path = os.path.join(base, filename)  # sin sanitizar: vulnerable
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return Response(content, mimetype="text/plain")
    except Exception as e:
        return Response(f"Error: {e}", status=404, mimetype="text/plain")


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
