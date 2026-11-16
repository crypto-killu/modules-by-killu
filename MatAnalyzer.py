# ◇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◇
# meta developer: @dubai_ip
# meta banner: https://raw.githubusercontent.com/crypto-killu/modules-by-killu/main/Module-banners/MatAnalyzer.jpg
# scope: Heroku, Hikka
# version: 2.2
# author: Killu
# Description: Анализирует маты в чате за последние 10к сообщений.
# ◇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◇

import logging
import re
from collections import Counter

from telethon.tl.types import Message

from .. import loader, utils

logger = logging.getLogger(__name__)

# Корни матов: слово считается матом, если начинается с одного из них
MAT_ROOTS = (
    'ахувается', 'ахувши', 'ахуев', 'ахуеем', 'ахуеет', 'ахуеешь', 'ахуел', 'ахуен', 'ахуеть',
    'ахуею', 'бля', 'выебал', 'выебанный', 'выебать', 'выебон', 'выебу', 'гандон', 'доеб', 'доёб',
    'долбаеб', 'долбаёб', 'долбоеб', 'долбоёб', 'еба', 'ёбаная', 'ёбанная', 'ёбанное', 'ёбанные',
    'ёбанный', 'ёбаное', 'ёбаные', 'ёбаный', 'ебём', 'ебёт', 'ебёшь', 'ебись', 'ебитесь', 'ебля',
    'ёбля', 'ёбнулся', 'ёбнуть', 'ебу', 'заебавший', 'заебал', 'заебать', 'заебу', 'наёб', 'наебал',
    'наебать', 'наебу', 'нехуевенький', 'нехуёвенький', 'нехуево', 'нехуёво', 'нехуевый',
    'нехуёвый', 'нехуя', 'нихуевато', 'нихуеватый', 'нихуевая', 'нихуевенький', 'нихуёвенький',
    'нихуево', 'нихуёво', 'нихуевую', 'нихуевые', 'нихуевый', 'нихуёвый', 'нихуевым', 'нихуя',
    'объебал', 'объебать', 'объебу', 'отъебал', 'отъебать', 'отъебу', 'переебал', 'переебать',
    'переебу', 'пизда', 'пизде', 'пиздёнка', 'пиздёныш', 'пиздо', 'пизду', 'пизды', 'пиздюк',
    'пиздюли', 'пиздюля', 'пиздюрить', 'пиздюха', 'пиздючка', 'пиздятина', 'подъебал', 'подъебать',
    'подъебу', 'поебал', 'поебать', 'поебу', 'похуе', 'похуи', 'похуй', 'похую', 'похуя', 'приеб',
    'приёб', 'проеб', 'проёб', 'разъеб', 'разъёб', 'сука', 'суке', 'суки', 'сукой', 'сукою', 'суку',
    'сучар', 'сучата', 'сучёнок', 'сучий', 'сучище', 'сучка', 'уебал', 'уебан', 'уебать',
    'уебический', 'уебище', 'уёбище', 'уёбка', 'уебковский', 'уёбок', 'уебский', 'уебу', 'хер',
    'хуё', 'хуевенький', 'хуево', 'хуевый', 'хуеглот', 'хуегрыз', 'хуежор', 'хуежуй', 'хуем',
    'хуеплет', 'хуесос', 'хуец', 'хуи', 'хуй', 'хую', 'хуя', 'шлюха', 'шлюхе', 'шлюхи', 'шлюхой',
    'шлюхою', 'шлюху'
)
MAT_RE = re.compile(r"\b(?:" + "|".join(map(re.escape, MAT_ROOTS)) + r")\w*")


@loader.tds
class MatAnalyzerMod(loader.Module):
    """Анализатор матов в чате"""

    strings = {
        "name": "MatAnalyzer",
        "analyzing": "<tg-emoji emoji-id=5258274739041883702>🔍</tg-emoji> Анализирую маты...",
        "mats": "<tg-emoji emoji-id=5373123633415723713>🤬</tg-emoji> <b>Статистика матов в чате за последние 10к сообщений:</b>\n\n"
               "<b>Всего матов:</b> <code>{total}</code>\n"
               "<b>Ваши маты:</b> <code>{my_mats}</code> ({my_percent}%)\n"
               "<b>Уникальных матов:</b> <code>{unique}</code>\n\n"
               "<b>Топ-10 матов:</b>\n{top_words}\n"
               "<b>Топ-матюкальщики:</b>\n{top_users}",
        "no_mats": "<tg-emoji emoji-id=5348437144945856263>😎</tg-emoji> В этом чате чисто! Матов не найдено.",
        "error": "❌ Ошибка анализа: <code>{}</code>",
    }

    async def matscmd(self, message: Message):
        """— статистика матов в чате"""
        msg = await utils.answer(message, self.strings["analyzing"])
        client = message.client

        try:
            all_mats = Counter()
            user_mats = Counter()
            my_mats = 0

            async for m in client.iter_messages(message.chat_id, limit=10000):
                found = MAT_RE.findall((m.message or "").lower())
                if not found:
                    continue
                all_mats.update(found)
                if m.sender_id:
                    user_mats[m.sender_id] += len(found)
                    if m.sender_id == message.sender_id:
                        my_mats += len(found)

            total = sum(all_mats.values())
            if not total:
                return await utils.answer(msg, self.strings["no_mats"])

            top_words = "".join(
                f"{i}. {word}: <code>{count}</code>\n"
                for i, (word, count) in enumerate(all_mats.most_common(10), 1)
            )
            top_users = ""
            for i, (user_id, count) in enumerate(user_mats.most_common(10), 1):
                top_users += f"{i}. {await self._name(client, user_id)}: <code>{count}</code>\n"

            await utils.answer(msg, self.strings["mats"].format(
                total=total,
                my_mats=my_mats,
                my_percent=round(my_mats / total * 100, 2),
                unique=len(all_mats),
                top_words=top_words,
                top_users=top_users,
            ))
        except Exception as e:
            logger.exception("mats failed")
            await utils.answer(msg, self.strings["error"].format(utils.escape_html(f"{type(e).__name__}: {e}")))

    @staticmethod
    async def _name(client, user_id):
        try:
            user = await client.get_entity(user_id)
        except Exception:
            return f"ID: {user_id}"
        if getattr(user, "username", None):
            return f"@{user.username}"
        name = " ".join(filter(None, [getattr(user, "first_name", None), getattr(user, "last_name", None)]))
        return utils.escape_html(name or getattr(user, "title", None) or f"ID: {user_id}")
