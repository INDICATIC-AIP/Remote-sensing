#!/usr/bin/env python3
"""
 PRUEBA DE task_api_client.py
Prueba con tu JSON real con múltiples consultas
"""

import os
import sys
import json
import asyncio

# Agregar rutas
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "utils")))

# Importar el cliente
from task_api_client import procesar_tarea_programada


async def test_with_real_json():
    """Probar con tu JSON real"""

    # Tu JSON real con múltiples consultas
    task_real = {
        "id": "task_mbsbwye2_0kk",
        "consultas": [
            {
                "source": "frames",
                "query": "frames|ptime|ge|003000|frames|ptime|le|045959|frames|lat|ge|6.1|frames|lat|le|10.8|frames|lon|ge|-82.9|frames|lon|le|-77.3",
                "return": "frames|mission|frames|tilt|frames|pdate|frames|ptime|frames|cldp|frames|azi|frames|elev|frames|fclt|frames|lat|frames|lon|frames|nlat|frames|nlon|frames|camera|frames|film|frames|geon|frames|feat|images|directory|images|filename|images|width|images|height",
                "modoNocturno": "003000-045959",
            },
            {
                "source": "frames",
                "query": "frames|ptime|ge|050000|frames|ptime|le|103000|frames|lat|ge|6.1|frames|lat|le|10.8|frames|lon|ge|-82.9|frames|lon|le|-77.3",
                "return": "frames|mission|frames|tilt|frames|pdate|frames|ptime|frames|cldp|frames|azi|frames|elev|frames|fclt|frames|lat|frames|lon|frames|nlat|frames|nlon|frames|camera|frames|film|frames|geon|frames|feat|images|directory|images|filename|images|width|images|height",
                "modoNocturno": "050000-103000",
            },
            {
                "source": "nadir",
                "query": "nadir|ptime|ge|003000|nadir|ptime|le|045959|nadir|lat|ge|6.1|nadir|lat|le|10.8|nadir|lon|ge|-82.9|nadir|lon|le|-77.3",
                "return": "nadir|mission|nadir|pdate|nadir|ptime|nadir|lat|nadir|lon|nadir|azi|nadir|elev|nadir|cldp|images|directory|images|filename|images|width|images|height",
                "modoNocturno": "003000-045959",
            },
            {
                "source": "nadir",
                "query": "nadir|ptime|ge|050000|nadir|ptime|le|103000|nadir|lat|ge|6.1|nadir|lat|le|10.8|nadir|lon|ge|-82.9|nadir|lon|le|-77.3",
                "return": "nadir|mission|nadir|pdate|nadir|ptime|nadir|lat|nadir|lon|nadir|azi|nadir|elev|nadir|cldp|images|directory|images|filename|images|width|images|height",
                "modoNocturno": "050000-103000",
            },
            {
                "source": "mlcoord",
                "query": "mlcoord|lat|ge|6.1|mlcoord|lat|le|10.8|mlcoord|lon|ge|-82.9|mlcoord|lon|le|-77.3",
                "return": "mlcoord|mission|mlcoord|lat|mlcoord|lon|mlcoord|orientation|images|directory|images|filename|images|width|images|height",
                "modoNocturno": "normal",
            },
        ],
        "hora": "14:16",
        "frecuencia": "ONCE",
        "intervalo": 1,
    }

    print(" Probando task_api_client.py con JSON real...")
    print(f" Tarea: {task_real['id']}")
    print(f" Consultas: {len(task_real['consultas'])}")

    try:
        # Ejecutar task_api_client
        resultados = await procesar_tarea_programada(task_real)

        print(f"\n ÉXITO!")
        print(f" Resultados obtenidos: {len(resultados)}")

        if resultados:
            print(f"\n Primer resultado:")
            primer = resultados[0]
            print(f"   - NASA_ID: {primer.get('images.filename', 'N/A')}")
            print(f"   - Directory: {primer.get('images.directory', 'N/A')}")
            print(f"   - Source: {primer.get('coordSource', 'N/A')}")
            print(f"   - Modo: {primer.get('modoConsulta', 'N/A')}")

            # Guardar resultados
            with open("test_resultados.json", "w", encoding="utf-8") as f:
                json.dump(resultados, f, indent=2, ensure_ascii=False, default=str)
            print(f"\n Resultados guardados en: test_resultados.json")

        return resultados

    except Exception as e:
        print(f"\n ERROR: {str(e)}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    # Ejecutar prueba
    resultados = asyncio.run(test_with_real_json())

    if resultados is not None:
        print(f"\n Prueba completada con {len(resultados)} resultados")
    else:
        print(f"\n Prueba falló")
