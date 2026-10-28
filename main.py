
import os
import asyncio
import logging

import discord
from dotenv import load_dotenv
from google import genai
from google.genai import types

# ==================================================
# 🌸 SAKURA AI | CONFIGURACIÓN
# ==================================================

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

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
# 🔐 VALIDACIÓN DE CONFIGURACIÓN
# ==================================================

if not DISCORD_TOKEN:
    raise RuntimeError(
        "❌ Falta DISCORD_TOKEN en las variables de entorno."
    )

if not GEMINI_API_KEY:
    raise RuntimeError(
        "❌ Falta GEMINI_API_KEY en las variables de entorno."
    )

# Crear cliente de Gemini
ai = genai.Client(api_key=GEMINI_API_KEY)

# ==================================================
# 🤖 CREACIÓN DEL BOT DE DISCORD
# IMPORTANTE: ANTES DE CUALQUIER @bot.event
# ==================================================

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

bot = discord.Client(intents=intents)

# Memoria temporal de conversación por usuario
chat_sessions = {}

# Bloqueo de solicitudes simultáneas por usuario
user_locks = {}


def get_user_lock(user_id: int) -> asyncio.Lock:
    if user_id not in user_locks:
        user_locks[user_id] = asyncio.Lock()
    return user_locks[user_id]


# ==================================================
# 🌸 EVENTO: CONEXIÓN CON DISCORD
# ==================================================

@bot.event
async def on_ready():
    print("\n")
    print("╔══════════════════════════════════════════╗")
    print("║       🌸 SAKURA AI — EN LÍNEA 🌸        ║")
    print("╠══════════════════════════════════════════╣")
    print(f"║ 🤖 BOT: {str(bot.user)[:30]:<30} ║")
    print("║ ✅ CONEXIÓN CON DISCORD ESTABLECIDA     ║")
    print("║ 💬 COMANDO: .S pregunta                 ║")
    print("║ 🧠 MOTOR: GOOGLE GEMINI                 ║")
    print("╚══════════════════════════════════════════╝")
    print("\n")

    logger.info("Sakura AI está lista para recibir mensajes.")


# ==================================================
# 💬 EVENTO: MENSAJES Y COMANDO .S
# ==================================================

@bot.event
async def on_message(message: discord.Message):

    # Ignorar mensajes enviados por bots
    if message.author.bot:
        return

    content = message.content.strip()

    # Registro para diagnosticar mensajes recibidos
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
            "Escribe una pregunta después de `.S`.\n\n"
            "Ejemplo: `.S Explícame qué es Roblox Lua`",
            mention_author=False,
        )
        return

    if len(prompt) > 1500:
        await message.reply(
            "⚠️ Tu pregunta supera el límite de 1500 caracteres.",
            mention_author=False,
        )
        return

    async with get_user_lock(message.author.id):
        try:
            logger.info("🧠 Preparando consulta para Gemini...")

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
                    "🌸 No recibí texto de Gemini. Inténtalo otra vez.",
                    mention_author=False,
                )
                return

            logger.info("✅ Gemini respondió; enviando respuesta a Discord.")

            # Discord limita cada mensaje a 2000 caracteres.
            for i in range(0, len(answer), 1900):
                await message.reply(
                    answer[i:i + 1900],
                    mention_author=False,
                    allowed_mentions=discord.AllowedMentions.none(),
                )

            logger.info("✅ Respuesta enviada correctamente.")

        except Exception:
            logger.exception("❌ Error procesando la pregunta.")

            try:
                await message.reply(
                    "❌ No pude completar tu consulta.\n"
                    "Revisa los registros de FadeHost para identificar "
                    "el error de Discord o Gemini.",
                    mention_author=False,
                )
            except discord.HTTPException:
                logger.exception("No se pudo enviar el mensaje de error.")


# ==================================================
# 🚀 INICIO DEL BOT
# ==================================================

if __name__ == "__main__":
    print("🚀 Iniciando Sakura AI...")
    print("⏳ Conectando con Discord; espera la confirmación...")

    bot.run(DISCORD_TOKEN)
