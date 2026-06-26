# X+ LoadCheck v4.3

Asistente de verificación de planillas de carguío.

## Cambios v4.3

- La lectura se centra principalmente en Kg pozo.
- El acumulado escrito en planilla se renombra como Kg acumulado operador.
- La app calcula automáticamente:
  - Kg acumulado calculado
  - Diferencia acumulado
- La validación compara:
  - Total calculado por kg/pozo
  - Último acumulado operador
  - Diferencias acumuladas fila por fila
- El Resumen de malla muestra claramente:
  - Suma total kg hojas
  - Total Blastcenter malla
  - Diferencia vs Blastcenter
- La comparación con Blastcenter se hace contra la suma de TODAS las hojas guardadas.
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
