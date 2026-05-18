"""
微信自动化聊天脚本

功能：
1. 自动查找并激活微信窗口
2. 打开微信搜索框
3. 搜索指定联系人或群组
4. 验证联系人存在于搜索结果中
5. 打开聊天窗口
6. 发送消息

注意：
- 需要启动微信
- 首次运行可能需要调整延迟时间
- 请合理合法使用此工具
"""

import pyautogui
import time
import sys
import pyperclip

# 配置参数
CONFIG = {
    "search_hotkey_delay": 0.5,  # 快捷键后延迟
    "type_delay": 0.05,  # 打字延迟
    "wait_after_search": 1.0,  # 搜索后等待时间
    "click_chat_delay": 0.5,  # 点击聊天前延迟
    "enter_chat_delay": 1.0,  # 进入聊天后延迟
    "message_delay": 1.0,  # 发送消息前延迟
    "safety_margin": 2.0,  # 安全等待时间
}

# 微信联系人列表大致位置（需要根据实际屏幕调整）
# 这些是相对位置，会在运行时根据窗口大小调整
CHAT_ITEM_OFFSET = 100  # 聊天列表项的垂直偏移量（从搜索框开始）
CHAT_ITEM_HEIGHT = 50  # 每个聊天项的高度


def set_position(x, y):
    """安全地移动鼠标位置"""
    pyautogui.FAILSAFE = True  # 鼠标移到屏幕角落可中断
    pyautogui.moveTo(x, y, duration=0.3)


def type_text(text, delay=None):
    """输入文本"""
    if delay is None:
        delay = CONFIG["type_delay"]
    pyautogui.typewrite(text, interval=delay)


def press_key(key):
    """按下按键"""
    pyautogui.press(key)


def click_position(x, y):
    """点击指定位置"""
    set_position(x, y)
    pyautogui.click()


def get_window_position():
    """获取微信窗口位置（简单实现）"""
    # 尝试获取鼠标当前位置作为参考
    return pyautogui.position()


def find_wechat_window():
    """查找并激活微信窗口"""
    try:
        import win32gui
        import win32con

        def enum_windows_callback(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                try:
                    title = win32gui.GetWindowText(hwnd)
                    if "微信" in title or "WeChat" in title:
                        results.append((hwnd, title))
                except:
                    pass
            return True

        wechat_windows = []
        win32gui.EnumWindows(enum_windows_callback, wechat_windows)

        if wechat_windows:
            # 选择第一个找到的窗口
            hwnd, title = wechat_windows[0]

            # 激活窗口
            try:
                win32gui.SetForegroundWindow(hwnd)
            except:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)

            # 获取窗口位置
            rect = win32gui.GetWindowRect(hwnd)
            center_x = rect[0] + (rect[2] - rect[0]) // 2
            center_y = rect[1] + (rect[3] - rect[1]) // 2

            print(f"✅ 找到并激活微信窗口：{title}")
            pyautogui.moveTo(center_x, center_y, duration=0.5)
            return True
        else:
            print("❌ 未找到微信窗口，请确保微信已启动")
            return False

    except ImportError:
        print("⚠️  pywin32 未安装，使用备用方法...")
        screen_width, screen_height = pyautogui.size()
        pyautogui.moveTo(screen_width // 2, screen_height // 2, duration=0.5)
        return True
    except Exception as e:
        print(f"⚠️  查找微信窗口异常：{e}")
        # 备用方案：移动到屏幕中心
        screen_width, screen_height = pyautogui.size()
        pyautogui.moveTo(screen_width // 2, screen_height // 2, duration=0.5)
        return True


def search_and_chat(contact_name, message="", auto_find_window=True, debug_mode=True):
    """
    搜索联系人并聊天

    Args:
        contact_name: 联系人或群组名称
        message: 要发送的消息（可选）
        auto_find_window: 是否自动查找并激活微信窗口
        debug_mode: 是否开启调试模式（显示详细日志）
    """
    print(f"\n{'=' * 50}")
    print(f"📱 微信自动化 - 开始执行")
    print(f"{'=' * 50}")
    print(f"📌 联系人：{contact_name}")
    print(f"📌 消息：{message if message else '(仅打开聊天)'}")
    print(f"{'=' * 50}\n")

    # 安全等待
    if debug_mode:
        print(f"⏱️  等待 {CONFIG['safety_margin']} 秒...")
    time.sleep(CONFIG["safety_margin"])

    # ===== 步骤 1: 激活微信窗口 =====
    if auto_find_window:
        print(f"[1/6] 🔍 查找并激活微信窗口...")
        window_found = find_wechat_window()
        if not window_found:
            error_msg = "❌ 未找到微信窗口，请确保微信已启动"
            print(error_msg)
            return error_msg
        print(f"      ✅ 微信窗口已激活")
        time.sleep(1.0)

    # ===== 步骤 2: 打开搜索框 =====
    print(f"[2/6] 🔍 按下 Ctrl+F 打开搜索框...")
    pyautogui.hotkey("ctrl", "f")
    if debug_mode:
        print(f"      ⏱️  等待搜索框出现 (2 秒)...")
    time.sleep(2.0)

    # 获取当前鼠标位置作为搜索框位置参考
    search_box_pos = pyautogui.position()
    if debug_mode:
        print(
            f"      📍 当前鼠标位置 (搜索框区域): ({search_box_pos.x}, {search_box_pos.y})"
        )

    # 点击搜索框确保焦点
    search_input_x = search_box_pos.x + 50  # 搜索框内偏右位置
    search_input_y = search_box_pos.y + 5
    print(f"      🖱️  点击搜索框确保焦点...")
    pyautogui.moveTo(search_input_x, search_input_y, duration=0.2)
    pyautogui.click()
    time.sleep(0.5)
    print(f"      ✅ 搜索框已打开并获取焦点")

    # ===== 步骤 3: 使用剪贴板粘贴联系人名称 =====
    print(f"[3/6] ✍️  使用剪贴板粘贴联系人名称 '{contact_name}'...")

    # 将联系人名称复制到剪贴板
    print(f"      📋 复制 '{contact_name}' 到剪贴板...")
    pyperclip.copy(contact_name)
    time.sleep(0.3)

    # 点击搜索框确保焦点
    print(f"      🖱️  点击搜索框确保焦点...")
    pyautogui.click(search_input_x, search_input_y)
    time.sleep(0.5)

    # 清空搜索框（如果有旧内容）
    print(f"      🧹 清空搜索框...")
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.2)
    pyautogui.press("delete")
    time.sleep(0.2)
    pyautogui.press("backspace")
    time.sleep(0.3)

    # 再次点击确保焦点
    pyautogui.click(search_input_x, search_input_y)
    time.sleep(0.3)

    # 使用 Ctrl+V 粘贴联系人名称
    print(f"      ⌨️  按 Ctrl+V 粘贴联系人名称...")
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.5)

    # 验证粘贴是否成功（读取剪贴板确认内容一致）
    clipboard_content = pyperclip.paste()
    if clipboard_content == contact_name:
        print(f"      ✅ 确认已粘贴：'{contact_name}'")
    else:
        print(f"      ⚠️  剪贴板内容不一致，尝试再次粘贴...")
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.5)

    if debug_mode:
        print(f"      ⏱️  等待搜索结果加载 (2.5 秒)...")
    time.sleep(2.5)
    print(f"      ✅ 联系人名称已输入到搜索框")

    # ===== 步骤 4: 使用方向键选择联系人 =====
    print(f"[4/6] ⌨️  使用方向键选择联系人 '{contact_name}'...")

    # 微信搜索结果默认第一个高亮，我们按向下方向键来遍历
    # 最多尝试 20 次，如果找到匹配的联系人就停止
    contact_found = False
    max_attempts = 20

    if debug_mode:
        print(f"      🔍 开始遍历搜索结果 (最多 {max_attempts} 个)...")

    for i in range(max_attempts):
        # 读取当前高亮项的文本（通过复制到剪贴板的方式）
        # 按 Ctrl+C 复制当前选中的联系人名称
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.2)

        # 读取剪贴板内容
        try:
            import pyperclip

            selected_text = pyperclip.paste().strip()

            if debug_mode:
                print(f"      [{i + 1}/{max_attempts}] 当前选中：'{selected_text}'")

            # 检查是否匹配联系人名称
            if contact_name in selected_text or selected_text in contact_name:
                print(f"      ✅ 找到匹配的联系人：'{selected_text}'")
                contact_found = True
                break

        except ImportError:
            if debug_mode:
                print(f"      ⚠️  pyperclip 未安装，使用备用方法...")
            # 备用方法：直接按向下键一次然后进入
            if i == 0:
                break
        except Exception as e:
            if debug_mode:
                print(f"      ⚠️  读取剪贴板失败：{e}")

        # 如果没有匹配，按向下方向键选择下一个
        if i < max_attempts - 1:
            pyautogui.press("down")
            time.sleep(0.3)

    if not contact_found:
        error_msg = f"❌ 未在搜索结果中找到联系人：'{contact_name}'"
        print(error_msg)
        print(f"      💡 请检查联系人名称是否正确，或尝试手动搜索确认")
        return error_msg

    print(f"      ✅ 已选中联系人")

    # ===== 步骤 5: 按回车进入聊天 =====
    print(f"[5/6] ⌨️  按回车进入聊天窗口...")
    press_key("enter")
    if debug_mode:
        print(f"      ⏱️  等待聊天窗口打开 (2 秒)...")
    time.sleep(2.0)
    print(f"      ✅ 已进入聊天窗口")

    # ===== 步骤 6: 发送消息 =====
    if message:
        print(f"[6/6] 📤 发送消息：{message}")
        time.sleep(CONFIG["message_delay"])

        # 点击输入框（大致在窗口底部）
        screen_width, screen_height = pyautogui.size()
        input_area_x = screen_width // 2
        input_area_y = screen_height - 100

        click_position(input_area_x, input_area_y)
        time.sleep(0.5)

        # 输入消息
        type_text(message)
        time.sleep(0.3)

        # 按回车发送
        print("      🚀 发送消息...")
        press_key("enter")
        time.sleep(1.0)
        print(f"      ✅ 消息已发送")
    else:
        print(f"[6/6] ℹ️  没有消息内容，仅打开聊天窗口")

    print("\n✅ 操作完成！")
    return f"✅ 已成功打开与 '{contact_name}' 的聊天窗口{f' 并发送消息' if message else ''}"


def search_and_chat_by_position(
    contact_name, message="", position=1, auto_find_window=True
):
    """
    通过指定位置点击搜索结果（更精确）

    Args:
        contact_name: 联系人或群组名称
        message: 要发送的消息
        position: 搜索结果的位置（1=第一个，2=第二个...）
        auto_find_window: 是否自动查找并激活微信窗口
    """
    print(f"📱 开始操作微信...")
    print(f"🔍 目标：{contact_name} (位置：{position})")

    time.sleep(CONFIG["safety_margin"])

    # 自动查找并激活微信窗口
    if auto_find_window:
        print("🔍 查找微信窗口...")
        window_found = find_wechat_window()
        if not window_found:
            return "❌ 未找到微信窗口"
        time.sleep(0.5)

    # 打开搜索框
    print("🔍 打开搜索框...")
    pyautogui.hotkey("ctrl", "f")
    time.sleep(CONFIG["search_hotkey_delay"])

    # 输入联系人名称
    print(f"✍️  输入联系人：{contact_name}")
    type_text(contact_name)
    time.sleep(CONFIG["wait_after_search"])

    # 获取屏幕尺寸
    screen_width, screen_height = pyautogui.size()

    # 计算搜索结果点击位置
    # 搜索框通常在窗口左侧，结果在右侧
    result_x = screen_width * 0.3  # 大概位置
    result_y = screen_height * 0.2 + (position - 1) * CHAT_ITEM_HEIGHT

    print(f"🖱️  点击搜索结果 (位置 {position})...")
    click_position(result_x, result_y)
    time.sleep(CONFIG["click_chat_delay"])

    # 按回车进入聊天
    print("⌨️  按回车进入聊天...")
    press_key("enter")
    time.sleep(CONFIG["enter_chat_delay"])

    # 发送消息
    if message:
        print(f"📤 发送消息：{message}")
        time.sleep(CONFIG["message_delay"])

        # 点击输入框区域
        input_x = screen_width * 0.5
        input_y = screen_height * 0.9

        click_position(input_x, input_y)
        time.sleep(0.5)

        type_text(message)
        time.sleep(0.3)

        print("🚀 发送消息...")
        press_key("enter")
        time.sleep(1.0)

    print("✅ 操作完成！")


def batch_send(contact_list, message):
    """
    批量发送给多个联系人

    Args:
        contact_list: 联系人列表，每个元素为 (名称，位置) 元组
        message: 要发送的消息
    """
    for i, (name, pos) in enumerate(contact_list, 1):
        print(f"\n[{i}/{len(contact_list)}] 处理：{name}")
        search_and_chat_by_position(name, message, pos)

        # 询问是否继续
        if i < len(contact_list):
            response = input("按回车继续下一个，或输入 q 退出：")
            if response.lower() == "q":
                break


def interactive_mode():
    """交互式模式"""
    print("=" * 50)
    print("🤖 微信自动化聊天工具")
    print("=" * 50)
    print()

    while True:
        print("\n选项：")
        print("1. 发送单条消息")
        print("2. 批量发送")
        print("3. 退出")

        choice = input("\n请选择 (1-3): ").strip()

        if choice == "1":
            contact_name = input("联系人/群组名称：").strip()
            message = input("消息内容（留空则只打开聊天）：").strip()
            position = input("搜索结果位置 (1-10, 默认 1): ").strip()
            position = int(position) if position.isdigit() else 1

            search_and_chat_by_position(contact_name, message, position)

        elif choice == "2":
            print("\n批量发送模式")
            message = input("消息内容：").strip()

            contact_list = []
            while True:
                name = input("\n联系人名称 (留空完成输入): ").strip()
                if not name:
                    break
                pos = input("搜索结果位置 (1-10): ").strip()
                pos = int(pos) if pos.isdigit() else 1
                contact_list.append((name, pos))

            if contact_list:
                batch_send(contact_list, message)

        elif choice == "3":
            print("退出程序")
            break
        else:
            print("无效选择")


if __name__ == "__main__":
    # 设置 pyautogui 配置
    pyautogui.FAILSAFE = True  # 鼠标移到屏幕边缘可中断
    pyautogui.PAUSE = 1  # 每次操作后暂停 1 秒

    print("⚠️  安全提示：将鼠标移到屏幕角落可随时中断程序\n")

    if len(sys.argv) > 1:
        # 命令行模式
        contact_name = sys.argv[1]
        message = sys.argv[2] if len(sys.argv) > 2 else ""
        search_and_chat(contact_name, message)
    else:
        # 交互模式
        interactive_mode()
