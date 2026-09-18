# -*- coding: utf-8 -*-
"""一箭又一箭 —— 核心逻辑自动化测试。

覆盖作业要求的 T01 ~ T06，以及关卡可解性、点击空格、撤销、计分、
AI 求解、随机关卡等附加功能。
运行方式：python -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_logic import Direction, GameSession
from levels import LEVELS, generate_random_level, is_solvable, solve


def arrow_positions(board):
    """以 (row, col, direction) 集合表示棋盘布局，用于比较。"""
    return {
        (a.row, a.col, a.direction)
        for row in board.grid
        for a in row
        if a is not None
    }


class TestPathDetection(unittest.TestCase):
    """T01/T02/T03：路径检测与边界处理。"""

    def setUp(self):
        self.session = GameSession(LEVELS[0])  # 第一关

    def test_T01_clear_arrow_fly(self):
        """点击前方无阻挡的箭头 -> 箭头飞出棋盘并消失。"""
        # (0,0) 朝上，位于顶边，前方没有箭头
        result = self.session.click(0, 0)
        self.assertEqual(result, "fly")
        self.assertIsNone(self.session.board.arrow_at(0, 0))
        self.assertEqual(self.session.remaining, 3)
        self.assertEqual(self.session.mistakes, 0)

    def test_T02_blocked_arrow_keeps_and_costs_mistake(self):
        """点击前方有阻挡的箭头 -> 箭头不消失，失误次数减 1（+1）。"""
        before = arrow_positions(self.session.board)
        # (1,1) 朝右，右侧 (1,2) 有箭头阻挡
        result = self.session.click(1, 1)
        self.assertEqual(result, "blocked")
        self.assertEqual(arrow_positions(self.session.board), before)  # 布局未变
        self.assertEqual(self.session.mistakes, 1)

    def test_T03_edge_arrow_no_index_error(self):
        """点击位于边缘且朝向棋盘外的箭头 -> 正常消失，不发生越界错误。"""
        session = GameSession(LEVELS[1])
        # (4,0) 朝左，左侧就是棋盘边界
        result = session.click(4, 0)
        self.assertEqual(result, "fly")
        self.assertIsNone(session.board.arrow_at(4, 0))
        # (0,0) 朝上，位于顶边
        session2 = GameSession(LEVELS[0])
        self.assertEqual(session2.click(0, 0), "fly")


class TestGameFlow(unittest.TestCase):
    """T04/T05/T06：通关、失败与重新开始。"""

    def test_T04_clear_all_arrows_wins(self):
        """消除本关全部箭头 -> 通关。"""
        session = GameSession(LEVELS[0])
        # 第一关的通关顺序：(0,0) -> (1,2) -> (3,1) -> (1,1)
        order = [(0, 0), (1, 2), (3, 1), (1, 1)]
        for row, col in order:
            self.assertEqual(session.click(row, col), "fly")
        self.assertTrue(session.board.is_cleared())
        self.assertTrue(session.won)
        self.assertEqual(session.remaining, 0)

    def test_T05_mistakes_exhausted_loses(self):
        """失误次数耗尽 -> 失败，并允许重新开始。"""
        session = GameSession(LEVELS[0])
        # (1,1) 朝右一直被 (1,2) 阻挡，连点 3 次耗尽失误
        for _ in range(session.max_mistakes):
            self.assertEqual(session.click(1, 1), "blocked")
        self.assertTrue(session.lost)
        self.assertEqual(session.mistakes, session.max_mistakes)
        # 重新开始：新会话恢复到初始状态
        fresh = GameSession(LEVELS[0])
        self.assertEqual(fresh.mistakes, 0)
        self.assertEqual(fresh.remaining, 4)
        self.assertFalse(fresh.finished)

    def test_T06_restart_restores_layout(self):
        """游戏进行中重新开始 -> 箭头布局和失误次数恢复。"""
        session = GameSession(LEVELS[2])
        init_layout = arrow_positions(session.board)
        # 玩几下：飞掉一个、撞一次
        self.assertEqual(session.click(0, 5), "fly")
        self.assertEqual(session.click(1, 1), "blocked")
        self.assertNotEqual(arrow_positions(session.board), init_layout)
        # 重新开始 = 新建同关会话
        restarted = GameSession(LEVELS[2])
        self.assertEqual(arrow_positions(restarted.board), init_layout)
        self.assertEqual(restarted.mistakes, 0)


class TestUndo(unittest.TestCase):
    """附加功能：撤销上一步。"""

    def test_undo_fly_restores_arrow(self):
        session = GameSession(LEVELS[0])
        init = arrow_positions(session.board)
        self.assertEqual(session.click(0, 0), "fly")   # 飞出 (0,0)
        self.assertIsNone(session.board.arrow_at(0, 0))
        item = session.undo()
        self.assertEqual(item[0], "fly")
        self.assertEqual(arrow_positions(session.board), init)  # 箭头放回
        self.assertFalse(session.finished)

    def test_undo_blocked_restores_mistake(self):
        session = GameSession(LEVELS[0])
        self.assertEqual(session.click(1, 1), "blocked")
        self.assertEqual(session.mistakes, 1)
        item = session.undo()
        self.assertEqual(item[0], "blocked")
        self.assertEqual(session.mistakes, 0)

    def test_undo_empty_returns_none(self):
        session = GameSession(LEVELS[0])
        self.assertIsNone(session.undo())
        self.assertFalse(session.undoable)


class TestScoreAndStars(unittest.TestCase):
    """附加功能：计分与星级。"""

    def test_no_score_before_win(self):
        session = GameSession(LEVELS[0])
        self.assertEqual(session.score(), 0)
        self.assertEqual(session.stars(), 0)

    def test_stars_by_mistakes(self):
        s0 = GameSession(LEVELS[0])
        for r, c in [(0, 0), (1, 2), (3, 1)]:
            s0.click(r, c)
        s0.click(1, 1)  # 0 失误通关
        self.assertEqual(s0.stars(), 3)
        self.assertGreater(s0.score(), 0)

        s1 = GameSession(LEVELS[0])
        s1.click(1, 1)  # 先撞一次
        for r, c in [(0, 0), (1, 2), (3, 1), (1, 1)]:
            s1.click(r, c)
        self.assertEqual(s1.stars(), 2)

    def test_score_positive_after_win(self):
        session = GameSession(LEVELS[0])
        for r, c in [(0, 0), (1, 2), (3, 1), (1, 1)]:
            session.click(r, c)
        self.assertTrue(session.won)
        self.assertGreaterEqual(session.score(), 100)


class TestLevels(unittest.TestCase):
    """关卡质量：至少 3 关且都可解；AI 求解与随机关卡。"""

    def test_level_count_at_least_three(self):
        self.assertGreaterEqual(len(LEVELS), 3)

    def test_all_levels_solvable(self):
        for i, level in enumerate(LEVELS, 1):
            self.assertTrue(is_solvable(level["grid"]), f"第 {i} 关不可解！")

    def test_solve_returns_winning_order(self):
        for level in LEVELS:
            order = solve(level["grid"])
            self.assertIsNotNone(order)
            # 按求解顺序模拟点击，应能清空棋盘
            board = GameSession(level)
            for r, c in order:
                self.assertEqual(board.click(r, c), "fly")
            self.assertTrue(board.won)

    def test_random_level_generated_is_solvable(self):
        for _ in range(20):
            level = generate_random_level()
            self.assertIsNotNone(level)
            self.assertTrue(is_solvable(level["grid"]))
            # 随机关卡也可求解
            self.assertIsNotNone(solve(level["grid"]))


class TestMisc(unittest.TestCase):
    def test_click_empty_cell_returns_empty(self):
        session = GameSession(LEVELS[0])
        self.assertEqual(session.click(2, 0), "empty")

    def test_click_out_of_bounds_is_safe(self):
        session = GameSession(LEVELS[0])
        self.assertIsNone(session.board.arrow_at(-1, 0))
        self.assertIsNone(session.board.arrow_at(99, 99))

    def test_direction_symbols_roundtrip(self):
        from game_logic import CHAR_FROM_DIRECTION, DIRECTION_FROM_CHAR
        for d in Direction:
            self.assertEqual(DIRECTION_FROM_CHAR[CHAR_FROM_DIRECTION[d]], d)


if __name__ == "__main__":
    unittest.main(verbosity=2)
