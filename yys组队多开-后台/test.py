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
DEFAULT_END_FILE = "end/end_normal.png"

SCENARIOS = {
    "1": {"name": "组队", "start_file": "start/start_team.png", "end_file": "end/end_normal.png"},
    "2": {"name": "八岐大蛇/御魂 （单人）", "start_file": "start/start_baqidashe.png", "end_file": "end/end_normal.png"},
    "3": {"name": "业原火/御灵", "start_file": "start/start_yeyuanhuo.png", "end_file": "end/end_normal.png"},
    "4": {"name": "永生之海", "start_file": "start/start_sea.png", "end_file": "end/end_normal.png"},
    "5": {"name": "探索", "start_file": "start/start_tansuo.png", "end_file": "end/end_normal.png"},
    "6": {"name": "爬塔", "start_file": "start/start_pata.png", "end_file": "end/end_pata.png"},
    "7": {"name": "鬼兵演武", "start_file": "start/start_guibing.png", "end_file": "end/end_normal.png"},
}
# ===========================================

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

def get_templates_for_mode(scenario_key):
    templates = {}
    selected = SCENARIOS.get(scenario_key)
    if not selected: return None

    print(f"   -> 正在加载 [{selected['name']}] 资源...")
    # 加载 Start
    s_path = os.path.join("img", selected["start_file"])
    if os.path.exists(s_path):
        templates["star"] = cv2.imread(s_path)
    
    # 加载 End
    e_file = selected.get("end_file", DEFAULT_END_FILE)
    e_path = os.path.join("img", e_file)
    if os.path.exists(e_path):
        templates["end_reward"] = cv2.imread(e_path)

    # 加载 Other 下的所有图片
    other_dir = os.path.join("img", "other")
    if os.path.exists(other_dir):
        for filename in os.listdir(other_dir):
            if filename.lower().endswith(('.png', '.jpg')):
                img = cv2.imread(os.path.join(other_dir, filename))
                if img is not None:
                    # key 存储为 filename，方便后面识别
                    templates[f"other_{filename}"] = img
    return templates

class AutoPlayer(threading.Thread):
    def __init__(self, device_serial, battle_count, templates):
        threading.Thread.__init__(self)
        self.device = device_serial
        self.battle_count = battle_count
        self.templates = templates
        self.current_count = 0
        self.running = True
        
        self.last_matched_key = None
        self.stuck_counter = 0
        
        # 计时器：用于 200s 超时检测和耗时统计
        self.last_any_match_time = time.time()
        self.IDLE_TIMEOUT = 200

    def run(self):
        print(f"设备 [{self.device}] 挂机启动 (目标: {self.battle_count}次)")
        self.last_any_match_time = time.time()

        while self.running and self.current_count < self.battle_count:
            # 200s 空转检查
            idle_duration = time.time() - self.last_any_match_time
            if idle_duration > self.IDLE_TIMEOUT:
                print(f"\n[退出] 设备 [{self.device}] 超过 {self.IDLE_TIMEOUT}s 未匹配到任何目标，保护退出。")
                break

            screenshot = self.get_screenshot_safe()
            if screenshot is None:
                time.sleep(2)
                continue

            found_any = False

            # 优先级：开始 -> 结算 -> 其他
            if self.check_and_click(screenshot, "star", "点击开始"):
                found_any = True
                self.random_sleep(0.5, 1.0)
            
            elif self.check_and_click(screenshot, "end_reward", "战斗结算"):
                self.current_count += 1
                # 战斗结算后打印总进度
                print(f"[{self.device}] >>> 任务进度: {self.current_count}/{self.battle_count}")
                found_any = True
                self.random_sleep(1.0, 2.0)
            
            else:
                for key in self.templates.keys():
                    if key.startswith("other_"):
                        # 提取文件名，让用户知道具体识别了哪张图
                        display_name = key.replace("other_", "")
                        if self.check_and_click(screenshot, key, f"通用识别: {display_name}"):
                            found_any = True
                            break

            if found_any:
                # 只要有匹配，就更新全局最后匹配时间
                self.last_any_match_time = time.time()
            else:
                time.sleep(random.uniform(0.6, 1.0))

        print(f"设备 [{self.device}] 任务流程结束。")

    def check_and_click(self, screenshot, template_key, log_msg):
        if template_key not in self.templates: return False
        template = self.templates[template_key]
        if screenshot.shape[0] < template.shape[0] or screenshot.shape[1] < template.shape[1]: return False

        res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        if max_val >= MATCH_THRESHOLD:
            # 1. 耗时统计 (当前成功匹配的时间 - 上次成功匹配的时间)
            duration = time.time() - self.last_any_match_time
            
            # 2. 防卡死：同模板连续20次
            if self.last_matched_key == template_key:
                self.stuck_counter += 1
                if self.stuck_counter >= 20:
                    print(f"[{self.device}] [异常] 连续20次识别到 [{template_key}] 无跳转，安全退出。")
                    self.running = False
                    return False
            else:
                self.stuck_counter = 1
                self.last_matched_key = template_key

            # 3. 正态分布坐标计算
            h, w = template.shape[:2]
            cx, cy = max_loc[0] + w // 2, max_loc[1] + h // 2
            off_x = int(np.random.normal(0, w * 0.1))
            off_y = int(np.random.normal(0, h * 0.1))
            target_x = cx + max(-w//3, min(w//3, off_x))
            target_y = cy + max(-h//3, min(h//3, off_y))
            
            # 打印日志：增加耗时统计
            print(f"[{self.device}] {log_msg} (置信:{max_val:.2f}) [间隔耗时: {duration:.1f}s]")
            
            self.human_click(target_x, target_y)
            return True
        return False

    def human_click(self, x, y):
        """ 模拟真人点击，带有微位移和随机压感时间 """
        ex = x + random.randint(-1, 1)
        ey = y + random.randint(-1, 1)
        duration = random.randint(120, 250)
        cmd = [ADB_PATH, "-s", self.device, "shell", "input", "swipe", 
               str(x), str(y), str(ex), str(ey), str(duration)]
        subprocess.run(cmd, stdout=subprocess.DEVNULL)

    def random_sleep(self, min_s, max_s):
        time.sleep(random.uniform(min_s, max_s))

    def get_screenshot_safe(self):
        serial_safe = self.device.replace(":", "_")
        remote_path = f"/sdcard/s_{serial_safe}.png"
        local_path = f"temp_{serial_safe}.png"
        try:
            # 加入 timeout 防止 adb 无响应卡死整个线程
            subprocess.run([ADB_PATH, "-s", self.device, "shell", "screencap", "-p", remote_path], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=5)
            subprocess.run([ADB_PATH, "-s", self.device, "pull", remote_path, local_path], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=5)
            if os.path.exists(local_path):
                return cv2.imread(local_path)
        except:
            pass
        return None

def main():
    print("=== 阴阳师防检测多设备挂机 (全增强版) ===")
    
    sorted_keys = sorted(SCENARIOS.keys(), key=lambda x: int(x))
    for key in sorted_keys:
        print(f"  [{key}] {SCENARIOS[key]['name']}")
    
    subprocess.run([ADB_PATH, "start-server"], stdout=subprocess.DEVNULL)

    try:
        d_input = input("\n默认循环次数 (回车=50): ").strip()
        global_default = int(d_input) if d_input else 50
    except:
        global_default = 50

    players = []
    for port in DEVICE_PORTS:
        print(f"\n>> 设备端口 [{port}]")
        choice = input(f"   是否启用? (y/n, 默认y): ").strip().lower()
        if choice == 'n': continue

        dev = adb_connect(port)
        if not dev: continue

        while True:
            mode = input(f"   模式编号 (默认1): ").strip() or "1"
            templates = get_templates_for_mode(mode)
            if templates and "star" in templates: break
            print("   [错误] 资源加载失败（请检查img文件夹），请重新选择模式。")

        c_input = input(f"   此设备循环次数 (默认{global_default}): ").strip()
        count = int(c_input) if c_input else global_default

        players.append(AutoPlayer(dev, count, templates))

    if not players:
        print("没有启动任何任务。")
        return

    print("\n[系统] 正在启动所有挂机线程...")
    for p in players: p.start()
    
    try:
        while any(p.is_alive() for p in players): time.sleep(1)
    except KeyboardInterrupt:
        print("\n[系统] 检测到手动中断(Ctrl+C)，正在安全停止...")
        for p in players: p.running = False

    print("程序已结束。")

if __name__ == "__main__":
    main()
