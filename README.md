# X+ LoadCheck v4.6

Asistente de verificación de planillas de carguío.

## Cambios v4.6

- Permite subir varias imágenes y analizarlas todas con un solo botón.
- Botón principal:
  - Analizar todas las planillas cargadas
- Cada imagen se analiza internamente una por una y queda guardada en el Resumen de malla.
- Evita duplicar hojas si vuelves a analizar el mismo archivo: actualiza por identificador de imagen.
- Permite renombrar las hojas antes del análisis masivo.
- Mantiene opción de analizar/revisar una planilla individual.
- En Tabla y validación puedes corregir una hoja y guardar las correcciones en el resumen.
- En Resumen de malla se suman todas las hojas guardadas y se compara contra Blastcenter.

## Secrets requeridos en Streamlit Cloud

```toml
GEMINI_API_KEY = "TU_API_KEY"
GEMINI_MODEL = "gemini-2.5-flash"
```
