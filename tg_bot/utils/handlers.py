from typing import Optional, List

from telegram.ext import (
    CommandHandler,
    MessageHandler,
    PrefixHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
    BaseFilter,
)


from tg_bot import dispatcher, ALLOW_EXCL


class CustomCommandHandler(PrefixHandler):
    def __init__(self, command, callback, **kwargs):
        if "admin_ok" in kwargs:
            del kwargs["admin_ok"]
        super().__init__(("/", "!") if ALLOW_EXCL else "/", command, callback, **kwargs)


class CustomMessageHandler(MessageHandler):
    def __init__(self, filters, callback, friendly="", **kwargs):
        super().__init__(filters, callback, **kwargs)


from tg_bot.modules.disable import (
    DisableAbleCommandHandler,
    DisableAbleMessageHandler,
)


class TgBotHandler:
    def __init__(self, dispatcher):
        self._dispatcher = dispatcher

    def command(
        self,
        command: str,
        filters: Optional[BaseFilter] = None,
        run_async: bool = True,
        can_disable: bool = True,
        group: Optional[int] = 10,
    ):
        def add_command(func):
            if can_disable:
                self._dispatcher.add_handler(
                    DisableAbleCommandHandler(
                        command=command,
                        callback=func,
                        filters=filters,
                        run_async=run_async,
                    ),
                    group,
                )
            else:
                self._dispatcher.add_handler(
                    CommandHandler(
                        command=command,
                        callback=func,
                        filters=filters,
                        run_async=run_async,
                    ),
                    group,
                )

            return func

        return add_command

    def message(
        self,
        filters: Optional[BaseFilter] = None,
        can_disable: bool = True,
        friendly=None,
        run_async: bool = True,
        group: Optional[int] = 10,
    ):
        def add_message(func):
            if can_disable:
                self._dispatcher.add_handler(
                    DisableAbleMessageHandler(
                        filters=filters,
                        callback=func,
                        friendly=friendly,
                        run_async=run_async,
                    ),
                    group,
                )
            else:
                self._dispatcher.add_handler(
                    MessageHandler(filters=filters, callback=func, run_async=run_async),
                    group,
                )

            return func

        return add_message

    def callbackquery(
        self,
        pattern: Optional[str] = None,
        run_async: bool = True,
    ):
        def add_callbackquery(func):
            self._dispatcher.add_handler(
                CallbackQueryHandler(
                    callback=func, pattern=pattern, run_async=run_async
                )
            )
            return func

        return add_callbackquery

    def inlinequery(
        self,
        pattern: Optional[str] = None,
        run_async: bool = True,
        chat_types: List[str] = None,
    ):
        def add_inlinequery(func):
            self._dispatcher.add_handler(
                InlineQueryHandler(
                    pattern=pattern,
                    callback=func,
                    run_async=run_async,
                    chat_types=chat_types,
                )
            )
            return func

        return add_inlinequery


tgbot_cmd = TgBotHandler(dispatcher).command
tgbot_msg = TgBotHandler(dispatcher).message
tgbot_callback = TgBotHandler(dispatcher).callbackquery
tgbot_inline = TgBotHandler(dispatcher).inlinequery
