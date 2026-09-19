# -*- coding: utf-8 -*-
"""一箭又一箭 —— 关卡数据与可解性验证。

关卡用字符数组描述：
    '↑' '↓' '←' '→'  表示带方向的箭头
    '·'               表示空格
"""

import random
from typing import List, Optional

from game_logic import Board, DIRECTION_FROM_CHAR


def is_solvable(grid: List[List[str]]) -> bool:
    """判断一个关卡是否存在通关顺序（是否可解）。

    思路：反复找出所有“当前路径畅通”的箭头并模拟消除，直到清空棋盘。
    由于消除箭头只会减少阻挡、绝不会产生新的阻挡，
    因此按任意顺序消除当前可飞的箭头，不会影响最终能否清空。
    若某一步没有任何可飞的箭头但棋盘还有剩余，说明存在死锁，不可解。
    """
    board = Board(grid)
    while board.remaining() > 0:
        movable = [
            a
            for row in board.grid
            for a in row
            if a is not None and board.is_path_clear(a)
        ]
        if not movable:
            return False
        for a in movable:
            board.remove(a)
    return True


def solve(grid: List[List[str]]) -> Optional[List[tuple]]:
    """AI 求解：返回一个可通关的点击顺序 [(row, col), ...]。

    与 is_solvable 同理（贪心模拟），同时记录消除顺序。
    不可解时返回 None。
    """
    board = Board(grid)
    order: List[tuple] = []
    while board.remaining() > 0:
        movable = [
            a
            for row in board.grid
            for a in row
            if a is not None and board.is_path_clear(a)
        ]
        if not movable:
            return None
        for a in movable:
            order.append((a.row, a.col))
            board.remove(a)
    return order


def generate_random_level(rows: int = 6, cols: int = 5,
                          arrow_count: int = 7,
                          max_attempts: int = 300) -> Optional[dict]:
    """随机生成一个可通关的关卡（附加功能）。

    随机摆放 arrow_count 个四方向箭头，用 is_solvable 验证，
    直到生成可解的布局（最多尝试 max_attempts 次）。
    返回与 LEVELS 元素同结构的关卡字典；失败返回 None。
    """
    chars = list(DIRECTION_FROM_CHAR.keys())
    for _ in range(max_attempts):
        grid = [["·"] * cols for _ in range(rows)]
        cells = [(r, c) for r in range(rows) for c in range(cols)]
        random.shuffle(cells)
        for (r, c) in cells[:arrow_count]:
            grid[r][c] = random.choice(chars)
        if is_solvable(grid):
            return {
                "name": "随机挑战",
                "mistakes": 3,
                "grid": grid,
                "random": True,
            }
    return None


LEVELS: List[dict] = [
    {
        "name": "第一关 · 入门",
        "mistakes": 3,
        "grid": [
            ["↑", "·", "·", "·"],
            ["·", "→", "→", "·"],
            ["·", "·", "·", "·"],
            ["·", "←", "·", "·"],
        ],
    },
    {
        "name": "第二关 · 转弯",
        "mistakes": 3,
        "grid": [
            ["·", "·", "↓", "·", "·"],
            ["·", "→", "·", "→", "·"],
            ["·", "·", "·", "·", "·"],
            ["·", "·", "·", "·", "·"],
            ["←", "·", "·", "·", "↑"],
        ],
    },
    {
        "name": "第三关 · 层层递进",
        "mistakes": 3,
        "grid": [
            ["·", "↓", "·", "·", "·", "↑"],
            ["·", "→", "·", "→", "·", "·"],
            ["·", "·", "←", "·", "·", "·"],
            ["·", "·", "·", "·", "·", "·"],
            ["·", "·", "·", "←", "·", "·"],
            ["·", "·", "·", "·", "↑", "·"],
        ],
    },
    {
        "name": "第四关 · 十字路口",
        "mistakes": 3,
        "grid": [
            ["·", "→", "·", "·", "·"],
            ["·", "·", "·", "↑", "·"],
            ["·", "↓", "·", "·", "·"],
            ["·", "·", "·", "·", "←"],
            ["→", "·", "↑", "·", "·"],
        ],
    },
    {
        "name": "第五关 · 交错",
        "mistakes": 3,
        "grid": [
            ["·", "·", "↓", "·", "·", "·"],
            ["·", "→", "·", "·", "↑", "·"],
            ["←", "·", "·", "↓", "·", "·"],
            ["·", "·", "·", "·", "·", "→"],
            ["·", "↑", "·", "·", "←", "·"],
            ["·", "·", "→", "·", "·", "·"],
        ],
    },
    {
        "name": "第六关 · 最终关",
        "mistakes": 3,
        "grid": [
            ["→", "·", "↓", "·", "·", "↑"],
            ["·", "·", "·", "←", "·", "·"],
            ["↑", "·", "·", "·", "→", "·"],
            ["·", "·", "←", "·", "·", "·"],
            ["·", "↓", "·", "·", "·", "→"],
            ["·", "·", "·", "↑", "·", "·"],
        ],
    },
]

# 启动自检：确保内置关卡都可以通关，防止关卡设计成死局。
for _i, _lv in enumerate(LEVELS, 1):
    if not is_solvable(_lv["grid"]):
        raise ValueError(f"第 {_i} 关无法通关，请检查关卡设计！")
