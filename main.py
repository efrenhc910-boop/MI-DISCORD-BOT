import os
import asyncio
import logging
import random

import discord
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# ============================================================
# 🌸 SAKURA AI — CONFIGURACIÓN
# ============================================================

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

# Pega aquí la URL pública y directa de tu imagen grande.
# Déjala vacía si no quieres mostrar ninguna imagen.
# No es un thumbnail: se utiliza embed.set_image().
EMBED_IMAGE_URL = "https://cdn.discordapp.com/attachments/1563710649429794816/1564143687087169536/Screenshot_20261024-1643262.jpg?ex=6ae37d93&is=6ae22c13&hm=24eebc0c2230088784a5e4c4c4c42f9e32131cac0ae2fe32b0217f85669d2eb5&"

# Número máximo de intentos, contando el primero.
MAX_RETRIES = 3

# Tiempo máximo de espera por cada consulta.
REQUEST_TIMEOUT = 45

# Colores del embed Sakura.
SAKURA_COLOR = discord.Color.from_rgb(255, 80, 170)
ERROR_COLOR = discord.Color.from_rgb(235, 65, 85)

# ============================================================
# 📝 REGISTROS
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("SAKURA_AI")

# ============================================================
# 🧠 INSTRUCCIONES DE SAKURA AI
# ============================================================

SYSTEM_INSTRUCTION = """
Eres Sakura AI, la asistente de inteligencia artificial
del servidor de Discord Sakura Hub.

Responde principalmente en español.
Sé amable, clara, útil y respetuosa.
Ayuda con programación, Roblox Lua, Discord,
tecnología y preguntas generales.

Utiliza Markdown y bloques de código cuando sean útiles.
Cuando compartas código, procura que sea completo y funcional.
No inventes información ni afirmes haber ejecutado acciones
que realmente no realizaste.
Adapta la extensión de la respuesta a la pregunta.
"""

if not DISCORD_TOKEN:
    raise RuntimeError(
        "Falta el token de Discord en las variables de entorno."
    )

if not GEMINI_API_KEY:
    raise RuntimeError(
        "Falta la clave de API de Gemini en las variables de entorno."
    )

# ============================================================
# 🤖 CLIENTE DE GEMINI
# ============================================================

ai = genai.Client(api_key=GEMINI_API_KEY)

# ============================================================
# 💬 CONFIGURACIÓN DE DISCORD
# ============================================================

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

bot = discord.Client(intents=intents)

# Historial independiente por usuario.
chat_sessions = {}

# Evita que dos consultas del mismo usuario se mezclen.
user_locks = {}


def get_user_lock(user_id: int) -> asyncio.Lock:
    if user_id not in user_locks:
        user_locks[user_id] = asyncio.Lock()
    return user_locks[user_id]


# ============================================================
# 🔁 DETECTAR ERRORES TEMPORALES
# ============================================================

def is_temporary_error(error: Exception) -> bool:
    """
    Detecta errores que podrían resolverse al volver a intentar.
    No reintenta automáticamente errores como un modelo inexistente
    o una clave de API inválida.
    """

    error_text = str(error).lower()

    status_code = getattr(error, "status_code", None)

    if status_code is None:
        status_code = getattr(error, "code", None)

    try:
        status_code = int(status_code)
    except (TypeError, ValueError):
        status_code = None

    temporary_codes = {408, 429, 500, 502, 503, 504}

    if status_code in temporary_codes:
        return True

    temporary_markers = (
        "503",
        "429",
        "500",
        "502",
        "504",
        "unavailable",
        "resource_exhausted",
        "high demand",
        "deadline_exceeded",
        "internal server error",
        "temporarily unavailable",
        "too many requests",
        "service unavailable",
    )

    return any(marker in error_text for marker in temporary_markers)


# ============================================================
# 🧠 CONSULTAR GEMINI CON REINTENTOS
# ============================================================

async def ask_gemini(chat, prompt: str):
    """
    Hace hasta MAX_RETRIES intentos.
    Espera progresivamente más tiempo entre intentos.
    """

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "🧠 Consultando Gemini | Modelo: %s | Intento %s/%s",
                GEMINI_MODEL,
                attempt,
                MAX_RETRIES,
            )

            response = await asyncio.wait_for(
                asyncio.to_thread(chat.send_message, prompt),
                timeout=REQUEST_TIMEOUT,
            )

            answer = (response.text or "").strip()

            if not answer:
                raise RuntimeError("Sakura Bot devolvió una respuesta vacía.")

            logger.info("✅ Gemini respondió correctamente.")
            return answer

        except asyncio.TimeoutError as error:
            logger.warning(
                "⏱️ Tiempo agotado en el intento %s/%s.",
                attempt,
                MAX_RETRIES,
            )

            if attempt >= MAX_RETRIES:
                raise TimeoutError(
                    "Sakura Bot superó el tiempo máximo de espera."
                ) from error

            retryable = True

        except Exception as error:
            if not is_temporary_error(error):
                logger.exception(
                    "❌ Error no temporal de Gemini. No se reintentará."
                )
                raise

            logger.warning(
                "⚠️ Error temporal de Gemini en el intento %s/%s: %s",
                attempt,
                MAX_RETRIES,
                error,
            )

            if attempt >= MAX_RETRIES:
                raise

            retryable = True

        if retryable:
            # Esperas aproximadas: 2, 4 segundos, con una pequeña
            # variación aleatoria para evitar reintentos sincronizados.
            delay = min(2 ** attempt, 10) + random.uniform(0, 0.5)

            logger.info(
                "🔁 Nuevo intento en %.1f segundos...",
                delay,
            )

            await asyncio.sleep(delay)

    raise RuntimeError("Sakura Bot no pudo completar la solicitud.")


# ============================================================
# 🎨 CREAR EMBEDS
# ============================================================

def create_embed(
    description: str,
    title: str = "🌸 Sakura AI",
    color: discord.Color = SAKURA_COLOR,
    include_image: bool = True,
) -> discord.Embed:

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=discord.utils.utcnow(),
    )

    # Imagen GRANDE del embed, no thumbnail.
    # La URL debe ser pública y apuntar directamente a la imagen.
    if include_image and EMBED_IMAGE_URL.strip():
        embed.set_image(url=EMBED_IMAGE_URL.strip())

    embed.set_footer(
        text="SAKURA AI • Sakura Hub",
        icon_url=(
            bot.user.display_avatar.url
            if bot.user
            else discord.Embed.Empty
        ),
    )

    return embed


async def send_embed_response(
    message: discord.Message,
    answer: str,
) -> None:
    """
    Divide respuestas largas en varios embeds para respetar
    los límites de Discord.
    """

    # Límite conservador para la descripción de cada embed.
    chunks = [
        answer[i:i + 3900]
        for i in range(0, len(answer), 3900)
    ]

    total = len(chunks)

    for index, chunk in enumerate(chunks):
        if total == 1:
            title = "🌸 Sakura AI"
        else:
            title = f"🌸 Sakura AI • Parte {index + 1}/{total}"

        embed = create_embed(
            description=chunk,
            title=title,
            include_image=(index == 0),
        )

        await message.reply(
            embed=embed,
            mention_author=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )


async def send_error_embed(
    message: discord.Message,
    description: str,
) -> None:
    embed = create_embed(
        title="⚠️ Sakura AI",
        description=description,
        color=ERROR_COLOR,
        include_image=False,
    )

    await message.reply(
        embed=embed,
        mention_author=False,
        allowed_mentions=discord.AllowedMentions.none(),
    )


# ============================================================
# 🌸 CUANDO EL BOT SE CONECTA
# ============================================================

@bot.event
async def on_ready():
    logger.info("╔══════════════════════════════════════════╗")
    logger.info("║         🌸 SAKURA AI EN LÍNEA 🌸        ║")
    logger.info("╠══════════════════════════════════════════╣")
    logger.info("║ Bot: %s", bot.user)
    logger.info("║ Modelo: %s", GEMINI_MODEL)
    logger.info("║ Comando: .S pregunta")
    logger.info("║ Reintentos: %s", MAX_RETRIES)
    logger.info("╚══════════════════════════════════════════╝")

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name=".S | Sakura AI 🌸",
        ),
        status=discord.Status.online,
    )


# ============================================================
# 💬 PROCESAR MENSAJES
# ============================================================

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    content = message.content.strip()

    logger.info(
        "📩 Mensaje recibido | Canal: %s | Usuario: %s",
        getattr(message.channel, "name", "privado"),
        message.author,
    )

    # Solo responde a .S y .S seguido de una pregunta.
    if not (
        content.lower() == ".s"
        or content.lower().startswith(".s ")
    ):
        return

    prompt = content[2:].strip()

    logger.info("🌸 Comando .S detectado.")

    if not prompt:
        embed = create_embed(
            title="🌸 ¡Hola! Soy Sakura AI",
            description=(
                "Estoy lista para ayudarte. ✨\n\n"
                "**Escribe tu pregunta después de `.S`.**\n\n"
                "Por ejemplo:\n"
                "```text\n"
                ".S Explícame cómo funcionan los scripts de Roblox Lua\n"
                "```\n"
                "También puedo ayudarte con Discord, programación "
                "y tecnología."
            ),
        )

        await message.reply(
            embed=embed,
            mention_author=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        return

    if len(prompt) > 1500:
        await send_error_embed(
            message,
            "Tu pregunta supera el límite de **1500 caracteres**. "
            "Divídela en preguntas más pequeñas e inténtalo de nuevo.",
        )
        return

    async with get_user_lock(message.author.id):
        try:
            chat = chat_sessions.get(message.author.id)

            if chat is None:
                chat = ai.chats.create(
                    model=GEMINI_MODEL,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        max_output_tokens=1200,
                    ),
                )
                chat_sessions[message.author.id] = chat

            async with message.channel.typing():
                answer = await ask_gemini(chat, prompt)

            await send_embed_response(message, answer)

            logger.info("✅ Respuesta enviada a Discord.")

        except Exception as error:
            logger.exception("❌ Error procesando la pregunta.")

            error_text = str(error).lower()

            if (
                isinstance(error, TimeoutError)
                or "timeout" in error_text
                or "timed out" in error_text
            ):
                user_message = (
                    "Sakura Bot está tardando demasiado en responder. "
                    "Espera unos segundos y vuelve a intentarlo. ⏳"
                )

            elif (
                "404" in error_text
                or "not_found" in error_text
                or "not found" in error_text
            ):
                user_message = (
                    "El modelo configurado no está disponible en este momento. "
                    "Inténtalo más tarde. 🔧"
                )

            elif (
                "429" in error_text
                or "resource_exhausted" in error_text
                or "quota" in error_text
            ):
                user_message = (
                    "Se ha alcanzado el límite de solicitudes. "
                    "Espera un poco antes de volver a intentarlo. ⏳"
                )

            elif (
                "401" in error_text
                or "403" in error_text
                or "api key" in error_text
                or "permission" in error_text
            ):
                user_message = (
                    "Hubo un problema de autenticación con el servicio. "
                    "Por favor, avísale a un administrador. 🔑"
                )

            elif is_temporary_error(error):
                user_message = (
                    "Sakura Bot sigue experimentando problemas temporales. "
                    "Prueba de nuevo en un rato. 🌸"
                )

            else:
                user_message = (
                    "Ocurrió un error inesperado al procesar tu pregunta. "
                    "Inténtalo de nuevo más tarde. ⚠️"
                )

            try:
                await send_error_embed(message, user_message)
            except discord.HTTPException:
                logger.exception(
                    "No se pudo enviar el embed de error a Discord."
                )


# ============================================================
# 🚀 INICIAR SAKURA AI
# ============================================================

if __name__ == "__main__":
    print("🌸 Iniciando Sakura AI...")
    print(f"🧠 Modelo configurado: {GEMINI_MODEL}")
    print(f"🔁 Reintentos máximos: {MAX_RETRIES}")
    print("⏳ Conectando con Discord...")

    bot.run(DISCORD_TOKEN)
