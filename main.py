"""
Forza Horizon 6 自动化脚本
依赖：paddlepaddle==2.6.2, paddleocr==2.7.0.3
"""

import os
import ctypes
import time
import logging
import numpy as np
import mss
import pydirectinput
from ctypes import wintypes
from paddleocr import PaddleOCR

# ----------------------------- 系统设置 -----------------------------
# 关闭 PaddleOCR 调试日志
logging.getLogger("ppocr").setLevel(logging.ERROR)

# 定义 Windows API 结构体
class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

# ----------------------------- 区域坐标配置 -----------------------------
# 格式：{区域名: (左上x, 左上y, 右下x, 右下y)}  ← 窗口内坐标

# enter_scenarios = {"继续", "选择", "领取奖励"}
# ENTER_SCENARIOS = {"继续", "选择", "领取奖励"}
REGION_COORDS = {
    "a": (796, 965, 1263, 1015),   # 设置路线提示
    "b": (140, 539, 301, 585),     # 加入赛事
    "c": (88, 661, 379, 700),      # 开始竞赛赛事
    "d": (141, 991, 240, 1021),    # 继续/选择
    "e": (1678, 931, 1860, 1037),  # 时速表
    "f": (101, 965, 292, 995),      # 自动驾驶状态
    "enter": (83, 994, 135, 1015)
}

# ----------------------------- OCR 初始化 -----------------------------
ocr = PaddleOCR(
    use_angle_cls=False,            # 关闭方向分类，提速
    lang="ch",
    use_textline_orientation=False,
    show_log=False
)

def tprint(msg):
    """打印带当前时间戳的消息"""
    now = time.strftime("%H:%M:%S")  # 只显示时分秒，若需要日期可改为 "%Y-%m-%d %H:%M:%S"
    print(f"[{now}] {msg}")

def get_text_from_region(sct, rect):
    """从指定区域截图并识别文字"""
    # 截取屏幕区域
    img = np.array(sct.grab(rect))
    # MSS 截图为 BGRA，取前三个通道 (BGR)
    img_bgr = img[:, :, :3]

    # OCR 识别，返回格式：[[[bbox, (text, confidence)], ...]]
    result = ocr.ocr(img_bgr, cls=False)

    text_content = ""
    if result and result[0]:
        for line in result[0]:
            # line[1] 是 (文字, 置信度) 的元组
            text, conf = line[1]
            text_content += text
    return text_content.strip()

# ----------------------------- 场景执行函数 -----------------------------
def scenario_idle():
    """场景1：退出并重新设置路线"""
    tprint("安娜，去下一场比赛")
    pydirectinput.press('c')
    time.sleep(0.5)
    pydirectinput.press('3')
    time.sleep(1)
    pydirectinput.press('enter')
    time.sleep(1.5)
    pydirectinput.press('enter')
    time.sleep(1)

def scenario_join_game():
    """连续按回车加入赛事（最多60次）"""
    tprint("加入赛事")
    for _ in range(60):
        pydirectinput.press('enter')
        time.sleep(3)

def scenario_start_game():
    """场景3：开始竞赛赛事"""
    tprint("开始竞赛")
    pydirectinput.press('enter')
    time.sleep(1)

def scenario_game_finished():
    """比赛结束，按回车跳过结算"""
    tprint("比赛结束")
    for _ in range(3):
        pydirectinput.press('enter')
        time.sleep(0.2)

def scenario_stuck():
    """场景5：时速为零时尝试脱困"""
    tprint("目的地到达，请接管")
    pydirectinput.press('c')
    time.sleep(0.5)
    pydirectinput.press('2')
    time.sleep(1)
    pydirectinput.keyDown('w')
    time.sleep(3)
    pydirectinput.keyUp('w')

def start_auto_pilot():
    pydirectinput.press('c')
    time.sleep(0.5)
    pydirectinput.press('3')

# ----------------------------- 主循环 -----------------------------
def main_loop():
    tprint("端到端辅助驾驶启动")
    time.sleep(5)

    # 卡死相关计数器
    speed_zero_start_time = None
    stuck_trigger_count = 0

    with mss.mss() as sct:
        while True:
            # ---- 0. 检查当前前台窗口是否为游戏 ----
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            buf = ctypes.create_unicode_buffer(512)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, 512)
            if buf.value != "Forza Horizon 6":
                time.sleep(1)
                continue

            # ---- 1. 获取游戏窗口在屏幕上的绝对位置 ----
            pt = POINT(0, 0)
            ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(pt))
            base_x, base_y = pt.x, pt.y

            # ---- 2. 根据窗口偏移动态生成截图区域 ----
            rects = {}
            for k, (x1, y1, x2, y2) in REGION_COORDS.items():
                rects[k] = {
                    "left": base_x + x1,
                    "top": base_y + y1,
                    "width": x2 - x1,
                    "height": y2 - y1,
                }

            # ---- 3. 识别各个区域的文字 ----
            text_a = get_text_from_region(sct, rects["a"])
            text_b = get_text_from_region(sct, rects["b"])
            text_c = get_text_from_region(sct, rects["c"])
            text_d = get_text_from_region(sct, rects["d"])
            text_e = get_text_from_region(sct, rects["e"])  # 时速
            text_f = get_text_from_region(sct, rects["f"])
            text_enter = get_text_from_region(sct, rects["enter"])
            tprint([text_a, text_b, text_c, text_d, text_d, text_e, text_f, text_enter])
            # 是否在赛事加入界面
            has_join_event = "加入赛事" in text_b
            auto_pilot_mode = "自动驾驶" in text_f

            # ---- 场景2：加入赛事 ----
            if has_join_event:
                scenario_join_game()
                # 检查自动驾驶开启状态
                if not auto_pilot_mode:
                    start_auto_pilot()
                speed_zero_start_time = None
                stuck_trigger_count = 0
                continue

            # ---- 场景1：设置路线提示（且不在赛事界面） ----
            if "设置路线以开始自动驾驶" in text_a and not has_join_event:
                scenario_idle()
                speed_zero_start_time = None
                stuck_trigger_count = 0
                continue

            # ---- 场景3：开始竞赛 ----
            if "开始竞赛赛事" in text_c:
                scenario_start_game()
                speed_zero_start_time = None
                stuck_trigger_count = 0
                continue

            # ---- 场景4：比赛结束（出现“继续”或“选择”） ----
            if text_d in {"继续", "选择", "领取奖励"}:
                scenario_game_finished()
                speed_zero_start_time = None
                stuck_trigger_count = 0
                continue

            # ---- 场景5 & 6：卡死检测 ----
            # 清洗时速文字（常见OCR误读）
            speed_str = text_e.replace("O", "0").replace("o", "0").replace(" ", "")

            if "继续" not in text_d and "选择"  not in text_d and "设置路线以开始自动驾驶" in text_a and not has_join_event:
                start_auto_pilot()
                tprint("端到端辅助驾驶开启")
            if speed_str in ("0", "00", "000"):
                if speed_zero_start_time is None:
                    speed_zero_start_time = time.time()
                elif time.time() - speed_zero_start_time >= 20:
                    scenario_stuck()
                    stuck_trigger_count += 1
                    speed_zero_start_time = None

                    # 场景6：连续三次脱困无效 → 强制重新开始
                    if stuck_trigger_count >= 3:
                        tprint("[场景6] 连续卡死，执行场景1逻辑")
                        scenario_idle()
                        stuck_trigger_count = 0
            
            if "Enter" in text_enter:
                pydirectinput.press('enter')


            # 控制循环频率，降低 CPU 占用
            time.sleep(0.5)

if __name__ == "__main__":
    main_loop()