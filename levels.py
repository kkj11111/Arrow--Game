# -*- coding: utf-8 -*-
"""一箭又一箭 —— 关卡数据与可解性验证。

关卡用字符数组描述：
    '↑' '↓' '←' '→'  表示带方向的箭头
    '·'               表示空格
"""

from typing import List

from game_logic import Board


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
]

# 启动自检：确保内置关卡都可以通关，防止关卡设计成死局。
for _i, _lv in enumerate(LEVELS, 1):
    if not is_solvable(_lv["grid"]):
        raise ValueError(f"第 {_i} 关无法通关，请检查关卡设计！")
