"""Los 10 CEDEARs de mejor puntaje del modelo, con la foto del mismo día que la elección del S&P 500.

    python cedears/top_cedears.py <cache> <precios_sp.pkl>     # después de sp500/seleccion_sp500.py

- Lista: sp500/cedears_byma_2026-09-16.csv. Se usan solo acciones que cotizan en EE.UU. (no ETFs, ni Brasil/Alemania/OTC).
- Las que están en el S&P 500 toman la evaluación ya hecha (sp500/evaluacion_sp500.csv).
- Las demás (MELI, VIST, TSM, etc.) se evalúan acá, con la misma cascada y el mismo enfoque del S&P: sin filtro de tamaño,
  momentum contra SPY y solo lo que se sabía ese día. Datos: Finnhub (noticias, balances, directivos) y Yahoo (precios).
  Muchas extranjeras no reportan a la SEC con normas de EE.UU.: para Graham se usan P/E y P/B de Finnhub (son cocientes,
  no dependen de la moneda del balance).
Salida: cedears/seleccion_cedears.csv (todas las evaluadas) con columna top10.
"""
import json
import pickle
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "sp500"))
from backtest import FuenteHistorica  # noqa: E402
from backtest_sp500 import pl, universo_sp  # noqa: E402
from bajar_sp500 import FinnhubRapido  # noqa: E402

AQUI, SP = Path(__file__).parent, RAIZ / "sp500"
MERCADOS_EEUU = {"NYSE", "NASDAQ", "NASDAQ GS", "NASDAQ GM", "NASDAQ CM", "NYSE American", "New York"}
# Código del CEDEAR en BYMA -> símbolo en EE.UU. cuando no coinciden
SIMBOLO = {"BRKB": "BRK-B", "DISN": "DIS", "BA.C": "BAC", "TRVV": "TRV", "BBV": "BBVA", "NOKA": "NOK", "TEN": "TS",
           "TXR": "TX", "AKO.B": "AKO-B", "BNG": "BG", "KOFM": "KOF", "PKS": "PKX", "UN": "NU", "XROX": "XRX",
           "ADGO": "AGRO"}


def precios_yahoo(t):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=1y&interval=1d"
    r = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}),
                                          timeout=20).read())["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    idx = pd.to_datetime([datetime.fromtimestamp(s, timezone.utc).date() for s in r["timestamp"]])
    return pd.DataFrame({k: q[k] for k in ("open", "high", "low", "close", "volume")}, index=idx).dropna()


def bajar(fh, dest, t, hoy):
    f = dest / f"{t}.pkl"
    if f.exists():
        return pickle.loads(f.read_bytes())
    s = t.replace("-", ".")
    perfil = fh._get("stock/profile2", symbol=s)
    d = {"perfil": perfil}
    if perfil.get("marketCapitalization"):  # vacío = ETF o ya no cotiza
        noticias = []
        for a, b in (("2026-09-25", "2026-10-11"), ("2026-10-12", hoy.date().isoformat())):
            noticias += [{"texto": f'{n["headline"]}. {n.get("summary", "")}', "momento": pd.Timestamp(n["datetime"], unit="s"),
                          "id": n.get("id")} for n in fh._get("company-news", symbol=s, **{"from": a, "to": b})]
        reps = []
        for freq, n in (("quarterly", 12), ("annual", 6)):
            for r in fh._get("stock/financials-reported", symbol=s, freq=freq).get("data", [])[:n]:
                reps.append({"freq": freq, "form": r["form"], "anio": r["year"], "trimestre": r["quarter"],
                             "presentado": pd.Timestamp(r["filedDate"]), "inicio": pd.Timestamp(r["startDate"]),
                             "cierre": pd.Timestamp(r["endDate"]),
                             "bs": {c["concept"]: c["value"] for c in r["report"].get("bs", [])},
                             "ic": {c["concept"]: c["value"] for c in r["report"].get("ic", [])}})
        d.update(noticias=pd.DataFrame(noticias).drop_duplicates("id") if noticias else pd.DataFrame(), reportes=reps,
                 ganancias=fh._get("stock/earnings", symbol=s),
                 insiders=fh._get("stock/insider-transactions", symbol=s, **{"from": "2026-06-01", "to": hoy.date().isoformat()}).get("data", []),
                 metricas=fh._get("stock/metric", symbol=s, metric="all").get("metric", {}))
        try:
            d["precios"] = precios_yahoo(t)
        except Exception:
            d["precios"] = None
    f.write_bytes(pickle.dumps(d))
    return d


class FuenteCedear(FuenteHistorica):
    min_posts = 5

    def __init__(self, mem):
        self._mem = mem

    def _datos(self, ticker):
        return self._mem[ticker]

    def fundamentales(self, ticker, hasta=None):
        f = super().fundamentales(ticker, hasta)
        if not f["eps"] or not f["bvps"]:  # sin balances con normas de EE.UU.: P/E y P/B de Finnhub
            m = self._mem[ticker]["metricas"]
            precio = float(self.precios(ticker, hasta)["close"].iloc[-1])
            pe, pb = m.get("peTTM") or m.get("peBasicExclExtraTTM"), m.get("pbQuarterly") or m.get("pbAnnual")
            f.update(eps=precio / pe if pe and pe > 0 else None, bvps=precio / pb if pb and pb > 0 else None,
                     current_ratio=m.get("currentRatioQuarterly"))
        return f


if __name__ == "__main__":
    cache, ruta_px = Path(sys.argv[1]) / "cedears", sys.argv[2]
    cache.mkdir(parents=True, exist_ok=True)
    ced = pd.read_csv(SP / "cedears_byma_2026-09-16.csv")
    ced = ced[ced.mercado.isin(MERCADOS_EEUU)].drop_duplicates("cedear")
    ced["ticker"] = ced.cedear.map(lambda c: SIMBOLO.get(c, c))
    evs = pd.read_csv(SP / "evaluacion_sp500.csv")
    hoy = pd.Timestamp(evs.fecha.iloc[0])
    en_sp = ced[ced.ticker.isin(evs.ticker)]
    resto = ced[~ced.ticker.isin(evs.ticker)]

    fh, mem = FinnhubRapido(), {}
    spy = pd.read_pickle(ruta_px).xs("SPY", axis=1, level=1).rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna()
    mem["SPY"] = {"precios": spy}
    def uno(t):
        try:
            return t, bajar(fh, cache, t, hoy)
        except Exception as e:
            print(t, "error", e, flush=True)
            return t, {}
    with ThreadPoolExecutor(4) as ex:  # FinnhubRapido mantiene el tope de 60 consultas por minuto entre hilos
        for i, (t, d) in enumerate(ex.map(uno, resto.ticker)):
            mem[t] = d
            if i % 20 == 0:
                print(i, t, flush=True)

    pl.INDICE, pl.filtro_universo = "SPY", universo_sp
    fuente, filas = FuenteCedear(mem), []
    for t in resto.ticker:
        d = mem.get(t, {})
        if d.get("precios") is None or len(d["precios"].loc[:hoy]) < 80:
            continue
        try:
            ev = pl.evaluar(t, fuente, hoy, estricto=False)
        except Exception as e:
            print(t, "no se pudo evaluar:", e)
            continue
        s = {r.filtro: r for r in ev["resultados"]}
        c = d["precios"]["close"].loc[:hoy]
        filas.append({"ticker": t, "cae_en": ev["eliminado_en"] or "pasa todo",
                      "puntaje": None if ev["score"] is None else round(ev["score"], 3),
                      **{f"s_{k}": round(r.score, 2) for k, r in s.items()},
                      "tono_noticias": s["sentimiento"].detalle.get("tono"), "pe": s["graham"].detalle.get("pe"),
                      "empresa": d["perfil"].get("name"), "sector": d["perfil"].get("finnhubIndustry"),
                      "precio": float(c.iloc[-1]), "vol_diaria": float(c.pct_change().iloc[-60:].std())})
    otras = pd.DataFrame(filas)

    # Balance en el mes siguiente (calendario de Finnhub) y rango esperado, igual que prediccion_sp500.py
    bal = {}
    for a in pd.date_range(hoy, hoy + pd.Timedelta(days=28), freq="7D"):
        b = min(a + pd.Timedelta(days=6), hoy + pd.Timedelta(days=28))
        for e in fh._get("calendar/earnings", **{"from": a.date().isoformat(), "to": b.date().isoformat()}).get("earningsCalendar", []):
            if e["date"] > hoy.date().isoformat():
                bal.setdefault(e["symbol"].replace(".", "-"), e["date"])
    aviso = pd.read_csv(SP / "aviso_balance_sp500.csv")
    a4 = aviso[aviso.h == "4s"].set_index("hay_balance").movimiento_medio
    factor = float(a4.get(True, 1) / a4.get(False, 1)) if len(a4) == 2 else 1.4
    otras["balance"] = otras.ticker.map(bal).fillna("")
    banda = otras.vol_diaria * np.sqrt(20) * np.where(otras.balance != "", factor, 1)
    otras["rango_mes_pct"] = (banda * 100).round(1)
    otras["piso"], otras["techo"] = (otras.precio * np.exp(-banda)).round(2), (otras.precio * np.exp(banda)).round(2)
    otras["en_sp500"] = "no"

    sp = evs[evs.ticker.isin(en_sp.ticker)].assign(en_sp500="sí")
    cols = ["ticker", "cae_en", "puntaje", "s_sentimiento", "s_tecnico", "s_momentum", "s_ganancias", "s_graham",
            "s_insiders", "tono_noticias", "pe", "empresa", "sector", "balance", "precio", "rango_mes_pct", "piso", "techo", "en_sp500"]
    todo = pd.concat([sp[cols], otras[cols]], ignore_index=True)
    todo = todo.merge(ced[["ticker", "cedear", "ratio"]], on="ticker", how="left")
    todo.insert(0, "fecha", hoy.date().isoformat())
    todo["balance"] = todo.balance.fillna("")
    todo = todo.sort_values(["puntaje"], ascending=False, na_position="last")
    pasan = todo.cae_en == "pasa todo"
    todo["top10"] = "no"
    todo.loc[todo[pasan].index[:10], "top10"] = "sí"
    todo.to_csv(AQUI / "seleccion_cedears.csv", index=False)
    print(f"{len(ced)} CEDEARs de acciones de EE.UU.; evaluadas {len(todo)} ({len(sp)} del S&P); pasan {int(pasan.sum())}")
    print(todo.cae_en.value_counts().to_string())
    print(todo[todo.top10 == "sí"][["cedear", "ticker", "empresa", "puntaje", "en_sp500", "balance", "precio", "piso", "techo"]].to_string(index=False))
