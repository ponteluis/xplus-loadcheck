# X+ LoadCheck v4.2

Asistente de verificación de planillas de carguío.

## Cambios v4.2

- El Total Blastcenter ya no aparece en Datos de control.
- El Total Blastcenter se ingresa en la pestaña Resumen de malla.
- Permite comparar la suma total de hojas contra Blastcenter.
- Permite limpiar toda la memoria de la sesión.
- Permite renombrar cada planilla antes de guardarla en el resumen.
- El resumen muestra nombre de hoja y archivo original.
- Exporta CSV separado por punto y coma (;), compatible con Excel regional.
- Exporta Excel .xlsx con:
  - Control_malla
  - Resumen_hojas
  - Detalle_pozos
- Mantiene tabla editable solo con:
  - Pozo ID
  - Longitud real [m]
  - Kg pozo
  - Kg acumulado

## Secrets requeridos en Streamlit Cloud

```toml
GEMINI_API_KEY = "TU_API_KEY"
GEMINI_MODEL = "gemini-2.5-flash"
```
