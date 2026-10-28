
import os
import asyncio
import logging

import discord
from dotenv import load_dotenv
from google import genai
from google.genai import types

# ==================================================
# 🌸 SAKURA AI - CONFIGURACIÓN
# ==================================================

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Si FadeHost define GEMINI_MODEL, ese valor tiene prioridad.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("SAKURA_AI")

SYSTEM_INSTRUCTION = """
Eres Sakura AI, la asistente de inteligencia artificial
del servidor de Discord Sakura Hub.

Responde principalmente en español.
Sé amable, clara, útil y respetuosa.
Ayuda con programación, Roblox Lua, Discord,
tecnología y preguntas generales.

Usa Markdown y bloques de código cuando sean útiles.
No inventes información ni afirmes haber ejecutado
acciones que no realizaste.
"""

# ==================================================
# 🔐 VALIDAR CONFIGURACIÓN
# ==================================================

if not DISCORD_TOKEN:
    raise RuntimeError(
        "Falta DISCORD_TOKEN en las variables de entorno de FadeHost."
    )

if not GEMINI_API_KEY:
    raise RuntimeError(
        "Falta GEMINI_API_KEY en las variables de entorno de FadeHost."
    )

# ==================================================
# 🧠 CLIENTE DE GEMINI
# ==================================================

ai = genai.Client(api_key=GEMINI_API_KEY)

# ==================================================
# 🤖 CREACIÓN DEL BOT DE DISCORD
# Debe ir antes de cualquier @bot.event
# ==================================================

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

bot = discord.Client(intents=intents)

# Memoria temporal de conversación por usuario
chat_sessions = {}

# Evitar consultas simultáneas del mismo usuario
user_locks = {}


def get_user_lock(user_id: int) -> asyncio.Lock:
    if user_id not in user_locks:
        user_locks[user_id] = asyncio.Lock()
    return user_locks[user_id]


# ==================================================
# 🌸 EVENTO DE CONEXIÓN
# ==================================================

@bot.event
async def on_ready():
    print("\n")
    print("╔══════════════════════════════════════════╗")
    print("║        🌸 SAKURA AI EN LÍNEA 🌸         ║")
    print("╠══════════════════════════════════════════╣")
    print(f"║ Bot: {str(bot.user)[:32]:<32} ║")
    print("║ Estado: CONECTADO A DISCORD              ║")
    print("║ Comando: .S pregunta                     ║")
    print(f"║ Modelo: {GEMINI_MODEL[:32]:<32} ║")
    print("╚══════════════════════════════════════════╝")
    print("\n")

    logger.info("Sakura AI está lista para recibir mensajes.")


# ==================================================
# 💬 EVENTO DE MENSAJES Y COMANDO .S
# ==================================================

@bot.event
async def on_message(message: discord.Message):
    # Ignorar mensajes de bots
    if message.author.bot:
        return

    content = message.content.strip()

    logger.info(
        "📩 Mensaje recibido | Canal: %s | Usuario: %s",
        getattr(message.channel, "name", "mensaje privado"),
        message.author,
    )

    # Aceptar .S, .s y .S seguido de una pregunta
    if content.lower() != ".s" and not content.lower().startswith(".s "):
        return

    prompt = content[2:].strip()

    logger.info("🌸 Comando .S detectado")

    if not prompt:
        await message.reply(
            "🌸 ¡Hola! Soy Sakura AI.\n"
            "Escribe tu pregunta después de `.S`.\n"
            "Ejemplo: `.S Explícame qué es Roblox Lua`",
            mention_author=False,
        )
        return

    if len(prompt) > 1500:
        await message.reply(
            "⚠️ Tu pregunta no puede superar los 1500 caracteres.",
            mention_author=False,
        )
        return

    async with get_user_lock(message.author.id):
        try:
            logger.info(
                "🧠 Consultando Gemini con el modelo %s...",
                GEMINI_MODEL,
            )

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
                response = await asyncio.to_thread(
                    chat.send_message,
                    prompt,
                )

            answer = (response.text or "").strip()

            if not answer:
                logger.warning("Gemini devolvió una respuesta vacía.")
                await message.reply(
                    "🌸 Gemini no devolvió texto. Inténtalo de nuevo.",
                    mention_author=False,
                )
                return

            logger.info("✅ Gemini respondió correctamente.")

            # Dividir respuestas para respetar el límite de Discord
            for i in range(0, len(answer), 1900):
                await message.reply(
                    answer[i:i + 1900],
                    mention_author=False,
                    allowed_mentions=discord.AllowedMentions.none(),
                )

            logger.info("✅ Respuesta enviada a Discord.")

        except Exception as error:
            logger.exception("❌ Error procesando la pregunta.")

            # Mensajes sencillos para los errores más habituales
            error_text = str(error)
            lower_error = error_text.lower()

            if "404" in error_text or "not_found" in lower_error:
                user_message = (
                    "⚠️ El modelo de Gemini configurado no está disponible. "
                    "Revisa GEMINI_MODEL en FadeHost."
                )
            elif "429" in error_text or "resource_exhausted" in lower_error:
                user_message = (
                    "⏳ Gemini ha alcanzado temporalmente un límite de uso. "
                    "Espera un poco y vuelve a intentarlo."
                )
            elif "401" in error_text or "403" in error_text:
                user_message = (
                    "🔑 Gemini rechazó la solicitud. "
                    "Revisa la clave y los permisos de la API."
                )
            else:
                user_message = (
                    "❌ No pude completar tu pregunta. "
                    "Revisa los registros de FadeHost."
                )

            try:
                await message.reply(
                    user_message,
                    mention_author=False,
                )
            except discord.HTTPException:
                logger.exception("No se pudo enviar el mensaje de error.")


# ==================================================
# 🚀 INICIAR SAKURA AI
# ==================================================

if __name__ == "__main__":
    print("🚀 Iniciando Sakura AI...")
    print(f"🧠 Modelo configurado: {GEMINI_MODEL}")
    print("⏳ Conectando con Discord...")

    bot.run(DISCORD_TOKEN)
