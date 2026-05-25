import json
import time
import ctypes
import logging
from ctypes import wintypes
import cv2
import numpy as np
import mss
import pydirectinput
import sys

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def tprint(msg):
    """打印带当前时间戳的消息"""
    now = time.strftime("%H:%M:%S")  # 只显示时分秒，若需要日期可改为 "%Y-%m-%d %H:%M:%S"
    print(f"[{now}] {msg}")

def get_game_window_rect(title):
    hwnd = ctypes.windll.user32.FindWindowW(None, title)
    if not hwnd:
        return None
    rect = ctypes.wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)

def is_game_foreground(title):
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    buf = ctypes.create_unicode_buffer(512)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value == title

def match_template(screen_bgr, template_path, region):
    x1, y1, x2, y2 = region
    roi = screen_bgr[y1:y2, x1:x2]
    template = cv2.imread(template_path)
    if template is None:
        logger.error(f"无法读取模板图片: {template_path}")
        return False
    if template.shape[0] > roi.shape[0] or template.shape[1] > roi.shape[1]:
        template = cv2.resize(template, (roi.shape[1], roi.shape[0]))
    result = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val

def execute_actions(actions, base_x=0, base_y=0):
    for action in actions:
        if action["type"] == "press":
            pydirectinput.press(action["key"])
            logger.info(f"按下按键: {action['key']}")
        elif action["type"] == "wait":
            logger.info(f"等待 {action['seconds']} 秒")
            time.sleep(action["seconds"])
        elif action["type"] == "keyDown":
            pydirectinput.keyDown(action["key"])
            logger.info(f"按住按键: {action['key']}")
        elif action["type"] == "keyUp":
            pydirectinput.keyUp(action["key"])
            logger.info(f"释放按键: {action['key']}")

# === 状态机 ===
def filter_scenes_by_state(scenes, current_state):
    """返回在当前状态下应该检测的场景列表"""
    active_scenes = []
    for scene in scenes:
        active_states = scene.get("active_in_states", ["*"])
        if "*" in active_states or current_state in active_states:
            active_scenes.append(scene)
    return active_scenes

def change_state(scene, current_state):
    """根据场景的 on_trigger_change_state 字段切换状态"""
    new_state = scene.get("on_trigger_change_state")
    if new_state and new_state != current_state:
        logger.info(f"状态切换: {current_state} → {new_state}")
        return new_state
    return current_state

# === 主循环 ===
def main_loop(config_path="config.json"):
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    game_title = config["game_window_title"]
    scenes = config["scenes"]
    current_state = config.get("initial_state", "default")
    logger.info(f"初始状态: {current_state}")

    last_triggered = {scene["name"]: 0.0 for scene in scenes}
    IDLE_TIMEOUT = 10  # 40秒无操作则激活全部场景
    logger.info(f"脚本启动，开始监控游戏窗口: {game_title}")
    time.sleep(3)
    last_action_time = time.time()

    with mss.mss() as sct:
        while True:
            if not is_game_foreground(game_title):
                time.sleep(1)
                tprint("请切换游戏到前台")
                continue

            win_rect = get_game_window_rect(game_title)
            if win_rect is None:
                logger.warning("找不到游戏窗口，等待...")
                time.sleep(2)
                continue
            base_x, base_y, win_w, win_h = win_rect

            monitor = {
                "left": base_x,
                "top": base_y,
                "width": win_w,
                "height": win_h,
            }
            screenshot = np.array(sct.grab(monitor))
            screen_bgr = screenshot[:, :, :3]

            # 根据当前状态过滤场景
            if time.time() - last_action_time >= IDLE_TIMEOUT:
                # 超时：所有场景参与匹配（不受状态限制）
                active_scenes = scenes
                logger.warning("检测到10秒无操作，临时激活所有场景以尝试恢复...")
            else:
                # 正常：按状态机过滤场景
                logger.info(f"当前状态: {current_state}")
                active_scenes = filter_scenes_by_state(scenes, current_state)
                
            for scene in active_scenes:
                name = scene["name"]
                if time.time() - last_triggered[name] < scene.get("cooldown", 0):
                    continue

                region = scene["region"]
                max_val = match_template(screen_bgr, scene["template"], region)
                if max_val > scene["threshold"]:
                    logger.info(f"匹配到场景: {name} (当前状态: {current_state})")
                    execute_actions(scene["actions"])
                    last_triggered[name] = time.time()
                    # 尝试切换状态
                    current_state = change_state(scene, current_state)
                    last_action_time = time.time()
                    break  # 一次只处理一个场景
                else:
                    logger.info(f"当前场景：{current_state} 匹配场景: {name} (匹配度: {max_val})")

            time.sleep(config.get("loop_interval", 0.5))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    else:
        config_file = "buy.cfg"
    main_loop(config_file)