"""Junta las elegidas de la semana (small caps y S&P 500), los balances y el backtest en dashboard/datos.json,
que es lo único que lee la página del dashboard (index.html)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
SEG = BASE / "seguimiento"

ops = pd.read_csv(SEG / "backtest_panel.csv", parse_dates=["fecha"])
ev = pd.read_csv(SEG / "backtest_evaluaciones.csv", parse_dates=["semana"])
pred = pd.read_csv(SEG / "predicciones.csv")
CART = BASE / "cartera"
if (CART / "cartera_small.csv").exists():   # cartera rotada (cartera/rotar_small.py): reemplaza a las predicciones de 1 semana
    pred = pd.read_csv(CART / "cartera_small.csv")
regla = pd.read_csv(SEG / "regla_seguimiento.csv")
resumen = pd.read_csv(SEG / "backtest_resumen.csv")

# Semana a semana: el modelo reparte en partes iguales entre las que pasan; sin candidatas queda en efectivo.
semanas = sorted(ev["semana"].unique())
mod = ops.groupby("fecha")["ret_real"].mean().reindex(semanas).fillna(0.0)
lista = ev.groupby("semana")["ret_real"].mean().reindex(semanas)
n_ops = ops.groupby("fecha").size().reindex(semanas).fillna(0).astype(int)
curva = (1 + mod).cumprod()
curva_lista = (1 + lista).cumprod()
dd = curva / curva.cummax() - 1

r = ops["ret_real"]
gan, per = r[r > 0], r[r <= 0]
por_ticker = ops.groupby("ticker")["ret_real"].agg(["sum", "count"]).query("count >= 2").sort_values("sum")
top5 = r.sort_values(ascending=False).head(5).sum() / r.sum()
sem_con = mod[n_ops > 0]

def fila(nombre):
    return resumen.loc[resumen["indicador"] == nombre].iloc[0]

ventaja = fila("Ventaja vs. la lista (misma semana)")
filtros = []
for _, f in resumen[resumen["indicador"].str.startswith("Filtro ")].iterrows():
    a, b = [float(x.strip().rstrip("%")) for x in f["valor"].split("vs")]
    filtros.append({"filtro": f["indicador"].split()[1].rstrip(":").capitalize().replace("Tecnico", "Técnico"), "pasan": a, "no_pasan": b})

datos = {
    "actualizado": str(pd.Timestamp.today().date()),
    "desde": str(semanas[0].date()), "hasta": str(semanas[-1].date()),
    "kpi": {
        "total": float(curva.iloc[-1] - 1), "total_lista": float(curva_lista.iloc[-1] - 1),
        "ventaja_sem": ventaja["valor"], "ventaja_margen": ventaja["margen_95"],
        "operaciones": int(len(r)), "ganadas": int(len(gan)), "perdidas": int(len(per)),
        "win": float(len(gan) / len(r)), "prom_gan": float(gan.mean()), "prom_per": float(per.mean()),
        "profit_factor": float(gan.sum() / -per.sum()), "esperanza": float(r.mean()),
        "max_dd": float(dd.min()), "semanas": len(semanas), "semanas_con": int((n_ops > 0).sum()),
        "stops": float(ops["toco_stop"].mean()),
    },
    "semanal": [{"f": str(s.date()), "m": round(float(mod[s]), 5), "l": round(float(lista[s]), 5),
                 "c": round(float(curva[s] - 1), 5), "cl": round(float(curva_lista[s] - 1), 5),
                 "dd": round(float(dd[s]), 5), "n": int(n_ops[s])} for s in semanas],
    "operaciones": [{"f": str(o.fecha.date()), "t": o.ticker, "s": round(o.score, 2), "r": round(o.ret_real, 4),
                     "stop": bool(o.toco_stop)} for o in ops.sort_values("fecha", ascending=False).itertuples()],
    "predicciones": pred.astype(object).where(pred.notna(), None).to_dict(orient="records"),
    "vence_small": (str(pred["vence"].max()) if "vence" in pred else str((pd.Timestamp(pred["fecha"].max()) + pd.Timedelta(days=7)).date())) if len(pred) else "",
    "regla": regla.fillna("").to_dict(orient="records"),
    "filtros": filtros,
    "insights": {
        "mejor": [por_ticker.index[-1], float(por_ticker["sum"].iloc[-1]), int(por_ticker["count"].iloc[-1])],
        "peor": [por_ticker.index[0], float(por_ticker["sum"].iloc[0]), int(por_ticker["count"].iloc[0])],
        "mejor_sem": [str(sem_con.idxmax().date()), float(sem_con.max())],
        "peor_sem": [str(sem_con.idxmin().date()), float(sem_con.min())],
        "top5": float(top5), "rel_gp": float(per.min() / -gan.mean()),
        "rho": float(fila("Relación puntaje → retorno (correlación de rangos)")["valor"]),
    },
}

# ---------- Small caps: nombre de cada elegida, regla "evitar" (secundaria) y señales probadas ----------
EST, SP = BASE / "estudio", BASE / "sp500"
nombres = pd.read_csv(EST / "universo.csv").drop_duplicates("ticker").set_index("ticker")["nombre"]
for p in datos["predicciones"]:
    p["empresa"] = str(nombres.get(p["ticker"], ""))
al = pd.read_csv(SEG / "alertas.csv")
al = al[al["fecha"] == al["fecha"].max()]
motivos = {"Mucha cobertura": int((al["alerta_cobertura"] == "sí").sum()), "Salto de noticias": int((al["alerta_salto"] == "sí").sum()),
           "Ventas de directivos": int((al["alerta_ventas"] == "sí").sum())}
def razones(f):
    return ", ".join(n for n, c in [("cobertura", "alerta_cobertura"), ("salto", "alerta_salto"), ("ventas", "alerta_ventas")] if f[c] == "sí")
rs = pd.read_csv(EST / "regla_semanal.csv").dropna(subset=["diferencia_4s"])
sen = pd.read_csv(EST / "senales.csv")
datos["small"] = {
    "fecha": al["fecha"].max(), "evaluadas": int(len(al)), "evitar": int((al["evitar"] == "sí").sum()), "motivos": motivos,
    "lista_evitar": [{"t": f["ticker"], "m": razones(f)} for _, f in al[al["evitar"] == "sí"].iterrows()],
    "regla_hist": [{"f": f.fecha, "d": round(f.diferencia_4s, 5)} for f in rs.itertuples()],
    "senales": [{"s": f.senal, "tipo": f.tipo, "d": f.diferencia_1s, "lo": f.margen_bajo, "hi": f.margen_alto} for f in sen.itertuples()],
}

# ---------- S&P 500: elección de la semana, embudo y filtros ----------
sel = pd.read_csv(SP / "seleccion_sp500.csv")
evs = pd.read_csv(SP / "evaluacion_sp500.csv")
orden = ["sentimiento", "tecnico", "momentum", "ganancias", "graham", "pasa todo"]
top = sel[sel["top10"] == "sí"].sort_values("puntaje", ascending=False)
datos["sp"] = {
    "fecha": sel["fecha"].max(), "vence": pd.read_csv(SP / "prediccion_sp500.csv")["vence"].max(), "evaluadas": int(len(evs)), "pasan": int((evs["cae_en"] == "pasa todo").sum()),
    "embudo": [{"etapa": e, "n": int((evs["cae_en"] == e).sum())} for e in orden],
    "top": [{"t": f.ticker, "e": f.empresa, "sec": f.sector, "p": f.puntaje, "px": round(f.precio, 2), "piso": f.piso, "techo": f.techo,
             "rango": f.rango_mes_pct, "bal": f.balance if isinstance(f.balance, str) else "", "evitar": f.evitar,
             "motivos": f.motivos if isinstance(f.motivos, str) else "",
             "cedear": f.cedear_ratio if isinstance(f.cedear_ratio, str) else ""} for f in top.itertuples()],
    "con_cedear": int(sel["cedear_ratio"].notna().sum()),
    "filtros": pd.read_csv(SP / "terminal_filtros.csv").to_dict(orient="records"),
}

# ---------- CEDEARs: los 10 de mejor puntaje, misma foto que el S&P 500 (cedears/top_cedears.py) ----------
ced = BASE / "cedears" / "seleccion_cedears.csv"
if ced.exists():
    cd = pd.read_csv(ced)
    tc = cd[cd["top10"] == "sí"].sort_values("puntaje", ascending=False)
    orden_c = ["universo", "sentimiento", "tecnico", "momentum", "ganancias", "graham", "pasa todo"]
    texto = lambda x: x if isinstance(x, str) else ""
    datos["cedears"] = {
        "fecha": cd["fecha"].max(), "vence": str((pd.Timestamp(cd["fecha"].max()) + pd.Timedelta(days=28)).date()),
        "total": int(len(cd)), "evaluadas": int(cd["cae_en"].notna().sum()), "pasan": int((cd["cae_en"] == "pasa todo").sum()),
        "en_sp": int((tc["en_sp500"] == "sí").sum()),
        "embudo": [{"etapa": e, "n": int((cd["cae_en"] == e).sum())} for e in orden_c if (cd["cae_en"] == e).any()],
        "top": [{"t": f.ticker, "cedear": f.cedear, "ratio": texto(f.ratio), "e": texto(f.empresa), "sec": texto(f.sector),
                 "p": f.puntaje, "px": round(f.precio, 2), "piso": f.piso, "techo": f.techo, "bal": texto(f.balance),
                 "sp": f.en_sp500 == "sí"} for f in tc.itertuples()],
    }

# ---------- Regla nueva (10/11/2026): impulso de 12 meses, revisión cada 3 meses (cartera/seleccion_trimestral.py) ----------
def trimestral(nombre):
    f = CART / f"seleccion_{nombre}.csv"
    if not f.exists():
        return None
    d = pd.read_csv(f).sort_values("puesto")
    texto = lambda x: x if isinstance(x, str) else ""
    return {"fecha": d["fecha"].iloc[0], "vence": d["revision"].iloc[0],
            "top": [{"t": r.ticker, "e": texto(r.empresa), "sec": texto(r.sector), "p": r.suba_12m, "px": r.precio, "piso": r.piso_3m,
                     "techo": r.techo_3m, "rango": r.rango_3m_pct, "stop": r.stop, "peso": r.peso, "grupo": r.grupo, "puesto": int(r.puesto),
                     "bal": texto(r.balance), "cedear": texto(r.cedear), "ratio": texto(r.ratio), "sp": True,
                     "evitar": "", "motivos": "", **({"mf": r.mf_puesto, "per": r.per} if "mf_puesto" in d else {})} for r in d.itertuples()]}
for clave, nombre in (("sp", "sp500"), ("cedears", "cedears")):
    t = trimestral(nombre)
    if t:
        datos[clave].update({**t, "regla": "impulso12"})
    b = trimestral(f"b_{nombre}")  # regla B en prueba (cartera/seleccion_b.py)
    if b:
        datos[clave]["b"] = b
if (CART / "cartera_tercios.csv").exists():  # cartera simulada 1/3 SPY + 1/3 QQQ + 1/3 regla B (cartera/cartera_tercios.py)
    ct = pd.read_csv(CART / "cartera_tercios.csv")
    datos["tercios"] = {"inicio": ct.inicio.iloc[0], "revision": ct.revision.iloc[0], "capital": float(ct.monto_usd.sum()),
                        "efectivo": round(float(ct.capital.iloc[0] - ct.monto_usd.sum()), 2) if "capital" in ct else 0,
                        "filas": [{"t": r.ticker, "parte": r.parte, "e": r.nombre, "peso": r.peso, "monto": r.monto_usd, "px": r.precio_entrada,
                                   **({"n": int(r.cedears), "ratio": r.ratio} if "cedears" in ct else {})} for r in ct.itertuples()]}
if (CART / "vendidas_small.csv").exists():
    datos["vendidas_small"] = pd.read_csv(CART / "vendidas_small.csv").to_dict(orient="records")

# ---------- Balances de las próximas dos semanas ----------
def proximos(nombre, prob):
    b = pd.read_csv(SEG / nombre)
    b = b[pd.to_datetime(b["fecha"]) <= pd.Timestamp(b["fecha"].min()) + pd.Timedelta(days=13)]
    return {"filas": b.fillna("").sort_values(["fecha", "prob_superar"], ascending=[True, False]).to_dict(orient="records"),
            "prob": pd.read_csv(SP / "balances" / prob).to_dict(orient="records")}
datos["balances"] = {"sp": proximos("proximos_balances.csv", "probabilidad_superar.csv"),
                     "small": proximos("proximos_balances_small.csv", "probabilidad_superar_small.csv"),
                     "aviso": pd.read_csv(SP / "aviso_balance_sp500.csv").to_dict(orient="records")}

# ---------- Balances ya presentados: resultado y reacción del precio (resultados_balances.py) ----------
rb = SEG / "resultados_balances.csv"
if rb.exists():
    r = pd.read_csv(rb)
    r = r[pd.to_datetime(r["fecha"]) >= pd.Timestamp.today().normalize() - pd.Timedelta(days=28)]
    datos["balances"]["resultados"] = r[["ticker", "fecha", "hora", "mercado", "prob_superar", "mov_tipico_pct", "eps_estimado",
                                         "eps_real", "supero", "sorpresa_pct", "dia_reaccion", "reaccion", "indice",
                                         "reaccion_indice", "hasta_hoy"]].astype(object).where(r.notna(), None).to_dict(orient="records")

# ---------- Checkpoints: foto de cómo vienen las elegidas, uno por fecha (checkpoint.py) ----------
cps = BASE / "checkpoints" / "checkpoints.json"
datos["checkpoints"] = json.loads(cps.read_text()) if cps.exists() else []

# ---------- Canastas a 1, 3 y 6 meses: cada viernes del pasado, comprar lo elegido y aguantar (canasta/plazos.py) ----------
pl = BASE / "canasta"
if (pl / "plazos_resumen.csv").exists():
    c = pd.read_csv(pl / "plazos_canastas.csv").sort_values(["grupo", "plazo", "fecha"])
    datos["plazos"] = {"canastas": c[["grupo", "fecha", "plazo", "tickers", "canasta", "indice"]].round(4).to_dict(orient="records"),
                       "resumen": pd.read_csv(pl / "plazos_resumen.csv").round(4).to_dict(orient="records")}

bal_small = {b["ticker"]: b["fecha"] for b in datos["balances"]["small"]["filas"]}
for p in datos["predicciones"]:
    p["balance"] = bal_small.get(p["ticker"], "")

def limpiar(x):  # NaN no es JSON válido: pasa a null
    if isinstance(x, dict): return {k: limpiar(v) for k, v in x.items()}
    if isinstance(x, list): return [limpiar(v) for v in x]
    if isinstance(x, float) and np.isnan(x): return None
    return x
datos = limpiar(datos)
precios = Path(__file__).parent / "precios.json"  # de bajar_precios.py
if precios.exists():
    datos["precios"] = json.loads(precios.read_text())
# ---------- Backtest de las reglas actuales (rotacion/t26_*.py y t27_mejoras.py, 11/11/2026) ----------
ROT = BASE / "rotacion"
if (ROT / "t27/metricas.csv").exists():
    NOM = {"Regla actual": "Impulso 12 m", "A: no comprar si SPY cayó": "A: no comprar si SPY cayó",
           "B: Magic Formula entre las de impulso": "Regla B", "SPY": "SPY", "QQQ": "QQQ", "A + B juntas": "A + B juntas",
           "Magic Formula sola": "Magic Formula sola", "Mitad SPY + mitad A+B": "Mitad SPY + mitad A+B"}
    met = pd.read_csv(ROT / "t27/metricas.csv")
    met = met[met.version.isin(NOM)].assign(version=lambda d: d.version.map(NOM))
    bt2 = {"metricas": met.round(3).replace({np.nan: None}).to_dict(orient="records"), "curvas": {}, "caidas": {}}
    for v, cols in (("2011-2026", ["Regla actual", "B: Magic Formula entre las de impulso", "SPY", "QQQ"]),
                    ("2000-2026", ["Regla actual", "A: no comprar si SPY cayó", "SPY", "QQQ"])):
        for clave, arch in (("curvas", "curvas"), ("caidas", "caidas")):
            c = pd.read_csv(ROT / f"t27/{arch}_{v}.csv")
            c = c.iloc[::2] if len(c) > 1000 else c  # cada 2 semanas en la ventana larga
            bt2[clave][v] = {"f": c.fecha.tolist(), "s": {NOM[k]: c[k].round(1).tolist() for k in cols}}
    tr = pd.read_csv(ROT / "t27/metricas_tramos.csv")
    tr = tr[tr.version.isin(["Regla actual", "B: Magic Formula entre las de impulso", "A: no comprar si SPY cayó", "SPY", "QQQ"])]
    bt2["tramos"] = tr.assign(version=tr.version.map(NOM))[["ventana", "version", "tramo", "cagr", "sharpe", "caida"]].round(2).to_dict(orient="records")
    an = pd.read_csv(ROT / "t27/anual.csv")
    bt2["anual"] = an.assign(version=an.version.map(NOM)).to_dict(orient="records")
    pr = pd.read_csv(ROT / "t26/precio_resumen.csv")
    pr = pr[pr.lapso == "Todo 2000-2026"]
    bt2["pruebas"] = pr[["prueba", "medio", "gana_a_spy", "caida_mediana"]].replace({np.nan: None}).to_dict(orient="records")
    bt2["spy_2000"] = float(pr.spy.iloc[0]); bt2["qqq_2000"] = float(pr.qqq.iloc[0])
    ap = pd.read_csv(ROT / "t26/aportes_resumen_2011.csv")
    ap = ap[(ap["años"] == 5) & ap.cartera.isin(["Regla (5 acc.)", "Magic Formula entre las de impulso", "SPY solo", "QQQ solo", "Mitad SPY + mitad regla"])]
    bt2["aportes"] = ap[["cartera", "arranques", "puesto", "final_mediano", "final_malo", "final_bueno", "pierde", "caida_peor"]].to_dict(orient="records")
    datos["bt2"] = bt2

(Path(__file__).parent / "datos.json").write_text(json.dumps(datos, ensure_ascii=False, default=str))
print(json.dumps(datos["kpi"], indent=1), datos["insights"])

# La página lleva los datos adentro, así funciona sola (Vercel o vista previa) sin pedir nada a ningún servidor.
plantilla = (Path(__file__).parent / "plantilla.html").read_text()
json_seguro = json.dumps(datos, ensure_ascii=False, default=str).replace("</", "<\\/")
pagina = plantilla.replace("/*DATOS*/", json_seguro)
(Path(__file__).parent / "vista_previa.html").write_text(pagina)  # para la vista previa en claude.ai
cabeza, cuerpo = pagina.split("</style>", 1)  # para Vercel: documento completo
(Path(__file__).parent / "index.html").write_text(
    '<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
    + cabeza + "body { margin: 0; }\n[hidden] { display: none !important; }\n</style>\n</head>\n<body>\n" + cuerpo + "\n</body>\n</html>\n")
