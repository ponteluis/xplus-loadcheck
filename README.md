# X+ LoadCheck v4.4

Asistente de verificación de planillas de carguío.

## Cambios v4.4

- Se corrige el problema de actualización de acumulados:
  - La tabla editable ahora contiene solo datos base.
  - La tabla de control automático se muestra debajo y se recalcula con cada cambio.
- Campos editables:
  - Pozo ID
  - Longitud real [m]
  - Kg pozo
  - Kg acumulado operador
- Campos calculados automáticamente:
  - Kg acumulado calculado
  - Diferencia acumulado
- Se mejora el flujo para analizar planillas en momentos separados:
  - Las hojas guardadas permanecen en Resumen de malla aunque cargues otra imagen después.
  - Botón "Guardar y preparar siguiente hoja".
  - Botón "Cargar otra planilla sin borrar resumen".
- El Resumen de malla suma todas las hojas guardadas:
  - Suma total kg hojas
  - Total Blastcenter malla
  - Diferencia vs Blastcenter
- Exporta CSV separado por punto y coma (;), compatible con Excel regional.
- Exporta Excel .xlsx con:
  - Control_malla
  - Resumen_hojas
  - Detalle_pozos

## Secrets requeridos en Streamlit Cloud

```toml
GEMINI_API_KEY = "TU_API_KEY"
GEMINI_MODEL = "gemini-2.5-flash"
```
