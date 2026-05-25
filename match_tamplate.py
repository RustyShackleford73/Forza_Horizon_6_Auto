import cv2 as cv
import numpy as np
import win32api, win32con
from PIL import ImageGrab, Image

def take_screenshot(points=(0,0,0,0)):
    """
    说明:
        返回RGB图像
    参数:
        :param points: 图像截取范围
    """
    width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
    height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
    game_img = ImageGrab.grab(bbox=(0, 0, width, height))
    screenshot = np.array(game_img)
    screenshot = cv.cvtColor(screenshot, cv.COLOR_BGR2RGB)
    return screenshot


def scan_screenshot(prepared) -> dict:
    """
    说明：
        比对图片
    参数：
        :param prepared: 比对图片地址
        :param pos: 截图的坐标
    """
    screenshot = take_screenshot()
    result = cv.matchTemplate(screenshot, prepared, cv.TM_CCORR_NORMED)
    length, width, __ = prepared.shape
    length = int(length)
    width = int(width)
    min_val, max_val, min_loc, max_loc = cv.minMaxLoc(result)
    
    return {
        "screenshot": screenshot,
        "min_val": min_val,
        "max_val": max_val,
        "min_loc": (min_loc[0] + width/2, min_loc[1] + length/2),
        "max_loc": (max_loc[0] + width/2, max_loc[1] + length/2)
    }

def scan_screenshots(p) -> list:
    """
    说明：
        比对图片
    参数：
        :param prepared: 比对图片地址
        :param pos: 截图的坐标
    """
    max_vals = []
    width = 2680
    height = 1300
    game_img = ImageGrab.grab(bbox=(600, 400, width, height))
    screenshot = np.array(game_img)
    # im = Image.fromarray(screenshot)
    # im.save('tmp.png')
    screenshot = cv.cvtColor(screenshot, cv.COLOR_BGR2RGB)
    for prepared in p:
        result = cv.matchTemplate(screenshot, prepared, cv.TM_CCORR_NORMED)
        min_val, max_val, min_loc, max_loc = cv.minMaxLoc(result)
        max_vals.append(max_val)
    return max_vals

if __name__ == "__main__":
    sample_img = '1.png'
    prepared = cv.imread(sample_img)
    prepared = cv.cvtColor(prepared, cv.COLOR_BGR2RGB)
    print(scan_screenshot(prepared)['max_val'], scan_screenshot(prepared)['min_val'])


    