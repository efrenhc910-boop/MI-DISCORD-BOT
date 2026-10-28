
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
# 🧠 CLIENTE GEMINI
# ==================================================

ai = genai.Client(api_key=GEMINI_API_KEY)

# ==================================================
# 🤖 CREAR BOT DE DISCORD
# ==================================================

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

bot = discord.Client(intents=intents)

chat_sessions = {}
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
    print(f"║ Modelo: {GEMINI_MODEL[:32]:<32} ║")
    print("║ Comando: .S pregunta                     ║")
    print("╚══════════════════════════════════════════╝")
    print("\n")

    logger.info("Bot conectado y listo para recibir mensajes.")


# ==================================================
# 💬 EVENTO DE MENSAJES
# ==================================================

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

    if content.lower() != ".s" and not content.lower().startswith(".s "):
        return

    prompt = content[2:].strip()

    logger.info("🌸 Comando .S detectado.")

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
                "🧠 Enviando pregunta a Gemini. Modelo: %s",
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

            # Gemini tiene un límite de 40 segundos para responder.
            async with message.channel.typing():
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        chat.send_message,
                        prompt,
                    ),
                    timeout=40,
                )

            answer = (response.text or "").strip()

            if not answer:
                logger.warning("Gemini devolvió una respuesta vacía.")
                await message.reply(
                    "🌸 Gemini no devolvió texto. Prueba otra pregunta.",
                    mention_author=False,
                )
                return

            logger.info("✅ Gemini respondió correctamente.")

            for i in range(0, len(answer), 1900):
                await message.reply(
                    answer[i:i + 1900],
                    mention_author=False,
                    allowed_mentions=discord.AllowedMentions.none(),
                )

            logger.info("✅ Respuesta enviada a Discord.")

        except asyncio.TimeoutError:
            logger.error("⏱️ Gemini superó el límite de 40 segundos.")

            try:
                await message.reply(
                    "⏳ Sakura tardó demasiado en recibir respuesta "
                    "de Gemini. Inténtalo de nuevo en unos segundos.",
                    mention_author=False,
                )
            except discord.HTTPException:
                logger.exception("No se pudo enviar el aviso de tiempo agotado.")

        except Exception as error:
            logger.exception("❌ Error procesando la pregunta.")

            error_text = str(error).lower()

            if "404" in error_text or "not_found" in error_text:
                user_message = (
                    "⚠️ El modelo de Gemini no está disponible. "
                    "Revisa GEMINI_MODEL en FadeHost."
                )
            elif "429" in error_text or "resource_exhausted" in error_text:
                user_message = (
                    "⏳ Gemini alcanzó un límite de uso. "
                    "Espera un poco y vuelve a intentarlo."
                )
            elif "401" in error_text or "403" in error_text:
                user_message = (
                    "🔑 Gemini rechazó la solicitud. "
                    "Comprueba la clave y los permisos de la API."
                )
            else:
                user_message = (
                    "❌ Ocurrió un error al consultar la IA. "
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
