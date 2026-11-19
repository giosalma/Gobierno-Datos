# Prueba de Concepto (PoC $0 USD): Calidad de Datos y MDM

Esta Prueba de Concepto implementa de forma reproducible y sin costo alguno (**$0 USD**) la Arquitectura de Solución diseñada para el caso de uso de **Vista Única de Cliente (Golden Record)**.

---

## Dos Modos de Ejecución Sin Costo

### Modo 1: En la Nube con Google BigQuery Sandbox + Looker Studio ($0 USD, sin tarjeta)
1. Ingresa a [Google Cloud BigQuery Sandbox](https://console.cloud.google.com/bigquery) con tu cuenta de Google.
2. Crea un proyecto gratuito y dentro crea el dataset `mdm_poc`.
3. Sube los 3 archivos de la carpeta `data/` como tablas:
   * `data/core_clientes.csv` → `mdm_poc.bronze_core_clientes`
   * `data/crm_clientes.csv` → `mdm_poc.bronze_crm_clientes`
   * `data/legado_clientes.csv` → `mdm_poc.bronze_legado_clientes`
4. Copia y ejecuta el contenido de `src/bigquery_mdm_sql.sql` en el editor SQL de BigQuery.
5. Conecta [Looker Studio](https://lookerstudio.google.com/) (gratuito) a las tablas `03_gold_dq_scorecard`, `02_cuarentena_dq` y `03_gold_clientes_golden_record` para visualizar el tablero ejecutivo en vivo.

### Modo 2: Ejecución Local en Python (VS Code / Google Colab)
Ejecuta el pipeline completo (incluyendo emparejamiento probabilístico *fuzzy* y bandeja de Zona Gris):

```bash
cd 02-calidad-y-mdm/poc-calidad-mdm
pip install -r requirements.txt
python src/run_mdm_pipeline.py
```

---

## Evidencias Generadas en `outputs/`

Al ejecutar el pipeline sobre los 24 registros sintéticos provenientes de Core (10), CRM (8) y Legado (6), se generan automáticamente:
* **`outputs/gold_clientes_golden_record.csv`:** Vista Única de Cliente consolidada con reglas de supervivencia (*Trust Score* + fecha más reciente) y enmascaramiento PII (*Zero Trust*).
* **`outputs/gold_clientes_xref.csv`:** Tabla de equivalencias (*Cross-Reference*) que garantiza linaje reversible entre el `mdm_golden_id` y cada sistema origen.
* **`outputs/cuarentena_rechazos.csv`:** Registros bloqueados en los *Quality Gates* con la dimensión DAMA fallida y SLA de remediación (`MTTR < 24h`).
* **`outputs/zona_gris_stewardship.csv`:** Candidatos a duplicado en rango `80% – 91%` enrutados para decisión humana del *Data Steward*.
* **`outputs/scorecard_calidad.md`:** Reporte ejecutivo automático con el porcentaje de calidad global y por sistema origen.
