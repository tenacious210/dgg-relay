from google.cloud import storage
import google.cloud.logging
from dggbot import DGGBot, Message, PrivateMessage
from discord import Intents, User
from discord.ext import commands
from threading import Thread
from queue import Queue
import tldextract
import logging
import json
import re

from cogs import OwnerCog, PublicCog


logger = logging.getLogger(__name__)
logging.getLogger("websocket").setLevel(logging.CRITICAL)
logging.root.disabled = True


class CustomDiscBot(commands.Bot):
    cloud_sync = True

    def __init__(self):
        if self.cloud_sync:
            storage_client = storage.Client()
            storage_bucket = storage_client.bucket("tenadev")
            self.config_blob = storage_bucket.blob("dgg-relay/config.json")
            logging_client = google.cloud.logging.Client()
            logging_client.setup_logging()
        intents = Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="/", intents=intents)
        self.read_config()
        self.dgg_bot = CustomDGGBot(auth_token=self.dgg_auth)
        self.owner: User = None

    def read_config(self):
        """Downloads and reads config file to set attributes"""
        if self.cloud_sync:
            self.config_blob.download_to_filename("config.json")
            logger.info("Downloaded config file")
        with open("config.json", "r") as config_file:
            config = json.loads(config_file.read())
            config["presence"] = {int(k): v for k, v in config["presence"].items()}
        self.disc_auth, self.dgg_auth = config["disc_auth"], config["dgg_auth"]
        self.nicks, self.phrases = config["nicks"], config["phrases"]
        self.emotes, self.presence = config["emotes"], config["presence"]

    def save_config(self):
        """Saves attributes to the config file and uploads them"""
        to_json = {
            "disc_auth": self.disc_auth,
            "dgg_auth": self.dgg_auth,
            "nicks": self.nicks,
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
        dgg_bot_thread = Thread(target=self.dgg_bot.run)
        dgg_bot_thread.start()
        dgg_listener_thread = Thread(target=self.dgg_listener)
        dgg_listener_thread.start()
        if self.dgg_auth:
            priv_listener_thread = Thread(target=self.dgg_priv_listener)
            priv_listener_thread.start()
        app_info = await self.application_info()
        self.owner = app_info.owner
        await self.add_cog(OwnerCog(self))
        await self.add_cog(PublicCog(self))

    def dgg_to_disc(self, dgg_nick: str, dgg_txt: str):
        """Converts DGG emotes/links to Discord ones"""
        for link in set(
            re.findall(r"(?:(?:https?|ftp):\/\/)?[\w/\-?=%.]+\.[\w/\-&?=%.]+", dgg_txt)
        ):
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
            msg = self.dgg_bot.msg_queue.get()
            self.relay(msg)

    def dgg_priv_listener(self):
        while True:
            msg = self.dgg_bot.privmsg_queue.get()
            self.relay_privmsg(msg)

    def relay(self, msg: Message):
        """Takes in a DGG message and relays it to Discord"""
        if msg.nick.lower() in [nick.lower() for nick in self.nicks.keys()]:
            for channel_id in self.nicks[msg.nick]:
                if channel := self.get_channel(channel_id):
                    msg_is_nsfw = any([n in msg.data.lower() for n in ("nsfw", "nsfl")])
                    if (not msg_is_nsfw) or (msg_is_nsfw and channel.is_nsfw()):
                        relay_message = self.dgg_to_disc(msg.nick, msg.data)
                    else:
                        relay_message = f"**{msg.nick}:** _Censored for nsfw tag_"
                    self.loop.create_task(channel.send(relay_message))
                    logger.debug(f"Relayed '{relay_message}' to {channel.guild}")
                else:
                    logger.warning(f"Channel {channel_id} wasn't found")
        for phrase in self.phrases.keys():
            lower_phrase = phrase.lower()
            if re.search(rf"\b{lower_phrase}\b", msg.data.lower()):
                for user_id in self.phrases[phrase]:
                    if user := self.get_user(user_id):
                        if (
                            self.presence[user_id] == "on"
                            and lower_phrase not in self.dgg_bot.users.keys()
                            or self.presence[user_id] == "off"
                        ):
                            relay_message = self.dgg_to_disc(msg.nick, msg.data)
                            self.loop.create_task(user.send(relay_message))
                            logger.info(f"Relayed '{relay_message}' to {user}")
                    else:
                        logger.warning(f"User {user_id} wasn't found")

    def relay_privmsg(self, msg: PrivateMessage):
        """Relays private messages to the bot's owner"""
        message = f"W {self.dgg_to_disc(msg.nick, msg.data)}"
        logger.info(f"Forwarding whisper to owner: {message}")
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
