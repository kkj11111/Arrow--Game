# -*- coding: utf-8 -*-
"""截图生成脚本：真实窗口驱动下渲染各界面并保存截图（供检查与 README 使用）。

运行方式：python render_check.py
"""
import os

import pygame

import main

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
os.makedirs(OUT, exist_ok=True)

game = main.Game()

# 01 开始界面
game.draw()
pygame.image.save(game.screen, os.path.join(OUT, "01_start.png"))

# 02 游戏界面（第一关）
game.start_level(0)
game.draw()
pygame.image.save(game.screen, os.path.join(OUT, "02_playing.png"))

# 03 飞出动画
game.on_click(game.cell_center(0, 0))
game.update()
game.update()
game.draw()
pygame.image.save(game.screen, os.path.join(OUT, "03_fly.png"))

# 04 碰撞动画（红色晃动 + 失误 +1）
game.restart_level()
game.on_click(game.cell_center(1, 1))
for _ in range(4):
    game.update()
game.draw()
pygame.image.save(game.screen, os.path.join(OUT, "04_shake.png"))

# 05 提示高亮（金色光圈）
game.restart_level()
game.on_click(game.btn_hint.rect.center)
game.draw()
pygame.image.save(game.screen, os.path.join(OUT, "05_hint.png"))

# 06 通关界面（得分 + 星级）
game.restart_level()
for row, col in [(0, 0), (1, 2), (3, 1), (1, 1)]:
    game.on_click(game.cell_center(row, col))
for _ in range(160):
    game.update()
game.draw()
pygame.image.save(game.screen, os.path.join(OUT, "06_won.png"))

# 07 失败界面
game.start_level(0)
for _ in range(3):
    game.on_click(game.cell_center(1, 1))
    for _ in range(100):
        game.update()
game.draw()
pygame.image.save(game.screen, os.path.join(OUT, "07_lost.png"))

# 08 随机挑战关卡
game.state = "start"  # 回到开始界面
game.draw()
game.on_click(game.btn_random.rect.center)
game.draw()
pygame.image.save(game.screen, os.path.join(OUT, "08_random.png"))

# 09 选关界面（新功能）
game.state = "start"
game.on_click(game.btn_levels.rect.center)
game.draw()
pygame.image.save(game.screen, os.path.join(OUT, "09_level_select.png"))

pygame.quit()
print("截图完成:", sorted(os.listdir(OUT)))
