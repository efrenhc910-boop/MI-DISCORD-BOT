
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    content = message.content.strip()

    if not content.lower().startswith(".s "):
        return

    prompt = content[3:].strip()

    if not prompt:
        await message.reply("🌸 Escribe tu pregunta después de `.S`.")
        return

    if len(prompt) > 1500:
        await message.reply("⚠️ Tu pregunta no puede superar los 1500 caracteres.")
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
                response = await asyncio.to_thread(
                    chat.send_message,
                    prompt,
                )

            answer = (response.text or "").strip()

            if not answer:
                await message.reply("No recibí una respuesta de Gemini.")
                return

            for i in range(0, len(answer), 1900):
                await message.reply(
                    answer[i:i + 1900],
                    allowed_mentions=discord.AllowedMentions.none(),
                )

        except Exception:
            logger.exception("Error al consultar Gemini")
            await message.reply("❌ Ocurrió un error al consultar la IA.")
