import logging
import smtplib
import ssl
import sys
import feedparser
import signal
import time
import aiohttp
import re
import base64
import datetime
import asyncio
import argparse
import tomllib

import log as log_setup

from email.mime.text import MIMEText

from deluge_client import DelugeRPCClient

RSS_FETCH_INTERVAL = 60 * 10  # every 15 minutes
UPTIME_KUMA_INTERVAL = 50

RSS_URL = ""

UPTIME_KUMA_URL = ""

EMAIL_DATA = {
    "host": "",
    "smtp": "",
    "port": 587,  # StartTLS 587
    "recipient": "",
    "user": "",
    "password": ""
}

DELUGE_DATA = {
    "host": "",
    "port": 58846,
    "username": "",
    "password": "",
    "label": "auto-add"
}

deferred_emails = []
new_deferred_emails = []

IS_DEV = "--dev" in sys.argv

def stop_signal(sig, frame):
    sys.exit(0)


signal.signal(signal.SIGINT, stop_signal)


def create_old_state(parsed) -> list:
    new_state = []
    for parsed_input in parsed.get("entries"):
        new_state.append(parsed_input.get("title_detail"))

    return new_state


async def add_torrent_to_deluge(torrent_url) -> bool:
    """
    Adds a torrent to deluge. Returns if it was added successfully
    :param torrent_url: Torrent url to add
    :return: True if added successfully. False if not
    """
    logger = logging.getLogger(__name__)
    logger.info("Downloading .torrent file")
    async with aiohttp.ClientSession() as session:
        async with session.get(torrent_url) as resp:
            file_dl = resp

            file_name: str = re.findall('filename=(.+);', file_dl.headers.get("content-disposition"))[0]
            file_name = file_name.removeprefix("\"").removesuffix("\"").removesuffix(".torrent")

            client = DelugeRPCClient(DELUGE_DATA["host"], int(DELUGE_DATA["port"]), DELUGE_DATA["username"], DELUGE_DATA["password"],
                                     automatic_reconnect=True)

            file_content = await file_dl.content.read()

    logger.info("Connecting to deluge")

    client.connect()

    if not client.connected:
        logger.error("Failed to connect to DelugeRPC")
        return False

    try:
        torrent_id = client.call("core.add_torrent_file", file_name, base64.b64encode(file_content), {})
    except BaseException as e:
        if "Torrent already in session" in str(e):
            logger.info("Torrent already in session")
            return True

        logger.error(f"Failed to add torrent: {e}")
        log_setup.log_traceback()
        return False

    client.call("label.set_torrent", torrent_id, DELUGE_DATA["label"])
    logger.info(f"Set torrent to label: {DELUGE_DATA['label']}")
    client.disconnect()

    return True


def format_bytes(size: int) -> str:
    if size < 1000:
        return f"{size} Bytes"

    kb = size / 1000

    if kb < 1000:
        return f"{round(kb, 2)} KB"

    mb = kb / 1000

    if mb < 1000:
        return f"{round(mb, 2)} MB"

    gb = mb / 1000

    return f"{round(gb, 2)} GB"


async def send_email(text, deferred=False):
    global deferred_emails, new_deferred_emails
    logger = logging.getLogger(__name__)
    context = ssl.create_default_context()
    if not deferred:
        if deferred_emails:
            for email in deferred_emails:
                await send_email(email, deferred=True)
            deferred_emails.clear()
            deferred_emails = new_deferred_emails.copy()
            new_deferred_emails.clear()
    try:
        with smtplib.SMTP(EMAIL_DATA["smtp"], int(EMAIL_DATA["port"]), timeout=30) as server:
            server.starttls(context=context)
            server.login(EMAIL_DATA["user"], EMAIL_DATA["password"])

            msg = MIMEText(text)

            msg["Subject"] = f"{'DEV: ' if IS_DEV else ''}{'Deferred -' if deferred else ''} BakaBT torrent entry"
            msg["From"] = EMAIL_DATA["user"]
            msg["To"] = EMAIL_DATA["recipient"]

            server.sendmail(EMAIL_DATA["user"],
                            EMAIL_DATA["recipient"], msg.as_string())
            server.quit()
            logger.info("Sent email")
    except (TimeoutError and OSError) as e:
        logger.error(f"Could not send email: {e}")
        if not deferred:
            logger.warning("Could not send email: Marked as deferred")
            new_deferred_emails.append(text)


async def send_uptime_kuma_ping():
    logger = logging.getLogger(__name__)
    while True:
        async with aiohttp.ClientSession() as session:
            try:
                await session.get(UPTIME_KUMA_URL)
                logger.debug("Sent uptime-kuma ping")
            except aiohttp.ClientConnectorError:
                logger.error("Failed to connect to uptime-kuma")

        logger.debug(f"Sleeping {UPTIME_KUMA_INTERVAL} seconds")
        await asyncio.sleep(UPTIME_KUMA_INTERVAL)

def set_config(config_path: str):
    global DELUGE_DATA, EMAIL_DATA, RSS_URL, UPTIME_KUMA_URL
    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    # print(config)

    DELUGE_DATA = config.get("DELUGE")
    EMAIL_DATA = config.get("EMAIL")

    RSS_URL = config.get("GENERAL").get("rss_url")
    UPTIME_KUMA_URL = config.get("GENERAL").get("uptime_url")


def main():
    asyncio.run(_main())

async def _main():
    parser = argparse.ArgumentParser(
        prog="auto-add-torrents",
    )
    parser.add_argument("-d", "--dev", action="store_true", dest="dev")
    parser.add_argument("-l", "--log-dir", help="What directory to use as a logging directory", type=str, dest="log_dir", required=True)
    parser.add_argument("-c", "--config", help="Location of the configuration file", type=str, required=True, dest="config")
    args = parser.parse_args()

    set_config(args.config)
   
    log_setup.setup_logging(log_root_folder=args.log_dir, console_level=logging.DEBUG if IS_DEV else logging.INFO)
    logger = logging.getLogger(__name__)
    old_state = []
    logging.info("Hello")
    asyncio.create_task(send_uptime_kuma_ping())

    logger.debug("Sending email...")
    await send_email("Successfully started auto-add-torrents")

    while True:
        parsed = feedparser.parse(RSS_URL)

        status = parsed.get("status")

        if status != 200:
            msg = f"Failed to parse torrents. Indexer unavailable. Sleeping {(RSS_FETCH_INTERVAL * 2) / 60} minutes: Status: {status} | Parsed: {parsed.text}"
            logger.info(msg)
            await send_email(msg)
            await asyncio.sleep(RSS_FETCH_INTERVAL * 2)
            continue

        if not old_state:
            logger.info("Initializing base state")
            old_state = create_old_state(parsed)
            if IS_DEV:
                old_state.pop(0)
            continue

        for entry in parsed.get("entries"):
            if entry.get("title_detail") not in old_state:
                logger.info(f"Found new entry: {entry.get('title')}")
                torrent_url = entry.get("link").replace("http://localhost:9696", "https://prowlarr.local.ole.blue")

                print(torrent_url)
                added_successful = await add_torrent_to_deluge(torrent_url)
                if added_successful:
                    await send_email(f"Added new torrent:"
                                     f"\nName: {entry.get('title')}"
                                     f"\nSize: {format_bytes(int(entry.get('size')))}"
                                     f"\nPublished at: {entry.get('published')}"
                                     f"\nGrabbed at: {datetime.datetime.now().strftime('%a, %d %b %Y %H:%M:%S')}"
                                     )
                    logger.info("Successfully sent email")
                else:
                    await send_email(f"Failed to add torrent: {entry.get('title')}")
                    logger.error("Failed to send email!")

        old_state = create_old_state(parsed)

        logger.info(f"Waiting {RSS_FETCH_INTERVAL / 60} minutes for a new fetch")
        await asyncio.sleep(RSS_FETCH_INTERVAL)


if __name__ == '__main__':
    main()
