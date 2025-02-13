import requests
import subprocess
import os
import speedtest

from telegram import Update
from telegram.ext import CommandHandler, Filters
from tg_bot.modules.helper_funcs.extraction import extract_text

from tg_bot import dispatcher, CallbackContext, OWNER_ID
from tg_bot.modules.helper_funcs.filters import CustomFilters


# Kanged from PaperPlane Extended userbot
def speed_convert(size):
    """
    Hi human, you can't read bytes?
    """
    power = 2 ** 10
    zero = 0
    units = {0: "", 1: "Kb/s", 2: "Mb/s", 3: "Gb/s", 4: "Tb/s"}
    while size > power:
        size /= power
        zero += 1
    return f"{round(size, 2)} {units[zero]}"


def get_bot_ip(update: Update, context: CallbackContext):
    bot = context.bot
    """ Sends the bot's IP address, so as to be able to ssh in if necessary.
        OWNER ONLY.
    """
    res = requests.get("http://ipinfo.io/ip")
    update.message.reply_text(res.text)


def rtt(update: Update, context: CallbackContext):
    bot = context.bot
    out = ""
    under = False
    if os.name == "nt":
        output = subprocess.check_output(
            "ping -n 1 149.154.167.220 | findstr time*", shell=True
        ).decode()
        outS = output.splitlines()
        out = outS[0]
    else:
        out = subprocess.check_output(
            "ping -c 1 149.154.167.220 | grep time=", shell=True
        ).decode()
    splitOut = out.split(" ")
    stringtocut = next(
        (
            line
            for line in splitOut
            if line.startswith("time=") or line.startswith("time<")
        ),
        "",
    )

    newstra = stringtocut.split("=")
    if len(newstra) == 1:
        under = True
        newstra = stringtocut.split("<")
    newstr = ""
    newstr = newstra[1].split("ms") if os.name == "nt" else newstra[1].split(
            " "
        )
    ping_time = float(newstr[0])
    if os.name == "nt" and under:
        update.effective_message.reply_text(
            " Round-trip time is <{}ms".format(ping_time)
        )
    else:
        update.effective_message.reply_text(" Round-trip time: {}ms".format(ping_time))


def ping(update: Update, context: CallbackContext):
    bot = context.bot
    message = update.effective_message
    parsing = extract_text(message).split(" ")
    if len(parsing) < 2:
        message.reply_text("Give me an address to ping!")
        return
    if len(parsing) > 2:
        message.reply_text("Too many arguments!")
        return
    dns = (parsing)[1]
    out = ""
    under = False
    if os.name == "nt":
        try:
            output = subprocess.check_output(
                f"ping -n 1 {dns} | findstr time*", shell=True
            ).decode()

        except:
            message.reply_text("There was a problem parsing the IP/Hostname")
            return
        outS = output.splitlines()
        out = outS[0]
    else:
        try:
            out = subprocess.check_output(
                f"ping -c 1 {dns} | grep time=", shell=True
            ).decode()

        except:
            message.reply_text("There was a problem parsing the IP/Hostname")
            return
    splitOut = out.split(" ")
    stringtocut = next(
        (
            line
            for line in splitOut
            if line.startswith("time=") or line.startswith("time<")
        ),
        "",
    )

    newstra = stringtocut.split("=")
    if len(newstra) == 1:
        under = True
        newstra = stringtocut.split("<")
    newstr = ""
    newstr = newstra[1].split("ms") if os.name == "nt" else newstra[1].split(
            " "
        )
    ping_time = float(newstr[0])
    if os.name == "nt" and under:
        update.effective_message.reply_text(
            f" Ping speed of {dns}" + " is <{}ms".format(ping_time)
        )

    else:
        update.effective_message.reply_text(
            f" Ping speed of {dns}" + ": {}ms".format(ping_time)
        )


def speedtst(update: Update, context: CallbackContext):
    bot = context.bot
    test = speedtest.Speedtest()
    test.get_best_server()
    test.download()
    test.upload()
    test.results.share()
    result = test.results.dict()
    update.effective_message.reply_text(
        "Download "
        f"{speed_convert(result['download'])} \n"
        "Upload "
        f"{speed_convert(result['upload'])} \n"
        "Ping "
        f"{result['ping']} \n"
        "ISP "
        f"{result['client']['isp']}"
    )


IP_HANDLER = CommandHandler(
    "ip", get_bot_ip, filters=Filters.chat(OWNER_ID), run_async=True
)
RTT_HANDLER = CommandHandler(
    "ping", rtt, filters=CustomFilters.sudo_filter, run_async=True
)
PING_HANDLER = CommandHandler(
    "cping", ping, filters=CustomFilters.sudo_filter, run_async=True
)
SPEED_HANDLER = CommandHandler(
    "speedtest", speedtst, filters=CustomFilters.sudo_filter, run_async=True
)

dispatcher.add_handler(IP_HANDLER)
dispatcher.add_handler(RTT_HANDLER)
dispatcher.add_handler(SPEED_HANDLER)
dispatcher.add_handler(PING_HANDLER)
