# ◇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◇
# meta developer: @dubai_ip
# meta banner: https://raw.githubusercontent.com/crypto-killu/modules-by-killu/main/Module-banners/File-creator.jpg
# scope: Heroku, Hikka
# version: 1.3
# author: Killu
# Description: Модуль для создания различных файлов.
# ◇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◇

from .. import loader, utils
from telethon.tl.types import Message
import io

@loader.tds
class CFileMod(loader.Module):
    """Создаёт файл из любого кода (даже очень длинного)"""

    strings = {
        "name": "File-creator",
        "start": "<b>Отправь код</b> (можно в несколько сообщений).\nКогда закончишь — напиши <code>.done</code>",
        "no_args": "<emoji document_id=5980869107891838347>❌</emoji> Укажи формат и название: .cfile py myscript",
        "done": "<b>Готово!</b> Создаю файл...",
        "error": "<emoji document_id=5980869107891838347>❌</emoji> Ошибка: {}"
    }

    def __init__(self):
        self.current_code = {}
        self.current_format = {}
        self.current_name = {}

    @loader.command()
    async def cfile(self, message: Message):
        """<формат> [название] — начать создание файла"""
        args = utils.get_args_raw(message).strip().split(maxsplit=1)

        if not args:
            return await utils.answer(message, self.strings("no_args"))

        file_format = args[0].strip().lower()
        if not file_format.startswith('.'):
            file_format = '.' + file_format

        filename = args[1].strip() if len(args) > 1 else "code"

        user_id = message.sender_id

        self.current_code[user_id] = []
        self.current_format[user_id] = file_format
        self.current_name[user_id] = filename

        await utils.answer(message, self.strings("start"))

    @loader.command()
    async def done(self, message: Message):
        """Завершить сбор кода и создать файл"""
        user_id = message.sender_id

        if user_id not in self.current_code:
            return await utils.answer(message, "<b>Ты не начинал создание файла!</b>")

        await utils.answer(message, self.strings("done"))

        full_code = "\n".join(self.current_code[user_id])

        if not full_code.strip():
            self._cleanup(user_id)
            return await utils.answer(message, "<b>Код пустой!</b>")

        file_format = self.current_format.get(user_id, ".txt")
        filename = self.current_name.get(user_id, "code") + file_format

        file_obj = io.BytesIO(full_code.encode('utf-8'))
        file_obj.name = filename

        try:
            await message.client.send_file(
                message.chat_id,
                file_obj,
                caption=f"<emoji document_id=5193177581888755275>💻</emoji> <code>{filename}</code>",
                reply_to=message.reply_to_msg_id or message.id
            )
            await message.delete()
        except Exception as e:
            await utils.answer(message, self.strings("error").format(str(e)))

        self._cleanup(user_id)

    def _cleanup(self, user_id):
        for d in (self.current_code, self.current_format, self.current_name):
            if user_id in d:
                del d[user_id]

    @loader.watcher()
    async def collect_code(self, event):
        """Собирает код"""
        try:
            user_id = event.sender_id
        except AttributeError:
            return

        if user_id not in self.current_code:
            return

        if event.raw_text.strip().lower() == ".done":
            return

        if event.media:
            return

        text = event.raw_text
        if not text or not text.strip():
            return

        self.current_code[user_id].append(text)

        try:
            await event.reply("<b>Добавлено</b>")
        except:
            pass

    async def on_unload(self):
        self.current_code.clear()
        self.current_format.clear()
        self.current_name.clear()
