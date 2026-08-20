import sys
import win32con
import win32gui
import ctypes
from ctypes import wintypes
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==============================================================================
#  全球统一初始化配置与全局变量
# ==============================================================================
trajectory_x = [0]       # 用于图1空间绘图 及 图2时间轴 (X绝对累加值)
trajectory_y = [0]       # 用于图1空间绘图 及 图2时间轴 (Y绝对累加值，向上为正)
delta_x_list = [0]       # 用于纯X轴单次变化量
delta_y_list = [0]       # 用于纯Y轴单次变化量
timestamps = [0.0]       # 存储相对时间 (单位: 毫秒 ms)
is_recording = False

# 全局文件句柄
log_file = None

# 高精度时钟变量
start_counter = 0
frequency = 0

WM_INPUT = 0x00FF
RIM_TYPEMOUSE = 0
RID_INPUT = 0x10000003

# ==============================================================================
#  Windows SDK 标准结构体声明
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
#  功能核心：设备注册与 Windows 消息回调
# ==============================================================================
def register_raw_input(hwnd):
    """向 Windows 注册原始输入设备（鼠标）"""
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
    print("  2. 按一下【鼠标左键】开始录制（不需要按住不放），在桌面上大幅度晃动。")
    print("  3. 按一下【鼠标右键】停止录制，窗口自动关闭，秒弹可视化高级数据图盘！")

def wnd_proc(hwnd, msg, wparam, lparam):
    """Windows 窗口消息回调函数"""
    global is_recording, trajectory_x, trajectory_y, delta_x_list, delta_y_list, timestamps, start_counter, frequency, log_file
    
    kernel32 = ctypes.windll.kernel32
    
    # 修改1：监听左键按下开始录制
    if msg == win32con.WM_LBUTTONDOWN:
        if not is_recording:  # 只有在未录制状态下才触发，防止中途误点左键重置数据
            is_recording = True
            trajectory_x = [0] 
            trajectory_y = [0]
            delta_x_list = [0]
            delta_y_list = [0]
            timestamps = [0.0]
            
            log_file = open("mouse_log.txt", "w", encoding="utf-8")
            
            freq = ctypes.c_int64()
            kernel32.QueryPerformanceFrequency(ctypes.byref(freq))
            frequency = freq.value
            
            start = ctypes.c_int64()
            kernel32.QueryPerformanceCounter(ctypes.byref(start))
            start_counter = start.value
            
            win32gui.SetCapture(hwnd)
            print("\n====== 正在高频录制中（样式对齐控制台并写入文件中），请快速晃动鼠标 ======")
            
    # 修改2：将原本的 WM_LBUTTONUP 改为监听右键按下 WM_RBUTTONDOWN 停止录制
    elif msg == win32con.WM_RBUTTONDOWN:
        if is_recording:
            is_recording = False
            win32gui.ReleaseCapture()
            
            if log_file:
                log_file.close()
                log_file = None
                
            print(f"\n====== 录制结束！样式数据已成功保存至当前目录下的 [mouse_log.txt] ======")
            print(f"共捕获 {len(trajectory_x)} 个纯净硬件包。正在全力渲染高级分析图盘... ======")
            win32gui.DestroyWindow(hwnd)

    elif msg == WM_INPUT:
        if is_recording:
            current_counter = ctypes.c_int64()
            kernel32.QueryPerformanceCounter(ctypes.byref(current_counter))
            elapsed_ms = ((current_counter.value - start_counter) * 1000.0) / frequency

            user32 = ctypes.windll.user32
            pcbSize = ctypes.c_uint()
            cbSizeHeader = ctypes.c_uint(ctypes.sizeof(RAWINPUTHEADER))
            
            user32.GetRawInputData(ctypes.c_void_p(lparam), RID_INPUT, None, ctypes.byref(pcbSize), cbSizeHeader)
            
            if pcbSize.value > 0:
                raw_input_data = RAWINPUT()
                res = user32.GetRawInputData(ctypes.c_void_p(lparam), RID_INPUT, ctypes.byref(raw_input_data), ctypes.byref(pcbSize), cbSizeHeader)
                
                if res != -1 and raw_input_data.header.dwType == RIM_TYPEMOUSE:
                    raw_x = ctypes.c_long(raw_input_data.mouse.lLastX).value
                    raw_y = ctypes.c_long(raw_input_data.mouse.lLastY).value
                    
                    if raw_x != 0 or raw_y != 0:
                        mapped_delta_x = -raw_x
                        mapped_delta_y = -raw_y
                        
                        new_traj_x = trajectory_x[-1] + mapped_delta_x
                        new_traj_y = trajectory_y[-1] + mapped_delta_y
                        
                        if log_file:
                            log_file.write(f"[{elapsed_ms:7.2f} ms] "
                                           f"Delta -> X: {mapped_delta_x:+5d}, Y: {mapped_delta_y:+5d} | "
                                           f"Trajectory -> X: {new_traj_x:+6d}, Y: {new_traj_y:+6d}\n")
                        
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
#  高级数据分析看盘（Matplotlib 多轴自由切换与无损缩放）
# ==============================================================================

def plot_trajectory_plotly():
    # 1. 创建 1行2列 的精美子图画布
    fig = make_subplots(rows=1, cols=2, subplot_titles=("鼠标轨迹 (Math Coordinates)", "单次位移/时间"))
    
    # --- 图1：空间轨迹 ---
    fig.add_trace(go.Scatter(
        x=trajectory_x, 
        y=trajectory_y, 
        mode='lines+markers',
        name='正常轨迹', 
        line=dict(
            color='rgba(31, 119, 180, 0.4)', 
            width=1                                
        ),
        marker=dict(
            size=2,                                
            color='#00ffcc',
            opacity=0.7,                
            line=dict(width=1, color='#fff') 
        ),
        hoverinfo='text', 
        text=[f"Index: {i}<br>Time: {t:.2f}ms" for i, t in enumerate(timestamps)]
    ), row=1, col=1)
    
    # --- 图2：时间演进（X/Y 轴拆分） ---
    # X轴绝对位置
    fig.add_trace(go.Scatter(
        x=timestamps, 
        y=delta_x_list, 
        mode='lines+markers', 
        name='X轴绝对位置', 
        line=dict(color='rgba(148, 103, 189, 0.7)', width=1), 
        marker=dict(size=2, color="#f326f0")                  
    ), row=1, col=2)
    
    # Y轴绝对位置
    fig.add_trace(go.Scatter(
        x=timestamps, 
        y=delta_y_list, 
        mode='lines+markers', 
        name='Y轴绝对位置', 
        line=dict(color='rgba(227, 119, 194, 0.7)', width=1), 
        marker=dict(size=2, color="#32f232")                  
    ), row=1, col=2)
    
    # 2. 奢华视觉配置
    fig.update_layout(
        template="plotly_dark", 
        title_text="鼠标性能测试 by 张同学讲数码",
        hovermode="closest",
        paper_bgcolor='#1E1E1E',   # 整个画板的背景色（高级深灰）
        plot_bgcolor='#1E1E1E',    # 内部绘图区域的背景色（高级深灰）     
    )
    import os

    # 定义子文件夹
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    # 基础文件名（不含数字后缀）
    base_name = "mouse_trajectory"
    extension = ".html"

    # 生成不重复的文件名
    counter = 0
    while True:
        if counter == 0:
            filename = f"{base_name}{extension}"
        else:
            filename = f"{base_name}_{counter}{extension}"
        
        file_path = os.path.join(output_dir, filename)
        if not os.path.exists(file_path):
            break
        counter += 1

    # 生成并自动打开
    import plotly.offline as pyo
    pyo.plot(fig, filename=file_path, auto_open=True)
    # fig.show()

# ==============================================================================
#  基础底层：Windows 消息泵创建
# ==============================================================================
def create_window():
    wc = win32gui.WNDCLASS()
    wc.lpfnWndProc = wnd_proc
    wc.lpszClassName = "MouseRawInputTracker"
    
    wc.hInstance = win32gui.GetModuleHandle(None)
    
    class_atom = win32gui.RegisterClass(wc)
    hwnd = win32gui.CreateWindow(
        class_atom, "RawInput 鼠标高频高级性能测试", 
        win32con.WS_OVERLAPPEDWINDOW, 
        100, 100, 460, 260, 
        0, 0, wc.hInstance, None
    )
    
    win32gui.ShowWindow(hwnd, win32con.SW_SHOWNORMAL)
    register_raw_input(hwnd)
    win32gui.PumpMessages()

if __name__ == "__main__":
    # 清理掉之前多余导入的未使用的 PyQt 和 matplotlib 以保持代码整洁
    create_window()
    plot_trajectory_plotly()