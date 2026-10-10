import time
import random
import csv
import os
from playwright.sync_api import sync_playwright
from qwen_client import Chat_qwen
from dotenv import load_dotenv
from browser_utils import detect_browser_config, get_playwright_launch_args, configure_bundled_browsers

def init_browser(playwright, user_data_dir="Chrome_data"):
    """
    初始化浏览器，使用持久化上下文保存登录状态
    优先尝试最佳可用系统浏览器，失败则降级到临时会话
    
    参数:
        playwright: Playwright 实例
        user_data_dir: Chrome 用户数据目录（默认 Chrome_data）
    """
    # 获取标准启动参数
    launch_args_dict = get_playwright_launch_args(headless=False)
    launch_args = launch_args_dict["args"]
    
    # 确保用户数据目录是绝对路径
    if user_data_dir and not os.path.isabs(user_data_dir):
        user_data_dir = os.path.join(os.getcwd(), user_data_dir)
    
    # 检测最佳浏览器配置
    browser_type, specific_kwargs, browser_name = detect_browser_config(playwright)
    
    if user_data_dir:
        # 创建目录（如果不存在）
        try:
            os.makedirs(user_data_dir, exist_ok=True)
            print(f"✓ 使用持久化会话目录: {user_data_dir}")
        except Exception as e:
            print(f"⚠️ 创建目录失败: {e}")
        
        # 尝试持久化启动
        try:
            print(f"正在尝试 {browser_name} (持久化模式)...")
            context = browser_type.launch_persistent_context(
                user_data_dir,
                headless=False,
                args=launch_args,
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                viewport={'width': 1500, 'height': 800},
                **specific_kwargs
            )
            page = context.pages[0] if context.pages else context.new_page()
            print(f"✓ 使用 {browser_name} (持久化) 启动成功")
            return None, context, page
        except Exception as e:
            print(f"⚠️ {browser_name} (持久化) 启动失败: {e}")
            print("⚠️ 持久化模式失败，降级到临时会话模式...")
    
    # 3. 降级方案：临时会话 (检测所有浏览器 + 内置)
    print("✓ 使用临时会话（不保存状态）")
    try:
        browser = browser_type.launch(
            headless=False,
            args=launch_args,
            **specific_kwargs
        )
        print(f"✓ 成功启动 {browser_name} (临时会话)")
    except Exception as e:
        print(f"❌ {browser_name} 启动失败: {e}")
        if browser_name != "Built-in Chromium":
            print("尝试降级到内置 Chromium...")
            configure_bundled_browsers()
            try:
                browser = playwright.chromium.launch(
                    headless=False,
                    args=launch_args
                )
                print("✓ 成功启动内置 Chromium")
            except Exception as e2:
                print(f"❌ 内置 Chromium 启动失败: {e2}")
                raise e2
        else:
            raise e

    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        viewport={'width': 1500, 'height': 800},
        locale="zh-CN",
        timezone_id="Asia/Shanghai"
    )
    
    page = context.new_page()
    return browser, context, page

def read_candidates_csv(filename="douyin_candidates.csv"):
    """读取候选人CSV文件，仅需要 user_link 字段"""
    candidates = []
    csv_type = None  # 'comment' 或 'video'
    
    try:
        with open(filename, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            
            # 检测CSV类型（仅用于兼容性）
            if 'comment' in fieldnames:
                csv_type = 'comment'
                print(f"✓ 检测到评论类型CSV文件")
            elif 'video_text' in fieldnames and 'comment' not in fieldnames:
                csv_type = 'video'
                print(f"✓ 检测到视频类型CSV文件")
            else:
                csv_type = 'unknown'
                print(f"✓ 检测到CSV文件")
            
            # 检查必需字段
            if 'user_link' not in fieldnames:
                print(f"✗ CSV文件缺少必需字段 'user_link'")
                return [], None
            
            for row_index, row in enumerate(reader):
                # 检查是否已经发送过（标记为Done）
                status = row.get('status', '').strip()
                if status.lower() == 'done':
                    continue  # 跳过已发送的
                
                # 只需要 user_link 字段，其他字段仅用于显示
                if row.get('user_link'):
                    candidates.append({
                        'user_link': row.get('user_link', ''),
                        'user_name': row.get('user_name', ''),
                        'video_url': row.get('video_url', ''),
                        'csv_type': csv_type,
                        'row_index': row_index + 1
                    })
        
        print(f"✓ 从 {filename} 读取到 {len(candidates)} 条待发送数据")
        return candidates, csv_type
    except FileNotFoundError:
        print(f"✗ 文件未找到: {filename}")
        return [], None
    except Exception as e:
        print(f"✗ 读取CSV文件失败: {e}")
        import traceback
        traceback.print_exc()
        return [], None

def generate_message_with_qwen(candidate_data, user_requirement=None):
    """
    使用Qwen模型生成私信内容（仅基于用户要求）
    
    参数:
        candidate_data: 候选人数据字典
        user_requirement: 用户的要求（必需参数）
    
    返回:
        生成的私信内容，失败返回None
    """
    # 从环境变量获取API Key
    api_key = os.getenv("Qwen_API_KEY")
    if not api_key:
        print(f"  -> ✗ 未找到环境变量 Qwen_API_KEY，请设置后重试")
        return None
    
    # 用户要求
    requirement = user_requirement or "生成一条友好、自然的私信内容"
    
    try:
        # 简化的prompt，仅根据用户要求生成私信内容
        prompt = f"""你是一位抖音私信助手，需要帮助生成私信内容。
要求：{requirement}
请根据以上要求生成一段简洁明了的私信内容。仅返回私信内容，不返回其他文字。"""
        
        print(f"\n  -> 正在调用Qwen模型生成私信内容...")
        message = Chat_qwen(
            message=prompt,
            model="qwen3-vl-flash",
            temperature=0.7,
            stream=False,  # 使用非流式，方便获取完整结果
            api_key=api_key  # 传递API Key
        )
        
        if message:
            print(f"  -> ✓ 生成的私信内容: {message[:100]}{'...' if len(message) > 100 else ''}")
            return message.strip()
        else:
            print(f"  -> ✗ Qwen模型返回空内容")
            return None
            
    except Exception as e:
        print(f"  -> ✗ 生成私信内容失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def update_csv_status(filename, user_link, status="Done"):
    """更新CSV文件中指定user_link的状态"""
    try:
        # 读取所有行
        rows = []
        with open(filename, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            
            # 如果没有status列，添加它
            if 'status' not in fieldnames:
                fieldnames = list(fieldnames) + ['status']
            
            for row in reader:
                if row.get('user_link') == user_link:
                    row['status'] = status
                rows.append(row)
        
        # 写回文件
        with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        return True
    except Exception as e:
        print(f"  -> ⚠️ 更新CSV状态失败: {e}")
        return False

def send_message(page, user_link, message, index, total, filename="douyin_candidates.csv", candidate_data=None, user_requirement=None):
    """
    访问用户主页，点击私信按钮，发送AI生成的消息
    
    参数:
        page: Playwright页面对象
        user_link: 用户主页链接
        message: 要发送的消息内容（如果为None，则使用AI根据要求生成）
        index: 当前索引（从1开始）
        total: 总数
        filename: CSV文件名
        candidate_data: 候选人数据
        user_requirement: 用户要求（AI生成私信的依据）
    """
    try:
        print(f"\n[{index}/{total}] 正在处理...")
        print(f"  博主主页: {user_link}")
        
        # 如果没有提供message，尝试使用AI生成
        if message is None and candidate_data:
            user_name = candidate_data.get('user_name', '用户')
            print(f"  用户名: {user_name}")
            message = generate_message_with_qwen(candidate_data, user_requirement)
            if not message:
                print(f"  -> ✗ 无法生成私信内容，跳过此用户")
                return False
        
        # 可能的私信按钮选择器（按优先级排序）
        message_button_selectors = [
            "button.semi-button:has-text('私信')",  # 最精确的选择器
            "button[type='button']:has-text('私信')",
            "button:has-text('私信')",
            "[aria-label*='私信']",
            "div:has-text('私信')",
            "span:has-text('私信')"
        ]
        
        button_found = False
        max_total_retries = 15  # 总共最多15次点击
        retries_per_reload = 5  # 每5次点击后重新加载页面
        total_click_attempts = 0  # 记录总点击次数
        reload_count = 0  # 页面重新加载次数
        
        # 外层循环：每5次点击失败后重新加载页面
        while total_click_attempts < max_total_retries and not button_found:
            # 1. 访问/重新访问博主主页
            if reload_count == 0:
                print("  -> 正在访问博主主页...")
            else:
                print(f"  -> 第 {reload_count + 1} 次重新进入博主主页...")
            
            page.goto(user_link, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(random.randint(3000, 5000))
            reload_count += 1
            
            # 2. 查找并点击私信按钮（每次最多尝试5次）
            print("  -> 正在查找私信按钮...")
            current_round_retries = min(retries_per_reload, max_total_retries - total_click_attempts)
            should_reload_page = False  # 标记是否需要重新加载页面
            
            for selector in message_button_selectors:
                if button_found or total_click_attempts >= max_total_retries or should_reload_page:
                    break
                    
                try:
                    buttons = page.locator(selector).all()
                    print(f"  -> 选择器 '{selector}' 找到 {len(buttons)} 个元素")
                    
                    for idx, button in enumerate(buttons):
                        if button_found or total_click_attempts >= max_total_retries or should_reload_page:
                            break
                            
                        if button.is_visible():
                            print(f"  -> 检查第 {idx+1} 个按钮...")
                            text = button.text_content()
                            if text and "私信" in text:
                                print(f"  -> 找到私信按钮: {selector} (文本: {text.strip()})")
                                
                                # 检查按钮是否被禁用
                                try:
                                    is_disabled = button.get_attribute("aria-disabled")
                                    if is_disabled == "true":
                                        print(f"  -> ⚠️ 按钮被禁用，跳过")
                                        continue
                                except:
                                    pass
                                
                                # 等待页面稳定
                                print(f"  -> 等待页面稳定...")
                                page.wait_for_timeout(random.randint(2000, 3000))
                                
                                # 本轮尝试点击（最多5次）
                                for retry in range(current_round_retries):
                                    if button_found or total_click_attempts >= max_total_retries:
                                        break
                                    
                                    total_click_attempts += 1
                                    print(f"  -> 第 {total_click_attempts}/{max_total_retries} 次尝试点击私信按钮...")
                                    
                                    # 尝试多种点击方式
                                    clicked = False
                                    
                                    # 先悬停到按钮上（有些按钮需要hover才能激活）
                                    try:
                                        button.hover(timeout=2000)
                                        page.wait_for_timeout(300)
                                    except:
                                        pass
                                    
                                    # 方法1：常规点击
                                    if not clicked:
                                        try:
                                            print(f"  -> 尝试常规点击...")
                                            button.click(timeout=5000)
                                            clicked = True
                                            print(f"  -> ✅ 常规点击成功")
                                        except Exception as e:
                                            print(f"  -> 常规点击失败: {str(e)[:50]}")
                                    
                                    # 方法2：强制点击（忽略遮挡）
                                    if not clicked:
                                        try:
                                            print(f"  -> 尝试强制点击...")
                                            button.click(force=True, timeout=5000)
                                            clicked = True
                                            print(f"  -> ✅ 强制点击成功")
                                        except Exception as e:
                                            print(f"  -> 强制点击失败: {str(e)[:50]}")
                                    
                                    # 方法3：JavaScript点击
                                    if not clicked:
                                        try:
                                            print(f"  -> 尝试JavaScript点击...")
                                            button.evaluate("el => el.click()")
                                            clicked = True
                                            print(f"  -> ✅ JavaScript点击成功")
                                        except Exception as e:
                                            print(f"  -> JavaScript点击失败: {str(e)[:50]}")
                                    
                                    # 方法4：通过坐标点击
                                    if not clicked:
                                        try:
                                            print(f"  -> 尝试坐标点击...")
                                            box = button.bounding_box()
                                            if box:
                                                x = box['x'] + box['width'] / 2
                                                y = box['y'] + box['height'] / 2
                                                page.mouse.click(x, y)
                                                clicked = True
                                                print(f"  -> ✅ 坐标点击成功")
                                        except Exception as e:
                                            print(f"  -> 坐标点击失败: {str(e)[:50]}")
                                    
                                    if not clicked:
                                        print("  -> ⚠️ 所有点击方式都失败")
                                        print("  -> 等待1秒后重试...")
                                        page.wait_for_timeout(1000)
                                        continue
                                    
                                    # ========== 每次点击后都进行弹窗检测 ==========
                                    print("  -> 私信按钮已点击，正在检测弹窗...")
                                    page.wait_for_timeout(random.randint(1500, 2500))
                                    
                                    # 验证私信弹窗是否真的出现了
                                    popup_appeared = False
                                    try:
                                        # 检查多种可能的弹窗元素
                                        popup_indicators = [
                                            "textarea[placeholder*='发送消息']",
                                            "input[placeholder*='发送消息']",
                                            "div[contenteditable='true']",
                                            "textarea",
                                            ".chat-list",
                                            "[class*='message-list']",
                                            "[class*='chat']"
                                        ]
                                        
                                        for indicator in popup_indicators:
                                            try:
                                                element = page.locator(indicator).first
                                                if element.is_visible(timeout=2000):
                                                    print(f"  -> ✅ 验证成功：检测到弹窗元素 ({indicator})")
                                                    popup_appeared = True
                                                    break
                                            except:
                                                continue
                                    except:
                                        pass
                                    
                                    # 如果检测到弹窗，立即成功退出
                                    if popup_appeared:
                                        print("  -> ✅ 私信弹窗已成功打开！")
                                        button_found = True
                                        break
                                    else:
                                        # 未检测到弹窗
                                        print(f"  -> ⚠️ 验证失败：弹窗未出现")
                                        
                                        # 检查是否需要重新加载页面
                                        if total_click_attempts % retries_per_reload == 0 and total_click_attempts < max_total_retries:
                                            print(f"  -> 已尝试 {retries_per_reload} 次，将重新进入博主主页...")
                                            should_reload_page = True
                                            break  # 跳出retry循环
                                        elif total_click_attempts < max_total_retries:
                                            print("  -> 将继续点击私信按钮...")
                                            page.wait_for_timeout(1000)
                                        else:
                                            print("  -> 已达到最大点击次数...")
                                
                                if button_found or should_reload_page:
                                    break
                except Exception as e:
                    continue
        
        if not button_found:
            print("  -> ⚠️ 未找到私信按钮，可能需要先关注或此用户不允许私信")
            return False
        
        # 3. 查找消息输入框
        print("  -> 正在查找消息输入框...")
        
        # 可能的输入框选择器
        input_selectors = [
            "textarea[placeholder*='发送消息']",
            "textarea[placeholder*='消息']",
            "input[placeholder*='发送消息']",
            "input[placeholder*='消息']",
            "div[contenteditable='true']",
            "textarea",
            "[data-e2e*='message-input']",
            "[class*='message-input']",
            "[class*='input']"
        ]
        
        input_found = False
        message_input = None
        for selector in input_selectors:
            try:
                inputs = page.locator(selector).all()
                for inp in inputs:
                    if inp.is_visible():
                        print(f"  -> 找到输入框: {selector}")
                        message_input = inp
                        input_found = True
                        break
                if input_found:
                    break
            except:
                continue
        
        if not message_input:
            print("  -> ⚠️ 未找到消息输入框")
            return False
        
        # 4. 输入消息
        print(f"  -> 正在输入消息: {message[:50]}...")
        message_input.click()
        page.wait_for_timeout(500)
        
        # 模拟人类输入，逐字输入
        for char in message:
            message_input.type(char, delay=random.randint(50, 150))
        
        page.wait_for_timeout(random.randint(500, 1000))
        
        # 5. 按Enter键发送消息
        print("  -> 按Enter键发送消息...")
        try:
            page.keyboard.press("Enter")
            page.wait_for_timeout(random.randint(1000, 2000))
            print("  -> ✅ 消息发送成功")
            
            # 更新CSV文件，标记为Done
            print("  -> 更新CSV文件状态...")
            if update_csv_status(filename, user_link, "Done"):
                print("  -> ✅ CSV状态已更新为Done")
            
        except Exception as e:
            print(f"  -> ✗ 发送失败: {e}")
            return False
        
        # 等待一段时间再处理下一个（避免被限制）
        wait_time = random.randint(1000, 3000)
        print(f"  -> 等待 {wait_time/1000:.1f} 秒后继续...")
        page.wait_for_timeout(wait_time)
        
        return True
        
    except Exception as e:
        print(f"  -> ✗ 发送消息失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_messenger(csv_path="douyin_candidates.csv", user_requirement=None):
    """
    运行私信发送程序（基于AI生成）
    
    参数:
        csv_path: CSV文件路径（仅需包含 user_link 字段）
        user_requirement: 用户要求（用于生成私信内容，如：邀请对方加入我们的招聘群）
    """
    # 加载 .env 文件中的环境变量
    load_dotenv()
    print("✓ 已加载 .env 文件中的环境变量")
    
    filename = csv_path
    
    # 读取CSV文件
    candidates, csv_type = read_candidates_csv(filename)
    
    if not candidates:
        print("没有找到待发送的数据")
        return
    
    # 如果未提供用户要求，提示用户输入
    if not user_requirement:
        print("\n请输入私信生成要求（AI将根据此要求生成个性化私信）：")
        user_requirement = input("要求 (例如：邀请对方加入我们的招聘群，提供兼职机会): ").strip()
        if not user_requirement:
            user_requirement = "生成一条友好、自然的私信内容"
            print(f"未输入要求，使用默认要求：{user_requirement}")
    
    print(f"\n准备向 {len(candidates)} 位用户发送AI生成的私信")
    print(f"生成要求: {user_requirement}")
    print(f"提示: AI将为每位用户生成个性化的私信内容")
    # confirm = input("是否继续？(y/n): ") # GUI模式下不需要再次确认
    # if confirm.lower() != 'y':
    #     print("已取消")
    #     return
    
    print("\n正在启动浏览器...")
    with sync_playwright() as playwright:
        browser, context, page = init_browser(playwright)
        
        try:
            success_count = 0
            fail_count = 0
            
            for i, candidate in enumerate(candidates, 1):
                # 使用AI生成私信内容
                result = send_message(
                    page, 
                    candidate['user_link'], 
                    None,  # message参数设为None，由AI生成
                    i,
                    len(candidates),
                    filename,
                    candidate_data=candidate,
                    user_requirement=user_requirement
                )
                
                if result:
                    success_count += 1
                else:
                    fail_count += 1
            
            print("\n" + "="*50)
            print("发送完成统计:")
            print(f"  成功: {success_count}")
            print(f"  失败: {fail_count}")
            print(f"  总计: {len(candidates)}")
            print("="*50)
            
        finally:
            # input("\n按回车键关闭浏览器...") # GUI模式下不需要
            # 关闭浏览器（持久化模式下 browser 为 None）
            try:
                if browser:
                    browser.close()
                else:
                    context.close()
            except:
                pass

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description='抖音私信发送工具 - 使用AI根据要求生成个性化私信内容',
        epilog='示例: python douyin_messenger.py douyin_comments.csv -r "邀请对方加入我们的招聘群"'
    )
    parser.add_argument('csv_file', nargs='?', default="douyin_candidates.csv", 
                        help='CSV文件路径（需包含 user_link 字段）')
    parser.add_argument('--requirement', '-r', type=str, 
                        help='私信生成要求（例如：邀请对方加入我们的招聘群，提供兼职机会）')
    args = parser.parse_args()
    
    run_messenger(args.csv_file, user_requirement=args.requirement)

