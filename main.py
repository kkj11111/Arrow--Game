# -*- coding: utf-8 -*-
"""一箭又一箭 —— Pygame 图形界面（v2.0）。

游戏状态机：
    start   -> 开始界面（含随机挑战入口）
    playing -> 游戏界面（点击箭头）
    won     -> 通关界面（得分 / 星级 / 用时，可进入下一关）
    lost    -> 失败界面（可重新开始本关）

附加功能：
    - 得分 / 计时 / 三星评价
    - 提示（高亮一个当前可飞的箭头）
    - 撤销上一步
    - 程序合成音效（无外部素材）
    - 本地存档最高分（save.json）
    - 随机生成可通关关卡
    - AI 自动求解演示
"""

import array
import json
import math
import os
import sys

import pygame

from game_logic import Direction, GameSession
from levels import LEVELS, generate_random_level, solve

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

SCREEN_WIDTH, SCREEN_HEIGHT = 800, 700
FPS = 60
TOP_BAR_HEIGHT = 104          # 游戏界面顶部信息栏高度

# 颜色
COLOR_BG = (246, 243, 232)
COLOR_PANEL = (235, 230, 214)
COLOR_GRID_LINE = (196, 190, 172)
COLOR_CELL = (255, 252, 242)
COLOR_CELL_HOVER = (255, 244, 205)
COLOR_ARROW = (52, 84, 148)
COLOR_ARROW_HOVER = (36, 62, 116)
COLOR_ARROW_HIT = (204, 60, 48)
COLOR_TEXT = (60, 56, 48)
COLOR_TEXT_LIGHT = (255, 255, 255)
COLOR_BUTTON = (98, 126, 172)
COLOR_BUTTON_HOVER = (122, 150, 196)
COLOR_RED = (204, 60, 48)
COLOR_GOLD = (200, 156, 56)
COLOR_HINT = (230, 170, 40)

# 动画参数
FLY_STEP = 16
SHAKE_PHASE = 8
SHAKE_TIMES = 3
SHAKE_AMPLITUDE = 6
AUTO_STEP_FRAMES = 30         # 自动求解：每 0.5 秒点击一步

SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "save.json")


def get_font(size: int) -> pygame.font.Font:
    """获取中文字体（Windows 优先微软雅黑，找不到则退回默认字体）。"""
    return pygame.font.SysFont("microsoftyahei,simhei,dengxian,arial", size)


# ---------------------------------------------------------------------------
# 存档（本地最高分 / 星级）
# ---------------------------------------------------------------------------


def load_save() -> dict:
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"best": {}, "stars": {}}


def save_save(data: dict) -> None:
    try:
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 程序合成音效（正弦波，无外部素材）
# ---------------------------------------------------------------------------


def _make_tone(freq_from: float, freq_to: float, duration: float,
               volume: float = 0.3) -> "pygame.mixer.Sound":
    """生成一段频率渐变、音量衰减的正弦波音效。"""
    rate = 44100
    n = int(rate * duration)
    buf = array.array("h")
    for i in range(n):
        t = i / rate
        f = freq_from + (freq_to - freq_from) * (i / n)
        env = 1.0 - i / n
        buf.append(int(32767 * volume * env * math.sin(2 * math.pi * f * t)))
    return pygame.mixer.Sound(buffer=buf.tobytes())


def _make_win_sound() -> "pygame.mixer.Sound":
    """通关音效：上行三连音。"""
    rate = 44100
    buf = array.array("h")
    for freq, dur in ((523, 0.12), (659, 0.12), (784, 0.22)):
        n = int(rate * dur)
        for i in range(n):
            t = i / rate
            env = 1.0 - i / n
            buf.append(int(32767 * 0.28 * env * math.sin(2 * math.pi * freq * t)))
    return pygame.mixer.Sound(buffer=buf.tobytes())


# ---------------------------------------------------------------------------
# 绘制：用几何图形画箭头（头部 + 箭杆 + 尾翼）
# ---------------------------------------------------------------------------


def draw_arrow(surface, cx: float, cy: float, size: float,
               direction: Direction, color) -> None:
    """以 (cx, cy) 为中心绘制一个 size 大小的箭头。

    造型：头部三角形 + 贯穿的箭杆 + 尾翼两条斜线，四个方向分别计算坐标。
    """
    s = size
    shaft_w = max(2, int(s * 0.14))
    wing_w = max(2, int(s * 0.10))

    if direction == Direction.RIGHT:
        tip = (cx + 0.50 * s, cy)
        base = ((cx + 0.10 * s, cy - 0.30 * s), (cx + 0.10 * s, cy + 0.30 * s))
        shaft = ((cx + 0.10 * s, cy), (cx - 0.48 * s, cy))
        wings = [
            ((cx - 0.48 * s, cy - 0.10 * s), (cx - 0.64 * s, cy - 0.26 * s)),
            ((cx - 0.48 * s, cy + 0.10 * s), (cx - 0.64 * s, cy + 0.26 * s)),
        ]
    elif direction == Direction.LEFT:
        tip = (cx - 0.50 * s, cy)
        base = ((cx - 0.10 * s, cy - 0.30 * s), (cx - 0.10 * s, cy + 0.30 * s))
        shaft = ((cx - 0.10 * s, cy), (cx + 0.48 * s, cy))
        wings = [
            ((cx + 0.48 * s, cy - 0.10 * s), (cx + 0.64 * s, cy - 0.26 * s)),
            ((cx + 0.48 * s, cy + 0.10 * s), (cx + 0.64 * s, cy + 0.26 * s)),
        ]
    elif direction == Direction.UP:
        tip = (cx, cy - 0.50 * s)
        base = ((cx - 0.30 * s, cy - 0.10 * s), (cx + 0.30 * s, cy - 0.10 * s))
        shaft = ((cx, cy - 0.10 * s), (cx, cy + 0.48 * s))
        wings = [
            ((cx - 0.10 * s, cy + 0.48 * s), (cx - 0.26 * s, cy + 0.64 * s)),
            ((cx + 0.10 * s, cy + 0.48 * s), (cx + 0.26 * s, cy + 0.64 * s)),
        ]
    else:  # DOWN
        tip = (cx, cy + 0.50 * s)
        base = ((cx - 0.30 * s, cy + 0.10 * s), (cx + 0.30 * s, cy + 0.10 * s))
        shaft = ((cx, cy + 0.10 * s), (cx, cy - 0.48 * s))
        wings = [
            ((cx - 0.10 * s, cy - 0.48 * s), (cx - 0.26 * s, cy - 0.64 * s)),
            ((cx + 0.10 * s, cy - 0.48 * s), (cx + 0.26 * s, cy - 0.64 * s)),
        ]

    pygame.draw.polygon(surface, color, [tip, base[0], base[1]])
    pygame.draw.line(surface, color, shaft[0], shaft[1], shaft_w)
    for w in wings:
        pygame.draw.line(surface, color, w[0], w[1], wing_w)


# ---------------------------------------------------------------------------
# 按钮
# ---------------------------------------------------------------------------


class Button:
    def __init__(self, rect, text, font, bg=COLOR_BUTTON, fg=COLOR_TEXT_LIGHT):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.font = font
        self.bg = bg
        self.fg = fg

    def draw(self, surface):
        hover = self.rect.collidepoint(pygame.mouse.get_pos())
        color = COLOR_BUTTON_HOVER if hover else self.bg
        pygame.draw.rect(surface, color, self.rect, border_radius=10)
        pygame.draw.rect(surface, COLOR_TEXT, self.rect, 2, border_radius=10)
        label = self.font.render(self.text, True, self.fg)
        surface.blit(label, label.get_rect(center=self.rect.center))

    def clicked(self, pos) -> bool:
        return self.rect.collidepoint(pos)


# ---------------------------------------------------------------------------
# 动画
# ---------------------------------------------------------------------------


class FlyAnimation:
    """箭头飞出动画：沿其方向移动，直到移出窗口。"""

    def __init__(self, arrow, origin):
        self.arrow = arrow
        self.x, self.y = origin
        self.dead = False

    def update(self):
        dr, dc = self.arrow.direction.value
        self.x += dc * FLY_STEP
        self.y += dr * FLY_STEP
        margin = 240
        if (self.x < -margin or self.x > SCREEN_WIDTH + margin
                or self.y < -margin or self.y > SCREEN_HEIGHT + margin):
            self.dead = True

    def draw(self, surface, size):
        draw_arrow(surface, self.x, self.y, size, self.arrow.direction, COLOR_ARROW)


class ShakeAnimation:
    """碰撞反馈：箭头在格子里左右（或上下）晃动并变红。"""

    def __init__(self, arrow, origin):
        self.arrow = arrow
        self.x0, self.y0 = origin
        self.frame = 0
        self.total = SHAKE_PHASE * SHAKE_TIMES * 2
        self.dead = False

    def update(self):
        self.frame += 1
        if self.frame >= self.total:
            self.dead = True

    def offset(self):
        phase = self.frame // SHAKE_PHASE
        sign = 1 if phase % 2 == 0 else -1
        if self.arrow.direction in (Direction.LEFT, Direction.RIGHT):
            return sign * SHAKE_AMPLITUDE, 0
        return 0, sign * SHAKE_AMPLITUDE

    def draw(self, surface, size):
        ox, oy = self.offset()
        draw_arrow(surface, self.x0 + ox, self.y0 + oy, size,
                   self.arrow.direction, COLOR_ARROW_HIT)


# ---------------------------------------------------------------------------
# 游戏主体
# ---------------------------------------------------------------------------


class Game:
    def __init__(self):
        pygame.mixer.pre_init(44100, -16, 1, 512)
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("一箭又一箭")
        self.clock = pygame.time.Clock()

        self.font_title = get_font(56)
        self.font_big = get_font(44)
        self.font_mid = get_font(26)
        self.font_small = get_font(20)
        self.font_tiny = get_font(17)

        # 合成音效（无声卡环境自动静音）
        self.sounds = {}
        try:
            if pygame.mixer.get_init() is not None:
                self.sounds = {
                    "fly": _make_tone(480, 920, 0.16, 0.22),
                    "blocked": _make_tone(200, 110, 0.18, 0.30),
                    "win": _make_win_sound(),
                    "lose": _make_tone(330, 90, 0.50, 0.25),
                }
        except Exception:
            self.sounds = {}

        # 会话状态
        self.state = "start"          # start / playing / won / lost
        self.level_index = 0
        self.is_random = False        # 是否为随机挑战关卡
        self.session: GameSession | None = None
        self.fly_animations = []
        self.shake_animations = []

        # 提示与自动求解
        self.hint_arrow = None
        self.hint_timer = 0
        self.auto_solving = False
        self.auto_solution = []
        self.auto_idx = 0
        self.auto_timer = 0

        # 按钮（预创建，矩形位置固定）
        self.btn_start = Button((SCREEN_WIDTH // 2 - 110, 420, 220, 56),
                                "开始游戏", self.font_mid)
        self.btn_random = Button((SCREEN_WIDTH // 2 - 110, 486, 220, 44),
                                 "随机挑战", self.font_small)
        self.btn_hint = Button((398, 16, 74, 40), "提示", self.font_tiny)
        self.btn_undo = Button((478, 16, 74, 40), "撤销", self.font_tiny)
        self.btn_auto = Button((558, 16, 100, 40), "自动求解", self.font_tiny)
        self.btn_restart = Button((664, 16, 112, 40), "重新开始", self.font_tiny)
        self.btn_next = Button((SCREEN_WIDTH // 2 - 100, 470, 200, 56),
                               "下一关", self.font_mid)
        self.btn_retry = Button((SCREEN_WIDTH // 2 - 100, 440, 200, 56),
                                "重新开始", self.font_mid)

        # 棋盘布局（进入关卡时计算）
        self.cell = 88
        self.board_x = 0
        self.board_y = 0

        self.running = True

    # ---------------- 音效 ----------------

    def play(self, name: str) -> None:
        s = self.sounds.get(name)
        if s is not None:
            s.play()

    # ---------------- 关卡流程 ----------------

    def _start_session(self, level: dict, index: int, is_random: bool) -> None:
        self.level_index = index
        self.is_random = is_random
        self.session = GameSession(level)
        self.fly_animations.clear()
        self.shake_animations.clear()
        self.hint_arrow = None
        self.hint_timer = 0
        self.auto_solving = False
        self.auto_solution = []
        self.auto_idx = 0
        self.auto_timer = 0
        self._layout_board()
        self.state = "playing"

    def start_level(self, index: int) -> None:
        self._start_session(LEVELS[index], index, False)

    def start_random_level(self) -> None:
        level = generate_random_level()
        if level is None:
            return  # 生成失败（概率极低），保持当前状态
        self._start_session(level, -1, True)

    def restart_level(self) -> None:
        if self.is_random:
            self.start_random_level()
        else:
            self.start_level(self.level_index)

    def next_level(self) -> None:
        if self.is_random or self.level_index + 1 >= len(LEVELS):
            self.state = "start"
            return
        self.start_level(self.level_index + 1)

    def _layout_board(self) -> None:
        rows = self.session.board.rows
        cols = self.session.board.cols
        area_top = TOP_BAR_HEIGHT + 12
        area_height = SCREEN_HEIGHT - area_top - 12
        self.cell = min(88, area_height // rows, (SCREEN_WIDTH - 64) // cols)
        board_w = cols * self.cell
        board_h = rows * self.cell
        self.board_x = (SCREEN_WIDTH - board_w) // 2
        self.board_y = area_top + (area_height - board_h) // 2

    def cell_center(self, row: int, col: int):
        return (self.board_x + col * self.cell + self.cell // 2,
                self.board_y + row * self.cell + self.cell // 2)

    def cell_at(self, pos):
        x, y = pos
        col = (x - self.board_x) // self.cell
        row = (y - self.board_y) // self.cell
        if 0 <= row < self.session.board.rows and 0 <= col < self.session.board.cols:
            return int(row), int(col)
        return None

    def shake_of(self, arrow):
        for a in self.shake_animations:
            if a.arrow is arrow:
                return a
        return None

    # ---------------- 事件 ----------------

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.on_click(event.pos)

    def on_click(self, pos) -> None:
        if self.state == "start":
            if self.btn_start.clicked(pos):
                self.start_level(0)
            elif self.btn_random.clicked(pos):
                self.start_random_level()
        elif self.state == "playing":
            if self.btn_restart.clicked(pos):
                self.restart_level()
            elif self.btn_hint.clicked(pos):
                self.do_hint()
            elif self.btn_undo.clicked(pos):
                self.do_undo()
            elif self.btn_auto.clicked(pos):
                self.do_auto_solve()
            else:
                self._click_board(pos)
        elif self.state == "won":
            if self.btn_next.clicked(pos):
                self.next_level()
        elif self.state == "lost":
            if self.btn_retry.clicked(pos):
                self.restart_level()

    def _click_board(self, pos) -> None:
        if self.auto_solving:
            return  # 自动求解演示期间锁定手动点击
        cell = self.cell_at(pos)
        if cell is None:
            return
        self._click_cell(*cell)

    def _click_cell(self, row: int, col: int) -> None:
        if self.session is None or self.session.finished:
            return
        arrow = self.session.board.arrow_at(row, col)
        if arrow is None or self.shake_of(arrow) is not None:
            return  # 空格或正在晃动反馈中的箭头
        result = self.session.click(row, col)
        if result == "fly":
            self.fly_animations.append(FlyAnimation(arrow, self.cell_center(row, col)))
            self.play("fly")
        elif result == "blocked":
            self.shake_animations.append(ShakeAnimation(arrow, self.cell_center(row, col)))
            self.play("blocked")

    # ---------------- 附加功能：提示 / 撤销 / 自动求解 ----------------

    def do_hint(self) -> None:
        if self.session is None or self.session.finished or self.auto_solving:
            return
        movable = [
            a for row in self.session.board.grid for a in row
            if a is not None and self.session.board.is_path_clear(a)
        ]
        if movable:
            self.hint_arrow = movable[0]
            self.hint_timer = 120  # 高亮 2 秒

    def do_undo(self) -> None:
        if self.auto_solving or self.session is None:
            return
        item = self.session.undo()
        if item is None:
            return
        if item[0] == "fly":
            _, (r, c, _d) = item
            # 若该箭头仍在飞出动画中，一并移除，避免“幽灵箭头”
            self.fly_animations = [
                a for a in self.fly_animations
                if not (a.arrow.row == r and a.arrow.col == c)
            ]
        self.hint_arrow = None
        self.hint_timer = 0
        if self.state in ("won", "lost"):
            self.state = "playing"

    def do_auto_solve(self) -> None:
        if self.session is None:
            return
        if self.auto_solving:  # 再次点击 = 停止演示
            self.auto_solving = False
            return
        solution = solve(self.session.initial_grid)
        if not solution:
            return
        self.auto_solution = solution
        self.auto_idx = 0
        self.auto_timer = 0
        self.auto_solving = True

    def _save_progress(self) -> None:
        """通关后保存本关最高分与最高星级（随机挑战不计入）。"""
        if self.is_random or self.session is None:
            return
        data = load_save()
        key = str(self.level_index + 1)
        sc, st = self.session.score(), self.session.stars()
        if sc > data["best"].get(key, 0):
            data["best"][key] = sc
        if st > data["stars"].get(key, 0):
            data["stars"][key] = st
        save_save(data)

    # ---------------- 每帧更新 ----------------

    def update(self) -> None:
        for a in self.fly_animations:
            a.update()
        self.fly_animations = [a for a in self.fly_animations if not a.dead]

        for a in self.shake_animations:
            a.update()
        shaking = [a for a in self.shake_animations if not a.dead]
        self.shake_animations = shaking

        # 提示高亮计时
        if self.hint_timer > 0:
            self.hint_timer -= 1
            if self.hint_timer <= 0:
                self.hint_arrow = None

        # 自动求解演示推进
        if (self.state == "playing" and self.auto_solving
                and self.session is not None and not self.session.finished):
            self.auto_timer += 1
            if self.auto_timer >= AUTO_STEP_FRAMES:
                self.auto_timer = 0
                if self.auto_idx < len(self.auto_solution):
                    r, c = self.auto_solution[self.auto_idx]
                    self.auto_idx += 1
                    self._click_cell(r, c)
                else:
                    self.auto_solving = False

        if self.state != "playing" or self.session is None:
            return
        # 失误耗尽：等晃动动画播完再进入失败界面
        if self.session.lost and not shaking:
            self.state = "lost"
            self.play("lose")
        # 全部飞出：等飞出动画播完再进入通关界面
        elif self.session.won and not self.fly_animations:
            self.state = "won"
            self.play("win")
            self._save_progress()

    # ---------------- 绘制 ----------------

    def draw(self) -> None:
        self.screen.fill(COLOR_BG)
        if self.state == "start":
            self._draw_start()
        elif self.state == "playing":
            self._draw_playing()
        elif self.state == "won":
            self._draw_result("恭喜通关！", is_won=True)
        elif self.state == "lost":
            self._draw_result("挑战失败！", is_won=False)
        pygame.display.flip()

    def _draw_start(self) -> None:
        title = self.font_title.render("一箭又一箭", True, COLOR_TEXT)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 150)))

        # 装饰箭头
        draw_arrow(self.screen, SCREEN_WIDTH // 2 - 150, 222, 46, Direction.RIGHT, COLOR_ARROW)
        draw_arrow(self.screen, SCREEN_WIDTH // 2 - 96, 222, 46, Direction.UP, COLOR_ARROW)
        draw_arrow(self.screen, SCREEN_WIDTH // 2 + 96, 222, 46, Direction.DOWN, COLOR_ARROW)
        draw_arrow(self.screen, SCREEN_WIDTH // 2 + 150, 222, 46, Direction.LEFT, COLOR_ARROW)

        sub = self.font_mid.render("点击箭头，让它们依次飞出棋盘！", True, COLOR_TEXT)
        self.screen.blit(sub, sub.get_rect(center=(SCREEN_WIDTH // 2, 280)))

        rules = [
            "箭头会沿朝向直线飞向棋盘边缘；",
            "前方有其他箭头阻挡时无法飞出，并消耗一次失误（每关 3 次）；",
            "按正确顺序清空全部箭头即可通关，还有三星评价等你挑战！",
        ]
        y = 330
        for line in rules:
            text = self.font_small.render(line, True, COLOR_TEXT)
            self.screen.blit(text, text.get_rect(center=(SCREEN_WIDTH // 2, y)))
            y += 30

        self.btn_start.draw(self.screen)
        self.btn_random.draw(self.screen)

        # 历史成绩
        data = load_save()
        total_stars = sum(data["stars"].values())
        best = sum(data["best"].values())
        info = self.font_tiny.render(
            f"历史成绩：共 {total_stars} 星 · 最高总分 {best}", True, COLOR_TEXT)
        self.screen.blit(info, info.get_rect(center=(SCREEN_WIDTH // 2, 560)))

    def _draw_playing(self) -> None:
        pygame.draw.rect(self.screen, COLOR_PANEL, (0, 0, SCREEN_WIDTH, TOP_BAR_HEIGHT))
        pygame.draw.line(self.screen, COLOR_GRID_LINE, (0, TOP_BAR_HEIGHT),
                         (SCREEN_WIDTH, TOP_BAR_HEIGHT), 2)

        session = self.session
        name = self.font_mid.render(f"关卡：{session.name}", True, COLOR_TEXT)
        self.screen.blit(name, (24, 14))

        remain = self.font_small.render(f"剩余箭头：{session.remaining}", True, COLOR_TEXT)
        self.screen.blit(remain, (24, 58))
        mist_color = COLOR_RED if session.mistakes >= session.max_mistakes else COLOR_TEXT
        mist = self.font_small.render(
            f"失误：{session.mistakes} / {session.max_mistakes}", True, mist_color)
        self.screen.blit(mist, mist.get_rect(midleft=(170, 66)))
        mm, ss = divmod(session.elapsed, 60)
        timer = self.font_small.render(f"用时：{mm:02d}:{ss:02d}", True, COLOR_TEXT)
        self.screen.blit(timer, timer.get_rect(midleft=(300, 66)))

        # 按钮
        self.btn_hint.draw(self.screen)
        self.btn_undo.draw(self.screen)
        self.btn_auto.text = "停止演示" if self.auto_solving else "自动求解"
        self.btn_auto.draw(self.screen)
        self.btn_restart.draw(self.screen)
        if self.auto_solving:
            # 自动演示期间：提示/撤销置灰
            dim = pygame.Surface((160, TOP_BAR_HEIGHT), pygame.SRCALPHA)
            dim.fill((0, 0, 0, 50))
            self.screen.blit(dim, (398, 0))

        self._draw_board()

    def _draw_board(self) -> None:
        board = self.session.board
        hover = self.cell_at(pygame.mouse.get_pos()) if self.state == "playing" else None

        for r in range(board.rows):
            for c in range(board.cols):
                rect = pygame.Rect(self.board_x + c * self.cell,
                                   self.board_y + r * self.cell,
                                   self.cell, self.cell)
                bg = COLOR_CELL_HOVER if hover == (r, c) else COLOR_CELL
                pygame.draw.rect(self.screen, bg, rect)
                pygame.draw.rect(self.screen, COLOR_GRID_LINE, rect, 1)

                arrow = board.grid[r][c]
                if arrow is None:
                    continue
                shake = self.shake_of(arrow)
                if shake is not None:
                    shake.draw(self.screen, self.cell * 0.62)
                else:
                    color = COLOR_ARROW_HOVER if hover == (r, c) else COLOR_ARROW
                    draw_arrow(self.screen, *self.cell_center(r, c),
                               self.cell * 0.62, arrow.direction, color)

        # 提示高亮：金色光圈（闪烁）
        if self.hint_arrow is not None and self.hint_timer > 0:
            blink = (self.hint_timer // 10) % 2 == 0
            if blink:
                rect = pygame.Rect(self.board_x + self.hint_arrow.col * self.cell,
                                   self.board_y + self.hint_arrow.row * self.cell,
                                   self.cell, self.cell).inflate(-8, -8)
                pygame.draw.rect(self.screen, COLOR_HINT, rect, 4, border_radius=12)

        # 飞出动画（最上层）
        for a in self.fly_animations:
            a.draw(self.screen, self.cell * 0.62)

    def _draw_result(self, headline: str, is_won: bool) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((246, 243, 232, 205))
        self.screen.blit(overlay, (0, 0))

        title = self.font_title.render(headline, True, COLOR_GOLD)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 210)))

        if is_won and self.session is not None:
            stars = self.session.stars()
            star_text = "★" * stars + "☆" * (3 - stars)
            star_img = self.font_big.render(star_text, True, COLOR_GOLD)
            self.screen.blit(star_img, star_img.get_rect(center=(SCREEN_WIDTH // 2, 280)))

            mm, ss = divmod(self.session.elapsed, 60)
            info = self.font_mid.render(
                f"得分：{self.session.score()}　用时：{mm:02d}:{ss:02d}　"
                f"失误：{self.session.mistakes}/{self.session.max_mistakes}",
                True, COLOR_TEXT)
            self.screen.blit(info, info.get_rect(center=(SCREEN_WIDTH // 2, 340)))

            # 历史最佳
            key = str(self.level_index + 1)
            data = load_save()
            best = data["best"].get(key, 0)
            best_line = self.font_small.render(
                f"本关历史最高分：{best}", True, COLOR_TEXT)
            self.screen.blit(best_line, best_line.get_rect(center=(SCREEN_WIDTH // 2, 390)))

            if self.is_random or self.level_index + 1 >= len(LEVELS):
                self.btn_next.text = "返回开始"
            else:
                self.btn_next.text = "下一关"
            self.btn_next.draw(self.screen)
        else:
            sub = self.font_mid.render("失误次数已用完，再来一次吧！", True, COLOR_TEXT)
            self.screen.blit(sub, sub.get_rect(center=(SCREEN_WIDTH // 2, 310)))
            self.btn_retry.draw(self.screen)

    # ---------------- 主循环 ----------------

    def run(self) -> None:
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()
        sys.exit(0)


def main() -> None:
    Game().run()


if __name__ == "__main__":
    main()
