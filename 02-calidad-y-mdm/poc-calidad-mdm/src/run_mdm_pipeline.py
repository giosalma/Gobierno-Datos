"""
Pipeline de Calidad de Datos y Master Data Management (MDM) - PoC $0 USD
Autor: Said Giovanny Salazar Marín (DAMA-CDMP® | TOGAF®)
Estándares: DAMA-DMBOK2 (Calidad y MDM), Arquitectura Medallion (Bronze -> Silver -> Gold)

Ejecución:
    python src/run_mdm_pipeline.py
"""

import os
import re
import unicodedata
from datetime import datetime, date
from difflib import SequenceMatcher
import pandas as pd

# ==============================================================================
# CONFIGURACIÓN DE RUTAS Y REGLAS DE GOBIERNO (DGO)
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TRUST_SCORES = {
    "CORE_TRANSACCIONAL": 95,
    "CRM_COMERCIAL": 85,
    "SISTEMA_LEGADO": 50,
}

VALID_DOC_TYPES = {"CC", "NIT", "CE", "PAS"}
EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

# Umbrales de emparejamiento probabilístico
THRESHOLD_AUTO_MERGE = 0.92
THRESHOLD_GRAY_ZONE = 0.80


def normalize_text(value: str) -> str:
    """Elimina tildes, signos y espacios redundantes para comparación MDM."""
    if pd.isna(value):
        return ""
    text = str(value).strip().upper()
    text = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("utf-8")
    text = re.sub(r"[^A-Z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def mask_email(email: str) -> str:
    """Enmascaramiento PII Zero Trust para vistas analíticas."""
    if not email or "@" not in str(email):
        return "***"
    local, domain = str(email).split("@", 1)
    visible = local[:2] if len(local) >= 2 else local[:1]
    return f"{visible}***@{domain}"


def mask_doc(num_doc: str) -> str:
    """Enmascaramiento parcial de documento de identidad (PII)."""
    s = str(num_doc).strip()
    if len(s) <= 4:
        return "****"
    return "*" * (len(s) - 4) + s[-4:]


def similarity_score(a: str, b: str) -> float:
    """Calcula similitud difusa entre dos cadenas normalizadas."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


# ==============================================================================
# CAPA 1: BRONZE (INGESTA INMUTABLE)
# ==============================================================================
def load_bronze() -> pd.DataFrame:
    sources = [
        ("core_clientes.csv", "CORE_TRANSACCIONAL"),
        ("crm_clientes.csv", "CRM_COMERCIAL"),
        ("legado_clientes.csv", "SISTEMA_LEGADO"),
    ]
    frames = []
    ingest_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for filename, system_name in sources:
        df = pd.read_csv(os.path.join(DATA_DIR, filename), dtype=str).fillna("")
        df["sistema_origen"] = system_name
        df["trust_score"] = TRUST_SCORES[system_name]
        df["fecha_ingesta"] = ingest_ts
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


# ==============================================================================
# CAPA 2: QUALITY GATES (6 DIMENSIONES DAMA) Y CUARENTENA
# ==============================================================================
def apply_quality_gates(df_bronze: pd.DataFrame):
    valid_records = []
    quarantine_records = []
    today = date.today()

    for _, row in df_bronze.iterrows():
        errors = []
        dimensions = []

        # 1. Completitud (Bloqueante)
        if not str(row["tipo_doc"]).strip() or not str(row["num_doc"]).strip():
            errors.append("CDE_NULL: tipo_doc o num_doc vacío")
            dimensions.append("Completitud")
        if not str(row["nombre_completo"]).strip():
            errors.append("CDE_NULL: nombre_completo vacío")
            dimensions.append("Completitud")

        # 2. Validez (Bloqueante)
        if str(row["tipo_doc"]).strip().upper() not in VALID_DOC_TYPES:
            errors.append(f"INVALID_DOMAIN: tipo_doc '{row['tipo_doc']}' fuera de catálogo")
            dimensions.append("Validez")
        if row["email"] and not EMAIL_REGEX.match(str(row["email"]).strip()):
            errors.append(f"INVALID_FORMAT: email '{row['email']}' no cumple RFC")
            dimensions.append("Validez")
        if row["fecha_nacimiento"]:
            try:
                dob = datetime.strptime(str(row["fecha_nacimiento"]).strip(), "%Y-%m-%d").date()
                if dob > today or dob.year < 1900:
                    errors.append(f"INVALID_RANGE: fecha_nacimiento '{row['fecha_nacimiento']}' fuera de rango")
                    dimensions.append("Validez")
            except ValueError:
                errors.append(f"INVALID_DATE: fecha_nacimiento '{row['fecha_nacimiento']}' inválida")
                dimensions.append("Validez")

        # 3. Consistencia lógica (Crítica -> Cuarentena)
        if str(row["estado_cliente"]).strip().upper() == "FALLECIDO" and str(row["tiene_producto_activo"]).strip().upper() == "SI":
            errors.append("INCONSISTENCY: Cliente FALLECIDO con producto ACTIVO")
            dimensions.append("Consistencia")

        rec = row.to_dict()
        if errors:
            rec["dimension_fallida"] = " | ".join(sorted(set(dimensions)))
            rec["motivo_rechazo"] = " ; ".join(errors)
            rec["sla_remediacion"] = "MTTR < 24h (Data Steward)"
            quarantine_records.append(rec)
        else:
            rec["nombre_norm"] = normalize_text(rec["nombre_completo"])
            rec["llave_natural"] = f"{str(rec['tipo_doc']).strip().upper()}-{str(rec['num_doc']).strip().upper()}"
            valid_records.append(rec)

    return pd.DataFrame(valid_records), pd.DataFrame(quarantine_records)


# ==============================================================================
# CAPA 3: MOTOR MDM (MATCH & MERGE + ZONA GRIS + SUPERVIVENCIA)
# ==============================================================================
def run_mdm_engine(df_silver: pd.DataFrame):
    # Ordenar por mayor Trust Score y fecha más reciente para priorizar registros maestros
    df_sorted = df_silver.sort_values(
        by=["trust_score", "fecha_actualizacion"], ascending=[False, False]
    ).reset_index(drop=True)

    clusters = []  # Cada cluster es una lista de diccionarios (registros fuente)
    gray_zone = []

    for _, row in df_sorted.iterrows():
        rec = row.to_dict()
        matched_cluster = None
        match_method = None
        match_score = 0.0

        for cluster in clusters:
            anchor = cluster[0]
            # 1. Emparejamiento Determinístico (100%)
            if rec["llave_natural"] == anchor["llave_natural"]:
                matched_cluster = cluster
                match_method = "DETERMINISTICO_ID"
                match_score = 1.00
                break

            # 2. Emparejamiento Probabilístico (misma fecha de nacimiento + similitud de nombre)
            if rec["fecha_nacimiento"] and rec["fecha_nacimiento"] == anchor["fecha_nacimiento"]:
                name_sim = similarity_score(rec["nombre_norm"], anchor["nombre_norm"])
                phone_bonus = 0.05 if (rec["telefono"] and rec["telefono"] == anchor["telefono"]) else 0.0
                score = min(1.0, round(name_sim + phone_bonus, 4))

                if score >= THRESHOLD_AUTO_MERGE:
                    matched_cluster = cluster
                    match_method = "PROBABILISTICO_AUTO"
                    match_score = score
                    break
                elif score >= THRESHOLD_GRAY_ZONE:
                    gray_zone.append({
                        "id_origen_candidato": rec["id_origen"],
                        "sistema_candidato": rec["sistema_origen"],
                        "nombre_candidato": rec["nombre_completo"],
                        "doc_candidato": rec["llave_natural"],
                        "id_origen_maestro": anchor["id_origen"],
                        "sistema_maestro": anchor["sistema_origen"],
                        "nombre_maestro": anchor["nombre_completo"],
                        "doc_maestro": anchor["llave_natural"],
                        "score_similitud": round(score * 100, 2),
                        "accion_requerida": "Revisión manual por Data Steward (Confirmar Merge o Separar)",
                    })

        if matched_cluster is not None:
            rec["metodo_match"] = match_method
            rec["score_match"] = round(match_score * 100, 2)
            matched_cluster.append(rec)
        else:
            rec["metodo_match"] = "REGISTRO_BASE"
            rec["score_match"] = 100.0
            clusters.append([rec])

    # Construir Capa Gold (Golden Record + XREF) aplicando Reglas de Supervivencia
    golden_records = []
    xref_records = []

    for idx, cluster in enumerate(clusters, start=1):
        golden_id = f"MDM-CLI-{idx:06d}"

        # Prioridad por Trust Score para Identidad Legal, Estado y Segmento
        by_trust = sorted(cluster, key=lambda r: (r["trust_score"], r["fecha_actualizacion"]), reverse=True)
        # Prioridad por fecha más reciente (con preferencia CRM/Digital sobre Legado) para Contacto
        by_recency = sorted(
            cluster,
            key=lambda r: (r["fecha_actualizacion"], r["trust_score"]),
            reverse=True,
        )

        primary = by_trust[0]
        contact_winner = next((r for r in by_recency if r["email"]), primary)
        phone_winner = next((r for r in by_recency if r["telefono"]), primary)
        address_winner = next((r for r in by_recency if r["direccion"]), primary)

        golden_records.append({
            "mdm_golden_id": golden_id,
            "tipo_doc": primary["tipo_doc"],
            "num_doc_enmascarado": mask_doc(primary["num_doc"]),
            "nombre_legal": primary["nombre_completo"],
            "fecha_nacimiento": primary["fecha_nacimiento"],
            "email_enmascarado": mask_email(contact_winner["email"]),
            "fuente_email": contact_winner["sistema_origen"],
            "telefono": phone_winner["telefono"],
            "direccion": address_winner["direccion"],
            "estado_cliente": primary["estado_cliente"],
            "segmento": primary["segmento"],
            "fuente_autoritativa": primary["sistema_origen"],
            "registros_consolidados": len(cluster),
            "ultima_actualizacion": max(r["fecha_actualizacion"] for r in cluster),
        })

        for pos, r in enumerate(by_trust):
            xref_records.append({
                "mdm_golden_id": golden_id,
                "sistema_origen": r["sistema_origen"],
                "id_origen": r["id_origen"],
                "llave_natural": r["llave_natural"],
                "trust_score": r["trust_score"],
                "rol_en_cluster": "PRIMARIO" if pos == 0 else "VINCULADO",
                "metodo_match": r["metodo_match"],
                "score_match_pct": r["score_match"],
                "fecha_actualizacion": r["fecha_actualizacion"],
            })

    return pd.DataFrame(golden_records), pd.DataFrame(xref_records), pd.DataFrame(gray_zone)


# ==============================================================================
# CAPA 4: SCORECARD AUTOMÁTICO DE CALIDAD Y MDM
# ==============================================================================
def generate_scorecard(df_bronze, df_silver, df_quarantine, df_golden, df_xref, df_gray):
    total_bronze = len(df_bronze)
    total_valid = len(df_silver)
    total_quarantine = len(df_quarantine)
    total_golden = len(df_golden)
    duplicados_resueltos = total_valid - total_golden
    pct_calidad_global = round((total_valid / total_bronze) * 100, 2) if total_bronze else 0.0

    # Métricas por sistema origen
    rows_sys = []
    for sys_name in ["CORE_TRANSACCIONAL", "CRM_COMERCIAL", "SISTEMA_LEGADO"]:
        tot = len(df_bronze[df_bronze["sistema_origen"] == sys_name])
        rej = len(df_quarantine[df_quarantine["sistema_origen"] == sys_name]) if not df_quarantine.empty else 0
        ok = tot - rej
        pct = round((ok / tot) * 100, 2) if tot else 0.0
        rows_sys.append(f"| `{sys_name}` | {tot} | {ok} | {rej} | **{pct}%** |")

    md = f"""# Scorecard Automático de Calidad de Datos y MDM

**Fecha de ejecución:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**Pipeline:** `run_mdm_pipeline.py` (Arquitectura Medallion: Bronze -> Quality Gates -> Silver MDM -> Gold)

---

## 1. Resumen Ejecutivo de Ejecución

| Métrica Clave | Valor Obtenido | Observación |
| :--- | :---: | :--- |
| **Registros ingresados (Bronze)** | **{total_bronze}** | Core (10), CRM (8), Legado (6) |
| **Registros aprobados (Quality Gates)** | **{total_valid}** | Índice de Calidad Global: **{pct_calidad_global}%** |
| **Registros enviados a Cuarentena** | **{total_quarantine}** | Bloqueados antes de contaminar Silver/Gold |
| **Golden Records generados (Gold)** | **{total_golden}** | Vista Única de Cliente certificada |
| **Duplicados consolidados (Match & Merge)** | **{duplicados_resueltos}** | Fusiones determinísticas y probabilísticas |
| **Casos en Zona Gris (Stewardship)** | **{len(df_gray)}** | Pendientes de decisión humana (80% - 91%) |

---

## 2. Cumplimiento de Calidad por Sistema Origen

| Sistema Origen | Total Bronze | Aprobados | En Cuarentena | % Calidad |
| :--- | :---: | :---: | :---: | :---: |
{chr(10).join(rows_sys)}

---

## 3. Evidencia de Trazabilidad y Seguridad
* **PII protegido (*Zero Trust*):** Los campos `num_doc` y `email` fueron enmascarados en la capa analítica `gold_clientes_golden_record.csv`.
* **Linaje reversible:** Cada `mdm_golden_id` conserva sus llaves de origen en `gold_clientes_xref.csv`.
* **Remediación auditable:** Los registros fallidos detallan la dimensión DAMA incumplida en `cuarentena_rechazos.csv`.
"""
    with open(os.path.join(OUTPUT_DIR, "scorecard_calidad.md"), "w", encoding="utf-8") as f:
        f.write(md)


def main():
    df_bronze = load_bronze()
    df_silver, df_quarantine = apply_quality_gates(df_bronze)
    df_golden, df_xref, df_gray = run_mdm_engine(df_silver)

    df_golden.to_csv(os.path.join(OUTPUT_DIR, "gold_clientes_golden_record.csv"), index=False, encoding="utf-8")
    df_xref.to_csv(os.path.join(OUTPUT_DIR, "gold_clientes_xref.csv"), index=False, encoding="utf-8")
    df_quarantine.to_csv(os.path.join(OUTPUT_DIR, "cuarentena_rechazos.csv"), index=False, encoding="utf-8")
    df_gray.to_csv(os.path.join(OUTPUT_DIR, "zona_gris_stewardship.csv"), index=False, encoding="utf-8")

    generate_scorecard(df_bronze, df_silver, df_quarantine, df_golden, df_xref, df_gray)
    print(f"Pipeline ejecutado con éxito: {len(df_bronze)} Bronze -> {len(df_silver)} Silver -> {len(df_quarantine)} Cuarentena -> {len(df_golden)} Golden Records ({len(df_gray)} Zona Gris).")


if __name__ == "__main__":
    main()
