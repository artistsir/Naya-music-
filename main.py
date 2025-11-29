import os
import asyncio
import time
import logging
import re
import uuid
import io
import sys
import shutil
import psutil
import platform
import aiohttp
import random
import yt_dlp
import ast
import traceback
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Union
from collections import defaultdict, deque
from functools import wraps
from html import escape
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# Third-party imports
from pyrogram import Client, filters, enums, types, idle
from pyrogram.errors import ChatAdminRequired, UserNotParticipant, FloodWait, MessageIdInvalid
from ntgcalls import ConnectionNotFound, TelegramServerError
from pytgcalls import PyTgCalls, exceptions
from pytgcalls.types import (
    InputAudioStream, 
    InputVideoStream, 
    AudioQuality, 
    VideoQuality,
    AudioParameters,
    VideoParameters,
    MediaStream,
    StreamAudioEnded,
    StreamVideoEnded,
    Update,
    GroupCallConfig
)
from pymongo import AsyncMongoClient
from youtube_search import YoutubeSearch
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

load_dotenv()

# ==================== CONFIGURATION ====================
class Config:
    def __init__(self):
        self.API_ID = int(os.getenv("API_ID", 0))
        self.API_HASH = os.getenv("API_HASH")
        self.BOT_TOKEN = os.getenv("BOT_TOKEN")
        self.MONGO_URL = os.getenv("MONGO_URL")
        self.LOGGER_ID = int(os.getenv("LOGGER_ID", 0))
        self.OWNER_ID = int(os.getenv("OWNER_ID", 0))
        self.DURATION_LIMIT = int(os.getenv("DURATION_LIMIT", 60)) * 60
        self.QUEUE_LIMIT = int(os.getenv("QUEUE_LIMIT", 20))
        self.PLAYLIST_LIMIT = int(os.getenv("PLAYLIST_LIMIT", 20))
        self.SESSION1 = os.getenv("SESSION1")
        self.SESSION2 = os.getenv("SESSION2")
        self.SESSION3 = os.getenv("SESSION3")
        self.SUPPORT_CHANNEL = os.getenv("SUPPORT_CHANNEL", "https://t.me/FallenAssociation")
        self.SUPPORT_CHAT = os.getenv("SUPPORT_CHAT", "https://t.me/DevilsHeavenMF")
        self.AUTO_END = os.getenv("AUTO_END", "False").lower() == "true"
        self.AUTO_LEAVE = os.getenv("AUTO_LEAVE", "False").lower() == "true"
        self.VIDEO_PLAY = os.getenv("VIDEO_PLAY", "True").lower() == "true"
        self.COOKIES_URL = [url for url in os.getenv("COOKIES_URL", "").split() if url and "batbin.me" in url]
        self.DEFAULT_THUMB = os.getenv("DEFAULT_THUMB", "https://te.legra.ph/file/3e40a408286d4eda24191.jpg")
        self.PING_IMG = os.getenv("PING_IMG", "https://files.catbox.moe/haagg2.png")
        self.START_IMG = os.getenv("START_IMG", "https://files.catbox.moe/zvziwk.jpg")

    def check(self):
        missing = [var for var in ["API_ID", "API_HASH", "BOT_TOKEN", "MONGO_URL", "LOGGER_ID", "OWNER_ID"] if not getattr(self, var)]
        if missing:
            raise SystemExit(f"Missing environment variables: {', '.join(missing)}")

config = Config()
config.check()

# ==================== LOGGING ====================
logging.basicConfig(
    format="[%(asctime)s - %(levelname)s] - %(name)s: %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler("log.txt", maxBytes=10485760, backupCount=5),
        logging.StreamHandler(),
    ],
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("ntgcalls").setLevel(logging.CRITICAL)
logging.getLogger("pymongo").setLevel(logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("pytgcalls").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

# ==================== DATACLASSES ====================
@dataclass
class Media:
    id: str
    duration: str
    duration_sec: int
    file_path: str
    message_id: int
    title: str
    url: str
    time: int = 0
    user: str = None
    video: bool = False

@dataclass
class Track:
    id: str
    channel_name: str
    duration: str
    duration_sec: int
    title: str
    url: str
    file_path: str = None
    message_id: int = 0
    time: int = 0
    thumbnail: str = None
    user: str = None
    view_count: str = None
    video: bool = False

# ==================== CORE COMPONENTS ====================
class Bot(Client):
    def __init__(self):
        super().__init__(
            name="Anony",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            parse_mode=enums.ParseMode.HTML,
            max_concurrent_transmissions=7,
        )
        self.owner = config.OWNER_ID
        self.logger = config.LOGGER_ID
        self.bl_users = filters.user()
        self.sudoers = filters.user(self.owner)

    async def boot(self):
        await super().start()
        self.id = self.me.id
        self.name = self.me.first_name
        self.username = self.me.username
        self.mention = self.me.mention
        
        try:
            await self.send_message(self.logger, "Bot Started")
            get = await self.get_chat_member(self.logger, self.id)
        except Exception as ex:
            raise SystemExit(f"Bot failed to access log group: {ex}")

        if get.status != enums.ChatMemberStatus.ADMINISTRATOR:
            raise SystemExit("Please promote bot as admin in logger group.")
        logger.info(f"Bot started as @{self.username}")

    async def exit(self):
        await super().stop()
        logger.info("Bot stopped.")

class Userbot(Client):
    def __init__(self):
        self.clients = []
        clients = {"one": "SESSION1", "two": "SESSION2", "three": "SESSION3"}
        for key, string_key in clients.items():
            name = f"AnonyUB{key[-1]}"
            session = getattr(config, string_key)
            if session:
                setattr(self, key, Client(name=name, api_id=config.API_ID, api_hash=config.API_HASH, session_string=session))

    async def boot_client(self, num: int, ub: Client):
        clients = {1: self.one, 2: self.two, 3: self.three}
        client = clients[num]
        await client.start()
        try:
            await client.send_message(config.LOGGER_ID, f"Assistant {num} Started")
        except:
            raise SystemExit(f"Assistant {num} failed to send message in log group.")

        client.id = client.me.id
        client.name = client.me.first_name
        client.username = client.me.username
        client.mention = client.me.mention
        self.clients.append(client)
        logger.info(f"Assistant {num} started as @{client.username}")

    async def boot(self):
        if config.SESSION1:
            await self.boot_client(1, self.one)
        if config.SESSION2:
            await self.boot_client(2, self.two)
        if config.SESSION3:
            await self.boot_client(3, self.three)

    async def exit(self):
        for client in [self.one, self.two, self.three]:
            if hasattr(self, client.__class__.__name__.lower()):
                await client.stop()
        logger.info("Assistants stopped.")

class MongoDB:
    def __init__(self):
        self.mongo = AsyncMongoClient(config.MONGO_URL, serverSelectionTimeoutMS=12500)
        self.db = self.mongo.Anon
        self.admin_list = {}
        self.active_calls = {}
        self.admin_play = []
        self.blacklisted = []
        self.cmd_delete = []
        self.notified = []
        self.cache = self.db.cache
        self.logger = False
        self.assistant = {}
        self.assistantdb = self.db.assistant
        self.auth = {}
        self.authdb = self.db.auth
        self.chats = []
        self.chatsdb = self.db.chats
        self.lang = {}
        self.langdb = self.db.lang
        self.users = []
        self.usersdb = self.db.users

    async def connect(self):
        try:
            start = time.time()
            await self.mongo.admin.command("ping")
            logger.info(f"Database connected. ({time.time() - start:.2f}s)")
            await self.load_cache()
        except Exception as e:
            raise SystemExit(f"Database connection failed: {type(e).__name__}") from e

    async def close(self):
        await self.mongo.close()
        logger.info("Database connection closed.")

    async def get_call(self, chat_id: int) -> bool:
        return chat_id in self.active_calls

    async def add_call(self, chat_id: int) -> None:
        self.active_calls[chat_id] = 1

    async def remove_call(self, chat_id: int) -> None:
        self.active_calls.pop(chat_id, None)

    async def playing(self, chat_id: int, paused: bool = None) -> bool | None:
        if paused is not None:
            self.active_calls[chat_id] = int(not paused)
        return bool(self.active_calls[chat_id])

    async def get_admins(self, chat_id: int, reload: bool = False) -> list[int]:
        if chat_id not in self.admin_list or reload:
            try:
                admins = [admin.user.id async for admin in app.get_chat_members(chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS) if not admin.user.is_bot]
                self.admin_list[chat_id] = admins
            except:
                self.admin_list[chat_id] = []
        return self.admin_list[chat_id]

    async def _get_auth(self, chat_id: int) -> set[int]:
        if chat_id not in self.auth:
            doc = await self.authdb.find_one({"_id": chat_id}) or {}
            self.auth[chat_id] = set(doc.get("user_ids", []))
        return self.auth[chat_id]

    async def is_auth(self, chat_id: int, user_id: int) -> bool:
        return user_id in await self._get_auth(chat_id)

    async def add_auth(self, chat_id: int, user_id: int) -> None:
        users = await self._get_auth(chat_id)
        if user_id not in users:
            users.add(user_id)
            await self.authdb.update_one({"_id": chat_id}, {"$addToSet": {"user_ids": user_id}}, upsert=True)

    async def rm_auth(self, chat_id: int, user_id: int) -> None:
        users = await self._get_auth(chat_id)
        if user_id in users:
            users.discard(user_id)
            await self.authdb.update_one({"_id": chat_id}, {"$pull": {"user_ids": user_id}})

    async def set_assistant(self, chat_id: int) -> int:
        num = random.randint(1, len(userbot.clients)) if userbot.clients else 1
        await self.assistantdb.update_one({"_id": chat_id}, {"$set": {"num": num}}, upsert=True)
        self.assistant[chat_id] = num
        return num

    async def get_assistant(self, chat_id: int):
        if chat_id not in self.assistant:
            doc = await self.assistantdb.find_one({"_id": chat_id})
            num = doc["num"] if doc else await self.set_assistant(chat_id)
            self.assistant[chat_id] = num
        return anon.clients[self.assistant[chat_id] - 1] if anon.clients else None

    async def get_client(self, chat_id: int):
        if chat_id not in self.assistant:
            await self.get_assistant(chat_id)
        clients_dict = {1: userbot.one, 2: userbot.two, 3: userbot.three}
        return clients_dict.get(self.assistant[chat_id])

    async def add_blacklist(self, chat_id: int) -> None:
        if str(chat_id).startswith("-"):
            self.blacklisted.append(chat_id)
            await self.cache.update_one({"_id": "bl_chats"}, {"$addToSet": {"chat_ids": chat_id}}, upsert=True)
        else:
            await self.cache.update_one({"_id": "bl_users"}, {"$addToSet": {"user_ids": chat_id}}, upsert=True)

    async def del_blacklist(self, chat_id: int) -> None:
        if str(chat_id).startswith("-"):
            if chat_id in self.blacklisted:
                self.blacklisted.remove(chat_id)
            await self.cache.update_one({"_id": "bl_chats"}, {"$pull": {"chat_ids": chat_id}})
        else:
            await self.cache.update_one({"_id": "bl_users"}, {"$pull": {"user_ids": chat_id}})

    async def get_blacklisted(self, chat: bool = False) -> list[int]:
        if chat:
            if not self.blacklisted:
                doc = await self.cache.find_one({"_id": "bl_chats"})
                self.blacklisted.extend(doc.get("chat_ids", []) if doc else [])
            return self.blacklisted
        doc = await self.cache.find_one({"_id": "bl_users"})
        return doc.get("user_ids", []) if doc else []

    async def is_chat(self, chat_id: int) -> bool:
        return chat_id in self.chats

    async def add_chat(self, chat_id: int) -> None:
        if not await self.is_chat(chat_id):
            self.chats.append(chat_id)
            await self.chatsdb.insert_one({"_id": chat_id})

    async def rm_chat(self, chat_id: int) -> None:
        if await self.is_chat(chat_id):
            self.chats.remove(chat_id)
            await self.chatsdb.delete_one({"_id": chat_id})

    async def get_chats(self) -> list:
        if not self.chats:
            self.chats.extend([chat["_id"] async for chat in self.chatsdb.find()])
        return self.chats

    async def get_cmd_delete(self, chat_id: int) -> bool:
        if chat_id not in self.cmd_delete:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            if doc and doc.get("cmd_delete"):
                self.cmd_delete.append(chat_id)
        return chat_id in self.cmd_delete

    async def set_cmd_delete(self, chat_id: int, delete: bool = False) -> None:
        if delete:
            self.cmd_delete.append(chat_id)
        else:
            if chat_id in self.cmd_delete:
                self.cmd_delete.remove(chat_id)
        await self.chatsdb.update_one({"_id": chat_id}, {"$set": {"cmd_delete": delete}}, upsert=True)

    async def set_lang(self, chat_id: int, lang_code: str):
        await self.langdb.update_one({"_id": chat_id}, {"$set": {"lang": lang_code}}, upsert=True)
        self.lang[chat_id] = lang_code

    async def get_lang(self, chat_id: int) -> str:
        if chat_id not in self.lang:
            doc = await self.langdb.find_one({"_id": chat_id})
            self.lang[chat_id] = doc["lang"] if doc else "en"
        return self.lang[chat_id]

    async def get_play_mode(self, chat_id: int) -> bool:
        if chat_id not in self.admin_play:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            if doc and doc.get("admin_play"):
                self.admin_play.append(chat_id)
        return chat_id in self.admin_play

    async def set_play_mode(self, chat_id: int, remove: bool = False) -> None:
        if remove and chat_id in self.admin_play:
            self.admin_play.remove(chat_id)
        else:
            self.admin_play.append(chat_id)
        await self.chatsdb.update_one({"_id": chat_id}, {"$set": {"admin_play": not remove}}, upsert=True)

    async def add_sudo(self, user_id: int) -> None:
        await self.cache.update_one({"_id": "sudoers"}, {"$addToSet": {"user_ids": user_id}}, upsert=True)

    async def del_sudo(self, user_id: int) -> None:
        await self.cache.update_one({"_id": "sudoers"}, {"$pull": {"user_ids": user_id}})

    async def get_sudoers(self) -> list[int]:
        doc = await self.cache.find_one({"_id": "sudoers"})
        return doc.get("user_ids", []) if doc else []

    async def is_user(self, user_id: int) -> bool:
        return user_id in self.users

    async def add_user(self, user_id: int) -> None:
        if not await self.is_user(user_id):
            self.users.append(user_id)
            await self.usersdb.insert_one({"_id": user_id})

    async def rm_user(self, user_id: int) -> None:
        if await self.is_user(user_id):
            self.users.remove(user_id)
            await self.usersdb.delete_one({"_id": user_id})

    async def get_users(self) -> list:
        if not self.users:
            self.users.extend([user["_id"] async for user in self.usersdb.find()])
        return self.users

    async def load_cache(self):
        await self.get_chats()
        await self.get_users()
        await self.get_blacklisted(True)
        logger.info("Database cache loaded.")

# ==================== HELPER CLASSES ====================
class Queue:
    def __init__(self):
        self.queues = defaultdict(deque)

    def add(self, chat_id: int, item) -> int:
        self.queues[chat_id].append(item)
        return len(self.queues[chat_id]) - 1

    def check_item(self, chat_id: int, item_id: str):
        for i, track in enumerate(list(self.queues[chat_id])):
            if hasattr(track, 'id') and track.id == item_id:
                return i, track
        return -1, None

    def force_add(self, chat_id: int, item, remove=False) -> None:
        self.remove_current(chat_id)
        self.queues[chat_id].appendleft(item)
        if remove:
            self.queues[chat_id].rotate(-remove)
            self.queues[chat_id].popleft()
            self.queues[chat_id].rotate(remove)

    def get_current(self, chat_id: int):
        return self.queues[chat_id][0] if self.queues[chat_id] else None

    def get_next(self, chat_id: int, check: bool = False):
        if not self.queues[chat_id]:
            return None
        if check:
            return self.queues[chat_id][1] if len(self.queues[chat_id]) > 1 else None
        self.queues[chat_id].popleft()
        return self.queues[chat_id][0] if self.queues[chat_id] else None

    def get_queue(self, chat_id: int) -> list:
        return list(self.queues[chat_id])

    def remove_current(self, chat_id: int) -> None:
        if self.queues[chat_id]:
            self.queues[chat_id].popleft()

    def clear(self, chat_id: int) -> None:
        self.queues[chat_id].clear()

class Inline:
    def __init__(self):
        self.ikm = types.InlineKeyboardMarkup
        self.ikb = types.InlineKeyboardButton

    def cancel_dl(self, text):
        return self.ikm([[self.ikb(text=text, callback_data="cancel_dl")]])

    def controls(self, chat_id: int, status: str = None, timer: str = None, remove: bool = False):
        keyboard = []
        if status:
            keyboard.append([self.ikb(text=status, callback_data=f"controls status {chat_id}")])
        elif timer:
            keyboard.append([self.ikb(text=timer, callback_data=f"controls status {chat_id}")])

        if not remove:
            keyboard.append([
                self.ikb(text="▷", callback_data=f"controls resume {chat_id}"),
                self.ikb(text="II", callback_data=f"controls pause {chat_id}"),
                self.ikb(text="⥁", callback_data=f"controls replay {chat_id}"),
                self.ikb(text="‣‣I", callback_data=f"controls skip {chat_id}"),
                self.ikb(text="▢", callback_data=f"controls stop {chat_id}"),
            ])
        return self.ikm(keyboard)

    def help_markup(self, _lang: dict, back: bool = False):
        if back:
            rows = [
                [self.ikb(text=_lang["back"], callback_data="help back"),
                 self.ikb(text=_lang["close"], callback_data="help close")]
            ]
        else:
            cbs = ["admins", "auth", "blist", "lang", "ping", "play", "queue", "stats", "sudo"]
            buttons = [self.ikb(text=_lang[f"help_{i}"], callback_data=f"help {cb}") for i, cb in enumerate(cbs)]
            rows = [buttons[i:i+3] for i in range(0, len(buttons), 3)]
        return self.ikm(rows)

    def lang_markup(self, _lang: str):
        langs = {"en": "English", "hi": "Hindi"}  # Simplified language list
        buttons = [self.ikb(text=f"{name} ({code}) {'✔️' if code == _lang else ''}", callback_data=f"lang_change {code}") for code, name in langs.items()]
        rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
        return self.ikm(rows)

    def ping_markup(self, text: str):
        return self.ikm([[self.ikb(text=text, url=config.SUPPORT_CHAT)]])

    def play_queued(self, chat_id: int, item_id: str, _text: str):
        return self.ikm([[self.ikb(text=_text, callback_data=f"controls force {chat_id} {item_id}")]])

    def queue_markup(self, chat_id: int, _text: str, playing: bool):
        _action = "pause" if playing else "resume"
        return self.ikm([[self.ikb(text=_text, callback_data=f"controls {_action} {chat_id} q")]])

    def settings_markup(self, lang_dict, admin_only: bool, cmd_delete: bool, language: str, chat_id: int):
        return self.ikm([
            [self.ikb(text=lang_dict["play_mode"] + " ➜", callback_data="settings"),
             self.ikb(text=str(admin_only), callback_data="settings play")],
            [self.ikb(text=lang_dict["cmd_delete"] + " ➜", callback_data="settings"),
             self.ikb(text=str(cmd_delete), callback_data="settings delete")],
            [self.ikb(text=lang_dict["language"] + " ➜", callback_data="settings"),
             self.ikb(text=language, callback_data="language")],
        ])

    def start_key(self, lang_dict, private: bool = False):
        rows = [
            [self.ikb(text=lang_dict["add_me"], url=f"https://t.me/{app.username}?startgroup=true")],
            [self.ikb(text=lang_dict["help"], callback_data="help")],
            [self.ikb(text=lang_dict["support"], url=config.SUPPORT_CHAT),
             self.ikb(text=lang_dict["channel"], url=config.SUPPORT_CHANNEL)],
        ]
        if private:
            rows.append([self.ikb(text=lang_dict["source"], url="https://github.com/AnonymousX1025/AnonXMusic")])
        else:
            rows.append([self.ikb(text=lang_dict["language"], callback_data="language")])
        return self.ikm(rows)

    def yt_key(self, link: str):
        return self.ikm([[
            self.ikb(text="❐", copy_text=link),
            self.ikb(text="Youtube", url=link),
        ]])

class Utilities:
    def format_eta(self, seconds: int) -> str:
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}:{seconds % 60:02d} min"
        else:
            h = seconds // 3600
            m = (seconds % 3600) // 60
            s = seconds % 60
            return f"{h}:{m:02d}:{s:02d} h"

    def format_size(self, bytes: int) -> str:
        if bytes >= 1024**3:
            return f"{bytes / 1024 ** 3:.2f} GB"
        elif bytes >= 1024**2:
            return f"{bytes / 1024 ** 2:.2f} MB"
        else:
            return f"{bytes / 1024:.2f} KB"

    def to_seconds(self, time_str: str) -> int:
        parts = [int(p) for p in time_str.strip().split(":")]
        return sum(value * 60**i for i, value in enumerate(reversed(parts)))

    async def extract_user(self, msg: types.Message):
        if msg.reply_to_message:
            return msg.reply_to_message.from_user

        if msg.entities:
            for e in msg.entities:
                if e.type == enums.MessageEntityType.TEXT_MENTION:
                    return e.user

        if msg.text:
            try:
                if m := re.search(r"@(\w{5,32})", msg.text):
                    return await app.get_users(m.group(0))
                if m := re.search(r"\b\d{6,15}\b", msg.text):
                    return await app.get_users(int(m.group(0)))
            except:
                pass
        return None

    async def play_log(self, m: types.Message, title: str, duration: str):
        if m.chat.id == app.logger:
            return
        _text = f"🎵 **Play Log**\n\n**Bot:** {app.name}\n**Chat:** {m.chat.id}\n**Title:** {m.chat.title}\n**User:** {m.from_user.id}\n**Mention:** {m.from_user.mention}\n**Message:** {m.link}\n**Track:** {title}\n**Duration:** {duration}"
        await app.send_message(chat_id=app.logger, text=_text)

    async def send_log(self, m: types.Message, chat: bool = False):
        if chat:
            user = m.from_user
            text = f"💬 **New Group**\n\n**Chat ID:** {m.chat.id}\n**Title:** {m.chat.title}\n**User ID:** {user.id if user else 0}\n**User:** {user.mention if user else 'Anonymous'}"
        else:
            text = f"👤 **New User**\n\n**User ID:** {m.from_user.id}\n**Username:** @{m.from_user.username}\n**Mention:** {m.from_user.mention}"
        await app.send_message(chat_id=app.logger, text=text)

class Thumbnail:
    def __init__(self):
        self.rect = (914, 514)
        self.fill = (255, 255, 255)
        self.mask = Image.new("L", self.rect, 0)
        try:
            self.font1 = ImageFont.truetype("arial.ttf", 30)
            self.font2 = ImageFont.truetype("arial.ttf", 30)
        except:
            self.font1 = self.font2 = ImageFont.load_default()

    async def save_thumb(self, output_path: str, url: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                with open(output_path, "wb") as f:
                    f.write(await resp.read())
            return output_path

    async def generate(self, song: Track, size=(1280, 720)) -> str:
        try:
            temp = f"cache/temp_{song.id}.jpg"
            output = f"cache/{song.id}.png"
            if os.path.exists(output):
                return output

            await self.save_thumb(temp, song.thumbnail)
            thumb = Image.open(temp).convert("RGBA").resize(size, Image.Resampling.LANCZOS)
            blur = thumb.filter(ImageFilter.GaussianBlur(25))
            image = ImageEnhance.Brightness(blur).enhance(.40)

            _rect = ImageOps.fit(thumb, self.rect, method=Image.LANCZOS, centering=(0.5, 0.5))
            draw = ImageDraw.Draw(self.mask)
            draw.rounded_rectangle((0, 0, self.rect[0], self.rect[1]), radius=15, fill=255)
            _rect.putalpha(self.mask)
            image.paste(_rect, (183, 30), _rect)

            draw = ImageDraw.Draw(image)
            draw.text((50, 560), f"{song.channel_name[:25]} | {song.view_count}", font=self.font2, fill=self.fill)
            draw.text((50, 600), song.title[:50], font=self.font1, fill=self.fill)
            draw.text((40, 650), "0:01", font=self.font1)
            draw.line([(140, 670), (1160, 670)], fill=self.fill, width=5, joint="curve")
            draw.text((1185, 650), song.duration, font=self.font1, fill=self.fill)

            image.save(output)
            os.remove(temp)
            return output
        except:
            return config.DEFAULT_THUMB

class YouTube:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.cookies = []
        self.checked = False
        self.warned = False
        self.regex = re.compile(r"(https?://)?(www\.|m\.|music\.)?(youtube\.com/(watch\?v=|shorts/|playlist\?list=)|youtu\.be/)([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?")

    def get_cookies(self):
        if not self.checked:
            if os.path.exists("anony/cookies"):
                for file in os.listdir("anony/cookies"):
                    if file.endswith(".txt"):
                        self.cookies.append(f"anony/cookies/{file}")
            self.checked = True
        return random.choice(self.cookies) if self.cookies else None

    def valid(self, url: str) -> bool:
        return bool(re.match(self.regex, url))

    def url(self, message_1: types.Message) -> Union[str, None]:
        messages = [message_1]
        link = None
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)

        for message in messages:
            text = message.text or message.caption or ""

            if message.entities:
                for entity in message.entities:
                    if entity.type == enums.MessageEntityType.URL:
                        link = text[entity.offset : entity.offset + entity.length]
                        break

            if message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == enums.MessageEntityType.TEXT_LINK:
                        link = entity.url
                        break

        if link:
            return link.split("&si")[0].split("?si")[0]
        return None

    async def search(self, query: str, m_id: int, video: bool = False) -> Track | None:
        try:
            results = YoutubeSearch(query, max_results=1).to_dict()
            if results:
                data = results[0]
                return Track(
                    id=data.get("id"),
                    channel_name=data.get("channel", "Unknown"),
                    duration=data.get("duration", "0:00"),
                    duration_sec=utils.to_seconds(data.get("duration", "0:00")),
                    message_id=m_id,
                    title=data.get("title", "Unknown")[:25],
                    thumbnail=f"https://i.ytimg.com/vi/{data.get('id')}/hqdefault.jpg",
                    url=f"https://youtube.com/watch?v={data.get('id')}",
                    view_count=data.get("views", "N/A"),
                    video=video,
                )
        except:
            pass
        return None

    async def playlist(self, limit: int, user: str, url: str, video: bool) -> list[Track | None]:
        tracks = []
        try:
            # Simple playlist implementation
            # You can enhance this later
            pass
        except:
            pass
        return tracks

    async def download(self, video_id: str, video: bool = False) -> Optional[str]:
        url = self.base + video_id
        ext = "mp4" if video else "webm"
        filename = f"downloads/{video_id}.{ext}"

        if os.path.exists(filename):
            return filename

        cookie = self.get_cookies()
        base_opts = {
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "quiet": True,
            "noplaylist": True,
            "geo_bypass": True,
            "no_warnings": True,
            "overwrites": False,
            "nocheckcertificate": True,
            "cookiefile": cookie,
        }

        if video:
            ydl_opts = {**base_opts, "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio)", "merge_output_format": "mp4"}
        else:
            ydl_opts = {**base_opts, "format": "bestaudio[ext=webm][acodec=opus]"}

        def _download():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                return filename
            except:
                if cookie in self.cookies:
                    self.cookies.remove(cookie)
                return None

        return await asyncio.to_thread(_download)

class Telegram:
    def __init__(self):
        self.active = []
        self.events = {}
        self.last_edit = {}
        self.active_tasks = {}
        self.sleep = 5

    def get_media(self, msg: types.Message) -> bool:
        return any([msg.video, msg.audio, msg.document, msg.voice])

    async def download(self, msg: types.Message, sent: types.Message) -> Media | None:
        msg_id = sent.id
        event = asyncio.Event()
        self.events[msg_id] = event
        self.last_edit[msg_id] = 0
        start_time = time.time()

        media = msg.audio or msg.voice or msg.video or msg.document
        file_id = getattr(media, "file_unique_id", None)
        file_ext = getattr(media, "file_name", "").split(".")[-1] or "mp3"
        file_size = getattr(media, "file_size", 0)
        file_title = getattr(media, "title", "Telegram File") or "Telegram File"
        duration = getattr(media, "duration", 0)
        video = bool(getattr(media, "mime_type", "").startswith("video/"))

        if duration > config.DURATION_LIMIT:
            await sent.edit_text(f"Duration limit exceeded. Max: {config.DURATION_LIMIT // 60} minutes")
            return None

        if file_size > 200 * 1024 * 1024:
            await sent.edit_text("File size too large. Max: 200MB")
            return None

        async def progress(current, total):
            if event.is_set():
                return

            now = time.time()
            if now - self.last_edit[msg_id] < self.sleep:
                return

            self.last_edit[msg_id] = now
            percent = current * 100 / total
            speed = current / (now - start_time or 1e-6)
            eta = utils.format_eta(int((total - current) / speed))
            text = f"Downloading...\n{utils.format_size(current)} / {utils.format_size(total)} ({percent:.1f}%)\nSpeed: {utils.format_size(speed)}/s\nETA: {eta}"

            await sent.edit_text(text, reply_markup=buttons.cancel_dl("Cancel"))

        try:
            file_path = f"downloads/{file_id}.{file_ext}"
            if not os.path.exists(file_path):
                if file_id in self.active:
                    await sent.edit_text("File already being downloaded")
                    return None

                self.active.append(file_id)
                task = asyncio.create_task(msg.download(file_name=file_path, progress=progress))
                self.active_tasks[msg_id] = task
                await task
                self.active.remove(file_id)
                self.active_tasks.pop(msg_id, None)
                await sent.edit_text(f"Download complete! ({round(time.time() - start_time, 2)}s)")

            return Media(
                id=file_id,
                duration=time.strftime("%M:%S", time.gmtime(duration)),
                duration_sec=duration,
                file_path=file_path,
                message_id=sent.id,
                url=msg.link,
                title=file_title[:25],
                video=video,
            )
        except asyncio.CancelledError:
            return None
        finally:
            self.events.pop(msg_id, None)
            self.last_edit.pop(msg_id, None)
            self.active = [f for f in self.active if f != file_id]

    async def cancel(self, query: types.CallbackQuery):
        event = self.events.get(query.message.id)
        task = self.active_tasks.pop(query.message.id, None)
        if event:
            event.set()

        if task and not task.done():
            task.cancel()
        if event or task:
            await query.edit_message_text(f"Download cancelled by {query.from_user.mention}")
        else:
            await query.answer("No active download found", show_alert=True)

class TgCall(PyTgCalls):
    def __init__(self):
        self.clients = []

    async def pause(self, chat_id: int) -> bool:
        client = await db.get_assistant(chat_id)
        await db.playing(chat_id, paused=True)
        return await client.pause(chat_id)

    async def resume(self, chat_id: int) -> bool:
        client = await db.get_assistant(chat_id)
        await db.playing(chat_id, paused=False)
        return await client.resume(chat_id)

    async def stop(self, chat_id: int) -> None:
        client = await db.get_assistant(chat_id)
        try:
            queue.clear(chat_id)
            await db.remove_call(chat_id)
        except:
            pass

        try:
            await client.leave_call(chat_id, close=False)
        except:
            pass

    async def play_media(self, chat_id: int, message: types.Message, media: Media | Track, seek_time: int = 0) -> None:
        client = await db.get_assistant(chat_id)
        _lang = await lang.get_lang(chat_id)
        _thumb = await thumb.generate(media) if isinstance(media, Track) else config.DEFAULT_THUMB

        if not media.file_path:
            return await message.edit_text(f"File not found. Please contact {config.SUPPORT_CHAT}")

                    if media.video:
                stream = MediaStream(
                    media_path=media.file_path,
                    audio_parameters=AudioQuality.HIGH,
                    video_parameters=VideoQuality.HD_720p,
                    ffmpeg_parameters=f"-ss {seek_time}" if seek_time > 1 else None,
                )
            else:
                stream = MediaStream(
                    media_path=media.file_path,
                    audio_parameters=AudioQuality.HIGH,
                    video_parameters=VideoQuality.HD_720p,
                    no_video=True,
                    ffmpeg_parameters=f"-ss {seek_time}" if seek_time > 1 else None,
                )
        try:
            await client.play(chat_id=chat_id, stream=stream, config=GroupCallConfig(auto_start=False))
            if not seek_time:
                media.time = 1
                await db.add_call(chat_id)
                text = f"🎵 **Now Playing**\n\n**Title:** [{media.title}]({media.url})\n**Duration:** {media.duration}\n**Requested by:** {media.user}"
                keyboard = buttons.controls(chat_id)
                try:
                    await message.edit_media(media=types.InputMediaPhoto(media=_thumb, caption=text), reply_markup=keyboard)
                except MessageIdInvalid:
                    new_msg = await app.send_photo(chat_id=chat_id, photo=_thumb, caption=text, reply_markup=keyboard)
                    media.message_id = new_msg.id
        except FileNotFoundError:
            await message.edit_text(f"File not found. Please contact {config.SUPPORT_CHAT}")
            await self.play_next(chat_id)
        except exceptions.NoActiveGroupCall:
            await self.stop(chat_id)
            await message.edit_text("No active voice chat found.")
        except exceptions.NoAudioSourceFound:
            await message.edit_text("No audio source found in file.")
            await self.play_next(chat_id)
        except (ConnectionNotFound, TelegramServerError):
            await self.stop(chat_id)
            await message.edit_text("Telegram server error.")

    async def replay(self, chat_id: int) -> None:
        if not await db.get_call(chat_id):
            return

        media = queue.get_current(chat_id)
        msg = await app.send_message(chat_id=chat_id, text="Replaying...")
        await self.play_media(chat_id, msg, media)

    async def play_next(self, chat_id: int) -> None:
        if not await db.get_call(chat_id):
            return

        media = queue.get_next(chat_id)
        try:
            if media and media.message_id:
                await app.delete_messages(chat_id=chat_id, message_ids=media.message_id, revoke=True)
                media.message_id = 0
        except:
            pass

        if not media:
            return await self.stop(chat_id)

        msg = await app.send_message(chat_id=chat_id, text="Playing next...")
        if not media.file_path:
            media.file_path = await yt.download(media.id, video=media.video)
            if not media.file_path:
                await self.stop(chat_id)
                return await msg.edit_text(f"Download failed. Please contact {config.SUPPORT_CHAT}")

        media.message_id = msg.id
        await self.play_media(chat_id, msg, media)

    async def ping(self) -> float:
        pings = [client.ping for client in self.clients]
        return round(sum(pings) / len(pings), 2) if pings else 0.0

    async def decorators(self, client: PyTgCalls) -> None:
        @client.on_update()
        async def update_handler(_, update: Update) -> None:
            if isinstance(update, StreamEnded):
                if update.stream_type == StreamEnded.Type.AUDIO:
                    await self.play_next(update.chat_id)
            elif isinstance(update, ChatUpdate):
                if update.status in [ChatUpdate.Status.KICKED, ChatUpdate.Status.LEFT_GROUP, ChatUpdate.Status.CLOSED_VOICE_CHAT]:
                    await self.stop(update.chat_id)

    async def boot(self) -> None:
        for ub in userbot.clients:
            client = PyTgCalls(ub, cache_duration=100)
            await client.start()
            self.clients.append(client)
            await self.decorators(client)
        logger.info("PyTgCalls client(s) started.")

# ==================== LANGUAGE SYSTEM ====================
class Language:
    def __init__(self):
        self.languages = {
            "en": {
                "start_pm": "Hello {}! I'm {} - A advanced telegram music bot.",
                "start_gp": "Hello! I'm {} - A music bot for groups.",
                "add_me": "Add Me",
                "help": "Help",
                "support": "Support",
                "channel": "Channel",
                "source": "Source Code",
                "language": "Language",
                "pinging": "Pinging...",
                "ping_pong": "**Pong!**\n\n**Latency:** {}ms\n**Uptime:** {}\n**CPU:** {}%\n**RAM:** {}%\n**Disk:** {}%\n**VC Ping:** {}ms",
                "not_playing": "Nothing is playing right now.",
                "play_searching": "Searching...",
                "play_queued": "**Added to queue**\n\n**Position:** {}\n**Title:** [{}]({})\n**Duration:** {}\n**Requested by:** {}",
                "play_now": "Play Now",
            },
            "hi": {
                "start_pm": "नमस्ते {}! मैं {} हूँ - एक एडवांस्ड टेलीग्राम म्यूजिक बॉट।",
                "start_gp": "नमस्ते! मैं {} हूँ - ग्रुप्स के लिए एक म्यूजिक बॉट।",
                "add_me": "मुझे जोड़ें",
                "help": "मदद",
                "support": "सपोर्ट",
                "channel": "चैनल",
                "source": "सोर्स कोड",
                "language": "भाषा",
                "pinging": "पिंग कर रहा हूं...",
                "ping_pong": "**पोंग!**\n\n**लेटेंसी:** {}ms\n**अपटाइम:** {}\n**CPU:** {}%\n**RAM:** {}%\n**डिस्क:** {}%\n**VC पिंग:** {}ms",
                "not_playing": "अभी कुछ नहीं चल रहा है।",
                "play_searching": "खोज रहा हूं...",
                "play_queued": "**कतार में जोड़ा गया**\n\n**पोजीशन:** {}\n**टाइटल:** [{}]({})\n**अवधि:** {}\n**द्वारा अनुरोध:** {}",
                "play_now": "अभी चलाएं",
            }
        }

    def language(self, func):
        @wraps(func)
        async def wrapper(_, m: types.Message, *args, **kwargs):
            lang_code = await db.get_lang(m.chat.id)
            m.lang = self.languages.get(lang_code, self.languages["en"])
            return await func(_, m, *args, **kwargs)
        return wrapper

    async def get_lang(self, chat_id: int) -> dict:
        lang_code = await db.get_lang(chat_id)
        return self.languages.get(lang_code, self.languages["en"])

    def get_languages(self) -> dict:
        return {"en": "English", "hi": "Hindi"}

# ==================== DECORATORS ====================
def admin_check(func):
    @wraps(func)
    async def wrapper(_, update: types.Message | types.CallbackQuery, *args, **kwargs):
        async def reply(text):
            if isinstance(update, types.Message):
                return await update.reply_text(text)
            else:
                return await update.answer(text, show_alert=True)

        chat_id = update.chat.id if isinstance(update, types.Message) else update.message.chat.id
        user_id = update.from_user.id
        admins = await db.get_admins(chat_id)

        if user_id in app.sudoers:
            return await func(_, update, *args, **kwargs)

        if user_id not in admins:
            return await reply("You need to be an admin to use this command.")

        return await func(_, update, *args, **kwargs)
    return wrapper

def can_manage_vc(func):
    @wraps(func)
    async def wrapper(_, update: types.Message | types.CallbackQuery, *args, **kwargs):
        chat_id = update.chat.id if isinstance(update, types.Message) else update.message.chat.id
        user_id = update.from_user.id

        if user_id in app.sudoers:
            return await func(_, update, *args, **kwargs)

        if await db.is_auth(chat_id, user_id):
            return await func(_, update, *args, **kwargs)

        admins = await db.get_admins(chat_id)
        if user_id in admins:
            return await func(_, update, *args, **kwargs)

        if isinstance(update, types.Message):
            return await update.reply_text("You don't have permission to manage VC.")
        else:
            return await update.answer("You don't have permission to manage VC.", show_alert=True)
    return wrapper

# ==================== GLOBAL INSTANCES ====================
app = Bot()
userbot = Userbot()
db = MongoDB()
queue = Queue()
buttons = Inline()
utils = Utilities()
thumb = Thumbnail()
yt = YouTube()
tg = Telegram()
anon = TgCall()
lang = Language()

tasks = []
boot = time.time()

# ==================== HANDLERS ====================
@app.on_message(filters.command(["start"]))
@lang.language()
async def start_handler(_, message: types.Message):
    if message.from_user.id in app.bl_users:
        return await message.reply_text("You are blacklisted.")

    private = message.chat.type == enums.ChatType.PRIVATE
    _text = message.lang["start_pm"].format(message.from_user.first_name, app.name) if private else message.lang["start_gp"].format(app.name)

    key = buttons.start_key(message.lang, private)
    await message.reply_photo(photo=config.START_IMG, caption=_text, reply_markup=key, quote=not private)

    if private:
        if not await db.is_user(message.from_user.id):
            await utils.send_log(message)
            await db.add_user(message.from_user.id)
    else:
        if not await db.is_chat(message.chat.id):
            await utils.send_log(message, True)
            await db.add_chat(message.chat.id)

@app.on_message(filters.command(["play", "vplay"]) & filters.group)
@lang.language()
async def play_handler(_, m: types.Message):
    if not m.from_user:
        return await m.reply_text("Invalid user.")

    if m.chat.type != enums.ChatType.SUPERGROUP:
        await m.reply_text("This command works only in supergroups.")
        return await app.leave_chat(m.chat.id)

    if not m.reply_to_message and len(m.command) < 2:
        return await m.reply_text("Usage: /play song_name or reply to audio file")

    if len(queue.get_queue(m.chat.id)) >= config.QUEUE_LIMIT:
        return await m.reply_text(f"Queue is full. Max: {config.QUEUE_LIMIT}")

    video = m.command[0] == "vplay" and config.VIDEO_PLAY
    url = yt.url(m)
    
    if url and not yt.valid(url):
        return await m.reply_text("Unsupported URL.")

    sent = await m.reply_text(m.lang["play_searching"])
    file = None

    if url:
        if "playlist" in url:
            tracks = await yt.playlist(config.PLAYLIST_LIMIT, m.from_user.mention, url, video)
            if tracks:
                file = tracks[0]
                tracks.remove(file)
                file.message_id = sent.id
        else:
            file = await yt.search(url, sent.id, video=video)
    elif len(m.command) >= 2:
        query = " ".join(m.command[1:])
        file = await yt.search(query, sent.id, video=video)
    elif m.reply_to_message and tg.get_media(m.reply_to_message):
        file = await tg.download(m.reply_to_message, sent)

    if not file:
        return await sent.edit_text("No results found.")

    if file.duration_sec > config.DURATION_LIMIT:
        return await sent.edit_text(f"Duration too long. Max: {config.DURATION_LIMIT // 60} minutes")

    file.user = m.from_user.mention
    position = queue.add(m.chat.id, file)

    if await db.get_call(m.chat.id):
        await sent.edit_text(
            m.lang["play_queued"].format(position, file.url, file.title, file.duration, m.from_user.mention),
            reply_markup=buttons.play_queued(m.chat.id, file.id, m.lang["play_now"])
        )
        return

    if not file.file_path:
        await sent.edit_text("Downloading...")
        file.file_path = await yt.download(file.id, video=video)

    await anon.play_media(chat_id=m.chat.id, message=sent, media=file)

@app.on_message(filters.command(["skip", "next"]) & filters.group)
@lang.language()
@can_manage_vc
async def skip_handler(_, m: types.Message):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])

    await anon.play_next(m.chat.id)
    await m.reply_text(f"Skipped by {m.from_user.mention}")

@app.on_message(filters.command(["pause"]) & filters.group)
@lang.language()
@can_manage_vc
async def pause_handler(_, m: types.Message):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])

    if not await db.playing(m.chat.id):
        return await m.reply_text("Already paused.")

    await anon.pause(m.chat.id)
    await m.reply_text(f"Paused by {m.from_user.mention}", reply_markup=buttons.controls(m.chat.id))

@app.on_message(filters.command(["resume"]) & filters.group)
@lang.language()
@can_manage_vc
async def resume_handler(_, m: types.Message):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])

    if await db.playing(m.chat.id):
        return await m.reply_text("Not paused.")

    await anon.resume(m.chat.id)
    await m.reply_text(f"Resumed by {m.from_user.mention}", reply_markup=buttons.controls(m.chat.id))

@app.on_message(filters.command(["end", "stop"]) & filters.group)
@lang.language()
@can_manage_vc
async def stop_handler(_, m: types.Message):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])

    await anon.stop(m.chat.id)
    await m.reply_text(f"Stopped by {m.from_user.mention}")

@app.on_message(filters.command(["ping", "alive"]))
@lang.language()
async def ping_handler(_, m: types.Message):
    start = time.time()
    sent = await m.reply_text(m.lang["pinging"])
    latency = round((time.time() - start) * 1000, 2)
    
    # Simple uptime calculation
    uptime_seconds = int(time.time() - boot)
    uptime_str = f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s"
    
    await sent.edit_media(
        media=types.InputMediaPhoto(
            media=config.PING_IMG,
            caption=m.lang["ping_pong"].format(
                latency,
                uptime_str,
                psutil.cpu_percent(),
                psutil.virtual_memory().percent,
                psutil.disk_usage("/").percent,
                await anon.ping(),
            )
        ),
        reply_markup=buttons.ping_markup("Support")
    )

@app.on_callback_query(filters.regex("controls"))
@lang.language()
@can_manage_vc
async def controls_handler(_, query: types.CallbackQuery):
    args = query.data.split()
    if len(args) < 3:
        return await query.answer()

    action, chat_id = args[1], int(args[2])

    if action == "status":
        return await query.answer()

    if not await db.get_call(chat_id):
        return await query.answer("Nothing is playing", show_alert=True)

    await query.answer("Processing...")

    if action == "pause":
        if not await db.playing(chat_id):
            return await query.answer("Already paused", show_alert=True)
        await anon.pause(chat_id)
        await query.edit_message_reply_markup(reply_markup=buttons.controls(chat_id, status="Paused"))
    elif action == "resume":
        if await db.playing(chat_id):
            return await query.answer("Not paused", show_alert=True)
        await anon.resume(chat_id)
        await query.edit_message_reply_markup(reply_markup=buttons.controls(chat_id))
    elif action == "skip":
        await anon.play_next(chat_id)
        await query.message.delete()
    elif action == "stop":
        await anon.stop(chat_id)
        await query.message.delete()

@app.on_callback_query(filters.regex("cancel_dl"))
async def cancel_dl_handler(_, query: types.CallbackQuery):
    await tg.cancel(query)

# ==================== BACKGROUND TASKS ====================
async def track_time():
    while True:
        await asyncio.sleep(1)
        for chat_id in db.active_calls:
            if await db.playing(chat_id):
                media = queue.get_current(chat_id)
                if media:
                    media.time += 1

async def update_timer():
    while True:
        await asyncio.sleep(7)
        for chat_id in db.active_calls:
            if await db.playing(chat_id):
                try:
                    media = queue.get_current(chat_id)
                    if media and media.message_id:
                        await app.edit_message_reply_markup(
                            chat_id=chat_id,
                            message_id=media.message_id,
                            reply_markup=buttons.controls(chat_id, timer=f"🕒 {media.time}s")
                        )
                except:
                    pass

# ==================== MAIN FUNCTION ====================
async def stop():
    logger.info("Stopping...")
    for task in tasks:
        task.cancel()
    await app.exit()
    await userbot.exit()
    await db.close()
    logger.info("Stopped.")

async def main():
    # Ensure directories
    Path("cache").mkdir(exist_ok=True)
    Path("downloads").mkdir(exist_ok=True)
    
    await db.connect()
    await app.boot()
    await userbot.boot()
    await anon.boot()

    # Load sudoers
    sudoers = await db.get_sudoers()
    app.sudoers.update(sudoers)
    app.bl_users.update(await db.get_blacklisted())
    logger.info(f"Loaded {len(app.sudoers)} sudo users.")

    # Start background tasks
    tasks.append(asyncio.create_task(track_time()))
    tasks.append(asyncio.create_task(update_timer()))

    logger.info("Bot started successfully!")
    await idle()
    await stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Error: {e}")
