import cv2
import numpy as np
import subprocess
import os
import sys

# ================= 配置区域 =================
ADB_PATH = r"E:/MuMuPlayer/nx_main/adb.exe"
DEVICE_ID = "127.0.0.1:16416"

# 临时文件
TEMP_REMOTE = "/sdcard/temp_cap.png"
TEMP_LOCAL = "temp_cap.png"

# 数据存储
coords = {}

# ================= 工具函数 =================
def get_screenshot():
    """稳健截图"""
    try:
        subprocess.run([ADB_PATH, "-s", DEVICE_ID, "shell", "screencap", "-p", TEMP_REMOTE], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        if os.path.exists(TEMP_LOCAL): os.remove(TEMP_LOCAL)
        subprocess.run([ADB_PATH, "-s", DEVICE_ID, "pull", TEMP_REMOTE, TEMP_LOCAL], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        if os.path.exists(TEMP_LOCAL):
            return cv2.imread(TEMP_LOCAL)
    except Exception as e:
        print(f"截图出错: {e}")
    return None

# 全局变量用于鼠标回调
current_click = None
img_display = None

def mouse_callback(event, x, y, flags, param):
    global current_click, img_display
    if event == cv2.EVENT_LBUTTONDOWN:
        current_click = (x, y)
        print(f"   -> 捕获坐标: ({x}, {y})")
        # 画个圈反馈
        cv2.circle(img_display, (x, y), 8, (0, 0, 255), -1)
        cv2.imshow("Pick Point", img_display)

def wait_for_click(window_name):
    """等待用户点击一次，返回坐标"""
    global current_click
    current_click = None # 重置
    while current_click is None:
        if cv2.waitKey(50) == 27: # ESC 退出
            sys.exit()
    return current_click

# ================= 主流程 =================

def main():
    print("="*50)
    print("      阴阳师 交互式坐标获取助手")
    print("="*50)
    print("请确保模拟器已打开。按 Ctrl+C 可随时强制终止。")
    
    # 尝试连接
    subprocess.run([ADB_PATH, "connect", DEVICE_ID], stdout=subprocess.DEVNULL)

    cv2.namedWindow("Pick Point", cv2.WINDOW_GUI_NORMAL)
    cv2.setMouseCallback("Pick Point", mouse_callback)
    
    global img_display

    # --- 阶段 1: 获取9个结界 (一张图) ---
    print("\n【阶段 1/2】获取 9 个结界坐标")
    print("请手动操作模拟器，停留在【结界突破-主界面】（能看到9个头像）。")
    input(">>> 准备好后，请按【回车键】开始截图...")
    
    img = get_screenshot()
    if img is None: return
    img_display = img.copy()
    cv2.imshow("Pick Point", img_display)
    
    grid_points = []
    print("请在弹出的图片窗口中，【依次点击】第1个到第9个结界。")
    
    for i in range(1, 10):
        print(f"   待点击: 结界_{i} ... ", end="")
        sys.stdout.flush()
        pt = wait_for_click("Pick Point") # 等待点击
        grid_points.append(pt)
        # 在图上标个号方便看
        cv2.putText(img_display, str(i), (pt[0], pt[1]), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
        cv2.imshow("Pick Point", img_display)
        # 短暂防抖
        cv2.waitKey(200)

    coords['grids'] = grid_points
    print("✅ 9个结界获取完成！")

    # --- 阶段 2: 获取各个分散按钮 (多张图) ---
    print("\n【阶段 2/2】获取功能按钮 (需要你配合操作界面)")
    
    # 定义任务列表：(显示名称, 提示语)
    tasks = [
        ("BTN_ATTACK", "【进攻】按钮", "请点击任意一个结界，弹出【进攻】弹窗"),
        ("BTN_READY",  "【准备】按钮", "请点击进攻，进入【式神录/准备】界面"),
        ("BTN_EXIT",   "【左上角退出】", "仍在准备界面，请找到左上角的【返回/退出】箭头"),
        ("BTN_CONFIRM_EXIT", "【确认退出】", "请点击退出，弹出【确认退出】弹窗"),
        ("BTN_AGAIN",  "【再次挑战】", "请让战斗失败/退出，进入失败结算界面 (如果没有，就凭感觉点大概位置)"),
        ("AREA_REWARD","【空白奖励区】", "回到主界面或任意界面，点一个不会触发功能的空白处"),
        ("BOX_EXTRA",  "【额外宝箱】", "想象屏幕中间弹出3/6/9胜宝箱的位置，点那个位置")
    ]

    for key, name, hint in tasks:
        print("-" * 40)
        print(f"目标: {name}")
        print(f"操作提示: {hint}")
        input(f">>> 调整好界面后，请按【回车键】截图...")
        
        img = get_screenshot()
        if img is None: 
            print("截图失败，跳过此点")
            continue
            
        img_display = img.copy()
        cv2.imshow("Pick Point", img_display)
        print(f"   请点击图片中的 {name} ...")
        
        pt = wait_for_click("Pick Point")
        coords[key] = pt
        print("   已记录。")

    cv2.destroyAllWindows()
    
    # --- 输出最终结果 ---
    print("\n" + "="*50)
    print("配置代码生成如下 (请复制替换 auto_raid.py 中的 class Coords):")
    print("="*50)
    
    print("class Coords:")
    print("    GRIDS = [")
    for i, pt in enumerate(coords['grids']):
        end_char = ",\n" if (i+1) % 3 == 0 else ", "
        if (i+1) % 3 == 1: print("        ", end="")
        print(f"{pt}", end=end_char)
    print("    ]")
    print("")
    for key, _, _ in tasks:
        if key in coords:
            print(f"    {key} = {coords[key]}")
        else:
            print(f"    {key} = (0, 0) # 未获取")
            
    print("="*50)

if __name__ == "__main__":
    main()