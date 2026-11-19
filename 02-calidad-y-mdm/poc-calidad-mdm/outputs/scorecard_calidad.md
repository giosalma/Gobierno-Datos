# Scorecard Automático de Calidad de Datos y MDM

**Fecha de ejecución:** 2026-11-19 00:52:51  
**Pipeline:** `run_mdm_pipeline.py` (Arquitectura Medallion: Bronze -> Quality Gates -> Silver MDM -> Gold)

---

## 1. Resumen Ejecutivo de Ejecución

| Métrica Clave | Valor Obtenido | Observación |
| :--- | :---: | :--- |
| **Registros ingresados (Bronze)** | **24** | Core (10), CRM (8), Legado (6) |
| **Registros aprobados (Quality Gates)** | **19** | Índice de Calidad Global: **79.17%** |
| **Registros enviados a Cuarentena** | **5** | Bloqueados antes de contaminar Silver/Gold |
| **Golden Records generados (Gold)** | **12** | Vista Única de Cliente certificada |
| **Duplicados consolidados (Match & Merge)** | **7** | Fusiones determinísticas y probabilísticas |
| **Casos en Zona Gris (Stewardship)** | **1** | Pendientes de decisión humana (80% - 91%) |

---

## 2. Cumplimiento de Calidad por Sistema Origen

| Sistema Origen | Total Bronze | Aprobados | En Cuarentena | % Calidad |
| :--- | :---: | :---: | :---: | :---: |
| `CORE_TRANSACCIONAL` | 10 | 9 | 1 | **90.0%** |
| `CRM_COMERCIAL` | 8 | 6 | 2 | **75.0%** |
| `SISTEMA_LEGADO` | 6 | 4 | 2 | **66.67%** |

---

## 3. Evidencia de Trazabilidad y Seguridad
* **PII protegido (*Zero Trust*):** Los campos `num_doc` y `email` fueron enmascarados en la capa analítica `gold_clientes_golden_record.csv`.
* **Linaje reversible:** Cada `mdm_golden_id` conserva sus llaves de origen en `gold_clientes_xref.csv`.
* **Remediación auditable:** Los registros fallidos detallan la dimensión DAMA incumplida en `cuarentena_rechazos.csv`.
