import sys
import os
import win32con
import win32gui
import ctypes
from ctypes import wintypes
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.offline as pyo

# ==============================================================================
#  全局变量（只保留必要的）
# ==============================================================================
trajectory_x = [0]
trajectory_y = [0]
delta_x_list = [0]
delta_y_list = [0]
timestamps   = [0.0]
is_recording = False

start_counter = 0
frequency     = 0

WM_INPUT     = 0x00FF
RIM_TYPEMOUSE = 0
RID_INPUT    = 0x10000003

# ==============================================================================
#  Windows SDK 结构体声明（保持不变）
# ==============================================================================
class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM)
    ]

class BUTTONSSTR(ctypes.Structure):
    _fields_ = [
        ("usButtonFlags", wintypes.USHORT),
        ("usButtonData", wintypes.USHORT)
    ]

class RAWMOUSE_UNION(ctypes.Union):
    _fields_ = [
        ("ulButtons", wintypes.ULONG),
        ("buttons", BUTTONSSTR)
    ]

class RAWMOUSE(ctypes.Structure):
    _fields_ = [
        ("usFlags", wintypes.USHORT),
        ("ulRawButtons", wintypes.ULONG),
        ("u", RAWMOUSE_UNION),
        ("lLastX", wintypes.LONG),
        ("lLastY", wintypes.LONG),
        ("ulExtraInformation", wintypes.ULONG)
    ]

class RAWINPUT(ctypes.Structure):
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("mouse", RAWMOUSE)
    ]

# ==============================================================================
#  注册 Raw Input
# ==============================================================================
def register_raw_input(hwnd):
    RIDEV_INPUTSINK = 0x00000100

    class RAWINPUTDEVICE(ctypes.Structure):
        _fields_ = [("usUsagePage", wintypes.USHORT),
                    ("usUsage", wintypes.USHORT),
                    ("dwFlags", wintypes.DWORD),
                    ("hwndTarget", wintypes.HWND)]

    user32 = ctypes.windll.user32
    device = RAWINPUTDEVICE(1, 2, RIDEV_INPUTSINK, hwnd)

    if not user32.RegisterRawInputDevices(ctypes.byref(device), 1, ctypes.sizeof(device)):
        print("Raw Input 注册失败！")
        sys.exit(1)

    print("Raw Input 鼠标注册成功。")
    print("【使用说明】:")
    print("  1. 点击弹出的空白小窗口将其激活。")
    print("  2. 按一下【鼠标左键】开始录制（不需要按住）。")
    print("  3. 按一下【鼠标右键】停止录制，自动保存日志并弹出图表。")

# ==============================================================================
#  窗口消息回调（核心优化：录制时只写内存）
# ==============================================================================
def wnd_proc(hwnd, msg, wparam, lparam):
    global is_recording, trajectory_x, trajectory_y, delta_x_list, delta_y_list
    global timestamps, start_counter, frequency

    kernel32 = ctypes.windll.kernel32

    # 左键按下 → 开始录制
    if msg == win32con.WM_LBUTTONDOWN:
        if not is_recording:
            is_recording = True
            trajectory_x = [0]
            trajectory_y = [0]
            delta_x_list = [0]
            delta_y_list = [0]
            timestamps   = [0.0]

            # 高精度计时初始化
            freq = ctypes.c_int64()
            kernel32.QueryPerformanceFrequency(ctypes.byref(freq))
            frequency = freq.value

            start = ctypes.c_int64()
            kernel32.QueryPerformanceCounter(ctypes.byref(start))
            start_counter = start.value

            win32gui.SetCapture(hwnd)
            print("\n====== 正在高频录制中（纯内存缓冲），请快速晃动鼠标 ======")

    # 右键按下 → 停止录制
    elif msg == win32con.WM_RBUTTONDOWN:
        if is_recording:
            is_recording = False
            win32gui.ReleaseCapture()
            print(f"\n====== 录制结束！共捕获 {len(trajectory_x)} 个包 ======")
            print("正在保存日志并渲染图表...")
            win32gui.DestroyWindow(hwnd)

    # 处理 Raw Input
    elif msg == WM_INPUT:
        if is_recording:
            # 高精度时间戳
            current_counter = ctypes.c_int64()
            kernel32.QueryPerformanceCounter(ctypes.byref(current_counter))
            elapsed_ms = ((current_counter.value - start_counter) * 1000.0) / frequency

            user32 = ctypes.windll.user32
            pcbSize = ctypes.c_uint()
            cbSizeHeader = ctypes.c_uint(ctypes.sizeof(RAWINPUTHEADER))

            # 先获取大小
            user32.GetRawInputData(ctypes.c_void_p(lparam), RID_INPUT, None,
                                   ctypes.byref(pcbSize), cbSizeHeader)

            if pcbSize.value > 0:
                raw_input_data = RAWINPUT()
                res = user32.GetRawInputData(ctypes.c_void_p(lparam), RID_INPUT,
                                             ctypes.byref(raw_input_data),
                                             ctypes.byref(pcbSize), cbSizeHeader)

                if res != -1 and raw_input_data.header.dwType == RIM_TYPEMOUSE:
                    raw_x = ctypes.c_long(raw_input_data.mouse.lLastX).value
                    raw_y = ctypes.c_long(raw_input_data.mouse.lLastY).value

                    if raw_x != 0 or raw_y != 0:
                        # 这里保留了原作者的翻转，如方向不对可去掉负号
                        mapped_delta_x = -raw_x
                        mapped_delta_y = -raw_y

                        new_traj_x = trajectory_x[-1] + mapped_delta_x
                        new_traj_y = trajectory_y[-1] + mapped_delta_y

                        # 只写内存，不做任何 I/O
                        trajectory_x.append(new_traj_x)
                        trajectory_y.append(new_traj_y)
                        delta_x_list.append(mapped_delta_x)
                        delta_y_list.append(mapped_delta_y)
                        timestamps.append(elapsed_ms)

    elif msg == win32con.WM_DESTROY:
        win32gui.PostQuitMessage(0)
        return 0

    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

# ==============================================================================
#  一次性批量写日志（录制结束后调用）
# ==============================================================================
def save_log_file():
    if len(timestamps) <= 1:
        print("没有有效数据，跳过日志保存。")
        return

    with open("mouse_log.txt", "w", encoding="utf-8") as f:
        for i in range(len(timestamps)):
            f.write(f"[{timestamps[i]:7.2f} ms] "
                    f"Delta -> X: {delta_x_list[i]:+5d}, Y: {delta_y_list[i]:+5d} | "
                    f"Trajectory -> X: {trajectory_x[i]:+6d}, Y: {trajectory_y[i]:+6d}\n")
    print("日志已保存至当前目录：mouse_log.txt")

# ==============================================================================
#  Plotly 可视化（保持原风格，略作整理）
# ==============================================================================
def plot_trajectory_plotly():
    if len(timestamps) <= 1:
        print("数据不足，无法绘图。")
        return

    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=("鼠标轨迹 (Math Coordinates)", "单次位移/时间"))

    # 图1：空间轨迹
    fig.add_trace(go.Scatter(
        x=trajectory_x,
        y=trajectory_y,
        mode='lines+markers',
        name='轨迹',
        line=dict(color='rgba(31, 119, 180, 0.4)', width=1),
        marker=dict(size=2, color='#00ffcc', opacity=0.7,
                    line=dict(width=1, color='#fff')),
        hoverinfo='text',
        text=[f"Index: {i}<br>Time: {t:.2f}ms" for i, t in enumerate(timestamps)]
    ), row=1, col=1)

    # 图2：X/Y 单次位移随时间
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=delta_x_list,
        mode='lines+markers',
        name='ΔX',
        line=dict(color='rgba(148, 103, 189, 0.7)', width=1),
        marker=dict(size=2, color="#f326f0")
    ), row=1, col=2)

    fig.add_trace(go.Scatter(
        x=timestamps,
        y=delta_y_list,
        mode='lines+markers',
        name='ΔY',
        line=dict(color='rgba(227, 119, 194, 0.7)', width=1),
        marker=dict(size=2, color="#32f232")
    ), row=1, col=2)

    fig.update_layout(
        template="plotly_dark",
        title_text="鼠标性能测试 by 张同学讲数码（优化版）",
        hovermode="closest",
        paper_bgcolor='#1E1E1E',
        plot_bgcolor='#1E1E1E',
    )

    # 自动生成不重复的文件名
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    base_name = "mouse_trajectory"
    counter = 0
    while True:
        filename = f"{base_name}{'' if counter == 0 else f'_{counter}'}.html"
        file_path = os.path.join(output_dir, filename)
        if not os.path.exists(file_path):
            break
        counter += 1

    pyo.plot(fig, filename=file_path, auto_open=True)
    print(f"图表已保存并打开：{file_path}")

# ==============================================================================
#  创建窗口 + 消息循环
# ==============================================================================
def create_window():
    wc = win32gui.WNDCLASS()
    wc.lpfnWndProc = wnd_proc
    wc.lpszClassName = "MouseRawInputTracker"
    wc.hInstance = win32gui.GetModuleHandle(None)

    class_atom = win32gui.RegisterClass(wc)
    hwnd = win32gui.CreateWindow(
        class_atom, "RawInput 鼠标高频高级性能测试（优化版）",
        win32con.WS_OVERLAPPEDWINDOW,
        100, 100, 460, 260,
        0, 0, wc.hInstance, None
    )

    win32gui.ShowWindow(hwnd, win32con.SW_SHOWNORMAL)
    register_raw_input(hwnd)
    win32gui.PumpMessages()

# ==============================================================================
#  主入口
# ==============================================================================
if __name__ == "__main__":
    create_window()          # 阻塞直到右键停止并销毁窗口
    save_log_file()          # 一次性写日志
    plot_trajectory_plotly() # 再画图