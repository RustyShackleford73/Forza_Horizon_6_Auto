"""
监控所有场景的模板匹配相似度，每3秒输出一次，并保存检测区域截图。
用法：python monitor.py [配置文件路径，默认 buy.cfg]
"""

import json
import time
import ctypes
import os
import logging
from datetime import datetime
from ctypes import wintypes
import cv2
import numpy as np
import mss

# ----------------------------- 日志设置 -----------------------------
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("Monitor")

# 截图保存目录
DEBUG_DIR = "debug_roi"

# ----------------------------- 窗口工具 -----------------------------
class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def get_game_window_rect(title):
    """获取游戏客户区在屏幕上的位置和尺寸"""
    hwnd = ctypes.windll.user32.FindWindowW(None, title)
    if not hwnd:
        return None
    pt = POINT(0, 0)
    ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(pt))
    client_rect = ctypes.wintypes.RECT()
    ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(client_rect))
    return (pt.x, pt.y, client_rect.right, client_rect.bottom)

def is_game_foreground(title):
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    buf = ctypes.create_unicode_buffer(512)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value == title

# ----------------------------- 图像匹配（返回分数） -----------------------------
def match_template(screen_bgr, template_path, region):
    """返回匹配得分 0~1，失败返回 0.0"""
    x1, y1, x2, y2 = region
    if x2 <= x1 or y2 <= y1:
        return 0.0
    roi = screen_bgr[y1:y2, x1:x2]
    template = cv2.imread(template_path)
    if template is None:
        return 0.0
    if template.shape[0] > roi.shape[0] or template.shape[1] > roi.shape[1]:
        template = cv2.resize(template, (roi.shape[1], roi.shape[0]))
    res = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    return max_val

# ----------------------------- 截图保存 -----------------------------
def save_roi(screen_bgr, region, scene_name):
    """将指定区域的图像保存到 debug_roi 目录，文件名包含场景名和时间戳"""
    os.makedirs(DEBUG_DIR, exist_ok=True)
    x1, y1, x2, y2 = region
    if x2 <= x1 or y2 <= y1:
        return
    roi = screen_bgr[y1:y2, x1:x2]
    timestamp = datetime.now().strftime("%H%M%S")
    filename = f"{scene_name}_{timestamp}.png"
    filepath = os.path.join(DEBUG_DIR, filename)
    cv2.imwrite(filepath, roi)
    logger.debug(f"已保存截图: {filepath}")  # 如果不想看到大量日志，可注释此行

# ----------------------------- 主函数 -----------------------------
def monitor(config_path="buy.cfg"):
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    game_title = config["game_window_title"]
    scenes = config["scenes"]
    logger.info(f"监控启动，游戏窗口标题: {game_title}")
    logger.info(f"共 {len(scenes)} 个场景待检测，每3秒刷新一次")
    logger.info(f"检测区域截图保存至: {os.path.abspath(DEBUG_DIR)}")

    with mss.mss() as sct:
        while True:
            if not is_game_foreground(game_title):
                time.sleep(1)
                continue

            win_rect = get_game_window_rect(game_title)
            if win_rect is None:
                logger.warning("未找到游戏窗口，等待...")
                time.sleep(2)
                continue
            base_x, base_y, win_w, win_h = win_rect

            monitor_region = {
                "left": base_x,
                "top": base_y,
                "width": win_w,
                "height": win_h,
            }
            screenshot = np.array(sct.grab(monitor_region))
            screen_bgr = screenshot[:, :, :3]

            scores = {}
            for scene in scenes:
                name = scene["name"]
                region = scene["region"]
                template = scene["template"]

                # 保存当前场景的 ROI 截图
                save_roi(screen_bgr, region, name)

                score = match_template(screen_bgr, template, region)
                scores[name] = score

            score_str = " | ".join([f"{name}: {score:.3f}" for name, score in scores.items()])
            logger.info(f"匹配度 → {score_str}")

            time.sleep(3)

if __name__ == "__main__":
    import sys
    cfg = sys.argv[1] if len(sys.argv) > 1 else "buy.cfg"
    monitor(cfg)