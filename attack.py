#!/usr/bin/env python3
"""
POC de ataque para demostrar un WAF (Aegis) en modo ANTES / DESPUÉS.

Lanza la misma batería de payloads contra dos destinos:
  - DIRECT : la app vulnerable sin WAF   (http://localhost:5000)
  - WAF    : la app detrás de Aegis       (http://localhost:8080)

Para cada payload compara qué pasó en cada destino y arma una tabla.
La idea del "antes/después": sin WAF el ataque funciona (200 + datos
filtrados); con WAF Aegis lo corta (403 / bloqueo).

Uso:
    python attack.py
    python attack.py --direct http://localhost:5000 --waf http://localhost:8080
    python attack.py --md resultados.md      # exporta la tabla a Markdown

Requisitos: requests  ->  pip install requests
"""
import argparse
import sys
from dataclasses import dataclass

try:
    import requests
except ImportError:
    sys.exit("Falta 'requests'. Instalá con:  pip install requests")


# ---------------------------------------------------------------------------
# Catálogo de ataques. Cada uno apunta a un endpoint de la app vulnerable.
# "evidence" es un texto que, si aparece en la respuesta, prueba que el
# ataque tuvo éxito (datos filtrados / payload reflejado).
# ---------------------------------------------------------------------------
@dataclass
class Attack:
    name: str
    path: str
    params: dict
    evidence: str          # señal de que el ataque FUNCIONÓ
    category: str


ATTACKS = [
    Attack(
        name="SQLi — bypass de login",
        path="/login",
        params={"username": "admin' OR '1'='1", "password": "x"},
        evidence="Login OK",
        category="SQL Injection",
    ),
    Attack(
        name="SQLi — UNION en búsqueda",
        path="/search",
        params={"q": "x' UNION SELECT username, password FROM users-- -"},
        evidence="S3cr3t-Admin-Pass",     # si filtra el hash/clave, cayó
        category="SQL Injection",
    ),
    Attack(
        name="XSS reflejado",
        path="/greet",
        params={"name": "<script>alert('xss')</script>"},
        evidence="<script>alert('xss')</script>",
        category="Cross-Site Scripting",
    ),
    Attack(
        name="Path Traversal — /etc/passwd",
        path="/download",
        params={"file": "../../../../etc/passwd"},
        evidence="root:",
        category="Path Traversal",
    ),
]

# Petición de control: tráfico legítimo. Debe pasar en AMBOS destinos
# (demuestra que el WAF no rompe a los usuarios reales).
BENIGN = Attack(
    name="Tráfico legítimo (control)",
    path="/search",
    params={"q": "Laptop"},
    evidence="Laptop",
    category="Benigno",
)


@dataclass
class Result:
    status: int
    blocked: bool
    succeeded: bool
    note: str


def run_one(base_url: str, atk: Attack, timeout: float = 8.0) -> Result:
    """Lanza un ataque contra un destino y clasifica el resultado."""
    try:
        r = requests.get(base_url + atk.path, params=atk.params, timeout=timeout)
    except requests.RequestException as e:
        return Result(status=0, blocked=False, succeeded=False, note=f"error de red: {e}")

    body = r.text
    # Heurística de bloqueo: Aegis responde 403 (o 406/429) ante un match de CRS.
    blocked = r.status_code in (403, 406, 429)
    # Éxito del ataque: respondió 200 y la evidencia aparece en el cuerpo.
    succeeded = (r.status_code == 200) and (atk.evidence in body)

    if blocked:
        note = f"BLOQUEADO por el WAF (HTTP {r.status_code})"
    elif succeeded:
        note = "ATAQUE EXITOSO — datos filtrados / payload reflejado"
    elif r.status_code == 200:
        note = "200 pero sin evidencia (payload no efectivo)"
    else:
        note = f"HTTP {r.status_code}"
    return Result(status=r.status_code, blocked=blocked, succeeded=succeeded, note=note)


def icon(ok: bool) -> str:
    return "✅" if ok else "❌"


def main():
    ap = argparse.ArgumentParser(description="POC de ataque antes/después con WAF")
    ap.add_argument("--direct", default="http://localhost:5000", help="App SIN WAF")
    ap.add_argument("--waf", default="http://localhost:8080", help="App detrás de Aegis")
    ap.add_argument("--md", metavar="ARCHIVO", help="Exporta la tabla comparativa a Markdown")
    args = ap.parse_args()

    print(f"\n  DIRECTO (sin WAF): {args.direct}")
    print(f"  CON WAF (Aegis)  : {args.waf}\n")
    print("=" * 78)

    rows = []  # (atk, res_direct, res_waf)

    for atk in [*ATTACKS, BENIGN]:
        rd = run_one(args.direct, atk)
        rw = run_one(args.waf, atk)
        rows.append((atk, rd, rw))

        print(f"\n▶ {atk.name}  [{atk.category}]")
        print(f"    sin WAF : {rd.note}")
        print(f"    con WAF : {rw.note}")

    # ---- Resumen en tabla ----
    print("\n" + "=" * 78)
    print("RESUMEN COMPARATIVO\n")
    header = f"{'Ataque':<34} {'Sin WAF':<22} {'Con WAF':<22}"
    print(header)
    print("-" * len(header))
    for atk, rd, rw in rows:
        if atk.category == "Benigno":
            # Para el control nos importa que SIGA funcionando con WAF.
            left = "pasa ✅" if rd.succeeded else "falla ❌"
            right = "pasa ✅" if rw.succeeded else "falla ❌"
        else:
            left = f"explota ❌ ({rd.status})" if rd.succeeded else f"ok ({rd.status})"
            right = f"bloquea ✅ ({rw.status})" if rw.blocked else f"PASA ❌ ({rw.status})"
        print(f"{atk.name:<34} {left:<22} {right:<22}")

    # ---- Veredicto ----
    attacks_only = [(a, d, w) for (a, d, w) in rows if a.category != "Benigno"]
    exploited_direct = sum(1 for _, d, _ in attacks_only if d.succeeded)
    blocked_waf = sum(1 for _, _, w in attacks_only if w.blocked)
    print("\n" + "=" * 78)
    print(f"Sin WAF : {exploited_direct}/{len(attacks_only)} ataques exitosos")
    print(f"Con WAF : {blocked_waf}/{len(attacks_only)} ataques bloqueados por Aegis")

    if args.md:
        write_markdown(args.md, rows)
        print(f"\nTabla Markdown escrita en: {args.md}")


def write_markdown(path: str, rows):
    lines = [
        "| Ataque | Categoría | Sin WAF | Con WAF (Aegis) |",
        "|--------|-----------|---------|-----------------|",
    ]
    for atk, rd, rw in rows:
        if atk.category == "Benigno":
            left = "Pasa ✅" if rd.succeeded else "Falla ❌"
            right = "Pasa ✅" if rw.succeeded else "Falla ❌"
        else:
            left = f"Explota ❌ (HTTP {rd.status})" if rd.succeeded else f"HTTP {rd.status}"
            right = f"Bloquea ✅ (HTTP {rw.status})" if rw.blocked else f"Pasa ❌ (HTTP {rw.status})"
        lines.append(f"| {atk.name} | {atk.category} | {left} | {right} |")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
