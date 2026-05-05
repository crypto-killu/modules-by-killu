# ◇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◇
# meta developer: @dubai_ip
# meta banner: https://raw.githubusercontent.com/crypto-killu/modules-by-killu/main/Module-banners/PMTracker.jpg
# scope: Heroku_only
# version: 2.1
# author: Killu
# desc: Модуль для сохранения удаленных сообщений в личках.
# ◇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◇

import io
import logging
import time
import aiohttp
from telethon.tl.types import DocumentAttributeFilename, Message, PeerUser, UpdateDeleteMessages
from telethon.utils import get_display_name
from aiogram.types import BufferedInputFile
from .. import loader, utils
from telethon.tl.functions.channels import EditPhotoRequest
from telethon.tl.types import InputChatUploadedPhoto

logger = logging.getLogger(__name__)


@loader.tds
class PMTracker(loader.Module):
    """Отслеживает удалённые сообщения в личных чатах"""

    strings = {
        "name": "PMTracker",
        "state": "<tg-emoji emoji-id=5433731759470578315>😎</tg-emoji> <b>Отслеживание удалённых сообщений {}</b>",
        "mode_off": "<tg-emoji emoji-id=5433731759470578315>😎</tg-emoji> <b>Отслеживание выключено</b>",
        "deleted_pm": "<tg-emoji emoji-id=5433731759470578315>😎</tg-emoji> <b><a href='{}'>{}</a> удалил сообщение</b>",
        "deleted_pm_with_text": "<tg-emoji emoji-id=5433731759470578315>😎</tg-emoji> <b><a href='{}'>{}</a> удалил сообщение</b>\n\n<b>Содержимое:</b>\n\n{}",
        "on": "включено",
        "off": "выключено",
        "cfg_fw_protect": "Задержка между отправками (сек) для защиты от флуда",
        "cfg_device_type": "Тип вашего устройства (влияет на формат ссылки на профиль)",
        "cfg_max_bulk_delete": "Максимальное количество удалённых сообщений за раз, чтобы не считать это очисткой истории (0 = отключить игнор)",
        "sd_media": "<tg-emoji emoji-id=5434035134485532499>👬</tg-emoji> <b><a href='https://t.me/@id{}'>{}</a> отправил самоуничтожающееся медиа</b>",
        "save_sd": "<tg-emoji emoji-id=5434035134485532499>👬</tg-emoji> <b>Сохраняю самоуничтожающееся медиа</b>\n",
        "cfg_save_sd": "Сохранять самоуничтожающиеся медиа",
        "info_enabled": "<tg-emoji emoji-id=5433731759470578315>😎</tg-emoji> <b>Отслеживание включено</b>\n",
        "device_iphone": "iPhone (ссылка https://t.me/@id)",
        "device_android": "Android (ссылка tg://openmessage?user_id=)",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue("fw_protect", 3.0, lambda: self.strings("cfg_fw_protect"), validator=loader.validators.Float(minimum=0.0)),
            loader.ConfigValue("save_sd", True, lambda: self.strings("cfg_save_sd"), validator=loader.validators.Boolean()),
            loader.ConfigValue("device_type", "iphone", lambda: self.strings("cfg_device_type"), validator=loader.validators.Choice(["iphone", "android"])),
            loader.ConfigValue("max_bulk_delete", 5, lambda: self.strings("cfg_max_bulk_delete"), validator=loader.validators.Integer(minimum=0)),
        )
        self._queue = []
        self._cache = {}
        self._next = 0
        self._channel = None

    @loader.loop(interval=0.1, autostart=True)
    async def sender(self):
        if not self._queue or self._next > time.time():
            return
        item = self._queue.pop(0)
        await item
        self._next = time.time() + self.config["fw_protect"]

    async def client_ready(self):
        channel, _ = await utils.asset_channel(
            self._client,
            "pmtracker",
            "Сюда сохраняются удалённые сообщения из личных чатов",
            silent=True,
            invite_bot=True,
            _folder="hikka",
        )
        self._channel = int(f"-100{channel.id}")

        # Установка аватарки канала, только если у канала нет фото
        try:
            # Получаем полную информацию о канале
            full_channel = await self._client.get_entity(self._channel)
            # Проверяем наличие фото
            if not getattr(full_channel, 'photo', None):
                async with aiohttp.ClientSession() as session:
                    async with session.get("https://x0.at/5imI.jpg") as resp:
                        if resp.status == 200:
                            photo_bytes = await resp.read()
                            file = await self._client.upload_file(photo_bytes, file_name="avatar.jpg")
                            input_photo = InputChatUploadedPhoto(file)
                            await self._client(EditPhotoRequest(
                                channel=self._channel,
                                photo=input_photo
                            ))
                            logger.info("Аватарка канала PMTracker установлена (ранее не было)")
                        else:
                            logger.warning(f"Не удалось скачать аватарку: HTTP {resp.status}")
            else:
                logger.info("У канала уже есть аватарка, пропускаем установку")
        except Exception as e:
            logger.exception(f"Ошибка при проверке/установке аватарки канала: {e}")

    @loader.command(name="pmtrack", ru_doc="Включить/выключить отслеживание удалённых сообщений")
    async def pmtrackcmd(self, message: Message):
        """Включить или выключить режим"""
        state = self.get("state", False)
        new_state = not state
        self.set("state", new_state)
        await utils.answer(message, self.strings("state").format(self.strings("on" if new_state else "off")))

    @loader.command(name="pminfo", ru_doc="Показать текущий статус")
    async def pminfocmd(self, message: Message):
        """Показать, включён ли трекинг"""
        if not self.get("state", False):
            await utils.answer(message, self.strings("mode_off"))
            return
        info = self.strings("info_enabled")
        if self.config["save_sd"]:
            info += self.strings("save_sd")
        device = "iPhone" if self.config["device_type"] == "iphone" else "Android"
        info += f"\n<b>Тип устройства:</b> {device}"
        info += "\n<b>Его можно изменить командой:</b>\n<code>.cfg PMTracker device_type</code>"
        info += f"\n\n<b>Игнорировать массовое удаление (> {self.config['max_bulk_delete']} сообщений)</b>"
        await utils.answer(message, info)

    async def _get_profile_link(self, user_id: int) -> str:
        if self.config["device_type"] == "iphone":
            return f"https://t.me/@id{user_id}"
        else:
            return f"tg://openmessage?user_id={user_id}"

    async def _message_deleted(self, msg_obj: Message, caption: str):
        caption = self.inline.sanitise_text(caption)

        # Стикеры
        if msg_obj.sticker:
            self._queue.append(
                self.inline.bot.send_message(
                    self._channel, caption + "\n\n&lt;sticker&gt;",
                    disable_web_page_preview=True,
                    parse_mode='HTML'
                )
            )
            return

        # Голосовые сообщения
        if msg_obj.voice:
            file_bytes = await self._client.download_media(msg_obj.voice, bytes)
            file_io = io.BytesIO(file_bytes)
            file_io.seek(0)
            file_io.name = "voice.ogg"
            self._queue.append(
                self.inline.bot.send_voice(
                    self._channel,
                    BufferedInputFile(file_io.getvalue(), filename=file_io.name),
                    caption=caption,
                    parse_mode='HTML'
                )
            )
            return

        # Если нет медиа
        if not msg_obj.photo and not msg_obj.video and not msg_obj.document:
            self._queue.append(
                self.inline.bot.send_message(
                    self._channel, caption,
                    disable_web_page_preview=True,
                    parse_mode='HTML'
                )
            )
            return

        # Скачиваем медиа
        file_bytes = await self._client.download_media(msg_obj, bytes)
        file_io = io.BytesIO(file_bytes)
        file_io.seek(0)

        if msg_obj.photo:
            file_io.name = "photo.jpg"
            self._queue.append(
                self.inline.bot.send_photo(
                    self._channel,
                    BufferedInputFile(file_io.getvalue(), filename=file_io.name),
                    caption=caption,
                    parse_mode='HTML'
                )
            )
        elif msg_obj.video:
            file_io.name = "video.mp4"
            self._queue.append(
                self.inline.bot.send_video(
                    self._channel,
                    BufferedInputFile(file_io.getvalue(), filename=file_io.name),
                    caption=caption,
                    parse_mode='HTML'
                )
            )
        elif msg_obj.document:
            name = next((a.file_name for a in msg_obj.document.attributes if isinstance(a, DocumentAttributeFilename)), "file")
            file_io.name = name
            self._queue.append(
                self.inline.bot.send_document(
                    self._channel,
                    BufferedInputFile(file_io.getvalue(), filename=file_io.name),
                    caption=caption,
                    parse_mode='HTML'
                )
            )
        else:
            self._queue.append(
                self.inline.bot.send_message(
                    self._channel, caption,
                    disable_web_page_preview=True,
                    parse_mode='HTML'
                )
            )

    @loader.raw_handler(UpdateDeleteMessages)
    async def delete_handler(self, update: UpdateDeleteMessages):
        if not self.get("state", False):
            return

        # Игнорируем массовое удаление (очистка истории)
        max_bulk = self.config["max_bulk_delete"]
        if max_bulk > 0 and len(update.messages) > max_bulk:
            logger.debug(f"Пропускаем массовое удаление {len(update.messages)} сообщений (лимит {max_bulk})")
            return

        for mid in update.messages:
            if mid not in self._cache:
                continue
            msg = self._cache.pop(mid)
            if not isinstance(msg.peer_id, PeerUser):
                continue
            sender = await self._client.get_entity(msg.sender_id, exp=0)
            if sender.bot:
                continue
            profile_link = await self._get_profile_link(sender.id)
            display_name = utils.escape_html(get_display_name(sender))
            text = msg.text or ""
            if text.strip():
                quoted_text = f"<blockquote>{text}</blockquote>"
                caption = self.strings("deleted_pm_with_text").format(
                    profile_link,
                    display_name,
                    quoted_text,
                )
            else:
                caption = self.strings("deleted_pm").format(profile_link, display_name)
            await self._message_deleted(msg, caption)

    @loader.watcher("in")
    async def watcher(self, message: Message):
        if not message.is_private:
            return
        self._cache[message.id] = message

        # Самоуничтожающиеся медиа
        if self.config["save_sd"] and getattr(message, "media", False) and getattr(message.media, "ttl_seconds", False):
            file_bytes = await self._client.download_media(message.media, bytes)
            file_io = io.BytesIO(file_bytes)
            file_io.seek(0)
            sender = await self._client.get_entity(message.sender_id, exp=0)
            profile_link = await self._get_profile_link(sender.id)
            base_caption = f"<tg-emoji emoji-id=5434035134485532499>👬</tg-emoji> <b><a href='{profile_link}'>{utils.escape_html(get_display_name(sender))}</a> отправил самоуничтожающееся медиа</b>"
            if message.text:
                base_caption += f"\n\n<b>Подпись:</b>\n<blockquote>{message.text}</blockquote>"

            # Определяем тип самоуничтожающегося медиа
            if message.photo:
                file_io.name = "sd_photo.jpg"
                await self.inline.bot.send_photo(
                    self._channel,
                    BufferedInputFile(file_io.getvalue(), filename=file_io.name),
                    caption=base_caption,
                    parse_mode='HTML'
                )
            elif message.video:
                file_io.name = "sd_video.mp4"
                await self.inline.bot.send_video(
                    self._channel,
                    BufferedInputFile(file_io.getvalue(), filename=file_io.name),
                    caption=base_caption,
                    parse_mode='HTML'
                )
            elif message.voice:
                file_io.name = "sd_voice.ogg"
                await self.inline.bot.send_voice(
                    self._channel,
                    BufferedInputFile(file_io.getvalue(), filename=file_io.name),
                    caption=base_caption,
                    parse_mode='HTML'
                )
            elif message.document:
                name = next((a.file_name for a in message.document.attributes if isinstance(a, DocumentAttributeFilename)), "file")
                file_io.name = name
                await self.inline.bot.send_document(
                    self._channel,
                    BufferedInputFile(file_io.getvalue(), filename=file_io.name),
                    caption=base_caption,
                    parse_mode='HTML'
                )
