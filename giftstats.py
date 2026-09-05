# ◇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◇
# meta developer: @dubai_ip
# meta banner: https://raw.githubusercontent.com/crypto-killu/modules-by-killu/main/Module-banners/GiftStats.jpg
# scope: Heroku, Hikka
# version: 2.7
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

@loader.tds
class GiftStatsMod(loader.Module):
    """Показывает статистику подарков пользователя"""

    strings = {
        "name": "GiftStats",
        "processing": "<emoji document_id=5328311576736833844>🔴</emoji> Получаю статистику подарков...",
        "user_not_found": "<emoji document_id=5980869107891838347>❌</emoji> Пользователь не найден!",
        "no_gifts": "<emoji document_id=5980869107891838347>❌</emoji> У пользователя {} нет подарков.",
        "api_error": "<emoji document_id=5980869107891838347>❌</emoji> Ошибка при получении данных: {}",
        "stats_self": (
            "<emoji document_id=6037175527846975726>🎁</emoji> <b>Статистика подарков {}</b>:\n"
            "• <emoji document_id=6028435952299413210>ℹ️</emoji> Всего подарков: {}\n"
            "• <emoji document_id=6050847684355428245>🖌</emoji> Обычных подарков: {}\n"
            "• <emoji document_id=5811925731785052842>🖌</emoji> Лимитированных: {}\n"
            "• <emoji document_id=5890727932011223292>🏷</emoji> Самый дорогой обычный: {} <emoji document_id=5924870095925942277>⭐️</emoji>\n"
            "• <emoji document_id=5890883384057533697>🏷</emoji> Самый дорогой\n   лимитированный: {} <emoji document_id=5924870095925942277>⭐️</emoji>\n"
            "• <emoji document_id=5890925363067886150>✨</emoji> NFT подарков: {}\n"
            "• <emoji document_id=6037243349675544634>👁</emoji> Скрытых: {}\n"
            "• <emoji document_id=6037397706505195857>👁</emoji> Открытых: {}\n"
            "• <emoji document_id=5879905000972358125>👥</emoji> Общая стоимость подарков\n   за звезды: {} <emoji document_id=5924870095925942277>⭐️</emoji>\n"
            "• <emoji document_id=5891105528356018797>💎</emoji> Общая стоимость NFT: {}"
        ),
        "stats_other": (
            "<emoji document_id=6037175527846975726>🎁</emoji> <b>Статистика подарков {}</b>:\n"
            "• <emoji document_id=6028435952299413210>ℹ️</emoji> Всего подарков: {}\n"
            "• <emoji document_id=6050847684355428245>🖌</emoji> Обычных подарков: {}\n"
            "• <emoji document_id=5811925731785052842>🖌</emoji> Лимитированных: {}\n"
            "• <emoji document_id=5890727932011223292>🏷</emoji> Самый дорогой обычный: {} <emoji document_id=5924870095925942277>⭐️</emoji>\n"
            "• <emoji document_id=5890883384057533697>🏷</emoji> Самый дорогой\n   лимитированный: {} <emoji document_id=5924870095925942277>⭐️</emoji>\n"
            "• <emoji document_id=5890925363067886150>✨</emoji> NFT подарков: {}\n"
            "• <emoji document_id=5879905000972358125>👥</emoji> Общая стоимость подарков\n   за звезды: {} <emoji document_id=5924870095925942277>⭐️</emoji>\n"
            "• <emoji document_id=5891105528356018797>💎</emoji> Общая стоимость NFT: {}"
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

        if not all_gifts:
            name = await self._get_display_name(message.client, peer)
            await message.edit(self.strings("no_gifts").format(name))
            return

        stats = await self._calculate_stats(all_gifts, is_self)
        name = await self._get_display_name(message.client, peer)

        total_gifts = stats['обычные'] + stats['лимитированные'] + stats['nft']

        # киньте мне мишку на пропитание, пж
        nft_value_str = await self._get_nft_total_values(message.client, all_gifts)

        if is_self:
            stats_text = self.strings("stats_self").format(
                name,
                total_gifts,
                stats['обычные'],
                stats['лимитированные'],
                stats['max_обычный'] or "нету",
                stats['max_лимитированный'] or "нету",
                stats['nft'],
                stats['скрытые'],
                stats['открытые'],
                stats['total_stars'],
                nft_value_str
            )

            stars_summary = await self._fetch_stars_summary(message.client)
            if stars_summary:
                balance_display = (
                    stars_summary['balance'] if isinstance(stars_summary['balance'], str)
                    else self._format_stars(stars_summary['balance'])
                )
                stats_text += self.strings("stars_stats_footer").format(
                    stars_summary['total_tx'],
                    self._format_stars(stars_summary['sent']),
                    self._format_stars(stars_summary['received']),
                    balance_display,
                )
                if stars_summary['total_tx'] == 0 and stars_summary.get('debug'):
                    stats_text += f"\n\n<code>[debug] {stars_summary['debug']}</code>"

            await message.edit(stats_text)
        else:
            await message.edit(self.strings("stats_other").format(
                name,
                total_gifts,
                stats['обычные'],
                stats['лимитированные'],
                stats['max_обычный'] or "нету",
                stats['max_лимитированный'] or "нету",
                stats['nft'],
                stats['total_stars'],
                nft_value_str
            ))

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
        """Форматирует звёзды: целые — без десятичных, дробные — обрезая нули."""
        if value == int(value):
            return str(int(value))
        return f"{value:.9f}".rstrip('0').rstrip('.')

    async def _fetch_stars_summary(self, client, limit=100, max_pages=1000):
        """Собирает сводку по звёздным транзакциям своего аккаунта:
        общее число транзакций, сколько отправлено/получено звёзд, текущий баланс.

        max_pages — это просто защита от бесконечного цикла (1000 страниц * 100 =
        100k транзакций с большим запасом), а не реальный лимит на твою историю.

        Если что-то пошло не так — кладём причину в 'debug', чтобы её было видно
        прямо в ответе бота (а не только в консоли, которую не всегда видно)."""
        debug = None

        try:
            balance_result = await client(GetStarsStatusRequest(peer=InputPeerSelf()))
            balance = self._stars_amount_to_float(getattr(balance_result, 'balance', None))
        except Exception as e:
            balance = "н/д"
            debug = f"GetStarsStatus упал: {type(e).__name__}: {e}"

        sent = 0.0
        received = 0.0
        total_tx = 0
        offset = ""
        first_page_raw = None

        for page_num in range(max_pages):
            try:
                result = await client(GetStarsTransactionsRequest(
                    peer=InputPeerSelf(),
                    offset=offset,
                    limit=limit,
                ))
            except Exception as e:
                debug = f"GetStarsTransactions упал: {type(e).__name__}: {e}"
                break

            if page_num == 0:
                try:
                    raw_history = result.history if hasattr(result, 'history') else None
                    if raw_history:
                        first_tx_dump = str(raw_history[0].to_dict())[:500]
                        first_page_raw = (
                            f"has 'history' attr, len={len(raw_history)}, "
                            f"first_tx={first_tx_dump}"
                        )
                    else:
                        attrs = [a for a in dir(result) if not a.startswith('_')]
                        first_page_raw = (
                            f"result has NO 'history' or it's empty/None. "
                            f"type={type(result).__name__}, attrs={attrs}"
                        )
                except Exception as e:
                    first_page_raw = f"debug dump упал: {type(e).__name__}: {e}"

            transactions = getattr(result, 'history', None) or []
            total_tx += len(transactions)

            for tx in transactions:
                value = self._stars_amount_to_float(getattr(tx, 'amount', None))
                if value < 0:
                    sent += abs(value)
                else:
                    received += value

            offset = getattr(result, 'next_offset', '') or ''
            if not offset or len(transactions) < limit:
                break

            await asyncio.sleep(0.3)  # небольшая пауза, чтобы не словить FloodWait на большой истории

        if total_tx == 0 and debug is None:
            debug = f"Запрос прошёл без ошибок, но вернул 0 транзакций. Сырой ответ: {first_page_raw}"

        return {
            'total_tx': total_tx,
            'sent': sent,
            'received': received,
            'balance': balance,
            'debug': debug,
        }

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
        """Суммирует стоимость всех NFT в рублях по данным API."""
        nft_slugs = []
        for saved_gift in gifts:
            gift = getattr(saved_gift, 'gift', saved_gift)
            if hasattr(gift, 'gift_address') or hasattr(gift, 'owner_address'):
                slug = getattr(gift, 'slug', None)
                if slug:
                    nft_slugs.append(slug)

        if not nft_slugs:
            return "нету NFT"

        async def fetch_value(slug):
            try:
                result = await client(GetUniqueStarGiftValueInfoRequest(slug=slug))
                # я заебался
                value = getattr(result, 'value', 0)
                return value
            except Exception as e:
                print(f"Error fetching price for {slug}: {e}")
                return 0

        tasks = [fetch_value(slug) for slug in nft_slugs]
        results = await asyncio.gather(*tasks)

        total_kopecks = sum(results)
        if total_kopecks == 0:
            return "нету данных о ценах"

        total_rubles = total_kopecks / 100.0
        return f"{int(total_rubles)} RUB"

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
            return getattr(entity, 'first_name', None) or getattr(entity, 'username', str(entity.id))
        except:
            return "пользователь"
