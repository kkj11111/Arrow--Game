# -*- coding: utf-8 -*-
"""一箭又一箭 —— 核心游戏逻辑。

本模块只包含与图形界面无关的纯逻辑（箭头、棋盘、路径检测、会话状态），
因此可以脱离 Pygame 独立运行和测试。关卡数据见 levels.py。

棋盘表示：
    棋盘是一个二维网格 grid，grid[r][c] 要么是 Arrow 对象，要么是 None（空格）。
    关卡用字符数组描述，例如：
        ['↑', '·', '·', '·'],
        ['·', '→', '→', '·'],
    其中 '↑↓←→' 表示带方向的箭头，'·' 表示空格。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# 方向
# ---------------------------------------------------------------------------


class Direction(Enum):
    """箭头方向。value 为 (行增量, 列增量)，用于沿方向逐格前进。"""

    UP = (-1, 0)
    DOWN = (1, 0)
    LEFT = (0, -1)
    RIGHT = (0, 1)


# 字符 -> 方向（关卡数据用）
DIRECTION_FROM_CHAR: Dict[str, Direction] = {
    "↑": Direction.UP,
    "↓": Direction.DOWN,
    "←": Direction.LEFT,
    "→": Direction.RIGHT,
}

# 方向 -> 字符（显示用）
CHAR_FROM_DIRECTION: Dict[Direction, str] = {
    d: ch for ch, d in DIRECTION_FROM_CHAR.items()
}


@dataclass
class Arrow:
    """棋盘上的一个箭头。row/col 为格子坐标，direction 为朝向。"""

    row: int
    col: int
    direction: Direction

    @property
    def symbol(self) -> str:
        return CHAR_FROM_DIRECTION[self.direction]


# ---------------------------------------------------------------------------
# 棋盘与路径检测
# ---------------------------------------------------------------------------


class Board:
    """网格棋盘。"""

    def __init__(self, grid: List[List[str]]):
        self.rows = len(grid)
        self.cols = len(grid[0])
        self.grid: List[List[Optional[Arrow]]] = [
            [None] * self.cols for _ in range(self.rows)
        ]
        for r in range(self.rows):
            for c in range(self.cols):
                ch = grid[r][c].strip()
                if ch in DIRECTION_FROM_CHAR:
                    self.grid[r][c] = Arrow(r, c, DIRECTION_FROM_CHAR[ch])

    # ---------- 查询 ----------

    def in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.rows and 0 <= col < self.cols

    def arrow_at(self, row: int, col: int) -> Optional[Arrow]:
        """返回 (row, col) 处的箭头；空格或越界返回 None。"""
        if not self.in_bounds(row, col):
            return None
        return self.grid[row][col]

    def remaining(self) -> int:
        """棋盘上剩余的箭头数量。"""
        return sum(1 for row in self.grid for a in row if a is not None)

    def is_cleared(self) -> bool:
        return self.remaining() == 0

    # ---------- 路径检测（本作业的核心算法） ----------

    def is_path_clear(self, arrow: Arrow) -> bool:
        """判断箭头前方到棋盘边界之间是否存在其他箭头。

        从箭头所在格沿其方向逐格前进，只要还在棋盘内：
            - 遇到其他箭头 -> 返回 False（被阻挡，不能飞出）
            - 走到边界外  -> 返回 True（路径畅通，可以飞出）
        返回 True 表示箭头可以飞出棋盘。
        """
        dr, dc = arrow.direction.value
        r, c = arrow.row + dr, arrow.col + dc
        while self.in_bounds(r, c):
            if self.grid[r][c] is not None:
                return False
            r += dr
            c += dc
        return True

    # ---------- 修改 ----------

    def remove(self, arrow: Arrow) -> None:
        """把箭头移出棋盘（飞出）。"""
        self.grid[arrow.row][arrow.col] = None


# ---------------------------------------------------------------------------
# 会话状态（一局的失误次数 / 胜负），同样与界面无关
# ---------------------------------------------------------------------------


class GameSession:
    """一局的完整状态：关卡 + 失误次数 + 胜负判定。

    click(row, col) 返回本次点击的结果：
        "fly"     -> 箭头前方畅通，已飞出
        "blocked" -> 箭头被阻挡，失误次数 +1
        "empty"   -> 点击的是空格
    """

    def __init__(self, level: dict):
        self.name: str = level["name"]
        self.max_mistakes: int = level["mistakes"]
        self.mistakes: int = 0
        self.board = Board(level["grid"])
        self.finished: bool = False  # True 表示胜负已定

    @property
    def remaining(self) -> int:
        return self.board.remaining()

    @property
    def won(self) -> bool:
        return self.finished and self.board.is_cleared()

    @property
    def lost(self) -> bool:
        return self.finished and not self.board.is_cleared()

    def click(self, row: int, col: int) -> str:
        """玩家点击 (row, col)，返回本次点击的结果字符串。"""
        arrow = self.board.arrow_at(row, col)
        if arrow is None:
            return "empty"
        if self.board.is_path_clear(arrow):
            self.board.remove(arrow)
            if self.board.is_cleared():
                self.finished = True
            return "fly"
        self.mistakes += 1
        if self.mistakes >= self.max_mistakes:
            self.finished = True
        return "blocked"
