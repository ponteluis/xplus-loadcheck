# X+ LoadCheck Free MVP

Versión gratuita/local:
- No usa API de OpenAI.
- No consume créditos.
- Mantiene imagen, tabla editable, cálculo de suma y exportación a CSV.
- Incluye OCR local experimental con Tesseract si está instalado.

## Ejecutar

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Logo

Para mostrar logo:
1. Copia un PNG del logo en esta carpeta.
2. Nómbralo exactamente `maxam_logo.png`.
3. Reinicia la app.

## OCR local

Para OCR necesitas instalar Tesseract en Windows. Si no está instalado, la app sigue funcionando como calculadora/validador editable.
