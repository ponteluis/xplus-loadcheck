from pathlib import Path
import hashlib
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


def reset_all():
    new_reset_id = st.session_state.get("reset_id", 0) + 1
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state["reset_id"] = new_reset_id
    st.rerun()


def empty_editable_table(n=18):
    return pd.DataFrame({
        "pozo_id": [""] * n,
        "longitud_real_m": [None] * n,
        "kg_pozo": [None] * n,
        "kg_acumulado_operador": [None] * n,
    })


def prepare_next_sheet():
    st.session_state["tabla_editable"] = empty_editable_table(18)
    st.session_state["obs_lectura"] = []
    st.session_state["modelo_usado"] = ""
    st.session_state["uso_tokens"] = {}
    st.session_state["archivo_actual"] = ""
    st.session_state["archivo_actual_id"] = ""
    st.session_state["nombre_hoja_actual"] = ""
    st.session_state["hoja_actual_guardada_id"] = ""
    st.session_state["editor_version"] = st.session_state.get("editor_version", 0) + 1
    st.session_state["upload_version"] = st.session_state.get("upload_version", 0) + 1
    st.rerun()


if "reset_id" not in st.session_state:
    st.session_state["reset_id"] = 0
if "upload_version" not in st.session_state:
    st.session_state["upload_version"] = 0
if "editor_version" not in st.session_state:
    st.session_state["editor_version"] = 0


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
st.caption("Verificación de planillas de carguío, acumulados por hoja y comparación contra Blastcenter.")
st.markdown(
    """
    <div class="brand-box">
        <div class="brand-main">Desarrollado por Luis Ponte</div>
        <div class="brand-sub">X+ Operational Excellence · Control preliminar de planillas de carguío</div>
    </div>
    """,
    unsafe_allow_html=True
)


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


def clean_editable_table(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return empty_editable_table(18)

    out = df.copy()

    for col in ["pozo_id", "longitud_real_m", "kg_pozo", "kg_acumulado_operador"]:
        if col not in out.columns:
            out[col] = "" if col == "pozo_id" else None

    out = out[["pozo_id", "longitud_real_m", "kg_pozo", "kg_acumulado_operador"]].copy()
    out["pozo_id"] = out["pozo_id"].fillna("").astype(str)

    for col in ["longitud_real_m", "kg_pozo", "kg_acumulado_operador"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    return out


def calculate_table_fields(df: pd.DataFrame) -> pd.DataFrame:
    out = clean_editable_table(df)

    acumulados = []
    running = 0.0

    for _, row in out.iterrows():
        kg = row.get("kg_pozo")
        pozo = str(row.get("pozo_id", "")).strip()
        has_any_data = bool(pozo) or pd.notna(row.get("longitud_real_m")) or pd.notna(kg) or pd.notna(row.get("kg_acumulado_operador"))

        if pd.notna(kg):
            running += float(kg)
            acumulados.append(running)
        elif has_any_data:
            acumulados.append(running if running != 0 else None)
        else:
            acumulados.append(None)

    out["kg_acumulado_calculado"] = acumulados

    diffs = []
    for _, row in out.iterrows():
        op = row.get("kg_acumulado_operador")
        calc = row.get("kg_acumulado_calculado")
        if pd.notna(op) and pd.notna(calc):
            diffs.append(float(op) - float(calc))
        else:
            diffs.append(None)

    out["diferencia_acumulado"] = diffs
    return out


def normalize_rows(rows):
    normalized = []
    for r in rows or []:
        normalized.append({
            "pozo_id": "" if r.get("pozo_id") is None else str(r.get("pozo_id")).strip(),
            "longitud_real_m": to_number(r.get("longitud_real_m")),
            "kg_pozo": to_number(r.get("kg_pozo")),
            "kg_acumulado_operador": to_number(
                r.get("kg_acumulado_operador", r.get("kg_acumulado"))
            ),
        })
    if not normalized:
        return empty_editable_table(18)
    return clean_editable_table(pd.DataFrame(normalized))


def extract_usage(response):
    usage = {"prompt_tokens": None, "output_tokens": None, "total_tokens": None}
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

La fotografía puede mostrar toda la hoja. Debes concentrarte SOLO en la tabla principal de carguío, ignorando fecha, firmas, operador, supervisor, densidad, recuadros laterales, referencia de carga y observaciones.

Extrae exclusivamente estas columnas por fila:
1. pozo_id: columna Pozo ID.
2. longitud_real_m: columna Longitud Real [m], si está escrita.
3. kg_pozo: columna Explosivo Cargado [kg]. Este es el dato principal.
4. kg_acumulado_operador: columna Explosivo Acumulado [kg] escrita por el operador.

Reglas críticas:
- Prioriza leer correctamente kg_pozo.
- No inventes valores.
- Si un número es ilegible, usa null.
- Si una fila está tachada/anulada, no la incluyas como fila válida y menciónala en observaciones_lectura.
- No confundas kg_pozo con kg_acumulado_operador.
- No calcules el acumulado. Solo copia el acumulado escrito por el operador si se ve.
- No extraigas fecha, camión, disparo, densidad ni números impresos como kg_pozo.
- Conserva el orden vertical de la tabla.

Devuelve exclusivamente JSON válido con este formato:

{
  "observaciones_lectura": ["texto breve"],
  "rows": [
    {
      "pozo_id": "string",
      "longitud_real_m": 0,
      "kg_pozo": 0,
      "kg_acumulado_operador": 0
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
    tabla_calculada = calculate_table_fields(df)
    total = float(pd.to_numeric(tabla_calculada["kg_pozo"], errors="coerce").fillna(0).sum())

    valid_acc_op = pd.to_numeric(tabla_calculada["kg_acumulado_operador"], errors="coerce").dropna()
    ultimo_acumulado_operador = float(valid_acc_op.iloc[-1]) if len(valid_acc_op) else None

    diferencia_final_operador = None
    if ultimo_acumulado_operador is not None:
        diferencia_final_operador = total - ultimo_acumulado_operador

    diffs = pd.to_numeric(tabla_calculada["diferencia_acumulado"], errors="coerce")
    filas_con_diferencia = int(diffs.fillna(0).abs().gt(0.0001).sum())

    pozos = tabla_calculada["pozo_id"].astype(str).str.strip()
    pozos = pozos[pozos.ne("")]
    duplicates = sorted(pozos[pozos.duplicated()].unique().tolist())

    return total, ultimo_acumulado_operador, diferencia_final_operador, filas_con_diferencia, duplicates, tabla_calculada


def make_sheet_id(file_key: str, display_name: str) -> str:
    raw = f"{file_key}|{display_name}|{datetime.now().isoformat()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def add_or_update_sheet(
    hoja_id: str,
    file_key: str,
    display_name: str,
    df: pd.DataFrame,
    total: float,
    last_acc_op,
    diff_final_op,
    filas_diff,
    obs,
    model_used,
    usage,
):
    sheets = st.session_state["hojas_resumen"]

    if not hoja_id:
        hoja_id = make_sheet_id(file_key, display_name)

    existing = None
    for i, h in enumerate(sheets):
        if h["hoja_id"] == hoja_id:
            existing = i
            break

    df_calc = calculate_table_fields(df)

    record = {
        "hoja_id": hoja_id,
        "nombre_hoja": display_name or file_key,
        "archivo_original": file_key,
        "fecha": st.session_state.get("fecha_control", ""),
        "camion": st.session_state.get("camion_control", ""),
        "explosivo": st.session_state.get("explosivo_control", ""),
        "disparo": st.session_state.get("disparo_control", ""),
        "total_kg_calculado": total,
        "ultimo_acumulado_operador": last_acc_op,
        "diferencia_final_operador": diff_final_op,
        "filas_con_diferencia": filas_diff,
        "modelo": model_used or "",
        "tokens": usage.get("total_tokens") if isinstance(usage, dict) else None,
        "observaciones": " | ".join(obs or []),
        "filas_json": df_calc.to_json(orient="records", force_ascii=False),
    }

    if existing is None:
        sheets.append(record)
    else:
        sheets[existing] = record

    st.session_state["hojas_resumen"] = sheets
    st.session_state["hoja_actual_guardada_id"] = hoja_id
    return hoja_id


def build_export_detail():
    filas = []
    for h in st.session_state["hojas_resumen"]:
        try:
            rows = json.loads(h.get("filas_json", "[]"))
            for r in rows:
                r["nombre_hoja"] = h["nombre_hoja"]
                r["archivo_original"] = h["archivo_original"]
                r["fecha"] = h["fecha"]
                r["camion"] = h["camion"]
                r["explosivo"] = h["explosivo"]
                r["disparo"] = h["disparo"]
                filas.append(r)
        except Exception:
            pass

    if not filas:
        return pd.DataFrame(columns=[
            "nombre_hoja", "archivo_original", "fecha", "camion", "explosivo", "disparo",
            "pozo_id", "longitud_real_m", "kg_pozo", "kg_acumulado_operador",
            "kg_acumulado_calculado", "diferencia_acumulado"
        ])

    detail = pd.DataFrame(filas)
    preferred = [
        "nombre_hoja", "archivo_original", "fecha", "camion", "explosivo", "disparo",
        "pozo_id", "longitud_real_m", "kg_pozo", "kg_acumulado_operador",
        "kg_acumulado_calculado", "diferencia_acumulado"
    ]
    cols = [c for c in preferred if c in detail.columns] + [c for c in detail.columns if c not in preferred]
    return detail[cols]


def build_excel_file(resumen_export: pd.DataFrame, detalle: pd.DataFrame, total_malla: float, total_blastcenter: float, diferencia: float | None) -> bytes:
    output = BytesIO()
    control = pd.DataFrame([{
        "suma_total_kg_todas_las_hojas": total_malla,
        "total_blastcenter_malla": total_blastcenter if total_blastcenter else None,
        "diferencia_kg": diferencia,
        "fecha_exportacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }])

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        control.to_excel(writer, index=False, sheet_name="Control_malla")
        resumen_export.to_excel(writer, index=False, sheet_name="Resumen_hojas")
        detalle.to_excel(writer, index=False, sheet_name="Detalle_pozos")

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
                ws.column_dimensions[column_letter].width = min(max(max_len + 2, 12), 45)

    return output.getvalue()


with st.sidebar:
    st.header("Datos de control")
    fecha = st.date_input("Fecha", value=date.today())
    camion = st.text_input("Camión")
    explosivo = st.selectbox("Tipo de explosivo", EXPLOSIVOS, index=1)
    disparo = st.text_input("Disparo")

    st.markdown("---")
    model = st.text_input("Modelo de lectura", value=get_secret("GEMINI_MODEL", DEFAULT_MODEL))

    st.markdown("---")
    st.subheader("Sesión")
    confirmar_limpieza = st.checkbox("Confirmar limpieza total")
    if st.button("Limpiar memoria / nuevo análisis", disabled=not confirmar_limpieza):
        reset_all()

    st.markdown("---")
    st.caption("Desarrollado por Luis Ponte · X+ Operational Excellence")

st.session_state["fecha_control"] = str(fecha)
st.session_state["camion_control"] = camion
st.session_state["explosivo_control"] = explosivo
st.session_state["disparo_control"] = disparo

if "tabla_editable" not in st.session_state:
    st.session_state["tabla_editable"] = empty_editable_table(18)
if "obs_lectura" not in st.session_state:
    st.session_state["obs_lectura"] = []
if "archivo_actual" not in st.session_state:
    st.session_state["archivo_actual"] = ""
if "archivo_actual_id" not in st.session_state:
    st.session_state["archivo_actual_id"] = ""
if "nombre_hoja_actual" not in st.session_state:
    st.session_state["nombre_hoja_actual"] = ""
if "hoja_actual_guardada_id" not in st.session_state:
    st.session_state["hoja_actual_guardada_id"] = ""
if "modelo_usado" not in st.session_state:
    st.session_state["modelo_usado"] = ""
if "uso_tokens" not in st.session_state:
    st.session_state["uso_tokens"] = {}
if "hojas_resumen" not in st.session_state:
    st.session_state["hojas_resumen"] = []
if "log_analisis" not in st.session_state:
    st.session_state["log_analisis"] = []
if "nombres_hojas" not in st.session_state:
    st.session_state["nombres_hojas"] = {}


reset_id = st.session_state["reset_id"]
upload_version = st.session_state["upload_version"]

uploaded_files = st.file_uploader(
    "Sube una o varias imágenes de planillas",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
    key=f"uploader_{reset_id}_{upload_version}"
)

activar_camara = st.checkbox("Activar cámara para tomar foto", value=False, key=f"activar_camara_{reset_id}_{upload_version}")
camera = None
if activar_camara:
    camera = st.camera_input("Tomar foto con cámara", key=f"camera_{reset_id}_{upload_version}")

if camera is not None:
    uploaded_files = [camera]

tab_planilla, tab_validacion, tab_resumen = st.tabs(["Planilla", "Tabla y validación", "Resumen de malla"])

with tab_planilla:
    if uploaded_files:
        names = [f.name for f in uploaded_files]
        selected_name = st.selectbox("Selecciona la planilla a analizar", names, key=f"select_file_{reset_id}_{upload_version}")
        selected_file = uploaded_files[names.index(selected_name)]

        image_bytes = selected_file.getvalue()
        file_hash = hashlib.sha1(image_bytes).hexdigest()[:10]
        file_key = f"{selected_name} [{file_hash}]"

        if selected_name not in st.session_state["nombres_hojas"]:
            st.session_state["nombres_hojas"][selected_name] = Path(selected_name).stem

        safe_name = re.sub(r"[^a-zA-Z0-9_]+", "_", file_key)
        nombre_hoja = st.text_input(
            "Nombre de hoja para el resumen",
            value=st.session_state["nombres_hojas"].get(selected_name, Path(selected_name).stem),
            help="Ejemplo: Hoja 1, Hoja camión 243, Planilla 01, etc.",
            key=f"nombre_hoja_{reset_id}_{upload_version}_{safe_name}"
        )
        st.session_state["nombres_hojas"][selected_name] = nombre_hoja

        mime_type = getattr(selected_file, "type", "image/jpeg") or "image/jpeg"

        left, right = st.columns([0.42, 0.58], gap="large")
        with left:
            st.subheader("Imagen")
            st.image(Image.open(selected_file), use_container_width=True)

        with right:
            st.subheader("Lectura inteligente")
            st.info("La lectura se enfocará en Pozo ID, Longitud real, Kg pozo y Acumulado operador.")

            if st.button("Analizar planilla seleccionada", type="primary"):
                with st.spinner("Analizando imagen..."):
                    try:
                        data, model_used, usage = extract_with_gemini(image_bytes, mime_type, model)
                        st.session_state["tabla_editable"] = normalize_rows(data.get("rows", []))
                        st.session_state["obs_lectura"] = data.get("observaciones_lectura", []) or []
                        st.session_state["modelo_usado"] = model_used
                        st.session_state["uso_tokens"] = usage or {}
                        st.session_state["archivo_actual"] = selected_name
                        st.session_state["archivo_actual_id"] = file_key
                        st.session_state["nombre_hoja_actual"] = nombre_hoja
                        st.session_state["hoja_actual_guardada_id"] = ""
                        st.session_state["editor_version"] = st.session_state.get("editor_version", 0) + 1
                        st.session_state["log_analisis"].append({
                            "fecha_hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "nombre_hoja": nombre_hoja,
                            "archivo_original": selected_name,
                            "archivo_id": file_key,
                            "modelo": model_used,
                            "tokens": usage.get("total_tokens") if isinstance(usage, dict) else None,
                        })
                        st.success("Lectura completada. Revisa la tabla antes de guardar la hoja.")
                    except Exception as e:
                        st.error(f"No se pudo analizar la imagen: {e}")

            if st.session_state["obs_lectura"]:
                st.warning("Observaciones de lectura:")
                for obs in st.session_state["obs_lectura"]:
                    st.write(f"- {obs}")

            st.markdown("---")
            if st.button("Cargar otra planilla sin borrar resumen"):
                prepare_next_sheet()
    else:
        st.info("Sube una o varias fotos de planillas para comenzar. Las hojas ya guardadas se mantienen en el resumen.")

with tab_validacion:
    st.subheader("Tabla editable de verificación")
    st.caption("Edita solo los datos base. La app calcula el acumulado y las diferencias automáticamente.")

    editor_key = f"main_editor_{reset_id}_{upload_version}_{st.session_state.get('editor_version', 0)}"
    edited = st.data_editor(
        clean_editable_table(st.session_state["tabla_editable"]),
        hide_index=True,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "pozo_id": st.column_config.TextColumn("Pozo ID"),
            "longitud_real_m": st.column_config.NumberColumn("Longitud real [m]", step=0.1),
            "kg_pozo": st.column_config.NumberColumn("Kg pozo", step=1),
            "kg_acumulado_operador": st.column_config.NumberColumn("Kg acumulado operador", step=1),
        },
        key=editor_key,
    )
    st.session_state["tabla_editable"] = clean_editable_table(edited)

    total, last_acc_op, diff_final_op, filas_diff, duplicates, tabla_calculada = validate_table(st.session_state["tabla_editable"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total kg calculado", f"{total:,.0f} kg")
    c2.metric("Último acumulado operador", f"{last_acc_op:,.0f} kg" if last_acc_op is not None else "—")
    c3.metric("Dif. final vs operador", f"{diff_final_op:,.0f} kg" if diff_final_op is not None else "—")
    c4.metric("Filas con diferencia", filas_diff)

    alerts = []
    if duplicates:
        alerts.append(f"Pozos repetidos: {', '.join(duplicates)}")
    if diff_final_op is not None and abs(diff_final_op) > 0.0001:
        alerts.append("El total calculado por kg/pozo no coincide con el último acumulado del operador.")
    if filas_diff:
        alerts.append(f"Hay {filas_diff} fila(s) donde el acumulado operador no coincide con el acumulado calculado.")

    if not alerts:
        st.markdown("<div class='ok-box'><b>✅ Hoja sin alertas internas.</b></div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='warn-box'><b>🟡 Revisión recomendada:</b></div>", unsafe_allow_html=True)
        for a in alerts:
            st.write(f"- {a}")

    with st.expander("Ver detalle automático de acumulados"):
        st.dataframe(
            tabla_calculada,
            use_container_width=True,
            hide_index=True,
            column_config={
                "pozo_id": st.column_config.TextColumn("Pozo ID"),
                "longitud_real_m": st.column_config.NumberColumn("Longitud real [m]"),
                "kg_pozo": st.column_config.NumberColumn("Kg pozo"),
                "kg_acumulado_operador": st.column_config.NumberColumn("Kg acumulado operador"),
                "kg_acumulado_calculado": st.column_config.NumberColumn("Kg acumulado calculado"),
                "diferencia_acumulado": st.column_config.NumberColumn("Diferencia acumulado"),
            }
        )

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("Guardar hoja en resumen", type="primary"):
            file_key = st.session_state.get("archivo_actual_id", "") or f"Hoja manual {len(st.session_state['hojas_resumen']) + 1}"
            display_name = st.session_state.get("nombre_hoja_actual", "") or f"Hoja {len(st.session_state['hojas_resumen']) + 1}"
            add_or_update_sheet(
                hoja_id=st.session_state.get("hoja_actual_guardada_id", ""),
                file_key=file_key,
                display_name=display_name,
                df=st.session_state["tabla_editable"],
                total=total,
                last_acc_op=last_acc_op,
                diff_final_op=diff_final_op,
                filas_diff=filas_diff,
                obs=st.session_state["obs_lectura"],
                model_used=st.session_state["modelo_usado"],
                usage=st.session_state["uso_tokens"],
            )
            st.success(f"Hoja guardada/actualizada: {display_name}")
    with col_b:
        if st.button("Guardar y preparar siguiente hoja"):
            file_key = st.session_state.get("archivo_actual_id", "") or f"Hoja manual {len(st.session_state['hojas_resumen']) + 1}"
            display_name = st.session_state.get("nombre_hoja_actual", "") or f"Hoja {len(st.session_state['hojas_resumen']) + 1}"
            add_or_update_sheet(
                hoja_id=st.session_state.get("hoja_actual_guardada_id", ""),
                file_key=file_key,
                display_name=display_name,
                df=st.session_state["tabla_editable"],
                total=total,
                last_acc_op=last_acc_op,
                diff_final_op=diff_final_op,
                filas_diff=filas_diff,
                obs=st.session_state["obs_lectura"],
                model_used=st.session_state["modelo_usado"],
                usage=st.session_state["uso_tokens"],
            )
            prepare_next_sheet()
    with col_c:
        if st.button("Limpiar tabla actual"):
            st.session_state["tabla_editable"] = empty_editable_table(18)
            st.session_state["obs_lectura"] = []
            st.session_state["modelo_usado"] = ""
            st.session_state["uso_tokens"] = {}
            st.session_state["hoja_actual_guardada_id"] = ""
            st.session_state["editor_version"] = st.session_state.get("editor_version", 0) + 1
            st.rerun()

with tab_resumen:
    st.subheader("Resumen de malla")
    st.caption("Suma total de hojas guardadas vs total Blastcenter de la malla.")

    total_blastcenter_malla = st.number_input(
        "Total Blastcenter de la malla",
        min_value=0.0,
        value=0.0,
        step=1.0,
        help="Ingresa el total de kg según Blastcenter para comparar contra la suma de todas las hojas guardadas.",
        key=f"total_blastcenter_malla_{reset_id}"
    )

    if st.session_state["hojas_resumen"]:
        resumen = pd.DataFrame(st.session_state["hojas_resumen"])

        total_malla = float(pd.to_numeric(resumen["total_kg_calculado"], errors="coerce").fillna(0).sum())
        diff_bc = total_malla - total_blastcenter_malla if total_blastcenter_malla > 0 else None

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Hojas guardadas", len(resumen))
        c2.metric("Suma total kg hojas", f"{total_malla:,.0f} kg")
        c3.metric("Total Blastcenter", f"{total_blastcenter_malla:,.0f} kg" if total_blastcenter_malla > 0 else "No usado")
        c4.metric("Diferencia", f"{diff_bc:,.0f} kg" if diff_bc is not None else "—")

        if total_blastcenter_malla > 0:
            if abs(diff_bc) < 0.0001:
                st.markdown("<div class='ok-box'><b>✅ La suma de hojas cuadra con Blastcenter.</b></div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='bad-box'><b>❌ La suma de hojas no cuadra con Blastcenter.</b></div>", unsafe_allow_html=True)

        resumen_simple = resumen[[
            "nombre_hoja",
            "camion",
            "explosivo",
            "disparo",
            "total_kg_calculado",
            "ultimo_acumulado_operador",
            "diferencia_final_operador",
            "filas_con_diferencia",
        ]].copy()

        resumen_simple = resumen_simple.rename(columns={
            "nombre_hoja": "Hoja",
            "camion": "Camión",
            "explosivo": "Explosivo",
            "disparo": "Disparo",
            "total_kg_calculado": "Total kg hoja",
            "ultimo_acumulado_operador": "Último acumulado operador",
            "diferencia_final_operador": "Dif. hoja",
            "filas_con_diferencia": "Alertas",
        })

        st.markdown("### Hojas guardadas")
        st.dataframe(resumen_simple, use_container_width=True, hide_index=True)

        hoja_map = {f"{h['nombre_hoja']}": h["hoja_id"] for h in st.session_state["hojas_resumen"]}
        hoja_eliminar_label = st.selectbox("Eliminar hoja del resumen", [""] + list(hoja_map.keys()))
        if hoja_eliminar_label and st.button("Eliminar hoja seleccionada"):
            hoja_id_to_delete = hoja_map[hoja_eliminar_label]
            st.session_state["hojas_resumen"] = [h for h in st.session_state["hojas_resumen"] if h["hoja_id"] != hoja_id_to_delete]
            st.success("Hoja eliminada.")
            st.rerun()

        detalle = build_export_detail()

        csv_resumen = resumen_simple.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
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

        excel_bytes = build_excel_file(resumen_simple, detalle, total_malla, total_blastcenter_malla, diff_bc)
        st.download_button(
            "Descargar Excel completo",
            data=excel_bytes,
            file_name="xplus_loadcheck_resultado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        with st.expander("Ver información técnica"):
            log = pd.DataFrame(st.session_state["log_analisis"]) if st.session_state["log_analisis"] else pd.DataFrame()
            if not log.empty:
                st.dataframe(log, use_container_width=True, hide_index=True)
            else:
                st.write("Sin registro técnico disponible.")
    else:
        st.info("Aún no hay hojas guardadas. Analiza una planilla y presiona “Guardar hoja en resumen”.")

    st.markdown("---")
    st.subheader("Limpiar análisis")
    st.caption("Borra planillas cargadas, tabla actual y resumen de malla.")
    confirmar_limpieza_resumen = st.checkbox("Confirmo que quiero limpiar todo", key=f"confirmar_limpieza_resumen_{reset_id}")
    if st.button("Limpiar memoria completa", disabled=not confirmar_limpieza_resumen):
        reset_all()

st.markdown("---")
st.caption("Desarrollado por Luis Ponte · X+ Operational Excellence")
