import datetime

from telegram import TelegramError, Update
from telegram.ext.dispatcher import Dispatcher, DispatcherHandlerStop
from telegram.utils.helpers import DEFAULT_FALSE


CHATS_COUNT = {}
CHATS_TIME = {}


def process_update(dispatcher: Dispatcher, update: Update):
    if isinstance(update, TelegramError):
        try:
            dispatcher.dispatch_error(None, update)
        except Exception:
            dispatcher.logger.exception(
                "An uncaught error was raised while handling the error!"
            )
        return

    now = datetime.datetime.utcnow()
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    # Avoid nonetype errors.
    if (chat or user or msg) is None:
        return

    count = CHATS_COUNT.get(chat.id, 0)
    time = CHATS_TIME.get(chat.id, now)

    if now > time + datetime.timedelta(0, 2):
        del CHATS_COUNT[chat.id]
        del CHATS_TIME[chat.id]
    else:
        count += 1
        CHATS_COUNT[chat.id] = count
        CHATS_TIME[chat.id] = now

    if count > 10:
        return

    context = None
    handled = False
    sync_modes = []

    for group in dispatcher.groups:
        try:
            for handler in dispatcher.handlers[group]:
                check = handler.check_update(update)
                if check is not None and check is not False:
                    if not context and dispatcher.use_context:
                        context = dispatcher.context_types.context.from_update(
                            update, dispatcher
                        )
                        context.refresh_data()
                    handled = True
                    sync_modes.append(handler.run_async)
                    handler.handle_update(update, dispatcher, check, context)
                    break

        # Stop processing with any other handler.
        except DispatcherHandlerStop:
            dispatcher.logger.debug(
                "Stopping further handlers due to DispatcherHandlerStop"
            )
            dispatcher.update_persistence(update=update)
            break

        # Dispatch any error.
        except Exception as exc:
            try:
                dispatcher.dispatch_error(update, exc)
            except DispatcherHandlerStop:
                dispatcher.logger.debug("Error handler stopped further handlers")
                break
            # Errors should not stop the thread.
            except Exception:
                dispatcher.logger.exception(
                    "An uncaught error was raised while handling the error."
                )

    # Update persistence, if handled
    handled_only_async = all(sync_modes)
    if handled:
        # Respect default settings
        if (
            all(mode is DEFAULT_FALSE for mode in sync_modes)
            and dispatcher.bot.defaults
        ):
            handled_only_async = dispatcher.bot.defaults.run_async
        # If update was only handled by async handlers, we don't need to update here
        if not handled_only_async:
            dispatcher.update_persistence(update=update)
