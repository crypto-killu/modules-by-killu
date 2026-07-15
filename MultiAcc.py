# ◇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◇
# meta developer: @dubai_ip
# meta pic: https://raw.githubusercontent.com/crypto-killu/modules-by-killu/main/Module-banners/MultiAcc.jpg
# scope: Heroku_only
# version: 3.1
# author: Killu
# desc: Управление всеми своими твинк аккаунтами в Telegram
# ◇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◇

import asyncio
import logging
import re
import json
import io
from datetime import datetime

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.channels import LeaveChannelRequest, JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest, GetMessagesViewsRequest
from telethon.tl.functions.contacts import BlockRequest
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    FloodWaitError,
    UserAlreadyParticipantError,
    InviteHashExpiredError,
    InviteHashInvalidError,
    ChannelPrivateError,
    RPCError,
)

from .. import loader, utils
from ..inline.types import InlineCall

logger = logging.getLogger(__name__)

DB_KEY_SESSIONS = "tvink-accs-sessions_v2"


@loader.tds
class MultiAccMod(loader.Module):
    """Управление всеми своими твинк аккаунтами в Telegram"""

    strings = {
        "name": "MultiAcc",
        "processing": "<tg-emoji emoji-id=5332739932832146628>☯️</tg-emoji> <b>Обрабатываю...</b>",
        "no_accounts": "<tg-emoji emoji-id=5456307331644037599>🌘</tg-emoji> <b>Нет подключённых аккаунтов.</b>\nДобавь через <code>.addtvink</code> и номер",
        "acc_added": "<tg-emoji emoji-id=5458805056990119991>🌘</tg-emoji> <b>Аккаунт добавлен:</b>\n👤 {name}\n📱 +{phone}\n🆔 {user_id}",
        "acc_error": "<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> <b>Ошибка:</b> <code>{err}</code>",
        "usage_addtvink": "<tg-emoji emoji-id=5456313473447268204>🌘</tg-emoji> <b>Использование:</b>\n<code>.addtvink +8801349872616</code> (пробелы не важны)",
        "code_sent": (
            "<tg-emoji emoji-id=5456669715214665877>🌘</tg-emoji> <b>Код отправлен на +{phone}</b>\n\n"
            "Введи его командой:\n"
            "<code>.confirmcode +{phone}</code> КОД\n\n"
            "Если есть 2FA пароль:\n"
            "<code>.confirmcode +{phone}</code> КОД ПАРОЛЬ"
        ),
        "no_pending": "<tg-emoji emoji-id=5456307331644037599>🌘</tg-emoji> Нет ожидающего кода для этого номера. Сначала запусти <code>.addtvink</code>",
        "need_2fa": (
            "<tg-emoji emoji-id=5456217626957091223>🌘</tg-emoji> <b>Требуется 2FA пароль!</b>\n"
            "Введи: <code>.confirmcode +{phone} {code}</code> 2FA_ПАРОЛЬ"
        ),
        "code_invalid": "<tg-emoji emoji-id=5456307331644037599>🌘</tg-emoji> Неверный код. Попробуй ещё раз",
        "acc_list_header": "<tg-emoji emoji-id=5458851476996657778>🌘</tg-emoji> <b>Подключённые аккаунты ({count}):</b>\n\n",
        "acc_list_item": "{i}. 👤 <b>{name}</b> {uname}\n    📱 +{phone}\n    🆔 {user_id}\n",
        "usage_delacc": "<tg-emoji emoji-id=5456307331644037599>🌘</tg-emoji> Использование: <code>.delacc 1</code> (номер из <code>.acclist</code>)",
        "acc_not_found": "<tg-emoji emoji-id=5456307331644037599>🌘</tg-emoji> Аккаунт с таким номером не найден",
        "acc_removed": "<tg-emoji emoji-id=5458572596180193103>🌘</tg-emoji> <b>Аккаунт удалён:</b> {name}",
        "usage_join": "<tg-emoji emoji-id=5456307331644037599>🌘</tg-emoji> Использование: <code>.join https://t.me/channel</code>",
        "join_header": "<tg-emoji emoji-id=5458502532378693210>🌘</tg-emoji> <b>Результат вступления:</b>\n\n",
        "join_ok": "<tg-emoji emoji-id=5458805056990119991>🌘</tg-emoji> {name}",
        "join_already": "️<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> {name} — уже в чате",
        "join_fail": "<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> {name}: {err}",
        "usage_leave": "<tg-emoji emoji-id=5456307331644037599>🌘</tg-emoji> Использование: <code>.leavechat https://t.me/channel</code>",
        "leave_header": "<tg-emoji emoji-id=5458567764341985638>🌘</tg-emoji> <b>Результат выхода из чата/канала:</b>\n\n",
        "leave_ok": "<tg-emoji emoji-id=5458805056990119991>🌘</tg-emoji> {name} — покинул(а)",
        "leave_not_member": "<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> {name} — не состоит в этом чате",
        "leave_fail": "<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> {name}: {err}",
        "leave_del_ok": "<tg-emoji emoji-id=5458805056990119991>🌘</tg-emoji> {name} — диалог удалён",
        "leave_del_fail": "<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> {name}: не удалось удалить диалог — {err}",
        "usage_bot": "<tg-emoji emoji-id=5456307331644037599>🌘</tg-emoji> Использование: .bot https://t.me/somebot или .bot @somebot",
        "bot_header": "<tg-emoji emoji-id=5458396206168312985>🌘</tg-emoji> <b>Результат запуска бота:</b>\n\n",
        "bot_ok": "<tg-emoji emoji-id=5458805056990119991>🌘</tg-emoji> {name}",
        "bot_fail": "<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> {name}: {err}",
        "usage_attuser": "<tg-emoji emoji-id=5456307331644037599>🌘</tg-emoji> Использование: .attuser @username Привет!",
        "attuser_header": "<tg-emoji emoji-id=5458567764341985638>🌘</tg-emoji> <b>Результат рассылки:</b>\n\n",
        "attuser_ok": "<tg-emoji emoji-id=5458805056990119991>🌘</tg-emoji> {name}",
        "attuser_fail": "<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> {name}: {err}",
        "loading_ok": "<tg-emoji emoji-id=5458443008426936556>🌘</tg-emoji> Загружен аккаунт: {name} (+{phone}) [id={user_id}]",
        "loading_fail": "️<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> Не удалось загрузить аккаунт: {err}",
        "loading_update_ok": "<tg-emoji emoji-id=5458443008426936556>🌘</tg-emoji> Обновлён аккаунт: {name} (+{phone}) [id={user_id}]",
        "loading_update_fail": "️<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> Не удалось обновить аккаунт {user_id}: {err}",
        "usage_react": "<tg-emoji emoji-id=5456313473447268204>🌘</tg-emoji> <b>Использование:</b>\n<code>.react https://t.me/killu_gifts/485 ❤️</code>\n<code>.react https://t.me/killu_gifts/485 ❤️ 5-10</code> - только аккаунты 5-10",
        "react_header": "️<tg-emoji emoji-id=5456469226141288702>🌘</tg-emoji> <b>Результат проставления реакций:</b>\n\n",
        "react_ok": "️<tg-emoji emoji-id=5458805056990119991>🌘</tg-emoji> {name}",
        "react_fail": "<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> {name}: {err}",
        "usage_ram": "<tg-emoji emoji-id=5456313473447268204>🌘</tg-emoji> <b>Использование:</b>\n<code>.ram</code> - отметить все сообщения как прочитанные на всех аккаунтах",
        "ram_processing": "<tg-emoji emoji-id=5332739932832146628>☯️</tg-emoji> <b>Читаю все сообщения на всех аккаунтах...</b>",
        "ram_header": "<tg-emoji emoji-id=5458443008426936556>🌘</tg-emoji> <b>Результат отметки прочитанных сообщений:</b>\n\n",
        "ram_ok": "<tg-emoji emoji-id=5458805056990119991>🌘</tg-emoji> {name} — помечено как прочитанное ({dialogs} диалогов)",
        "ram_fail": "<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> {name}: {err}",
        "ram_empty": "<tg-emoji emoji-id=5456307331644037599>🌘</tg-emoji> {name} — нет непрочитанных сообщений",
        "usage_ramc": (
            "<tg-emoji emoji-id=5456313473447268204>🌘</tg-emoji> <b>Использование:</b>\n"
            "<code>.ramc @канал 10</code> — отметить последние 10 постов как просмотренные\n"
            "<code>.ramc https://t.me/канал/123</code> — отметить конкретный пост как просмотренный\n"
            "Можно передать @username или ссылку t.me/username"
        ),
        "ramc_processing": "<tg-emoji emoji-id=5332739932832146628>☯️</tg-emoji> <b>Отмечаю пост как просмотренный...</b>",
        "ramc_header": "<tg-emoji emoji-id=5458443008426936556>🌘</tg-emoji> <b>Результат просмотра поста:</b>\n\n",
        "ramc_ok": "<tg-emoji emoji-id=5458805056990119991>🌘</tg-emoji> {name} — пост отмечен просмотренным",
        "ramc_fail": "<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> {name}: {err}",
        "ramc_no_posts": "<tg-emoji emoji-id=5456307331644037599>🌘</tg-emoji> В канале не найдено постов.",
        "acc_list_page": "🌘 <b>Подключённые аккаунты</b> [<b>{page}</b>/<b>{total_pages}</b>] (<b>{total}</b>):\n\n",
        "updating_accounts": "<tg-emoji emoji-id=5332739932832146628>☯️</tg-emoji> <b>Обновляю информацию об аккаунтах...</b>",
        "update_complete": "<tg-emoji emoji-id=5458805056990119991>🌘</tg-emoji> <b>Информация об аккаунтах обновлена!</b>\nОбновлено: {updated} аккаунтов\nОшибок: {errors}",
        "tspam_processing": "<tg-emoji emoji-id=5332739932832146628>☯️</tg-emoji> <b>Проверяю аккаунты на спам-бан...</b>",
        "tspam_header": "<tg-emoji emoji-id=5458443008426936556>🌘</tg-emoji> <b>Результат проверки спам-бана:</b>\n\n",
        "tspam_ok": "<tg-emoji emoji-id=5458805056990119991>🌘</tg-emoji> {name} — свободен от спам-бана",
        "tspam_banned": "<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> {name} — ОГРАНИЧЕН до {date}",
        "tspam_banned_no_date": "<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> {name} — ОГРАНИЧЕН",
        "tspam_error": "<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> {name}: {err}",
        "usage_tbutton": "<tg-emoji emoji-id=5456313473447268204>🌘</tg-emoji> <b>Использование:</b>\n<code>.tbutton https://t.me/channel/msg_id 1</code> - нажать кнопку под сообщением\n<code>.tbutton @username 1 5-10</code> - нажать кнопку аккаунтами 5-10",
        "tbutton_processing": "<tg-emoji emoji-id=5332739932832146628>☯️</tg-emoji> <b>Нажимаю кнопки на всех аккаунтах...</b>",
        "tbutton_header": "<tg-emoji emoji-id=5458443008426936556>🌘</tg-emoji> <b>Результат нажатия кнопок:</b>\n\n",
        "tbutton_ok": "<tg-emoji emoji-id=5458805056990119991>🌘</tg-emoji> {name} — кнопка нажата",
        "tbutton_no_buttons": "<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> {name}: кнопок не найдено",
        "tbutton_fail": "<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> {name}: {err}",
        "usage_dsoo": "<tg-emoji emoji-id=5456313473447268204>🌘</tg-emoji> <b>Использование:</b>\n<code>.dsoo @username 5</code> - удалить последние 5 сообщений в чате с пользователем\n<code>.dsoo @username 5 20-24</code> - удалить аккаунтами 20-24",
        "dsoo_processing": "<tg-emoji emoji-id=5332739932832146628>☯️</tg-emoji> <b>Удаляю последние {count} сообщений в чате с {user}...</b>",
        "dsoo_header": "<tg-emoji emoji-id=5458567764341985638>🌘</tg-emoji> <b>Результат удаления сообщений:</b>\n\n",
        "dsoo_ok": "<tg-emoji emoji-id=5458805056990119991>🌘</tg-emoji> {name} — удалено {count} сообщений",
        "dsoo_fail": "<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> {name}: {err}",
        "dsoo_no_messages": "<tg-emoji emoji-id=5456307331644037599>🌘</tg-emoji> {name} — нет сообщений для удаления",
        "usage_block": "<tg-emoji emoji-id=5456313473447268204>🌘</tg-emoji> <b>Использование:</b>\n<code>.tblock @username</code> - заблокировать пользователя/бота на всех аккаунтах",
        "block_header": "<tg-emoji emoji-id=5458567764341985638>🌘</tg-emoji> <b>Результат блокировки:</b>\n\n",
        "block_ok": "<tg-emoji emoji-id=5458805056990119991>🌘</tg-emoji> {name} — заблокирован(а)",
        "block_fail": "<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> {name}: {err}",
        "file_confirm": (
            "<tg-emoji emoji-id=5980925264589232084>⚠️</tg-emoji> <b>ВНИМАНИЕ!</b> <tg-emoji emoji-id=5980925264589232084>⚠️</tg-emoji> \n\n"
            "Ты собираешься выгрузить файл со всеми сессиями твоих аккаунтов.\n"
            "Этот файл содержит <b>критически важные данные</b>, которые "
            "позволяют получить полный доступ к аккаунтам.\n\n"
            "<b><u>Рекомендуется делать это только в чате Избранное</u></b>.\n\n"
            "Ты уверен, что хочешь продолжить??"
        ),
        "file_cancel": "<tg-emoji emoji-id=5458805056990119991>🌘</tg-emoji> Файл не был отправлен.",
        "file_sending": "<tg-emoji emoji-id=5445355530111437729>📤</tg-emoji> Отправляю файл...",
        "file_sent": "<tg-emoji emoji-id=5458805056990119991>🌘</tg-emoji> Файл отправлен.",
        "file_error": "<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> Ошибка при отправке файла: {err}",
    }

    def __init__(self):
        self._accounts = {}
        self._pending = {}
        self._loaded = False
        self._per_page = 40
        self._client = None

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        return re.sub(r'\D', '', phone)

    async def _load_accounts(self, client, force_reload=False):
        """Загружает аккаунты из базы данных"""
        if self._loaded and not force_reload:
            return
        
        data = self.db.get(self.strings["name"], DB_KEY_SESSIONS, {})
        api_id = client.api_id
        api_hash = client.api_hash
        
        # Очищаем старые аккаунты при принудительной перезагрузке
        if force_reload:
            for user_id, data_acc in self._accounts.items():
                try:
                    await data_acc["client"].disconnect()
                except Exception:
                    pass
            self._accounts.clear()

        for user_id, acc_info in data.items():
            try:
                ss = acc_info["session"]
                phone_digits = acc_info.get("phone", "")
                c = TelegramClient(StringSession(ss), api_id, api_hash)
                await c.connect()
                if not await c.is_user_authorized():
                    continue
                me = await c.get_me()
                self._accounts[int(user_id)] = {
                    "client": c,
                    "me": me,
                    "phone": phone_digits
                }
                logger.info(self.strings["loading_ok"].format(
                    name=self._full_name(me),
                    phone=phone_digits,
                    user_id=user_id
                ))
            except Exception as e:
                logger.error(self.strings["loading_fail"].format(err=e))
        self._loaded = True
        self._client = client

    async def _update_accounts_info(self):
        """Обновляет информацию об аккаунтах (только имя и юзернейм)"""
        if not self._accounts:
            return 0, 0
        
        updated = 0
        errors = 0
        
        for user_id, data in list(self._accounts.items()):
            try:
                c = data["client"]
                if not await c.is_user_authorized():
                    logger.warning(f"Аккаунт {user_id} не авторизован, пропускаем")
                    continue
                
                me = await c.get_me()
                data["me"] = me
                updated += 1
                
            except Exception as e:
                errors += 1
                logger.error(self.strings["loading_update_fail"].format(
                    user_id=user_id,
                    err=str(e)
                ))
        
        if updated > 0:
            self._save_sessions()
        
        return updated, errors

    def _save_sessions(self):
        to_save = {}
        for user_id, data in self._accounts.items():
            try:
                to_save[user_id] = {
                    "session": data["client"].session.save(),
                    "phone": data["phone"],
                    "name": self._full_name(data["me"])
                }
            except Exception as e:
                logger.error(f"Не сохранил аккаунт {user_id}: {e}")
        self.db.set(self.strings["name"], DB_KEY_SESSIONS, to_save)

    def _full_name(self, me):
        return f"{me.first_name or ''} {me.last_name or ''}".strip() or "Без имени"

    def _username_str(self, me):
        return f"(@{me.username})" if me.username else ""

    def _account_by_index(self, idx):
        keys = list(self._accounts.keys())
        if idx < 1 or idx > len(keys):
            return None, None
        user_id = keys[idx - 1]
        return user_id, self._accounts[user_id]
    
    def _parse_account_range(self, range_str):
        """Парсит диапазон аккаунтов вида '5-10' или '5'"""
        if not range_str:
            return None
        
        # Если просто число
        if range_str.isdigit():
            num = int(range_str)
            return [num]
        
        # Если диапазон вида 5-10
        if '-' in range_str:
            parts = range_str.split('-')
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                start = int(parts[0])
                end = int(parts[1])
                if start <= end:
                    return list(range(start, end + 1))
        
        return None

    async def addtvinkcmd(self, message):
        """[номер телефона] - добавить аккаунт"""
        args = utils.get_args_raw(message).strip()
        if not args:
            return await utils.answer(message, self.strings["usage_addtvink"])
        raw_phone = self._normalize_phone(args)
        if not raw_phone:
            return await utils.answer(message, "❌ Не удалось распознать номер. Введите цифры.")
        await self._addacc_phone(message, raw_phone)

    async def _addacc_phone(self, message, phone_digits):
        await utils.answer(message, self.strings["processing"])
        try:
            full_phone = '+' + phone_digits
            c = TelegramClient(StringSession(), message.client.api_id, message.client.api_hash)
            await c.connect()
            sent = await c.send_code_request(full_phone)
            self._pending[phone_digits] = {
                "client": c,
                "phone_code_hash": sent.phone_code_hash,
            }
            await utils.answer(message, self.strings["code_sent"].format(phone=phone_digits))
        except Exception as e:
            await utils.answer(message, self.strings["acc_error"].format(err=str(e)))

    async def confirmcodecmd(self, message):
        """[код] - подтвердить полученый код"""
        raw_args = utils.get_args_raw(message).strip()
        if not raw_args:
            return await utils.answer(message, "<tg-emoji emoji-id=5456313473447268204>🌘</tg-emoji> Использование: .confirmcode 8801349872616 12345")

        parts = raw_args.split()
        if len(parts) < 2:
            return await utils.answer(message, "<tg-emoji emoji-id=5456313473447268204>🌘</tg-emoji> Использование: .confirmcode 8801349872616 12345")

        candidate = parts[0]
        phone_digits = self._normalize_phone(candidate)
        if not phone_digits and len(parts) > 2:
            combined = ''.join(parts[:-2])
            phone_digits = self._normalize_phone(combined)

        if not phone_digits:
            return await utils.answer(message, "❌ Не удалось определить номер. Введите номер цифрами без пробелов.")

        if len(parts) == 2:
            code = parts[1]
            password = None
        elif len(parts) == 3:
            code = parts[1]
            password = parts[2]
        else:
            code = parts[-1]
            password = parts[-2] if len(parts) > 2 else None

        if phone_digits not in self._pending:
            return await utils.answer(message, self.strings["no_pending"])

        pending = self._pending[phone_digits]
        c = pending["client"]
        pch = pending["phone_code_hash"]
        full_phone = '+' + phone_digits

        try:
            await c.sign_in(full_phone, code, phone_code_hash=pch)
        except SessionPasswordNeededError:
            if not password:
                return await utils.answer(message, self.strings["need_2fa"].format(phone=phone_digits, code=code))
            try:
                await c.sign_in(password=password)
            except Exception as e:
                return await utils.answer(message, self.strings["acc_error"].format(err=str(e)))
        except PhoneCodeInvalidError:
            return await utils.answer(message, self.strings["code_invalid"])
        except Exception as e:
            return await utils.answer(message, self.strings["acc_error"].format(err=str(e)))

        me = await c.get_me()
        user_id = me.id
        ss = c.session.save()
        await c.disconnect()

        c2 = TelegramClient(StringSession(ss), message.client.api_id, message.client.api_hash)
        await c2.connect()

        self._accounts[user_id] = {
            "client": c2,
            "me": me,
            "phone": phone_digits
        }
        self._save_sessions()
        del self._pending[phone_digits]

        await utils.answer(
            message,
            self.strings["acc_added"].format(
                name=self._full_name(me),
                phone=phone_digits,
                user_id=user_id
            )
        )

    async def acclistcmd(self, message):
        """список аккаунтов"""
        await self._load_accounts(message.client)
        if not self._accounts:
            return await utils.answer(message, self.strings["no_accounts"])

        await message.delete()
        await self._show_accounts_page_inline(message, 1)

    def _build_page_content(self, page):
        """Возвращает (text, keyboard) для указанной страницы"""
        accounts_list = list(self._accounts.items())
        total = len(accounts_list)
        total_pages = (total + self._per_page - 1) // self._per_page if total > 0 else 1

        if page < 1:
            page = 1
        if page > total_pages:
            page = total_pages

        start = (page - 1) * self._per_page
        end = min(start + self._per_page, total)

        text = self.strings["acc_list_page"].format(
            page=page,
            total_pages=total_pages,
            total=total
        )

        for i, (user_id, data) in enumerate(accounts_list[start:end], start=start + 1):
            me = data["me"]
            text += self.strings["acc_list_item"].format(
                i=i,
                name=self._full_name(me),
                uname=self._username_str(me),
                phone=data["phone"],
                user_id=user_id,
            )

        keyboard = self._build_keyboard(page, total_pages)
        return text, keyboard

    async def _show_accounts_page_inline(self, message, page):
        """Отображает страницу с аккаунтами через инлайн (первый вызов)"""
        text, keyboard = self._build_page_content(page)

        await self.inline.form(
            text=text,
            message=message,
            always_allow=[message.sender_id] if message else [],
            reply_markup=keyboard,
            manual_security=True,
        )

    def _build_keyboard(self, page, total_pages):
        """Строит клавиатуру для пагинации"""
        buttons = []

        # Ряд с навигацией
        nav_row = []
        if page > 1:
            nav_row.append({"text": "◀️", "callback": self._page_cb, "args": (page - 1,)})
        nav_row.append({"text": f"{page}/{total_pages}", "callback": self._page_info_cb, "args": ()})
        if page < total_pages:
            nav_row.append({"text": "▶️", "callback": self._page_cb, "args": (page + 1,)})
        buttons.append(nav_row)

        # Кнопка обновления
        buttons.append([{"text": "🔄 Обновить", "callback": self._update_cb, "args": ()}])

        return buttons

    async def _page_cb(self, call: InlineCall, page: int):
        """Обработчик переключения страниц"""
        text, keyboard = self._build_page_content(page)
        await call.edit(text=text, reply_markup=keyboard)

    async def _page_info_cb(self, call: InlineCall):
        """Обработчик кнопки с информацией о странице"""
        await call.answer("Используйте кнопки для навигации", show_alert=False)

    async def _update_cb(self, call: InlineCall):
        """Обработчик кнопки обновления - полностью перезагружает все аккаунты из БД"""
        await call.answer("🔄 Обновляю список аккаунтов...", show_alert=False)
        
        # Полностью перезагружаем аккаунты из БД
        await self._load_accounts(self._client, force_reload=True)
        
        # Обновляем информацию об аккаунтах
        updated, errors = await self._update_accounts_info()
        
        # Обновляем страницу
        text, keyboard = self._build_page_content(1)
        await call.edit(text=text, reply_markup=keyboard)
        
        if updated > 0 or errors > 0:
            await call.answer(f"✅ Обновлено: {updated} аккаунтов, ошибок: {errors}", show_alert=True)
        else:
            await call.answer("✅ Список аккаунтов обновлён", show_alert=True)

    async def delacccmd(self, message):
        """удалить аккаунт по номеру из списка .acclist"""
        await self._load_accounts(message.client)
        args = utils.get_args_raw(message).strip()
        if not args or not args.isdigit():
            return await utils.answer(message, self.strings["usage_delacc"])

        user_id, data = self._account_by_index(int(args))
        if user_id is None:
            return await utils.answer(message, self.strings["acc_not_found"])

        name = self._full_name(data["me"])
        try:
            await data["client"].disconnect()
        except Exception:
            pass
        del self._accounts[user_id]
        self._save_sessions()
        await utils.answer(message, self.strings["acc_removed"].format(name=name))

    async def client_ready(self, client, db):
        """Вызывается при загрузке модуля/перезапуске"""
        self.db = db
        await self._load_accounts(client)
        if self._accounts:
            logger.info("🔄 Обновляю информацию об аккаунтах при перезапуске...")
            updated, errors = await self._update_accounts_info()
            logger.info(f"✅ Обновлено: {updated} аккаунтов, ошибок: {errors}")

    # ---------- Остальные команды ----------
    async def tjoincmd(self, message):
        """ссылка/юзернейм - вступление в канал/чат"""
        await self._load_accounts(message.client)
        link = utils.get_args_raw(message).strip()
        if not link:
            return await utils.answer(message, self.strings["usage_join"])
        if not self._accounts:
            return await utils.answer(message, self.strings["no_accounts"])

        await utils.answer(message, self.strings["processing"])
        results = []
        for user_id, data in self._accounts.items():
            c = data["client"]
            name = self._full_name(data["me"])
            try:
                await self._join_chat(c, link)
                results.append(self.strings["join_ok"].format(name=name))
            except UserAlreadyParticipantError:
                results.append(self.strings["join_already"].format(name=name))
            except (InviteHashExpiredError, InviteHashInvalidError, ChannelPrivateError) as e:
                results.append(self.strings["join_fail"].format(name=name, err=type(e).__name__))
                break
            except Exception as e:
                results.append(self.strings["join_fail"].format(name=name, err=str(e)))
        await utils.answer(message, self.strings["join_header"] + "\n".join(results))

    async def _join_chat(self, client, link):
        link = link.strip().rstrip("/")
        last = link.split("/")[-1]
        if last.startswith("+") or "joinchat" in link:
            invite_hash = last.lstrip("+")
            await client(ImportChatInviteRequest(invite_hash))
        else:
            entity = await client.get_entity(link)
            await client(JoinChannelRequest(entity))

    async def dchatcmd(self, message):
        """ссылка/юзернейм - покинуть канал/группу или удалить личный чат/бота"""
        await self._load_accounts(message.client)
        link = utils.get_args_raw(message).strip()
        if not link:
            return await utils.answer(message, self.strings["usage_leave"])
        if not self._accounts:
            return await utils.answer(message, self.strings["no_accounts"])

        await utils.answer(message, self.strings["processing"])
        results = []
        for user_id, data in self._accounts.items():
            c = data["client"]
            name = self._full_name(data["me"])
            try:
                entity = await c.get_entity(link)
                is_channel = hasattr(entity, 'broadcast') and entity.broadcast
                is_megagroup = hasattr(entity, 'megagroup') and entity.megagroup
                is_group = hasattr(entity, 'group') and entity.group

                if is_channel or is_megagroup or (hasattr(entity, 'id') and entity.id < 0):
                    await c(LeaveChannelRequest(entity))
                    results.append(self.strings["leave_ok"].format(name=name))
                else:
                    try:
                        await c.delete_dialog(entity, revoke=False)
                        results.append(self.strings["leave_del_ok"].format(name=name))
                    except Exception as e_del:
                        results.append(self.strings["leave_del_fail"].format(name=name, err=str(e_del)))
            except Exception as e:
                err_str = str(e)
                if "CHANNEL_PRIVATE" in err_str or "USER_NOT_PARTICIPANT" in err_str or "not in the channel" in err_str:
                    results.append(self.strings["leave_not_member"].format(name=name))
                else:
                    results.append(self.strings["leave_fail"].format(name=name, err=err_str))
        await utils.answer(message, self.strings["leave_header"] + "\n".join(results))

    async def tbotcmd(self, message):
        """реф. ссылка бота - переход по ссылке и сообщение /start"""
        await self._load_accounts(message.client)
        raw = utils.get_args_raw(message).strip()
        if not raw:
            return await utils.answer(message, self.strings["usage_bot"])
        if not self._accounts:
            return await utils.answer(message, self.strings["no_accounts"])

        link = raw
        for prefix in ("https://", "http://"):
            if link.startswith(prefix):
                link = link[len(prefix):]
        if link.startswith("t.me/"):
            link = link[5:]

        start_param = None
        if "?" in link:
            bot_part, query = link.split("?", 1)
            for pair in query.split("&"):
                if pair.startswith("start="):
                    start_param = pair.split("=", 1)[1]
                    break
            link = bot_part

        bot_name = link.rstrip("/").split("/")[-1].lstrip("@")
        if not bot_name:
            return await utils.answer(message, "<tg-emoji emoji-id=5456307331644037599>🌘</tg-emoji> Не удалось определить имя бота.")

        msg_text = f"/start {start_param}" if start_param else "/start"

        await utils.answer(message, self.strings["processing"])
        results = []
        for user_id, data in self._accounts.items():
            c = data["client"]
            name = self._full_name(data["me"])
            try:
                await c.send_message(bot_name, msg_text)
                results.append(self.strings["bot_ok"].format(name=name))
            except Exception as e:
                results.append(self.strings["bot_fail"].format(name=name, err=str(e)))
        await utils.answer(message, self.strings["bot_header"] + "\n".join(results))

    async def attusercmd(self, message):
        """юзернейм/айди - массовый спам с разных аккаунтов"""
        await self._load_accounts(message.client)
        raw = utils.get_args_raw(message).strip()
        if not raw:
            return await utils.answer(message, self.strings["usage_attuser"])
        if not self._accounts:
            return await utils.answer(message, self.strings["no_accounts"])

        parts = raw.split(maxsplit=1)
        if len(parts) < 2:
            return await utils.answer(message, self.strings["usage_attuser"])
        target = parts[0].lstrip("@")
        text = parts[1]

        await utils.answer(message, self.strings["processing"])
        results = []
        for user_id, data in self._accounts.items():
            c = data["client"]
            name = self._full_name(data["me"])
            try:
                await c.send_message(target, text)
                results.append(self.strings["attuser_ok"].format(name=name))
            except Exception as e:
                results.append(self.strings["attuser_fail"].format(name=name, err=str(e)))
        await utils.answer(message, self.strings["attuser_header"] + "\n".join(results))

    async def treactcmd(self, message):
        """поставить реакцию на пост"""
        await self._load_accounts(message.client)
        raw = utils.get_args_raw(message).strip()
        if not raw:
            return await utils.answer(message, self.strings["usage_react"])
        if not self._accounts:
            return await utils.answer(message, self.strings["no_accounts"])

        parts = raw.split(maxsplit=2)
        if len(parts) < 2:
            return await utils.answer(message, self.strings["usage_react"])
        
        link = parts[0]
        reaction = parts[1]
        
        # Проверяем, есть ли диапазон аккаунтов
        account_range = None
        if len(parts) >= 3:
            range_str = parts[2].strip()
            parsed = self._parse_account_range(range_str)
            if parsed:
                account_range = parsed
            else:
                # Если не удалось распарсить как диапазон, возможно это часть реакции
                # Проверяем, не является ли это просто продолжением реакции
                if not range_str.startswith('-') and not range_str.isdigit():
                    reaction += ' ' + range_str
                    account_range = None
                else:
                    account_range = parsed

        try:
            clean_link = link.split('?')[0]
            if clean_link.startswith("https://"):
                path = clean_link[8:]
            elif clean_link.startswith("http://"):
                path = clean_link[7:]
            else:
                path = clean_link
            
            if path.startswith("t.me/"):
                path = path[5:]

            path_parts = path.split('/')
            if len(path_parts) < 2:
                raise ValueError("Неверный формат ссылки")

            if path_parts[0] == 'c' and len(path_parts) >= 3:
                channel_identifier = int(path_parts[1])
                msg_id = int(path_parts[2])
            else:
                channel_identifier = path_parts[0]
                msg_id = int(path_parts[1])

        except (ValueError, IndexError) as e:
            return await utils.answer(message, f"❌ Не удалось разобрать ссылку: {e}")

        await utils.answer(message, self.strings["processing"])
        results = []

        # Получаем список аккаунтов для обработки
        accounts_to_process = []
        if account_range:
            accounts_list = list(self._accounts.items())
            for idx in account_range:
                if 1 <= idx <= len(accounts_list):
                    accounts_to_process.append(accounts_list[idx - 1])
                else:
                    results.append(f"<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> Аккаунт #{idx} не найден (всего {len(accounts_list)})")
        else:
            accounts_to_process = list(self._accounts.items())

        for user_id, data in accounts_to_process:
            c = data["client"]
            name = self._full_name(data["me"])
            try:
                entity = await c.get_entity(channel_identifier)
                await c.send_reaction(entity, message=msg_id, reaction=[reaction])
                results.append(self.strings["react_ok"].format(name=name))
            except Exception as e:
                err_str = str(e)
                if "Cannot find any entity" in err_str:
                    err_str = "Не удалось найти канал. Возможно, аккаунт не вступил в него."
                results.append(self.strings["react_fail"].format(name=name, err=err_str))

        await utils.answer(message, self.strings["react_header"] + "\n".join(results))

    async def ramcmd(self, message):
        """отметить все сообщения как прочитанные на всех аккаунтах"""
        await self._load_accounts(message.client)
        if not self._accounts:
            return await utils.answer(message, self.strings["no_accounts"])

        await utils.answer(message, self.strings["ram_processing"])
        results = []

        for user_id, data in self._accounts.items():
            c = data["client"]
            name = self._full_name(data["me"])
            try:
                dialogs_processed = 0

                async for dialog in c.iter_dialogs():
                    if dialog.unread_count > 0:
                        dialogs_processed += 1
                        await c.send_read_acknowledge(dialog.entity)
                        await asyncio.sleep(0.05)

                if dialogs_processed == 0:
                    results.append(self.strings["ram_empty"].format(name=name))
                else:
                    results.append(self.strings["ram_ok"].format(
                        name=name,
                        dialogs=dialogs_processed
                    ))

            except FloodWaitError as e:
                results.append(self.strings["ram_fail"].format(
                    name=name,
                    err=f"FloodWait: нужно подождать {e.seconds}с"
                ))
            except Exception as e:
                results.append(self.strings["ram_fail"].format(name=name, err=str(e)))

        await utils.answer(message, self.strings["ram_header"] + "\n".join(results))

    async def ramccmd(self, message):
        """[канал/ссылка на пост] [количество] — отметить последние N постов или конкретный пост как просмотренный"""
        await self._load_accounts(message.client)
        raw = utils.get_args_raw(message).strip()
        if not raw:
            return await utils.answer(message, self.strings["usage_ramc"])
        if not self._accounts:
            return await utils.answer(message, self.strings["no_accounts"])

        parts = raw.split(maxsplit=1)
        channel_raw = parts[0].strip()

        # Проверяем, является ли ввод ссылкой на конкретный пост
        is_single_post = False
        single_post_id = None
        channel_identifier = None

        # Пытаемся распарсить ссылку на пост
        try:
            clean_link = channel_raw.split('?')[0]
            if clean_link.startswith("https://"):
                path = clean_link[8:]
            elif clean_link.startswith("http://"):
                path = clean_link[7:]
            else:
                path = clean_link
            
            if path.startswith("t.me/"):
                path = path[5:]

            path_parts = path.split('/')
            if len(path_parts) >= 2:
                # Проверяем, есть ли числовой ID сообщения в конце
                try:
                    potential_msg_id = int(path_parts[-1])
                    # Определяем идентификатор канала
                    if path_parts[0] == 'c' and len(path_parts) >= 3:
                        channel_part = int(path_parts[1])
                    else:
                        channel_part = path_parts[0]
                    
                    is_single_post = True
                    single_post_id = potential_msg_id
                    channel_identifier = channel_part
                except ValueError:
                    pass
        except Exception:
            pass

        # Если это не ссылка на пост, обрабатываем как обычную команду с каналом и количеством
        if not is_single_post:
            if len(parts) < 2 or not parts[1].strip().isdigit():
                return await utils.answer(message, self.strings["usage_ramc"])
            count = int(parts[1].strip())
            
            for prefix in ("https://", "http://"):
                if channel_raw.startswith(prefix):
                    channel_raw = channel_raw[len(prefix):]
            if channel_raw.startswith("t.me/"):
                channel_raw = channel_raw[5:]
            channel_raw = channel_raw.rstrip("/")
            channel_identifier = channel_raw if channel_raw.startswith("@") else "@" + channel_raw.lstrip("@")
            
            await utils.answer(
                message,
                self.strings["ramc_processing"].format(count=count, channel=channel_identifier)
            )

            try:
                entity = await message.client.get_entity(channel_identifier)
                msg_ids = []
                async for msg in message.client.iter_messages(entity, limit=count):
                    msg_ids.append(msg.id)
                if not msg_ids:
                    return await utils.answer(message, self.strings["ramc_no_posts"])
            except Exception as e:
                return await utils.answer(
                    message,
                    f"<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> Не удалось получить посты канала: <code>{e}</code>"
                )
        else:
            # Это ссылка на конкретный пост
            await utils.answer(
                message,
                self.strings["ramc_processing"].format(channel=channel_identifier, count=1)
            )
            msg_ids = [single_post_id]
            try:
                entity = await message.client.get_entity(channel_identifier)
            except Exception as e:
                return await utils.answer(
                    message,
                    f"<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> Не удалось найти канал: <code>{e}</code>"
                )

        results = []
        for user_id, data in self._accounts.items():
            c = data["client"]
            name = self._full_name(data["me"])
            try:
                acc_entity = await c.get_entity(channel_identifier)
                chunk_size = 100
                viewed = 0
                for i in range(0, len(msg_ids), chunk_size):
                    chunk = msg_ids[i:i + chunk_size]
                    # Используем GetMessagesViewsRequest для увеличения счетчика просмотров [citation:1][citation:6]
                    await c(GetMessagesViewsRequest(
                        peer=acc_entity,
                        id=chunk,
                        increment=True
                    ))
                    viewed += len(chunk)
                    await asyncio.sleep(0.3)
                
                if is_single_post:
                    results.append(self.strings["ramc_ok"].format(name=name))
                else:
                    results.append(self.strings["ramc_ok"].format(name=name))
            except FloodWaitError as e:
                results.append(self.strings["ramc_fail"].format(
                    name=name,
                    err=f"FloodWait: подождите {e.seconds}с"
                ))
            except Exception as e:
                err_str = str(e)
                if "Cannot find any entity" in err_str:
                    err_str = "Аккаунт не подписан на канал или канал не найден"
                results.append(self.strings["ramc_fail"].format(name=name, err=err_str))

        if is_single_post:
            await utils.answer(
                message,
                self.strings["ramc_header"].format(channel=channel_identifier, msg_id=single_post_id)
                + "\n".join(results)
            )
        else:
            await utils.answer(
                message,
                self.strings["ramc_header"].format(channel=channel_identifier, msg_id="последние " + str(len(msg_ids)))
                + "\n".join(results)
            )

    async def tspamcmd(self, message):
        """- проверяет все аккаунты на наличие спам-бана через бота @SpamBot."""
        await self._load_accounts(message.client)
        if not self._accounts:
            return await utils.answer(message, self.strings["no_accounts"])

        await utils.answer(message, self.strings["tspam_processing"])
        results = []

        for user_id, data in self._accounts.items():
            c = data["client"]
            name = self._full_name(data["me"])
            try:
                async with c.conversation("@SpamBot") as conv:
                    msg = await conv.send_message("/start")
                    response = await conv.get_response()
                    
                    # Проверяем наличие ключевых слов о свободе
                    text_lower = response.text.lower()
                    
                    # Список ключевых слов/фраз, указывающих на отсутствие бана
                    free_indicators = [
                        "free as a bird",
                        "no limits",
                        "свободен",
                        "ограничений",
                        "good news",
                        "не имеете ограничений",
                        "no restrictions",
                        "without any limits",
                        "no limitations"
                    ]
                    
                    # Список ключевых слов/фраз, указывающих на бан
                    banned_indicators = [
                        "ограничен",
                        "limited",
                        "заблокирован",
                        "restricted",
                        "spam ban",
                        "anti-spam",
                        "cannot send messages",
                        "не можете отправлять сообщения"
                    ]
                    
                    is_free = any(indicator in text_lower for indicator in free_indicators)
                    is_banned = any(indicator in text_lower for indicator in banned_indicators)
                    
                    if is_free:
                        results.append(self.strings["tspam_ok"].format(name=name))
                    elif is_banned:
                        # Пытаемся найти дату
                        date_match = re.search(r'до (\d{2}\.\d{2}\.\d{4})', response.text)
                        if not date_match:
                            date_match = re.search(r'until (\d{2}\.\d{2}\.\d{4})', response.text, re.IGNORECASE)
                        if not date_match:
                            date_match = re.search(r'until (\d{1,2} \w+ \d{4})', response.text, re.IGNORECASE)
                        if not date_match:
                            date_match = re.search(r'до (\d{1,2} \w+ \d{4})', response.text)
                        
                        if date_match:
                            date = date_match.group(1)
                            results.append(self.strings["tspam_banned"].format(name=name, date=date))
                        else:
                            results.append(self.strings["tspam_banned_no_date"].format(name=name))
                    else:
                        # Если непонятно - смотрим на наличие слова "limited" или "ограничен"
                        if "limited" in text_lower or "ограничен" in text_lower:
                            results.append(self.strings["tspam_banned_no_date"].format(name=name))
                        else:
                            # По умолчанию считаем свободным, если нет явных признаков бана
                            results.append(self.strings["tspam_ok"].format(name=name))
                        
            except Exception as e:
                error_msg = str(e)
                if "is not a chat member" in error_msg:
                    error_msg = "Не удалось начать диалог с @SpamBot"
                results.append(self.strings["tspam_error"].format(name=name, err=error_msg))

        await utils.answer(
            message,
            self.strings["tspam_header"] + "\n".join(results)
        )

    async def tbuttoncmd(self, message):
        """нажать кнопку под сообщением"""
        await self._load_accounts(message.client)
        raw = utils.get_args_raw(message).strip()
        if not raw:
            return await utils.answer(message, self.strings["usage_tbutton"])
        if not self._accounts:
            return await utils.answer(message, self.strings["no_accounts"])

        parts = raw.split(maxsplit=3)
        if len(parts) < 2:
            return await utils.answer(message, self.strings["usage_tbutton"])
        
        target = parts[0].strip()
        button_index_str = parts[1].strip()
        
        if not button_index_str.isdigit():
            return await utils.answer(message, self.strings["usage_tbutton"])
        
        button_index = int(button_index_str) - 1  # Переводим в 0-based индекс

        if button_index < 0:
            return await utils.answer(message, "❌ Номер кнопки должен быть больше 0")
        
        # Проверяем, есть ли диапазон аккаунтов
        account_range = None
        if len(parts) >= 3:
            range_str = parts[2].strip()
            parsed = self._parse_account_range(range_str)
            if parsed:
                account_range = parsed
            else:
                # Если не удалось распарсить как диапазон, возможно это часть аргументов
                # Проверяем, не является ли это просто продолжением
                if not range_str.startswith('-') and not range_str.isdigit():
                    account_range = None
                else:
                    account_range = parsed

        await utils.answer(message, self.strings["tbutton_processing"])
        results = []

        # Получаем список аккаунтов для обработки
        accounts_to_process = []
        if account_range:
            accounts_list = list(self._accounts.items())
            for idx in account_range:
                if 1 <= idx <= len(accounts_list):
                    accounts_to_process.append(accounts_list[idx - 1])
                else:
                    results.append(f"<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> Аккаунт #{idx} не найден (всего {len(accounts_list)})")
        else:
            accounts_to_process = list(self._accounts.items())

        # Определяем, что передано: ссылка на сообщение или юзернейм
        is_link = target.startswith("http://") or target.startswith("https://")
        
        # Получаем сообщение для каждого аккаунта
        for user_id, data in accounts_to_process:
            c = data["client"]
            name = self._full_name(data["me"])
            try:
                if is_link:
                    # Ссылка на сообщение - парсим
                    clean_link = target.split('?')[0]
                    if clean_link.startswith("https://"):
                        path = clean_link[8:]
                    elif clean_link.startswith("http://"):
                        path = clean_link[7:]
                    else:
                        path = clean_link
                    
                    if path.startswith("t.me/"):
                        path = path[5:]
                    
                    path_parts = path.split('/')
                    if len(path_parts) < 2:
                        raise ValueError("Неверный формат ссылки")

                    # Определяем сущность и ID сообщения
                    if path_parts[0] == 'c' and len(path_parts) >= 3:
                        channel_identifier = int(path_parts[1])
                        msg_id = int(path_parts[2])
                    else:
                        channel_identifier = path_parts[0]
                        msg_id = int(path_parts[1])
                    
                    # Получаем сущность
                    entity = await c.get_entity(channel_identifier)
                    
                    # Получаем сообщение
                    message_obj = await c.get_messages(entity, ids=msg_id)
                    if not message_obj:
                        results.append(self.strings["tbutton_fail"].format(name=name, err="Сообщение не найдено"))
                        continue
                    
                    # Нажимаем кнопку
                    await self._click_button(message_obj, button_index, name, results)
                    
                else:
                    # Юзернейм - получаем последнее сообщение в чате
                    entity = await c.get_entity(target)
                    
                    # Получаем последние сообщения
                    messages = await c.get_messages(entity, limit=5)
                    if not messages:
                        results.append(self.strings["tbutton_fail"].format(name=name, err="Нет сообщений в чате"))
                        continue
                    
                    # Берем последнее сообщение от кого угодно
                    message_obj = messages[0]
                    
                    # Нажимаем кнопку
                    await self._click_button(message_obj, button_index, name, results)
                    
            except Exception as e:
                err_str = str(e)
                results.append(self.strings["tbutton_fail"].format(name=name, err=err_str))

        await utils.answer(
            message,
            self.strings["tbutton_header"] + "\n".join(results)
        )

    async def _click_button(self, message_obj, button_index, name, results):
        """Нажимает кнопку по индексу в сообщении"""
        try:
            # Проверяем наличие кнопок
            if not message_obj.reply_markup or not message_obj.reply_markup.rows:
                results.append(self.strings["tbutton_no_buttons"].format(name=name))
                return
            
            # Собираем все кнопки в один список
            all_buttons = []
            for row in message_obj.reply_markup.rows:
                for button in row.buttons:
                    all_buttons.append(button)
            
            # Проверяем, что индекс существует
            if button_index >= len(all_buttons):
                results.append(self.strings["tbutton_fail"].format(
                    name=name, 
                    err=f"Кнопки #{button_index+1} не существует (всего {len(all_buttons)})"
                ))
                return
            
            # Нажимаем кнопку (без аргументов)
            await message_obj.click(button_index)
            results.append(self.strings["tbutton_ok"].format(name=name))
            
        except Exception as e:
            results.append(self.strings["tbutton_fail"].format(name=name, err=str(e)))

    async def dsoocmd(self, message):
        """удалить последние N сообщений в чате с пользователем"""
        await self._load_accounts(message.client)
        raw = utils.get_args_raw(message).strip()
        if not raw:
            return await utils.answer(message, self.strings["usage_dsoo"])
        if not self._accounts:
            return await utils.answer(message, self.strings["no_accounts"])

        parts = raw.split(maxsplit=3)
        if len(parts) < 2:
            return await utils.answer(message, self.strings["usage_dsoo"])
        
        target = parts[0].strip()
        count_str = parts[1].strip()
        
        if not count_str.isdigit():
            return await utils.answer(message, self.strings["usage_dsoo"])
        
        count = int(count_str)
        if count <= 0:
            return await utils.answer(message, "<tg-emoji emoji-id=5456313473447268204>🌘</tg-emoji> Количество должно быть больше 0")
        
        # Проверяем, есть ли диапазон аккаунтов
        account_range = None
        if len(parts) >= 3:
            range_str = parts[2].strip()
            parsed = self._parse_account_range(range_str)
            if parsed:
                account_range = parsed
            else:
                # Если не удалось распарсить как диапазон
                if not range_str.startswith('-') and not range_str.isdigit():
                    account_range = None
                else:
                    account_range = parsed

        # Очищаем target от @ если есть
        clean_target = target.lstrip('@')
        
        await utils.answer(message, self.strings["dsoo_processing"].format(count=count, user=clean_target))
        results = []

        # Получаем список аккаунтов для обработки
        accounts_to_process = []
        if account_range:
            accounts_list = list(self._accounts.items())
            for idx in account_range:
                if 1 <= idx <= len(accounts_list):
                    accounts_to_process.append(accounts_list[idx - 1])
                else:
                    results.append(f"❌ Аккаунт #{idx} не найден (всего {len(accounts_list)})")
        else:
            accounts_to_process = list(self._accounts.items())

        for user_id, data in accounts_to_process:
            c = data["client"]
            name = self._full_name(data["me"])
            try:
                # Получаем сущность пользователя
                entity = await c.get_entity(clean_target)
                
                # Получаем последние N сообщений в чате с этим пользователем (ЛЮБЫЕ сообщения, не только свои)
                messages = []
                async for msg in c.iter_messages(entity, limit=count):
                    messages.append(msg)
                
                if not messages:
                    results.append(self.strings["dsoo_no_messages"].format(name=name))
                    continue
                
                # Удаляем сообщения
                deleted_count = 0
                for msg in messages:
                    try:
                        await msg.delete()
                        deleted_count += 1
                        await asyncio.sleep(0.3)  # Небольшая задержка, чтобы не получить флуд
                    except Exception as e:
                        logger.error(f"Не удалось удалить сообщение {msg.id}: {e}")
                
                if deleted_count > 0:
                    results.append(self.strings["dsoo_ok"].format(name=name, count=deleted_count))
                else:
                    results.append(self.strings["dsoo_no_messages"].format(name=name))
                    
            except FloodWaitError as e:
                results.append(self.strings["dsoo_fail"].format(
                    name=name,
                    err=f"FloodWait: подождите {e.seconds}с"
                ))
            except Exception as e:
                err_str = str(e)
                if "Cannot find any entity" in err_str:
                    err_str = "Пользователь не найден"
                elif "USER_ID_INVALID" in err_str:
                    err_str = "Неверный ID пользователя"
                results.append(self.strings["dsoo_fail"].format(name=name, err=err_str))

        await utils.answer(
            message,
            self.strings["dsoo_header"] + "\n".join(results)
        )

    # ---------- НОВЫЕ КОМАНДЫ ----------

    async def tblockcmd(self, message):
        """заблокировать пользователя/бота по юзу/айди"""
        await self._load_accounts(message.client)
        target = utils.get_args_raw(message).strip()
        if not target:
            return await utils.answer(message, self.strings["usage_block"])
        if not self._accounts:
            return await utils.answer(message, self.strings["no_accounts"])

        # Очищаем target от @ и лишнего
        clean_target = target.lstrip('@').split()[0]  # Берем только первый аргумент как юзернейм

        await utils.answer(message, self.strings["processing"])
        results = []

        for user_id, data in self._accounts.items():
            c = data["client"]
            name = self._full_name(data["me"])
            try:
                entity = await c.get_entity(clean_target)
                await c(BlockRequest(id=entity))
                results.append(self.strings["block_ok"].format(name=name))
            except Exception as e:
                err_str = str(e)
                if "Cannot find any entity" in err_str:
                    err_str = "Пользователь не найден"
                elif "USER_ID_INVALID" in err_str:
                    err_str = "Неверный ID пользователя"
                results.append(self.strings["block_fail"].format(name=name, err=err_str))

        await utils.answer(
            message,
            self.strings["block_header"] + "\n".join(results)
        )

    async def tfilecmd(self, message):
        """отправить файл со всеми сессиями в чат"""
        await self._load_accounts(message.client)
        if not self._accounts:
            return await utils.answer(message, self.strings["no_accounts"])

        me = await message.client.get_me()
        is_saved = bool(message.is_private) and message.chat_id == me.id

        if is_saved:
            # Избранное — свой личный чат, поэтому шлём файл сразу, без подтверждения
            await utils.answer(message, self.strings["file_sending"])
            ok, result_text = await self._send_sessions_file(message.client, message.chat_id)
            await utils.answer(message, result_text)
            return

        # Любой другой чат — сначала спрашиваем подтверждение
        keyboard = [
            [
                {"text": "Да, точно!", "callback": self._file_confirm_cb, "args": (message.chat_id,), "color": "red"},
                {"text": "Нет", "callback": self._file_cancel_cb, "args": (message.chat_id,), "color": "blue"}
            ]
        ]

        unit = await self.inline.form(
            text=self.strings["file_confirm"],
            message=message,
            always_allow=[message.sender_id],
            reply_markup=keyboard,
            manual_security=True,
        )

        # Костыль: тг иногда не рисует премиум-эмодзи в самом первом сообщении формы,
        # они появляются только после любого edit (например, после нажатия кнопки).
        # Поэтому форсируем мгновенный self-edit тем же текстом сразу после отправки.
        if unit is not None and hasattr(unit, "edit"):
            try:
                await asyncio.sleep(0.3)
                await unit.edit(text=self.strings["file_confirm"], reply_markup=keyboard)
            except Exception as e:
                logger.debug(f"Не удалось форсировать re-render эмодзи в file_confirm: {e}")

    async def _send_sessions_file(self, client, chat_id):
        """Собирает JSON со всеми сессиями и отправляет его в chat_id.
        Возвращает (ok: bool, текст результата)."""
        try:
            raw_data = self.db.get(self.strings["name"], DB_KEY_SESSIONS, {})

            if not raw_data:
                return False, "❌ Нет данных для отправки."

            json_str = json.dumps(raw_data, indent=2, ensure_ascii=False)
            file_obj = io.BytesIO(json_str.encode("utf-8"))
            file_obj.name = f"tvink-accs-sessions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            await client.send_file(
                chat_id,
                file_obj,
                caption="<tg-emoji emoji-id=5458851476996657778>🌘</tg-emoji> Файл со всеми сессиями аккаунтов",
                parse_mode="html",
            )

            return True, self.strings["file_sent"]

        except Exception as e:
            logger.error(f"Ошибка отправки файла: {e}")
            return False, self.strings["file_error"].format(err=str(e))

    async def _file_confirm_cb(self, call: InlineCall, chat_id: int):
        """Обработчик подтверждения отправки файла"""
        await call.edit(self.strings["file_sending"])
        ok, result_text = await self._send_sessions_file(self._client, chat_id)
        await call.edit(result_text)

    async def _file_cancel_cb(self, call: InlineCall, chat_id: int):
        """Обработчик отмены отправки файла"""
        await call.delete()
        await call.answer(self.strings["file_cancel"], show_alert=True)
