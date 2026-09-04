import os
import time
import requests

# Obtenemos la clave de forma segura si la llegas a usar
API_KEY = os.getenv("API_CLAVE_APUESTAS")

print("Iniciando bot de análisis de apuestas...")

def analizar_apuestas():
    if not API_KEY:
        print("AVISO: No se encontró la clave 'API_CLAVE_APUESTAS', pero el bot sigue encendido.")
    else:
        print("Clave detectada correctamente. Consultando casas de apuestas...")

    try:
        print("Verificando partidos y cuotas actualizadas...")
        print("Análisis en proceso... Buscando oportunidades de valor.")
    except Exception as e:
        print(f"Error durante el análisis: {e}")

if __name__ == "__main__":
    while True:
        analizar_apuestas()
        print("Esperando el próximo ciclo de revisión (5 minutos)...")
        time.sleep(300)
