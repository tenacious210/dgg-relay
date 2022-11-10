import json
import logging
import re
from queue import Queue
from threading import Thread
from time import sleep

import google.cloud.logging
from tldextract import tldextract
from dggbot import DGGBot, Message, PrivateMessage
from discord import Intents, User
from discord.ext import commands
from google.cloud import storage

from cogs import OwnerCog, PublicCog

logging.getLogger("websocket").setLevel(logging.CRITICAL)
logging.root.disabled = True
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class CustomDiscBot(commands.Bot):
    cloud_sync = True

    def __init__(self):
        if self.cloud_sync:
            storage_client = storage.Client()
            storage_bucket = storage_client.bucket("tenadev")
            self.config_blob = storage_bucket.blob("dgg-relay/config.json")
            logging_client = google.cloud.logging.Client()
            logging_client.setup_logging(log_level=logging.DEBUG)
        intents = Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="/", intents=intents)
        self.read_config()
        self.dgg_bot = CustomDGGBot(auth_token=self.dgg_auth)

    def read_config(self):
        """Downloads and reads config file to set attributes"""
        if self.cloud_sync:
            self.config_blob.download_to_filename("config.json")
            logger.info("Downloaded config file")
        with open("config.json", "r") as config_file:
            config = json.loads(config_file.read())
            config["presence"] = {int(k): v for k, v in config["presence"].items()}
        self.disc_auth, self.dgg_auth = config["disc_auth"], config["dgg_auth"]
        self.relays, self.phrases = config["relays"], config["phrases"]
        self.emotes, self.presence = config["emotes"], config["presence"]

    def save_config(self):
        """Saves attributes to the config file and uploads them"""
        to_json = {
            "disc_auth": self.disc_auth,
            "dgg_auth": self.dgg_auth,
            "relays": self.relays,
            "phrases": self.phrases,
            "presence": {str(k): v for k, v in self.presence.items()},
            "emotes": self.emotes,
        }
        with open("config.json", "w") as config_file:
            json.dump(to_json, config_file, indent=2)
        if self.cloud_sync:
            self.config_blob.upload_from_filename("config.json")
            logger.info("Uploaded config file")

    async def setup_hook(self):
        logger.info("Starting Discord bot")
        app_info = await self.application_info()
        self.owner: User = app_info.owner
        dgg_bot_thread = Thread(target=self.dgg_bot.run)
        dgg_bot_thread.start()
        dgg_listener_thread = Thread(target=self.dgg_listener)
        dgg_listener_thread.start()
        if self.dgg_auth:
            priv_listener_thread = Thread(target=self.dgg_priv_listener)
            priv_listener_thread.start()
        await self.add_cog(OwnerCog(self))
        await self.add_cog(PublicCog(self))

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

    def dgg_listener(self):
        while True:
            messages = []
            for _ in range(self.dgg_bot.msg_queue.qsize()):
                messages.append(self.dgg_bot.msg_queue.get())
            self.relay(messages)
            sleep(30)

    def dgg_priv_listener(self):
        while True:
            msg = self.dgg_bot.privmsg_queue.get()
            self.relay_privmsg(msg)

    def relay(self, dgg_messages: list):
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
                    phrase_message = f"{self.dgg_to_disc(msg.nick, msg.data)}\n"
                    for user_id in self.phrases[phrase]:
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
            if (
                self.presence[user_id] == "on"
                and phrase.lower() not in self.dgg_bot.users.keys()
                or self.presence[user_id] == "off"
            ):
                for message in p_messages:
                    self.loop.create_task(user.send(message[:-1]))
                    logger.debug(f"Relayed '{message[:-1]}' to {user}")

    def relay_privmsg(self, msg: PrivateMessage):
        """Relays private messages to the bot's owner"""
        message = f"W {self.dgg_to_disc(msg.nick, msg.data)}"
        logger.debug(f"Forwarding whisper to owner: {message}")
        self.loop.create_task(self.owner.send(message))


class CustomDGGBot(DGGBot):
    def __init__(self, auth_token: str):
        super().__init__(auth_token)
        self.msg_queue = Queue()
        self.privmsg_queue = Queue()

    def on_msg(self, msg: Message):
        super().on_msg(msg)
        self.msg_queue.put(msg)

    def on_privmsg(self, msg: PrivateMessage):
        super().on_privmsg(msg)
        self.privmsg_queue.put(msg)

    def on_quit(self, msg: Message):
        if msg.nick.lower() in self._users.keys():
            del self._users[msg.nick.lower()]
        for func in self._events.get("on_quit", tuple()):
            func(msg)

    def run(self, origin: str = None):
        while True:
            logger.info("Starting DGG bot")
            self.ws.run_forever(origin=origin or self.URL)


if __name__ == "__main__":
    main_bot = CustomDiscBot()
    main_bot.run(main_bot.disc_auth, root_logger=True)
