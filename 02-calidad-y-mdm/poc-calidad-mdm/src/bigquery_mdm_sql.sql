-- =============================================================================
-- PoC Calidad de Datos y Master Data Management (MDM) en Google BigQuery Sandbox
-- Costo de ejecución: $0 USD (Capa Always Free / BigQuery Sandbox)
-- Autor: Said Giovanny Salazar Marín (DAMA-CDMP® | TOGAF®)
-- =============================================================================
-- Instrucciones:
-- 1. Crea un dataset llamado `mdm_poc` en tu proyecto de BigQuery Sandbox.
-- 2. Sube los 3 archivos CSV de `data/` como tablas:
--      - `mdm_poc.bronze_core_clientes`
--      - `mdm_poc.bronze_crm_clientes`
--      - `mdm_poc.bronze_legado_clientes`
-- 3. Ejecuta este script completo en el editor SQL de BigQuery.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- CAPA 1: BRONZE UNIFICADO CON TRUST SCORE POR FUENTE
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `mdm_poc.01_bronze_clientes_unificado` AS
SELECT *, 'CORE_TRANSACCIONAL' AS sistema_origen, 95 AS trust_score, CURRENT_TIMESTAMP() AS fecha_ingesta
FROM `mdm_poc.bronze_core_clientes`
UNION ALL
SELECT *, 'CRM_COMERCIAL' AS sistema_origen, 85 AS trust_score, CURRENT_TIMESTAMP() AS fecha_ingesta
FROM `mdm_poc.bronze_crm_clientes`
UNION ALL
SELECT *, 'SISTEMA_LEGADO' AS sistema_origen, 50 AS trust_score, CURRENT_TIMESTAMP() AS fecha_ingesta
FROM `mdm_poc.bronze_legado_clientes`;

-- -----------------------------------------------------------------------------
-- CAPA 2A: QUALITY GATES (6 DIMENSIONES DAMA) -> TABLA DE CUARENTENA
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `mdm_poc.02_cuarentena_dq` AS
WITH evaluacion AS (
  SELECT
    *,
    ARRAY_TO_STRING(ARRAY(
      SELECT err FROM UNNEST([
        IF(NULLIF(TRIM(tipo_doc), '') IS NULL OR NULLIF(TRIM(num_doc), '') IS NULL, 'COMPLETITUD: tipo_doc/num_doc nulo', NULL),
        IF(NULLIF(TRIM(nombre_completo), '') IS NULL, 'COMPLETITUD: nombre_completo nulo', NULL),
        IF(UPPER(TRIM(tipo_doc)) NOT IN ('CC', 'NIT', 'CE', 'PAS'), 'VALIDEZ: tipo_doc fuera de dominio', NULL),
        IF(email IS NOT NULL AND TRIM(email) != '' AND NOT REGEXP_CONTAINS(TRIM(email), r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'), 'VALIDEZ: email inválido', NULL),
        IF(SAFE.PARSE_DATE('%Y-%m-%d', fecha_nacimiento) > CURRENT_DATE() OR EXTRACT(YEAR FROM SAFE.PARSE_DATE('%Y-%m-%d', fecha_nacimiento)) < 1900, 'VALIDEZ: fecha_nacimiento fuera de rango', NULL),
        IF(UPPER(TRIM(estado_cliente)) = 'FALLECIDO' AND UPPER(TRIM(tiene_producto_activo)) = 'SI', 'CONSISTENCIA: Fallecido con producto activo', NULL)
      ]) AS err
      WHERE err IS NOT NULL
    ), ' | ') AS motivo_rechazo
  FROM `mdm_poc.01_bronze_clientes_unificado`
)
SELECT
  id_origen,
  sistema_origen,
  tipo_doc,
  num_doc,
  nombre_completo,
  email,
  estado_cliente,
  motivo_rechazo,
  'MTTR < 24h (Data Steward)' AS sla_remediacion,
  fecha_ingesta
FROM evaluacion
WHERE motivo_rechazo != '';

-- -----------------------------------------------------------------------------
-- CAPA 2B: SILVER ESTANDARIZADO (SOLO REGISTROS APROBADOS)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `mdm_poc.02_silver_clientes_validos` AS
SELECT
  b.*,
  CONCAT(UPPER(TRIM(b.tipo_doc)), '-', UPPER(TRIM(b.num_doc))) AS llave_natural,
  UPPER(REGEXP_REPLACE(NORMALIZE(TRIM(b.nombre_completo), NFD), r'\pM', '')) AS nombre_norm
FROM `mdm_poc.01_bronze_clientes_unificado` b
LEFT JOIN `mdm_poc.02_cuarentena_dq` q
  ON b.id_origen = q.id_origen AND b.sistema_origen = q.sistema_origen
WHERE q.id_origen IS NULL;

-- -----------------------------------------------------------------------------
-- CAPA 3A: GOLD — TABLA DE EQUIVALENCIAS (XREF) CON MATCH DETERMINÍSTICO
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `mdm_poc.03_gold_clientes_xref` AS
WITH agrupacion AS (
  SELECT
    *,
    DENSE_RANK() OVER (ORDER BY llave_natural) AS cluster_num,
    ROW_NUMBER() OVER (PARTITION BY llave_natural ORDER BY trust_score DESC, fecha_actualizacion DESC) AS rank_trust
  FROM `mdm_poc.02_silver_clientes_validos`
)
SELECT
  FORMAT('MDM-CLI-%06d', cluster_num) AS mdm_golden_id,
  sistema_origen,
  id_origen,
  llave_natural,
  trust_score,
  IF(rank_trust = 1, 'PRIMARIO', 'VINCULADO') AS rol_en_cluster,
  fecha_actualizacion
FROM agrupacion;

-- -----------------------------------------------------------------------------
-- CAPA 3B: GOLD — GOLDEN RECORD CON SUPERVIVENCIA Y ENMASCARAMIENTO PII
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `mdm_poc.03_gold_clientes_golden_record` AS
WITH base AS (
  SELECT
    x.mdm_golden_id,
    s.*
  FROM `mdm_poc.03_gold_clientes_xref` x
  JOIN `mdm_poc.02_silver_clientes_validos` s
    ON x.id_origen = s.id_origen AND x.sistema_origen = s.sistema_origen
)
SELECT
  mdm_golden_id,
  ARRAY_AGG(tipo_doc ORDER BY trust_score DESC, fecha_actualizacion DESC LIMIT 1)[OFFSET(0)] AS tipo_doc,
  CONCAT('****', RIGHT(ARRAY_AGG(num_doc ORDER BY trust_score DESC, fecha_actualizacion DESC LIMIT 1)[OFFSET(0)], 4)) AS num_doc_enmascarado,
  ARRAY_AGG(nombre_completo ORDER BY trust_score DESC, fecha_actualizacion DESC LIMIT 1)[OFFSET(0)] AS nombre_legal,
  ARRAY_AGG(fecha_nacimiento ORDER BY trust_score DESC, fecha_actualizacion DESC LIMIT 1)[OFFSET(0)] AS fecha_nacimiento,
  REGEXP_REPLACE(
    ARRAY_AGG(email IGNORE NULLS ORDER BY fecha_actualizacion DESC, trust_score DESC LIMIT 1)[OFFSET(0)],
    r'^(.{2})[^@]*(@.*)$',
    r'\1***\2'
  ) AS email_enmascarado,
  ARRAY_AGG(telefono IGNORE NULLS ORDER BY fecha_actualizacion DESC, trust_score DESC LIMIT 1)[OFFSET(0)] AS telefono,
  ARRAY_AGG(direccion IGNORE NULLS ORDER BY fecha_actualizacion DESC, trust_score DESC LIMIT 1)[OFFSET(0)] AS direccion,
  ARRAY_AGG(estado_cliente ORDER BY trust_score DESC, fecha_actualizacion DESC LIMIT 1)[OFFSET(0)] AS estado_cliente,
  ARRAY_AGG(segmento ORDER BY trust_score DESC, fecha_actualizacion DESC LIMIT 1)[OFFSET(0)] AS segmento,
  COUNT(*) AS registros_consolidados,
  MAX(fecha_actualizacion) AS ultima_actualizacion
FROM base
GROUP BY mdm_golden_id;

-- -----------------------------------------------------------------------------
-- CAPA 3C: SCORECARD DE CALIDAD PARA LOOKER STUDIO
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `mdm_poc.03_gold_dq_scorecard` AS
SELECT
  b.sistema_origen,
  COUNT(*) AS total_registros_bronze,
  COUNTIF(q.id_origen IS NULL) AS registros_aprobados,
  COUNTIF(q.id_origen IS NOT NULL) AS registros_cuarentena,
  ROUND(SAFE_DIVIDE(COUNTIF(q.id_origen IS NULL), COUNT(*)) * 100, 2) AS pct_calidad
FROM `mdm_poc.01_bronze_clientes_unificado` b
LEFT JOIN `mdm_poc.02_cuarentena_dq` q
  ON b.id_origen = q.id_origen AND b.sistema_origen = q.sistema_origen
GROUP BY b.sistema_origen;
