import cv2
import time
import random
import numpy as np
import subprocess
import threading
import os
import sys

# ================= 配置区域 =================
ADB_PATH = r"E:/MuMuPlayer/nx_main/adb.exe"
MATCH_THRESHOLD = 0.80 
DEVICE_PORTS = ["16384", "16416"]

# 默认保底，万一配置里写错了防止报错
DEFAULT_END_FILE = "end/end_normal.png"

# === 场景配置 (全部显式指定 end_file) ===
SCENARIOS = {
    "1": { 
        "name": "组队",   
        "start_file": "start/start_team.png",
        "end_file":   "end/end_normal.png"
    },
    "2": { 
        "name": "八岐大蛇/御魂 （单人）",
        "start_file": "start/start_baqidashe.png",
        "end_file":   "end/end_normal.png"
    },
    "3": { 
        "name": "业原火", 
        "start_file": "start/start_yeyuanhuo.png",
        "end_file":   "end/end_normal.png"
    },
    "4": { 
        "name": "永生之海", 
        "start_file": "start/start_sea.png",
        "end_file":   "end/end_normal.png"
    },
    "5": { 
        "name": "探索", 
        "start_file": "start/start_tansuo.png",
        "end_file":   "end/end_normal.png"
    },
}
# ===========================================

def get_templates_for_mode(scenario_key):
    """
    根据配置加载：
    1. 指定的 start_file
    2. 指定的 end_file (如果没有指定则用默认)
    3. img/other 下的所有图片
    """
    templates = {}
    
    selected = SCENARIOS.get(scenario_key)
    if not selected:
        print(f"[错误] 模式 {scenario_key} 不存在")
        return None

    print(f"   -> 正在加载 [{selected['name']}] 资源...")

    # 1. 加载 Start 图片
    s_path = os.path.join("img", selected["start_file"])
    if not os.path.exists(s_path):
         print(f"[错误] Start 图片不存在: {s_path}")
         return None
         
    img_start = cv2.imread(s_path)
    if img_start is None:
        print(f"[错误] Start 图片无法读取: {s_path}")
        return None
    templates["star"] = img_start

    # 2. 加载 End 图片
    # 虽然配置里写全了，这里还是保留一个 .get 的写法作为双重保险
    e_file = selected.get("end_file", DEFAULT_END_FILE)
    e_path = os.path.join("img", e_file)
    
    if os.path.exists(e_path):
        img_end = cv2.imread(e_path)
        if img_end is not None:
            templates["end_reward"] = img_end
            print(f"      (结束图已加载: {e_file})")
        else:
            print(f"[警告] End 图片损坏: {e_path}")
    else:
        print(f"[警告] End 图片不存在: {e_path} (将无法计数)")

    # 3. 加载 img/other 下的所有图片 (通用防卡)
    other_dir = os.path.join("img", "other")
    if os.path.exists(other_dir):
        count_other = 0
        for filename in os.listdir(other_dir):
            if filename.lower().endswith(('.png', '.jpg')):
                full_path = os.path.join(other_dir, filename)
                img = cv2.imread(full_path)
                if img is not None:
                    templates[f"other_{filename}"] = img
                    count_other += 1
        if count_other > 0:
            print(f"      (已加载 {count_other} 张通用防卡图片)")
    
    return templates

def adb_connect(device_port):
    address = f"127.0.0.1:{device_port}"
    print(f"正在尝试连接 {address} ...", end="")
    try:
        subprocess.run([ADB_PATH, "connect", address], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        print(" 连接成功")
        return address
    except:
        print(" 连接失败")
        return None

class AutoPlayer(threading.Thread):
    def __init__(self, device_serial, battle_count, templates):
        threading.Thread.__init__(self)
        self.device = device_serial
        self.battle_count = battle_count
        self.templates = templates
        self.current_count = 0
        self.running = True
        self.last_end_time = None 

    def run(self):
        print(f"设备 [{self.device}] 挂机线程启动 (目标: {self.battle_count}次)")
        self.last_end_time = time.time()

        while self.running and self.current_count < self.battle_count:
            loop_start_time = time.time() # 记录循环开始时间

            # --- 1. 截屏阶段 ---
            t0 = time.time()
            screenshot = self.get_screenshot_safe()
            t_screenshot = time.time() - t0 # 计算截屏耗时
            
            if screenshot is None:
                print(f"[性能日志] [{self.device}] 截屏失败，耗时: {t_screenshot:.3f}s")
                time.sleep(1) 
                continue

            # --- 2. 识别与决策阶段 ---
            t1 = time.time()
            found_any = False

            # 1. 优先逻辑：点击开始
            if self.check_and_click(screenshot, "star", "点击开始"):
                found_any = True
                time.sleep(0.5) 

            # 2. 优先逻辑：结算
            elif self.check_and_click(screenshot, "end_reward", "战斗结算"):
                self.handle_battle_end()
                found_any = True

            # 3. 通用逻辑
            else:
                for key in self.templates.keys():
                    if key.startswith("other_"):
                        clean_name = key.replace("other_", "").replace(".png", "")
                        if self.check_and_click(screenshot, key, f"通用-{clean_name}"):
                            found_any = True
                            break 
            
            t_match = time.time() - t1 # 计算识别耗时

            if not found_any:
                time.sleep(0.3)
            
            loop_total = time.time() - loop_start_time
            
            # --- 关键：打印性能日志 ---
            # 为了防止刷屏太快，我们只打印截屏超过 0.5秒 或 识别超过 0.2秒 的情况
            # 或者你可以注释掉 if，全部打印
            print(f"[性能日志] [{self.device}] 循环总耗时: {loop_total:.3f}s | "
                  f"截屏: {t_screenshot:.3f}s | "
                  f"识别: {t_match:.3f}s")

        print(f"设备 [{self.device}] 任务结束。")

    def handle_battle_end(self):
        self.current_count += 1
        current_time = time.time()
        duration_str = ""
        if self.last_end_time is not None:
            duration = current_time - self.last_end_time
            duration_str = f" [本轮耗时: {duration:.1f}秒]"
        
        self.last_end_time = current_time
        print(f"[{self.device}] === 进度: {self.current_count}/{self.battle_count}{duration_str} ===")
        time.sleep(random.uniform(0.3, 0.6))

    def get_screenshot_safe(self):
        serial_safe = self.device.replace(":", "_")
        remote_path = f"/sdcard/s_{serial_safe}.png"
        local_path = f"temp_{serial_safe}.png"
        try:
            # 记录 ADB 命令的绝对时间
            subprocess.run([ADB_PATH, "-s", self.device, "shell", "screencap", "-p", remote_path], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            subprocess.run([ADB_PATH, "-s", self.device, "pull", remote_path, local_path], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            if os.path.exists(local_path):
                img = cv2.imread(local_path)
                return img
        except:
            pass
        return None

    def check_and_click(self, screenshot, template_key, log_msg, offset_x=0, offset_y=0):
        if template_key not in self.templates: return False
        template = self.templates[template_key]
        
        if screenshot.shape[0] < template.shape[0] or screenshot.shape[1] < template.shape[1]:
            return False

        res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        if max_val >= MATCH_THRESHOLD:
            top_left = max_loc
            h, w = template.shape[:2]
            cx = int(top_left[0] + w / 2) + offset_x
            cy = int(top_left[1] + h / 2) + offset_y
            
            final_x = cx + random.randint(-8, 8)
            final_y = cy + random.randint(-8, 8)
            
            print(f"[{self.device}] {log_msg} (置信: {max_val:.2f})")
            
            # 记录点击耗时
            t_click_start = time.time()
            self.adb_click(final_x, final_y)
            t_click_end = time.time()
            print(f"   -> 点击指令耗时: {t_click_end - t_click_start:.3f}s")
            
            return True
        return False

    def adb_click(self, x, y):
        cmd = [ADB_PATH, "-s", self.device, "shell", "input", "tap", str(x), str(y)]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL)
            time.sleep(random.uniform(0.05, 0.15))
        except:
            pass

def main():
    print("=== 阴阳师多设备独立挂机脚本 (全配置版) ===")
    
    print("\n[可用模式列表]")
    sorted_keys = sorted(SCENARIOS.keys(), key=lambda x: int(x))
    for key in sorted_keys:
        info = SCENARIOS[key]
        print(f"  [{key}] {info['name']}")
    print("-" * 30)

    subprocess.run([ADB_PATH, "kill-server"], stdout=subprocess.DEVNULL)
    subprocess.run([ADB_PATH, "start-server"], stdout=subprocess.DEVNULL)

    # 1. 设置默认次数
    try:
        d_input = input("\n设置全局默认次数 (回车=50): ")
        global_default = 50 if d_input.strip() == "" else int(d_input)
    except:
        global_default = 50

    players = []

    print("\n=== 开始配置设备 ===")
    for port in DEVICE_PORTS:
        print(f"\n>> 配置端口 [{port}]")
        
        # 2. 是否启用
        choice = input(f"   是否启用? (y/n, 默认y): ").strip().lower()
        if choice != '' and choice != 'y':
            continue

        dev = adb_connect(port)
        if not dev: continue

        # 3. 选择模式
        while True:
            mode = input(f"   请输入模式编号: ").strip()
            if not mode: mode = "1"
            
            # 加载资源
            templates = get_templates_for_mode(mode)
            if templates and "star" in templates and "end_reward" in templates:
                break
            elif templates:
                # 这种情况是图没找全
                print("   [错误] 资源缺失 (Start或End图没找到)，请检查文件路径")
            else:
                print("   [错误] 模式无效，请重试")

        # 4. 设定次数
        c_input = input(f"   请输入次数 (回车={global_default}): ").strip()
        try:
            count = int(c_input) if c_input else global_default
        except:
            count = global_default

        players.append(AutoPlayer(dev, count, templates))
        print(f"   -> 配置完成")

    if not players:
        print("\n未启动任何任务，退出。")
        return

    print("\n=== 任务启动 ===")
    for p in players: p.start()
    
    try:
        while any(p.is_alive() for p in players): time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止所有任务...")
        for p in players: p.running = False

    print("结束。")

if __name__ == "__main__":
    main()