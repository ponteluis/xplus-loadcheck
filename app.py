from pathlib import Path
import json
import re
from datetime import date

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


def require_password():
    expected = get_secret("APP_PASSWORD", "")
    if not expected:
        return True

    st.title("X+ LoadCheck")
    pwd = st.text_input("Clave de acceso", type="password")
    if pwd == expected:
        return True
    if pwd:
        st.error("Clave incorrecta.")
    st.stop()


require_password()

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


def extract_with_gemini(image_bytes: bytes, mime_type: str, model: str):
    api_key = get_secret("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("Falta configurar GEMINI_API_KEY en los Secrets de Streamlit.")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    prompt = """
Actúa como analista de QA/QC de tronadura y lector avanzado de planillas manuales de control de carga.

Debes leer la fotografía de una planilla de carguío manual. Extrae SOLO la tabla de pozos y devuelve JSON válido.

Campos por fila:
- pozo_id: identificador del pozo.
- longitud_real_m: valor de la columna Longitud Real [m], si se ve.
- kg_pozo: valor de la columna Explosivo Cargado [kg], NO uses valores de acumulado.
- kg_acumulado: valor de la columna Explosivo Acumulado [kg], si se ve.

También intenta detectar:
- camion_detectado
- explosivo_detectado
- observaciones_lectura: lista breve de dudas, tachados o filas ilegibles.

Reglas críticas:
- No inventes números.
- Si una fila está tachada/anulada, no la incluyas como fila válida; menciónala en observaciones_lectura.
- Si un número es dudoso, usa null y explica la duda en observaciones_lectura.
- No confundas kg_pozo con kg_acumulado.
- No extraigas fechas, número de formulario, densidad, números impresos o referencias como si fueran kg_pozo.
- Si hay acumulado, úsalo solo en kg_acumulado.
- Devuelve exclusivamente este JSON:

{
  "camion_detectado": null,
  "explosivo_detectado": null,
  "observaciones_lectura": [],
  "rows": [
    {"pozo_id": "string", "longitud_real_m": 0, "kg_pozo": 0, "kg_acumulado": 0}
  ]
}
"""

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
    return data


def quick_input_to_df(text: str):
    # Accepts: pozo longitud kg acumulado OR pozo kg OR pozo longitud kg
    lines = [x.strip() for x in (text or "").splitlines() if x.strip()]
    rows = []
    for line in lines:
        parts = re.split(r"[;\t, ]+", line)
        parts = [p for p in parts if p]
        if not parts:
            continue

        pozo = parts[0]
        nums = []
        for p in parts[1:]:
            n = to_number(p)
            if n is not None:
                nums.append(n)

        longitud = None
        kg = None
        acumulado = None
        if len(nums) == 1:
            kg = nums[0]
        elif len(nums) == 2:
            longitud, kg = nums
        elif len(nums) >= 3:
            longitud, kg, acumulado = nums[:3]

        rows.append({
            "pozo_id": pozo,
            "longitud_real_m": longitud,
            "kg_pozo": kg,
            "kg_acumulado": acumulado,
        })

    return normalize_rows(rows)


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

    kg_m_alerts = 0
    if "longitud_real_m" in tmp.columns:
        mask = tmp["longitud_real_m"].notna() & tmp["kg_pozo"].notna() & (tmp["longitud_real_m"] > 0)
        kg_m = tmp.loc[mask, "kg_pozo"] / tmp.loc[mask, "longitud_real_m"]
        # Solo alerta valores muy extremos para no ensuciar.
        kg_m_alerts = int(((kg_m < 3) | (kg_m > 35)).sum())

    return total, last_acc, diff_acc, duplicates, kg_m_alerts


with st.sidebar:
    st.header("Datos de control")
    fecha = st.date_input("Fecha", value=date.today())
    camion = st.text_input("Camión")
    explosivo = st.selectbox("Tipo de explosivo", EXPLOSIVOS, index=1)
    disparo = st.text_input("Disparo")
    vuelta = st.selectbox("Vuelta", ["1", "2", "3", "4"], index=0)
    total_referencia = st.number_input("Total referencia / Blastcenter", min_value=0.0, value=0.0, step=1.0)
    usar_total = st.checkbox("Usar total referencia", value=False)
    st.markdown("---")
    model = st.text_input("Modelo de lectura", value=get_secret("GEMINI_MODEL", "gemini-3.5-flash"))
    st.caption("Desarrollado por Luis Ponte · X+ Operational Excellence")


if "tabla" not in st.session_state:
    st.session_state["tabla"] = empty_table(18)

if "obs_lectura" not in st.session_state:
    st.session_state["obs_lectura"] = []

if "meta_ia" not in st.session_state:
    st.session_state["meta_ia"] = {}


uploaded = st.file_uploader("Sube imagen de la planilla", type=["jpg", "jpeg", "png", "webp"])

activar_camara = st.checkbox("Activar cámara para tomar foto", value=False)
camera = None
if activar_camara:
    camera = st.camera_input("Tomar foto con cámara")

image_file = camera or uploaded

tab_planilla, tab_ingreso, tab_validacion = st.tabs(["Planilla", "Ingreso rápido", "Tabla y validación"])

with tab_planilla:
    if image_file:
        image_bytes = image_file.getvalue()
        mime_type = getattr(image_file, "type", "image/jpeg") or "image/jpeg"

        left, right = st.columns([0.42, 0.58], gap="large")
        with left:
            st.subheader("Imagen")
            st.image(Image.open(image_file), use_container_width=True)

        with right:
            st.subheader("Lectura inteligente")
            st.info("Analiza la planilla y luego revisa/ajusta la tabla antes de validar.")

            if st.button("Analizar planilla", type="primary"):
                with st.spinner("Analizando imagen..."):
                    try:
                        data = extract_with_gemini(image_bytes, mime_type, model)
                        st.session_state["tabla"] = normalize_rows(data.get("rows", []))
                        st.session_state["obs_lectura"] = data.get("observaciones_lectura", []) or []
                        st.session_state["meta_ia"] = {
                            "camion_detectado": data.get("camion_detectado"),
                            "explosivo_detectado": data.get("explosivo_detectado"),
                        }
                        st.success("Lectura completada. Revisa la tabla antes de validar.")
                    except Exception as e:
                        st.error(f"No se pudo analizar la imagen: {e}")

            if st.session_state["meta_ia"]:
                c1, c2 = st.columns(2)
                c1.metric("Camión detectado", st.session_state["meta_ia"].get("camion_detectado") or "—")
                c2.metric("Explosivo detectado", st.session_state["meta_ia"].get("explosivo_detectado") or "—")

            if st.session_state["obs_lectura"]:
                st.warning("Observaciones de lectura:")
                for obs in st.session_state["obs_lectura"]:
                    st.write(f"- {obs}")
    else:
        st.info("Sube o toma una foto para comenzar.")

with tab_ingreso:
    st.subheader("Ingreso rápido")
    st.caption("Una fila por pozo. Formato recomendado: `pozo_id longitud_real kg_pozo kg_acumulado`.")
    quick_text = st.text_area(
        "Pegar datos",
        placeholder="97 8.0 120 120\n16 8.0 120 240\n12 8.0 130 370",
        height=180
    )
    if st.button("Cargar ingreso rápido"):
        st.session_state["tabla"] = quick_input_to_df(quick_text)
        st.success("Datos cargados a la tabla editable.")

with tab_validacion:
    st.subheader("Tabla editable de verificación")
    st.caption("Solo campos operacionales clave: Pozo ID, longitud real, kg por pozo y kg acumulado.")

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
        key="main_editor",
    )
    st.session_state["tabla"] = edited

    total, last_acc, diff_acc, duplicates, kg_m_alerts = validate_table(edited)

    ref_diff = None
    if usar_total:
        ref_diff = total - total_referencia

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total kg pozo", f"{total:,.0f} kg")
    c2.metric("Último acumulado", f"{last_acc:,.0f} kg" if last_acc is not None else "—")
    c3.metric("Dif. vs acumulado", f"{diff_acc:,.0f} kg" if diff_acc is not None else "—")
    c4.metric("Dif. vs referencia", f"{ref_diff:,.0f} kg" if ref_diff is not None else "—")

    alerts = []
    if duplicates:
        alerts.append(f"Pozos repetidos: {', '.join(duplicates)}")
    if diff_acc is not None and abs(diff_acc) > 0.0001:
        alerts.append("El total de kg/pozo no coincide con el último acumulado.")
    if usar_total and ref_diff is not None and abs(ref_diff) > 0.0001:
        alerts.append("El total de kg/pozo no coincide con el total de referencia.")
    if kg_m_alerts:
        alerts.append(f"Revisar kg/m en {kg_m_alerts} fila(s), podría haber longitud o kg atípico.")

    if not alerts:
        st.markdown("<div class='ok-box'><b>✅ Validación sin alertas internas.</b></div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='warn-box'><b>🟡 Revisión recomendada:</b></div>", unsafe_allow_html=True)
        for a in alerts:
            st.write(f"- {a}")

    export = edited.copy()
    export["fecha"] = str(fecha)
    export["camion"] = camion
    export["explosivo"] = explosivo
    export["disparo"] = disparo
    export["vuelta"] = vuelta
    export["total_kg_pozo"] = total
    export["ultimo_acumulado"] = last_acc
    export["diferencia_acumulado"] = diff_acc
    export["total_referencia"] = total_referencia if usar_total else None
    export["diferencia_referencia"] = ref_diff

    csv = export.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "Descargar CSV para Excel",
        data=csv,
        file_name="xplus_loadcheck_resultado.csv",
        mime="text/csv"
    )

st.markdown("---")
st.caption("Desarrollado por Luis Ponte · X+ Operational Excellence")
