
        except Exception as error:
            # Los detalles técnicos solo aparecen en los registros.
            logger.exception("Error interno al procesar la solicitud.")

            error_text = str(error).lower()
            status_code = getattr(error, "status_code", None)

            try:
                status_code = int(status_code)
            except (TypeError, ValueError):
                status_code = None

            if (
                isinstance(error, TimeoutError)
                or isinstance(error, asyncio.TimeoutError)
                or "timeout" in error_text
                or "timed out" in error_text
            ):
                user_message = (
                    "⏳ Sakura está tardando un poco más de lo esperado. "
                    "Inténtalo de nuevo en unos segundos."
                )

            elif (
                status_code == 404
                or "404" in error_text
                or "not_found" in error_text
            ):
                user_message = (
                    "🌸 No pude completar tu solicitud en este momento. "
                    "Inténtalo de nuevo más tarde."
                )

            elif (
                status_code == 429
                or "429" in error_text
                or "resource_exhausted" in error_text
                or "quota" in error_text
            ):
                user_message = (
                    "⏳ Hay muchas solicitudes en este momento. "
                    "Espera un poco e inténtalo de nuevo."
                )

            elif (
                status_code in (401, 403)
                or "401" in error_text
                or "403" in error_text
                or "api key" in error_text
                or "permission" in error_text
            ):
                user_message = (
                    "🌸 No pude completar tu solicitud. "
                    "Vuelve a intentarlo más tarde."
                )

            elif is_temporary_error(error):
                user_message = (
                    "🌸 Estoy experimentando una interrupción temporal. "
                    "Dame unos segundos e inténtalo de nuevo."
                )

            else:
                user_message = (
                    "❌ Ocurrió un problema al procesar tu mensaje. "
                    "Inténtalo de nuevo más tarde."
                )

            try:
                await send_error_embed(message, user_message)
            except discord.HTTPException:
                logger.exception("No se pudo enviar el mensaje de error.")
