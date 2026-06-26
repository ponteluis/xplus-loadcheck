from pathlib import Path
import json
import re
from datetime import date, datetime
from io import BytesIO

import pandas as pd
import streamlit as st
from PIL import Image


st.set_page_config(
    page_title="X+ LoadCheck",
    page_icon="⛏️",
    layout="wide"
)

APP_TITLE = "X+ LoadCheck"
EXPLOSIVOS = ["RIOFLEX 5000", "RIOFLEX 7000", "RIOFLEX 8000", "RIOFLEX", "ANFO", "OTRO"]
DEFAULT_MODEL = "gemini-2.5-flash"
FALLBACK_MODEL = "gemini-2.5-flash-lite"


st.markdown(
    """
    <style>
    .brand-box {
        padding: 14px 16px;
        border-radius: 14px;
        background: rgba(255, 77, 77, 0.10);
        border: 1px solid rgba(255, 77, 77, 0.35);
        margin-bottom: 18px;
    }
    .brand-main { font-weight: 800; font-size: 18px; }
    .brand-sub { color: #9ca3af; font-size: 14px; }
    .ok-box {
        padding: 12px 14px; border-radius: 10px;
        background: rgba(31, 185, 129, 0.12);
        border: 1px solid rgba(31, 185, 129, 0.35);
    }
    .warn-box {
        padding: 12px 14px; border-radius: 10px;
        background: rgba(255, 193, 7, 0.12);
        border: 1px solid rgba(255, 193, 7, 0.35);
    }
    .bad-box {
        padding: 12px 14px; border-radius: 10px;
        background: rgba(255, 77, 77, 0.12);
        border: 1px solid rgba(255, 77, 77, 0.35);
    }
    </style>
    """,
    unsafe_allow_html=True
)


def get_secret(name: str, default: str = "") -> str:
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


logo_path = Path("maxam_logo.png")
if logo_path.exists():
    st.image(str(logo_path), width=190)

st.title(APP_TITLE)
st.caption("Asistente de verificación de planillas de carguío, edición por supervisor y validación de suma.")
st.markdown(
    """
    <div class="brand-box">
        <div class="brand-main">Desarrollado por Luis Ponte</div>
        <div class="brand-sub">X+ Operational Excellence · Verificación preliminar de planillas de carguío</div>
    </div>
    """,
    unsafe_allow_html=True
)


def empty_table(n=18):
    return pd.DataFrame({
        "pozo_id": [""] * n,
        "longitud_real_m": [None] * n,
        "kg_pozo": [None] * n,
        "kg_acumulado": [None] * n,
    })


def to_number(value):
    try:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return float(str(value).replace(",", "."))
    except Exception:
        return None


def clean_json_text(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text.strip(), flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text.strip()).strip()
    return text


def normalize_rows(rows):
    normalized = []
    for r in rows or []:
        normalized.append({
            "pozo_id": "" if r.get("pozo_id") is None else str(r.get("pozo_id")).strip(),
            "longitud_real_m": to_number(r.get("longitud_real_m")),
            "kg_pozo": to_number(r.get("kg_pozo")),
            "kg_acumulado": to_number(r.get("kg_acumulado")),
        })
    if not normalized:
        return empty_table(18)
    return pd.DataFrame(normalized)


def extract_usage(response):
    usage = {
        "prompt_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
    }
    try:
        meta = response.usage_metadata
        usage["prompt_tokens"] = getattr(meta, "prompt_token_count", None)
        usage["output_tokens"] = getattr(meta, "candidates_token_count", None)
        usage["total_tokens"] = getattr(meta, "total_token_count", None)
    except Exception:
        pass
    return usage


def gemini_models_to_try(selected_model: str):
    models = []
    for m in [selected_model, DEFAULT_MODEL, FALLBACK_MODEL]:
        if m and m not in models:
            models.append(m)
    return models


def extract_with_gemini(image_bytes: bytes, mime_type: str, selected_model: str):
    api_key = get_secret("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("Falta configurar GEMINI_API_KEY en los secretos de Streamlit.")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    prompt = """
Actúa como analista QA/QC de tronadura y lector avanzado de planillas manuales de CONTROL DE CARGA.

La fotografía puede mostrar toda la hoja. Debes concentrarte SOLO en la tabla principal de carguío, ignorando:
- fecha;
- firmas;
- operador/supervisor;
- densidad;
- recuadros laterales;
- referencias de carga;
- observaciones;
- textos impresos que no sean datos de la tabla.

Extrae exclusivamente estas columnas operacionales por fila:
1. pozo_id: columna Pozo ID.
2. longitud_real_m: columna Longitud Real [m], si está escrita.
3. kg_pozo: columna Explosivo Cargado [kg].
4. kg_acumulado: columna Explosivo Acumulado [kg].

Reglas críticas de lectura:
- No inventes valores.
- Si un número es ilegible, usa null.
- Si una fila está tachada/anulada, no la incluyas como fila válida; menciónala en observaciones_lectura.
- No confundas kg_pozo con kg_acumulado.
- No extraigas fecha, camión, disparo, densidad o números impresos como kg_pozo.
- Si kg_acumulado está disponible, úsalo solo como kg_acumulado, no como kg_pozo.
- Conserva el orden vertical de la tabla.
- Si un valor parece dudoso, usa null y explica la duda.

Devuelve exclusivamente JSON válido con este formato:

{
  "observaciones_lectura": ["texto breve"],
  "rows": [
    {
      "pozo_id": "string",
      "longitud_real_m": 0,
      "kg_pozo": 0,
      "kg_acumulado": 0
    }
  ]
}
"""

    errors = []
    for model in gemini_models_to_try(selected_model):
        try:
            response = client.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                ),
            )
            data = json.loads(clean_json_text(response.text))
            usage = extract_usage(response)
            return data, model, usage
        except Exception as e:
            errors.append(f"{model}: {e}")

    raise RuntimeError("No se pudo completar la lectura con los modelos disponibles. " + " | ".join(errors[-2:]))


def validate_table(df: pd.DataFrame):
    tmp = df.copy()
    for col in ["longitud_real_m", "kg_pozo", "kg_acumulado"]:
        tmp[col] = pd.to_numeric(tmp[col], errors="coerce")

    total = float(tmp["kg_pozo"].fillna(0).sum())
    last_acc = None
    valid_acc = tmp["kg_acumulado"].dropna()
    if len(valid_acc):
        last_acc = float(valid_acc.iloc[-1])

    diff_acc = None if last_acc is None else total - last_acc

    pozos = tmp["pozo_id"].astype(str).str.strip()
    pozos = pozos[pozos.ne("")]
    duplicates = sorted(pozos[pozos.duplicated()].unique().tolist())

    return total, last_acc, diff_acc, duplicates


def add_or_update_sheet(file_name: str, df: pd.DataFrame, total: float, last_acc, diff_acc, obs, model_used, usage):
    sheets = st.session_state["hojas_resumen"]
    existing = None
    for i, h in enumerate(sheets):
        if h["archivo"] == file_name:
            existing = i
            break

    record = {
        "archivo": file_name,
        "fecha": st.session_state.get("fecha_control", ""),
        "camion": st.session_state.get("camion_control", ""),
        "explosivo": st.session_state.get("explosivo_control", ""),
        "disparo": st.session_state.get("disparo_control", ""),
        "total_kg": total,
        "ultimo_acumulado": last_acc,
        "diferencia_acumulado": diff_acc,
        "modelo": model_used or "",
        "tokens": usage.get("total_tokens") if isinstance(usage, dict) else None,
        "observaciones": " | ".join(obs or []),
        "filas_json": df.to_json(orient="records", force_ascii=False),
    }

    if existing is None:
        sheets.append(record)
    else:
        sheets[existing] = record

    st.session_state["hojas_resumen"] = sheets


def build_export_detail():
    filas = []
    for h in st.session_state["hojas_resumen"]:
        try:
            rows = json.loads(h.get("filas_json", "[]"))
            for r in rows:
                r["archivo"] = h["archivo"]
                r["fecha"] = h["fecha"]
                r["camion"] = h["camion"]
                r["explosivo"] = h["explosivo"]
                r["disparo"] = h["disparo"]
                filas.append(r)
        except Exception:
            pass

    if not filas:
        return pd.DataFrame(columns=[
            "archivo", "fecha", "camion", "explosivo", "disparo",
            "pozo_id", "longitud_real_m", "kg_pozo", "kg_acumulado"
        ])

    detail = pd.DataFrame(filas)
    preferred = [
        "archivo", "fecha", "camion", "explosivo", "disparo",
        "pozo_id", "longitud_real_m", "kg_pozo", "kg_acumulado"
    ]
    cols = [c for c in preferred if c in detail.columns] + [c for c in detail.columns if c not in preferred]
    return detail[cols]


def build_excel_file(resumen: pd.DataFrame, detalle: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        resumen.to_excel(writer, index=False, sheet_name="Resumen_malla")
        detalle.to_excel(writer, index=False, sheet_name="Detalle_pozos")

        # Ajuste visual simple de anchos
        for sheet_name in writer.sheets:
            ws = writer.sheets[sheet_name]
            for column_cells in ws.columns:
                max_len = 0
                column_letter = column_cells[0].column_letter
                for cell in column_cells:
                    try:
                        max_len = max(max_len, len(str(cell.value)))
                    except Exception:
                        pass
                ws.column_dimensions[column_letter].width = min(max(max_len + 2, 12), 40)

    return output.getvalue()


with st.sidebar:
    st.header("Datos de control")
    fecha = st.date_input("Fecha", value=date.today())
    camion = st.text_input("Camión")
    explosivo = st.selectbox("Tipo de explosivo", EXPLOSIVOS, index=1)
    disparo = st.text_input("Disparo")
    total_blastcenter = st.number_input("Total Blastcenter de la malla", min_value=0.0, value=0.0, step=1.0)
    usar_total_blastcenter = st.checkbox("Comparar con Blastcenter", value=False)
    st.markdown("---")
    model = st.text_input("Modelo de lectura", value=get_secret("GEMINI_MODEL", DEFAULT_MODEL))
    st.caption("Desarrollado por Luis Ponte · X+ Operational Excellence")

st.session_state["fecha_control"] = str(fecha)
st.session_state["camion_control"] = camion
st.session_state["explosivo_control"] = explosivo
st.session_state["disparo_control"] = disparo

if "tabla" not in st.session_state:
    st.session_state["tabla"] = empty_table(18)

if "obs_lectura" not in st.session_state:
    st.session_state["obs_lectura"] = []

if "archivo_actual" not in st.session_state:
    st.session_state["archivo_actual"] = ""

if "modelo_usado" not in st.session_state:
    st.session_state["modelo_usado"] = ""

if "uso_tokens" not in st.session_state:
    st.session_state["uso_tokens"] = {}

if "hojas_resumen" not in st.session_state:
    st.session_state["hojas_resumen"] = []

if "log_analisis" not in st.session_state:
    st.session_state["log_analisis"] = []


uploaded_files = st.file_uploader(
    "Sube una o varias imágenes de planillas",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True
)

activar_camara = st.checkbox("Activar cámara para tomar foto", value=False)
camera = None
if activar_camara:
    camera = st.camera_input("Tomar foto con cámara")

if camera is not None:
    uploaded_files = [camera]

tab_planilla, tab_validacion, tab_resumen = st.tabs(["Planilla", "Tabla y validación", "Resumen de malla"])

with tab_planilla:
    if uploaded_files:
        names = [f.name for f in uploaded_files]
        selected_name = st.selectbox("Selecciona la planilla a analizar", names)
        selected_file = uploaded_files[names.index(selected_name)]
        st.session_state["archivo_actual"] = selected_name

        image_bytes = selected_file.getvalue()
        mime_type = getattr(selected_file, "type", "image/jpeg") or "image/jpeg"

        left, right = st.columns([0.42, 0.58], gap="large")
        with left:
            st.subheader("Imagen")
            st.image(Image.open(selected_file), use_container_width=True)

        with right:
            st.subheader("Lectura inteligente")
            st.info("Analiza la planilla completa. La lectura se enfocará en la tabla principal de carguío.")

            if st.button("Analizar planilla seleccionada", type="primary"):
                with st.spinner("Analizando imagen..."):
                    try:
                        data, model_used, usage = extract_with_gemini(image_bytes, mime_type, model)
                        st.session_state["tabla"] = normalize_rows(data.get("rows", []))
                        st.session_state["obs_lectura"] = data.get("observaciones_lectura", []) or []
                        st.session_state["modelo_usado"] = model_used
                        st.session_state["uso_tokens"] = usage or {}
                        st.session_state["log_analisis"].append({
                            "fecha_hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "archivo": selected_name,
                            "modelo": model_used,
                            "tokens": usage.get("total_tokens") if isinstance(usage, dict) else None,
                        })
                        st.success("Lectura completada. Revisa la tabla antes de guardar la hoja.")
                    except Exception as e:
                        st.error(f"No se pudo analizar la imagen: {e}")

            if st.session_state["modelo_usado"]:
                c1, c2 = st.columns(2)
                c1.metric("Modelo usado", st.session_state["modelo_usado"])
                tokens = st.session_state["uso_tokens"].get("total_tokens") if isinstance(st.session_state["uso_tokens"], dict) else None
                c2.metric("Tokens estimados", tokens if tokens is not None else "—")

            if st.session_state["obs_lectura"]:
                st.warning("Observaciones de lectura:")
                for obs in st.session_state["obs_lectura"]:
                    st.write(f"- {obs}")
    else:
        st.info("Sube una o varias fotos de planillas para comenzar.")

with tab_validacion:
    st.subheader("Tabla editable de verificación")
    st.caption("Campos operacionales clave: Pozo ID, longitud real, kg por pozo y kg acumulado.")

    edited = st.data_editor(
        st.session_state["tabla"],
        hide_index=True,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "pozo_id": st.column_config.TextColumn("Pozo ID"),
            "longitud_real_m": st.column_config.NumberColumn("Longitud real [m]", step=0.1),
            "kg_pozo": st.column_config.NumberColumn("Kg pozo", step=1),
            "kg_acumulado": st.column_config.NumberColumn("Kg acumulado", step=1),
        },
        key="main_editor_v4_1",
    )
    st.session_state["tabla"] = edited

    total, last_acc, diff_acc, duplicates = validate_table(edited)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total kg hoja", f"{total:,.0f} kg")
    c2.metric("Último acumulado", f"{last_acc:,.0f} kg" if last_acc is not None else "—")
    c3.metric("Dif. vs acumulado", f"{diff_acc:,.0f} kg" if diff_acc is not None else "—")

    alerts = []
    if duplicates:
        alerts.append(f"Pozos repetidos: {', '.join(duplicates)}")
    if diff_acc is not None and abs(diff_acc) > 0.0001:
        alerts.append("El total de kg/pozo no coincide con el último acumulado.")

    if not alerts:
        st.markdown("<div class='ok-box'><b>✅ Hoja sin alertas internas.</b></div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='warn-box'><b>🟡 Revisión recomendada:</b></div>", unsafe_allow_html=True)
        for a in alerts:
            st.write(f"- {a}")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Guardar/actualizar hoja en resumen", type="primary"):
            file_name = st.session_state.get("archivo_actual", "") or f"Hoja {len(st.session_state['hojas_resumen']) + 1}"
            add_or_update_sheet(
                file_name=file_name,
                df=edited,
                total=total,
                last_acc=last_acc,
                diff_acc=diff_acc,
                obs=st.session_state["obs_lectura"],
                model_used=st.session_state["modelo_usado"],
                usage=st.session_state["uso_tokens"],
            )
            st.success("Hoja guardada en el resumen de malla.")
    with col_b:
        if st.button("Limpiar tabla actual"):
            st.session_state["tabla"] = empty_table(18)
            st.session_state["obs_lectura"] = []
            st.session_state["modelo_usado"] = ""
            st.session_state["uso_tokens"] = {}
            st.rerun()

with tab_resumen:
    st.subheader("Resumen de malla")
    st.caption("Suma los totales de cada hoja de carguío y compara contra el total de Blastcenter de la malla.")

    if st.session_state["hojas_resumen"]:
        resumen = pd.DataFrame(st.session_state["hojas_resumen"])
        visible_cols = [
            "archivo", "fecha", "camion", "explosivo", "disparo",
            "total_kg", "ultimo_acumulado", "diferencia_acumulado",
            "modelo", "tokens", "observaciones"
        ]
        resumen_visible = resumen[visible_cols].copy()
        st.dataframe(resumen_visible, use_container_width=True, hide_index=True)

        total_malla = float(resumen["total_kg"].fillna(0).sum())
        diff_bc = total_malla - total_blastcenter if usar_total_blastcenter else None

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Hojas registradas", len(resumen))
        c2.metric("Total kg hojas", f"{total_malla:,.0f} kg")
        c3.metric("Total Blastcenter", f"{total_blastcenter:,.0f} kg" if usar_total_blastcenter else "No usado")
        c4.metric("Diferencia", f"{diff_bc:,.0f} kg" if diff_bc is not None else "—")

        if usar_total_blastcenter:
            if abs(diff_bc) < 0.0001:
                st.markdown("<div class='ok-box'><b>✅ La suma de hojas cuadra con Blastcenter.</b></div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='bad-box'><b>❌ La suma de hojas no cuadra con Blastcenter.</b></div>", unsafe_allow_html=True)

        hoja_eliminar = st.selectbox("Eliminar hoja del resumen", [""] + resumen["archivo"].tolist())
        if hoja_eliminar and st.button("Eliminar hoja seleccionada"):
            st.session_state["hojas_resumen"] = [h for h in st.session_state["hojas_resumen"] if h["archivo"] != hoja_eliminar]
            st.success("Hoja eliminada.")
            st.rerun()

        detalle = build_export_detail()

        # CSV compatible con Excel regional: separador ; y decimal ,
        csv_resumen = resumen_visible.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
        st.download_button(
            "Descargar resumen CSV",
            data=csv_resumen,
            file_name="xplus_resumen_malla.csv",
            mime="text/csv"
        )

        csv_detalle = detalle.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
        st.download_button(
            "Descargar detalle CSV",
            data=csv_detalle,
            file_name="xplus_detalle_pozos.csv",
            mime="text/csv"
        )

        excel_bytes = build_excel_file(resumen_visible, detalle)
        st.download_button(
            "Descargar Excel completo",
            data=excel_bytes,
            file_name="xplus_loadcheck_resultado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("Aún no hay hojas guardadas. Analiza una planilla y presiona “Guardar/actualizar hoja en resumen”.")

    if st.session_state["log_analisis"]:
        st.markdown("---")
        st.subheader("Registro de análisis de esta sesión")
        log = pd.DataFrame(st.session_state["log_analisis"])
        st.dataframe(log, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("Desarrollado por Luis Ponte · X+ Operational Excellence")
