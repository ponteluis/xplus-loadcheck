# X+ LoadCheck v4.5

Asistente de verificación de planillas de carguío.

## Cambios v4.5

- Interfaz más simple y menos cargada.
- En Tabla y validación queda una sola tabla editable visible:
  - Pozo ID
  - Longitud real [m]
  - Kg pozo
  - Kg acumulado operador
- El detalle automático de acumulados queda oculto en un desplegable:
  - Kg acumulado calculado
  - Diferencia acumulado
- En Resumen de malla se eliminan columnas técnicas de la vista principal:
  - modelo
  - tokens
  - observaciones largas
  - archivo original
- El resumen principal muestra solo:
  - Hoja
  - Camión
  - Explosivo
  - Disparo
  - Total kg hoja
  - Último acumulado operador
  - Dif. hoja
  - Alertas
- La comparación principal es:
  - Suma total kg hojas
  - Total Blastcenter
  - Diferencia
- La información técnica queda oculta en "Ver información técnica".
- Exporta CSV con separador punto y coma (;).
- Exporta Excel .xlsx con Control_malla, Resumen_hojas y Detalle_pozos.

## Secrets requeridos en Streamlit Cloud

```toml
GEMINI_API_KEY = "TU_API_KEY"
GEMINI_MODEL = "gemini-2.5-flash"
```
