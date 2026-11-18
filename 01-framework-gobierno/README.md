# Marco Operativo y Política de Gobierno de Datos

**Estándares de referencia:** DAMA-DMBOK2 | TOGAF 10 | Seguridad Zero Trust  
**Alcance:** Corporativo, agnóstico a industria (Banca, Seguros, Retail, Tecnología, Sector Público)

---

## 1. Tesis de Implementación y Enfoque Pragmático

La mayoría de los programas de Gobierno de Datos fracasan por dos extremos: se diseñan como burocracia documental desconectada de la operación, o se reducen a la compra de una herramienta de catálogo que nadie alimenta.

Este marco operacionaliza el gobierno como un habilitador de negocio. Su propósito es reducir el costo de la mala calidad de los datos (reprocesos operativos, sanciones regulatorias y modelos analíticos sesgados) sin frenar el *time-to-market* de las iniciativas de BI e Inteligencia Artificial.

**Decisión de diseño sobre el modelo operativo:**
* **Organizaciones con madurez inicial (Niveles 1 y 2):** Aplicar un modelo **centralizado** para establecer estándares mínimos, glosario de negocio y control de accesos. Intentar un *Data Mesh* federado sin cultura de propiedad previa multiplica los silos en lugar de resolverlos.
* **Organizaciones con madurez intermedia o alta (Nivel 3+):** Evolucionar hacia un modelo **híbrido federado**, manteniendo políticas y arquitectura centralizadas mientras los dominios de negocio ejecutan la curaduría y calidad de forma autónoma.

---

## 2. Estructura de Gobierno y Toma de Decisiones

El gobierno requiere autoridad real para arbitrar conflictos entre áreas (por ejemplo, cuando Comercial y Finanzas definen distinto el concepto de "Cliente Activo"). La estructura se divide en tres niveles:

1. **Comité Ejecutivo de Datos (Nivel Estratégico):** Integrado por C-Level y Directores de Dominio. Aprueba la inversión (ROI/TCO), prioriza los dominios críticos a gobernar y resuelve disputas de propiedad que escalan desde la operación. Sesiona trimestralmente.
2. **Oficina de Gobierno de Datos / DGO (Nivel Táctico):** Liderada por la Dirección de Gobierno de Datos junto a Arquitectura de Información y Seguridad. Define políticas, administra la plataforma de metadatos, audita el cumplimiento y capacita a la organización.
3. **Consejos de Dominio (Nivel Operativo):** Células permanentes por dominio crítico (Clientes, Productos, Finanzas, Riesgos, Operaciones) compuestas por *Data Owners*, *Data Stewards* y *Data Custodians*. Ejecutan reglas de calidad, certifican datos maestros (MDM) y gestionan incidentes en la fuente.

---

## 3. Matriz RACI de Responsabilidades

**Convenciones:** **R** = Responsable de ejecutar | **A** = Aprobador final (único por actividad) | **C** = Consultado | **I** = Informado

| Actividad Crítica de Gobierno | Comité Ejecutivo | Director Gobierno (CDO) | Data Owner (Negocio) | Data Steward (Táctico) | Data Custodian (TI / Ing.) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Aprobar la Política Corporativa de Datos y presupuesto | **A** | **R** | C | I | I |
| Definir Elementos Críticos de Datos (CDE) por dominio | I | C | **A** | **R** | C |
| Aprobar definiciones del Glosario de Negocio y reglas MDM | I | C | **A** | **R** | I |
| Implementar reglas automáticas de calidad en pipelines | I | I | I | C | **R / A** |
| Clasificar sensibilidad de datos (PII, Confidencial) | I | C | **A** | **R** | C |
| Aprobar solicitudes de acceso a datos restringidos | I | I | **A** | C | **R** |
| Garantizar linaje técnico y trazabilidad en Data Fabric | I | C | I | C | **R / A** |
| Certificar conjuntos de datos para modelos de Analítica e IA | I | **A** | C | **R** | C |
| Gestionar remediación en la fuente ante fallos de calidad | I | I | **A** | **R** | **R** |

> **Regla operativa:** Ningún rol de TI (*Data Custodian*) puede ser *Data Owner*. TI custodia la infraestructura, la disponibilidad y los controles de seguridad, pero el negocio es el único dueño de la semántica, las reglas de validación y la autorización de acceso.

---

## 4. Política Corporativa Base (Lineamientos Obligatorios)

### 4.1 Clasificación y Seguridad desde el Diseño
Todo activo de datos catalogado debe clasificarse en uno de cuatro niveles antes de pasar a producción:
* **Pública:** Información aprobada para divulgación externa sin restricciones.
* **Interna:** Datos operativos cuyo acceso está limitado a colaboradores autorizados.
* **Confidencial:** Información financiera, comercial o estratégica cuya exposición impacta la competitividad.
* **Restringida / PII:** Datos personales sensibles, financieros regulados o credenciales. Exigen cifrado en tránsito y en reposo, acceso bajo principio de mínimo privilegio (*Zero Trust*) y enmascaramiento obligatorio en ambientes de desarrollo y pruebas.

### 4.2 Gobierno de Integración y Control de Deuda Técnica
* Se prohíben las extracciones punto a punto no documentadas desde sistemas *Core* hacia bases locales o reportes ejecutivos. Toda ingesta productiva debe transitar por la capa de integración estandarizada (*Data Fabric* / bus de servicios) con registro de linaje.
* Ningún modelo de Inteligencia Artificial o reporte regulatorio podrá desplegarse en producción utilizando fuentes sin *Data Owner* asignado y sin controles automatizados de calidad vigentes.

### 4.3 Gestión del Ciclo de Vida y Retención
Cada dominio define los periodos de retención, archivado y purga segura conforme a la regulación local aplicable (protección de datos personales, normativa financiera o fiscal), optimizando simultáneamente los costos de almacenamiento en nube (FinOps).

---

## 5. Tablero de KPIs (Medición de Impacto y Cumplimiento)

El gobierno se sostiene con métricas verificables, no con percepción. Estos indicadores se reportan mensualmente al Comité Ejecutivo:

| Indicador (KPI) | Fórmula / Criterio de Medición | Meta Base (Año 1) | Impacto de Negocio |
| :--- | :--- | :---: | :--- |
| **Índice de Calidad en CDE** | `% de registros sin error en Completitud, Exactitud y Consistencia sobre Elementos Críticos` | Mayor o igual a 98% | Confiabilidad en reportes directivos y regulatorios |
| **Cobertura de Linaje End-to-End** | `(CDE con linaje documentado desde origen hasta consumo / Total CDE) x 100` | Mayor o igual a 85% | Reducción drástica de tiempos de auditoría y análisis de impacto |
| **MTTR de Incidentes de Datos** | `Tiempo promedio desde detección de anomalía hasta remediación en fuente` | Menor a 24 horas | Menor interrupción operativa y eliminación de reprocesos manuales |
| **Adopción de Activos Certificados** | `% de tableros ejecutivos y modelos de IA que consumen datos del repositorio gobernado` | Mayor o igual a 80% | Eliminación de "múltiples versiones de la verdad" |
| **Cumplimiento de Privacidad y Accesos** | `% de accesos a datos PII revisados y recertificados trimestralmente` | 100% | Mitigación de multas regulatorias y riesgo reputacional |

---

## 6. Notas de Campo: Decisiones Clave de Implementación (ADRs)

* **Arrancar por valor, no por cobertura total:** Gobernar toda la compañía desde el día uno paraliza el programa. Se seleccionan máximo dos dominios con dolor financiero o regulatorio evidente (habitualmente Cliente y Producto/Finanzas) para entregar resultados medibles en los primeros 90 días.
* **Procesos antes que licencias:** Adquirir plataformas costosas de catálogo o MDM antes de formalizar *Data Owners* y reglas de negocio genera *shelfware* (software subutilizado) y destruye la credibilidad del área ante la junta directiva.
* **Calidad automatizada en origen:** Las limpiezas manuales en hojas de cálculo antes de entregar un reporte son insostenibles. Las reglas de validación deben codificarse dentro de los pipelines de ingesta para rechazar o cuarentenar registros corruptos automáticamente.

---

[Volver al Portafolio Principal](../README.md)