import cv2
import numpy as np
import subprocess
import time
import os
import random
import logging
from datetime import datetime

# ================= 配置区域 =================
ADB_PATH = r"E:/MuMuPlayer/nx_main/adb.exe"
DEVICE_ID = "127.0.0.1:16384"
TEMPLATE_DIR = "img"
LOG_DIR = "logs"

# 9个结界坐标
GRIDS = [
    (639, 404), (1315, 388), (1984, 388),
    (619, 665), (1288, 665), (1971, 675),
    (606, 932), (1292, 946), (1991, 925),
]

# ================= 日志设置 =================
if not os.path.exists(LOG_DIR): os.makedirs(LOG_DIR)
log_filename = os.path.join(LOG_DIR, f"raid_auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

class RealmRaidBot:
    def __init__(self):
        self.templates = {}
        self.load_templates()
        self.connect_adb()

    def connect_adb(self):
        logger.info(f"正在连接 ADB: {DEVICE_ID}...")
        subprocess.run([ADB_PATH, "connect", DEVICE_ID], stdout=subprocess.DEVNULL)

    def load_templates(self):
        # 移除了 refresh，不需要手动刷新了
        required_images = ["attack", "ready", "back", "confirm", "again", "reward"]
        logger.info("正在加载图片模板...")
        
        if not os.path.exists(TEMPLATE_DIR):
            logger.error(f"找不到文件夹: {TEMPLATE_DIR}")
            exit()
        
        for name in required_images:
            path = os.path.join(TEMPLATE_DIR, f"{name}.png")
            img = cv2.imread(path)
            if img is not None:
                self.templates[name] = img
            else:
                logger.warning(f"⚠️ 警告: 缺失模板 {name}.png")

    def get_screenshot(self):
        remote = "/sdcard/autocap.png"
        local = "autocap.png"
        try:
            subprocess.run([ADB_PATH, "-s", DEVICE_ID, "shell", "screencap", "-p", remote], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run([ADB_PATH, "-s", DEVICE_ID, "pull", remote, local], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(local):
                return cv2.imread(local)
        except Exception as e:
            logger.error(f"截图失败: {e}")
        return None

    def click(self, x, y, desc="未知目标"):
        x_rand = x + random.randint(-5, 5)
        y_rand = y + random.randint(-5, 5)
        logger.info(f"点击 -> {desc} ({x_rand}, {y_rand})")
        subprocess.run([ADB_PATH, "-s", DEVICE_ID, "shell", "input", "tap", str(x_rand), str(y_rand)], stdout=subprocess.DEVNULL)
        
        # 全局稳定延时
        time.sleep(random.uniform(1.0, 1.5)) 

    def find_image(self, template_name, screen):
        if template_name in self.templates:
            res = cv2.matchTemplate(screen, self.templates[template_name], cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            if max_val >= 0.8:
                h, w = self.templates[template_name].shape[:2]
                cx, cy = max_loc[0] + w//2, max_loc[1] + h//2
                return (cx, cy)
        return None

    def wait_and_click(self, template_name, timeout=15, desc=""):
        start_time = time.time()
        logger.info(f"寻找: [{desc}]...")
        
        while time.time() - start_time < timeout:
            screen = self.get_screenshot()
            if screen is None: continue
            
            pos = self.find_image(template_name, screen)
            if pos:
                logger.info(f" √ 发现 [{desc}] -> 点击")
                self.click(pos[0], pos[1], desc)
                return True
            time.sleep(0.5)
            
        logger.warning(f" X 未找到: [{desc}] (超时)")
        return False

    def process_rewards_loop(self):
        """无限清空奖励"""
        logger.info(">>> 监听结算(最长120s)...")
        
        if not self.wait_and_click("reward", timeout=120, desc="首个奖励"):
            logger.error("严重错误：战斗超时或未检测到结算！")
            return

        logger.info("检查后续奖励...")
        while True:
            time.sleep(2.0) 
            screen = self.get_screenshot()
            if screen is None: continue

            pos = self.find_image("reward", screen)
            if pos:
                logger.info(" ★ 发现额外奖励 -> 点击")
                self.click(pos[0], pos[1], "额外奖励")
            else:
                logger.info("未检测到奖励，流程结束。")
                break

    def ensure_select_target(self, index):
        """死磕选中目标"""
        target_pos = GRIDS[index]
        logger.info(f"准备选中第 {index+1} 个目标...")
        attempt = 0
        while True:
            attempt += 1
            self.click(target_pos[0], target_pos[1], f"结界_{index+1}")
            
            start_check = time.time()
            found = False
            while time.time() - start_check < 3.0:
                screen = self.get_screenshot()
                if self.find_image("attack", screen):
                    found = True
                    break
                time.sleep(0.5)
            
            if found:
                return
            else:
                logger.warning(f"第 {attempt} 次点击未触发弹窗，重试...")

    def run_one_round(self):
        """执行一轮(9个怪)的逻辑"""
        for i in range(9):
            logger.info(f"\n--- 挑战第 {i+1}/9 个结界 ---")
            
            # 1. 选中
            self.ensure_select_target(i)
            
            # 2. 进攻
            if not self.wait_and_click("attack", timeout=10, desc="进攻按钮"):
                continue

            # 3. 战斗
            if i < 8:
                # === 普通怪 (1-8) ===
                if self.wait_and_click("ready", desc="准备"):
                    self.process_rewards_loop()
            else:
                # === 第9怪 (降级 x 3) ===
                logger.info(">>> 第9关：启动3次降级流程 <<<")
                
                # 3次退出循环
                for retry in range(3):
                    logger.info(f"--- 执行降级 {retry+1}/3 ---")
                    if not self.wait_and_click("back", timeout=20, desc=f"退出({retry+1}/3)"):
                        logger.error("加载超时或未找到返回按钮")
                    
                    self.wait_and_click("confirm", desc="确认")
                    self.wait_and_click("again", timeout=15, desc="再次挑战")
                    
                    logger.info("等待重载...")
                    time.sleep(3.0) 

                # 正式进攻
                logger.info(">>> 降级结束，正式进攻 <<<")
                if self.wait_and_click("ready", timeout=15, desc="正式准备"):
                    self.process_rewards_loop()

            time.sleep(1.0)

    def main_loop(self):
        print("===================================")
        print("   阴阳师结界突破助手 (最终版)   ")
        print("===================================")
        
        # 默认值为 1
        val = input("请输入要执行的轮数 (默认为 1): ").strip()
        if not val:
            total_rounds = 1
        else:
            try:
                total_rounds = int(val)
            except:
                print("输入格式错误，使用默认值 1")
                total_rounds = 1

        current_round = 0
        
        while True:
            current_round += 1
            logger.info(f"\n========================================")
            logger.info(f"      正在开始总第 {current_round} 轮")
            if total_rounds > 0:
                logger.info(f"      目标进度: {current_round} / {total_rounds}")
            logger.info(f"========================================")

            # 执行一轮突破
            self.run_one_round()

            # 判断是否结束
            if total_rounds > 0 and current_round >= total_rounds:
                logger.info("已达到设定轮数，脚本结束。")
                break
            
            # 等待自动刷新
            logger.info("本轮结束，等待游戏自动刷新界面 (8秒)...")
            time.sleep(8.0) # 给足时间让自动刷新动画播放完

if __name__ == "__main__":
    try:
        bot = RealmRaidBot()
        bot.main_loop()
    except KeyboardInterrupt:
        logger.info("用户手动停止脚本")
    except Exception:
        logger.exception("发生未知错误")