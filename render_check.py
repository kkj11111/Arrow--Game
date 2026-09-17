# -*- coding: utf-8 -*-
"""临时脚本：真实窗口驱动下渲染各界面并保存截图（供检查与 README 使用）。"""
import os
import pygame
import main

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
os.makedirs(OUT, exist_ok=True)

game = main.Game()

# 开始界面
game.draw()
pygame.image.save(game.screen, os.path.join(OUT, "01_start.png"))

# 游戏界面
game.start_level(0)
game.draw()
pygame.image.save(game.screen, os.path.join(OUT, "02_playing.png"))

# 飞出动画
game.on_click(game.cell_center(0, 0))
game.update()
game.update()
game.draw()
pygame.image.save(game.screen, os.path.join(OUT, "03_fly.png"))

# 碰撞动画
game.restart_level()
game.on_click(game.cell_center(1, 1))
for _ in range(4):
    game.update()
game.draw()
pygame.image.save(game.screen, os.path.join(OUT, "04_shake.png"))

# 通关界面（重开一局干净状态，避免上一步晃动动画未结束导致箭头不可点）
game.restart_level()
for row, col in [(0, 0), (1, 2), (3, 1), (1, 1)]:
    game.on_click(game.cell_center(row, col))
for _ in range(160):
    game.update()
game.draw()
pygame.image.save(game.screen, os.path.join(OUT, "05_won.png"))

# 失败界面
game.start_level(0)
for _ in range(3):
    game.on_click(game.cell_center(1, 1))
    for _ in range(100):
        game.update()
game.draw()
pygame.image.save(game.screen, os.path.join(OUT, "06_lost.png"))

pygame.quit()
print("截图完成:", sorted(os.listdir(OUT)))
