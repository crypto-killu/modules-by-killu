# ◇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◇
# meta developer: @dubai_ip
# meta banner: https://raw.githubusercontent.com/crypto-killu/modules-by-killu/main/Module-banners/MazeGame.jpg
# scope: Heroku, Hikka
# version: 5.0
# author: Killu
# Description: Модуль для игры одному или с собеседником.
# ◇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◇

import asyncio
import logging
import random
import math
from typing import Optional, Tuple, List

from telethon import TelegramClient
from telethon.tl.types import Message
from telethon.tl.functions.users import GetFullUserRequest

from .. import loader
from ..inline.types import InlineCall

logger = logging.getLogger(__name__)

class Maze:
    def __init__(self, rows: int, cols: int, wall_fire_percent: int = 15):
        self.rows = rows if rows % 2 == 1 else rows + 1
        self.cols = cols if cols % 2 == 1 else cols + 1
        self.wall_fire_percent = wall_fire_percent
        self.grid = [['<tg-emoji emoji-id=5231249189907761291>⬛️</tg-emoji>' for _ in range(self.cols)] for _ in range(self.rows)]

    def _in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.rows and 0 <= c < self.cols

    def _carve_passages_from(self, r: int, c: int):
        directions = [(0, 2), (2, 0), (0, -2), (-2, 0)]
        random.shuffle(directions)
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            if self._in_bounds(nr, nc) and self.grid[nr][nc] == '<tg-emoji emoji-id=5231249189907761291>⬛️</tg-emoji>':
                self.grid[r + dr // 2][c + dc // 2] = '<tg-emoji emoji-id=5231229729410943257>⬜️</tg-emoji>'
                self.grid[nr][nc] = '<tg-emoji emoji-id=5231229729410943257>⬜️</tg-emoji>'
                self._carve_passages_from(nr, nc)

    def _count_passage_neighbors(self, r: int, c: int) -> int:
        count = 0
        for dr, dc in [(0, 2), (2, 0), (0, -2), (-2, 0)]:
            nr, nc = r + dr, c + dc
            if self._in_bounds(nr, nc) and self.grid[nr][nc] == '<tg-emoji emoji-id=5231229729410943257>⬜️</tg-emoji>':
                count += 1
        return count

    def _find_finish_candidates(self, start_pos: Tuple[int, int], player2_pos: Optional[Tuple[int, int]] = None, min_distance: int = 7) -> List[Tuple[int, int]]:
        passages = []
        for r in range(1, self.rows, 2):
            for c in range(1, self.cols, 2):
                if self.grid[r][c] == '<tg-emoji emoji-id=5231229729410943257>⬜️</tg-emoji>':
                    dist_to_start = abs(r - start_pos[0]) + abs(c - start_pos[1])
                    if dist_to_start < min_distance:
                        continue
                    
                    if player2_pos:
                        dist_to_player2 = abs(r - player2_pos[0]) + abs(c - player2_pos[1])
                        if dist_to_player2 < min_distance:
                            continue
                    
                    passages.append((r, c))
        return passages

    def _find_nearby_passage(self, pos: Tuple[int, int], min_distance: int = 1, max_distance: int = 2) -> Optional[Tuple[int, int]]:
        """Находит проход рядом с заданной позицией"""
        r, c = pos
        candidates = []
        
        # Ищем в радиусе max_distance клеток
        for dr in range(-max_distance, max_distance + 1):
            for dc in range(-max_distance, max_distance + 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                dist = abs(dr) + abs(dc)
                if dist < min_distance or dist > max_distance:
                    continue
                if self._in_bounds(nr, nc) and self.grid[nr][nc] == '<tg-emoji emoji-id=5231229729410943257>⬜️</tg-emoji>':
                    candidates.append((dist, nr, nc))
        
        if candidates:
            # Сортируем по расстоянию и выбираем случайный из ближайших
            candidates.sort()
            min_dist = candidates[0][0]
            closest = [(r, c) for d, r, c in candidates if d == min_dist]
            return random.choice(closest)
        return None

    def generate(self, player2_start: Optional[Tuple[int, int]] = None) -> Tuple[list, Tuple[int, int], Optional[Tuple[int, int]]]:
        start_r = random.randrange(1, self.rows, 2)
        start_c = random.randrange(1, self.cols, 2)
        self.grid[start_r][start_c] = '<tg-emoji emoji-id=5231229729410943257>⬜️</tg-emoji>'
        self._carve_passages_from(start_r, start_c)

        passages = []
        for r in range(1, self.rows, 2):
            for c in range(1, self.cols, 2):
                if self.grid[r][c] == '<tg-emoji emoji-id=5231229729410943257>⬜️</tg-emoji>':
                    passages.append((r, c))

        good_starts = [p for p in passages if self._count_passage_neighbors(p[0], p[1]) >= 2]
        if good_starts:
            start = random.choice(good_starts)
        else:
            start = random.choice(passages)

        # Ищем позицию для второго игрока РЯДОМ с первым
        player2_pos = None
        if player2_start:
            # Ищем проход рядом с первым игроком (расстояние 1-2 клетки)
            nearby = self._find_nearby_passage(start, min_distance=1, max_distance=2)
            if nearby:
                player2_pos = nearby
                logger.info(f"Второй игрок спавнится рядом: {player2_pos}")
            else:
                # Если не нашли рядом, ищем на расстоянии 3-4
                nearby = self._find_nearby_passage(start, min_distance=3, max_distance=4)
                if nearby:
                    player2_pos = nearby
                    logger.info(f"Второй игрок спавнится на расстоянии 3-4: {player2_pos}")
                else:
                    # Самый крайний случай - просто случайная клетка
                    candidates = [p for p in passages if p != start]
                    if candidates:
                        player2_pos = random.choice(candidates)
                        logger.info(f"Второй игрок спавнится случайно: {player2_pos}")

        finish_candidates = self._find_finish_candidates(start, player2_pos, min_distance=7)
        
        if finish_candidates:
            fr, fc = random.choice(finish_candidates)
        else:
            finish_candidates = self._find_finish_candidates(start, min_distance=7)
            if finish_candidates:
                fr, fc = random.choice(finish_candidates)
            else:
                candidate = None
                max_dist = 0
                for r in range(1, self.rows, 2):
                    for c in range(1, self.cols, 2):
                        if self.grid[r][c] == '<tg-emoji emoji-id=5231229729410943257>⬜️</tg-emoji>' and (r, c) != start:
                            if player2_pos and (r, c) == player2_pos:
                                continue
                            dist = abs(r - start[0]) + abs(c - start[1])
                            if dist > max_dist:
                                max_dist = dist
                                candidate = (r, c)
                if candidate:
                    fr, fc = candidate
                else:
                    fr, fc = start[0] + 2, start[1]
                    if not self._in_bounds(fr, fc) or self.grid[fr][fc] != '<tg-emoji emoji-id=5231229729410943257>⬜️</tg-emoji>':
                        fr, fc = start[0], start[1] + 2

        self.grid[fr][fc] = '<tg-emoji emoji-id=5424605383463316658>🐸</tg-emoji>'

        walls = []
        for r in range(1, self.rows - 1):
            for c in range(1, self.cols - 1):
                if self.grid[r][c] == '<tg-emoji emoji-id=5231249189907761291>⬛️</tg-emoji>':
                    walls.append((r, c))
        fire_count = int(len(walls) * self.wall_fire_percent / 100)
        random.shuffle(walls)
        for r, c in walls[:fire_count]:
            self.grid[r][c] = '<tg-emoji emoji-id=5231269182980525488>🔥</tg-emoji>'

        return self.grid, start, player2_pos

class GameState:
    def __init__(self, maze: list, start: Tuple[int, int],
                 player1_id: int, player2_id: Optional[int] = None, player2_pos: Optional[Tuple[int, int]] = None):
                     
        self.maze = [row[:] for row in maze]
        self.start = start
        self.finish = self._find_finish()
        self.player1 = {'id': player1_id, 'pos': start, 'symbol': '<tg-emoji emoji-id=5424900241558121200>👾</tg-emoji>'}
        self.player2 = None
        self.turn = 1
        self.finished = False
        self.steps = 0
        self.auto_back_task = None

        r, c = start
        self.maze[r][c] = self.player1['symbol']

        if player2_id and player2_pos:
            r2, c2 = player2_pos
            self.player2 = {'id': player2_id, 'pos': player2_pos, 'symbol': '<tg-emoji emoji-id=5424662253125278534>🫥</tg-emoji>'}
            if self.maze[r2][c2] == '<tg-emoji emoji-id=5231229729410943257>⬜️</tg-emoji>':
                self.maze[r2][c2] = self.player2['symbol']
            else:
                # Если клетка занята, ищем свободную рядом
                for dr, dc in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                    nr, nc = r2 + dr, c2 + dc
                    if (0 <= nr < len(self.maze) and 0 <= nc < len(self.maze[0]) and 
                        self.maze[nr][nc] == '<tg-emoji emoji-id=5231229729410943257>⬜️</tg-emoji>'):
                        self.player2['pos'] = (nr, nc)
                        self.maze[nr][nc] = self.player2['symbol']
                        break

    def _find_finish(self) -> Tuple[int, int]:
        for r, row in enumerate(self.maze):
            for c, cell in enumerate(row):
                if cell == '<tg-emoji emoji-id=5424605383463316658>🐸</tg-emoji>':
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

        if cell == '<tg-emoji emoji-id=5231249189907761291>⬛️</tg-emoji>':
            return 'wall'
        if cell == '<tg-emoji emoji-id=5231269182980525488>🔥</tg-emoji>':
            return 'fire'
        if cell == '<tg-emoji emoji-id=5424605383463316658>🐸</tg-emoji>':
            return 'win'

        other = self.other_player(player_num)
        if other and (nr, nc) == other['pos']:
            return 'occupied'

        return 'ok'

    def apply_move(self, player_num: int, dr: int, dc: int):
        player = self.get_player(player_num)
        r, c = player['pos']
        nr, nc = r + dr, c + dc
        self.maze[r][c] = '<tg-emoji emoji-id=5231229729410943257>⬜️</tg-emoji>'
        player['pos'] = (nr, nc)
        self.maze[nr][nc] = player['symbol']
        self.steps += 1

    def get_view(self, player_num: int, view_size: int = 7) -> list:
        player = self.get_player(player_num)
        if not player:
            return [['<tg-emoji emoji-id=5231249189907761291>⬛️</tg-emoji>' for _ in range(view_size)] for _ in range(view_size)]

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
                    row.append('<tg-emoji emoji-id=5231249189907761291>⬛️</tg-emoji>')
            view.append(row)

        return view

    def to_display(self, player_num: int, view_size: int = 7) -> str:
        view = self.get_view(player_num, view_size)
        lines = [''.join(row) for row in view]
        return '\n'.join(lines)

@loader.tds
class MazeModMod(loader.Module):
    """Игра в лабиринт с огненными ловушками и двумя игроками"""

    strings = {
        "name": "MazeGame",
        "cfg_width": "Размер лабиринта (нечётное число, по умолчанию 21)",
        "cfg_wall_fire": "Процент внутренних стен, заменяемых на огонь (0-100, по умолчанию 15)",
        "cfg_view_single": "Размер видимой области для одного игрока (по умолчанию 6, может быть чётным или нечётным)",
        "cfg_view_multi": "Размер видимой области для двух игроков (по умолчанию 7, может быть чётным или нечётным)",
        "start_single": "<tg-emoji emoji-id=5886486492892630446>🐸</tg-emoji> <b>Спаси лягушку Пепе!</b>\nТы играешь за <tg-emoji emoji-id=5424900241558121200>👾</tg-emoji>\nХоди кнопками и не наступай на <tg-emoji emoji-id=5231269182980525488>🔥</tg-emoji>\n\n<b>Шагов:</b> <u>{steps}</u>",
        "start_multi": "<tg-emoji emoji-id=5886486492892630446>🐸</tg-emoji> <b>Спасите лягушку Пепе вместе!</b>\n{player1} и {player2} начинают рядом\nХод игрока {turn}\nШагов: {steps}",
        "turn": "Сейчас ходит {player}\n\n<b>Шагов:</b> <u>{steps}</u>",
        "move_ok": "<b>Ход сделан</b>",
        "move_blocked": "<b>Туда нельзя ходить!</b>",
        "move_wall": "<b>Не можешь походить, стена!</b> '<tg-emoji emoji-id=5231249189907761291>⬛️</tg-emoji>'",
        "move_occupied": "<b>Там уже другой игрок!</b>",
        "fire_loss_single": "{player} наступил на огонь... ты проиграл...",
        "fire_loss_multi": "{player} наступил на огонь... вы проиграли...",
        "win_alert": "🐸 Победа!",
        "win_single": "<tg-emoji emoji-id=5886486492892630446>🐸</tg-emoji> Ты спас лягушку! Победа!\n<b>Шагов:</b> <u>{steps}</u>",
        "win_multi": "<tg-emoji emoji-id=5886486492892630446>🐸</tg-emoji> {player} спас лягушку! Победа!\n<b>Всего шагов:</b> <u>{steps}</u>",
        "not_your_turn": "<b>Сейчас не твой ход!</b>",
        "error": "Ошибка игры",
        "doc": "\n<tg-emoji emoji-id=5424900241558121200>👾</tg-emoji> – игрок 1\n<tg-emoji emoji-id=5424662253125278534>🫥</tg-emoji> – игрок 2\n\n<tg-emoji emoji-id=5231269182980525488>🔥</tg-emoji> – огонь (проигрыш)\n<tg-emoji emoji-id=5424605383463316658>🐸</tg-emoji> – финиш (победа)",
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

    async def _get_user_name(self, user_id: int) -> str:
        try:
            user = await self._client.get_entity(user_id)
            if user.first_name:
                return user.first_name.split()[0]
            elif user.username:
                return f"@{user.username}"
            else:
                return f"Пользователь {user_id}"
        except:
            return f"Пользователь {user_id}"

    def _get_view_size(self, game: GameState) -> int:
        if game.player2:
            return self.config["view_size_multi"]
        else:
            return self.config["view_size_single"]

    @loader.unrestricted
    @loader.ratelimit
    async def mazecmd(self, message: Message):
        """- команда .maze игра одному, команда .maze + реплай игра с собеседником."""
        player1_id = message.sender_id
        player2_id = None
        
        reply = await message.get_reply_message()
        if reply and reply.sender_id != player1_id:
            player2_id = reply.sender_id
            logger.info(f"Найден второй игрок: {player2_id}")

        size = self.config["maze_width"]
        fire_pct = self.config["wall_fire_percent"]
        maze_gen = Maze(size, size, wall_fire_percent=fire_pct)
        
        maze_grid, start, player2_pos = maze_gen.generate(player2_start=None)
        
        if player2_id and not player2_pos:
            logger.warning("Позиция для второго игрока не найдена, генерируем заново")
            maze_grid, start, player2_pos = maze_gen.generate(player2_start=(start[0], start[1]))

        game = GameState(maze_grid, start, player1_id, player2_id, player2_pos)
        chat_id = message.chat_id
        self.active_games[chat_id] = game
        
        logger.info(f"Создана игра для {player1_id} и {player2_id} в чате {chat_id}")

        if player2_id and game.player2:
            p1_name = await self._get_user_name(player1_id)
            p2_name = await self._get_user_name(player2_id)
            
            p1_mention = f"<a href=\"tg://user?id={player1_id}\">{p1_name}</a>"
            p2_mention = f"<a href=\"tg://user?id={player2_id}\">{p2_name}</a>"
            
            turn_mention = p1_mention if game.turn == 1 else p2_mention
            text = self.strings("start_multi").format(
                player1=p1_mention, player2=p2_mention, turn=turn_mention, steps=game.steps
            )
            
            allowed_users = [player1_id, player2_id]
        else:
            text = self.strings("start_single").format(steps=game.steps)
            allowed_users = [player1_id]

        text += self.strings("doc") + "\n\n" + game.to_display(1, self._get_view_size(game))

        await message.delete()
        await self.inline.form(
            text=text,
            message=message,
            always_allow=allowed_users,
            reply_markup=self._build_keyboard(chat_id, game),
            manual_security=True,
        )

    def _build_keyboard(self, game_id: int, game: GameState = None):
        if game is None:
            game = self.active_games.get(game_id)
        if not game:
            return [
                [{"text": "🔼", "callback": self._move_cb, "args": (game_id, -1, 0)}],
                [
                    {"text": "◀️", "callback": self._move_cb, "args": (game_id, 0, -1)},
                    {"text": "▶️", "callback": self._move_cb, "args": (game_id, 0, 1)},
                ],
                [{"text": "🔽", "callback": self._move_cb, "args": (game_id, 1, 0)}],
            ]

        return [
            [{"text": "🔼", "callback": self._move_cb, "args": (game_id, -1, 0)}],
            [
                {"text": "◀️", "callback": self._move_cb, "args": (game_id, 0, -1)},
                {"text": "▶️", "callback": self._move_cb, "args": (game_id, 0, 1)},
            ],
            [{"text": "🔽", "callback": self._move_cb, "args": (game_id, 1, 0)}],
        ]

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
            
            if player_num is None:
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
                    player_name = await self._get_user_name(user_id)
                    loss_text = self.strings("fire_loss_multi").format(player=player_name, steps=game.steps)
                else:
                    loss_text = self.strings("fire_loss_single").format(player=current_symbol, steps=game.steps)
                await call.answer(loss_text, show_alert=True)
                await call.edit(text=loss_text + "\n\n" + game.to_display(player_num, self._get_view_size(game)))
                return
            elif result == 'win':
                game.finished = True
                self.active_games.pop(game_id, None)
                await call.answer(self.strings("win_alert"), show_alert=True)
                if game.player2:
                    player_name = await self._get_user_name(user_id)
                    win_text = self.strings("win_multi").format(player=player_name, steps=game.steps)
                else:
                    win_text = self.strings("win_single").format(player=current_symbol, steps=game.steps)
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
                turn_name = await self._get_user_name(turn_id)
                turn_mention = f"<a href=\"tg://user?id={turn_id}\">{turn_name}</a>"
                header = self.strings("turn").format(player=turn_mention, steps=game.steps)
            else:
                header = f"{status}\n\n<b>Шагов:</b> <u>{game.steps}</u>"

            text = header + "\n\n" + game.to_display(player_num, self._get_view_size(game))
            await call.edit(text=text, reply_markup=self._build_keyboard(game_id, game))

        except Exception as e:
            logger.exception("Ошибка в _move_cb")
            await call.answer("Произошла внутренняя ошибка", show_alert=True)