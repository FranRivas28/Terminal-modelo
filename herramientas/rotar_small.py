"""Rotación de la cartera de small caps (10/11/2026, pedido de Francisco).

1. Se revisan las elegidas vigentes (seguimiento/predicciones.csv): si en algún día desde la entrada el mínimo tocó el stop,
   se considera vendida al stop (o a la apertura si abrió más abajo).
2. Solo esos lugares se llenan con las de mejor puntaje de la cascada de hoy (cascada_small_hoy.csv) que pasan todos los filtros
   y no estaban en la cartera. Si no alcanzan, el lugar queda en efectivo.
3. Las que siguen mantienen su precio de entrada y su stop sube si hoy da uno más alto (precio − 1,5 ATR; nunca baja).
4. Predicción a 3 meses: rango ±1 desvío con la volatilidad de 60 días (no se proyecta suba: el modelo no mostró ventaja).

Salida: cartera_small.csv (la cartera vigente) y vendidas_small.csv.
"""
import json, urllib.request
from pathlib import Path
import numpy as np
import pandas as pd

AQUI = Path(__file__).parent
BASE = AQUI.parent
LUGARES = 9


def precios(t, rango="6mo"):
    u = f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range={rango}&interval=1d"
    j = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read())["chart"]["result"][0]
    q = j["indicators"]["quote"][0]
    return pd.DataFrame({k: q[n] for k, n in [("o", "open"), ("h", "high"), ("l", "low"), ("c", "close")]},
                        index=pd.to_datetime(j["timestamp"], unit="s").normalize()).dropna()


def medidas(d):
    rg = pd.concat([d.h - d.l, (d.h - d.c.shift()).abs(), (d.l - d.c.shift()).abs()], axis=1).max(axis=1)
    return float(d.c.iloc[-1]), float(rg.rolling(14).mean().iloc[-1]), float(np.log(d.c).diff().iloc[-60:].std())


pred = pd.read_csv(BASE / "seguimiento/predicciones.csv")
hoy_c = pd.read_csv(AQUI / "cascada_small_hoy.csv")
sigue, vendidas = [], []
for r in pred.itertuples():
    d = precios(r.ticker)
    despues = d[d.index > pd.Timestamp(r.fecha)]
    toco = despues[despues.l <= r.stop]
    if len(toco):
        dia = toco.index[0]; salida = min(r.stop, float(toco.o.iloc[0]))
        vendidas.append({"ticker": r.ticker, "entrada": r.fecha, "precio_entrada": r.precio_entrada, "stop": r.stop,
                         "vendida": dia.date().isoformat(), "precio_salida": round(salida, 2), "resultado": round(salida / r.precio_entrada - 1, 4),
                         "hoy": round(float(d.c.iloc[-1]), 2)})
    else:
        sigue.append((r, d))
hoy = None
filas = []
for r, d in sigue:
    px, atr, vol = medidas(d); hoy = d.index[-1]
    filas.append({"fecha": r.fecha, "ticker": r.ticker, "precio_entrada": r.precio_entrada, "score": r.score, "estado": "sigue",
                  "stop": round(max(r.stop, px - 1.5 * atr), 2), "vol_diaria": vol, "precio_hoy": round(px, 2)})
libres = LUGARES - len(filas)
fuera = set(pred.ticker)
cand = hoy_c[(hoy_c.cae_en == "pasa todo") & ~hoy_c.ticker.isin(fuera)].sort_values("score", ascending=False).head(libres)
for r in cand.itertuples():
    d = precios(r.ticker); px, atr, vol = medidas(d); hoy = d.index[-1]
    filas.append({"fecha": hoy.date().isoformat(), "ticker": r.ticker, "precio_entrada": round(px, 2), "score": r.score, "estado": "nueva",
                  "stop": round(px - 1.5 * atr, 2), "vol_diaria": vol, "precio_hoy": round(px, 2)})
C = pd.DataFrame(filas)
C["vence"] = [(pd.Timestamp(f) + pd.DateOffset(months=3)).date().isoformat() for f in C.fecha]
C["banda"] = (C.vol_diaria * np.sqrt(63)).round(4)          # ±1 desvío a 3 meses (en proporción del precio)
C["vol_semanal"] = (C.vol_diaria * np.sqrt(5)).round(4)
C["ret_esperado"] = 0.0
C["stop_desde"] = hoy.date().isoformat()   # el stop (subido o nuevo) cuenta desde esta revisión
C = C.drop(columns="vol_diaria")
C.to_csv(AQUI / "cartera_small.csv", index=False)
pd.DataFrame(vendidas).to_csv(AQUI / "vendidas_small.csv", index=False)
print("vendidas por stop:"); print(pd.DataFrame(vendidas).to_string(index=False))
print(f"\ncartera ({len(C)} de {LUGARES}; {LUGARES - len(C)} lugares en efectivo):"); print(C.to_string(index=False))
