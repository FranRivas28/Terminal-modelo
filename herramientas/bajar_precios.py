"""Baja 6 meses de cierres diarios (Yahoo) de todas las acciones que aparecen en el dashboard -> precios.json.
Correr después de datos_dashboard.py y antes de volver a armarlo. No necesita instalar nada."""
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).parent
d = json.loads((AQUI / "datos.json").read_text())
tickers = sorted(set([x["t"] for x in d["sp"]["top"]] + [p["ticker"] for p in d["predicciones"]]
                     + [x["t"] for x in d.get("cedears", {}).get("top", [])]
                     + [x["t"] for k in ("sp", "cedears") for x in d.get(k, {}).get("b", {}).get("top", [])]
                     + [b["ticker"] for b in d["balances"]["sp"]["filas"]]
                     + [x["t"] for x in d.get("tercios", {}).get("filas", [])]
                     + [o["t"] for o in d["operaciones"][:30]] + ["SPY", "IWM", "QQQ"]))


def bajar(t):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{t.replace('.', '-')}?range=6mo&interval=1d"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        r = json.loads(urllib.request.urlopen(req, timeout=20).read())["chart"]["result"][0]
        fechas = [datetime.fromtimestamp(s, timezone.utc).date().isoformat() for s in r["timestamp"]]
        return t, dict(zip(fechas, r["indicators"]["adjclose"][0]["adjclose"]))
    except Exception:
        return t, {}


with ThreadPoolExecutor(8) as ex:
    series = dict(ex.map(bajar, tickers))
fechas = sorted({f for s in series.values() for f in s})
out = {"fechas": fechas, "cierres": {}}
for t, s in series.items():
    if sum(v is not None for v in s.values()) > 20:
        out["cierres"][t] = [None if s.get(f) is None else round(float(s[f]), 2) for f in fechas]
(AQUI / "precios.json").write_text(json.dumps(out))
print(len(out["cierres"]), "de", len(tickers), "con precios;", fechas[-1])
