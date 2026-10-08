# 🎾 Tennis KCR — Modelo de Predicción de Tenis

Aplicación de predicción de partidos ATP/WTA con modelo ML entrenado sobre datos históricos (2019–2026).  
Incluye dashboard Streamlit y API REST con FastAPI.

---

## Estructura del proyecto

```
tennismodelkcr/
├── streamlit_app.py          # Dashboard principal (Streamlit)
├── main.py                   # API REST (FastAPI)
├── requirements.txt          # Dependencias FastAPI/API
├── requirements-streamlit.txt# Dependencias Streamlit
├── .env.example              # Plantilla de variables de entorno
├── Dockerfile                # Para deploy en Railway/Render
├── railway.toml              # Config Railway
│
├── backend/
│   ├── routers/
│   │   ├── predictions.py    # Endpoints de predicción
│   │   ├── rankings.py       # Rankings ATP/WTA
│   │   ├── players.py        # Perfiles de jugadores
│   │   └── auth.py           # Autenticación JWT
│   └── services/
│       ├── model.py          # Carga modelos .pkl y hace predicciones
│       ├── tennis_api.py     # Cliente RapidAPI (live scores, fixtures)
│       ├── config.py         # Variables de entorno
│       └── auth.py           # Lógica de autenticación
│
├── backend/models/           # ⚠️ NO incluido en git (ver abajo)
│   ├── tennis_model_v3.pkl   # Modelo ATP (GBM calibrado, acc ~89%)
│   └── tennis_model_wta.pkl  # Modelo WTA (GBM calibrado, acc ~87%)
│
└── frontend/                 # Assets estáticos (HTML/CSS/JS legacy)
```

> **Los ficheros `.pkl` no se incluyen en git** (están en `.gitignore`).  
> Ver la sección [Modelos ML](#modelos-ml) para obtenerlos o reentrenarlos.

---

## Instalación rápida — Dashboard Streamlit

```bash
git clone https://github.com/TU_USUARIO/tennismodelkcr.git
cd tennismodelkcr

# Instalar dependencias
pip install -r requirements-streamlit.txt

# Configurar variables de entorno
cp .env.example .env
# Edita .env y añade tu RAPIDAPI_KEY

# Copiar los modelos entrenados a backend/models/
mkdir -p backend/models
# cp /ruta/a/tennis_model_v3.pkl backend/models/
# cp /ruta/a/tennis_model_wta.pkl backend/models/

# Arrancar
streamlit run streamlit_app.py
```

Abre `http://localhost:8501` en el navegador.

---

## Instalación — API REST (FastAPI)

```bash
pip install -r requirements.txt

uvicorn main:app --reload
```

Documentación interactiva en `http://localhost:8000/docs`.

---

## Variables de entorno

Copia `.env.example` a `.env` y rellena:

| Variable | Descripción | Requerida |
|---|---|---|
| `RAPIDAPI_KEY` | Clave de [tennis-api-atp-wta-itf](https://rapidapi.com/sportcontentapi/api/tennis-api-atp-wta-itf) | Para datos reales |
| `SECRET_KEY` | Clave secreta JWT (solo API) | Solo para FastAPI |
| `INVITE_CODES` | Códigos de invitación separados por coma | Solo para FastAPI |

Sin `RAPIDAPI_KEY` la app funciona con **datos de demostración**.

---

## Modelos ML

Los modelos no están en git por su tamaño (~4–5 MB cada uno). Tienes dos opciones:

### Opción A — Descargar los modelos pre-entrenados

Descárgalos del último release de este repositorio:

```
backend/models/tennis_model_v3.pkl   # ATP
backend/models/tennis_model_wta.pkl  # WTA
```

### Opción B — Reentrenar desde cero

Necesitas los CSV de datos históricos (`df_500_v2.csv`, `df_wta.csv` + temporadas).  
Ejecuta el script de entrenamiento:

```bash
python scripts/train_v3.py
```

Los modelos se guardan automáticamente en `backend/models/`.

### Características del modelo

- **Algoritmo**: `GradientBoostingClassifier` envuelto en `CalibratedClassifierCV`
- **Features** (26): `rank_diff`, `elo_diff`, `oi_diff`, `surface_wr_diff`, `h2h_diff`, `form_diff`... (ver `backend/services/model.py`)
- **Periodo de entrenamiento**: 2019–2023  
- **Periodo de test**: 2025–2026  
- **Accuracy test**: ATP ~89%, WTA ~87%

---

## Deploy en Railway

```bash
# Asegúrate de tener los .pkl en backend/models/
# El fichero .railwayignore sobreescribe .gitignore para incluirlos

railway login
railway up
```

Variables de entorno a configurar en Railway:
- `RAPIDAPI_KEY`
- `SECRET_KEY`
- `INVITE_CODES`

---

## Screenshots

| Dashboard Streamlit |
|---|
| Tarjetas por partido con % de victoria, superficie, estado en vivo |
| Filtros por torneo, superficie y estado |
| Predicciones en tiempo real con el modelo v3 |

---

## Stack técnico

- **ML**: scikit-learn (GradientBoosting + CalibratedCV), pandas, numpy
- **Dashboard**: Streamlit
- **API**: FastAPI + Uvicorn
- **Datos en vivo**: RapidAPI — tennis-api-atp-wta-itf
- **Deploy**: Railway / Render (Docker)

---

## Licencia

MIT — úsalo libremente para proyectos personales.
