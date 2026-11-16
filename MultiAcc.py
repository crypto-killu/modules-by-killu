# ◇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◇
# meta developer: @dubai_ip
# meta banner: https://raw.githubusercontent.com/crypto-killu/modules-by-killu/main/Module-banners/MultiAcc.jpg
# scope: Heroku_only
# version: 5.0
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
from telethon.tl.functions.messages import (
    ImportChatInviteRequest,
    GetMessagesViewsRequest,
    ReportRequest,
)
from telethon.tl.functions.account import ReportPeerRequest, ReportProfilePhotoRequest
try:
    from telethon.tl.functions.stories import ReportRequest as StoryReportRequest
    _STORY_REPORT = True
except ImportError:
    StoryReportRequest = None
    _STORY_REPORT = False
from telethon.tl.functions.contacts import BlockRequest
from telethon.tl.types import (
    InputReportReasonSpam,
    InputReportReasonViolence,
    InputReportReasonPornography,
    InputReportReasonChildAbuse,
    InputReportReasonCopyright,
    InputReportReasonGeoIrrelevant,
    InputReportReasonFake,
    InputReportReasonIllegalDrugs,
    InputReportReasonPersonalDetails,
    InputReportReasonOther,
)
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    FloodWaitError,
    UserAlreadyParticipantError,
    InviteHashExpiredError,
    InviteHashInvalidError,
    ChannelPrivateError,
)

from .. import loader, utils
from ..inline.types import InlineCall

logger = logging.getLogger(__name__)

DB_KEY = "tvink-accs-sessions_v2"

# ── Маппинг причин для жалоб ────────────────────────────────
# Причины, которые есть как отдельные TL-типы
_NATIVE = {
    "spam": InputReportReasonSpam,
    "violence": InputReportReasonViolence,
    "porn": InputReportReasonPornography,
    "child": InputReportReasonChildAbuse,
    "copyright": InputReportReasonCopyright,
    "geo": InputReportReasonGeoIrrelevant,
    "fake": InputReportReasonFake,
    "drugs": InputReportReasonIllegalDrugs,
    "personal": InputReportReasonPersonalDetails,
    "other": InputReportReasonOther,
}
# Причины, которых нет в TL-схеме — отправляются как Other + автокомментарий
_EXTRA = {
    "scam": (InputReportReasonOther, "Scam / Мошенничество"),
    "terrorism": (InputReportReasonOther, "Terrorism / Терроризм"),
    "harassment": (InputReportReasonOther, "Harassment / Буллинг / Домогательства"),
    "suicide": (InputReportReasonOther, "Suicide / Self-harm / Суицид / Самоповреждение"),
    "impersonation": (InputReportReasonOther, "Impersonation / Выдаёт себя за другого"),
}

def _reasons(keys):
    out = {}
    for k in keys:
        if k in _NATIVE:
            out[k] = _NATIVE[k]
        elif k in _EXTRA:
            out[k] = _EXTRA[k][0]
    return out

REASON_SETS = {
    "user": _reasons(["spam", "violence", "porn", "child", "fake", "drugs", "personal",
                       "scam", "terrorism", "harassment", "suicide", "impersonation", "other"]),
    "bot": _reasons(["spam", "violence", "porn", "child", "fake", "drugs", "personal",
                      "scam", "other"]),
    "channel": _reasons(["spam", "violence", "porn", "child", "copyright", "fake", "drugs",
                          "scam", "terrorism", "other"]),
    "chat": _reasons(["spam", "violence", "porn", "child", "copyright", "drugs", "geo",
                       "scam", "terrorism", "harassment", "other"]),
    "photo": _reasons(["spam", "violence", "porn", "child", "other"]),
    "legacy": _reasons(["spam", "violence", "porn", "child", "copyright", "geo", "fake",
                         "drugs", "personal", "scam", "terrorism", "harassment",
                         "suicide", "impersonation", "other"]),
}

# Ключевые слова для tree-based API (messages.report / stories.report)
MSG_KW = {
    "spam": ["spam", "спам", "unwanted", "advert"],
    "violence": ["violen", "насил", "harm", "graphic"],
    "porn": ["porn", "adult", "sexual", "explicit", "nud", "порн"],
    "child": ["child", "minor", "несовершен", "дет"],
    "drugs": ["drug", "narcot", "наркот", "illegal subst"],
    "scam": ["scam", "мошен", "fraud"],
    "terrorism": ["terror", "террор"],
    "harassment": ["harass", "bully", "домогат", "булл"],
    "suicide": ["suicid", "self-harm", "суицид", "самоповрежд"],
    "other": ["other", "друг", "else"],
}

def _auto_comment(reason_key, user_comment):
    """Если причина из _EXTRA и пользователь не дал комментарий, подставляем описание."""
    if user_comment:
        return user_comment
    if reason_key in _EXTRA:
        return _EXTRA[reason_key][1]
    return ""


def _parse_tme(link: str):
    """Разбирает t.me ссылку → (identifier, msg_id|None, kind).
    kind: None / 'msg' / 'story'."""
    clean = link.strip()
    for p in ("https://", "http://"):
        if clean.startswith(p):
            clean = clean[len(p):]
            break

    if not clean.startswith("t.me/"):
        return clean, None, None

    parts = clean[5:].rstrip("/").split("/")

    # t.me/user/s/2 → история
    if len(parts) >= 3 and parts[1] == "s":
        try:
            return "@" + parts[0].lstrip("@"), int(parts[2]), "story"
        except ValueError:
            pass

    # t.me/c/12345/678 → приватный канал
    if parts[0] == "c" and len(parts) >= 3:
        try:
            return int("-100" + parts[1]), int(parts[2]), "msg"
        except ValueError:
            pass

    # t.me/user/123 → сообщение
    if len(parts) == 2:
        try:
            return "@" + parts[0].lstrip("@"), int(parts[1]), "msg"
        except ValueError:
            pass

    return "@" + parts[0].lstrip("@"), None, None


def _parse_tme_channel(link: str):
    """Разбирает t.me ссылку на канал/чат → (identifier, msg_id|None)."""
    clean = link.strip().split("?")[0]
    for p in ("https://", "http://"):
        if clean.startswith(p):
            clean = clean[len(p):]
            break
    if clean.startswith("t.me/"):
        clean = clean[5:]
    parts = clean.rstrip("/").split("/")
    if parts[0] == "c" and len(parts) >= 3:
        try:
            return int(parts[1]), int(parts[2])
        except ValueError:
            pass
    if len(parts) >= 2:
        try:
            return parts[0], int(parts[-1])
        except ValueError:
            pass
    return parts[0] if parts else clean, None


OK = "<tg-emoji emoji-id=5458805056990119991>🌘</tg-emoji>"
ERR = "<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji>"
INFO = "<tg-emoji emoji-id=5456307331644037599>🌘</tg-emoji>"

_RANGE = ("range", "Диапазон акков", "Какие аккаунты задействовать: номера из меню, напр. 5-10 (не указал — все)", False)

# id: (заголовок, кнопка в меню, [(поле, кнопка, подсказка, обязательное)])
ACTIONS = {
    "join": ("Вступление в канал/чат", "Вступить в канал/чат", [("link", "Ссылка", "Ссылка на канал/чат", True)]),
    "leave": ("Выход из канала/чата", "Покинуть канал/чат", [("link", "Ссылка", "Ссылка на канал/чат или @юзер", True)]),
    "bot": ("Запуск бота", "Запустить бота", [("link", "Ссылка", "Ссылка на бота (можно реферальную)", True), _RANGE]),
    "send": ("Рассылка", "Рассылка", [("target", "Получатель", "@юзер", True), ("text", "Текст", "Текст сообщения", True)]),
    "react": ("Реакция", "Реакция", [("link", "Ссылка", "Ссылка на пост", True), ("reaction", "Реакция", "Эмодзи реакции", True), _RANGE]),
    "views": ("Просмотры", "Просмотры", [("link", "Канал/пост", "@канал или ссылка на пост", True), ("count", "Кол-во постов", "Сколько последних постов (только для канала)", False)]),
    "button": ("Нажатие кнопки", "Нажать кнопку", [("target", "Ссылка/бот", "Ссылка на сообщение или @бот", True), ("num", "Номер кнопки", "Номер кнопки, с 1", True), _RANGE]),
    "dsoo": ("Удаление сообщений", "Удалить N сообщений", [("target", "Юзер", "@юзер", True), ("count", "Кол-во", "Сколько последних сообщений", True), _RANGE]),
    "block": ("Блокировка", "Заблокировать", [("target", "Юзер", "@юзер", True)]),
    "report": ("Жалоба", "Жалоба", [("target", "Цель", "@юзер или ссылка", True), ("reason", "Причина", None, True), ("comment", "Комментарий", "Комментарий к жалобе", False)]),
    "spam": ("Проверка спам-бана", "Спам-бан", []),
}

REASON_SECTIONS = [
    ("user", "Пользователь"), ("bot", "Бот"), ("channel", "Канал"), ("chat", "Группа/чат"),
    ("photo", "Фото профиля"), ("msg", "Сообщение"), ("story", "История"),
]
REASON_NAMES = {
    "spam": "Спам", "violence": "Насилие", "porn": "Порнография",
    "child": "Жестокость к детям", "copyright": "Авторские права",
    "geo": "Нерелевантное гео", "fake": "Фейк", "drugs": "Наркотики",
    "personal": "Личные данные", "other": "Другое",
    "scam": "Мошенничество", "terrorism": "Терроризм",
    "harassment": "Буллинг", "suicide": "Суицид",
    "impersonation": "Выдаёт себя за другого",
}
REASON_KEYS = {k: list(v) for k, v in REASON_SETS.items() if k in ("user", "bot", "channel", "chat", "photo")}
REASON_KEYS["msg"] = REASON_KEYS["story"] = list(MSG_KW)

FAQ = (
    '<tg-emoji emoji-id="5456217626957091223">🌘</tg-emoji> <strong>FAQ</strong>\n\n'
    "<strong>Как добавить аккаунт?</strong>\n"
    "<blockquote><code>addtvink</code> → «Номер» → «Отправить код» → «Код» (и «Облачный пароль», если есть) → «Подтвердить».\n\n"
    "<strong>Как запустить действие?</strong>\n"
    "<blockquote>Выбери действие в меню, нажми кнопки полей и впиши значения в строку ввода, затем «Запуск».</blockquote>\n\n"
    "<strong>Что такое диапазон аккаунтов?</strong>\n"
    "<blockquote>Номера аккаунтов из меню: <code>3</code> или <code>5-10</code>. Если не указать — действие пойдёт на все аккаунты.</blockquote>\n\n"
    "<strong>Как пожаловаться?</strong>\n"
    "<blockquote>«Жалоба» → «Цель» (@юзер, ссылка на канал, пост или историю) → «Выбрать причину». "
    "«Автоопределение» само поймёт тип цели и отправит все причины.</blockquote>\n\n"
    "<strong>Как удалить аккаунт или выгрузить сессии?</strong>\n"
    "<blockquote><code>delacc 2</code> — удалить аккаунт №2 из меню.\n"
    "<code>tfile</code> — файл со всеми сессиями, лучше только в Избранном.</blockquote>"
)


@loader.tds
class MultiAccMod(loader.Module):
    """Управление всеми своими твинк аккаунтами в Telegram"""

    strings = {"name": "MultiAcc"}

    def __init__(self):
        self._accounts = {}
        self._vals = {}
        self._add = {}
        self._loaded = False
        self._client = None

    # ── Утилиты ──────────────────────────────────────────────

    @staticmethod
    def _phone(raw: str) -> str:
        return re.sub(r"\D", "", raw)

    @staticmethod
    def _name(me) -> str:
        return f"{me.first_name or ''} {me.last_name or ''}".strip() or "Без имени"

    @staticmethod
    def _uname(me) -> str:
        return f"(@{me.username})" if me.username else ""

    def _by_idx(self, idx: int):
        keys = list(self._accounts.keys())
        if 1 <= idx <= len(keys):
            uid = keys[idx - 1]
            return uid, self._accounts[uid]
        return None, None

    def _parse_range(self, s: str):
        if not s:
            return None
        if s.isdigit():
            return [int(s)]
        if "-" in s:
            a, b = s.split("-", 1)
            if a.isdigit() and b.isdigit() and int(a) <= int(b):
                return list(range(int(a), int(b) + 1))
        return None

    def _select(self, range_str=None):
        """Возвращает список (user_id, data) с учётом диапазона и список ошибок."""
        acc_list = list(self._accounts.items())
        if not range_str:
            return acc_list, []

        idxs = self._parse_range(range_str)
        if idxs is None:
            return acc_list, []

        selected, errs = [], []
        for i in idxs:
            if 1 <= i <= len(acc_list):
                selected.append(acc_list[i - 1])
            else:
                errs.append(f"<tg-emoji emoji-id=5456537889783452967>🌘</tg-emoji> Аккаунт #{i} не найден (всего {len(acc_list)})")
        return selected, errs

    def _patch(self, client, me):
        try:
            client.heroku_me = me
            client.me = me
            client._hikka_me = me
        except Exception:
            pass

    def _save(self):
        out = {}
        for uid, d in self._accounts.items():
            try:
                out[uid] = {
                    "session": d["client"].session.save(),
                    "phone": d["phone"],
                    "name": self._name(d["me"]),
                }
            except Exception as e:
                logger.error(f"Не сохранил аккаунт {uid}: {e}")
        self.db.set("MultiAcc", DB_KEY, out)

    # ── Загрузка ─────────────────────────────────────────────

    async def _load(self, client, force=False):
        if self._loaded and not force:
            return

        data = self.db.get("MultiAcc", DB_KEY, {})
        api_id, api_hash = client.api_id, client.api_hash

        if force:
            for d in self._accounts.values():
                try:
                    await d["client"].disconnect()
                except Exception:
                    pass
            self._accounts.clear()

        for uid_str, info in data.items():
            try:
                c = TelegramClient(StringSession(info["session"]), api_id, api_hash)
                await c.connect()
                if not await c.is_user_authorized():
                    continue
                me = await c.get_me()
                self._patch(c, me)
                self._accounts[int(uid_str)] = {
                    "client": c,
                    "me": me,
                    "phone": info.get("phone", ""),
                }
            except Exception as e:
                logger.error(f"Не удалось загрузить аккаунт: {e}")

        self._loaded = True
        self._client = client

    async def _update_info(self):
        updated = errors = 0
        for uid, d in list(self._accounts.items()):
            try:
                c = d["client"]
                if not await c.is_user_authorized():
                    continue
                me = await c.get_me()
                d["me"] = me
                self._patch(c, me)
                updated += 1
            except Exception as e:
                errors += 1
                logger.error(f"Не удалось обновить аккаунт {uid}: {e}")
        if updated:
            self._save()
        return updated, errors

    async def client_ready(self, client, db):
        self.db = db
        await self._load(client)
        if self._accounts:
            updated, errors = await self._update_info()
            logger.info(f"Обновлено: {updated} аккаунтов, ошибок: {errors}")

    # ── Массовые операции (общий паттерн) ────────────────────

    async def _run_on_all(self, range_str, action, not_found="Не найдено"):
        """Запускает action(client, name) на выбранных аккаунтах, возвращает строки результатов."""
        accs, results = self._select(range_str)
        for _, d in accs:
            c, name = d["client"], self._name(d["me"])
            try:
                results.append(await action(c, name))
            except FloodWaitError as e:
                results.append(f"{ERR} {name}: FloodWait {e.seconds}с")
            except Exception as e:
                err = str(e)
                if "Cannot find any entity" in err:
                    err = not_found
                results.append(f"{ERR} {name}: {err}")
        return results

    @staticmethod
    def _result(emoji_id, title, results):
        return (
            f"<tg-emoji emoji-id={emoji_id}>🌘</tg-emoji> <b>{title}:</b>\n\n"
            "<blockquote expandable>" + ("\n".join(results) or "—") + "</blockquote>"
        )

    async def _form(self, message, text, kb):
        unit = await self.inline.form(
            text=text,
            message=message,
            always_allow=[message.sender_id],
            reply_markup=kb,
            manual_security=True,
        )
        if unit and hasattr(unit, "edit"):
            try:
                await asyncio.sleep(0.3)
                await unit.edit(text=text, reply_markup=kb)
            except Exception:
                pass

    # ── Меню ─────────────────────────────────────────────────

    async def accmenucmd(self, message):
        """— меню аккаунтов"""
        await self._load(message.client)
        text, kb = self._menu()
        await self._form(message, text, kb)

    def _menu(self):
        names = "\n".join(f"<b>{i}.</b> {utils.escape_html(self._name(d['me']))}" for i, d in enumerate(self._accounts.values(), 1))
        text = (
            '<tg-emoji emoji-id="5456625794879099391">🌘</tg-emoji> <strong>Меню аккаунтов:</strong>\n\n'
            f"<blockquote expandable>{names or 'Нет аккаунтов'}</blockquote>\n\n"
            "<strong>Выбор действия:</strong>"
        )
        kb = [[{"text": a[1], "callback": self._open_cb, "args": (aid,)}] for aid, a in ACTIONS.items()]
        kb.append([{"text": "FAQ", "callback": self._faq_cb, "style": "primary"}])
        return text, kb

    async def _faq_cb(self, call: InlineCall):
        await call.edit(text=FAQ, reply_markup=[[{"text": "Назад", "callback": self._menu_cb, "style": "danger"}]])

    async def _menu_cb(self, call: InlineCall):
        text, kb = self._menu()
        await call.edit(text=text, reply_markup=kb)

    def _action_view(self, aid):
        title, _, fields = ACTIONS[aid]
        v = self._vals.setdefault(aid, {})
        text = f"<strong>{title}:</strong>"
        filled = [f"{label}: <code>{utils.escape_html(v[k])}</code>" for k, label, _, _ in fields if k in v]
        if filled:
            text += "\n\n<blockquote>" + "\n".join(filled) + "</blockquote>"
        kb = []
        for k, label, prompt, required in fields:
            if prompt is None:  # причина жалобы выбирается кнопками, а не вводом
                kb.append([{"text": "Выбрать причину", "callback": self._reasons_cb}])
                continue
            text_ = label if required else f"{label} (не обяз.)"
            kb.append([{"text": text_, "input": prompt, "handler": self._input_cb, "args": (aid, k)}])
        kb.append([{"text": "Запуск", "callback": self._run_cb, "args": (aid,), "style": "primary"}])
        kb.append([{"text": "Назад", "callback": self._menu_cb, "style": "danger"}])
        return text, kb

    async def _open_cb(self, call: InlineCall, aid):
        self._vals[aid] = {}
        text, kb = self._action_view(aid)
        await call.edit(text=text, reply_markup=kb)

    async def _input_cb(self, call: InlineCall, query, aid, key):
        self._vals.setdefault(aid, {})[key] = query.strip()
        text, kb = self._action_view(aid)
        await call.edit(text=text, reply_markup=kb)

    async def _reasons_cb(self, call: InlineCall):
        kb = [[{"text": "Автоопределение (все причины)", "callback": self._reason_pick_cb, "args": ("all",)}]]
        pairs = [{"text": title, "callback": self._reason_cat_cb, "args": (p,)} for p, title in REASON_SECTIONS]
        kb += [pairs[i:i + 2] for i in range(0, len(pairs), 2)]
        kb.append([{"text": "Назад", "callback": self._back_cb, "args": ("report",), "style": "danger"}])
        await call.edit(
            text="<tg-emoji emoji-id=5456669715214665877>🌘</tg-emoji> <strong>Причина жалобы</strong>\n\nНа кого жалуемся?",
            reply_markup=kb,
        )

    async def _reason_cat_cb(self, call: InlineCall, prefix):
        title = dict(REASON_SECTIONS)[prefix]
        btns = [{"text": REASON_NAMES[k], "callback": self._reason_pick_cb, "args": (f"{prefix}_{k}",)} for k in REASON_KEYS[prefix]]
        kb = [[{"text": "Все причины", "callback": self._reason_pick_cb, "args": (f"{prefix}_all",)}]]
        kb += [btns[i:i + 2] for i in range(0, len(btns), 2)]
        kb.append([{"text": "Назад", "callback": self._reasons_cb, "style": "danger"}])
        hint = "\n\nНужна ссылка на пост." if prefix == "msg" else "\n\nНужна ссылка на историю." if prefix == "story" else ""
        await call.edit(
            text=f"<tg-emoji emoji-id=5456669715214665877>🌘</tg-emoji> <strong>Причина жалобы</strong>\n\n{title}{hint}",
            reply_markup=kb,
        )

    async def _reason_pick_cb(self, call: InlineCall, key):
        self._vals.setdefault("report", {})["reason"] = key
        await self._back_cb(call, "report")

    async def _back_cb(self, call: InlineCall, aid):
        text, kb = self._action_view(aid)
        await call.edit(text=text, reply_markup=kb)

    async def _run_cb(self, call: InlineCall, aid):
        v = self._vals.get(aid, {})
        missing = [label for k, label, _, required in ACTIONS[aid][2] if required and not v.get(k)]
        if missing:
            return await call.answer("Укажи: " + ", ".join(missing), show_alert=True)
        if not self._accounts:
            return await call.answer("Нет аккаунтов", show_alert=True)
        await call.edit('<tg-emoji emoji-id="5328311576736833844">🔴</tg-emoji> <strong>Обработка</strong>')
        try:
            text = await getattr(self, "_a_" + aid)(v)
        except Exception as e:
            text = f"{ERR} <b>Ошибка:</b> <code>{utils.escape_html(str(e))}</code>"
        await call.edit(
            text=text,
            reply_markup=[
                [{"text": "Ещё раз", "callback": self._back_cb, "args": (aid,)}],
                [{"text": "Меню", "callback": self._menu_cb}],
            ],
        )

    # ── Добавление аккаунта ──────────────────────────────────

    async def addtvinkcmd(self, message):
        """— добавить аккаунт"""
        await self._load(message.client)
        self._add = {}
        text, kb = self._add_view()
        await self._form(message, text, kb)

    def _add_view(self, note=""):
        a = self._add
        inp = lambda label, key, prompt: {  # noqa: E731
            "text": label + "", "input": prompt, "handler": self._add_input_cb, "args": (key,),
        }
        if "hash" not in a:
            text = "<strong>Добавление аккаунта:</strong>"
            if a.get("phone"):
                text += f"\n\n<blockquote>Номер: <code>+{self._phone(a['phone'])}</code></blockquote>"
            kb = [
                [inp("Номер", "phone", "Номер телефона, напр. +8801349872616")],
                [{"text": "Отправить код", "callback": self._send_code_cb, "style": "primary"}],
            ]
        else:
            text = f"<tg-emoji emoji-id=5456669715214665877>🌘</tg-emoji> <strong>Код отправлен на +{a['phone']}</strong>"
            filled = []
            if a.get("code"):
                filled.append(f"Код: <code>{utils.escape_html(a['code'])}</code>")
            if a.get("password"):
                filled.append("Облачный пароль: ••••••")
            if filled:
                text += "\n\n<blockquote>" + "\n".join(filled) + "</blockquote>"
            kb = [
                [inp("Код", "code", "Код из Telegram")],
                [inp("Облачный пароль", "password", "Облачный пароль (2FA)")],
                [{"text": "Подтвердить", "callback": self._confirm_cb, "style": "primary"}],
            ]
        if note:
            text += "\n\n" + note
        return text, kb

    async def _add_show(self, call, note=""):
        text, kb = self._add_view(note)
        await call.edit(text=text, reply_markup=kb)

    async def _add_input_cb(self, call: InlineCall, query, key):
        self._add[key] = query.strip()
        await self._add_show(call)

    async def _send_code_cb(self, call: InlineCall):
        phone = self._phone(self._add.get("phone", ""))
        if not phone:
            return await call.answer("Укажи номер", show_alert=True)
        await call.edit('<tg-emoji emoji-id="5328311576736833844">🔴</tg-emoji> <strong>Обработка</strong>')
        try:
            c = TelegramClient(StringSession(), self._client.api_id, self._client.api_hash)
            await c.connect()
            sent = await c.send_code_request("+" + phone)
        except Exception as e:
            return await self._add_show(call, f"{ERR} <b>Ошибка:</b> <code>{utils.escape_html(str(e))}</code>")
        self._add.update(client=c, hash=sent.phone_code_hash, phone=phone)
        await self._add_show(call)

    async def _confirm_cb(self, call: InlineCall):
        a = self._add
        # цифры из кода, чтобы можно было вводить «1 2 3 4 5» — Telegram сжигает код, если видит его целиком
        code = re.sub(r"\D", "", a.get("code", ""))
        if not code and not a.get("need_pw"):
            return await call.answer("Укажи код", show_alert=True)
        c, phone = a["client"], a["phone"]
        await call.edit('<tg-emoji emoji-id="5328311576736833844">🔴</tg-emoji> <strong>Обработка</strong>')
        try:
            if not a.get("need_pw"):
                try:
                    await c.sign_in("+" + phone, code, phone_code_hash=a["hash"])
                except SessionPasswordNeededError:
                    a["need_pw"] = True
            if a.get("need_pw"):
                if not a.get("password"):
                    return await self._add_show(call, f"<tg-emoji emoji-id=5456217626957091223>🌘</tg-emoji> <b>Нужен облачный пароль!</b>")
                await c.sign_in(password=a["password"])
        except PhoneCodeInvalidError:
            return await self._add_show(call, f"{INFO} Неверный код")
        except Exception as e:
            return await self._add_show(call, f"{ERR} <b>Ошибка:</b> <code>{utils.escape_html(str(e))}</code>")

        me = await c.get_me()
        ss = c.session.save()
        await c.disconnect()

        c2 = TelegramClient(StringSession(ss), self._client.api_id, self._client.api_hash)
        await c2.connect()
        self._patch(c2, me)

        self._accounts[me.id] = {"client": c2, "me": me, "phone": phone}
        self._save()
        self._add = {}

        await call.edit(
            text=(
                f"<tg-emoji emoji-id=5456250960198274077>🌘</tg-emoji> <b>Аккаунт добавлен:</b>\n"
                f"┌ {self._name(me)}\n├ +{phone}\n└ {me.id}"
            ),
            reply_markup=[[{"text": "Меню", "callback": self._menu_cb}]],
        )

    # ── Действия меню (v — значения полей из ACTIONS) ────────

    async def delacccmd(self, message):
        """[номер] — удалить аккаунт (номер из .accmenu)"""
        await self._load(message.client)
        args = utils.get_args_raw(message).strip()
        if not args.isdigit():
            return await utils.answer(message, f"{INFO} <code>.delacc 1</code> (номер из <code>.accmenu</code>)")
        await utils.answer(message, await self._a_delacc({"num": args}))

    async def _a_delacc(self, v):
        if not v["num"].isdigit():
            return f"{INFO} Номер аккаунта — число из списка"
        uid, d = self._by_idx(int(v["num"]))
        if uid is None:
            return f"{INFO} Аккаунт не найден"
        name = self._name(d["me"])
        try:
            await d["client"].disconnect()
        except Exception:
            pass
        del self._accounts[uid]
        self._save()
        return f"<tg-emoji emoji-id=5458572596180193103>🌘</tg-emoji> <b>Аккаунт удалён:</b> {name}"

    async def _a_join(self, v):
        results = []
        for _, d in self._accounts.items():
            c, name = d["client"], self._name(d["me"])
            try:
                await self._do_join(c, v["link"])
                results.append(f"{OK} {name}")
            except UserAlreadyParticipantError:
                results.append(f"{ERR} {name} — уже в чате")
            except (InviteHashExpiredError, InviteHashInvalidError, ChannelPrivateError) as e:
                results.append(f"{ERR} {name}: {type(e).__name__}")
                break
            except Exception as e:
                results.append(f"{ERR} {name}: {e}")
        return self._result("5458502532378693210", "Результат вступления", results)

    @staticmethod
    async def _do_join(client, link):
        link = link.strip().rstrip("/")
        last = link.split("/")[-1]
        if last.startswith("+") or "joinchat" in link:
            await client(ImportChatInviteRequest(last.lstrip("+")))
        else:
            await client(JoinChannelRequest(await client.get_entity(link)))

    async def _a_leave(self, v):
        async def act(c, name):
            try:
                entity = await c.get_entity(v["link"])
                if getattr(entity, "broadcast", False) or getattr(entity, "megagroup", False) or getattr(entity, "id", 0) < 0:
                    await c(LeaveChannelRequest(entity))
                    return f"{OK} {name} — покинул(а)"
                await c.delete_dialog(entity, revoke=False)
                return f"{OK} {name} — диалог удалён"
            except Exception as e:
                if any(x in str(e) for x in ("CHANNEL_PRIVATE", "USER_NOT_PARTICIPANT", "not in the channel")):
                    return f"{ERR} {name} — не состоит в чате"
                raise

        return self._result("5458567764341985638", "Результат выхода", await self._run_on_all(None, act))

    async def _a_bot(self, v):
        clean = v["link"]
        for p in ("https://", "http://"):
            if clean.startswith(p):
                clean = clean[len(p):]
        if clean.startswith("t.me/"):
            clean = clean[5:]

        start_param = None
        if "?" in clean:
            bot_part, query = clean.split("?", 1)
            for pair in query.split("&"):
                if pair.startswith("start="):
                    start_param = pair.split("=", 1)[1]
                    break
            clean = bot_part

        bot_name = clean.rstrip("/").split("/")[-1].lstrip("@")
        if not bot_name:
            return f"{ERR} Не удалось определить бота"
        msg_text = f"/start {start_param}" if start_param else "/start"

        async def act(c, name):
            await c.send_message(bot_name, msg_text)
            return f"{OK} {name}"

        return self._result("5458396206168312985", "Результат запуска бота", await self._run_on_all(v.get("range"), act))

    async def _a_send(self, v):
        async def act(c, name):
            await c.send_message(v["target"].lstrip("@"), v["text"])
            return f"{OK} {name}"

        return self._result("5458567764341985638", "Результат рассылки", await self._run_on_all(None, act))

    async def _a_react(self, v):
        ident, msg_id = _parse_tme_channel(v["link"])
        if msg_id is None:
            return f"{ERR} Не удалось разобрать ссылку"

        async def act(c, name):
            await c.send_reaction(await c.get_entity(ident), message=msg_id, reaction=[v["reaction"]])
            return f"{OK} {name}"

        results = await self._run_on_all(v.get("range"), act, "Не подписан на канал")
        return self._result("5456469226141288702", "Результат реакций", results)

    async def _a_views(self, v):
        ident, msg_id = _parse_tme_channel(v["link"])

        if msg_id is not None:
            msg_ids = [msg_id]
        else:
            count = v.get("count", "")
            if not count.isdigit():
                return f"{INFO} Для канала укажи количество постов"
            ch_name = v["link"].strip()
            for p in ("https://", "http://"):
                if ch_name.startswith(p):
                    ch_name = ch_name[len(p):]
            if ch_name.startswith("t.me/"):
                ch_name = ch_name[5:]
            ident = "@" + ch_name.rstrip("/").lstrip("@")

            try:
                entity = await self._client.get_entity(ident)
                msg_ids = [m.id async for m in self._client.iter_messages(entity, limit=int(count))]
            except Exception as e:
                return f"{ERR} Не получить посты: <code>{e}</code>"
            if not msg_ids:
                return f"{INFO} Постов не найдено"

        async def act(c, name):
            entity = await c.get_entity(ident)
            for i in range(0, len(msg_ids), 100):
                await c(GetMessagesViewsRequest(peer=entity, id=msg_ids[i:i+100], increment=True))
                await asyncio.sleep(0.3)
            return f"{OK} {name}"

        results = await self._run_on_all(None, act, "Не подписан на канал")
        return self._result("5458443008426936556", "Результат просмотров", results)

    async def _a_spam(self, v):
        FREE = ["free as a bird", "no limits", "свободен", "ограничений", "good news",
                "не имеете ограничений", "no restrictions", "without any limits", "no limitations"]
        BANNED = ["ограничен", "limited", "заблокирован", "restricted", "spam ban",
                  "anti-spam", "cannot send messages", "не можете отправлять сообщения"]

        async def act(c, name):
            try:
                async with c.conversation("@SpamBot") as conv:
                    await conv.send_message("/start")
                    resp = await conv.get_response()
            except Exception as e:
                if "is not a chat member" in str(e):
                    return f"{ERR} {name}: Не удалось начать диалог с @SpamBot"
                raise
            low = resp.text.lower()
            if any(x in low for x in FREE) or not any(x in low for x in BANNED):
                return f"{OK} {name} — чист"
            date = re.search(r"(?:до|until)\s+(\d{1,2}[.\s]\w+[.\s]\d{4})", resp.text, re.I)
            return f"{ERR} {name} — ОГРАНИЧЕН" + (f" до {date.group(1)}" if date else "")

        return self._result("5458443008426936556", "Спам-бан", await self._run_on_all(None, act))

    async def _a_button(self, v):
        if not v["num"].isdigit() or int(v["num"]) < 1:
            return f"{ERR} Номер кнопки должен быть > 0"
        target, btn_idx = v["target"], int(v["num"]) - 1
        is_link = target.startswith("http://") or target.startswith("https://")

        async def act(c, name):
            if is_link:
                ident, msg_id = _parse_tme_channel(target)
                if msg_id is None:
                    return f"{ERR} {name}: не разобрал ссылку"
                msg_obj = await c.get_messages(await c.get_entity(ident), ids=msg_id)
            else:
                msgs = await c.get_messages(await c.get_entity(target), limit=5)
                msg_obj = msgs[0] if msgs else None

            if not msg_obj:
                return f"{ERR} {name}: сообщение не найдено"
            if not msg_obj.reply_markup or not msg_obj.reply_markup.rows:
                return f"{ERR} {name}: нет кнопок"
            btns = [b for row in msg_obj.reply_markup.rows for b in row.buttons]
            if btn_idx >= len(btns):
                return f"{ERR} {name}: кнопки #{btn_idx+1} нет (всего {len(btns)})"
            await msg_obj.click(btn_idx)
            return f"{OK} {name}"

        return self._result("5458443008426936556", "Результат кнопок", await self._run_on_all(v.get("range"), act))

    async def _a_dsoo(self, v):
        if not v["count"].isdigit() or int(v["count"]) < 1:
            return f"{ERR} Количество должно быть > 0"
        target, count = v["target"].lstrip("@"), int(v["count"])

        async def act(c, name):
            msgs = [m async for m in c.iter_messages(await c.get_entity(target), limit=count)]
            if not msgs:
                return f"{INFO} {name} — нет сообщений"
            deleted = 0
            for m in msgs:
                try:
                    await m.delete()
                    deleted += 1
                    await asyncio.sleep(0.3)
                except Exception:
                    pass
            return f"{OK} {name} — удалено {deleted}" if deleted else f"{INFO} {name} — нечего удалять"

        results = await self._run_on_all(v.get("range"), act, "Пользователь не найден")
        return self._result("5458567764341985638", "Удаление сообщений", results)

    async def _a_block(self, v):
        clean = v["target"].lstrip("@").split()[0]

        async def act(c, name):
            await c(BlockRequest(id=await c.get_entity(clean)))
            return f"{OK} {name}"

        return self._result("5458567764341985638", "Блокировка", await self._run_on_all(None, act, "Не найден"))

    # ── Файл с сессиями ──────────────────────────────────────

    async def tfilecmd(self, message):
        """— выгрузить файл со всеми сессиями"""
        await self._load(message.client)
        if not self._accounts:
            return await utils.answer(message, f"{INFO} Нет аккаунтов")

        me = await message.client.get_me()
        if message.is_private and message.chat_id == me.id:
            await utils.answer(message, f"<tg-emoji emoji-id=5445355530111437729>📤</tg-emoji> Отправляю файл...")
            _, text = await self._send_file(message.client, message.chat_id)
            return await utils.answer(message, text)

        await self._form(
            message,
            (
                f"<tg-emoji emoji-id=5980925264589232084>⚠️</tg-emoji> <b>ВНИМАНИЕ!</b> <tg-emoji emoji-id=5980925264589232084>⚠️</tg-emoji>\n\n"
                "Ты собираешься выгрузить файл со всеми сессиями.\n"
                "Он содержит <b>критически важные данные</b>.\n\n"
                "<b><u>Рекомендуется делать это только в Избранном.</u></b>\n\n"
                "Продолжить?"
            ),
            [[
                {"text": "Да, точно!", "callback": self._file_yes, "args": (message.chat_id,), "style": "danger"},
                {"text": "Нет", "callback": self._file_no, "args": (message.chat_id,), "style": "primary"},
            ]],
        )

    async def _file_yes(self, call: InlineCall, chat_id: int):
        await call.edit(f"<tg-emoji emoji-id=5445355530111437729>📤</tg-emoji> Отправляю файл...")
        _, text = await self._send_file(self._client, chat_id)
        await call.edit(text)

    async def _file_no(self, call: InlineCall, chat_id: int):
        await call.delete()
        await call.answer("Файл не отправлен.", show_alert=True)

    async def _send_file(self, client, chat_id):
        try:
            data = self.db.get("MultiAcc", DB_KEY, {})
            if not data:
                return False, f"{ERR} Нет данных"
            buf = io.BytesIO(json.dumps(data, indent=2, ensure_ascii=False).encode())
            buf.name = f"tvink-sessions_{datetime.now():%Y%m%d_%H%M%S}.json"
            await client.send_file(
                chat_id, buf,
                caption=f"<tg-emoji emoji-id=5458851476996657778>🌘</tg-emoji> Файл со всеми сессиями",
                parse_mode="html",
            )
            return True, f"{OK} Файл отправлен."
        except Exception as e:
            return False, f"{ERR} Ошибка: {e}"

    # ── Жалобы ───────────────────────────────────────────────

    async def _a_report(self, v):
        target_raw = v["target"]
        reason_key = v["reason"].lower()
        comment = v.get("comment") or None
        peer_id, target_id, kind = _parse_tme(target_raw)

        # Собираем задачи: (type, data, label)
        tasks = self._build_report_tasks(reason_key, kind, target_id)
        if isinstance(tasks, str):
            if tasks == "detect":
                detected = await self._detect_kind(peer_id)
                if detected and detected in REASON_SETS:
                    prefix = detected + "_"
                    tasks = [("peer", cls, f"{prefix}{k}") for k, cls in REASON_SETS[detected].items()]
                else:
                    tasks = [("peer", cls, k) for k, cls in REASON_SETS["legacy"].items()]
            else:
                return tasks

        if any(t[0] == "story" for t in tasks) and not _STORY_REPORT:
            return f"{ERR} Жалобы на истории не поддерживаются. Обнови Telethon."

        results = []
        for _, d in self._accounts.items():
            c, name = d["client"], self._name(d["me"])
            for rtype, reason_data, label in tasks:
                try:
                    entity = await c.get_entity(peer_id)

                    auto_cmt = _auto_comment(label, comment)

                    if rtype == "peer":
                        await c(ReportPeerRequest(entity, reason_data(), auto_cmt))
                    elif rtype == "photo":
                        photos = await c.get_profile_photos(entity, limit=1)
                        if not photos:
                            raise ValueError("Нет фото профиля")
                        from telethon import utils as tutils
                        await c(ReportProfilePhotoRequest(
                            entity, tutils.get_input_photo(photos[0]),
                            reason_data(), auto_cmt,
                        ))
                    elif rtype == "msg":
                        await self._report_tree(c, ReportRequest, entity, [target_id], reason_data, auto_cmt)
                    elif rtype == "story":
                        await self._report_tree(c, StoryReportRequest, entity, [target_id], reason_data, auto_cmt)

                    results.append(f"{OK} <b>{name}</b> — <i>{label}</i>")
                except Exception as e:
                    results.append(f"{ERR} <b>{name}</b>: <code>{e}</code> (<i>{label}</i>)")

        return self._result("5458567764341985638", "Результат жалоб", results)

    def _build_report_tasks(self, key, kind, target_id):
        """Возвращает список задач или строку-ошибку ('detect' = нужно определить тип)."""
        if key == "all":
            if kind == "msg":
                return [("msg", kw, f"msg_{k}") for k, kw in MSG_KW.items()]
            if kind == "story":
                return [("story", kw, f"story_{k}") for k, kw in MSG_KW.items()]
            return "detect"

        for prefix in ("user", "bot", "channel", "chat", "photo"):
            if key == f"{prefix}_all":
                rtype = "photo" if prefix == "photo" else "peer"
                return [(rtype, cls, f"{prefix}_{k}") for k, cls in REASON_SETS[prefix].items()]

        if key == "msg_all":
            if kind != "msg":
                return "<tg-emoji emoji-id=5456307331644037599>🌘</tg-emoji> Для <code>msg_*</code> нужна ссылка на сообщение"
            return [("msg", kw, f"msg_{k}") for k, kw in MSG_KW.items()]

        if key == "story_all":
            if kind != "story":
                return "<tg-emoji emoji-id=5456307331644037599>🌘</tg-emoji> Для <code>story_*</code> нужна ссылка на историю"
            return [("story", kw, f"story_{k}") for k, kw in MSG_KW.items()]

        for prefix in ("user", "bot", "channel", "chat"):
            if key.startswith(prefix + "_"):
                short = key[len(prefix) + 1:]
                if short in REASON_SETS[prefix]:
                    return [("peer", REASON_SETS[prefix][short], key)]

        if key.startswith("photo_"):
            short = key[6:]
            if short in REASON_SETS["photo"]:
                return [("photo", REASON_SETS["photo"][short], key)]

        if key.startswith("msg_"):
            if kind != "msg":
                return "<tg-emoji emoji-id=5456307331644037599>🌘</tg-emoji> Для <code>msg_*</code> нужна ссылка на сообщение"
            short = key[4:]
            if short in MSG_KW:
                return [("msg", MSG_KW[short], key)]

        if key.startswith("story_"):
            if kind != "story":
                return "<tg-emoji emoji-id=5456307331644037599>🌘</tg-emoji> Для <code>story_*</code> нужна ссылка на историю"
            short = key[6:]
            if short in MSG_KW:
                return [("story", MSG_KW[short], key)]

        if key in REASON_SETS["legacy"]:
            return [("peer", REASON_SETS["legacy"][key], key)]

        return f"<tg-emoji emoji-id=5456307331644037599>🌘</tg-emoji> Неизвестная причина: <code>{key}</code>. См. кнопку «Причины»"

    async def _detect_kind(self, peer_id):
        if not self._accounts:
            return None
        c = next(iter(self._accounts.values()))["client"]
        try:
            entity = await c.get_entity(peer_id)
        except Exception:
            return None
        tn = type(entity).__name__
        if tn == "User":
            return "bot" if getattr(entity, "bot", False) else "user"
        if tn == "Channel":
            return "chat" if getattr(entity, "megagroup", False) else "channel"
        if tn == "Chat":
            return "chat"
        return None

    async def _report_tree(self, c, req_cls, entity, ids, keywords, comment=None):
        option = b""
        msg = ""
        for _ in range(6):
            result = await c(req_cls(entity, ids, option, msg))
            tn = type(result).__name__

            if tn == "ReportResultReported":
                return

            if tn == "ReportResultChooseOption":
                opts = getattr(result, "options", []) or []
                if not opts:
                    raise ValueError("Сервер не вернул причин")
                chosen = None
                for o in opts:
                    if any(kw in getattr(o, "text", "").lower() for kw in keywords):
                        chosen = o
                        break
                option = getattr(chosen or opts[-1], "option", b"")
                msg = ""
                continue

            if tn == "ReportResultAddComment":
                option = getattr(result, "option", option)
                optional = getattr(result, "optional", True)
                if comment:
                    msg = comment
                elif optional:
                    msg = ""
                else:
                    msg = "Report"
                continue

            return

        raise ValueError("Не пройдено дерево причин за 6 шагов")
