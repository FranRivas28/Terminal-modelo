# Terminal Cascada

Dashboard del modelo predictivo en cascada (small caps EE.UU., S&P 500, CEDEARs y balances). Herramienta de investigación y paper trading: no es asesoría financiera.

- `index.html`: la página completa, con los datos de la última corrida adentro.
- `api/cotizaciones.js`: función de Vercel que trae precios en vivo de Finnhub. Necesita la variable de entorno `FINNHUB_API_KEY`.
- `herramientas/`: scripts que arman `index.html` a partir de los resultados del modelo (`datos_dashboard.py`, `bajar_precios.py`, `plantilla.html`) y `top_cedears.py` (los 10 CEDEARs de mejor puntaje; va en `cedears/` de la carpeta del modelo y se corre después de la elección del S&P 500). Se corren desde la carpeta del modelo, no en Vercel.

## Publicar en Vercel

1. En vercel.com: Add New → Project → importar este repositorio (sin cambiar nada de la configuración).
2. En Environment Variables agregar `FINNHUB_API_KEY` con la clave de Finnhub.
3. Deploy.
