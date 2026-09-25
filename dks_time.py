import sys
import os
import ctypes
from ctypes import wintypes
import time
from datetime import datetime
import threading
import traceback
import re

# ==============================================================================
#  用户配置区
# ==============================================================================
KEY_MAP = {
    'A': 'F9',
    'D': 'F8'
}
PRINT_ALL_KEYS = True
BATCH_SIZE = 10  # 每累积多少次触发记录输出一次批次报告

# 脚本所在目录，CSV 文件将保存到这里
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ==============================================================================
#  Windows API 常量定义
# ==============================================================================

WS_OVERLAPPEDWINDOW = 0x00CF0000
SW_SHOWNORMAL = 1
CW_USEDEFAULT = 0x80000000

WM_INPUT = 0x00FF
WM_DESTROY = 0x0002
WM_QUIT = 0x0012

RIM_TYPKEYBOARD = 1
RID_INPUT = 0x10000003
RIDEV_INPUTSINK = 0x00000100
RIDI_DEVICENAME = 0x20000007

VK_A = 0x41
VK_D = 0x44
VK_F8 = 0x77
VK_F9 = 0x78

RI_KEY_MAKE = 0
RI_KEY_BREAK = 1

F_KEY_TO_LETTER = {v: k for k, v in KEY_MAP.items()}

# 虚拟键名映射：A-Z、0-9 在 _get_key_name 中动态转换，这里只补充无法用 chr() 的键
VK_NAME_MAP = {
    0x01: '鼠标左键', 0x02: '鼠标右键', 0x04: '鼠标中键',
    0x05: '鼠标X1', 0x06: '鼠标X2',
    0x08: 'Backspace', 0x09: 'Tab',
    0x0C: 'Clear', 0x0D: 'Enter',
    0x10: 'Shift', 0x11: 'Ctrl', 0x12: 'Alt', 0x13: 'Pause',
    0x14: 'CapsLock',
    0x1B: 'Esc',
    0x20: '空格',
    0x21: 'PageUp', 0x22: 'PageDown',
    0x23: 'End', 0x24: 'Home',
    0x25: '←', 0x26: '↑', 0x27: '→', 0x28: '↓',
    0x2D: 'Insert', 0x2E: 'Delete',
    0x5B: '左Win', 0x5C: '右Win', 0x5D: '菜单键',
    0x60: 'Num0', 0x61: 'Num1', 0x62: 'Num2', 0x63: 'Num3',
    0x64: 'Num4', 0x65: 'Num5', 0x66: 'Num6', 0x67: 'Num7',
    0x68: 'Num8', 0x69: 'Num9',
    0x6A: 'Num*', 0x6B: 'Num+', 0x6D: 'Num-', 0x6E: 'Num.', 0x6F: 'Num/',
    0x70: 'F1', 0x71: 'F2', 0x72: 'F3', 0x73: 'F4',
    0x74: 'F5', 0x75: 'F6', 0x76: 'F7',
    0x77: 'F8', 0x78: 'F9', 0x79: 'F10', 0x7A: 'F11', 0x7B: 'F12',
    0x90: 'NumLock', 0x91: 'ScrollLock',
    0xA0: '左Shift', 0xA1: '右Shift',
    0xA2: '左Ctrl', 0xA3: '右Ctrl',
    0xA4: '左Alt', 0xA5: '右Alt',
    0xAD: '静音', 0xAE: '音量-', 0xAF: '音量+',
    0xB0: '下一曲', 0xB1: '上一曲', 0xB2: '停止', 0xB3: '播放/暂停',
}

# ==============================================================================
#  Windows 结构体
# ==============================================================================

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM)
    ]

class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [
        ("MakeCode", wintypes.USHORT),
        ("Flags", wintypes.USHORT),
        ("Reserved", wintypes.USHORT),
        ("VKey", wintypes.USHORT),
        ("Message", wintypes.UINT),
        ("ExtraInformation", wintypes.ULONG)
    ]

class RAWINPUT(ctypes.Structure):
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("keyboard", RAWKEYBOARD)
    ]

class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND)
    ]

class WNDCLASSEX(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", ctypes.WINFUNCTYPE(ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HANDLE),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HANDLE)
    ]

class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", POINT)
    ]

# ==============================================================================
#  Windows API 加载
# ==============================================================================

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEX)]
user32.RegisterClassExW.restype = wintypes.ATOM

user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
    wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p
]
user32.CreateWindowExW.restype = wintypes.HWND

user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = ctypes.c_bool

user32.UpdateWindow.argtypes = [wintypes.HWND]
user32.UpdateWindow.restype = ctypes.c_bool

user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_void_p

user32.GetRawInputData.argtypes = [wintypes.HANDLE, wintypes.UINT, ctypes.c_void_p, ctypes.POINTER(wintypes.UINT), wintypes.UINT]
user32.GetRawInputData.restype = wintypes.UINT

user32.RegisterRawInputDevices.argtypes = [ctypes.POINTER(RAWINPUTDEVICE), wintypes.UINT, wintypes.UINT]
user32.RegisterRawInputDevices.restype = ctypes.c_bool

user32.PeekMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
user32.PeekMessageW.restype = ctypes.c_bool

user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.TranslateMessage.restype = ctypes.c_bool

user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.restype = ctypes.c_void_p

user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = ctypes.c_bool

user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PostQuitMessage.restype = None

user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
user32.LoadCursorW.restype = wintypes.HANDLE

user32.GetRawInputDeviceInfoW.argtypes = [wintypes.HANDLE, wintypes.UINT, ctypes.c_void_p, ctypes.POINTER(wintypes.UINT)]
user32.GetRawInputDeviceInfoW.restype = wintypes.UINT

kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE

kernel32.GetLastError.argtypes = []
kernel32.GetLastError.restype = wintypes.DWORD

kernel32.QueryPerformanceFrequency.argtypes = [ctypes.POINTER(ctypes.c_int64)]
kernel32.QueryPerformanceFrequency.restype = ctypes.c_bool

kernel32.QueryPerformanceCounter.argtypes = [ctypes.POINTER(ctypes.c_int64)]
kernel32.QueryPerformanceCounter.restype = ctypes.c_bool

# ==============================================================================
#  键盘状态追踪器（含时间格式化）
# ==============================================================================

class KeyStateTracker:
    def __init__(self):
        try:
            self.key_states = {
                VK_A: {'pressed_time': None, 'released_time': None, 'last_state': 'up'},
                VK_D: {'pressed_time': None, 'released_time': None, 'last_state': 'up'}
            }
            self.f8_trigger_count = 0
            self.f9_trigger_count = 0
            self.lock = threading.Lock()
            self.running = True
            self.test_data = []

            self.frequency = ctypes.c_int64()
            if not kernel32.QueryPerformanceFrequency(ctypes.byref(self.frequency)):
                raise RuntimeError("QueryPerformanceFrequency 失败")
            self.frequency = self.frequency.value
            if self.frequency == 0:
                raise RuntimeError("性能计数器频率为0")

            # 记录程序启动时的 QPC 时间，用于计算相对偏移
            self.start_qpc = self.get_timestamp_ms()
            self.session_id = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"✅ 性能计数器初始化成功 (频率: {self.frequency} Hz)")
            print(f"🔧 映射配置: A→{KEY_MAP['A']}, D→{KEY_MAP['D']}")
            print(f"⏱️  程序启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
            print(f"📋 本次会话ID: {self.session_id}")
        except Exception as e:
            print(f"❌ KeyStateTracker 初始化失败: {e}")
            print(traceback.format_exc())
            raise

    def get_timestamp_ms(self):
        try:
            counter = ctypes.c_int64()
            if not kernel32.QueryPerformanceCounter(ctypes.byref(counter)):
                raise RuntimeError("QueryPerformanceCounter 失败")
            return (counter.value * 1000.0) / self.frequency
        except Exception as e:
            print(f"⚠️  get_timestamp_ms 错误: {e}")
            return time.time() * 1000

    def _format_event_prefix(self, qpc_ms):
        """生成事件前缀: [绝对时间] [+相对偏移]"""
        abs_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        rel_ms = qpc_ms - self.start_qpc
        return f"[{abs_time}] [{rel_ms:+.3f} ms]"

    def handle_key_event(self, vkey, key_flags, timestamp, device_name="Unknown"):
        try:
            with self.lock:
                is_press = (key_flags == RI_KEY_MAKE)
                is_release = (key_flags == RI_KEY_BREAK)
                key_name = self._get_key_name(vkey)
                prefix = self._format_event_prefix(timestamp)

                if PRINT_ALL_KEYS:
                    action = "按下" if is_press else "松开"
                    print(f"{prefix} ⌨️  {action} {key_name} (VK=0x{vkey:02X}) [设备: {device_name}]")

                # 处理 F8/F9 触发
                if vkey == VK_F8 and is_press:
                    self.f8_trigger_count += 1
                    self._check_f_trigger('F8', timestamp, device_name, prefix)
                    return
                if vkey == VK_F9 and is_press:
                    self.f9_trigger_count += 1
                    self._check_f_trigger('F9', timestamp, device_name, prefix)
                    return

                # 记录 A/D 按下/松开时间（仍保存QPC原始值，用于差值计算）
                if vkey in [VK_A, VK_D]:
                    if is_press:
                        self.key_states[vkey]['pressed_time'] = timestamp
                        self.key_states[vkey]['released_time'] = None  # 新周期开始，清空旧松开时间
                        self.key_states[vkey]['last_state'] = 'pressed'
                    elif is_release:
                        self.key_states[vkey]['released_time'] = timestamp
                        self.key_states[vkey]['last_state'] = 'released'

        except Exception as e:
            print(f"❌ handle_key_event 错误: {e}")
            print(traceback.format_exc())

    def _get_key_name(self, vkey):
        # 先从完整映射表查
        if vkey in VK_NAME_MAP:
            return VK_NAME_MAP[vkey]
        # A-Z: VK 0x41-0x5A
        if 0x41 <= vkey <= 0x5A:
            return chr(vkey)
        # 0-9: VK 0x30-0x39
        if 0x30 <= vkey <= 0x39:
            return chr(vkey)
        # 符号键：尝试用 MapVirtualKey 转换扫描码，失败则显示 VK_xx
        return f"VK_{vkey:02X}"

    def _check_f_trigger(self, fkey_name, trigger_time, device_name, event_prefix):
        try:
            if fkey_name not in F_KEY_TO_LETTER:
                fkey_vk = self._get_vk_for_fkey(fkey_name)
                print(f"{event_prefix} ⚡ 触发 {fkey_name} (VK=0x{fkey_vk:02X}) [设备: {device_name}]，但未在映射中找到对应键")
                return
            letter = F_KEY_TO_LETTER[fkey_name]
            target_vk = VK_A if letter == 'A' else VK_D

            key_info = self.key_states.get(target_vk)
            if not key_info:
                fkey_vk = self._get_vk_for_fkey(fkey_name)
                print(f"{event_prefix} ⚡ 触发 {fkey_name} (VK=0x{fkey_vk:02X}) [设备: {device_name}]，但目标键 {letter} 状态未知")
                return

            released = key_info['released_time']
            pressed = key_info['pressed_time']

            if released is None:
                fkey_vk = self._get_vk_for_fkey(fkey_name)
                print(f"{event_prefix} ⚡ 触发 {fkey_name} (VK=0x{fkey_vk:02X}) [设备: {device_name}]，但 {letter} 键尚未松开")
                return

            delay = trigger_time - released
            entry = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                'session_id': self.session_id,
                'trigger_key': fkey_name,
                'target_key': letter,
                'trigger_time': trigger_time,
                'release_time': released,
                'press_time': pressed,
                'delay_ms': delay,
                'device': device_name
            }
            self.test_data.append(entry)

            # 每累积 BATCH_SIZE 条触发记录，输出批次报告
            if len(self.test_data) % BATCH_SIZE == 0:
                self._report_batch()

            fkey_vk = self._get_vk_for_fkey(fkey_name)
            print(f"{event_prefix} ⚡ 触发 {fkey_name} (VK=0x{fkey_vk:02X}) [设备: {device_name}] (对应 {letter} VK=0x{target_vk:02X})")
            # 显示事件发生时的相对偏移（相对于程序启动）
            rel_trigger = trigger_time - self.start_qpc
            rel_pressed = (pressed - self.start_qpc) if pressed is not None else None
            rel_released = released - self.start_qpc
            if pressed is not None:
                print(f"   按下时间: [{rel_pressed:+.3f} ms]")
            else:
                print(f"   按下时间: (未记录)")
            print(f"   松开时间: [{rel_released:+.3f} ms]")
            print(f"   触发时间: [{rel_trigger:+.3f} ms]")
            print(f"   ✅ 松开→触发延迟: {delay:.3f} ms")
            if pressed is not None:
                total = trigger_time - pressed
                print(f"   📌 按下→触发总时间: {total:.3f} ms")
            print()

        except Exception as e:
            print(f"❌ _check_f_trigger 错误: {e}")
            print(traceback.format_exc())

    def _get_vk_for_fkey(self, fkey_name):
        if fkey_name == 'F8':
            return VK_F8
        elif fkey_name == 'F9':
            return VK_F9
        return 0

    def _report_batch(self):
        """每累积 BATCH_SIZE 条触发记录时输出批次报告并追加到同一个 CSV"""
        try:
            total = len(self.test_data)
            if total == 0:
                return
            batch_start = max(0, total - BATCH_SIZE)
            batch = self.test_data[batch_start:total]
            batch_num = total // BATCH_SIZE  # 第几批

            f8_batch = [d for d in batch if d['trigger_key'] == 'F8']
            f9_batch = [d for d in batch if d['trigger_key'] == 'F9']

            # ── 计算统计值 ──
            def stats(data_list):
                if not data_list:
                    return {'count': 0, 'avg': '', 'min': '', 'max': '', 'std': ''}
                delays = [d['delay_ms'] for d in data_list]
                return {
                    'count': len(delays),
                    'avg': f"{sum(delays)/len(delays):.3f}",
                    'min': f"{min(delays):.3f}",
                    'max': f"{max(delays):.3f}",
                    'std': f"{calc_std(delays):.3f}"
                }

            s_f8 = stats(f8_batch)
            s_f9 = stats(f9_batch)
            s_all = stats(batch)

            # ── 控制台输出 ──
            print("\n" + "─" * 60)
            print(f"📦 批次报告 (第 {batch_start + 1} ~ {total} 条，共 {len(batch)} 次)")
            print("─" * 60)

            for label, s in [('F8 (D→F8)', s_f8), ('F9 (A→F9)', s_f9)]:
                if s['count'] > 0:
                    print(f"  {label}: {s['count']}次 | 平均 {s['avg']}ms | 最小 {s['min']}ms | 最大 {s['max']}ms | 标准差 {s['std']}ms")
                else:
                    print(f"  {label}: 0次")

            if s_all['count'] > 0:
                print(f"  📌 批次总计: 平均 {s_all['avg']}ms | 最小 {s_all['min']}ms | 最大 {s_all['max']}ms | 标准差 {s_all['std']}ms")
            print("─" * 60)

            # ── 追加到同一个 CSV（每个统计值独立一列）──
            import csv
            filename = os.path.join(SCRIPT_DIR, "dks_batch_results.csv")
            file_exists = os.path.isfile(filename)

            FIELD_NAMES = [
                '会话', '批次', '序号', '触发键', '目标键', '设备', '延迟ms', '时间戳',
                'F8次数', 'F8平均ms', 'F8最小ms', 'F8最大ms', 'F8标准差',
                'F9次数', 'F9平均ms', 'F9最小ms', 'F9最大ms', 'F9标准差',
                '全部平均ms', '全部最小ms', '全部最大ms', '全部标准差'
            ]

            # 每个批次用 DictWriter 保证列对齐
            with open(filename, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=FIELD_NAMES)
                if not file_exists:
                    writer.writeheader()

                # 写入 10 条数据行（附带批次统计，方便阅读）
                for i, entry in enumerate(batch, 1):
                    writer.writerow({
                        '会话': self.session_id,
                        '批次': batch_num,
                        '序号': i,
                        '触发键': entry['trigger_key'],
                        '目标键': entry['target_key'],
                        '设备': entry.get('device', 'Unknown'),
                        '延迟ms': f"{entry['delay_ms']:.3f}" if entry['delay_ms'] is not None else '',
                        '时间戳': entry['timestamp'],
                        'F8次数': s_f8['count'], 'F8平均ms': s_f8['avg'], 'F8最小ms': s_f8['min'], 'F8最大ms': s_f8['max'], 'F8标准差': s_f8['std'],
                        'F9次数': s_f9['count'], 'F9平均ms': s_f9['avg'], 'F9最小ms': s_f9['min'], 'F9最大ms': s_f9['max'], 'F9标准差': s_f9['std'],
                        '全部平均ms': s_all['avg'], '全部最小ms': s_all['min'], '全部最大ms': s_all['max'], '全部标准差': s_all['std']
                    })

                # 写入汇总行（序号="统计"）
                writer.writerow({
                    '会话': self.session_id,
                    '批次': batch_num,
                    '序号': '统计',
                    '触发键': '-', '目标键': '-', '设备': '-', '延迟ms': '-',
                    '时间戳': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                    'F8次数': s_f8['count'], 'F8平均ms': s_f8['avg'], 'F8最小ms': s_f8['min'], 'F8最大ms': s_f8['max'], 'F8标准差': s_f8['std'],
                    'F9次数': s_f9['count'], 'F9平均ms': s_f9['avg'], 'F9最小ms': s_f9['min'], 'F9最大ms': s_f9['max'], 'F9标准差': s_f9['std'],
                    '全部平均ms': s_all['avg'], '全部最小ms': s_all['min'], '全部最大ms': s_all['max'], '全部标准差': s_all['std']
                })

            print(f"  💾 批次数据已追加到: {filename}\n")

        except Exception as e:
            print(f"❌ _report_batch 错误: {e}")
            print(traceback.format_exc())

# ==============================================================================
#  Windows 窗口与消息循环（设备名称获取）
# ==============================================================================

class WindowsMessageLoop:
    def __init__(self, tracker):
        self.tracker = tracker
        self.hwnd = None
        self.WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        self.wnd_proc = self.WNDPROC(self._wnd_proc)
        self.device_name_cache = {}

    def get_device_name(self, hDevice):
        if hDevice in self.device_name_cache:
            return self.device_name_cache[hDevice]
        try:
            pcbSize = wintypes.UINT()
            if user32.GetRawInputDeviceInfoW(hDevice, RIDI_DEVICENAME, None, ctypes.byref(pcbSize)) == -1:
                return None
            if pcbSize.value == 0:
                return None
            buf = ctypes.create_unicode_buffer(pcbSize.value)
            if user32.GetRawInputDeviceInfoW(hDevice, RIDI_DEVICENAME, buf, ctypes.byref(pcbSize)) == -1:
                return None
            device_path = buf.value
            match = re.search(r'VID_([0-9A-F]{4})&PID_([0-9A-F]{4})', device_path, re.I)
            if match:
                vid, pid = match.groups()
                short_name = f"VID_{vid}_PID_{pid}"
            else:
                short_name = device_path[-20:] if len(device_path) > 20 else device_path
            self.device_name_cache[hDevice] = short_name
            return short_name
        except Exception as e:
            print(f"⚠️ 获取设备名称失败: {e}")
            return "Unknown"

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_INPUT:
                return self._handle_raw_input(lparam)
            elif msg == WM_DESTROY:
                self.tracker.running = False
                user32.PostQuitMessage(0)
                return 0
        except Exception as e:
            print(f"❌ 窗口消息处理错误: {e}")
            print(traceback.format_exc())
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _handle_raw_input(self, lparam):
        try:
            pcbSize = wintypes.UINT()
            cbSizeHeader = wintypes.UINT(ctypes.sizeof(RAWINPUTHEADER))
            if user32.GetRawInputData(ctypes.c_void_p(lparam), RID_INPUT, None, ctypes.byref(pcbSize), cbSizeHeader) == -1:
                return 0
            if pcbSize.value == 0:
                return 0

            raw = RAWINPUT()
            if user32.GetRawInputData(ctypes.c_void_p(lparam), RID_INPUT, ctypes.byref(raw), ctypes.byref(pcbSize), cbSizeHeader) == -1:
                return 0

            if raw.header.dwType == RIM_TYPKEYBOARD:
                vkey = raw.keyboard.VKey
                flags = raw.keyboard.Flags
                if vkey != 0xFF:
                    device_name = self.get_device_name(raw.header.hDevice) or "Unknown"
                    self.tracker.handle_key_event(vkey, flags, self.tracker.get_timestamp_ms(), device_name)
            return 0
        except Exception as e:
            print(f"❌ _handle_raw_input 错误: {e}")
            print(traceback.format_exc())
            return 0

    def register_raw_input(self, hwnd):
        try:
            device = RAWINPUTDEVICE(1, 6, RIDEV_INPUTSINK, hwnd)
            if not user32.RegisterRawInputDevices(ctypes.byref(device), 1, ctypes.sizeof(device)):
                raise RuntimeError(f"RegisterRawInputDevices 失败，错误码: {kernel32.GetLastError()}")
            print("✅ Raw Input 键盘注册成功")
            return True
        except Exception as e:
            print(f"❌ register_raw_input 错误: {e}")
            print(traceback.format_exc())
            return False

    def create_window(self):
        try:
            hInstance = kernel32.GetModuleHandleW(None)
            if not hInstance:
                raise RuntimeError(f"GetModuleHandleW 失败，错误码: {kernel32.GetLastError()}")

            wc = WNDCLASSEX()
            wc.cbSize = ctypes.sizeof(WNDCLASSEX)
            wc.lpfnWndProc = self.wnd_proc
            wc.hInstance = hInstance
            wc.lpszClassName = "KeyboardDKSTest"
            wc.hCursor = user32.LoadCursorW(None, ctypes.c_void_p(32512))

            if not user32.RegisterClassExW(ctypes.byref(wc)):
                raise RuntimeError(f"RegisterClassEx 失败，错误码: {kernel32.GetLastError()}")

            hwnd = user32.CreateWindowExW(
                0, wc.lpszClassName, "磁轴键盘 DKS 延迟测试工具",
                WS_OVERLAPPEDWINDOW,
                CW_USEDEFAULT, CW_USEDEFAULT, 500, 300,
                None, None, wc.hInstance, None
            )
            if not hwnd:
                raise RuntimeError(f"CreateWindowEx 失败，错误码: {kernel32.GetLastError()}")

            self.hwnd = hwnd
            user32.ShowWindow(hwnd, SW_SHOWNORMAL)
            user32.UpdateWindow(hwnd)

            if not self.register_raw_input(hwnd):
                user32.DestroyWindow(hwnd)
                return False
            return True
        except Exception as e:
            print(f"❌ create_window 错误: {e}")
            print(traceback.format_exc())
            return False

    def run_message_loop(self):
        try:
            msg = MSG()
            while self.tracker.running:
                if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                    if msg.message == WM_QUIT:
                        break
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                else:
                   pass
        
                   #time.sleep(0.001)

        except Exception as e:
            print(f"❌ 消息循环错误: {e}")
            print(traceback.format_exc())

    def cleanup(self):
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None

# ==============================================================================
#  统计与报告
# ==============================================================================

def calc_std(data):
    if len(data) < 2:
        return 0.0
    mean = sum(data) / len(data)
    variance = sum((x - mean) ** 2 for x in data) / len(data)
    return variance ** 0.5

def save_detailed_data(tracker):
    """程序退出时将本次所有数据追加到固定 CSV 文件"""
    try:
        import csv
        if not tracker.test_data:
            return
        filename = os.path.join(SCRIPT_DIR, "dks_test_all.csv")
        file_exists = os.path.isfile(filename)

        with open(filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['会话', '时间戳', '触发键', '目标键', '设备', '触发时间(ms)', '松开时间(ms)', '按下时间(ms)', '延迟(ms)'])
            if not file_exists:
                writer.writeheader()
            for entry in tracker.test_data:
                writer.writerow({
                    '会话': entry.get('session_id', ''),
                    '时间戳': entry['timestamp'],
                    '触发键': entry['trigger_key'],
                    '目标键': entry['target_key'],
                    '设备': entry.get('device', 'Unknown'),
                    '触发时间(ms)': f"{entry['trigger_time']:.3f}" if entry['trigger_time'] is not None else '',
                    '松开时间(ms)': f"{entry['release_time']:.3f}" if entry['release_time'] is not None else '',
                    '按下时间(ms)': f"{entry['press_time']:.3f}" if entry['press_time'] is not None else '',
                    '延迟(ms)': f"{entry['delay_ms']:.3f}" if entry['delay_ms'] is not None else ''
                })
        print(f"\n💾 本次 {len(tracker.test_data)} 条数据已追加到: {filename}")
    except Exception as e:
        print(f"❌ save_detailed_data 错误: {e}")
        print(traceback.format_exc())

def print_statistics(tracker):
    try:
        print("\n" + "="*70)
        print("📊 测试结果统计")
        print("="*70)
        if not tracker.test_data:
            print("没有捕获到任何触发事件!")
            return

        f8_data = [d for d in tracker.test_data if d['trigger_key'] == 'F8']
        f9_data = [d for d in tracker.test_data if d['trigger_key'] == 'F9']

        print(f"\n总有效触发记录: {len(tracker.test_data)}")
        print(f"  - F8 触发: {len(f8_data)} 次")
        print(f"  - F9 触发: {len(f9_data)} 次")

        devices = set(d.get('device', 'Unknown') for d in tracker.test_data)
        if len(devices) > 1:
            print(f"\n检测到 {len(devices)} 个不同的键盘设备，触发事件分布：")
            for dev in devices:
                count = sum(1 for d in tracker.test_data if d.get('device') == dev)
                print(f"  - {dev}: {count} 次")

        for fkey, data in [('F8', f8_data), ('F9', f9_data)]:
            if data:
                delays = [d['delay_ms'] for d in data]
                print(f"\n📌 {fkey} 松开→触发延迟统计:")
                print(f"    样本数: {len(delays)}")
                print(f"    最小值: {min(delays):.3f} ms")
                print(f"    最大值: {max(delays):.3f} ms")
                print(f"    平均值: {sum(delays)/len(delays):.3f} ms")
                print(f"    标准差: {calc_std(delays):.3f} ms")

        if f8_data and f9_data:
            all_delays = [d['delay_ms'] for d in (f8_data + f9_data)]
            print(f"\n📌 总体延迟统计 (全部):")
            print(f"    样本数: {len(all_delays)}")
            print(f"    最小值: {min(all_delays):.3f} ms")
            print(f"    最大值: {max(all_delays):.3f} ms")
            print(f"    平均值: {sum(all_delays)/len(all_delays):.3f} ms")
            print(f"    标准差: {calc_std(all_delays):.3f} ms")

        save_detailed_data(tracker)
    except Exception as e:
        print(f"❌ print_statistics 错误: {e}")
        print(traceback.format_exc())

# ==============================================================================
#  全局异常处理 & 主程序
# ==============================================================================

def global_exception_handler(exc_type, exc_value, exc_traceback):
    print("\n" + "="*70)
    print("❌ 发生未捕获的异常:")
    print("="*70)
    print(f"异常类型: {exc_type.__name__}")
    print(f"异常信息: {exc_value}")
    print("\n详细堆栈:")
    print(''.join(traceback.format_tb(exc_traceback)))
    print("="*70)
    sys.exit(1)

def main():
    try:
        tracker = KeyStateTracker()
        print("\n" + "="*70)
        print("🎯 磁轴键盘 DKS 功能延迟测试工具 (多键盘识别 + 人性化时间)")
        print("="*70)
        print("\n📖 使用说明:")
        print("  1. 点击弹出的窗口将其激活")
        print("  2. 按下并松开 A 或 D 键（DKS会自动触发对应的 F 键）")
        print("  3. 所有按键事件均显示绝对时间与相对偏移")
        print("  4. 可在代码开头修改 KEY_MAP 来调整映射关系")
        print("  5. 关闭窗口或按 Ctrl+C 退出程序")
        print("  6. 退出后自动生成统计报告和CSV数据文件")
        print("\n⏳ 开始测试...")
        print("-"*70 + "\n")

        msg_loop = WindowsMessageLoop(tracker)
        if not msg_loop.create_window():
            print("❌ 创建窗口失败，程序退出")
            return

        try:
            msg_loop.run_message_loop()
        except KeyboardInterrupt:
            print("\n\n⚠️  检测到中断信号，正在退出...")
        except Exception as e:
            print(f"❌ 运行错误: {e}")
            print(traceback.format_exc())
        finally:
            msg_loop.cleanup()

        print_statistics(tracker)
        print("\n✅ 测试完成!")

    except Exception as e:
        print(f"❌ main 函数异常: {e}")
        print(traceback.format_exc())
        sys.exit(1)
        
if __name__ == "__main__":
    sys.excepthook = global_exception_handler
    if not sys.platform.startswith('win'):
        print("❌ 此程序仅支持Windows系统")
        sys.exit(1)
    main()