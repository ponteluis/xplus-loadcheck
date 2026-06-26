from pathlib import Path
import re
from datetime import date

import pandas as pd
import streamlit as st
from PIL import Image, ImageOps, ImageEnhance


st.set_page_config(
    page_title="X+ LoadCheck",
    page_icon="⛏️",
    layout="wide"
)

APP_TITLE = "X+ LoadCheck"

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
    .brand-main {
        font-weight: 800;
        font-size: 18px;
    }
    .brand-sub {
        color: #9ca3af;
        font-size: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

logo_path = Path("maxam_logo.png")
if logo_path.exists():
    st.image(str(logo_path), width=190)
else:
    st.markdown("### MAXAM")

st.title(APP_TITLE)
st.caption("Prototipo 100% local/gratuito para control de suma, corrección de planillas y OCR experimental.")
st.markdown(
    """
    <div class="brand-box">
        <div class="brand-main">Desarrollado por Luis Ponte</div>
        <div class="brand-sub">X+ Operational Excellence · Asistente preliminar de verificación de planillas de carguío</div>
    </div>
    """,
    unsafe_allow_html=True
)

with st.sidebar:
    st.header("Datos de control")
    fecha = st.date_input("Fecha", value=date.today())
    camion = st.text_input("Camión")
    disparo = st.text_input("Disparo")
    vuelta = st.selectbox("Vuelta", ["1", "2", "3", "4"], index=0)
    total_referencia = st.number_input("Total referencia / papel / Blastcenter", min_value=0.0, value=0.0, step=1.0)
    usar_total = st.checkbox("Usar este total como referencia", value=False)
    st.markdown("---")
    st.caption("Desarrollado por Luis Ponte · X+ Operational Excellence")
    st.info("Modo gratis: no usa API de OpenAI ni consume créditos. El OCR local es experimental y puede fallar con letra manuscrita.")

def default_table(n=20):
    return pd.DataFrame({
        "fila": list(range(1, n + 1)),
        "pozo": [""] * n,
        "kg": [None] * n,
        "contar": [True] * n,
        "tachado": [False] * n,
        "observacion": [""] * n,
    })

def parse_numbers(text):
    return [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[,.]\d+)?", text or "")]

def try_tesseract_ocr(image: Image.Image):
    try:
        import pytesseract
        img = ImageOps.grayscale(image)
        img = ImageEnhance.Contrast(img).enhance(2.2)
        raw = pytesseract.image_to_string(
            img,
            config="--psm 6 -c tessedit_char_whitelist=0123456789.,-/ "
        )
        return raw, None
    except Exception as e:
        return "", str(e)

def compute_total(df):
    if df is None or df.empty:
        return 0.0
    tmp = df.copy()
    tmp["kg"] = pd.to_numeric(tmp["kg"], errors="coerce")
    tmp["contar"] = tmp["contar"].fillna(False).astype(bool)
    return float(tmp.loc[tmp["contar"], "kg"].fillna(0).sum())

def compute_status(total, ref_enabled, ref):
    if not ref_enabled:
        return "🟡 SIN TOTAL DE REFERENCIA", None
    diff = total - ref
    if abs(diff) < 0.0001:
        return "✅ CUADRA", diff
    return "❌ HAY DISCREPANCIA", diff

uploaded = st.file_uploader("Sube imagen de la planilla", type=["jpg", "jpeg", "png", "webp"])

activar_camara = st.checkbox("Activar cámara para tomar foto", value=False)
camera = None
if activar_camara:
    camera = st.camera_input("Tomar foto con cámara")

image_file = camera or uploaded

if "tabla" not in st.session_state:
    st.session_state["tabla"] = default_table(20)

if image_file:
    img = Image.open(image_file).convert("RGB")
    left, right = st.columns([0.42, 0.58], gap="large")

    with left:
        st.subheader("Imagen")
        st.image(img, use_container_width=True)

    with right:
        st.subheader("Lectura autom?tica")
        st.warning("Este OCR es gratis/local, pero no es tan bueno como un modelo con visión para letra manuscrita. Úsalo solo como ayuda; el supervisor corrige la tabla.")

        if st.button("Analizar planilla"):
            raw, err = try_tesseract_ocr(img)
            st.session_state["ocr_raw"] = raw
            if err:
                st.session_state["ocr_error"] = err
            else:
                st.session_state["ocr_error"] = ""

        if st.session_state.get("ocr_error"):
            st.error("No se pudo completar la lectura autom?tica. Revisa la imagen o ingresa los datos manualmente.")
            st.code(st.session_state["ocr_error"])

        raw_text = st.text_area(
            "Texto/números detectados por OCR o pegados manualmente",
            value=st.session_state.get("ocr_raw", ""),
            height=140
        )

        nums = parse_numbers(raw_text)
        st.caption(f"Números detectados/pegados: {len(nums)}")

        if nums:
            st.write(nums[:80])

        if st.button("Cargar números detectados como KG"):
            df = default_table(max(20, len(nums)))
            for i, val in enumerate(nums):
                df.loc[i, "kg"] = val
                df.loc[i, "observacion"] = "Valor detectado autom?ticamente; revisar."
            st.session_state["tabla"] = df
            st.success("Números cargados a la tabla editable. Revisa y elimina los que no sean kg cargados.")

st.divider()
st.subheader("Tabla editable de verificación")

st.caption("Puedes escribir los KG manualmente, pegar números detectados, desmarcar filas tachadas y agregar observaciones.")

tabla_editada = st.data_editor(
    st.session_state["tabla"],
    num_rows="dynamic",
    hide_index=True,
    width="stretch",
    column_config={
        "fila": st.column_config.NumberColumn("Fila"),
        "pozo": st.column_config.TextColumn("Pozo"),
        "kg": st.column_config.NumberColumn("Kg cargado", step=1),
        "contar": st.column_config.CheckboxColumn("Contar"),
        "tachado": st.column_config.CheckboxColumn("Tachado"),
        "observacion": st.column_config.TextColumn("Observación"),
    },
    key="tabla_editor"
)

st.session_state["tabla"] = tabla_editada

total = compute_total(tabla_editada)
status, diff = compute_status(total, usar_total, total_referencia)

c1, c2, c3 = st.columns(3)
c1.metric("Total calculado", f"{total:,.0f} kg")
c2.metric("Total referencia", f"{total_referencia:,.0f} kg" if usar_total else "No usado")
c3.metric("Diferencia", f"{diff:,.0f} kg" if diff is not None else "—")

st.markdown(f"## {status}")

export = tabla_editada.copy()
export["fecha_control"] = str(fecha)
export["camion"] = camion
export["disparo"] = disparo
export["vuelta"] = vuelta
export["total_calculado"] = total
export["total_referencia"] = total_referencia if usar_total else None
export["estado"] = status

csv = export.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "Descargar CSV para Excel",
    data=csv,
    file_name="xplus_loadcheck_free_resultado.csv",
    mime="text/csv"
)

st.markdown("---")
st.caption("Desarrollado por Luis Ponte · X+ Operational Excellence · MVP local/gratuito")
