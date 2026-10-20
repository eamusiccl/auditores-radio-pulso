import time
import random
import json
import os
import requests

# ==========================================
# 1. CONFIGURACIÓN SEGURA (Desde Secrets de GitHub)
# ==========================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
STREAM_URL = os.getenv("STREAM_URL")
FIREBASE_CHAT_URL = os.getenv("FIREBASE_CHAT_URL")

DURACION_BLOQUE_MINUTOS = 50
INTERVALO_ESCUCHA_MIN = 180  # 3 minutos
INTERVALO_ESCUCHA_MAX = 290  # casi 5 minutos

# ==========================================
# 2. 45 AUDITORES CON CIUDAD FIJA Y 10 ESTILOS
# ==========================================
ESTILOS_ESCRITURA = [
    "Escribe todo en minúsculas, sin punto final, corto y directo. No usa emojis.",
    "Entusiasta y cercana, usa 1 o 2 emojis como 🔥, 🙌 o 😊. Destaca lo que acaba de decir el locutor.",
    "Participativo y reflexivo. Hace una pregunta corta sobre el tema o aporta una idea breve.",
    "Juvenil y espontáneo. Reacciona con buena onda al tema comentando desde el estudio o el trabajo.",
    "Directo, usa expresiones chilenas suaves y naturales ('buenísimo el programa', 'tremendo punto', 'toda la razón').",
    "Alegre y expresivo, usa signos de exclamación y algún emoji como ✨, 🎵 o 👏.",
    "Relajado, escribe frases cortas de 6 a 12 palabras reaccionando al punto exacto que explicó el locutor.",
    "Cálido y edificante, agradece por la reflexión o el mensaje que están compartiendo en el programa.",
    "Muy atento a los detalles, comenta en una frase breve qué fue lo que más le llegó de lo que acaban de hablar.",
    "Estilo rápido de celular: sin mayúsculas al inicio, directo al grano y muy natural, a veces cierra con un 🙌 o 👍."
]

# Lista de 45 oyentes (Nombre, Ciudad fija)
BASE_OYENTES = [
    ("Nico", "Coquimbo"), ("Javi Morales", "La Serena"), ("Matías R.", "Ovalle"),
    ("Cami", "La Serena"), ("Diego Araya", "Coquimbo"), ("Vale Ignacia", "Viña del Mar"),
    ("Seba", "Santiago"), ("Fran", "Coquimbo"), ("Coni Rojas", "La Serena"),
    ("Bastián", "Coquimbo"), ("Pame", "Coquimbo"), ("Lucas V.", "Antofagasta"),
    ("Cata", "La Serena"), ("Tomás Castillo", "Ovalle"), ("Nacho", "Coquimbo"),
    ("Maca", "Santiago"), ("Pipe", "La Serena"), ("Anto Díaz", "Coquimbo"),
    ("Gabo", "Concepción"), ("Dani", "La Serena"), ("Cris Olivares", "Coquimbo"),
    ("Fernanda", "Viña del Mar"), ("Pancho", "Ovalle"), ("Martina", "La Serena"),
    ("Leo Cortés", "Coquimbo"), ("Sofi", "Santiago"), ("Benja", "Coquimbo"),
    ("Caro Muñoz", "La Serena"), ("Maxi", "Copiapó"), ("Romi", "Coquimbo"),
    ("Joaquín", "La Serena"), ("Belen", "Ovalle"), ("Claudio P.", "Coquimbo"),
    ("Josefa", "Temuco"), ("Álvaro", "La Serena"), ("Trini", "Santiago"),
    ("Gonzalo", "Coquimbo"), ("Pau", "La Serena"), ("Vicente", "Coquimbo"),
    ("Maite", "Valparaíso"), ("Rodrigo Tapia", "La Serena"), ("Isi", "Coquimbo"),
    ("Fabián", "Ovalle"), ("Ale", "La Serena"), ("Cristóbal", "Coquimbo")
]

# Construimos el padrón completo asignándole a cada uno su estilo fijo
AUDITORES = [
    {
        "nombre": nombre,
        "ciudad": ciudad,
        "estilo": ESTILOS_ESCRITURA[i % len(ESTILOS_ESCRITURA)]
    }
    for i, (nombre, ciudad) in enumerate(BASE_OYENTES)
]

ultimos_auditores_locales = []

def obtener_recien_publicados_en_firebase():
    """Lee el muro de Firebase para no repetir a nadie que haya comentado recién."""
    try:
        r = requests.get(FIREBASE_CHAT_URL, timeout=10)
        if r.status_code == 200 and r.json():
            datos = r.json()
            if isinstance(datos, dict):
                # Tomamos los últimos 15 mensajes del muro
                ultimas_llaves = list(datos.keys())[-15:]
                nombres_recientes = [
                    datos[k].get("name", "") for k in ultimas_llaves if isinstance(datos[k], dict)
                ]
                return [n for n in nombres_recientes if n]
    except Exception as e:
        print(f"⚠️ No se pudo leer historial previo: {e}")
    return []

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
    """Elige entre 1 y 3 auditores evitando los últimos 15 del muro y de la sesión."""
    global ultimos_auditores_locales
    recientes_muro = obtener_recien_publicados_en_firebase()
    bloqueados = set(ultimos_auditores_locales[-15:] + recientes_muro)

    disponibles = [a for a in AUDITORES if a["nombre"] not in bloqueados]
    if len(disponibles) < 5:
        disponibles = AUDITORES

    cantidad = random.choices([1, 2, 3], weights=[40, 45, 15])[0]
    seleccionados = random.sample(disponibles, k=min(cantidad, len(disponibles)))

    for a in seleccionados:
        ultimos_auditores_locales.append(a["nombre"])

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
    1. Si es SOLO letra rimada de una canción, música o frases sueltas sin sentido, devuelve: {{"comentarios": []}}
    2. Si es un locutor o conductora hablando en un programa, genera comentarios cortos (entre 5 y 18 palabras) reaccionando específicamente a lo que dijo para estos auditores:
    {perfiles_txt}
    3. No repitas las mismas palabras de inicio entre un auditor y otro. Respeta el estilo de cada uno.

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
        "temperature": 0.85,
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
        "category": " ⚡ Saludo",
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
                        time.sleep(random.randint(14, 32))

        espera = random.randint(INTERVALO_ESCUCHA_MIN, INTERVALO_ESCUCHA_MAX)
        if (time.time() - inicio_bloque + espera) >= (DURACION_BLOQUE_MINUTOS * 60):
            break
        time.sleep(espera)
