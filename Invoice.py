# ◇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◇
# meta developer: @dubai_ip
# meta banner: https://raw.githubusercontent.com/crypto-killu/modules-by-killu/main/Module-banners/Invoice.jpg
# scope: Heroku, Hikka
# version: 1.0
# author: Killu
# Description: Создает в чате инвойс на звезды, оплата идет в бота из конфига.
# ◇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◇

from .. import loader, utils
from telethon.tl.types import Message
import asyncio
import uuid
import aiohttp

API = "https://api.telegram.org/bot{}/{}"


@loader.tds
class InvoiceMod(loader.Module):
    """Инвойсы на звезды через своего бота"""

    strings = {
        "name": "Invoice",
        "no_token": "<emoji document_id=5980869107891838347>❌</emoji> <b>Укажи токен бота:</b> <code>cfg Invoice</code>",
        "bad_args": "<emoji document_id=5980869107891838347>❌</emoji> <b>Использование:</b> <code>invoice 50</code>",
        "api_error": "<emoji document_id=5980869107891838347>❌</emoji> <b>Ошибка Bot API:</b> {}",
        "created": (
            "<b>Счет на {amount}</b> <tg-emoji emoji-id=\"5924870095925942277\">⭐️</tg-emoji>"
        ),
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "bot_token", "", "Токен бота, в которого идут звезды",
                validator=loader.validators.Hidden(),
            ),
        )

    async def _api(self, method, **params):
        # no getUpdates here — the bot's main app keeps receiving its updates
        async with aiohttp.ClientSession() as s:
            async with s.post(API.format(self.config["bot_token"], method), json=params) as r:
                data = await r.json()
        if not data.get("ok"):
            raise RuntimeError(data.get("description"))
        return data["result"]

    async def invoicecmd(self, message: Message):
        """<кол-во звезд> — создать инвойс на звезды"""
        if not self.config["bot_token"]:
            return await utils.answer(message, self.strings("no_token"))
        args = utils.get_args_raw(message).strip()
        if not args.isdigit() or int(args) < 1:
            return await utils.answer(message, self.strings("bad_args"))
        amount = int(args)
        try:
            link = await self._api(
                "createInvoiceLink",
                title="оплату счета",
                description=f"{amount} ⭐️",
                payload=uuid.uuid4().hex,
                currency="XTR",
                prices=[{"label": f"{amount} ⭐️", "amount": amount}],
            )
        except Exception as e:
            return await utils.answer(message, self.strings("api_error").format(utils.escape_html(str(e))))
        text = self.strings("created").format(amount=amount)
        kb = [[{"text": "Оплатить", "url": link}]]
        form = await self.inline.form(text=text, message=message, reply_markup=kb)
        # premium emoji in inline messages only render after the first edit
        if form and hasattr(form, "edit"):
            try:
                await asyncio.sleep(0.3)
                await form.edit(text=text, reply_markup=kb)
            except Exception:
                pass
