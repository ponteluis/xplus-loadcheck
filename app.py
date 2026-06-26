from pathlib import Path
import re
from datetime import date

import pandas as pd
import streamlit as st
from PIL import Image, ImageOps, ImageEnhance, ImageFilter


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
    .ok-box {
        padding: 12px 14px;
        border-radius: 10px;
        background: rgba(31, 185, 129, 0.12);
        border: 1px solid rgba(31, 185, 129, 0.35);
    }
    .warn-box {
        padding: 12px 14px;
        border-radius: 10px;
        background: rgba(255, 193, 7, 0.12);
        border: 1px solid rgba(255, 193, 7, 0.35);
    }
    .bad-box {
        padding: 12px 14px;
        border-radius: 10px;
        background: rgba(255, 77, 77, 0.12);
        border: 1px solid rgba(255, 77, 77, 0.35);
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

EXPLOSIVOS = [
    "RIOFLEX 5000",
    "RIOFLEX 7000",
    "RIOFLEX 8000",
    "RIOFLEX",
    "ANFO",
    "OTRO",
]

with st.sidebar:
    st.header("Datos de control")
    fecha = st.date_input("Fecha", value=date.today())
    camion_default = st.text_input("Camión")
    disparo = st.text_input("Disparo")
    vuelta = st.selectbox("Vuelta", ["1", "2", "3", "4"], index=0)
    explosivo_default = st.selectbox("Explosivo", EXPLOSIVOS, index=1)
    total_referencia = st.number_input("Total referencia / papel / Blastcenter", min_value=0.0, value=0.0, step=1.0)
    usar_total = st.checkbox("Usar este total como referencia", value=False)

    st.markdown("---")
    st.subheader("Filtros de lectura")
    kg_min = st.number_input("Kg mínimo esperado por pozo", min_value=0.0, value=20.0, step=5.0)
    kg_max = st.number_input("Kg máximo esperado por pozo", min_value=0.0, value=250.0, step=5.0)
    st.caption("Estos filtros evitan que números como fechas, camiones o totales se carguen por error como kg/pozo.")

    st.markdown("---")
    st.caption("Desarrollado por Luis Ponte · X+ Operational Excellence")
    st.info("Herramienta piloto para apoyar la revisión operacional de planillas de carguío.")


def default_table(n=20):
    return pd.DataFrame({
        "fila": list(range(1, n + 1)),
        "camion": [""] * n,
        "explosivo": [""] * n,
        "pozo_id": [""] * n,
        "longitud_real_m": [None] * n,
        "kg_pozo": [None] * n,
        "kg_acumulado_planilla": [None] * n,
        "kg_acumulado_calculado": [None] * n,
        "delta_acumulado": [None] * n,
        "kg_por_m": [None] * n,
        "contar": [True] * n,
        "tachado": [False] * n,
        "observacion": [""] * n,
    })


def parse_numbers(text):
    values = []
    for x in re.findall(r"\d+(?:[,.]\d+)?", text or ""):
        try:
            values.append(float(x.replace(",", ".")))
        except Exception:
            pass
    return values


def preprocess_image(image: Image.Image, mode: str = "standard") -> Image.Image:
    img = image.convert("RGB")
    img = ImageOps.exif_transpose(img)
    img = ImageOps.grayscale(img)

    if mode == "high_contrast":
        img = ImageEnhance.Contrast(img).enhance(2.8)
        img = ImageEnhance.Sharpness(img).enhance(2.0)
        img = img.filter(ImageFilter.SHARPEN)
    elif mode == "soft":
        img = ImageEnhance.Contrast(img).enhance(1.7)
        img = ImageEnhance.Sharpness(img).enhance(1.4)
    else:
        img = ImageEnhance.Contrast(img).enhance(2.2)
        img = ImageEnhance.Sharpness(img).enhance(1.8)

    return img


def try_tesseract_ocr(image: Image.Image, psm: int = 6, mode: str = "standard"):
    try:
        import pytesseract
        img = preprocess_image(image, mode=mode)
        config = f"--psm {psm} -c tessedit_char_whitelist=0123456789.,-/ "
        raw = pytesseract.image_to_string(img, config=config)
        return raw, None
    except Exception as e:
        return "", str(e)


def calculate_fields(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return default_table(20)

    out = df.copy()

    for col in ["longitud_real_m", "kg_pozo", "kg_acumulado_planilla"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    out["contar"] = out["contar"].fillna(False).astype(bool)

    acumulado = []
    running = 0.0
    for _, row in out.iterrows():
        kg = row.get("kg_pozo")
        contar = bool(row.get("contar"))
        if contar and pd.notna(kg):
            running += float(kg)
            acumulado.append(running)
        else:
            acumulado.append(None)

    out["kg_acumulado_calculado"] = acumulado

    out["delta_acumulado"] = out.apply(
        lambda r: None
        if pd.isna(r.get("kg_acumulado_planilla")) or pd.isna(r.get("kg_acumulado_calculado"))
        else float(r.get("kg_acumulado_planilla")) - float(r.get("kg_acumulado_calculado")),
        axis=1
    )

    out["kg_por_m"] = out.apply(
        lambda r: None
        if pd.isna(r.get("longitud_real_m")) or pd.isna(r.get("kg_pozo")) or float(r.get("longitud_real_m")) == 0
        else float(r.get("kg_pozo")) / float(r.get("longitud_real_m")),
        axis=1
    )

    return out


def compute_total(df):
    if df is None or df.empty:
        return 0.0
    tmp = df.copy()
    tmp["kg_pozo"] = pd.to_numeric(tmp["kg_pozo"], errors="coerce")
    tmp["contar"] = tmp["contar"].fillna(False).astype(bool)
    return float(tmp.loc[tmp["contar"], "kg_pozo"].fillna(0).sum())


def compute_status(total, ref_enabled, ref, warnings_count):
    if not ref_enabled:
        if warnings_count > 0:
            return "🟡 REVISIÓN RECOMENDADA", None
        return "🟡 PENDIENTE DE REFERENCIA", None

    diff = total - ref
    if abs(diff) < 0.0001 and warnings_count == 0:
        return "✅ CUADRA", diff
    if abs(diff) < 0.0001 and warnings_count > 0:
        return "🟡 CUADRA CON OBSERVACIONES", diff
    return "❌ HAY DISCREPANCIA", diff


def duplicate_pozos(df):
    if df is None or df.empty or "pozo_id" not in df.columns:
        return []
    pozos = df.loc[df["contar"].fillna(False).astype(bool), "pozo_id"].astype(str).str.strip()
    pozos = pozos[pozos.ne("")]
    return sorted(pozos[pozos.duplicated()].unique().tolist())


def accumulated_warnings(df):
    if df is None or df.empty:
        return 0
    if "delta_acumulado" not in df.columns:
        return 0
    d = pd.to_numeric(df["delta_acumulado"], errors="coerce")
    return int(d.fillna(0).abs().gt(0.0001).sum())


def quick_input_to_df(text, camion, explosivo):
    """
    Expected row formats:
    pozo kg
    pozo longitud kg
    pozo longitud kg acumulado
    Separators may be spaces, tabs, commas or semicolons.
    """
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    rows = []
    for i, line in enumerate(lines, start=1):
        parts = re.split(r"[;\t, ]+", line.strip())
        parts = [p for p in parts if p]
        pozo = parts[0] if parts else ""
        nums = []
        for p in parts[1:]:
            try:
                nums.append(float(p.replace(",", ".")))
            except Exception:
                pass

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
            "fila": i,
            "camion": camion,
            "explosivo": explosivo,
            "pozo_id": pozo,
            "longitud_real_m": longitud,
            "kg_pozo": kg,
            "kg_acumulado_planilla": acumulado,
            "kg_acumulado_calculado": None,
            "delta_acumulado": None,
            "kg_por_m": None,
            "contar": True,
            "tachado": False,
            "observacion": "Ingreso rápido; revisar."
        })
    return calculate_fields(pd.DataFrame(rows)) if rows else default_table(20)


uploaded = st.file_uploader("Sube imagen de la planilla", type=["jpg", "jpeg", "png", "webp"])

activar_camara = st.checkbox("Activar cámara para tomar foto", value=False)
camera = None
if activar_camara:
    camera = st.camera_input("Tomar foto con cámara")

image_file = camera or uploaded

if "tabla" not in st.session_state:
    st.session_state["tabla"] = default_table(20)

tab1, tab2, tab3 = st.tabs(["Planilla", "Ingreso rápido", "Tabla y validación"])

with tab1:
    if image_file:
        img = Image.open(image_file).convert("RGB")
        left, right = st.columns([0.42, 0.58], gap="large")

        with left:
            st.subheader("Imagen")
            st.image(img, use_container_width=True)

        with right:
            st.subheader("Lectura automática")
            st.info("Analiza la imagen y revisa los valores detectados antes de validar la suma.")

            c1, c2, c3 = st.columns(3)
            with c1:
                psm = st.selectbox("Modo OCR", [6, 11, 12, 13], index=1)
            with c2:
                pre_mode = st.selectbox("Contraste", ["standard", "high_contrast", "soft"], index=1)
            with c3:
                only_kg_filter = st.checkbox("Filtrar posibles kg/pozo", value=True)

            if st.button("Analizar planilla", type="primary"):
                raw, err = try_tesseract_ocr(img, psm=psm, mode=pre_mode)
                st.session_state["ocr_raw"] = raw
                st.session_state["ocr_error"] = err or ""

            if st.session_state.get("ocr_error"):
                st.warning("No se pudo completar la lectura automática. Revisa la imagen o ingresa los datos manualmente.")

            raw_text = st.text_area(
                "Valores detectados o ingresados manualmente",
                value=st.session_state.get("ocr_raw", ""),
                height=150
            )

            nums = parse_numbers(raw_text)
            if only_kg_filter:
                filtered = [n for n in nums if kg_min <= n <= kg_max]
            else:
                filtered = nums

            st.caption(f"Valores detectados: {len(nums)} · Posibles kg/pozo según filtro: {len(filtered)}")

            if filtered:
                st.write(filtered[:80])

            if st.button("Cargar posibles kg/pozo a tabla"):
                df = default_table(max(20, len(filtered)))
                for i, val in enumerate(filtered):
                    df.loc[i, "camion"] = camion_default
                    df.loc[i, "explosivo"] = explosivo_default
                    df.loc[i, "kg_pozo"] = val
                    df.loc[i, "observacion"] = "Valor detectado automáticamente; revisar."
                st.session_state["tabla"] = calculate_fields(df)
                st.success("Valores cargados a kg/pozo. Revisa pozo_id, longitud, acumulado y elimina valores que no correspondan.")
    else:
        st.info("Sube o toma una foto para comenzar.")

with tab2:
    st.subheader("Ingreso rápido")
    st.caption("Pega o escribe una fila por pozo. Formatos aceptados: `pozo kg`, `pozo longitud kg`, o `pozo longitud kg acumulado`.")

    ejemplo = "97 8.0 120 120\n16 8.0 120 240\n12 8.0 130 370"
    quick_text = st.text_area("Datos rápidos", value="", placeholder=ejemplo, height=180)

    if st.button("Cargar ingreso rápido"):
        st.session_state["tabla"] = quick_input_to_df(quick_text, camion_default, explosivo_default)
        st.success("Datos cargados a la tabla editable.")

with tab3:
    st.subheader("Tabla editable de verificación")
    st.caption("Campos clave: Pozo ID, longitud real, kg/pozo y acumulado de planilla. El acumulado calculado y las diferencias se recalculan automáticamente.")

    st.session_state["tabla"] = calculate_fields(st.session_state["tabla"])

    tabla_editada = st.data_editor(
        st.session_state["tabla"],
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            "fila": st.column_config.NumberColumn("Fila"),
            "camion": st.column_config.TextColumn("Camión"),
            "explosivo": st.column_config.SelectboxColumn("Explosivo", options=EXPLOSIVOS),
            "pozo_id": st.column_config.TextColumn("Pozo ID"),
            "longitud_real_m": st.column_config.NumberColumn("Longitud real [m]", step=0.1),
            "kg_pozo": st.column_config.NumberColumn("Kg pozo", step=1),
            "kg_acumulado_planilla": st.column_config.NumberColumn("Kg acumulado planilla", step=1),
            "kg_acumulado_calculado": st.column_config.NumberColumn("Kg acumulado calculado", disabled=True),
            "delta_acumulado": st.column_config.NumberColumn("Delta acumulado", disabled=True),
            "kg_por_m": st.column_config.NumberColumn("Kg/m", disabled=True),
            "contar": st.column_config.CheckboxColumn("Contar"),
            "tachado": st.column_config.CheckboxColumn("Tachado"),
            "observacion": st.column_config.TextColumn("Observación"),
        },
        key="tabla_editor_v2"
    )

    st.session_state["tabla"] = calculate_fields(tabla_editada)

    total = compute_total(st.session_state["tabla"])
    dup = duplicate_pozos(st.session_state["tabla"])
    acc_warn = accumulated_warnings(st.session_state["tabla"])
    warnings_count = len(dup) + acc_warn
    status, diff = compute_status(total, usar_total, total_referencia, warnings_count)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total calculado", f"{total:,.0f} kg")
    c2.metric("Total referencia", f"{total_referencia:,.0f} kg" if usar_total else "No usado")
    c3.metric("Diferencia", f"{diff:,.0f} kg" if diff is not None else "—")
    c4.metric("Alertas", warnings_count)

    st.markdown(f"## {status}")

    if dup:
        st.markdown(
            f"<div class='warn-box'><b>Pozos repetidos:</b> {', '.join(dup)}</div>",
            unsafe_allow_html=True
        )
    if acc_warn:
        st.markdown(
            f"<div class='warn-box'><b>Revisar acumulados:</b> {acc_warn} fila(s) tienen diferencia entre acumulado de planilla y acumulado calculado.</div>",
            unsafe_allow_html=True
        )
    if not dup and not acc_warn:
        st.markdown(
            "<div class='ok-box'><b>Sin alertas internas:</b> no se detectaron pozos repetidos ni diferencias de acumulado.</div>",
            unsafe_allow_html=True
        )

    export = st.session_state["tabla"].copy()
    export["fecha_control"] = str(fecha)
    export["disparo"] = disparo
    export["vuelta"] = vuelta
    export["total_calculado"] = total
    export["total_referencia"] = total_referencia if usar_total else None
    export["estado"] = status

    csv = export.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "Descargar CSV para Excel",
        data=csv,
        file_name="xplus_loadcheck_resultado.csv",
        mime="text/csv"
    )

st.markdown("---")
st.caption("Desarrollado por Luis Ponte · X+ Operational Excellence")
