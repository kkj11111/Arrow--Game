# -*- coding: utf-8 -*-
"""一箭又一箭 —— Pygame 图形界面。

游戏状态机：
    start   -> 开始界面
    playing -> 游戏界面（点击箭头）
    won     -> 通关界面（可进入下一关）
    lost    -> 失败界面（可重新开始本关）

动画：
    FlyAnimation   箭头飞出棋盘（沿方向移动直至移出屏幕）
    ShakeAnimation 箭头被阻挡时的晃动反馈（红色左右/上下抖动）
"""

import sys

import pygame

from game_logic import Direction, GameSession
from levels import LEVELS

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

SCREEN_WIDTH, SCREEN_HEIGHT = 800, 680
FPS = 60
TOP_BAR_HEIGHT = 96          # 游戏界面顶部信息栏高度

# 颜色
COLOR_BG = (246, 243, 232)          # 米色背景
COLOR_PANEL = (235, 230, 214)       # 信息栏背景
COLOR_GRID_LINE = (196, 190, 172)   # 网格线
COLOR_CELL = (255, 252, 242)        # 格子底色
COLOR_CELL_HOVER = (255, 244, 205)  # 悬停格子
COLOR_ARROW = (52, 84, 148)         # 箭头蓝
COLOR_ARROW_HOVER = (36, 62, 116)   # 悬停箭头深蓝
COLOR_ARROW_HIT = (204, 60, 48)     # 碰撞红
COLOR_TEXT = (60, 56, 48)
COLOR_TEXT_LIGHT = (255, 255, 255)
COLOR_BUTTON = (98, 126, 172)
COLOR_BUTTON_HOVER = (122, 150, 196)
COLOR_RED = (204, 60, 48)
COLOR_GOLD = (200, 156, 56)

# 动画参数
FLY_STEP = 16          # 飞出动画：每帧移动像素数
SHAKE_PHASE = 8        # 晃动：每 8 帧换一次方向
SHAKE_TIMES = 3        # 晃动：共 3 个来回
SHAKE_AMPLITUDE = 6    # 晃动幅度（像素）


def get_font(size: int) -> pygame.font.Font:
    """获取中文字体（Windows 优先微软雅黑，找不到则退回默认字体）。"""
    return pygame.font.SysFont("microsoftyahei,simhei,dengxian,arial", size)


# ---------------------------------------------------------------------------
# 绘制：用几何图形画箭头（不依赖外部素材）
# ---------------------------------------------------------------------------


def draw_arrow(surface, cx: float, cy: float, size: float,
               direction: Direction, color) -> None:
    """以 (cx, cy) 为中心绘制一个 size 大小的箭头。

    箭头由“头部三角形 + 箭杆矩形”组成，方向由 direction 决定。
    """
    s = size
    half = s * 0.40   # 三角形张开幅度
    tip = s * 0.52    # 三角形尖端到中心的距离
    tail = s * 0.42   # 箭杆延伸到中心另一侧的长度

    if direction == Direction.RIGHT:
        head = [(cx + tip, cy), (cx - tip * 0.6, cy - half), (cx - tip * 0.6, cy + half)]
        shaft = pygame.Rect(0, 0, tail * 0.9, s * 0.28)
        shaft.center = (cx - tip * 0.35, cy)
    elif direction == Direction.LEFT:
        head = [(cx - tip, cy), (cx + tip * 0.6, cy - half), (cx + tip * 0.6, cy + half)]
        shaft = pygame.Rect(0, 0, tail * 0.9, s * 0.28)
        shaft.center = (cx + tip * 0.35, cy)
    elif direction == Direction.UP:
        head = [(cx, cy - tip), (cx - half, cy + tip * 0.6), (cx + half, cy + tip * 0.6)]
        shaft = pygame.Rect(0, 0, s * 0.28, tail * 0.9)
        shaft.center = (cx, cy + tip * 0.35)
    else:  # DOWN
        head = [(cx, cy + tip), (cx - half, cy - tip * 0.6), (cx + half, cy - tip * 0.6)]
        shaft = pygame.Rect(0, 0, s * 0.28, tail * 0.9)
        shaft.center = (cx, cy - tip * 0.35)

    pygame.draw.polygon(surface, color, head)
    pygame.draw.rect(surface, color, shaft)


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
        """当前帧相对格心的偏移像素。"""
        phase = self.frame // SHAKE_PHASE
        sign = 1 if phase % 2 == 0 else -1
        # 横向箭头左右晃，纵向箭头上下晃
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
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("一箭又一箭")
        self.clock = pygame.time.Clock()

        self.font_title = get_font(56)
        self.font_big = get_font(44)
        self.font_mid = get_font(26)
        self.font_small = get_font(20)

        # 会话状态
        self.state = "start"        # start / playing / won / lost
        self.level_index = 0
        self.session: GameSession | None = None
        self.fly_animations = []
        self.shake_animations = []

        # 按钮（矩形位置固定，预创建以便事件处理与绘制共用）
        self.btn_start = Button((SCREEN_WIDTH // 2 - 100, 440, 200, 56),
                                "开始游戏", self.font_mid)
        self.btn_restart = Button((SCREEN_WIDTH - 170, 28, 146, 44),
                                  "重新开始", self.font_small)
        self.btn_next = Button((SCREEN_WIDTH // 2 - 100, 400, 200, 56),
                               "下一关", self.font_mid)
        self.btn_retry = Button((SCREEN_WIDTH // 2 - 100, 400, 200, 56),
                                "重新开始", self.font_mid)

        # 棋盘布局（进入关卡时计算）
        self.cell = 88
        self.board_x = 0
        self.board_y = 0

        self.running = True

    # ---------------- 关卡流程 ----------------

    def start_level(self, index: int) -> None:
        self.level_index = index
        self.session = GameSession(LEVELS[index])
        self.fly_animations.clear()
        self.shake_animations.clear()
        self._layout_board()
        self.state = "playing"

    def restart_level(self) -> None:
        self.start_level(self.level_index)

    def next_level(self) -> None:
        if self.level_index + 1 < len(LEVELS):
            self.start_level(self.level_index + 1)
        else:
            self.state = "start"

    def _layout_board(self) -> None:
        """根据当前关卡棋盘尺寸计算格子大小和棋盘左上角。"""
        rows = self.session.board.rows
        cols = self.session.board.cols
        area_top = TOP_BAR_HEIGHT + 16
        area_height = SCREEN_HEIGHT - area_top - 16
        self.cell = min(88, area_height // rows, (SCREEN_WIDTH - 64) // cols)
        board_w = cols * self.cell
        board_h = rows * self.cell
        self.board_x = (SCREEN_WIDTH - board_w) // 2
        self.board_y = area_top + (area_height - board_h) // 2

    def cell_center(self, row: int, col: int):
        return (self.board_x + col * self.cell + self.cell // 2,
                self.board_y + row * self.cell + self.cell // 2)

    def cell_at(self, pos):
        """屏幕坐标 -> 格子坐标；不在棋盘内返回 None。"""
        x, y = pos
        col = (x - self.board_x) // self.cell
        row = (y - self.board_y) // self.cell
        if 0 <= row < self.session.board.rows and 0 <= col < self.session.board.cols:
            return int(row), int(col)
        return None

    def shake_of(self, arrow):
        """返回正在晃动指定箭头的动画对象（没有则 None）。"""
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
        elif self.state == "playing":
            if self.btn_restart.clicked(pos):
                self.restart_level()
                return
            self._click_board(pos)
        elif self.state == "won":
            if self.btn_next.clicked(pos):
                self.next_level()
        elif self.state == "lost":
            if self.btn_retry.clicked(pos):
                self.restart_level()

    def _click_board(self, pos) -> None:
        if self.session is None or self.session.finished:
            return
        cell = self.cell_at(pos)
        if cell is None:
            return
        row, col = cell
        arrow = self.session.board.arrow_at(row, col)
        if arrow is None or self.shake_of(arrow) is not None:
            return  # 空格或正在晃动反馈中的箭头

        result = self.session.click(row, col)
        if result == "fly":
            self.fly_animations.append(FlyAnimation(arrow, self.cell_center(row, col)))
        elif result == "blocked":
            self.shake_animations.append(ShakeAnimation(arrow, self.cell_center(row, col)))

    # ---------------- 每帧更新 ----------------

    def update(self) -> None:
        for a in self.fly_animations:
            a.update()
        self.fly_animations = [a for a in self.fly_animations if not a.dead]

        for a in self.shake_animations:
            a.update()
        shaking = [a for a in self.shake_animations if not a.dead]
        self.shake_animations = shaking

        if self.state != "playing" or self.session is None:
            return
        # 失误耗尽：等晃动动画播完再进入失败界面（让玩家看到碰撞反馈）
        if self.session.lost and not shaking:
            self.state = "lost"
        # 全部飞出：等飞出动画播完再进入通关界面
        elif self.session.won and not self.fly_animations:
            self.state = "won"

    # ---------------- 绘制 ----------------

    def draw(self) -> None:
        self.screen.fill(COLOR_BG)
        if self.state == "start":
            self._draw_start()
        elif self.state == "playing":
            self._draw_playing()
        elif self.state == "won":
            left = self.session.max_mistakes - self.session.mistakes
            self._draw_result("恭喜通关！", f"本关剩余失误：{left}")
        elif self.state == "lost":
            self._draw_result("挑战失败！", "失误次数已用完，再来一次吧！")
        pygame.display.flip()

    def _draw_start(self) -> None:
        title = self.font_title.render("一箭又一箭", True, COLOR_TEXT)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 170)))
        sub = self.font_mid.render("点击箭头，让它们依次飞出棋盘！", True, COLOR_TEXT)
        self.screen.blit(sub, sub.get_rect(center=(SCREEN_WIDTH // 2, 240)))

        rules = [
            "规则：箭头会沿朝向直线飞行，飞向棋盘边缘。",
            "如果箭头前方有其他箭头阻挡，就无法飞出，并消耗一次失误。",
            "想办法按正确的顺序点击，清空全部箭头即可通关！",
        ]
        y = 310
        for line in rules:
            text = self.font_small.render(line, True, COLOR_TEXT)
            self.screen.blit(text, text.get_rect(center=(SCREEN_WIDTH // 2, y)))
            y += 34

        # 用一枚示例箭头做装饰
        draw_arrow(self.screen, SCREEN_WIDTH // 2 - 120, 300, 34, Direction.RIGHT, COLOR_ARROW)
        draw_arrow(self.screen, SCREEN_WIDTH // 2 + 120, 300, 34, Direction.UP, COLOR_ARROW)

        self.btn_start.draw(self.screen)

    def _draw_playing(self) -> None:
        # 顶部信息栏
        pygame.draw.rect(self.screen, COLOR_PANEL, (0, 0, SCREEN_WIDTH, TOP_BAR_HEIGHT))
        pygame.draw.line(self.screen, COLOR_GRID_LINE, (0, TOP_BAR_HEIGHT),
                         (SCREEN_WIDTH, TOP_BAR_HEIGHT), 2)

        session = self.session
        name = self.font_mid.render(f"关卡：{session.name}", True, COLOR_TEXT)
        self.screen.blit(name, (24, 22))
        remain = self.font_mid.render(f"剩余箭头：{session.remaining}", True, COLOR_TEXT)
        self.screen.blit(remain, (24, 58))

        mist_color = COLOR_RED if session.mistakes >= session.max_mistakes else COLOR_TEXT
        mist = self.font_mid.render(f"失误：{session.mistakes} / {session.max_mistakes}",
                                    True, mist_color)
        self.screen.blit(mist, mist.get_rect(midleft=(320, 58)))

        self.btn_restart.draw(self.screen)

        # 棋盘
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

        # 飞出动画（叠加在最上层）
        for a in self.fly_animations:
            a.draw(self.screen, self.cell * 0.62)

    def _draw_result(self, headline: str, subtitle: str) -> None:
        # 半透明遮罩，保留棋盘残影
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((246, 243, 232, 205))
        self.screen.blit(overlay, (0, 0))

        title = self.font_title.render(headline, True, COLOR_GOLD)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 240)))
        sub = self.font_mid.render(subtitle, True, COLOR_TEXT)
        self.screen.blit(sub, sub.get_rect(center=(SCREEN_WIDTH // 2, 310)))

        if self.state == "won":
            if self.level_index + 1 < len(LEVELS):
                self.btn_next.text = "下一关"
            else:
                self.btn_next.text = "返回开始"
            self.btn_next.draw(self.screen)
        else:
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
