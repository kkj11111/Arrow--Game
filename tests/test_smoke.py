# -*- coding: utf-8 -*-
"""一箭又一箭 —— 界面冒烟测试。

使用 SDL 的 dummy 驱动（不弹出真实窗口）驱动 Pygame 游戏主体，
验证完整的“开始 -> 游戏 -> 通关/失败 -> 重新开始”流程不会崩溃。
"""

import os
import sys
import unittest

# 必须在导入 pygame/main 之前设置，让 SDL 使用无窗口驱动
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: E402

# 第一关的通关顺序（与 test_core 一致）
LEVEL1_SOLUTION = [(0, 0), (1, 2), (3, 1), (1, 1)]


def wait_until(game, cond, max_frames=400):
    """推进游戏直到条件满足或超时。"""
    for _ in range(max_frames):
        game.update()
        if cond():
            return True
    return False


class TestSmoke(unittest.TestCase):
    def test_start_interface_renders(self):
        game = main.Game()
        game.draw()
        self.assertEqual(game.state, "start")
        # 点击“开始游戏”按钮
        game.on_click(game.btn_start.rect.center)
        self.assertEqual(game.state, "playing")

    def test_click_clear_arrow_shows_fly_animation(self):
        game = main.Game()
        game.start_level(0)
        game.draw()
        game.on_click(game.cell_center(0, 0))
        self.assertEqual(len(game.fly_animations), 1)
        # 飞出动画结束后应销毁
        self.assertTrue(wait_until(game, lambda: not game.fly_animations))
        self.assertEqual(game.state, "playing")

    def test_click_blocked_arrow_shows_shake_and_costs_mistake(self):
        game = main.Game()
        game.start_level(0)
        game.draw()
        game.on_click(game.cell_center(1, 1))  # 被 (1,2) 阻挡
        self.assertEqual(game.session.mistakes, 1)
        self.assertEqual(len(game.shake_animations), 1)
        # 晃动动画结束后恢复
        self.assertTrue(wait_until(game, lambda: not game.shake_animations))
        self.assertEqual(game.state, "playing")
        self.assertEqual(game.session.remaining, 4)  # 箭头未消失

    def test_win_flow_enters_won_then_next_level(self):
        game = main.Game()
        game.start_level(0)
        game.draw()
        for row, col in LEVEL1_SOLUTION:
            game.on_click(game.cell_center(row, col))
        self.assertTrue(game.session.won)
        self.assertTrue(wait_until(game, lambda: game.state == "won"))
        # 进入下一关
        game.on_click(game.btn_next.rect.center)
        self.assertEqual(game.state, "playing")
        self.assertEqual(game.level_index, 1)

    def test_lose_flow_enters_lost_then_restart(self):
        game = main.Game()
        game.start_level(0)
        game.draw()
        for _ in range(3):
            game.on_click(game.cell_center(1, 1))  # 连点被阻挡的箭头
            wait_until(game, lambda: not game.shake_animations)
        self.assertEqual(game.session.mistakes, 3)
        self.assertTrue(wait_until(game, lambda: game.state == "lost"))
        # 失败后重新开始本关
        game.on_click(game.btn_retry.rect.center)
        self.assertEqual(game.state, "playing")
        self.assertEqual(game.session.mistakes, 0)
        self.assertEqual(game.session.remaining, 4)

    def test_restart_button_resets_session(self):
        game = main.Game()
        game.start_level(0)
        game.draw()
        game.on_click(game.cell_center(0, 0))   # 飞掉一个
        game.on_click(game.cell_center(1, 1))   # 撞一次
        game.on_click(game.btn_restart.rect.center)
        self.assertEqual(game.session.mistakes, 0)
        self.assertEqual(game.session.remaining, 4)
        self.assertEqual(game.state, "playing")

    def test_last_level_won_returns_to_start(self):
        game = main.Game()
        game.start_level(len(main.LEVELS) - 1)
        game.draw()
        # 直接强制清空会话（模拟通关状态）
        game.session.finished = True
        game.session.board = game.session.board  # 保持引用一致
        # 手动把所有箭头移除
        for r in range(game.session.board.rows):
            for c in range(game.session.board.cols):
                game.session.board.grid[r][c] = None
        game.update()
        self.assertEqual(game.state, "won")
        game.draw()
        game.on_click(game.btn_next.rect.center)  # 最后一关按钮为“返回开始”
        self.assertEqual(game.state, "start")


if __name__ == "__main__":
    unittest.main(verbosity=2)
