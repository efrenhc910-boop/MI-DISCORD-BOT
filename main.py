
import os
import asyncio
import logging

import discord
from dotenv import load_dotenv
from google import genai
from google.genai import types

# ==========================================
# 🌸 SAKURA AI - CONFIGURACIÓN
# ==========================================

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("SakuraAI")

SYSTEM_INSTRUCTION = """
Eres Sakura AI, el asistente de inteligencia artificial
del servidor de Discord Sakura Hub.

Responde en español de forma amable, clara y útil.
Puedes ayudar con programación, Roblox Lua, Discord,
tecnología, dudas generales y aprendizaje.

Usa Markdown cuando ayude a entender la respuesta.
Si no sabes algo, dilo con honestidad.
No inventes información ni afirmes haber ejecutado
acciones que no realizaste.
"""

# ==========================================
# ⚙️ VALIDAR CONFIGURACIÓN
# ==========================================

if not DISCORD_TOKEN:
    raise RuntimeError(
        "Falta DISCORD_TOKEN en las variables de entorno de FadeHost."
    )

if not GEMINI_API_KEY:
    raise RuntimeError(
        "Falta GEMINI_API_KEY en las variables de entorno de FadeHost."
    )

ai = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# 🤖 CREAR EL BOT DE DISCORD
# ==========================================

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

bot = discord.Client(intents=intents)

# Memoria de conversación y bloqueos por usuario
chat_sessions = {}
user_locks = {}


def get_user_lock(user_id: int) -> asyncio.Lock:
    """Evita que dos mensajes del mismo usuario
    modifiquen simultáneamente su conversación."""
    if user_id not in user_locks:
        user_locks[user_id] = asyncio.Lock()

    return user_locks[user_id]


# ==========================================
# 🌸 CUANDO EL BOT SE CONECTA
# ==========================================

@bot.event
async def on_ready():
    logger.info("Sakura AI inició sesión como %s", bot.user)
    logger.info("Comando disponible: .S pregunta")
    logger.info("Modelo Gemini: %s", GEMINI_MODEL)


# ==========================================
# 💬 COMANDO .S
# ==========================================

@bot.event
async def on_message(message: discord.Message):
    # Ignorar mensajes de bots, incluido el propio
    if message.author.bot:
        return

    content = message.content.strip()

    # Aceptar .S, .s y variantes en mayúsculas/minúsculas
    lowered = content.lower()

    if lowered != ".s" and not lowered.startswith(".s "):
        return

    prompt = content[2:].strip()

    if not prompt:
        await message.reply(
            "🌸 Escribe tu pregunta después de `.S`.\n"
            "Ejemplo: `.S ¿Qué es Roblox Lua?`",
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
            # Crear una conversación nueva si el usuario
            # todavía no tiene una sesión de chat
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
                await message.reply(
                    "🌸 No recibí una respuesta de Gemini. "
                    "Inténtalo de nuevo.",
                    mention_author=False,
                )
                return

            # Discord limita los mensajes a 2000 caracteres.
            # Enviar partes de hasta 1900 para mantener margen.
            for i in range(0, len(answer), 1900):
                await message.reply(
                    answer[i:i + 1900],
                    mention_author=False,
                    allowed_mentions=discord.AllowedMentions.none(),
                )

        except Exception:
            logger.exception(
                "Error al consultar Gemini para el usuario %s",
                message.author.id,
            )

            await message.reply(
                "❌ Ocurrió un error al consultar la IA. "
                "Revisa la configuración y los registros del bot.",
                mention_author=False,
            )


# ==========================================
# 🚀 INICIAR SAKURA AI
# ==========================================

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
