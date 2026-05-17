import ctypes
import mss
import numpy as np
import pydirectinput
import time
from paddleocr import PaddleOCR

# ==========================================
# 1. 配置区域 (左上角X, 左上角Y, 右下角X, 右下角Y)
# ==========================================
# 请用微信截图(Alt+A)等工具，记录下你要识别的文字所在框的对角坐标
REGION_COORDS = {
    "a": (100, 100, 400, 200),  # 区域a: “设置路线以开始自动驾驶”
    "b": (500, 100, 800, 200),  # 区域b: “加入赛事”
    "c": (100, 800, 400, 900),  # 区域c: “开始竞赛赛事”
    "d": (500, 800, 800, 900),  # 区域d: “观看回放影片”
    "e": (1600, 900, 1800, 1050) # 区域e: 时速表位置 (右下角)
}

# ==========================================
# 2. 初始化 OCR 与辅助函数
# ==========================================
# 关闭角度检测提速，屏蔽调试日志
ocr = PaddleOCR(use_angle_cls=False, lang="ch", show_log=False)

def coords_to_mss_rect(coords):
    """将 (x1, y1, x2, y2) 转换为 mss 需要的字典格式"""
    return {
        "left": coords[0],
        "top": coords[1],
        "width": coords[2] - coords[0],
        "height": coords[3] - coords[1]
    }

def get_text_from_region(sct, rect):
    """从指定区域截图并提取所有文字拼成一个字符串"""
    img = np.array(sct.grab(rect))
    img_bgr = img[:, :, :3]  # 去掉 alpha 通道
    result = ocr.ocr(img_bgr, cls=False)
    
    text_content = ""
    if result and result[0]:
        for line in result[0]:
            text_content += line[1][0]
    return text_content

# ==========================================
# 3. 定义各个场景的执行动作
# ==========================================
def action_scenario_1():
    print(">>> 执行动作 1: 退出并重新设置路线")
    pydirectinput.press('esc')
    time.sleep(3)
    pydirectinput.press('s')
    time.sleep(1)
    pydirectinput.press('enter')
    time.sleep(1.5)
    pydirectinput.press('enter')
    time.sleep(1) # 缓冲

def action_scenario_2():
    print(">>> 执行动作 2: 加入赛事")
    for _ in range(4):
        pydirectinput.press('enter')
        time.sleep(4)

def action_scenario_3():
    print(">>> 执行动作 3: 开始竞赛赛事")
    pydirectinput.press('enter')
    time.sleep(1)

def action_scenario_4():
    print(">>> 执行动作 4: 观看回放影片")
    pydirectinput.press('enter')
    time.sleep(10)
    pydirectinput.press('enter')
    time.sleep(1)

def action_scenario_5():
    print(">>> 执行动作 5: 车辆卡死，长按 W 尝试脱困")
    pydirectinput.keyDown('w')
    time.sleep(3)
    pydirectinput.keyUp('w')

# ==========================================
# 4. 主循环逻辑 (状态机)
# ==========================================
def main_loop():
    print("✅ 脚本已启动，3秒后开始监控...")
    time.sleep(3)
    
    # 提前转换好所有的 mss 截屏区域
    rects = {k: coords_to_mss_rect(v) for k, v in REGION_COORDS.items()}
    
    # 场景 5 和 6 需要用的状态变量
    speed_zero_start_time = None
    scenario_5_trigger_count = 0

    with mss.mss() as sct:
        while True:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            buf = ctypes.create_unicode_buffer(512)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, 512)
            
            # 如果当前窗口不是地平线6，则休眠1秒并跳过本次循环（相当于暂停运行）
            if buf.value != "Forza Horizon 6":
                # print("游戏未在前台，脚本已暂停...") # 需要调试可以解除这行注释
                time.sleep(1)
                continue
            # --- 读取所有关键区域的文字 ---
            text_a = get_text_from_region(sct, rects["a"])
            text_b = get_text_from_region(sct, rects["b"])
            text_c = get_text_from_region(sct, rects["c"])
            text_d = get_text_from_region(sct, rects["d"])
            text_e = get_text_from_region(sct, rects["e"])

            # 打印调试信息（正式使用时可注释掉）
            # print(f"A:{text_a} | B:{text_b} | C:{text_c} | D:{text_d} | E(时速):{text_e}")

            has_join_event_in_b = "加入赛事" in text_b
            
            # --- 场景 2：检测到区域b显示“加入赛事” ---
            if has_join_event_in_b:
                action_scenario_2()
                # 只要触发了菜单操作，重置卡死判定
                speed_zero_start_time = None 
                scenario_5_trigger_count = 0
                continue # 完成动作后重新开始循环
            
            # --- 场景 1：区域a显示特定文字，且区域b不显示“加入赛事” ---
            if "设置路线以开始自动驾驶" in text_a and not has_join_event_in_b:
                action_scenario_1()
                speed_zero_start_time = None
                scenario_5_trigger_count = 0
                continue
                
            # --- 场景 3：检测到区域c显示“开始竞赛赛事” ---
            if "开始竞赛赛事" in text_c:
                action_scenario_3()
                speed_zero_start_time = None
                scenario_5_trigger_count = 0
                continue

            # --- 场景 4：检测到区域d显示文字“观看回放影片” ---
            if "观看回放影片" in text_d:
                action_scenario_4()
                speed_zero_start_time = None
                scenario_5_trigger_count = 0
                continue

            # --- 场景 5 & 6：时速检测与防卡死逻辑 ---
            # 清理时速文本，防止OCR误识别出字母 (比如把 0 识别成了 O)
            speed_text = text_e.replace("O", "0").replace("o", "0").strip()
            
            # 如果没有处在上面的任何菜单中，我们开始检查时速
            if speed_text == "0" or speed_text == "00" or speed_text == "000":
                # 开始计时
                if speed_zero_start_time is None:
                    speed_zero_start_time = time.time()
                
                # 如果时速为0持续了 20 秒
                elif time.time() - speed_zero_start_time >= 20:
                    action_scenario_5()
                    scenario_5_trigger_count += 1
                    speed_zero_start_time = None # 执行完后重新开始计20秒
                    
                    # --- 场景 6：如果场景5连续重复执行3次 ---
                    if scenario_5_trigger_count >= 3:
                        print(">>> 场景 6 触发: 连续3次长按W无效，执行场景 1 逻辑")
                        action_scenario_1()
                        scenario_5_trigger_count = 0 # 触发兜底后重置计数器
            else:
                # 只要时速不为 0（车动起来了），立刻重置计时器
                speed_zero_start_time = None
                # 如果时速文本存在且不为0，说明车正常跑起来了，也重置连续卡死计数器
                if speed_text: 
                    scenario_5_trigger_count = 0
            
            # 短暂休息，防止 CPU 占用达到 100%
            time.sleep(0.5)

if __name__ == "__main__":
    main_loop()