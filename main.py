import json
import logging
import re
from queue import Queue
from threading import Thread
import time

import google.cloud.logging
from google.cloud import storage
from tldextract import tldextract
from dggbot import DGGChat, Message, DGGLive, StreamInfo
from discord import Intents, User
from discord.ext import commands

from cogs import OwnerCog, PublicCog

logging.getLogger("websocket").setLevel(logging.CRITICAL)
logging.root.disabled = True
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class CustomDGGChat(DGGChat):
    def __init__(self):
        super().__init__()
        self.msg_queue = Queue()

    def on_msg(self, msg: Message):
        super().on_msg(msg)
        self.msg_queue.put(msg)


class CustomDGGLive(DGGLive):
    def __init__(self):
        super().__init__()
        self.live_queue = Queue()

    def on_streaminfo(self, streaminfo: StreamInfo):
        super().on_streaminfo(streaminfo)
        self.live_queue.put(streaminfo)

    def run_forever(self, origin: str = None, sleep: int = 2):
        """Runs the client forever by automatically reconnecting the websocket."""
        while True:
            self.run(origin=origin or self.ORIGIN)
            time.sleep(sleep)


class CustomDiscBot(commands.Bot):
    cloud_sync = False

    def __init__(self):
        if self.cloud_sync:
            storage_client = storage.Client()
            storage_bucket = storage_client.bucket("tenadev")
            self.cfg_blob = storage_bucket.blob("dgg-relay/config.json")
            logging_client = google.cloud.logging.Client()
            logging_client.setup_logging(log_level=logging.DEBUG)
        intents = Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="/", intents=intents)
        self.read_cfg()
        self.dgg_chat = CustomDGGChat()
        self.dgg_live = CustomDGGLive()

    async def setup_hook(self):
        logger.info("Starting Discord bot")
        app_info = await self.application_info()
        self.owner: User = app_info.owner
        Thread(target=self.dgg_chat.run_forever).start()
        Thread(target=self.dgg_thread).start()
        Thread(target=self.dgg_live.run_forever).start()
        Thread(target=self.live_thread).start()
        await self.add_cog(OwnerCog(self))
        await self.add_cog(PublicCog(self))

    def read_cfg(self):
        """Downloads and reads config file to set attributes"""
        if self.cloud_sync:
            self.cfg_blob.download_to_filename("config.json")
            logger.info("Downloaded config file")
        with open("config.json", "r") as cfg_file:
            cfg = json.loads(cfg_file.read())
        self.disc_auth, self.cfg_owner_id = cfg["disc_auth"], cfg["owner_id"]
        self.relays, self.phrases = cfg["relays"], cfg["phrases"]
        self.emotes, self.live = cfg["emotes"], cfg["live"]
        self.user_prefs = {int(k): v for k, v in cfg["user_prefs"].items()}
        self.live["channels"] = {int(k): v for k, v in self.live["channels"].items()}

    def save_cfg(self):
        """Saves attributes to the config file and uploads them"""
        json_channels = {str(k): v for k, v in self.live["channels"].items()}
        to_json = {
            "disc_auth": self.disc_auth,
            "relays": self.relays,
            "phrases": self.phrases,
            "user_prefs": {str(k): v for k, v in self.user_prefs.items()},
            "live": {"id": self.live["id"], "channels": json_channels},
            "emotes": self.emotes,
        }
        with open("config.json", "w") as cfg_file:
            json.dump(to_json, cfg_file, indent=2)
        if self.cloud_sync:
            self.cfg_blob.upload_from_filename("config.json")
            logger.info("Uploaded config file")

    def dgg_to_disc(self, dgg_nick: str, dgg_txt: str):
        """Converts DGG emotes/links to Discord ones"""
        link_re = r"(?:(?:https?|ftp):\/\/)?[\w/\-?=%.]+\.[\w/\-&?=%.]+"
        for link in set(re.findall(link_re, dgg_txt)):
            url = tldextract.extract(link)
            if url.domain and url.suffix:
                if not re.search(r"\Ahttps?://", link):
                    dgg_txt = dgg_txt.replace(link, f"https://{link}")
                    link = f"https://{link}"
        disc_txt = []
        for part in dgg_txt.split():
            if not part.startswith("http"):
                for dgg_emote, disc_emote in self.emotes.items():
                    part = re.sub(rf"\b{dgg_emote}\b", disc_emote, part)
                part = re.sub("[*_`|@]", r"\\\g<0>", part)
            disc_txt.append(part)
        disc_txt = " ".join(disc_txt)
        dgg_nick = re.sub("[*_`|]", r"\\\g<0>", dgg_nick)
        if any([tag in disc_txt.lower() for tag in ("nsfw", "nsfl")]):
            disc_txt = f"||{disc_txt}||"
        return f"**{dgg_nick}:** {disc_txt}"

    def live_thread(self):
        while True:
            time.sleep(5)
            self.live_notify(self.dgg_live.live_queue.get())

    def live_notify(self, yt_info: StreamInfo):
        if yt_info.live and not self.live["id"]:
            logger.info("Stream started, sending notifications")
            for channel_id in self.live["channels"]:
                if not (channel := self.get_channel(channel_id)):
                    logger.warning(f"LN channel {channel_id} wasn't found")
                    continue
                if not self.live["channels"][channel_id]["enabled"]:
                    continue
                live_msg = ""
                if role := self.live["channels"][channel_id]["role"]:
                    live_msg += f"<@&{role}> "
                live_msg += f"**Destiny is live!** https://youtu.be/{yt_info.id}"
                self.loop.create_task(channel.send(live_msg))
            self.live["id"] = yt_info.id
            self.save_cfg()
        elif self.live["id"] and not yt_info.live:
            self.live["id"] = None
            logger.info("Stream ended")
            self.save_cfg()

    def dgg_thread(self):
        while True:
            messages = []
            for _ in range(self.dgg_chat.msg_queue.qsize()):
                messages.append(self.dgg_chat.msg_queue.get())
            self.relay(messages)
            time.sleep(30)

    def relay(self, dgg_messages: list[Message]):
        """Takes in a list of DGG messages and relays them to Discord"""

        def add_message_to_queue(queue: dict, disc_id: int, message: str):
            if disc_id not in queue.keys():
                queue[disc_id] = [""]
            if len(queue[disc_id][-1]) + len(message) > 2000:
                queue[disc_id].append("")
            queue[disc_id][-1] += message

        relay_queue, phrase_queue = {}, {}
        for msg in dgg_messages:
            if msg.nick in self.relays.keys():
                relay_message = f"{self.dgg_to_disc(msg.nick, msg.data)}\n"
                for channel_id in self.relays[msg.nick]:
                    add_message_to_queue(relay_queue, channel_id, relay_message)
            for phrase in self.phrases.keys():
                if re.search(rf"\b{phrase.lower()}\b", msg.data.lower()):
                    for user_id in self.phrases[phrase]:
                        prefs = self.user_prefs[user_id]
                        presence_enabled = prefs["detect_presence"]
                        presence_check = (
                            presence_enabled
                            and phrase.lower() not in self.dgg_chat.users.keys()
                        ) or not presence_enabled
                        if not presence_check or msg.nick in prefs["ignores"]:
                            logger.debug(
                                f"Skipped relay to {user_id} due to preferences"
                            )
                            continue
                        phrase_message = f"{self.dgg_to_disc(msg.nick, msg.data)}\n"
                        add_message_to_queue(phrase_queue, user_id, phrase_message)
        for channel_id, r_messages in relay_queue.items():
            if not (channel := self.get_channel(channel_id)):
                logger.warning(f"Channel {channel_id} wasn't found")
                continue
            for message in r_messages:
                msg_is_nsfw = any([n in message.lower() for n in ("nsfw", "nsfl")])
                if msg_is_nsfw and not channel.is_nsfw():
                    logger.debug(f"Skipped relay to {channel.guild} due to nsfw tag")
                    continue
                self.loop.create_task(channel.send(message[:-1]))
                logger.debug(f"Relayed '{message[:-1]}' to {channel.guild}")
        for user_id, p_messages in phrase_queue.items():
            if not (user := self.get_user(user_id)):
                logger.warning(f"User {user_id} wasn't found")
                continue
            for message in p_messages:
                self.loop.create_task(user.send(message[:-1]))
                logger.debug(f"Relayed '{message[:-1]}' to {user}")


if __name__ == "__main__":
    main_bot = CustomDiscBot()
    main_bot.run(main_bot.disc_auth, root_logger=True)
