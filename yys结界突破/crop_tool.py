import cv2, subprocess, os, time

# adb 和设备
ADB = r"E:\MuMuPlayer\nx_main\adb"
DEVICE = "127.0.0.1:16416"

def run(cmd):
    # 打印错误信息，确保问题可以排查
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stderr:
        print("ADB ERROR:", result.stderr.strip())
    return result.stdout

def check_device_online():
    """确保设备已连接，否则主动连接"""
    run(f"{ADB} kill-server")
    time.sleep(0.2)
    run(f"{ADB} connect {DEVICE}")

    out = run(f"{ADB} devices")
    if DEVICE not in out:
        print("❌ 模拟器未连接，请先启动模拟器")
        return False

    return True

def capture_to_local(local_path="img/debug_cap.png"):
    """截图并保存到本地"""
    if not check_device_online():
        return None

    os.makedirs("img", exist_ok=True)

    # 1. 模拟器截图
    run(f"{ADB} -s {DEVICE} shell screencap -p /sdcard/debug_cap.png")
    time.sleep(0.2)

    # 2. 拉取文件
    run(f"{ADB} -s {DEVICE} pull /sdcard/debug_cap.png {local_path}")

    # 3. 等 adb 保存完成
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
        print("❌ 读取图片失败，你的模拟器可能截图黑屏或 adb 拉取失败")
        exit()

    print("截图成功！可以开始裁剪模板。")

    while True:
        print("请用鼠标框选模板区域，选好后按 Enter / Space 确认；按 c 取消；按 q 退出。")

        r = cv2.selectROI("select ROI", img, showCrosshair=True, fromCenter=False)
        x, y, w, h = r
        cv2.destroyWindow("select ROI")

        if w == 0 or h == 0:
            print("未选择区域，退出。")
            break

        name = input("输入要保存的模板文件名（例如 xuanshang.png）： ").strip()
        if not name:
            print("文件名不能为空，取消保存")
            continue

        save_path = os.path.join("img", name)
        crop = img[y:y + h, x:x + w]
        cv2.imwrite(save_path, crop)
        print(f"已保存模板：{save_path}  (尺寸: {w}x{h})")

        again = input("是否继续裁剪新的模板？(y/n) ").lower()
        if again != 'y':
            break

    print("结束。")
