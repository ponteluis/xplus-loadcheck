# X+ LoadCheck v4.1

Asistente de verificación de planillas de carguío.

## Cambios incluidos

- Interfaz en español.
- Sin contraseña inicial.
- Sin número de vuelta.
- Sin ingreso rápido.
- Datos de control: fecha, camión, tipo de explosivo, disparo y total Blastcenter.
- Tabla editable solo con:
  - Pozo ID
  - Longitud real [m]
  - Kg pozo
  - Kg acumulado
- Soporte para varias hojas de planilla en un mismo análisis.
- Resumen de malla: suma de totales por hoja y comparación con Blastcenter.
- CSV compatible con Excel regional usando separador punto y coma (;).
- Exportación Excel .xlsx con hojas:
  - Resumen_malla
  - Detalle_pozos

## Secrets requeridos en Streamlit Cloud

```toml
GEMINI_API_KEY = "TU_API_KEY"
GEMINI_MODEL = "gemini-2.5-flash"
```
