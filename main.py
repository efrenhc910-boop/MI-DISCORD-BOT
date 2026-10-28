
import os
import asyncio
import logging

import discord
from dotenv import load_dotenv
from google import genai
from google.genai import types

# ============================================
# 🌸 SAKURA AI - CONFIGURACIÓN PRINCIPAL
# ============================================

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Configurar registros para diagnosticar errores
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("SakuraAI")

# Instrucciones de personalidad de Sakura AI
SYSTEM_INSTRUCTION = """
Eres Sakura AI, la asistente de inteligencia artificial
del servidor de Discord Sakura Hub.

Responde principalmente en español.
Sé amable, clara, útil y respetuosa.
Ayuda con programación, Roblox Lua, Discord,
tecnología y preguntas generales.

Utiliza Markdown y bloques de código cuando ayuden.
No inventes información si no conoces una respuesta.
No afirmes que has ejecutado acciones que no realizaste.
"""

# ============================================
# 🔐 VALIDAR LAS VARIABLES DE ENTORNO
# ============================================

if not DISCORD_TOKEN:
    raise RuntimeError(
        "Falta DISCORD_TOKEN en las variables de entorno."
    )

if not GEMINI_API_KEY:
    raise RuntimeError(
        "Falta GEMINI_API_KEY en las variables de entorno."
    )

# Crear el cliente de Gemini
ai = genai.Client(api_key=GEMINI_API_KEY)

# ============================================
# 🤖 CREAR EL BOT DE DISCORD
# IMPORTANTE: ESTO VA ANTES DE @bot.event
# ============================================

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

bot = discord.Client(intents=intents)

# Memoria temporal de conversación por usuario
chat_sessions = {}

# Bloqueos para evitar peticiones simultáneas
user_locks = {}


def get_user_lock(user_id: int) -> asyncio.Lock:
    """Obtiene el bloqueo de un usuario."""
    if user_id not in user_locks:
        user_locks[user_id] = asyncio.Lock()

    return user_locks[user_id]


# ============================================
# 🌸 EVENTO: BOT CONECTADO
# ============================================

@bot.event
async def on_ready():
    logger.info("===================================")
    logger.info("🌸 SAKURA AI ESTÁ EN LÍNEA")
    logger.info("Bot: %s", bot.user)
    logger.info("ID: %s", bot.user.id if bot.user else "N/A")
    logger.info("Modelo Gemini: %s", GEMINI_MODEL)
    logger.info("Comando: .S pregunta")
    logger.info("===================================")


# ============================================
# 💬 EVENTO: RECIBIR Y RESPONDER A .S
# ============================================

@bot.event
async def on_message(message: discord.Message):
    # Ignorar mensajes de bots
    if message.author.bot:
        return

    content = message.content.strip()

    # Aceptar .S, .s, .Sakura no: solo el prefijo .S
    # seguido de un espacio o sin texto
    if content.lower() != ".s" and not content.lower().startswith(".s "):
        return

    # Obtener la pregunta después de .S
    prompt = content[2:].strip()

    if not prompt:
        await message.reply(
            "🌸 ¡Hola! Soy Sakura AI.\n"
            "Escribe tu pregunta después de `.S`.\n\n"
            "Ejemplo: `.S Explícame qué es Roblox Lua`",
            mention_author=False,
        )
        return

    if len(prompt) > 1500:
        await message.reply(
            "⚠️ Tu pregunta es demasiado larga. "
            "El límite es de 1500 caracteres.",
            mention_author=False,
        )
        return

    async with get_user_lock(message.author.id):
        try:
            # Recuperar o crear la conversación del usuario
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

            # Mostrar que Sakura está escribiendo
            async with message.channel.typing():
                response = await asyncio.to_thread(
                    chat.send_message,
                    prompt,
                )

            answer = (response.text or "").strip()

            if not answer:
                await message.reply(
                    "🌸 Gemini no devolvió texto. "
                    "Prueba otra vez con una pregunta diferente.",
                    mention_author=False,
                )
                return

            # Dividir las respuestas para respetar el límite de Discord
            for i in range(0, len(answer), 1900):
                part = answer[i:i + 1900]

                await message.reply(
                    part,
                    mention_author=False,
                    allowed_mentions=discord.AllowedMentions.none(),
                )

        except Exception:
            logger.exception(
                "Error procesando una pregunta de Sakura AI"
            )

            try:
                await message.reply(
                    "❌ No pude completar tu pregunta.\n"
                    "Comprueba la configuración de Gemini "
                    "y revisa los registros de FadeHost.",
                    mention_author=False,
                )
            except discord.HTTPException:
                logger.exception(
                    "No se pudo enviar el mensaje de error a Discord"
                )


# ============================================
# 🚀 INICIAR EL BOT
# ============================================

if __name__ == "__main__":
    logger.info("Iniciando Sakura AI...")

    bot.run(DISCORD_TOKEN)
