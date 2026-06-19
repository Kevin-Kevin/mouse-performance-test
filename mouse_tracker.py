import sys
import win32con
import win32gui
import matplotlib.pyplot as plt
import ctypes
from ctypes import wintypes

# ==============================================================================
#  全球统一初始化配置与全局变量
# ==============================================================================
trajectory_x = [0]       # 用于图1空间绘图 (X累加)
trajectory_y = [0]       # 用于图1空间绘图 (Y累加，向上为正)
delta_x_list = [0]       # 用于图2时间轴 (纯X轴单次变化量，右移为正，左移为负)
delta_y_list = [0]       # 用于图2时间轴 (纯Y轴单次变化量，上移为正，下移为负)
timestamps = [0.0]       # 存储相对时间 (单位: 毫秒 ms)
is_recording = False

# 高精度时钟变量
start_counter = 0
frequency = 0

WM_INPUT = 0x00FF
RIM_TYPEMOUSE = 0
RID_INPUT = 0x10000003

# ==============================================================================
#  Windows SDK 标准结构体声明（严格处理 32/64 位对齐，防止无符号解析 Bug）
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
        # 🚨 核心关键：必须声明为 LONG (有符号32位)，确保负数位移正常
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
    print("  2. 按住【鼠标左键】不放，在桌面上大幅度晃动（控制台将实时打印带正负号的纯净位移）。")
    print("  3. 松开【鼠标左键】，窗口自动关闭，秒弹可视化高级数据图盘！")

def wnd_proc(hwnd, msg, wparam, lparam):
    """Windows 窗口消息回调函数"""
    global is_recording, trajectory_x, trajectory_y, delta_x_list, delta_y_list, timestamps, start_counter, frequency
    
    kernel32 = ctypes.windll.kernel32
    
    if msg == win32con.WM_LBUTTONDOWN:
        is_recording = True
        trajectory_x = [0] 
        trajectory_y = [0]
        delta_x_list = [0]
        delta_y_list = [0]
        timestamps = [0.0]
        
        # 初始化高精度硬件级微秒时钟
        freq = ctypes.c_int64()
        kernel32.QueryPerformanceFrequency(ctypes.byref(freq))
        frequency = freq.value
        
        start = ctypes.c_int64()
        kernel32.QueryPerformanceCounter(ctypes.byref(start))
        start_counter = start.value
        
        # 强制锁死鼠标捕获，防止甩出窗口边界丢失松开事件
        win32gui.SetCapture(hwnd)
        print("\n====== 正在高频录制中，请快速晃动鼠标 ======")
        
    elif msg == win32con.WM_LBUTTONUP:
        if is_recording:
            is_recording = False
            win32gui.ReleaseCapture()
            print(f"\n====== 录制结束，共成功捕获 {len(trajectory_x)} 个纯净硬件包。正在全力渲染高级分析图盘... ======")
            win32gui.DestroyWindow(hwnd)

    elif msg == WM_INPUT:
        if is_recording:
            # 瞬间捕获当前包到达的时间戳
            current_counter = ctypes.c_int64()
            kernel32.QueryPerformanceCounter(ctypes.byref(current_counter))
            elapsed_ms = ((current_counter.value - start_counter) * 1000.0) / frequency

            user32 = ctypes.windll.user32
            pcbSize = ctypes.c_uint()
            cbSizeHeader = ctypes.c_uint(ctypes.sizeof(RAWINPUTHEADER))
            
            # 两步法安全安全提取 RawInput 数据
            user32.GetRawInputData(ctypes.c_void_p(lparam), RID_INPUT, None, ctypes.byref(pcbSize), cbSizeHeader)
            
            if pcbSize.value > 0:
                raw_input_data = RAWINPUT()
                res = user32.GetRawInputData(ctypes.c_void_p(lparam), RID_INPUT, ctypes.byref(raw_input_data), ctypes.byref(pcbSize), cbSizeHeader)
                
                if res != -1 and raw_input_data.header.dwType == RIM_TYPEMOUSE:
                    # 🚨 终极安全转换：用 c_long 强铸类型，规避无符号数漏洞
                    raw_x = ctypes.c_long(raw_input_data.mouse.lLastX).value
                    raw_y = ctypes.c_long(raw_input_data.mouse.lLastY).value
                    
                    if raw_x != 0 or raw_y != 0:
                        # 严格的方向映射要求：
                        # X方向：右移为正，左移为负
                        mapped_delta_x = raw_x
                        # Y方向：上移为正（因Windows默认下移为正，故取反还原物理方向）
                        mapped_delta_y = -raw_y
                        
                        # 实时在控制台打印带有方向正负号（+/-）的纯净变化量数据
                        print(f"[{elapsed_ms:7.2f} ms] 原始 Delta 位移 -> X: {mapped_delta_x:+4d}, Y: {mapped_delta_y:+4d}")
                        
                        # 归档图1（空间坐标）所需的绝对累加值
                        trajectory_x.append(trajectory_x[-1] + mapped_delta_x)
                        trajectory_y.append(trajectory_y[-1] + mapped_delta_y)
                        
                        # 归档图2（时间波动）所需的纯净变化量（不累加，只看每次高低）
                        delta_x_list.append(mapped_delta_x)
                        delta_y_list.append(mapped_delta_y)
                        timestamps.append(elapsed_ms)

    elif msg == win32con.WM_DESTROY:
        win32gui.PostQuitMessage(0)
        return 0

    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

# ==============================================================================
#  高级数据分析看盘（Matplotlib 多轴联动与滚轮无损缩放）
# ==============================================================================
def plot_trajectory():
    """联合绘制面板：左边看空间轨迹形状，右边看纯变化量高频垂直垂线波动"""
    if len(trajectory_x) <= 1:
        print("未捕获到足够的有效硬件位移，请重新运行并大幅度拖动。")
        return
        
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7.5))
    
    # --------------------------------------------------------------------------
    # 图 1：经典空间轨迹图 (Cumulative Path)
    # --------------------------------------------------------------------------
    ax1.plot(trajectory_x, trajectory_y, color='#1f77b4', alpha=0.3, label='Path')
    sc1 = ax1.scatter(trajectory_x, trajectory_y, color='#ff7f0e', s=12, picker=True, label='Counts')
    ax1.set_title("Mouse Space Trajectory (Math Coordinates)")
    ax1.set_xlabel("X Cumulative (Right = +)")
    ax1.set_ylabel("Y Cumulative (Up = +)")
    ax1.grid(True, linestyle='--', alpha=0.5)
    ax1.legend()
    ax1.axis('equal') # 强行锁定 1:1 分辨率长宽比，防止圆画成椭圆
    
    # 交互提示框 1
    annot1 = ax1.annotate("", xy=(0,0), xytext=(15,15), textcoords="offset points",
                        color="white",
                        bbox=dict(boxstyle="round", fc="black", alpha=0.8),
                        arrowprops=dict(arrowstyle="->", color="black"))
    annot1.set_visible(False)

    # --------------------------------------------------------------------------
    # 图 2：Delta 位移变化量 - 时间图 (严格遵循：右/上移为正，左/下移为负)
    # --------------------------------------------------------------------------
    # 1. 绘制极细的演进背景线
    ax2.plot(timestamps, delta_x_list, color='#9467bd', linewidth=0.5, alpha=0.4)
    ax2.plot(timestamps, delta_y_list, color='#e377c2', linewidth=0.5, alpha=0.4)
    
    # 2. 绘制分立的原始硬件离散采样点，绑定拾取器
    sc_line_x = ax2.scatter(timestamps, delta_x_list, color='#9467bd', s=8, picker=True, label='X Delta (Right=+ / Left=-)')
    sc_line_y = ax2.scatter(timestamps, delta_y_list, color='#e377c2', s=8, picker=True, label='Y Delta (Up=+ / Down=-)')
    
    # 3. 核心定制：拉出每个硬件点到 0 基准线的垂直点阵虚线
    ax2.vlines(timestamps, ymin=0, ymax=delta_x_list, colors='#9467bd', linestyles=':', linewidth=0.5, alpha=0.25)
    ax2.vlines(timestamps, ymin=0, ymax=delta_y_list, colors='#e377c2', linestyles=':', linewidth=0.5, alpha=0.25)
    
    # 4. 显式强化 0 刻度中央地平线
    ax2.axhline(0, color='black', linewidth=0.9, linestyle='-')
    
    ax2.set_title("Mouse Delta Counts vs Time (Directional Waves)")
    ax2.set_xlabel("Time (ms)")
    ax2.set_ylabel("Delta Counts (Per Message)")
    ax2.grid(True, linestyle='--', alpha=0.3)
    ax2.legend()

    # 交互提示框 2
    annot2 = ax2.annotate("", xy=(0,0), xytext=(15,15), textcoords="offset points",
                        color="white",
                        bbox=dict(boxstyle="round", fc="black", alpha=0.8),
                        arrowprops=dict(arrowstyle="->", color="black"))
    annot2.set_visible(False)

    # --------------------------------------------------------------------------
    #  高级动态交互：点击事件 (Pick Event)
    # --------------------------------------------------------------------------
    def on_pick(event):
        if event.artist == sc1:
            ind = event.ind[0]
            x = trajectory_x[ind]
            y = trajectory_y[ind]
            t = timestamps[ind]
            annot1.xy = (x, y)
            annot1.set_text(f"Index: {ind}\nX: {x}\nY: {y}\nTime: {t:.2f} ms")
            annot1.set_visible(True)
            fig.canvas.draw_idle()
        elif event.artist in [sc_line_x, sc_line_y]:
            ind = event.ind[0]
            x_val = timestamps[ind]
            y_val = delta_x_list[ind] if event.artist == sc_line_x else delta_y_list[ind]
            label = "X Delta" if event.artist == sc_line_x else "Y Delta"
            annot2.xy = (x_val, y_val)
            annot2.set_text(f"Index: {ind}\nTime: {x_val:.2f} ms\n{label}: {y_val:+d} counts")
            annot2.set_visible(True)
            fig.canvas.draw_idle()

    # --------------------------------------------------------------------------
    #  高级动态交互：滚轮无限缩放 (以鼠标悬停中心为圆心)
    # --------------------------------------------------------------------------
    def on_scroll(event):
        ax = event.inaxes
        if ax is None: 
            return
            
        cur_xlim = ax.get_xlim()
        cur_ylim = ax.get_ylim()
        xdata = event.xdata
        ydata = event.ydata
        
        # 向上滚动放大(范围缩小为0.75)，向下滚动缩小(范围扩大为1.3)
        base_scale = 0.75 if event.button == 'up' else 1.3
        
        new_width = (cur_xlim[1] - cur_xlim[0]) * base_scale
        rel_x_pos = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0])
        new_xlim = [xdata - new_width * (1 - rel_x_pos), xdata + new_width * rel_x_pos]
        
        new_height = (cur_ylim[1] - cur_ylim[0]) * base_scale
        rel_y_pos = (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0])
        new_ylim = [ydata - new_height * (1 - rel_y_pos), ydata + new_height * rel_y_pos]
        
        ax.set_xlim(new_xlim)
        ax.set_ylim(new_ylim)
        
        # 保证图1在缩放时物理形状不失真
        if ax == ax1: 
            ax.set_aspect('equal', adjustable='box')
            
        fig.canvas.draw_idle()

    # 挂载高级交互连接器
    fig.canvas.mpl_connect('pick_event', on_pick)
    fig.canvas.mpl_connect('scroll_event', on_scroll)
    
    plt.tight_layout() 
    print("图表加载完成。你可以把鼠标放到任意图上滚动【滚轮】无损缩放。")
    plt.show()

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
    create_window()
    plot_trajectory()