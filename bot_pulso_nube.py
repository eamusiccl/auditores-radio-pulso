import time
import random
import json
import os
import requests

# ==========================================
# 1. CONFIGURACIÓN SEGURA (Lee desde Secrets de GitHub)
# ==========================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
STREAM_URL = os.getenv("STREAM_URL")
FIREBASE_CHAT_URL = os.getenv("FIREBASE_CHAT_URL")

DURACION_BLOQUE_MINUTOS = 50
INTERVALO_ESCUCHA_MIN = 180  # 3 minutos
INTERVALO_ESCUCHA_MAX = 280  # 4.5 minutos

# ==========================================
# 2. POOL DE AUDITORES CON CIUDAD Y ESTILO PROPIO
# ==========================================
AUDITORES = [
    {
        "nombre": "Nico",
        "ciudad": "Coquimbo",
        "estilo": "Escribe todo en minúsculas, sin punto final, corto y directo. No usa emojis."
    },
    {
        "nombre": "Javi Morales",
        "ciudad": "La Serena",
        "estilo": "Entusiasta y cercana, usa 1 o 2 emojis como 🔥, 🙌 o 😊. Destaca lo que acaba de decir el locutor."
    },
    {
        "nombre": "Matías R.",
        "ciudad": "Ovalle",
        "estilo": "Participativo y reflexivo. Hace una pregunta corta sobre el tema o aporta una idea breve."
    },
    {
        "nombre": "Cami",
        "ciudad": "La Serena",
        "estilo": "Juvenil y espontánea. Reacciona con buena onda al tema mientras estudia o trabaja."
    },
    {
        "nombre": "Diego Araya",
        "ciudad": "Coquimbo",
        "estilo": "Directo, usa expresiones naturales ('buenísimo el programa', 'tremendo punto', 'tal cual')."
    },
    {
        "nombre": "Vale Ignacia",
        "ciudad": "Viña del Mar",
        "estilo": "Alegre y expresiva, usa signos de exclamación y algún emoji como ✨, 🎵 o 👏."
    },
    {
        "nombre": "Seba",
        "ciudad": "Santiago",
        "estilo": "Estilo relajado, escribe frases cortas de 6 a 12 palabras reaccionando al punto exacto que explicó el locutor."
    },
    {
        "nombre": "Fran",
        "ciudad": "Coquimbo",
        "estilo": "Muy atenta a los detalles de la conversación, comenta en una frase corta lo que más le gustó de lo que acaban de hablar."
    }
]

ultimos_auditores = []

def capturar_audio_directo(url_stream, archivo_salida="muestra_pulso.mp3", segundos=20):
    """Captura 20 segundos del stream directamente con Python."""
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
    perfiles_txt = "\n".join([f"- {a['nombre']} (de {a['ciudad']}): {a['estilo']}" for a in auditores_turno])

    prompt_usuario = f"""
    Esto se escuchó en vivo en Radio Pulso en los últimos 20 segundos:
    "{texto_escuchado}"

    REGLAS:
    1. Si es SOLO letra rimada de una canción, música o frases sin sentido, devuelve: {{"comentarios": []}}
    2. Si es un locutor o conductora hablando en un programa, genera comentarios cortos (entre 5 y 18 palabras) reaccionando específicamente a lo que dijo para estos auditores:
    {perfiles_txt}

    Responde SOLO en JSON con este formato exacto:
    {{
      "comentarios": [
        {{"name": "Nombre_Exacto_Del_Auditor", "message": "comentario aquí"}}
      ]
    }}
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

def publicar_en_muro_pulso(nombre, mensaje, ciudad):
    """Publica en Firebase usando la estructura exacta de muro_pulso."""
    datos_mensaje = {
        "category": "⚡ Saludo",
        "city": ciudad,
        "createdAt": int(time.time() * 1000),
        "likes": 0,
        "message": mensaje,
        "name": nombre
    }
    try:
        r = requests.post(FIREBASE_CHAT_URL, json=datos_mensaje, timeout=10)
        if r.status_code in [200, 201]:
            print(f"💬 [{nombre} - {ciudad}]: {mensaje}")
        else:
            print(f"⚠️ Error Firebase ({r.status_code}): {r.text}")
    except Exception as e:
        print(f"⚠️ Error al publicar: {e}")

if __name__ == "__main__":
    inicio_bloque = time.time()
    archivo_temp = "muestra_pulso.mp3"
    mapa_ciudades = {a["nombre"]: a["ciudad"] for a in AUDITORES}

    while (time.time() - inicio_bloque) < (DURACION_BLOQUE_MINUTOS * 60):
        if capturar_audio_directo(STREAM_URL, archivo_temp, segundos=20):
            texto_radio = transcribir_con_groq(archivo_temp)
            print(f"📝 Escuchado: {texto_radio[:80]}...")

            auditores_turno = elegir_auditores_turno()
            comentarios = generar_comentarios_groq(texto_radio, auditores_turno)

            for i, item in enumerate(comentarios):
                nombre_auditor = item.get("name", "Nico")
                texto_comentario = item.get("message", "")
                ciudad_auditor = mapa_ciudades.get(nombre_auditor, "Coquimbo")

                if texto_comentario:
                    publicar_en_muro_pulso(nombre_auditor, texto_comentario, ciudad_auditor)
                    if i < len(comentarios) - 1:
                        time.sleep(random.randint(12, 25))

        espera = random.randint(INTERVALO_ESCUCHA_MIN, INTERVALO_ESCUCHA_MAX)
        if (time.time() - inicio_bloque + espera) >= (DURACION_BLOQUE_MINUTOS * 60):
            break
        time.sleep(espera)
