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
COLOR_SKY_TOP = (208, 230, 246)      # 背景渐变：顶部浅蓝
COLOR_SKY_BOTTOM = (246, 243, 232)   # 背景渐变：底部米色
COLOR_PANEL = (255, 255, 255)        # 卡片底色
COLOR_PANEL_BORDER = (198, 210, 220) # 卡片描边
COLOR_SHADOW = (182, 196, 210)       # 卡片阴影
COLOR_GRID_LINE = (212, 219, 228)
COLOR_CELL_A = (255, 255, 255)
COLOR_CELL_B = (238, 244, 250)
COLOR_CELL_HOVER = (255, 246, 214)

# 四方向箭头配色
COLOR_ARROW_UP = (52, 168, 120)      # 绿
COLOR_ARROW_RIGHT = (240, 148, 52)   # 橙
COLOR_ARROW_DOWN = (128, 98, 196)    # 紫
COLOR_ARROW_LEFT = (46, 152, 196)    # 青
COLOR_ARROW_HIT = (222, 74, 62)      # 碰撞红

COLOR_TEXT = (60, 56, 48)
COLOR_TEXT_LIGHT = (255, 255, 255)
COLOR_GOLD = (210, 158, 40)
COLOR_HINT = (240, 180, 48)          # 提示光圈

# 按钮配色
COLOR_BTN_BLUE = (84, 136, 206)
COLOR_BTN_GREEN = (56, 166, 116)
COLOR_BTN_PURPLE = (140, 108, 200)
COLOR_BTN_GOLD = (224, 168, 56)
COLOR_BTN_GRAY = (152, 160, 172)
COLOR_BTN_RED = (222, 92, 78)

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
# 绘制辅助：颜色 / 卡片 / 徽章
# ---------------------------------------------------------------------------


def lighten(color, amount=26):
    """把颜色调亮，用于悬停效果。"""
    return tuple(min(255, c + amount) for c in color)


def arrow_color(direction):
    """每个方向一种颜色，方便玩家一眼区分方向。"""
    return {
        Direction.UP: COLOR_ARROW_UP,
        Direction.RIGHT: COLOR_ARROW_RIGHT,
        Direction.DOWN: COLOR_ARROW_DOWN,
        Direction.LEFT: COLOR_ARROW_LEFT,
    }[direction]


def make_vertical_gradient(top, bottom, width, height):
    """生成一张自上而下渐变的 surface（顶部浅蓝 -> 底部米色）。"""
    surf = pygame.Surface((width, height))
    for y in range(height):
        t = y / max(1, height - 1)
        color = tuple(int(a + (b - a) * t) for a, b in zip(top, bottom))
        pygame.draw.line(surf, color, (0, y), (width, y))
    return surf


def draw_card(surface, rect, radius=14, shadow=True):
    """白色圆角卡片（带浅色阴影与描边）。"""
    r = pygame.Rect(rect)
    if shadow:
        pygame.draw.rect(surface, COLOR_SHADOW, r.move(3, 4), border_radius=radius)
    pygame.draw.rect(surface, COLOR_PANEL, r, border_radius=radius)
    pygame.draw.rect(surface, COLOR_PANEL_BORDER, r, 2, border_radius=radius)


def draw_badge(surface, rect, text, font, bg):
    """彩色圆角信息徽章（剩余箭头 / 失误 / 用时）。"""
    rect = pygame.Rect(rect)
    pygame.draw.rect(surface, bg, rect, border_radius=9)
    img = font.render(text, True, COLOR_TEXT_LIGHT)
    surface.blit(img, img.get_rect(center=rect.center))


# ---------------------------------------------------------------------------
# 绘制：用几何图形画箭头（头部 + 箭杆）
# ---------------------------------------------------------------------------


def draw_arrow(surface, cx: float, cy: float, size: float,
               direction: Direction, color) -> None:
    """以 (cx, cy) 为中心绘制一个 size 大小的箭头。

    造型：头部三角形 + 贯穿的箭杆，四个方向分别计算坐标。
    """
    s = size
    shaft_w = max(2, int(s * 0.14))

    if direction == Direction.RIGHT:
        tip = (cx + 0.50 * s, cy)
        base = ((cx + 0.10 * s, cy - 0.30 * s), (cx + 0.10 * s, cy + 0.30 * s))
        shaft = ((cx + 0.10 * s, cy), (cx - 0.48 * s, cy))
    elif direction == Direction.LEFT:
        tip = (cx - 0.50 * s, cy)
        base = ((cx - 0.10 * s, cy - 0.30 * s), (cx - 0.10 * s, cy + 0.30 * s))
        shaft = ((cx - 0.10 * s, cy), (cx + 0.48 * s, cy))
    elif direction == Direction.UP:
        tip = (cx, cy - 0.50 * s)
        base = ((cx - 0.30 * s, cy - 0.10 * s), (cx + 0.30 * s, cy - 0.10 * s))
        shaft = ((cx, cy - 0.10 * s), (cx, cy + 0.48 * s))
    else:  # DOWN
        tip = (cx, cy + 0.50 * s)
        base = ((cx - 0.30 * s, cy + 0.10 * s), (cx + 0.30 * s, cy + 0.10 * s))
        shaft = ((cx, cy + 0.10 * s), (cx, cy - 0.48 * s))

    pygame.draw.polygon(surface, color, [tip, base[0], base[1]])
    pygame.draw.line(surface, color, shaft[0], shaft[1], shaft_w)


# ---------------------------------------------------------------------------
# 按钮
# ---------------------------------------------------------------------------


class Button:
    def __init__(self, rect, text, font, bg=COLOR_BTN_BLUE, fg=COLOR_TEXT_LIGHT):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.font = font
        self.bg = bg
        self.fg = fg

    def draw(self, surface):
        hover = self.rect.collidepoint(pygame.mouse.get_pos())
        color = lighten(self.bg, 26) if hover else self.bg
        pygame.draw.rect(surface, color, self.rect, border_radius=10)
        pygame.draw.rect(surface, (255, 255, 255), self.rect, 2, border_radius=10)
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
        draw_arrow(surface, self.x, self.y, size, self.arrow.direction,
                   arrow_color(self.arrow.direction))


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
        self.background = make_vertical_gradient(
            COLOR_SKY_TOP, COLOR_SKY_BOTTOM, SCREEN_WIDTH, SCREEN_HEIGHT)

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

        # 按钮（预创建，矩形位置固定，各功能不同颜色）
        self.btn_start = Button((SCREEN_WIDTH // 2 - 110, 420, 220, 56),
                                "开始游戏", self.font_mid, bg=COLOR_BTN_BLUE)
        self.btn_random = Button((SCREEN_WIDTH // 2 - 110, 486, 220, 44),
                                 "随机挑战", self.font_small, bg=COLOR_BTN_PURPLE)
        self.btn_hint = Button((470, 20, 66, 38), "提示", self.font_tiny,
                               bg=COLOR_BTN_GOLD)
        self.btn_undo = Button((542, 20, 66, 38), "撤销", self.font_tiny,
                               bg=COLOR_BTN_GRAY)
        self.btn_auto = Button((614, 20, 92, 38), "自动求解", self.font_tiny,
                               bg=COLOR_BTN_GREEN)
        self.btn_restart = Button((712, 20, 80, 38), "重新开始", self.font_tiny,
                                  bg=COLOR_BTN_RED)
        self.btn_next = Button((SCREEN_WIDTH // 2 - 100, 440, 200, 56),
                               "下一关", self.font_mid, bg=COLOR_BTN_BLUE)
        self.btn_retry = Button((SCREEN_WIDTH // 2 - 100, 410, 200, 56),
                                "重新开始", self.font_mid, bg=COLOR_BTN_RED)

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
        self.screen.blit(self.background, (0, 0))
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
        # 标题（阴影立体感）
        title = self.font_title.render("一箭又一箭", True, COLOR_SHADOW)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2 + 3, 153)))
        title = self.font_title.render("一箭又一箭", True, (58, 66, 92))
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 150)))

        # 装饰箭头（四个方向四种颜色）
        decor = [(SCREEN_WIDTH // 2 - 150, Direction.RIGHT),
                 (SCREEN_WIDTH // 2 - 96, Direction.UP),
                 (SCREEN_WIDTH // 2 + 96, Direction.DOWN),
                 (SCREEN_WIDTH // 2 + 150, Direction.LEFT)]
        for x, d in decor:
            draw_arrow(self.screen, x, 222, 46, d, arrow_color(d))

        sub = self.font_mid.render("点击箭头，让它们依次飞出棋盘！", True, COLOR_TEXT)
        self.screen.blit(sub, sub.get_rect(center=(SCREEN_WIDTH // 2, 280)))

        # 规则卡片
        draw_card(self.screen, (120, 310, 560, 128), radius=14)
        rules = [
            "箭头会沿朝向直线飞向棋盘边缘；",
            "前方有其他箭头阻挡时无法飞出，并消耗一次失误（每关 3 次）；",
            "按正确顺序清空全部箭头即可通关，还有三星评价等你挑战！",
        ]
        y = 340
        for line in rules:
            text = self.font_small.render(line, True, COLOR_TEXT)
            self.screen.blit(text, text.get_rect(center=(SCREEN_WIDTH // 2, y)))
            y += 30

        self.btn_start.draw(self.screen)
        self.btn_random.draw(self.screen)

        # 历史成绩（小卡片）
        data = load_save()
        total_stars = sum(data["stars"].values())
        best = sum(data["best"].values())
        info = self.font_tiny.render(
            f"历史成绩：共 {total_stars} 星 · 最高总分 {best}", True, COLOR_TEXT)
        info_rect = info.get_rect(center=(SCREEN_WIDTH // 2, 560))
        draw_card(self.screen, info_rect.inflate(44, 18), radius=10)
        self.screen.blit(info, info_rect)

    def _draw_playing(self) -> None:
        session = self.session
        # 顶部信息卡片
        draw_card(self.screen, (12, 10, SCREEN_WIDTH - 24, TOP_BAR_HEIGHT - 20),
                  radius=14)

        name = self.font_mid.render(f"关卡：{session.name}", True, COLOR_TEXT)
        self.screen.blit(name, name.get_rect(midleft=(28, 26)))

        # 信息徽章（彩色圆角）
        draw_badge(self.screen, (28, 56, 140, 34),
                   f"剩余箭头：{session.remaining}", self.font_tiny, COLOR_BTN_BLUE)
        mist_bg = COLOR_BTN_RED if session.mistakes > 0 else COLOR_BTN_GRAY
        draw_badge(self.screen, (178, 56, 116, 34),
                   f"失误：{session.mistakes}/{session.max_mistakes}",
                   self.font_tiny, mist_bg)
        mm, ss = divmod(session.elapsed, 60)
        draw_badge(self.screen, (304, 56, 128, 34), f"用时：{mm:02d}:{ss:02d}",
                   self.font_tiny, COLOR_BTN_GREEN)

        # 功能按钮
        self.btn_hint.draw(self.screen)
        self.btn_undo.draw(self.screen)
        self.btn_auto.text = "停止演示" if self.auto_solving else "自动求解"
        self.btn_auto.draw(self.screen)
        self.btn_restart.draw(self.screen)
        if self.auto_solving:
            # 自动演示期间：提示/撤销等置灰
            dim = pygame.Surface((322, TOP_BAR_HEIGHT - 20), pygame.SRCALPHA)
            dim.fill((255, 255, 255, 110))
            self.screen.blit(dim, (470, 10))

        self._draw_board()

    def _draw_board(self) -> None:
        board = self.session.board
        hover = self.cell_at(pygame.mouse.get_pos()) if self.state == "playing" else None

        # 棋盘外层阴影卡片
        pad = 14
        card = pygame.Rect(self.board_x - pad, self.board_y - pad,
                           board.cols * self.cell + pad * 2,
                           board.rows * self.cell + pad * 2)
        draw_card(self.screen, card, radius=16)

        for r in range(board.rows):
            for c in range(board.cols):
                rect = pygame.Rect(self.board_x + c * self.cell,
                                   self.board_y + r * self.cell,
                                   self.cell, self.cell)
                if hover == (r, c):
                    bg = COLOR_CELL_HOVER
                else:
                    bg = COLOR_CELL_A if (r + c) % 2 == 0 else COLOR_CELL_B
                pygame.draw.rect(self.screen, bg, rect)
                pygame.draw.rect(self.screen, COLOR_GRID_LINE, rect, 1)

                arrow = board.grid[r][c]
                if arrow is None:
                    continue
                shake = self.shake_of(arrow)
                if shake is not None:
                    shake.draw(self.screen, self.cell * 0.62)
                else:
                    color = arrow_color(arrow.direction)
                    if hover == (r, c):
                        color = lighten(color, 30)
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
        overlay.fill((232, 238, 244, 180))
        self.screen.blit(overlay, (0, 0))

        # 结果卡片
        draw_card(self.screen, (140, 130, 520, 380), radius=20)

        title_color = COLOR_GOLD if is_won else COLOR_BTN_RED
        title = self.font_title.render(headline, True, title_color)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 190)))

        if is_won and self.session is not None:
            stars = self.session.stars()
            star_text = "★" * stars + "☆" * (3 - stars)
            star_img = self.font_big.render(star_text, True, COLOR_GOLD)
            self.screen.blit(star_img, star_img.get_rect(center=(SCREEN_WIDTH // 2, 260)))

            mm, ss = divmod(self.session.elapsed, 60)
            info = self.font_mid.render(
                f"得分：{self.session.score()}　用时：{mm:02d}:{ss:02d}　"
                f"失误：{self.session.mistakes}/{self.session.max_mistakes}",
                True, COLOR_TEXT)
            self.screen.blit(info, info.get_rect(center=(SCREEN_WIDTH // 2, 320)))

            # 历史最佳
            key = str(self.level_index + 1)
            data = load_save()
            best = data["best"].get(key, 0)
            best_line = self.font_small.render(
                f"本关历史最高分：{best}", True, COLOR_TEXT)
            self.screen.blit(best_line, best_line.get_rect(center=(SCREEN_WIDTH // 2, 370)))

            if self.is_random or self.level_index + 1 >= len(LEVELS):
                self.btn_next.text = "返回开始"
            else:
                self.btn_next.text = "下一关"
            self.btn_next.draw(self.screen)
        else:
            sub = self.font_mid.render("失误次数已用完，再来一次吧！", True, COLOR_TEXT)
            self.screen.blit(sub, sub.get_rect(center=(SCREEN_WIDTH // 2, 290)))
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
