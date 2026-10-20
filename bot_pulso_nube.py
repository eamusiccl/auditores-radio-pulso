import time
import random
import json
import os
import requests

# ==========================================
# 1. CONFIGURACIÓN (Lee desde la nube o directo aquí)
# ==========================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
STREAM_URL = os.getenv("STREAM_URL")
FIREBASE_CHAT_URL = os.getenv("FIREBASE_CHAT_URL")

# Cuántos minutos durará encendido este turno en la nube (ej. 50 minutos por cada hora)
DURACION_BLOQUE_MINUTOS = 50
INTERVALO_ESCUCHA_MIN = 180  # 3 minutos
INTERVALO_ESCUCHA_MAX = 280  # 4.5 minutos

AUDITORES = [
    {"nombre": "Nico_V", "estilo": "Escribe todo en minúsculas, sin punto final, corto y directo. No usa emojis."},
    {"nombre": "Javi Morales", "estilo": "Entusiasta y cercana, usa 1 o 2 emojis como 🔥, 🙌 o ❤️. Destaca lo que dice el locutor."},
    {"nombre": "Matías R.", "estilo": "Participativo y reflexivo. Hace una pregunta corta sobre el tema o aporta una idea breve."},
    {"nombre": "Cami_99", "estilo": "Juvenil y espontánea. Reacciona con buena onda al tema mientras estudia o trabaja."},
    {"nombre": "Diego Araya", "estilo": "Directo, usa expresiones chilenas suaves ('buenísimo el programa', 'tremendo punto', 'tal cual')."},
    {"nombre": "Vale_Ignacia", "estilo": "Alegre y expresiva, usa signos de exclamación y algún emoji como ✨ o 👏."}
]

ultimos_auditores = []

def capturar_audio_directo(url_stream, archivo_salida="muestra_pulso.mp3", segundos=20):
    """Captura 20 segundos del stream directamente con Python (¡Sin necesitar FFmpeg!)."""
    try:
        inicio = time.time()
        with requests.get(url_stream, stream=True, timeout=15) as r:
            r.raise_for_status()
            with open(archivo_salida, "wb") as f:
                for chunk in r.iter_content(chunk_size=4096):
                    if chunk:
                        f.write(chunk)
                    if time.time() - inicio >= segundos:
                        break
        return os.path.exists(archivo_salida) and os.path.getsize(archivo_salida) > 10000
    except Exception as e:
        print(f"⚠️ Error capturando stream: {e}")
        return False

def transcribir_con_groq(archivo_audio):
    """Usa Whisper en Groq para convertir los 20 segundos de radio en texto."""
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    try:
        with open(archivo_audio, "rb") as f:
            archivos = {"file": ("radio.mp3", f, "audio/mpeg")}
            datos = {"model": "whisper-large-v3-turbo", "language": "es", "response_format": "json"}
            r = requests.post(url, headers=headers, files=archivos, data=datos, timeout=30)
            if r.status_code == 200:
                return r.json().get("text", "").strip()
    except Exception as e:
        print(f"⚠️ Error al transcribir: {e}")
    return ""

def elegir_auditores_turno():
    global ultimos_auditores
    disponibles = [a for a in AUDITORES if a["nombre"] not in ultimos_auditores]
    cantidad = random.choices([1, 2, 3], weights=[35, 45, 20])[0]
    seleccionados = random.sample(disponibles, k=min(cantidad, len(disponibles)))
    ultimos_auditores = [a["nombre"] for a in seleccionados]
    return seleccionados

def generar_comentarios_groq(texto_escuchado, auditores_turno):
    if len(texto_escuchado.split()) < 8:
        return []

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    perfiles_txt = "\n".join([f"- {a['nombre']}: {a['estilo']}" for a in auditores_turno])

    prompt_usuario = f"""
    Esto se escuchó en vivo en Radio Pulso en los últimos 20 segundos:
    "{texto_escuchado}"

    1. Si es SOLO letra de una canción o frases sin sentido, devuelve: {{"comentarios": []}}
    2. Si es un locutor hablando en un programa, genera comentarios cortos (5 a 18 palabras) sobre ese tema exacto para estos auditores:
    {perfiles_txt}

    Responde SOLO en JSON con este formato:
    {{"comentarios": [{{"usuario": "Nombre", "mensaje": "texto"}}]}}
    """

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "Coordinador de auditores en vivo de Radio Pulso. Responde solo en JSON."},
            {"role": "user", "content": prompt_usuario}
        ],
        "temperature": 0.8,
        "response_format": {"type": "json_object"}
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        if r.status_code == 200:
            contenido = r.json()["choices"][0]["message"]["content"]
            return json.loads(contenido).get("comentarios", [])
    except Exception as e:
        print(f"⚠️ Error en IA: {e}")
    return []

def publicar_en_chat(usuario, mensaje):
    datos_mensaje = {
        "nombre": usuario,
        "texto": mensaje,
        "timestamp": int(time.time() * 1000)
    }
    try:
        requests.post(FIREBASE_CHAT_URL, json=datos_mensaje, timeout=10)
        print(f"💬 [{usuario}]: {mensaje}")
    except Exception as e:
        print(f"⚠️ Error al publicar: {e}")

if __name__ == "__main__":
    inicio_bloque = time.time()
    archivo_temp = "muestra_pulso.mp3"

    while (time.time() - inicio_bloque) < (DURACION_BLOQUE_MINUTOS * 60):
        if capturar_audio_directo(STREAM_URL, archivo_temp, segundos=20):
            texto_radio = transcribir_con_groq(archivo_temp)
            print(f"📝 Escuchado: {texto_radio[:80]}...")

            auditores_turno = elegir_auditores_turno()
            comentarios = generar_comentarios_groq(texto_radio, auditores_turno)

            for i, item in enumerate(comentarios):
                publicar_en_chat(item["usuario"], item["mensaje"])
                if i < len(comentarios) - 1:
                    time.sleep(random.randint(12, 25))

        espera = random.randint(INTERVALO_ESCUCHA_MIN, INTERVALO_ESCUCHA_MAX)
        if (time.time() - inicio_bloque + espera) >= (DURACION_BLOQUE_MINUTOS * 60):
            break
        time.sleep(espera)
