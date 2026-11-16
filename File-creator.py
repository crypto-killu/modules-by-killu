# ◇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◇
# meta developer: @dubai_ip
# meta banner: https://raw.githubusercontent.com/crypto-killu/modules-by-killu/main/Module-banners/File-creator.jpg
# scope: Heroku, Hikka
# version: 1.4
# author: Killu
# Description: Модуль для создания различных файлов.
# ◇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◇

from .. import loader, utils
from telethon.tl.types import Message
import io

@loader.tds
class CFileMod(loader.Module):
    """Создаёт файл из любого кода"""

    strings = {
        "name": "File-creator",
        "start": "<b>Отправь код</b> (можно в несколько сообщений).\nКогда закончишь — напиши <code>{prefix}done</code>",
        "no_args": "<emoji document_id=5980869107891838347>❌</emoji> Укажи формат и название: .cfile py myscript",
        "done": "<b>Готово!</b> Создаю файл...",
        "error": "<emoji document_id=5980869107891838347>❌</emoji> Ошибка: {}"
    }

    def __init__(self):
        # chat_id → {"code": [...], "name": "файл.py"}; код собирается только в том чате, где начали
        self.sessions = {}

    @loader.command()
    async def cfile(self, message: Message):
        """<формат> [название] — начать создание файла"""
        args = utils.get_args_raw(message).strip().split(maxsplit=1)

        if not args:
            return await utils.answer(message, self.strings("no_args"))

        ext = args[0].strip().lower()
        if not ext.startswith('.'):
            ext = '.' + ext
        name = args[1].strip() if len(args) > 1 else "code"

        self.sessions[message.chat_id] = {"code": [], "name": name + ext}
        await utils.answer(message, self.strings("start").format(prefix=self.get_prefix()))

    @loader.command()
    async def done(self, message: Message):
        """Завершить сбор кода и создать файл"""
        session = self.sessions.pop(message.chat_id, None)
        if session is None:
            return await utils.answer(message, "<b>Ты не начинал создание файла!</b>")

        full_code = "\n".join(session["code"])
        if not full_code.strip():
            return await utils.answer(message, "<b>Код пустой!</b>")

        await utils.answer(message, self.strings("done"))

        file_obj = io.BytesIO(full_code.encode('utf-8'))
        file_obj.name = session["name"]

        try:
            await message.client.send_file(
                message.chat_id,
                file_obj,
                caption=f"<emoji document_id=5193177581888755275>💻</emoji> <code>{utils.escape_html(session['name'])}</code>",
                reply_to=message.reply_to_msg_id or message.id
            )
            await message.delete()
        except Exception as e:
            await utils.answer(message, self.strings("error").format(utils.escape_html(str(e))))

    @loader.watcher(out=True, only_messages=True)
    async def collect_code(self, event):
        """Собирает код"""
        session = self.sessions.get(event.chat_id)
        if session is None or event.media:
            return

        text = event.raw_text or ""
        if not text.strip() or text.startswith(self.get_prefix()):
            return  # команды юзербота (.done и любые другие) в файл не попадают

        session["code"].append(text)
        try:
            await event.reply("<b>Добавлено</b>")
        except Exception:
            pass

    async def on_unload(self):
        self.sessions.clear()
