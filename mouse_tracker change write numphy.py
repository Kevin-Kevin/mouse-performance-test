import sys
import os
import win32con
import win32gui
import ctypes
from ctypes import wintypes
from array import array
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.offline as pyo

# ==============================================================================
#  全局变量
# ==============================================================================
trajectory_x = array('i', [0])
trajectory_y = array('i', [0])
delta_x_list = array('i', [0])
delta_y_list = array('i', [0])
timestamps   = array('d', [0.0])
is_recording = False

start_counter = 0
frequency     = 0

WM_INPUT      = 0x00FF
RIM_TYPEMOUSE = 0
RID_INPUT     = 0x10000003

# ==============================================================================
#  Windows SDK 结构体
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

# ==============================================================================
#  窗口消息回调
# ==============================================================================
def wnd_proc(hwnd, msg, wparam, lparam):
    global is_recording, trajectory_x, trajectory_y, delta_x_list, delta_y_list
    global timestamps, start_counter, frequency

    kernel32 = ctypes.windll.kernel32

    # ---------- 白底黑字 + 中文稳定显示 ----------
    # ---------- 白底黑字 + 中文稳定显示 ----------
    if msg == win32con.WM_PAINT:
        hdc, ps = win32gui.BeginPaint(hwnd)

        # 1. 先把整个客户区刷成白色
        rect = win32gui.GetClientRect(hwnd)
        brush = win32gui.GetStockObject(win32con.WHITE_BRUSH)
        win32gui.FillRect(hdc, rect, brush)

        # 2. 创建字体（用 CreateFontIndirect）
        lf = win32gui.LOGFONT()
        lf.lfHeight = 22
        lf.lfWeight = win32con.FW_NORMAL
        lf.lfCharSet = win32con.DEFAULT_CHARSET
        lf.lfQuality = win32con.CLEARTYPE_QUALITY
        lf.lfFaceName = "Microsoft YaHei"

        font = win32gui.CreateFontIndirect(lf)
        if not font:
            lf.lfFaceName = "SimSun"
            font = win32gui.CreateFontIndirect(lf)

        old_font = win32gui.SelectObject(hdc, font)

        # 3. 设置文字颜色
        win32gui.SetBkMode(hdc, win32con.TRANSPARENT)
        win32gui.SetTextColor(hdc, 0x00000000)  # 黑色

        lines = [
            "【鼠标高频测试 - 使用说明】",
            "",
            "1. 【鼠标左键】点击本窗口空白处，获得焦点开始录制",
            "2. 快速晃动鼠标（画圆 / 来回扫）",
            "3. 单击【鼠标右键】 → 停止录制",
            "   （自动保存日志并弹出图表）",
            "",
        ]

        if is_recording:
            status = "● 正在高频录制中...（请快速手动大幅度画圆晃动鼠标）"
            win32gui.SetTextColor(hdc, 0x00008000)  # 深绿色
        else:
            status = "○ 等待开始（按左键开始录制）"
            win32gui.SetTextColor(hdc, 0x00000000)

        lines.append(status)

        # 逐行用 DrawText 绘制
        y = 25
        for line in lines:
            # 定义这一行的矩形区域
            text_rect = (30, y, 500, y + 30)
            win32gui.DrawText(
                hdc,
                line,
                -1,
                text_rect,
                win32con.DT_LEFT | win32con.DT_SINGLELINE | win32con.DT_VCENTER
            )
            y += 30

        # 清理
        win32gui.SelectObject(hdc, old_font)
        if font:
            win32gui.DeleteObject(font)
        win32gui.EndPaint(hwnd, ps)
        return 0

    # 左键按下 → 开始录制
    if msg == win32con.WM_LBUTTONDOWN:
        if not is_recording:
            is_recording = True
            trajectory_x = array('i', [0])
            trajectory_y = array('i', [0])
            delta_x_list = array('i', [0])
            delta_y_list = array('i', [0])
            timestamps   = array('d', [0.0])

            freq = ctypes.c_int64()
            kernel32.QueryPerformanceFrequency(ctypes.byref(freq))
            frequency = freq.value

            start = ctypes.c_int64()
            kernel32.QueryPerformanceCounter(ctypes.byref(start))
            start_counter = start.value

            win32gui.SetCapture(hwnd)
            print("\n====== 正在高频录制中（array 纯内存缓冲），请快速晃动鼠标 ======")
            win32gui.InvalidateRect(hwnd, None, True)   # 刷新窗口显示状态

    # 右键按下 → 停止录制
    elif msg == win32con.WM_RBUTTONDOWN:
        if is_recording:
            is_recording = False
            win32gui.ReleaseCapture()
            print(f"\n====== 录制结束！共捕获 {len(trajectory_x)} 个包 ======")
            print("正在保存日志并渲染图表...")
            win32gui.InvalidateRect(hwnd, None, True)
            win32gui.DestroyWindow(hwnd)

    # 处理 Raw Input
    elif msg == WM_INPUT:
        if is_recording:
            current_counter = ctypes.c_int64()
            kernel32.QueryPerformanceCounter(ctypes.byref(current_counter))
            elapsed_ms = ((current_counter.value - start_counter) * 1000.0) / frequency

            user32 = ctypes.windll.user32
            pcbSize = ctypes.c_uint()
            cbSizeHeader = ctypes.c_uint(ctypes.sizeof(RAWINPUTHEADER))

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
                        mapped_delta_x = -raw_x
                        mapped_delta_y = -raw_y

                        new_traj_x = trajectory_x[-1] + mapped_delta_x
                        new_traj_y = trajectory_y[-1] + mapped_delta_y

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
#  保存日志
# ==============================================================================
def save_log_file():
    if len(timestamps) <= 10:
        print("有效数据太少，无法计算回报率。")
        return None

    n = len(timestamps)
    start_idx = int(n * 0.20)
    end_idx   = int(n * 0.80)

    if end_idx <= start_idx:
        start_idx = 0
        end_idx = n - 1

    mid_packets = end_idx - start_idx
    mid_time_sec = (timestamps[end_idx] - timestamps[start_idx]) / 1000.0

    actual_rate = mid_packets / mid_time_sec if mid_time_sec > 0 else 0
    total_packets = n - 1
    total_time_sec = timestamps[-1] / 1000.0
    overall_rate = total_packets / total_time_sec if total_time_sec > 0 else 0

    print(f"总录制时长          : {total_time_sec:.3f} 秒")
    print(f"总有效报告包数      : {total_packets}")
    print(f"整体平均回报率      : {overall_rate:.1f} Hz（含开头结尾空闲）")
    print("-" * 50)
    print(f"中间画圆段时长      : {mid_time_sec:.3f} 秒")
    print(f"中间画圆段包数      : {mid_packets}")
    print(f"【推荐】实际回报率  : {actual_rate:.1f} Hz  ← 请重点看这个")
    print("-" * 50)

    with open("mouse_log.txt", "w", encoding="utf-8") as f:
        for i in range(n):
            f.write(f"[{timestamps[i]:7.2f} ms] "
                    f"Delta -> X: {delta_x_list[i]:+5d}, Y: {delta_y_list[i]:+5d} | "
                    f"Trajectory -> X: {trajectory_x[i]:+6d}, Y: {trajectory_y[i]:+6d}\n")
    print("日志已保存至当前目录：mouse_log.txt")

    return {
        "total_time_sec": total_time_sec,
        "total_packets": total_packets,
        "overall_rate": overall_rate,
        "mid_time_sec": mid_time_sec,
        "mid_packets": mid_packets,
        "actual_rate": actual_rate,
    }

# ==============================================================================
#  Plotly 可视化
# ==============================================================================
def plot_trajectory_plotly(results=None):
    if len(timestamps) <= 1:
        print("数据不足，无法绘图。")
        return

    traj_x = list(trajectory_x)
    traj_y = list(trajectory_y)
    deltas_x = list(delta_x_list)
    deltas_y = list(delta_y_list)
    times = list(timestamps)

    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=("鼠标轨迹 (Math Coordinates)", "单次位移/时间"))

    fig.add_trace(go.Scatter(
        x=traj_x, y=traj_y,
        mode='lines+markers', name='轨迹',
        line=dict(color='rgba(31, 119, 180, 0.4)', width=1),
        marker=dict(size=2, color='#00ffcc', opacity=0.7,
                    line=dict(width=1, color='#fff')),
        hoverinfo='text',
        text=[f"Index: {i}<br>Time: {t:.2f}ms" for i, t in enumerate(times)]
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=times, y=deltas_x,
        mode='lines+markers', name='ΔX',
        line=dict(color='rgba(148, 103, 189, 0.7)', width=1),
        marker=dict(size=2, color="#f326f0")
    ), row=1, col=2)

    fig.add_trace(go.Scatter(
        x=times, y=deltas_y,
        mode='lines+markers', name='ΔY',
        line=dict(color='rgba(227, 119, 194, 0.7)', width=1),
        marker=dict(size=2, color="#32f232")
    ), row=1, col=2)

    # 把回报率结果汇总到网页标题里
    if results:
        summary_lines = [
            f"总录制时长：{results['total_time_sec']:.3f} 秒",
            f"总有效报告包数：{results['total_packets']}",
            f"整体平均回报率：{results['overall_rate']:.1f} Hz",
            f"中间画圆段时长：{results['mid_time_sec']:.3f} 秒",
            f"中间画圆段包数：{results['mid_packets']}",
            f"<b><span style='color:#00e676'>实际回报率（推荐）：{results['actual_rate']:.1f} Hz</span></b>",
        ]
        summary_text = "  |  ".join(summary_lines)
        title_text = (
            "鼠标性能测试 by 张同学讲数码（array 优化版）"
            f" <span style='font-size:14px'>  |  {summary_text}</span>"
        )
    else:
        title_text = (
            "鼠标性能测试 by 张同学讲数码（array 优化版）"
            " <span style='font-size:14px;color:#ff6b6b'>  |  回报率没有结果（有效数据太少）</span>"
        )

    fig.update_layout(
        template="plotly_dark",
        title_text=title_text,
        hovermode="closest",
        paper_bgcolor='#1E1E1E',
        plot_bgcolor='#1E1E1E',
    )

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
#  创建窗口
# ==============================================================================
def create_window():
    wc = win32gui.WNDCLASS()
    wc.lpfnWndProc = wnd_proc
    wc.lpszClassName = "MouseRawInputTracker"
    wc.hInstance = win32gui.GetModuleHandle(None)
    # 白色背景
    wc.hbrBackground = win32gui.GetStockObject(win32con.WHITE_BRUSH)

    class_atom = win32gui.RegisterClass(wc)
    hwnd = win32gui.CreateWindow(
        class_atom,
        "RawInput 鼠标高频高级性能测试（array 优化版）",
        win32con.WS_OVERLAPPEDWINDOW,
        100, 100, 520, 340,          # 窗口稍微加大一点
        0, 0, wc.hInstance, None
    )

    win32gui.ShowWindow(hwnd, win32con.SW_SHOWNORMAL)
    register_raw_input(hwnd)
    win32gui.PumpMessages()

# ==============================================================================
#  主入口
# ==============================================================================
if __name__ == "__main__":
    create_window()
    results = save_log_file()
    plot_trajectory_plotly(results)