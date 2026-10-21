import subprocess
import time
import random
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import requests

# ==========================================
# 1. CONFIGURACIÓN Y AUTO-CORRECCIÓN DE URL
# ==========================================
GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()
STREAM_URL = (os.getenv("STREAM_URL") or "").strip()
FIREBASE_CHAT_URL = (os.getenv("FIREBASE_CHAT_URL") or "").strip()

# Asegurar que la URL apunte exactamente a /muro_pulso.json
if FIREBASE_CHAT_URL:
    FIREBASE_CHAT_URL = FIREBASE_CHAT_URL.rstrip("/")
    if not FIREBASE_CHAT_URL.endswith(".json"):
        if "muro_pulso" not in FIREBASE_CHAT_URL:
            FIREBASE_CHAT_URL += "/muro_pulso.json"
        else:
            FIREBASE_CHAT_URL += ".json"

DURACION_BLOQUE_MINUTOS = 50
INTERVALO_ESCUCHA_MIN = 180  # 3 minutos
INTERVALO_ESCUCHA_MAX = 280  # 4.5 minutos
PROBABILIDAD_COMENTAR_MUSICA = 20

# ==========================================
# 2. 45 AUDITORES CON ESTILO JUVENIL REAL
# ==========================================
ESTILOS_ESCRITURA = [
    "Escribe todo en minúsculas, abreviando como en WhatsApp ('q', 'pa q', 'xq', 'tkm'), sin punto final y muy natural.",
    "Entusiasta y juvenil, usa expresiones como 'wena wenaaa', 'cabros', 'bacán' y 1 o 2 emojis como 🔥, 🙌 o 😎.",
    "Participativo y reflexivo. Destaca el mensaje de lo que suena o hace una pregunta corta al equipo de Pulso.",
    "Espontáneo, cuenta qué está haciendo (estudiando, en la pega, viajando) mientras escucha Radio Pulso.",
    "Directo y cercano ('tremendo temazo', 'se pasaron con la música hoy', 'bendiciones a toda la comunidad de pulso').",
    "Alegre y expresiva, usa algún emoji como ❤️‍🔥, ✨, 🎵 o 🙌 y anima a otros a compartir la radio.",
    "Pide un tema musical cristiano juvenil (como Redimi2, Barak, Un Corazón, Alex Zurdo, Averly Morillo o Funky) o saluda.",
    "Cálido y edificante, agradece a Dios por la radio o deja un motivo breve de oración por su semana.",
    "Estilo rápido de celular: frases de 8 a 16 palabras, sin mayúsculas al inicio, muy auténtico.",
    "Comenta la energía de la radio y manda saludos desde su ciudad a todos los que están conectados."
]

BASE_OYENTES = [
    ("Nico", "Coquimbo"), ("Javi Morales", "La Serena"), ("Matías R.", "Ovalle"),
    ("Cami", "La Serena"), ("Diego Araya", "Coquimbo"), ("Vale Ignacia", "Viña del Mar"),
    ("Seba", "Santiago"), ("Fran", "Coquimbo"), ("Coni Rojas", "La Serena"),
    ("Bastián", "Chillán"), ("Pame", "Coquimbo"), ("Lucas V.", "Antofagasta"),
    ("Cata", "La Serena"), ("Tomás", "Los Ángeles"), ("Nacho", "Coquimbo"),
    ("Maca", "Santiago"), ("Pipe", "La Serena"), ("Anto Díaz", "Coquimbo"),
    ("Gabo", "Concepción"), ("Dani", "La Serena"), ("Cris Olivares", "Coquimbo"),
    ("Fernanda", "Viña del Mar"), ("Pancho", "Ovalle"), ("Martina", "La Serena"),
    ("Leo Cortés", "Coquimbo"), ("Sofi", "Santiago"), ("Benja", "Río Hurtado"),
    ("Caro Muñoz", "La Serena"), ("Maxi", "Copiapó"), ("Romi", "Coquimbo"),
    ("Joaquín", "La Serena"), ("Belén", "Ovalle"), ("Claudio P.", "Coquimbo"),
    ("Josefa", "Temuco"), ("Álvaro", "La Serena"), ("Trini", "Santiago"),
    ("Gonzalo", "Coquimbo"), ("Pau", "La Serena"), ("Vicente", "Coquimbo"),
    ("Maite", "Valparaíso"), ("Rodrigo", "La Serena"), ("Isi", "Coquimbo"),
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

def log(mensaje):
    print(mensaje, flush=True)

def obtener_contexto_hora_chile():
    ahora = datetime.now(ZoneInfo("America/Santiago"))
    hora = ahora.hour
    if 6 <= hora < 12:
        momento = "por la mañana (buen día, activándose)"
    elif 12 <= hora < 20:
        momento = "por la tarde (buenas tardes, acompañando el estudio o la pega)"
    else:
        momento = "por la noche (buenas noches, descansando o cerrando el día)"
    return f"{ahora.strftime('%H:%M')} hrs ({momento})"

def leer_muro_firebase():
    try:
        r = requests.get(FIREBASE_CHAT_URL, timeout=10)
        if r.status_code == 200 and isinstance(r.json(), dict):
            return r.json()
    except Exception as e:
        log(f"⚠️ Error leyendo muro: {e}")
    return {}

def capturar_audio(url_stream, archivo_salida="muestra_pulso.mp3", segundos=20):
    if os.path.exists(archivo_salida):
        os.remove(archivo_salida)
    try:
        comando = [
            "ffmpeg", "-y",
            "-user_agent", "Mozilla/5.0",
            "-i", url_stream,
            "-t", str(segundos),
            "-acodec", "libmp3lame",
            "-ab", "64k",
            "-ar", "16000",
            archivo_salida
        ]
        subprocess.run(comando, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=35)
        if os.path.exists(archivo_salida) and os.path.getsize(archivo_salida) > 5000:
            return True
    except Exception:
        pass

    try:
        inicio = time.time()
        headers = {"User-Agent": "Mozilla/5.0"}
        with requests.get(url_stream, headers=headers, stream=True, timeout=15) as r:
            with open(archivo_salida, "wb") as f:
                for chunk in r.iter_content(chunk_size=4096):
                    if chunk:
                        f.write(chunk)
                    if time.time() - inicio >= segundos:
                        break
        return os.path.exists(archivo_salida) and os.path.getsize(archivo_salida) > 5000
    except Exception as e:
        log(f"⚠️ Error capturando stream: {e}")
        return False

def transcribir_con_groq(archivo_audio):
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
        log(f"⚠️ Error al transcribir: {e}")
    return ""

def elegir_auditores_turno(datos_muro, cantidad=1):
    global ultimos_auditores_locales
    ultimas_llaves = list(datos_muro.keys())[-15:] if datos_muro else []
    recientes_muro = [
        datos_muro[k].get("name", "") for k in ultimas_llaves if isinstance(datos_muro.get(k), dict)
    ]
    bloqueados = set(ultimos_auditores_locales[-15:] + recientes_muro)

    disponibles = [a for a in AUDITORES if a["nombre"] not in bloqueados]
    if len(disponibles) < 5:
        disponibles = AUDITORES

    seleccionados = random.sample(disponibles, k=min(cantidad, len(disponibles)))
    for a in seleccionados:
        ultimos_auditores_locales.append(a["nombre"])
    return seleccionados

def generar_comentarios_groq(texto_escuchado, datos_muro, forzar_comentario=False):
    hora_chile = obtener_contexto_hora_chile()
    palabras = len(texto_escuchado.split())

    if not forzar_comentario and palabras < 12:
        if random.randint(1, 100) > PROBABILIDAD_COMENTAR_MUSICA:
            log("🎵 Sonando música. Los auditores escuchan en silencio.")
            return []

    cantidad = 1 if palabras < 15 else random.choices([1, 2], weights=[65, 35])[0]
    auditores_turno = elegir_auditores_turno(datos_muro, cantidad=cantidad)
    perfiles_txt = "\n".join([f"- {a['nombre']} (de {a['ciudad']}): {a['estilo']}" for a in auditores_turno])

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

    contexto_audio = (
        f'En la radio se escuchó: "{texto_escuchado}"'
        if palabras >= 5 else
        "Está sonando música cristiana juvenil en vivo en Radio Pulso."
    )

    prompt_usuario = f"""
    Hora actual en Chile: {hora_chile}.
    {contexto_audio}

    Genera mensajes para el muro de Radio Pulso simulando ser estos auditores reales (respeta estrictamente la longitud máxima de 300 caracteres por mensaje):
    {perfiles_txt}

    REGLAS:
    1. Si hay un locutor hablando, comenta sobre eso. Si hay música, manda un saludo o pide un tema.
    2. Tono juvenil chileno ('q', 'pa q', 'bacán', 'wena'). Longitud entre 8 y 25 palabras (muy por debajo del límite).
    3. Categoría exacta: " ⚡ Saludo", " 🔥 Pido Tema" o " 🙏 Oración".

    Responde SOLO en JSON con este formato exacto:
    {{
      "comentarios": [
        {{"name": "Nombre", "category": " ⚡ Saludo", "message": "texto aquí"}}
      ]
    }}
    """

    payload = {
        "model": "qwen/qwen3.8-27b",
        "messages": [
            {"role": "system", "content": "Coordinador de auditores en vivo de Radio Pulso. Responde siempre en JSON válido."},
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
        else:
            log(f"⚠️ Error IA ({r.status_code}): {r.text[:150]}")
    except Exception as e:
        log(f"⚠️ Error en IA: {e}")
    return []

def publicar_en_muro_pulso(nombre, mensaje, ciudad, categoria=" ⚡ Saludo"):
    # Cumple exactamente con las validaciones de tus reglas:
    # hasChildren(['name', 'message', 'category', 'createdAt', 'likes', 'pinned'])
    # pinned: false, likes: 0, longitudes de texto válidas.
    datos_mensaje = {
        "category": categoria,
        "city": ciudad,
        "createdAt": int(time.time() * 1000),
        "likes": 0,
        "message": mensaje,
        "name": nombre,
        "pinned": False
    }
    try:
        r = requests.post(FIREBASE_CHAT_URL, json=datos_mensaje, timeout=10)
        if r.status_code in [200, 201]:
            log(f"✅ PUBLICADO -> [{nombre} • {ciudad} | {categoria}]: {mensaje}")
        else:
            log(f"❌ Error Firebase ({r.status_code}): {r.text}")
    except Exception as e:
        log(f"❌ Error de red al publicar: {e}")

if __name__ == "__main__":
    log("🚀 Iniciando Auditores IA de Radio Pulso...")
    log(f"🔗 Destino Firebase: {FIREBASE_CHAT_URL}")
    inicio_bloque = time.time()
    archivo_temp = "muestra_pulso.mp3"
    mapa_ciudades = {a["nombre"]: a["ciudad"] for a in AUDITORES}
    primer_turno = True

    while (time.time() - inicio_bloque) < (DURACION_BLOQUE_MINUTOS * 60):
        log("\n🎧 Escuchando 20 segundos de Radio Pulso...")
        if capturar_audio(STREAM_URL, archivo_temp, segundos=20):
            texto_radio = transcribir_con_groq(archivo_temp)
            log(f"📝 Transcripción: '{texto_radio}'")
        else:
            texto_radio = ""
            log("⚠️ Usando contexto musical en vivo.")

        datos_muro = leer_muro_firebase()
        comentarios = generar_comentarios_groq(texto_radio, datos_muro, forzar_comentario=primer_turno)
        primer_turno = False

        for i, item in enumerate(comentarios):
            nombre_auditor = item.get("name", "Nico")
            texto_comentario = item.get("message", "")
            categoria = item.get("category", " ⚡ Saludo")
            ciudad_auditor = mapa_ciudades.get(nombre_auditor, "Coquimbo")

            if texto_comentario:
                publicar_en_muro_pulso(nombre_auditor, texto_comentario, ciudad_auditor, categoria)
                if i < len(comentarios) - 1:
                    time.sleep(random.randint(15, 30))

        espera = random.randint(INTERVALO_ESCUCHA_MIN, INTERVALO_ESCUCHA_MAX)
        if (time.time() - inicio_bloque + espera) >= (DURACION_BLOQUE_MINUTOS * 60):
            break
        log(f"💤 Próxima escucha en {espera // 60} min {espera % 60} seg...")
        time.sleep(espera)
