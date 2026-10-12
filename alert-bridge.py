#!/usr/bin/env python3
"""
alert-bridge — de los bloqueos del WAF a Slack (o cualquier webhook).

Aegis no trae notificaciones nativas: la telemetria vive en ClickHouse.
Este script hace de puente: cada N segundos consulta los bloqueos nuevos
en aegis.waf_events y los postea a un webhook entrante de Slack.

Uso:
    WEBHOOK_URL=https://hooks.slack.com/services/T.../B.../xxxx python3 alert-bridge.py
    WEBHOOK_URL=... python3 alert-bridge.py --once   # un solo barrido y sale

Para probar sin Slack, generá una URL en https://webhook.site y usala como WEBHOOK_URL.

Requisitos: requests -> pip install requests
"""
import argparse
import os
import time

import requests

CLICKHOUSE = "http://localhost:8123"  # HTTP interface de ClickHouse
DB_USER = "default"
DB_PASS = "analytics"
POLL_EVERY = 5  # segundos entre barridos


def blocked_since(ts: str):
    """Bloqueos nuevos desde el timestamp ISO dado."""
    q = (
        "SELECT toString(timestamp) AS timestamp, ip, method, path, query_string, "
        "toInt32(extract(rule_messages, 'Total Score: ([0-9]+)')) AS anomaly_score "
        "FROM aegis.waf_events "
        f"WHERE action = 'block' AND timestamp > '{ts}' "
        "ORDER BY timestamp ASC FORMAT JSONEachRow"
    )
    r = requests.post(
        CLICKHOUSE,
        params={"user": DB_USER, "password": DB_PASS},
        data=q,
        timeout=10,
    )
    r.raise_for_status()
    return [__import__("json").loads(l) for l in r.text.splitlines() if l.strip()]


def to_slack(ev: dict) -> dict:
    """Evento de ClickHouse -> mensaje con formato de Slack."""
    query = ev["query_string"][:80] or "-"
    return {
        "text": (
            f":rotating_light: *Aegis WAF bloqueó una request*\n"
            f"• path: `{ev['method']} {ev['path']}`\n"
            f"• query: `{query}`\n"
            f"• anomaly score: *{ev['anomaly_score']}* (umbral: 5)\n"
            f"• ip: `{ev['ip']}`"
        )
    }


def main():
    ap = argparse.ArgumentParser(description="Puente ClickHouse -> Slack para bloqueos del WAF")
    ap.add_argument("--once", action="store_true", help="un solo barrido y sale")
    ap.add_argument("--catch-up", action="store_true",
                    help="también alertar los bloqueos históricos (por defecto solo los nuevos)")
    args = ap.parse_args()

    webhook = os.environ["WEBHOOK_URL"]
    # por defecto arranca desde "ahora": alerta lo que pase con el bridge corriendo
    last = "1970-01-01 00:00:00" if args.catch_up else time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

    while True:
        for ev in blocked_since(last):
            r = requests.post(webhook, json=to_slack(ev), timeout=10)
            r.raise_for_status()
            print(f"alerta enviada: {ev['method']} {ev['path']} (score {ev['anomaly_score']})")
            last = ev["timestamp"]
        if args.once:
            break
        time.sleep(POLL_EVERY)


if __name__ == "__main__":
    main()
