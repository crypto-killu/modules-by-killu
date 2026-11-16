# ◇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◇
# meta developer: @dubai_ip
# meta banner: https://raw.githubusercontent.com/crypto-killu/modules-by-killu/main/Module-banners/GiftStats.jpg
# scope: Heroku, Hikka
# version: 2.8
# author: Killu
# Description: Анализирует подарки в профиле, и называет цену всех подарков.
# ◇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◇

from .. import loader, utils
from telethon.tl.types import Message, InputPeerSelf
from telethon.tl.functions.payments import (
    GetSavedStarGiftsRequest,
    GetUniqueStarGiftValueInfoRequest,
    GetStarsTransactionsRequest,
    GetStarsStatusRequest,
)
import asyncio
import logging

logger = logging.getLogger(__name__)

@loader.tds
class GiftStatsMod(loader.Module):
    """Показывает статистику подарков пользователя"""

    strings = {
        "name": "GiftStats",
        "processing": "<emoji document_id=5328311576736833844>🔴</emoji> Получаю статистику подарков...",
        "user_not_found": "<emoji document_id=5980869107891838347>❌</emoji> Пользователь не найден!",
        "no_gifts": "<emoji document_id=5980869107891838347>❌</emoji> У пользователя {} нет подарков.",
        "api_error": "<emoji document_id=5980869107891838347>❌</emoji> Ошибка при получении данных: {}",
        "stats": (
            "<emoji document_id=6037175527846975726>🎁</emoji> <b>Статистика подарков {name}</b>:\n"
            "• <emoji document_id=6028435952299413210>ℹ️</emoji> Всего подарков: {total}\n"
            "• <emoji document_id=6050847684355428245>🖌</emoji> Обычных подарков: {regular}\n"
            "• <emoji document_id=5811925731785052842>🖌</emoji> Лимитированных: {limited}\n"
            "• <emoji document_id=5890727932011223292>🏷</emoji> Самый дорогой обычный: {max_regular} <emoji document_id=5924870095925942277>⭐️</emoji>\n"
            "• <emoji document_id=5890883384057533697>🏷</emoji> Самый дорогой\n   лимитированный: {max_limited} <emoji document_id=5924870095925942277>⭐️</emoji>\n"
            "• <emoji document_id=5890925363067886150>✨</emoji> NFT подарков: {nft}\n"
            "{hidden}"
            "• <emoji document_id=5879905000972358125>👥</emoji> Общая стоимость подарков\n   за звезды: {total_stars} <emoji document_id=5924870095925942277>⭐️</emoji>\n"
            "• <emoji document_id=5891105528356018797>💎</emoji> Общая стоимость NFT: {nft_value}"
        ),
        "hidden": (
            "• <emoji document_id=6037243349675544634>👁</emoji> Скрытых: {}\n"
            "• <emoji document_id=6037397706505195857>👁</emoji> Открытых: {}\n"
        ),
        "stars_stats_footer": (
            "\n\n<tg-emoji emoji-id=5444860552310457690>💰</tg-emoji><b> Количество транзакций:</b> {}\n"
            "├ Звезд отправлено: {}\n"
            "└ Звезд получено: {}\n"
            "<b>Баланс сейчас:</b> {}"
        ),
    }

    async def giftstatcmd(self, message: Message):
        """[юзернейм/реплай/ID] — получить статистику подарков пользователя"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()

        await message.edit(self.strings("processing"))

        try:
            peer, is_self = await self._get_peer_and_check_self(message, args, reply)
        except Exception:
            await message.edit(self.strings("user_not_found"))
            return

        all_gifts = await self._fetch_all_gifts(message.client, peer)
        if all_gifts is None:
            await message.edit(self.strings("api_error").format("Не удалось получить подарки"))
            return

        name = await self._get_display_name(message.client, peer)
        if not all_gifts:
            await message.edit(self.strings("no_gifts").format(name))
            return

        stats = await self._calculate_stats(all_gifts, is_self)

        # киньте мне мишку на пропитание, пж
        nft_value_str = await self._get_nft_total_values(message.client, all_gifts)

        stats_text = self.strings("stats").format(
            name=name,
            total=stats['обычные'] + stats['лимитированные'] + stats['nft'],
            regular=stats['обычные'],
            limited=stats['лимитированные'],
            max_regular=stats['max_обычный'] or "нету",
            max_limited=stats['max_лимитированный'] or "нету",
            nft=stats['nft'],
            hidden=self.strings("hidden").format(stats['скрытые'], stats['открытые']) if is_self else "",
            total_stars=stats['total_stars'],
            nft_value=nft_value_str,
        )

        if is_self:
            s = await self._fetch_stars_summary(message.client)
            balance = s['balance'] if isinstance(s['balance'], str) else self._format_stars(s['balance'])
            stats_text += self.strings("stars_stats_footer").format(
                s['total_tx'], self._format_stars(s['sent']), self._format_stars(s['received']), balance,
            )

        await message.edit(stats_text)

    @staticmethod
    def _stars_amount_to_float(amount_obj):
        """Переводит StarsAmount (amount + nanos) в float с учётом дробной части.
        1 nano = 1e-9 звезды. Знак nanos следует знаку amount, если amount != 0,
        иначе берём знак самого nanos (для чисто дробных сумм)."""
        if amount_obj is None:
            return 0.0
        amount = getattr(amount_obj, 'amount', 0) or 0
        nanos = getattr(amount_obj, 'nanos', 0) or 0
        if amount != 0:
            sign = 1 if amount > 0 else -1
            return amount + sign * (abs(nanos) / 1_000_000_000)
        return nanos / 1_000_000_000

    @staticmethod
    def _format_stars(value: float) -> str:
        """Форматирует звёзды: целые — без десятичных, дробные — максимум 2 знака после точки."""
        value = round(value, 2)
        if value == int(value):
            return str(int(value))
        return f"{value:.2f}".rstrip('0').rstrip('.')

    async def _fetch_stars_summary(self, client, limit=100, max_pages=1000):
        """Число звёздных транзакций, сколько отправлено/получено и текущий баланс.
        max_pages — защита от бесконечного цикла, а не лимит истории."""
        try:
            status = await client(GetStarsStatusRequest(peer=InputPeerSelf()))
            balance = self._stars_amount_to_float(getattr(status, 'balance', None))
        except Exception:
            logger.exception("GetStarsStatus failed")
            balance = "н/д"

        sent = received = 0.0
        total_tx = 0
        offset = ""
        for _ in range(max_pages):
            try:
                result = await client(GetStarsTransactionsRequest(peer=InputPeerSelf(), offset=offset, limit=limit))
            except Exception:
                logger.exception("GetStarsTransactions failed")
                break

            transactions = getattr(result, 'history', None) or []
            total_tx += len(transactions)
            for tx in transactions:
                value = self._stars_amount_to_float(getattr(tx, 'amount', None))
                if value < 0:
                    sent -= value
                else:
                    received += value

            offset = getattr(result, 'next_offset', '') or ''
            if not offset or len(transactions) < limit:
                break
            await asyncio.sleep(0.3)  # чтобы не словить FloodWait на большой истории

        return {'total_tx': total_tx, 'sent': sent, 'received': received, 'balance': balance}

    async def _get_peer_and_check_self(self, message, args, reply):
        client = message.client
        me = await client.get_me()
        if args:
            try:
                if args.lstrip('-').isdigit():
                    entity = await client.get_entity(int(args))
                else:
                    entity = await client.get_entity(args)
            except Exception:
                raise ValueError("User not found")
            peer = await client.get_input_entity(entity)
            is_self = entity.id == me.id
        elif reply:
            sender = await reply.get_sender()
            peer = await client.get_input_entity(sender)
            is_self = sender.id == me.id
        else:
            peer = InputPeerSelf()
            is_self = True
        return peer, is_self

    async def _fetch_all_gifts(self, client, peer, limit=100):
        all_gifts = []
        offset = ""
        try:
            while True:
                result = await client(GetSavedStarGiftsRequest(
                    peer=peer,
                    offset=offset,
                    limit=limit
                ))
                gifts = getattr(result, 'gifts', [])
                all_gifts.extend(gifts)

                if len(gifts) < limit:
                    break
                offset = getattr(result, 'next_offset', '')
                if not offset:
                    break
            return all_gifts
        except Exception:
            return None

    async def _get_nft_total_values(self, client, gifts):
        """Суммирует стоимость всех NFT по данным API, отдельно по каждой валюте."""
        slugs = [
            gift.slug
            for gift in (getattr(g, 'gift', g) for g in gifts)
            if (hasattr(gift, 'gift_address') or hasattr(gift, 'owner_address')) and getattr(gift, 'slug', None)
        ]
        if not slugs:
            return "нету NFT"

        sem = asyncio.Semaphore(5)  # не больше 5 запросов разом, иначе FloodWait на больших коллекциях

        async def fetch_value(slug):
            async with sem:
                try:
                    r = await client(GetUniqueStarGiftValueInfoRequest(slug=slug))
                    return getattr(r, 'currency', 'RUB'), getattr(r, 'value', 0) or 0
                except Exception as e:
                    logger.warning("Нет цены для %s: %s", slug, e)
                    return None, 0

        totals = {}
        for currency, value in await asyncio.gather(*map(fetch_value, slugs)):
            if currency and value:
                totals[currency] = totals.get(currency, 0) + value
        if not totals:
            return "нету данных о ценах"
        # shortcut: считаем, что у валюты 2 знака после запятой (RUB, USD); для JPY и т.п. будет в 100 раз меньше
        return ", ".join(f"{int(v / 100)} {cur}" for cur, v in totals.items())

    async def _calculate_stats(self, gifts, is_self):
        обычные = 0
        лимитированные = 0
        nft = 0
        скрытые = 0
        открытые = 0
        max_обычный = 0
        max_лимитированный = 0
        total_stars = 0

        for saved_gift in gifts:
            gift = getattr(saved_gift, 'gift', saved_gift)
            price = getattr(gift, 'stars', 0) or getattr(gift, 'price', 0)
            is_limited = getattr(gift, 'limited', False)
            is_nft = hasattr(gift, 'gift_address') or hasattr(gift, 'owner_address')

            if is_self:
                hidden = getattr(saved_gift, 'unsaved', False)
            else:
                hidden = False

            total_stars += price

            if is_self:
                if hidden:
                    скрытые += 1
                else:
                    открытые += 1

            if is_nft:
                nft += 1

            if is_limited:
                лимитированные += 1
                if price > max_лимитированный:
                    max_лимитированный = price
            else:
                if not is_nft:
                    обычные += 1
                    if price > max_обычный:
                        max_обычный = price

        if not is_self:
            открытые = len(gifts)
            скрытые = 0

        return {
            'обычные': обычные,
            'лимитированные': лимитированные,
            'nft': nft,
            'скрытые': скрытые,
            'открытые': открытые,
            'max_обычный': max_обычный,
            'max_лимитированный': max_лимитированный,
            'total_stars': total_stars
        }

    async def _get_display_name(self, client, peer):
        try:
            entity = await client.get_entity(peer)
            return utils.escape_html(getattr(entity, 'first_name', None) or getattr(entity, 'username', None) or str(entity.id))
        except Exception:
            return "пользователь"
