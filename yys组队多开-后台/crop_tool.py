import cv2, subprocess, os, time

# adb 和设备
ADB = r"E:\MuMuPlayer\nx_main\adb"
DEVICE = "127.0.0.1:16384"

def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stderr:
        print("ADB ERROR:", result.stderr.strip())
    return result.stdout

def check_device_online():
    run(f"{ADB} kill-server")
    time.sleep(0.2)
    run(f"{ADB} connect {DEVICE}")
    out = run(f"{ADB} devices")
    if DEVICE not in out:
        print("❌ 模拟器未连接，请先启动模拟器")
        return False
    return True

def capture_to_local(local_path="img/debug_cap.png"):
    if not check_device_online():
        return None
    os.makedirs("img", exist_ok=True)
    run(f"{ADB} -s {DEVICE} shell screencap -p /sdcard/debug_cap.png")
    time.sleep(0.2)
    run(f"{ADB} -s {DEVICE} pull /sdcard/debug_cap.png {local_path}")
    time.sleep(0.2)
    if not os.path.exists(local_path):
        print("❌ 截图未拉取成功")
        return None
    return local_path


if __name__ == "__main__":
    p = capture_to_local()

    if not p or not os.path.exists(p):
        print("截图失败，请先确保模拟器和 adb 正常")
        exit()

    img = cv2.imread(p)

    if img is None:
        print("❌ 读取图片失败")
        exit()

    # --- 新增：计算缩放比例 ---
    screen_max_height = 800  # 设置你希望显示窗口的最大高度（根据你的屏幕调整）
    h, w = img.shape[:2]
    scale = 1.0

    if h > screen_max_height:
        scale = screen_max_height / h
        print(f"检测到图片过大({w}x{h})，已自动缩小至 {int(scale*100)}% 进行显示")

    # 缩放图片用于显示
    display_img = cv2.resize(img, (int(w * scale), int(h * scale)))

    print("截图成功！可以开始裁剪模板。")

    while True:
        print("请用鼠标框选模板区域，选好后按 Enter / Space 确认；按 c 取消；按 q 退出。")

        # 在缩放后的图上选区
        win_name = "select ROI (Scaled)"
        r = cv2.selectROI(win_name, display_img, showCrosshair=True, fromCenter=False)
        x, y, w_roi, h_roi = r
        cv2.destroyWindow(win_name)

        if w_roi == 0 or h_roi == 0:
            print("未选择区域，退出。")
            break

        # --- 关键点：将选区坐标映射回原图 ---
        real_x = int(x / scale)
        real_y = int(y / scale)
        real_w = int(w_roi / scale)
        real_h = int(h_roi / scale)

        name = input("输入要保存的模板文件名（例如 xuanshang.png）： ").strip()
        if not name:
            print("文件名不能为空，取消保存")
            continue

        if not name.endswith(".png"):
            name += ".png"

        save_path = os.path.join("img", name)
        
        # 从原始高分辨率图中裁剪
        crop = img[real_y:real_y + real_h, real_x:real_x + real_w]
        
        cv2.imwrite(save_path, crop)
        print(f"已保存模板：{save_path}")
        print(f"原图尺寸: {real_w}x{real_h} | 显示尺寸: {w_roi}x{h_roi}")

        again = input("是否继续裁剪新的模板？(y/n) ").lower()
        if again != 'y':
            break

    print("结束。")