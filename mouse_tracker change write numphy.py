import sys
import os
import win32con
import win32gui
import ctypes
from ctypes import wintypes
from array import array
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
import webbrowser
from pathlib import Path

def get_language():
    env_lang = os.environ.get("MOUSE_TESTER_LANG", "").strip().lower()
    if env_lang.startswith("zh"):
        return "zh"
    if env_lang.startswith(("en", "english")):
        return "en"

    try:
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        if lang_id & 0x03FF == 0x04:
            return "zh"
    except Exception:
        pass
    return "en"

LANG = get_language()

TEXT = {
    "zh": {
        "raw_registration_failed": "Raw Input 注册失败！",
        "raw_registered": "Raw Input 鼠标注册成功。",
        "instructions_title": "【鼠标高频测试 - 使用说明】",
        "instruction_1": "1. 【鼠标左键】点击本窗口空白处，获得焦点开始录制",
        "instruction_2": "2. 快速晃动鼠标（画圆 / 来回扫）",
        "instruction_3": "3. 单击【鼠标右键】 → 停止录制",
        "instruction_4": "   （自动保存日志并弹出图表）",
        "recording": "● 正在高频录制中...（请快速手动大幅度画圆晃动鼠标）",
        "waiting": "○ 等待开始（按左键开始录制）",
        "recording_console": "\n====== 正在高频录制中（array 纯内存缓冲），请快速晃动鼠标 ======",
        "recording_stopped": "录制结束！共捕获",
        "saving": "正在保存日志并渲染图表...",
        "not_enough_rate": "有效数据太少，无法计算回报率。",
        "total_time": "总录制时长",
        "valid_packets": "总有效报告包数",
        "overall_rate": "整体平均回报率",
        "idle_note": "（含开头结尾空闲）",
        "middle_time": "中间画圆段时长",
        "middle_packets": "中间画圆段包数",
        "recommended_rate": "【推荐】实际回报率",
        "look_here": "← 请重点看这个",
        "log_saved": "日志已保存至当前目录：mouse_log.txt",
        "not_enough_chart": "数据不足，无法绘图。",
        "trajectory_title": "鼠标轨迹 (Math Coordinates)",
        "displacement_title": "单次位移/时间",
        "trajectory": "轨迹",
        "total_time_summary": "总录制时长",
        "valid_packets_summary": "总有效报告包数",
        "overall_rate_summary": "整体平均回报率",
        "middle_time_summary": "中间画圆段时长",
        "middle_packets_summary": "中间画圆段包数",
        "recommended_summary": "实际回报率（推荐）",
        "chart_title": "鼠标性能测试 by 张同学讲数码",
        "no_rate": "回报率没有结果（有效数据太少）",
        "seconds": "秒",
        "chart_saved": "图表已保存并打开",
        "window_title": "RawInput 鼠标高频高级性能测试",
        "font": "Microsoft YaHei",
        "fallback_font": "SimSun",
    },
    "en": {
        "raw_registration_failed": "Raw Input registration failed!",
        "raw_registered": "Raw Input mouse registered successfully.",
        "instructions_title": "[High-Frequency Mouse Test - Instructions]",
        "instruction_1": "1. Left-click in this window to start recording",
        "instruction_2": "2. Move the mouse quickly (draw circles or sweep back and forth)",
        "instruction_3": "3. Right-click to stop recording",
        "instruction_4": "   (The log is saved and the chart opens automatically)",
        "recording": "● Recording high-frequency input... Move the mouse quickly and broadly",
        "waiting": "○ Waiting to start (left-click to begin recording)",
        "recording_console": "\n====== Recording high-frequency input (array memory buffer). Move the mouse quickly ======",
        "recording_stopped": "Recording stopped! Captured",
        "saving": "Saving the log and rendering the chart...",
        "not_enough_rate": "Not enough valid data to calculate the report rate.",
        "total_time": "Total recording time",
        "valid_packets": "Valid report packets",
        "overall_rate": "Overall report rate",
        "idle_note": "(including idle periods at the beginning and end)",
        "middle_time": "Middle circle segment time",
        "middle_packets": "Middle circle segment packets",
        "recommended_rate": "[Recommended] Actual report rate",
        "look_here": "",
        "log_saved": "Log saved to the current directory: mouse_log.txt",
        "not_enough_chart": "Not enough data to draw a chart.",
        "trajectory_title": "Mouse Trajectory (Math Coordinates)",
        "displacement_title": "Per-Movement Displacement / Time",
        "trajectory": "Trajectory",
        "total_time_summary": "Total recording time",
        "valid_packets_summary": "Valid report packets",
        "overall_rate_summary": "Overall report rate",
        "middle_time_summary": "Middle circle segment time",
        "middle_packets_summary": "Middle circle segment packets",
        "recommended_summary": "Recommended report rate",
        "chart_title": "Mouse Performance Test by 张同学讲数码",
        "no_rate": "No report-rate result (not enough valid data)",
        "seconds": "sec",
        "chart_saved": "Chart saved and opened",
        "window_title": "Raw Input High-Frequency Mouse Performance Test",
        "font": "Segoe UI",
        "fallback_font": "Arial",
    },
}

T = TEXT[LANG]

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
        print(T["raw_registration_failed"])
        sys.exit(1)

    print(T["raw_registered"])

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
        lf.lfFaceName = T["font"]

        font = win32gui.CreateFontIndirect(lf)
        if not font:
            lf.lfFaceName = T["fallback_font"]
            font = win32gui.CreateFontIndirect(lf)

        old_font = win32gui.SelectObject(hdc, font)

        # 3. 设置文字颜色
        win32gui.SetBkMode(hdc, win32con.TRANSPARENT)
        win32gui.SetTextColor(hdc, 0x00000000)  # 黑色

        lines = [
            T["instructions_title"],
            "",
            T["instruction_1"],
            T["instruction_2"],
            T["instruction_3"],
            T["instruction_4"],
            "",
        ]

        if is_recording:
            status = T["recording"]
            win32gui.SetTextColor(hdc, 0x00008000)  # 深绿色
        else:
            status = T["waiting"]
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
            print(T["recording_console"])
            win32gui.InvalidateRect(hwnd, None, True)   # 刷新窗口显示状态

    # 右键按下 → 停止录制
    elif msg == win32con.WM_RBUTTONDOWN:
        if is_recording:
            is_recording = False
            win32gui.ReleaseCapture()
            print(f"\n====== {T['recording_stopped']} {len(trajectory_x)} {'包' if LANG == 'zh' else 'packets'} ======")
            print(T["saving"])
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
        print(T["not_enough_rate"])
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

    print(f"{T['total_time']:20} : {total_time_sec:.3f} {T['seconds']}")
    print(f"{T['valid_packets']:20} : {total_packets}")
    print(f"{T['overall_rate']:20} : {overall_rate:.1f} Hz {T['idle_note']}")
    print("-" * 50)
    print(f"{T['middle_time']:25} : {mid_time_sec:.3f} {T['seconds']}")
    print(f"{T['middle_packets']:25} : {mid_packets}")
    print(f"{T['recommended_rate']:25} : {actual_rate:.1f} Hz {T['look_here']}")
    print("-" * 50)

    with open("mouse_log.txt", "w", encoding="utf-8") as f:
        for i in range(n):
            f.write(f"[{timestamps[i]:7.2f} ms] "
                    f"Delta -> X: {delta_x_list[i]:+5d}, Y: {delta_y_list[i]:+5d} | "
                    f"Trajectory -> X: {trajectory_x[i]:+6d}, Y: {trajectory_y[i]:+6d}\n")
    print(T["log_saved"])

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
        print(T["not_enough_chart"])
        return

    traj_x = list(trajectory_x)
    traj_y = list(trajectory_y)
    deltas_x = list(delta_x_list)
    deltas_y = list(delta_y_list)
    times = list(timestamps)

    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=(T["trajectory_title"], T["displacement_title"]))

    fig.add_trace(go.Scatter(
        x=traj_x, y=traj_y,
        mode='lines+markers', name=T["trajectory"],
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
            f"{T['total_time_summary']}: {results['total_time_sec']:.3f} {T['seconds']}",
            f"{T['valid_packets_summary']}: {results['total_packets']}",
            f"{T['overall_rate_summary']}: {results['overall_rate']:.1f} Hz",
            f"{T['middle_time_summary']}: {results['mid_time_sec']:.3f} {T['seconds']}",
            f"{T['middle_packets_summary']}: {results['mid_packets']}",
            f"<b><span style='color:#00e676'>{T['recommended_summary']}: {results['actual_rate']:.1f} Hz</span></b>",
        ]
        summary_text = "  |  ".join(summary_lines)
        title_text = (
            T["chart_title"] +
            f" <span style='font-size:14px'>  |  {summary_text}</span>"
        )
    else:
        title_text = (
            T["chart_title"] +
            f" <span style='font-size:14px;color:#ff6b6b'>  |  {T['no_rate']}</span>"
        )

    fig.update_layout(
        template="plotly_dark",
        title=None,
        margin=dict(t=40, l=40, r=40, b=40),
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

    html = pio.to_html(
        fig,
        full_html=True,
        include_plotlyjs=True,
        config={"responsive": True},
    )
    title_style = (
        "<style>"
        "body{margin:0;background:#1E1E1E;color:#f2f2f2;font-family:Arial,sans-serif}"
        "#report-title{box-sizing:border-box;width:100%;padding:16px 40px 8px;"
        "text-align:center;font-size:24px;line-height:1.45;overflow-wrap:anywhere}"
        "</style>"
    )
    title_html = f'<div id="report-title">{title_text}</div>'
    html = html.replace("</head>", f"{title_style}</head>", 1)
    html = html.replace("<body>", f"<body>{title_html}", 1)
    with open(file_path, "w", encoding="utf-8") as html_file:
        html_file.write(html)
    webbrowser.open(Path(file_path).resolve().as_uri())
    print(f"{T['chart_saved']}: {file_path}")

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
        T["window_title"],
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