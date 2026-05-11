# ◇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◇
# meta developer: @dubai_ip
# meta banner: https://raw.githubusercontent.com/crypto-killu/modules-by-killu/main/Module-banners/MazeGame.jpg
# scope: Heroku, Hikka
# version: 4.5
# author: Killu
# Description: Модуль для игры одному или с собеседником.
# ◇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◇

import asyncio
import logging
import random
from typing import Optional, Tuple

from telethon import TelegramClient
from telethon.tl.types import Message

from .. import loader
from ..inline.types import InlineCall

logger = logging.getLogger(__name__)

class Maze:
    def __init__(self, rows: int, cols: int, wall_fire_percent: int = 15):
        self.rows = rows if rows % 2 == 1 else rows + 1
        self.cols = cols if cols % 2 == 1 else cols + 1
        self.wall_fire_percent = wall_fire_percent
        self.grid = [['⬛️' for _ in range(self.cols)] for _ in range(self.rows)]

    def _in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.rows and 0 <= c < self.cols

    def _carve_passages_from(self, r: int, c: int):
        directions = [(0, 2), (2, 0), (0, -2), (-2, 0)]
        random.shuffle(directions)
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            if self._in_bounds(nr, nc) and self.grid[nr][nc] == '⬛️':
                self.grid[r + dr // 2][c + dc // 2] = '⬜️'
                self.grid[nr][nc] = '⬜️'
                self._carve_passages_from(nr, nc)

    def _count_passage_neighbors(self, r: int, c: int) -> int:
        """Считает количество соседних проходов (через стену) для клетки (r,c)"""
        count = 0
        for dr, dc in [(0, 2), (2, 0), (0, -2), (-2, 0)]:
            nr, nc = r + dr, c + dc
            if self._in_bounds(nr, nc) and self.grid[nr][nc] == '⬜️':
                count += 1
        return count

    def generate(self) -> Tuple[list, Tuple[int, int]]:
        """Генерирует лабиринт и возвращает (grid, start_pos)"""
        
        start_r = random.randrange(1, self.rows, 2)
        start_c = random.randrange(1, self.cols, 2)
        self.grid[start_r][start_c] = '⬜️'
        self._carve_passages_from(start_r, start_c)

        
        passages = []
        for r in range(1, self.rows, 2):
            for c in range(1, self.cols, 2):
                if self.grid[r][c] == '⬜️':
                    passages.append((r, c))

        
        good_starts = [p for p in passages if self._count_passage_neighbors(p[0], p[1]) >= 2]
        if good_starts:
            start = random.choice(good_starts)
        else:
            start = random.choice(passages)  

        
        finish_candidates = [p for p in passages if p != start]
        if finish_candidates:
            fr, fc = random.choice(finish_candidates)
            self.grid[fr][fc] = '🐸'
        else:
            
            fr, fc = start[0] + 2, start[1]
            if self._in_bounds(fr, fc) and self.grid[fr][fc] == '⬜️':
                self.grid[fr][fc] = '🐸'
            else:
                self.grid[start[0]][start[1] + 2] = '🐸'

        
        walls = []
        for r in range(1, self.rows - 1):
            for c in range(1, self.cols - 1):
                if self.grid[r][c] == '⬛️':
                    walls.append((r, c))
        fire_count = int(len(walls) * self.wall_fire_percent / 100)
        random.shuffle(walls)
        for r, c in walls[:fire_count]:
            self.grid[r][c] = '🔥'

        return self.grid, start

class GameState:
    def __init__(self, maze: list, start: Tuple[int, int],
                 player1_id: int, player2_id: Optional[int] = None):
                     
        self.maze = [row[:] for row in maze]
        self.start = start
        self.finish = self._find_finish()
        self.player1 = {'id': player1_id, 'pos': start, 'symbol': '🏃‍♂️'}
        self.player2 = None
        self.turn = 1
        self.finished = False
        self.steps = 0
        self.show_full_map = False
        self.map_used = False
        self.auto_back_task = None

        
        r, c = start
        self.maze[r][c] = self.player1['symbol']

        if player2_id:
            
            second_pos = self._find_good_spot_for_player2(r, c)
            if second_pos is None:
                
                second_pos = (r, c)
            self.player2 = {'id': player2_id, 'pos': second_pos, 'symbol': '🏃‍♂️‍➡️'}
            r2, c2 = second_pos
            self.maze[r2][c2] = self.player2['symbol']

    def _find_good_spot_for_player2(self, pr: int, pc: int) -> Optional[Tuple[int, int]]:
        """Ищет клетку для второго игрока, чтобы не заблокировать первого.
        """
        
        adjacent = []
        for dr, dc in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            nr, nc = pr + dr, pc + dc
            if 0 <= nr < len(self.maze) and 0 <= nc < len(self.maze[0]) and self.maze[nr][nc] == '⬜️':
                adjacent.append((nr, nc))

        
        if not adjacent:
            return self._find_two_step_away(pr, pc)

        
        for spot in adjacent:
            
            remaining = 0
            for dr, dc in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nr, nc = spot[0] + dr, spot[1] + dc
                if (nr, nc) == (pr, pc):
                    continue  
                if 0 <= nr < len(self.maze) and 0 <= nc < len(self.maze[0]) and self.maze[nr][nc] == '⬜️':
                    remaining += 1
            if remaining >= 1:
                
                return spot

        
        two_step = self._find_two_step_away(pr, pc)
        if two_step:
            return two_step

        
        return adjacent[0] if adjacent else None

    def _find_two_step_away(self, r: int, c: int) -> Optional[Tuple[int, int]]:
        """Ищет свободную клетку через одну от (r,c)"""
        directions = [(0, 2), (2, 0), (0, -2), (-2, 0)]
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            if 0 <= nr < len(self.maze) and 0 <= nc < len(self.maze[0]):
                if self.maze[nr][nc] == '⬜️':
                    return (nr, nc)
        return None

    def _find_finish(self) -> Tuple[int, int]:
        for r, row in enumerate(self.maze):
            for c, cell in enumerate(row):
                if cell == '🐸':
                    return (r, c)
        return (-1, -1)

    def get_player(self, player_num: int) -> dict:
        return self.player1 if player_num == 1 else self.player2

    def other_player(self, player_num: int) -> Optional[dict]:
        return self.player2 if player_num == 1 else self.player1

    def move(self, player_num: int, dr: int, dc: int) -> str:
        if self.finished:
            return 'finished'

        player = self.get_player(player_num)
        if not player:
            return 'no_player'

        r, c = player['pos']
        nr, nc = r + dr, c + dc

        if not (0 <= nr < len(self.maze) and 0 <= nc < len(self.maze[0])):
            return 'blocked'

        cell = self.maze[nr][nc]

        if cell == '⬛️':
            return 'wall'
        if cell == '🔥':
            return 'fire'
        if cell == '🐸':
            return 'win'

        other = self.other_player(player_num)
        if other and (nr, nc) == other['pos']:
            return 'occupied'

        return 'ok'

    def apply_move(self, player_num: int, dr: int, dc: int):
        player = self.get_player(player_num)
        r, c = player['pos']
        nr, nc = r + dr, c + dc
        self.maze[r][c] = '⬜️'
        player['pos'] = (nr, nc)
        self.maze[nr][nc] = player['symbol']
        self.steps += 1

    def get_view(self, player_num: int, view_size: int = 7) -> list:
        """Возвращает видимую область размером ровно view_size x view_size,
        заполняя недостающие края стенами.
        """
        player = self.get_player(player_num)
        if not player:
            
            return [['⬛️' for _ in range(view_size)] for _ in range(view_size)]

        pr, pc = player['pos']
        rows = len(self.maze)
        cols = len(self.maze[0])
        half = view_size // 2

        if view_size % 2 == 1:  
            top = pr - half
            bottom = pr + half
            left = pc - half
            right = pc + half
        else:  
            top = pr - half + 1
            bottom = pr + half
            left = pc - half + 1
            right = pc + half

        
        view = []
        for r in range(top, bottom + 1):
            row = []
            for c in range(left, right + 1):
                if 0 <= r < rows and 0 <= c < cols:
                    row.append(self.maze[r][c])
                else:
                    row.append('⬛️')  
            view.append(row)

        return view

    def to_display(self, player_num: int, view_size: int = 7) -> str:
        if self.show_full_map:
            lines = [''.join(row) for row in self.maze]
        else:
            view = self.get_view(player_num, view_size)
            lines = [''.join(row) for row in view]
        return '\n'.join(lines)

@loader.tds
class MazeModMod(loader.Module):
    """Игра в лабиринт с огненными ловушками и двумя игроками + скроллинг карты (карта 1 раз)"""

    strings = {
        "name": "MazeGame",
        "cfg_width": "Размер лабиринта (нечётное число, по умолчанию 21)",
        "cfg_wall_fire": "Процент внутренних стен, заменяемых на огонь (0-100, по умолчанию 15)",
        "cfg_view_single": "Размер видимой области для одного игрока (по умолчанию 6, может быть чётным или нечётным)",
        "cfg_view_multi": "Размер видимой области для двух игроков (по умолчанию 7, может быть чётным или нечётным)",
        "start_single": "🐸 <b>Спаси лягушку Пепе!</b>\nТы играешь за {player}\nХоди кнопками и не наступай на 🔥\nШагов: {steps}",
        "start_multi": "🐸 <b>Спасите лягушку Пепе вместе!</b>\n{player1} и {player2} начинают рядом\nХод игрока {turn}\nШагов: {steps}",
        "turn": "▶️ Сейчас ходит {player}\nШагов: {steps}",
        "move_ok": "✅ Ход сделан",
        "move_blocked": "🚫 Туда нельзя",
        "move_wall": "🧱 Стена",
        "move_occupied": "🤝 Там уже другой игрок",
        "fire_loss_single": "🔥 {player} наступил на огонь! Ты проиграл!",
        "fire_loss_multi": "🔥 {player} наступил на огонь! Все проиграли!",
        "win_single": "🐸 Ты спас лягушку! Победа!\nШагов: {steps}",
        "win_multi": "🐸 {player} спас лягушку! Победа!\nВсего шагов: {steps}",
        "not_your_turn": "⏳ Сейчас не твой ход",
        "map_button": "🗺 Карта (1 раз)",
        "map_hint": "🗺 Показана вся карта (на 3 секунды)",
        "error": "❗️ Ошибка игры",
        "doc": "\n🏃‍♂️ – игрок 1\n🏃‍♂️‍➡️ – игрок 2\n⬜️ – дорога\n⬛️ – стена\n🔥 – огонь (проигрыш)\n🐸 – финиш (победа)",
    }

    strings_ru = {
        "start_single": "🐸 <b>Спаси лягушку Пепе!</b>\nТы играешь за {player}\nХоди кнопками и не наступай на 🔥\nШагов: {steps}",
        "start_multi": "🐸 <b>Спасите лягушку Пепе вместе!</b>\n{player1} и {player2} начинают рядом\nХод игрока {turn}\nШагов: {steps}",
        "turn": "▶️ Сейчас ходит {player}\nШагов: {steps}",
        "move_ok": "✅ Ход сделан",
        "move_blocked": "🚫 Туда нельзя",
        "move_wall": "🧱 Стена",
        "move_occupied": "🤝 Там уже другой игрок",
        "fire_loss_single": "🔥 {player} наступил на огонь! Ты проиграл!",
        "fire_loss_multi": "🔥 {player} наступил на огонь! Все проиграли!",
        "win_single": "🐸 Ты спас лягушку! Победа!\nШагов: {steps}",
        "win_multi": "🐸 {player} спас лягушку! Победа!\nВсего шагов: {steps}",
        "not_your_turn": "⏳ Сейчас не твой ход",
        "map_button": "🗺 Карта (1 раз)",
        "map_hint": "🗺 Показана вся карта (на 3 секунды)",
        "error": "❗️ Ошибка игры",
        "doc": "\n🏃‍♂️ – игрок 1\n🏃‍♂️‍➡️ – игрок 2\n⬜️ – дорога\n⬛️ – стена\n🔥 – огонь (проигрыш)\n🐸 – финиш (победа)",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            "maze_width", 21, lambda: self.strings("cfg_width"),
            "wall_fire_percent", 15, lambda: self.strings("cfg_wall_fire"),
            "view_size_single", 6, lambda: self.strings("cfg_view_single"),
            "view_size_multi", 7, lambda: self.strings("cfg_view_multi")
        )
        self.active_games = {}

    async def client_ready(self, client: TelegramClient, db):
        self._db = db
        self._client = client

    def _get_view_size(self, game: GameState) -> int:
        """Возвращает размер обзора в зависимости от количества игроков"""
        if game.player2:
            return self.config["view_size_multi"]
        else:
            return self.config["view_size_single"]

    @loader.unrestricted
    @loader.ratelimit
    async def mazecmd(self, message: Message):
        """короче, лабиринт, ок? это типо игра, ну не типо, а игра. играй, ок?"""
        player1_id = message.sender_id
        player2_id = None
        reply = await message.get_reply_message()
        if reply and reply.sender_id != player1_id:
            player2_id = reply.sender_id

        size = self.config["maze_width"]
        fire_pct = self.config["wall_fire_percent"]
        maze_gen = Maze(size, size, wall_fire_percent=fire_pct)
        maze_grid, start = maze_gen.generate()

        game = GameState(maze_grid, start, player1_id, player2_id)
        chat_id = message.chat_id
        self.active_games[chat_id] = game

        if player2_id:
            p1_mention = f"<a href=\"tg://user?id={player1_id}\">Игрок 1</a>"
            p2_mention = f"<a href=\"tg://user?id={player2_id}\">Игрок 2</a>"
            turn_mention = p1_mention if game.turn == 1 else p2_mention
            text = self.strings("start_multi").format(
                player1=p1_mention, player2=p2_mention, turn=turn_mention, steps=game.steps
            )
        else:
            text = self.strings("start_single").format(player="🏃‍♂️", steps=game.steps)

        text += self.strings("doc") + "\n\n" + game.to_display(1, self._get_view_size(game))

        keyboard = self._build_keyboard(chat_id, game)

        await message.delete()
        await self.inline.form(
            text=text,
            message=message,
            always_allow=[player1_id, player2_id] if player2_id else [player1_id],
            reply_markup=keyboard,
            manual_security=True,
        )

    def _build_keyboard(self, game_id: int, game: GameState = None):
        """Строит клавиатуру. Если игра не передана, пытается получить из active_games (для колбэков)"""
        if game is None:
            game = self.active_games.get(game_id)
        if not game:
            
            base = [
                [{"text": "🔼", "callback": self._move_cb, "args": (game_id, -1, 0)}],
                [
                    {"text": "◀️", "callback": self._move_cb, "args": (game_id, 0, -1)},
                    {"text": "▶️", "callback": self._move_cb, "args": (game_id, 0, 1)},
                ],
                [{"text": "🔽", "callback": self._move_cb, "args": (game_id, 1, 0)}],
            ]
            return base

        
        if not game.map_used:
            return [
                [{"text": "🔼", "callback": self._move_cb, "args": (game_id, -1, 0)}],
                [
                    {"text": "◀️", "callback": self._move_cb, "args": (game_id, 0, -1)},
                    {"text": "▶️", "callback": self._move_cb, "args": (game_id, 0, 1)},
                ],
                [{"text": "🔽", "callback": self._move_cb, "args": (game_id, 1, 0)}],
                [{"text": self.strings("map_button"), "callback": self._map_cb, "args": (game_id,)}],
            ]
        else:
            
            return [
                [{"text": "🔼", "callback": self._move_cb, "args": (game_id, -1, 0)}],
                [
                    {"text": "◀️", "callback": self._move_cb, "args": (game_id, 0, -1)},
                    {"text": "▶️", "callback": self._move_cb, "args": (game_id, 0, 1)},
                ],
                [{"text": "🔽", "callback": self._move_cb, "args": (game_id, 1, 0)}],
            ]

    async def _map_cb(self, call: InlineCall, game_id: int):
        game = self.active_games.get(game_id)
        if not game or game.finished:
            await call.answer("Игра не активна", show_alert=True)
            return

        
        if game.map_used:
            await call.answer("Карту можно показать только один раз", show_alert=True)
            return

        game.map_used = True
        game.show_full_map = True
        user_id = call.from_user.id
        player_num = 1 if game.player1['id'] == user_id else (2 if game.player2 and game.player2['id'] == user_id else None)
        if not player_num:
            await call.answer("Ты не участвуешь", show_alert=True)
            return

        
        view_size = self._get_view_size(game)
        display = game.to_display(player_num, view_size)
        text = f"{self.strings('map_hint')}\n\n" + display

        
        await call.answer()
        await call.edit(
            text=text,
            reply_markup=[[{"text": "◀️ Назад", "callback": self._back_from_map_cb, "args": (game_id,)}]]
        )

        
        if game.auto_back_task and not game.auto_back_task.done():
            game.auto_back_task.cancel()

        
        async def auto_back():
            await asyncio.sleep(3)
            
            game = self.active_games.get(game_id)
            if not game or game.finished:
                return
            if game.show_full_map:  
                await self._back_from_map(call, game_id, auto=True)

        game.auto_back_task = asyncio.create_task(auto_back())

    async def _back_from_map_cb(self, call: InlineCall, game_id: int):
        
        game = self.active_games.get(game_id)
        if not game or game.finished:
            await call.answer("Игра не активна", show_alert=True)
            return

        
        if game.auto_back_task and not game.auto_back_task.done():
            game.auto_back_task.cancel()
            game.auto_back_task = None

        await self._back_from_map(call, game_id, auto=False)

    async def _back_from_map(self, call: InlineCall, game_id: int, auto: bool = False):
        """Общая логика возврата из карты"""
        game = self.active_games.get(game_id)
        if not game or game.finished:
            return

        game.show_full_map = False
        user_id = call.from_user.id if not auto else None
        
        if auto:
            player_num = game.turn
        else:
            player_num = 1 if game.player1['id'] == user_id else (2 if game.player2 and game.player2['id'] == user_id else None)

        if not player_num:
            player_num = 1

        view_size = self._get_view_size(game)
        display = game.to_display(player_num, view_size)

        if game.player2:
            turn_id = game.player1['id'] if game.turn == 1 else game.player2['id']
            turn_mention = f"<a href=\"tg://user?id={turn_id}\">Игрок {game.turn}</a>"
            header = self.strings("turn").format(player=turn_mention, steps=game.steps)
        else:
            header = self.strings("move_ok") + f"\nШагов: {game.steps}"

        text = header + "\n" + self.strings("doc") + "\n\n" + display
        
        keyboard = self._build_keyboard(game_id, game)
        await call.edit(text=text, reply_markup=keyboard)

    async def _move_cb(self, call: InlineCall, game_id: int, dr: int, dc: int):
        try:
            game = self.active_games.get(game_id)
            if not game:
                await call.answer("Игра не найдена", show_alert=True)
                return
            if game.finished:
                await call.answer("Игра уже закончена", show_alert=True)
                return

            user_id = call.from_user.id
            player_num = None
            if game.player1['id'] == user_id:
                player_num = 1
            elif game.player2 and game.player2['id'] == user_id:
                player_num = 2
            else:
                await call.answer("Ты не участвуешь в этой игре", show_alert=True)
                return

            if player_num != game.turn:
                await call.answer(self.strings("not_your_turn"), show_alert=True)
                return

            result = game.move(player_num, dr, dc)
            current_symbol = game.get_player(player_num)['symbol']

            if result == 'ok':
                game.apply_move(player_num, dr, dc)
                if game.player2:
                    game.turn = 2 if game.turn == 1 else 1
                status = self.strings("move_ok")
            elif result == 'fire':
                game.finished = True
                self.active_games.pop(game_id, None)
                
                if game.player2:
                    loss_text = self.strings("fire_loss_multi").format(player=current_symbol, steps=game.steps)
                else:
                    loss_text = self.strings("fire_loss_single").format(player=current_symbol, steps=game.steps)
                await call.answer(loss_text, show_alert=True)
                await call.edit(text=loss_text + "\n\n" + game.to_display(player_num, self._get_view_size(game)))
                return
            elif result == 'win':
                game.finished = True
                self.active_games.pop(game_id, None)
                if game.player2:
                    win_text = self.strings("win_multi").format(player=current_symbol, steps=game.steps)
                else:
                    win_text = self.strings("win_single").format(player=current_symbol, steps=game.steps)
                await call.answer(win_text, show_alert=True)
                await call.edit(text=win_text + "\n\n" + game.to_display(player_num, self._get_view_size(game)))
                return
            elif result == 'wall':
                status = self.strings("move_wall")
            elif result == 'occupied':
                status = self.strings("move_occupied")
            else:
                status = self.strings("move_blocked")

            if game.player2:
                turn_id = game.player1['id'] if game.turn == 1 else game.player2['id']
                turn_mention = f"<a href=\"tg://user?id={turn_id}\">Игрок {game.turn}</a>"
                header = self.strings("turn").format(player=turn_mention, steps=game.steps)
            else:
                header = self.strings("move_ok") + f"\nШагов: {game.steps}"

            text = header + "\n" + status + "\n\n" + game.to_display(player_num, self._get_view_size(game))
            await call.edit(text=text, reply_markup=self._build_keyboard(game_id, game))

        except Exception as e:
            logger.exception("Ошибка в _move_cb")
            await call.answer("Произошла внутренняя ошибка", show_alert=True)
