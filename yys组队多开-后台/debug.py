import subprocess
import os

# === 你的配置 ===
ADB_PATH = r"E:/MuMuPlayer/nx_main/adb.exe"
# 注意：MuMu 12 通常是 16384，MuMu 6/安卓6 通常是 7555
# 如果你多开了模拟器，端口号可能会变（如 16416, 16448 等）
DEVICE_ID = "127.0.0.1:16416" 

def run_cmd(cmd_list):
    print(f"执行命令: {' '.join(cmd_list)}")
    try:
        # capture_output=True 会同时捕获 stdout 和 stderr
        result = subprocess.run(cmd_list, capture_output=True, text=True)
        return result
    except FileNotFoundError:
        print("【致命错误】找不到 adb.exe，请检查路径是否完全正确！")
        return None

def check():
    # 1. 检查 ADB 文件是否存在
    if not os.path.exists(ADB_PATH):
        print(f"❌ 错误：文件不存在 -> {ADB_PATH}")
        return
    print(f"✅ ADB 文件存在。")

    # 2. 尝试连接
    print("-" * 20)
    res_connect = run_cmd([ADB_PATH, "connect", DEVICE_ID])
    print(f"连接结果 (STDOUT): {res_connect.stdout.strip()}")
    print(f"连接结果 (STDERR): {res_connect.stderr.strip()}")

    # 3. 检查设备列表
    print("-" * 20)
    res_devices = run_cmd([ADB_PATH, "devices"])
    print("当前设备列表:")
    print(res_devices.stdout)

    # 4. 关键：检查是否能截图
    print("-" * 20)
    print("尝试获取截图数据大小...")
    # 这里不能用 text=True，因为截图是二进制数据
    proc = subprocess.Popen([ADB_PATH, "-s", DEVICE_ID, "shell", "screencap", "-p"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    
    if stderr:
        print(f"❌ 截图命令报错: {stderr.decode('utf-8', errors='ignore')}")
    
    data_len = len(stdout)
    print(f"截图数据长度: {data_len} bytes")

    if data_len < 100:
        print("❌ 截图失败：数据量过小，说明没获取到图片。")
        if "device offline" in res_devices.stdout:
            print("原因推测：设备处于 offline 离线状态。请重启模拟器或重启ADB。")
        elif DEVICE_ID not in res_devices.stdout:
            print("原因推测：设备未连接。请检查端口号是否正确（Mumu12=16384, Mumu6=7555）。")
    else:
        print("✅ 诊断通过！Python 可以正常获取截图。")

if __name__ == "__main__":
    check()