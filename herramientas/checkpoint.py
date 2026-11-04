"""Checkpoint de las elegidas: cómo vienen las small caps, las del S&P 500 y los CEDEARs desde que se eligieron.

Para cada acción guarda precio de entrada, precio de hoy, rendimiento y si está dentro del cono proyectado.
Para cada grupo lo compara con su índice (IWM o SPY) y con el azar: 20.000 carteras del mismo tamaño
sacadas del universo que evaluó el modelo. El percentil dice a qué porcentaje de esas carteras le ganó.

Se agrega a checkpoints/checkpoints.json (si ya hay uno del mismo día, lo reemplaza). Después rearmar la
terminal con datos_dashboard.py. Uso:  python checkpoint.py ["nota opcional"]
Va en dashboard/ de la carpeta del modelo, igual que datos_dashboard.py. No necesita instalar nada."""
import csv
import json
import math
import random
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SALIDA = BASE / "checkpoints" / "checkpoints.json"
d = json.loads((Path(__file__).parent / "datos.json").read_text())

universo = {
    "small": (BASE / "seguimiento" / "lista_regla.txt").read_text().split(),
    "sp": [r["Symbol"] for r in csv.DictReader(open(BASE / "sp500" / "constituyentes.csv"))],
    "ced": [r["ticker"] for r in csv.DictReader(open(BASE / "cedears" / "seleccion_cedears.csv"))],
}
grupos = [
    {"id": "small", "nombre": "Small caps", "ref": "IWM", "ref_nombre": "Russell 2000", "inicio": d["predicciones"][0]["fecha"],
     "vence": d["vence_small"], "filas": [{"t": p["ticker"], "px": p["precio_entrada"], "ret": p["ret_esperado"],
                                         "banda": p["banda"], "stop": p["stop"]} for p in d["predicciones"]]},
    {"id": "sp", "nombre": "S&P 500", "ref": "SPY", "ref_nombre": "S&P 500", "inicio": d["sp"]["fecha"], "vence": d["sp"]["vence"],
     "filas": [{"t": x["t"], "px": x["px"], "techo": x["techo"]} for x in d["sp"]["top"]]},
    {"id": "ced", "nombre": "CEDEARs", "ref": "SPY", "ref_nombre": "S&P 500", "inicio": d["cedears"]["fecha"],
     "vence": d["cedears"]["vence"], "filas": [{"t": x["t"], "px": x["px"], "techo": x["techo"]} for x in d["cedears"]["top"]]},
]


def bajar(t):  # cierres diarios del último mes (Yahoo)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{t.replace('.', '-')}?range=1mo&interval=1d"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        r = json.loads(urllib.request.urlopen(req, timeout=20).read())["chart"]["result"][0]
        fechas = [datetime.fromtimestamp(s, timezone.utc).date().isoformat() for s in r["timestamp"]]
        return t, {f: v for f, v in zip(fechas, r["indicators"]["quote"][0]["close"]) if v}
    except Exception:
        return t, {}


tickers = sorted({t for u in universo.values() for t in u} | {f["t"] for g in grupos for f in g["filas"]} | {"IWM", "SPY"})
with ThreadPoolExecutor(16) as ex:
    S = dict(ex.map(bajar, tickers))
hoy = max(S["SPY"])


def cierre(t, f):  # último cierre en o antes de la fecha f
    s = S.get(t, {}); ks = [k for k in s if k <= f]
    return s[max(ks)] if ks else None


def rend(t, desde):
    a, b = cierre(t, desde), cierre(t, hoy)
    return b / a - 1 if a and b else None


dias = lambda a, b: (date.fromisoformat(b) - date.fromisoformat(a)).days
random.seed(1)
cp = {"fecha": hoy, "nota": sys.argv[1] if len(sys.argv) > 1 else "", "grupos": []}
for g in grupos:
    f0, fr = g["inicio"], max(0.0, min(1.0, dias(g["inicio"], hoy) / max(1, dias(g["inicio"], g["vence"]))))
    acciones = []
    for e in g["filas"]:
        px = cierre(e["t"], hoy)
        if px is None:
            continue
        if "banda" in e:  # small caps: suba esperada ± banda, se abre como raíz del tiempo
            c = e["px"] * (1 + e["ret"] * fr); h = e["px"] * e["banda"] * math.sqrt(fr); lo, hi = c - h, c + h
        else:  # S&P 500 y CEDEARs: rango a 1 mes centrado en el precio (escala log)
            h = math.log(e["techo"] / e["px"]) * math.sqrt(fr); lo, hi = e["px"] * math.exp(-h), e["px"] * math.exp(h)
        estado = "dentro" if lo <= px <= hi else "arriba" if px > hi else "abajo"
        despues = [v for k, v in S[e["t"]].items() if k > f0]
        stop = bool(e.get("stop") and despues and min(despues) <= e["stop"])
        acciones.append({"t": e["t"], "entrada": e["px"], "hoy": round(px, 2), "r": round(px / e["px"] - 1, 4),
                         "lo": round(lo, 2), "hi": round(hi, 2), "estado": estado, "stop": stop})
    rs = [a["r"] for a in acciones]
    prom, ref = sum(rs) / len(rs), rend(g["ref"], f0)
    con_stop = [(e["stop"] / e["px"] - 1) if a["stop"] else a["r"] for a, e in zip(acciones, [x for x in g["filas"] if cierre(x["t"], hoy)])]
    U = [u for u in (rend(t, f0) for t in universo[g["id"]]) if u is not None and abs(u) < 1.5]
    sims = [sum(random.sample(U, len(rs))) / len(rs) for _ in range(20000)]
    cp["grupos"].append({
        "id": g["id"], "nombre": g["nombre"], "inicio": f0, "vence": g["vence"], "vencido": hoy >= g["vence"],
        "ref": g["ref"], "ref_nombre": g["ref_nombre"], "prom": round(prom, 4), "ref_r": round(ref, 4),
        "prom_stop": round(sum(con_stop) / len(con_stop), 4) if "banda" in g["filas"][0] else None,
        "universo_n": len(U), "universo_r": round(sum(U) / len(U), 4), "percentil": round(100 * sum(s < prom for s in sims) / len(sims)),
        "suben": sum(r > 0 for r in rs), "le_ganan": sum(r > ref for r in rs),
        "dentro": sum(a["estado"] == "dentro" for a in acciones), "arriba": sum(a["estado"] == "arriba" for a in acciones),
        "abajo": sum(a["estado"] == "abajo" for a in acciones), "stops": sum(a["stop"] for a in acciones),
        "acciones": sorted(acciones, key=lambda a: -a["r"]),
    })

hist = json.loads(SALIDA.read_text()) if SALIDA.exists() else []
hist = [c for c in hist if c["fecha"] != hoy] + [cp]
SALIDA.parent.mkdir(exist_ok=True)
SALIDA.write_text(json.dumps(sorted(hist, key=lambda c: c["fecha"]), ensure_ascii=False, indent=1))
for g in cp["grupos"]:
    print(f"{g['nombre']:10} {g['prom']:+.2%} vs {g['ref']} {g['ref_r']:+.2%} · percentil vs azar {g['percentil']} · "
          f"{g['dentro']} dentro, {g['arriba']} arriba, {g['abajo']} abajo, {g['stops']} stop")
print(len(hist), "checkpoints en", SALIDA)
