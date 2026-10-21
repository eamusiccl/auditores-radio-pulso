import time
import random
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import requests

# ==========================================
# 1. CONFIGURACIÓN SEGURA (Desde Secrets de GitHub)
# ==========================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
STREAM_URL = os.getenv("STREAM_URL")
FIREBASE_CHAT_URL = os.getenv("FIREBASE_CHAT_URL")

DURACION_BLOQUE_MINUTOS = 50
INTERVALO_ESCUCHA_MIN = 190  # ~3.1 minutos
INTERVALO_ESCUCHA_MAX = 310  # ~5.1 minutos

# Probabilidad (de 0 a 100) de que alguien comente cuando SOLO suena música
PROBABILIDAD_COMENTAR_MUSICA = 30

# ==========================================
# 2. 45 AUDITORES CON CIUDAD FIJA Y 10 ESTILOS
# ==========================================
ESTILOS_ESCRITURA = [
    "Escribe todo en minúsculas, sin punto final, corto y directo. No usa emojis.",
    "Entusiasta y cercana, usa 1 o 2 emojis como 🔥, 🙌 o 😊. Muy buena onda.",
    "Participativo y reflexivo. Hace una pregunta corta o destaca una frase de lo que escucha.",
    "Juvenil y espontáneo. Comenta qué está haciendo (estudiando, trabajando o descansando) mientras escucha.",
    "Directo, usa expresiones chilenas suaves y naturales ('buenísimo el programa', 'tremendo tema', 'se pasaron').",
    "Alegre y expresivo, usa signos de exclamación y algún emoji como ✨, 🎵 o 👏.",
    "Relajado, escribe frases cortas de 6 a 12 palabras directo al grano.",
    "Cálido y edificante, manda bendiciones al equipo de la radio y agradece la compañía.",
    "Muy atento a los detalles, comenta qué fue lo que más le gustó de lo que acaba de sonar.",
    "Estilo rápido de celular: sin mayúsculas al inicio, muy natural, a veces cierra con un 🙌 o 👍."
]

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

AUDITORES = [
    {
        "nombre": nombre,
        "ciudad": ciudad,
        "estilo": ESTILOS_ESCRITURA[i % len(ESTILOS_ESCRITURA)]
    }
    for i, (nombre, ciudad) in enumerate(BASE_OYENTES)
]

ultimos_auditores_locales = []

def obtener_contexto_hora_chile():
    """Devuelve la hora actual en Chile y el momento del día para que saluden acorde."""
    ahora = datetime.now(ZoneInfo("America/Santiago"))
    hora = ahora.hour
    if 6 <= hora < 12:
        momento = "por la mañana (pueden decir buen día, tomando desayuno, activándose en la mañana)"
    elif 12 <= hora < 20:
        momento = "por la tarde (pueden decir buenas tardes, acompañando la tarde de trabajo o estudio)"
    else:
        momento = "por la noche (pueden decir buenas noches, descansando o cerrando el día con la radio)"
    return f"{ahora.strftime('%H:%M')} hrs ({momento})"

def leer_muro_firebase():
    """Obtiene los últimos mensajes del muro para no repetir nombres y poder dar likes."""
    try:
        r = requests.get(FIREBASE_CHAT_URL, timeout=10)
        if r.status_code == 200 and isinstance(r.json(), dict):
            return r.json()
    except Exception as e:
        print(f"⚠️ Error leyendo muro: {e}")
    return {}

def dar_likes_naturales(datos_muro):
    """Simula que los auditores le dan Like (+1) a 1 o 2 mensajes recientes del muro."""
    if not datos_muro or not FIREBASE_CHAT_URL:
        return
    try:
        ultimas_llaves = list(datos_muro.keys())[-8:]
        elegidas = random.sample(ultimas_llaves, k=min(random.randint(1, 2), len(ultimas_llaves)))
        url_base = FIREBASE_CHAT_URL.replace(".json", "")

        for llave in elegidas:
            msg_obj = datos_muro.get(llave, {})
            if isinstance(msg_obj, dict):
                likes_actuales = int(msg_obj.get("likes", 0))
                if likes_actuales < 9:  # Para no inflar un mensaje con demasiados likes
                    nuevos_likes = likes_actuales + 1
                    requests.patch(f"{url_base}/{llave}.json", json={"likes": nuevos_likes}, timeout=8)
    except Exception as e:
        print(f"⚠️ No se pudo actualizar likes: {e}")

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

def elegir_auditores_turno(datos_muro, max_cantidad=3):
    global ultimos_auditores_locales
    ultimas_llaves = list(datos_muro.keys())[-15:] if datos_muro else []
    recientes_muro = [
        datos_muro[k].get("name", "") for k in ultimas_llaves if isinstance(datos_muro.get(k), dict)
    ]
    bloqueados = set(ultimos_auditores_locales[-15:] + recientes_muro)

    disponibles = [a for a in AUDITORES if a["nombre"] not in bloqueados]
    if len(disponibles) < 5:
        disponibles = AUDITORES

    if max_cantidad == 1:
        cantidad = 1
    else:
        cantidad = random.choices([1, 2, 3], weights=[40, 45, 15])[0]

    seleccionados = random.sample(disponibles, k=min(cantidad, len(disponibles)))
    for a in seleccionados:
        ultimos_auditores_locales.append(a["nombre"])
    return seleccionados

def generar_comentarios_groq(texto_escuchado, datos_muro):
    if len(texto_escuchado.split()) < 4:
        return []

    hora_chile = obtener_contexto_hora_chile()
    permitir_musica = random.randint(1, 100) <= PROBABILIDAD_COMENTAR_MUSICA
    auditores_turno = elegir_auditores_turno(datos_muro, max_cantidad=3)
    perfiles_txt = "\n".join([f"- {a['nombre']} (de {a['ciudad']}): {a['estilo']}" for a in auditores_turno])

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

    regla_musica = (
        f"Si detectas que está sonando UNA CANCIÓN o MÚSICA, elige SOLO A 1 AUDITOR de la lista ({auditores_turno[0]['nombre']}) "
        "para que deje un saludo natural comentando qué buena está la música, qué linda canción suena o cómo lo acompaña Radio Pulso."
        if permitir_musica else
        "Si detectas que es SOLO letra de canción o música sin un locutor hablando en un programa, devuelve exactamente: {\"comentarios\": []}"
    )

    prompt_usuario = f"""
    Hora actual en Chile: {hora_chile}.
    Esto se escuchó en vivo en Radio Pulso durante los últimos 20 segundos:
    "{texto_escuchado}"

    INSTRUCCIONES DE REALISMO:
    1. Si hay un locutor o conductora hablando en un programa, haz que los auditores de la lista comenten específicamente sobre lo que acaba de decir.
    2. {regla_musica}
    3. Cada comentario debe tener entre 6 y 18 palabras.
    4. Si mencionan el momento del día, debe coincidir con la hora actual en Chile ({hora_chile}).
    5. Respeta al 100% el estilo de escritura de cada auditor:
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
        "likes": random.choices([0, 1], weights=[75, 25])[0],
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

            datos_muro = leer_muro_firebase()
            comentarios = generar_comentarios_groq(texto_radio, datos_muro)

            if comentarios:
                # Además de comentar, simulan dar like a mensajes anteriores del muro
                dar_likes_naturales(datos_muro)

            for i, item in enumerate(comentarios):
                nombre_auditor = item.get("name", "Nico")
                texto_comentario = item.get("message", "")
                ciudad_auditor = mapa_ciudades.get(nombre_auditor, "Coquimbo")

                if texto_comentario:
                    publicar_en_muro_pulso(nombre_auditor, texto_comentario, ciudad_auditor)
                    if i < len(comentarios) - 1:
                        time.sleep(random.randint(15, 35))

        espera = random.randint(INTERVALO_ESCUCHA_MIN, INTERVALO_ESCUCHA_MAX)
        if (time.time() - inicio_bloque + espera) >= (DURACION_BLOQUE_MINUTOS * 60):
            break
        time.sleep(espera)
