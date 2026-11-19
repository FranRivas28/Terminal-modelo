"""Baja 6 meses de cierres diarios (Yahoo) de todas las acciones que aparecen en el dashboard -> precios.json.
También baja precios cada 15 minutos (Yahoo) de la cartera 1/3 desde el día de la compra (gráfico del Resumen).
Y el valor de mercado de las elegidas (Finnhub) para el tamaño de los cuadros del mapa de calor.
Correr después de datos_dashboard.py y antes de volver a armarlo. No necesita instalar nada."""
import json
import os
import urllib.parse
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
    for intento in range(3):  # Yahoo a veces falla una vez: se reintenta
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            r = json.loads(urllib.request.urlopen(req, timeout=20).read())["chart"]["result"][0]
            fechas = [datetime.fromtimestamp(s, timezone.utc).date().isoformat() for s in r["timestamp"]]
            return t, dict(zip(fechas, r["indicators"]["adjclose"][0]["adjclose"]))
        except Exception:
            pass
    return t, {}


with ThreadPoolExecutor(8) as ex:
    series = dict(ex.map(bajar, tickers))
fechas = sorted({f for s in series.values() for f in s})
out = {"fechas": fechas, "cierres": {}}
for t, s in series.items():
    if sum(v is not None for v in s.values()) > 20:
        out["cierres"][t] = [None if s.get(f) is None else round(float(s[f]), 2) for f in fechas]
# último y anterior cierre de todas (aunque Yahoo traiga poca historia): cambio de hoy del mapa de calor
out["ultimos"] = {t: [round(float(v), 2) for v in [s[f] for f in sorted(s) if s[f] is not None][-2:]]
                  for t, s in series.items() if sum(v is not None for v in s.values()) >= 2}


# ---------- cartera 1/3: precios dentro del día desde la compra (gráfico del Resumen) ----------
def bajar_intradia(t, desde, intervalo):
    p1 = int(datetime.fromisoformat(desde).replace(tzinfo=timezone.utc).timestamp())
    p2 = int(datetime.now(timezone.utc).timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{t.replace('.', '-')}?period1={p1}&period2={p2}&interval={intervalo}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        r = json.loads(urllib.request.urlopen(req, timeout=20).read())["chart"]["result"][0]
        return t, {s: c for s, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c is not None}
    except Exception:
        return t, {}


ter = d.get("tercios")
if ter and ter.get("filas"):
    dias_desde = (datetime.now(timezone.utc).date() - datetime.fromisoformat(ter["inicio"]).date()).days
    intervalo = "15m" if dias_desde <= 45 else "30m" if dias_desde <= 55 else "1h"  # Yahoo da 15 y 30 min solo de los últimos 60 días
    tk = sorted({x["t"] for x in ter["filas"]} | {"SPY", "QQQ"})
    with ThreadPoolExecutor(8) as ex:
        intra = dict(ex.map(lambda t: bajar_intradia(t, ter["inicio"], intervalo), tk))
    ts = sorted({s for v in intra.values() for s in v})
    out["intradia"] = {"intervalo": intervalo, "desde": ter["inicio"], "ts": ts,
                       "cierres": {t: [None if v.get(s) is None else round(float(v[s]), 3) for s in ts] for t, v in intra.items() if v}}
    print("cartera 1/3 cada", intervalo + ":", len(ts), "puntos de", len(out["intradia"]["cierres"]), "activos")


# ---------- mapa de calor del Resumen: tamaño de cada empresa (valor de mercado, Finnhub, en millones de USD) ----------
def valor_mercado(t):
    params = {"symbol": t}
    if os.environ.get("FINNHUB_API_KEY"):  # en el entorno de Claude la clave la pone el proxy
        params["token"] = os.environ["FINNHUB_API_KEY"]
    try:
        url = "https://finnhub.io/api/v1/stock/profile2?" + urllib.parse.urlencode(params)
        v = json.loads(urllib.request.urlopen(url, timeout=20).read()).get("marketCapitalization")
        return t, round(float(v), 1) if v else None
    except Exception:
        return t, None


elegidas = sorted({p["ticker"] for p in d["predicciones"]} | {x["t"] for x in d.get("cedears", {}).get("top", [])}
                  | {x["t"] for x in d.get("cedears", {}).get("b", {}).get("top", [])})
with ThreadPoolExecutor(4) as ex:
    out["mcap"] = {t: v for t, v in ex.map(valor_mercado, elegidas) if v}
print("valor de mercado:", len(out["mcap"]), "de", len(elegidas))
(AQUI / "precios.json").write_text(json.dumps(out))
print(len(out["cierres"]), "de", len(tickers), "con precios;", fechas[-1])
