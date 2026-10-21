# Pipeline de Ingeniería de Datos · AutoMarket

Llena la base de datos con el inventario inicial de la agencia a partir de **scraping de catálogos
oficiales** de marcas en México. Se ejecuta una sola vez (o cuando se quiera actualizar el catálogo).
El sistema **no depende** de estos sitios en tiempo de ejecución: los datos quedan en PostgreSQL.

```
 honda.mx / mazda.mx                     PostgreSQL
        │                                    ▲
  1. extract ─► raw/<run>/*.html          4. load (1 transacción, idempotente)
        │       raw/<run>/catalog_raw.csv    │
  2. transform (Pandas) ─► processed/catalog_clean.csv
        │                                    │
  3. generate ─► processed/inventory.csv ────┘
                                          5. stats ─► evidence/<run>/estadisticas.md
```

## Ejecución

Usa el entorno virtual del backend, porque la carga reutiliza sus modelos SQLAlchemy:

```powershell
cd data-pipeline
..\backend\.venv\Scripts\python.exe run_pipeline.py                 # todos los pasos
..\backend\.venv\Scripts\python.exe run_pipeline.py --steps transform,generate,load,stats  # sin descargar
..\backend\.venv\Scripts\python.exe -m pytest tests -q              # pruebas de limpieza
```

## Fuentes y uso permitido

Antes de elegir las fuentes se revisó el `robots.txt` de cada sitio:

| Sitio | robots.txt | Decisión |
|---|---|---|
| honda.mx | `User-agent: * / Disallow:` (todo permitido) | ✅ Usado |
| mazda.mx | Solo bloquea herramientas internas | ✅ Usado (páginas de vehículos) |
| toyota.mx, chevrolet.com.mx | Responden 403 a bots | ❌ Descartado |
| vw.com.mx | Bloquea `/app/` y `/content` para bots | ❌ Descartado |

Reglas del scraper (`automarket_pipeline/http.py`):
- Consulta `robots.txt` **antes de cada URL** y omite lo prohibido (queda registrado).
- Se identifica con un User-Agent propio (`AutoMarketBot/0.1 ... proyecto escolar`).
- Espera **2 s entre peticiones** y reintenta como máximo 3 veces con espera creciente.
- Descarga solo páginas públicas de catálogo: sin inicio de sesión, sin formularios, sin datos personales.

## Procedencia: datos reales vs. derivados

Cada vehículo apunta a un registro de `data_sources` con su tipo:

| Tipo | Qué es | Ejemplo |
|---|---|---|
| `real` | Unidad nueva 0 km con precio y especificaciones **tal como los publica la marca** | Civic i-Style 2026, $605,900 |
| `referencia` | Seminuevo **derivado** de una versión real: año (−1 a −4), kilometraje y precio calculados | CX-5 i Sport 2023, 51,200 km, $356,500 |
| `prueba` | Reservado para datos creados por pruebas automatizadas | — |

Reglas de derivación (`generate.py`, semilla fija = reproducible): depreciación de 12 % anual,
15,000 ± 4,000 km por año, hasta 15 % adicional de descuento por kilometraje y precio redondeado a
múltiplos de $500. El color se elige entre los colores reales de esa versión.

## Limpieza y validación (`transform.py`)

| Problema en el dato crudo | Regla aplicada |
|---|---|
| `"DESDE $ 403,900¹"` | Se quita HTML y notas al pie y se extrae el número: `403900.0` |
| `"MAZDA3 SEDÁN"`, `"MAZDA CX-30"` | Formato título conservando siglas: `Mazda3 Sedán`, `CX-30` |
| `"PRIME CVT"` | Versión normalizada y sin transmisión repetida: `Prime` |
| Marca en mayúsculas o minúsculas | Catálogo controlado: `Honda`, `Mazda` |
| Transmisión en texto libre | Enum: `manual`, `automatica`, `cvt` |
| Una versión con manual **y** automática | Se divide en dos registros de catálogo |
| Motor en texto largo | Formato compacto: `2.0L 4 cil. 150 hp` |
| Combustible implícito (MHEV, diésel) | Enum: `gasolina`, `hibrido`, `diesel`, `electrico` |
| Año, precio, transmisión o motor inválidos | Se rechaza el registro → `rechazados.csv` con su motivo |
| Duplicados por marca, modelo, año, versión y transmisión | Se conserva el primero → `duplicados.csv` |

## Evidencias de cada corrida

`raw/<run_id>/` guarda el HTML original de cada página descargada, sin modificar. **Ese HTML no se
publica en el repositorio**: es contenido de Honda y Mazda, y su `robots.txt` permite consultarlo, no
redistribuirlo. En el repositorio quedan `catalog_raw.csv` (los datos extraídos) y
`manifest_descargas.json`, que registra cada URL con la huella SHA-256 de lo descargado. El HTML se
regenera ejecutando el paso `extract`.
`evidence/<run_id>/` contiene:

| Archivo | Contenido |
|---|---|
| `pipeline.log` | Bitácora completa con fecha y hora |
| `manifest_descargas.json` | Cada URL con estado HTTP, bytes, **SHA-256**, intentos y fecha |
| `transform_report.json` | Nulos antes y después, rechazados por motivo, duplicados y tipos de dato |
| `catalog_clean.csv`, `inventory.csv` | Salidas de la transformación y de la generación |
| `rechazados.csv`, `duplicados.csv` | Registros descartados y su motivo |
| `inventario_en_bd.csv`, `estadisticas.md` | Lo que quedó en PostgreSQL y sus estadísticas |
| `resumen.json` | Filas y duración de cada paso |

## Idempotencia

El folio (`stock_number`, por ejemplo `AM-AE8705C5`) se calcula con un hash de la llave natural del
vehículo. Volver a ejecutar la carga **no duplica** registros: los existentes se omiten con
`ON CONFLICT DO NOTHING`. Cada vehículo insertado deja un evento `carga_inicial` en
`operation_history` y su `INSERT` en `audit_log` (vía trigger).
