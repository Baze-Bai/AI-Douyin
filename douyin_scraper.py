import time
import random
import os
import csv
import re
from datetime import datetime
from playwright.sync_api import sync_playwright
from qwen_analyzer import analyze_with_qwen
from browser_utils import detect_browser_config, get_playwright_launch_args, configure_bundled_browsers

def init_browser(playwright, user_data_dir="Chrome_data"):
    """
    初始化浏览器，使用持久化上下文保存登录状态
    
    参数:
        playwright: Playwright 实例
        user_data_dir: Chrome 用户数据目录（默认 Chrome_data）
    """
    launch_config = get_playwright_launch_args(headless=False)
    launch_args = launch_config["args"]
    
    # 确保用户数据目录是绝对路径
    if user_data_dir and not os.path.isabs(user_data_dir):
        user_data_dir = os.path.join(os.getcwd(), user_data_dir)
    
    # 检测最佳浏览器
    browser_type, specific_kwargs, browser_name = detect_browser_config(playwright)
    
    if user_data_dir:
        # 创建目录（如果不存在）
        try:
            os.makedirs(user_data_dir, exist_ok=True)
            print(f"✓ 使用持久化会话目录: {user_data_dir}")
        except Exception as e:
            print(f"⚠️ 创建目录失败: {e}")
        
        # 使用持久化上下文启动
        try:
            print(f"正在启动 {browser_name} (持久化模式)...")
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
            return None, context, page  # 持久化模式下 browser 为 None
            
        except Exception as e:
            print(f"⚠️ {browser_name} 持久化模式启动失败: {e}")
            print("⚠️ 降级到临时会话模式...")
            
            # 如果是Firefox且失败，可能需要清理lock文件？
            # 暂时忽略，直接降级
    
    # 降级方案：临时会话
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
            print("尝试使用 Playwright 内置 Chromium...")
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

def search_douyin(page, keyword):
    print(f"正在打开抖音并搜索: {keyword}")
    try:
        # 访问抖音首页
        print("正在访问抖音首页...")
        page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=60000)
        
        # 等待页面稳定
        print("等待页面加载...")
        page.wait_for_timeout(random.randint(3000, 5000))
        
        # 尝试多种搜索框选择器
        search_selectors = [
            "input[type='search']",
            "input[placeholder*='搜索']",
            "input[class*='search']",
            "input[data-e2e*='search']",
            "#search-input",
            ".search-input"
        ]
        
        search_input = None
        print("正在查找搜索框...")
        
        for selector in search_selectors:
            try:
                # 等待元素出现
                page.wait_for_selector(selector, timeout=5000, state="visible")
                search_input = page.locator(selector).first
                
                # 验证元素是否可见且可用
                if search_input.is_visible():
                    print(f"✓ 找到搜索框: {selector}")
                    break
            except:
                continue
        
        if not search_input:
            print("✗ 未找到搜索框，尝试直接使用URL搜索...")
            # 备用方案：直接访问搜索结果页
            search_url = f"https://www.douyin.com/search/{keyword}"
            page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)
            print("✓ 已通过URL直接进入搜索结果页")
            return True
        
        # 点击搜索框
        print("正在输入搜索关键词...")
        search_input.click(timeout=10000)
        page.wait_for_timeout(500)
        
        # 清空并输入关键词
        search_input.fill(keyword)
        page.wait_for_timeout(random.randint(500, 1500))
        
        # 按回车搜索
        print("正在执行搜索...")
        page.keyboard.press("Enter")
        
        print("搜索完成，等待结果加载...")
        page.wait_for_timeout(random.randint(3000, 5000))
        
        print("✓ 搜索成功")
        return True
        
    except Exception as e:
        print(f"✗ 搜索过程中出错: {e}")
        print("尝试使用备用搜索方案...")
        
        try:
            # 最终备用方案：直接访问搜索结果页
            search_url = f"https://www.douyin.com/search/{keyword}"
            print(f"正在访问: {search_url}")
            page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)
            print("✓ 备用搜索方案成功")
            return True
        except Exception as e2:
            print(f"✗ 备用搜索方案也失败: {e2}")
            return False

def close_intro_modal(page):
    """检测并关闭抖音的新手引导提示框（"我知道了"按钮）"""
    try:
        # 快速检测，不等待
        pass
        
        # 可能的"我知道了"按钮选择器
        button_selectors = [
            'button:has-text("我知道了")',
            'button:has-text("知道了")',
            'div:has-text("我知道了")',
            '[class*="modal"] button',
            '[class*="dialog"] button',
            'button[class*="confirm"]',
            'button[class*="close"]'
        ]
        
        for selector in button_selectors:
            try:
                # 查找按钮
                buttons = page.query_selector_all(selector)
                for button in buttons:
                    if button.is_visible():
                        text = button.text_content().strip()
                        # 检查是否包含"知道了"相关文字
                        if "知道了" in text or "我知道了" in text:
                            print(f"  -> 检测到引导提示，点击关闭: {text}")
                            button.click()
                            page.wait_for_timeout(500)
                            return True
            except:
                continue
        
        # 没有找到提示框
        return False
    except Exception as e:
        print(f"  -> 检测提示框时出错: {e}")
        return False

def click_avatar_and_get_profile(page, original_video_url):
    """点击视频页面右上角的头像，跳转到博主主页并获取链接"""
    try:
        print("  -> 正在查找并点击博主头像...")
        
        # 可能的头像选择器（根据实际HTML结构）
        avatar_selectors = [
            "span[data-e2e='live-avatar']",  # 最精确的选择器
            "span[data-e2e='live-avatar'] img",  # 头像图片本身
            ".avatar-component-avatar-container",  # 通过类名定位
            "span[class*='avatar-component-avatar-container']",
            "div[data-e2e='video-avatar']",  # 备用选择器
            "a[data-e2e='video-avatar']",
            "img[class*='avatar']",
            "[class*='user-avatar']",
            "div[class*='author'] img"
        ]
        
        avatar_clicked = False
        for selector in avatar_selectors:
            try:
                avatars = page.query_selector_all(selector)
                if len(avatars) == 0:
                    continue
                    
                print(f"  -> 尝试选择器: {selector} (找到 {len(avatars)} 个元素)")
                
                for idx, avatar in enumerate(avatars):
                    try:
                        if not avatar.is_visible():
                            continue
                        
                        print(f"  -> 找到可见头像元素 [{idx+1}]: {selector}")
                        
                        # 滚动到元素可见位置
                        try:
                            avatar.scroll_into_view_if_needed(timeout=2000)
                            page.wait_for_timeout(300)
                        except:
                            pass
                        
                        # 尝试点击头像
                        avatar.click(timeout=3000)
                        print(f"  -> ✅ 点击头像成功")
                        page.wait_for_timeout(100)  # 等待页面响应 0.1秒
                        
                        # 点击头像后再次暂停视频
                        print(f"  -> 再次暂停视频...")
                        try:
                            # 连续按三次空格键，确保视频暂停
                            for pause_attempt in range(3):
                                page.keyboard.press("Space")
                                if pause_attempt < 2:  # 最后一次按完不需要等待
                                    page.wait_for_timeout(500)
                        except:
                            pass
                        
                        avatar_clicked = True
                        break
                        
                    except Exception as e:
                        print(f"  -> 点击元素 [{idx+1}] 失败: {str(e)[:50]}")
                        continue
                
                if avatar_clicked:
                    break
            except Exception as e:
                print(f"  -> 选择器 {selector} 处理出错: {str(e)[:50]}")
                continue
        
        if not avatar_clicked:
            print("  -> ⚠️ 未能点击头像，尝试直接提取链接")
            return extract_user_profile_url(page)
        
        # 点击成功后，等待页面更新并提取博主链接
        print("  -> 正在提取博主主页链接...")
        page.wait_for_timeout(2000)  # 等待页面响应和内容加载
        
        # 尝试从页面中提取博主链接
        user_link = extract_user_profile_url(page)
        
        if user_link:
            print(f"  -> ✅ 成功获取博主主页: {user_link}")
        else:
            print(f"  -> ⚠️ 未能提取到博主主页链接")
        
        # 按 ESC 键关闭信息卡片
        try:
            print(f"  -> 按 ESC 键关闭信息卡片...")
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)  # 等待关闭动画
        except Exception as e:
            print(f"  -> 关闭信息卡片失败: {e}")
        
        return user_link
        
    except Exception as e:
        print(f"  -> 点击头像失败: {e}")
        import traceback
        traceback.print_exc()
        return extract_user_profile_url(page)

def extract_user_profile_url(page):
    """提取当前视频页面中的博主主页链接（备用方法）"""
    try:
        user_link = None
        import re
        
        # 策略0: 查找点击头像后出现的博主主页链接（最优先）
        # 特征: target="_blank" 和 rel="noopener noreferrer" 且包含 /user/
        try:
            print("  -> [策略0] 查找带 target='_blank' 的博主链接...")
            blank_links = page.query_selector_all("a[target='_blank'][rel*='noreferrer'][href*='/user/']")
            print(f"  -> 找到 {len(blank_links)} 个符合条件的链接")
            
            for idx, link in enumerate(blank_links):
                try:
                    href = link.get_attribute("href")
                    if href and "/user/" in href:
                        # 处理各种URL格式
                        if href.startswith("//"):
                            # 协议相对URL: //www.douyin.com/user/...
                            href = "https:" + href
                        elif href.startswith("/"):
                            # 路径相对URL: /user/...
                            href = "https://www.douyin.com" + href
                        elif not href.startswith("http"):
                            # 其他格式
                            href = "https://www.douyin.com/" + href
                        
                        # 清理链接
                        match = re.search(r'(https?://[^/]+/user/MS4wLjABAAAA[A-Za-z0-9_-]+)', href)
                        if not match:
                            match = re.search(r'(https?://[^/]+/user/[^?&#\s]+)', href)
                        
                        if match:
                            user_link = match.group(1)
                            if idx < 3:
                                print(f"    [{idx+1}] {user_link}")
                            
                            if "/user/MS4wLjABAAAA" in user_link:
                                print(f"  -> [策略0] ✅ 提取到博主主页: {user_link}")
                                return user_link
                except:
                    continue
        except Exception as e:
            print(f"  -> [策略0] 执行失败: {e}")
        
        # 策略1: 查找作者信息区域的链接
        author_selectors = [
            "a[data-e2e='video-author-name']",
            "a[data-e2e='video-avatar']",
            "a[class*='author']",
            "div[class*='author'] a",
            "div[class*='user'] a",
            ".account-card a",
            "[class*='video-info'] a[href*='/user/']"
        ]
        
        for selector in author_selectors:
            try:
                links = page.query_selector_all(selector)
                for link in links:
                    href = link.get_attribute("href")
                    if href and "/user/" in href:
                        # 处理各种URL格式
                        if href.startswith("//"):
                            # 协议相对URL: //www.douyin.com/user/...
                            href = "https:" + href
                        elif href.startswith("/"):
                            # 路径相对URL: /user/...
                            href = "https://www.douyin.com" + href
                        elif not href.startswith("http"):
                            # 其他格式
                            href = "https://www.douyin.com/" + href
                        
                        # 清理链接，只保留到用户ID为止
                        match = re.search(r'(https?://[^/]+/user/MS4wLjABAAAA[A-Za-z0-9_-]+)', href)
                        if not match:
                            match = re.search(r'(https?://[^/]+/user/[^?&#\s]+)', href)
                        
                        if match:
                            user_link = match.group(1)
                            print(f"  -> [策略1] 通过 {selector} 提取到博主主页: {user_link}")
                            return user_link
            except:
                continue
        
        # 策略2: 从当前页面 URL 中提取（如果当前就在视频页）
        try:
            current_url = page.url
            if "/user/" in current_url:
                # URL 格式: https://www.douyin.com/user/MS4wLjABAAAA...?xxx
                # 优先匹配标准格式
                match = re.search(r'(https?://[^/]+/user/MS4wLjABAAAA[A-Za-z0-9_-]+)', current_url)
                if not match:
                    # 备用：匹配任何 /user/ 格式
                    match = re.search(r'(https?://[^/]+/user/[^?&#\s]+)', current_url)
                if match:
                    user_link = match.group(1)
                    print(f"  -> [策略2] 从当前URL提取到博主主页: {user_link}")
                    return user_link
        except:
            pass
        
        # 策略3: 查找所有 /user/ 链接（最后的备用方案）
        try:
            print("  -> [策略3] 查找所有 /user/ 链接...")
            links = page.query_selector_all("a[href*='/user/']")
            print(f"  -> 找到 {len(links)} 个包含 /user/ 的链接")
            
            for idx, link in enumerate(links):
                try:
                    href = link.get_attribute("href")
                    if href and "/user/" in href:
                        # 处理各种URL格式
                        if href.startswith("//"):
                            # 协议相对URL: //www.douyin.com/user/...
                            href = "https:" + href
                        elif href.startswith("/"):
                            # 路径相对URL: /user/...
                            href = "https://www.douyin.com" + href
                        elif not href.startswith("http"):
                            # 其他格式
                            href = "https://www.douyin.com/" + href
                        
                        # 清理链接，提取标准格式
                        match = re.search(r'(https?://[^/]+/user/MS4wLjABAAAA[A-Za-z0-9_-]+)', href)
                        if not match:
                            match = re.search(r'(https?://[^/]+/user/[^?&#\s]+)', href)
                        
                        if match:
                            user_link = match.group(1)
                            # 打印前3个链接供调试
                            if idx < 3:
                                print(f"    [{idx+1}] {user_link}")
                            
                            # 验证链接格式
                            if "/user/MS4wLjABAAAA" in user_link:
                                print(f"  -> [策略3] 提取到博主主页: {user_link}")
                                return user_link
                except:
                    continue
        except:
            pass
        
        print("  -> ❌ 未提取到博主主页链接")
        return None
            
    except Exception as e:
        print(f"  -> 提取博主链接失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_user_info(page, user_link):
    """访问博主主页并提取名字和IP地址
    
    Args:
        page: Playwright page 对象
        user_link: 博主主页链接
    
    Returns:
        dict: {'user_name': str, 'user_ip': str}
    """
    try:
        print(f"  -> 正在访问博主主页: {user_link}")
        
        # 在新标签页中打开博主主页
        user_page = page.context.new_page()
        user_page.goto(user_link, wait_until="domcontentloaded", timeout=30000)
        user_page.wait_for_timeout(3000)  # 等待页面完全加载
        
        # 尝试等待用户信息区域加载
        try:
            user_page.wait_for_selector("[class*='user']", timeout=5000)
        except:
            pass
        
        user_name = ""
        user_ip = ""
        
        # 提取博主名字
        name_selectors = [
            "span.OcCvrt2a",  # 根据源码提供的class
            "[data-e2e='user-info'] [data-e2e='user-title']",
            "h1.GMEdHzXq",  # 另一个可能的名字class
            "[class*='user-info'] span[class*='title']",
            "h1[class*='name']",
            ".account-card .name",
            "[class*='username']",
            "span[title]",  # 名字通常带有title属性
            "h1"
        ]
        
        for selector in name_selectors:
            try:
                elements = user_page.query_selector_all(selector)
                for el in elements:
                    if el.is_visible():
                        text = el.text_content()
                        if text and text.strip() and len(text.strip()) > 0:
                            # 排除一些无关文本
                            text = text.strip()
                            if text and text != "IP属地" and "关注" not in text and "粉丝" not in text:
                                user_name = text
                                print(f"  -> 提取到博主名字: {user_name}")
                                break
                if user_name:
                    break
            except:
                continue
        
        # 提取IP地址（地理位置信息）
        ip_selectors = [
            "span.DttGrR",  # 根据源码提供的class: IP属地：四川
            "span.arnSiSbK",  # 另一个可能的IP class
            "span.eTvkrF8I",  # 备用选择器
            "[data-e2e='user-info'] span:has-text('IP属地')",
            "[class*='ip-location']",
            "[class*='location']",
            "span:has-text('IP属地')"
        ]
        
        # 首先尝试通过具体的class选择器
        for selector in ip_selectors:
            try:
                elements = user_page.query_selector_all(selector)
                for el in elements:
                    if el.is_visible():
                        text = el.text_content()
                        if text and text.strip():
                            # 清理文本，提取IP属地
                            text = text.strip()
                            if "IP属地" in text:
                                # 提取 "IP属地：XXX" 或 "IP属地·XXX" 中的地名
                                user_ip = text.replace("IP属地", "").replace("：", "").replace(":", "").replace("·", "").strip()
                            elif text and len(text) <= 10 and not any(char.isdigit() for char in text):
                                # 可能是纯省份名，且不包含数字
                                user_ip = text
                            
                            if user_ip:
                                print(f"  -> 提取到IP属地: {user_ip} (使用选择器: {selector})")
                                break
                if user_ip:
                    break
            except:
                continue
        
        # 如果上面没找到，尝试正则表达式匹配整个页面
        if not user_ip:
            try:
                # 获取页面所有文本，查找"IP属地"相关信息
                page_text = user_page.content()
                # 匹配 "IP属地：XXX" 或 "IP属地·XXX" 格式
                ip_match = re.search(r'IP属地[：:·\s]+([^<>\s,]+)', page_text)
                if ip_match:
                    user_ip = ip_match.group(1).strip()
                    print(f"  -> 提取到IP属地: {user_ip} (使用正则表达式)")
            except:
                pass
        
        # 如果信息提取失败，保存调试截图
        if not user_name or not user_ip:
            try:
                debug_dir = "screenshots/debug"
                os.makedirs(debug_dir, exist_ok=True)
                debug_screenshot = os.path.join(debug_dir, f"user_page_debug_{int(time.time())}.png")
                user_page.screenshot(path=debug_screenshot)
                print(f"  -> 已保存调试截图: {debug_screenshot}")
            except:
                pass
        
        # 关闭博主主页
        user_page.close()
        
        if not user_name:
            user_name = "未获取"
            print(f"  -> ⚠️ 未能提取到博主名字")
        
        if not user_ip:
            user_ip = "未获取"
            print(f"  -> ⚠️ 未能提取到IP属地")
        
        return {
            'user_name': user_name,
            'user_ip': user_ip
        }
        
    except Exception as e:
        print(f"  -> 获取博主信息失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            'user_name': '获取失败',
            'user_ip': '获取失败'
        }

def save_to_csv(contact_info, filename="douyin_videos.csv"):
    """保存单条联系人信息到CSV"""
    # 确保目录存在
    directory = os.path.dirname(filename)
    if directory and not os.path.exists(directory):
        try:
            os.makedirs(directory, exist_ok=True)
        except:
            pass
            
    file_exists = os.path.isfile(filename)
    
    try:
        with open(filename, mode='a', newline='', encoding='utf-8-sig') as f:
            fieldnames = ['user_name', 'user_ip', 'user_link', 'video_url', 'video_text', 'screenshot_path']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()
            
            writer.writerow({
                'user_name': contact_info.get('user_name', ''),
                'user_ip': contact_info.get('user_ip', ''),
                'user_link': contact_info.get('user_link', ''),
                'video_url': contact_info.get('video_url', ''),
                'video_text': contact_info.get('video_text', ''),
                'screenshot_path': contact_info.get('screenshot_path', '')
            })
            print(f"  -> 数据已保存到 {filename}")
    except Exception as e:
        print(f"  -> 保存CSV失败: {e}")

def collect_video_data(page, condition, max_videos=5, csv_filename="douyin_videos.csv"):
    video_data = []
    contact_list = []
    
    try:
        print("正在识别视频卡片（矩形边框）...")
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass
        
        # 尝试定位视频卡片
        valid_cards = []
        potential_locators = [
            "[data-e2e*='search-card']", 
            "[data-e2e*='item']",
            "ul li", 
            ".video-card"
        ]
        
        for selector in potential_locators:
            cards = page.locator(selector).all()
            if len(cards) > 0:
                for card in cards:
                    try:
                        if card.is_visible():
                            box = card.bounding_box()
                            if box and box['width'] > 100 and box['height'] > 100:
                                valid_cards.append(card)
                    except:
                        continue
                if len(valid_cards) > 2:
                    print(f"使用选择器 '{selector}' 识别到 {len(valid_cards)} 个卡片")
                    break
                else:
                    valid_cards = []
        
        if not valid_cards:
            print("未找到标准卡片结构，尝试识别视频封面图片...")
            imgs = page.locator("img").all()
            for img in imgs:
                try:
                    if img.is_visible():
                         box = img.bounding_box()
                         if box and box['width'] > 150 and box['height'] > 100:
                             valid_cards.append(img)
                except:
                    continue
            print(f"识别到 {len(valid_cards)} 个封面图片")

        if not valid_cards:
            print("未能识别到视频卡片或边框。")
            return []

        print(f"准备点击第一个视频，并通过键盘切换采集，目标筛选出 {max_videos} 个符合条件的博主...")
        
        card = valid_cards[0]
        video_page = None
        
        try:
            # 1. 点击第一个视频
            print("正在点击第一个卡片...")
            card.evaluate("el => el.scrollIntoView({block: 'center', inline: 'nearest'})")
            page.wait_for_timeout(1000)
            
            # 尝试检测是否会打开新标签页
            try:
                # 设置短超时，快速检测是否有新页面
                with page.context.expect_page(timeout=3000) as new_page_info:
                    card.click(force=True)
                
                video_page = new_page_info.value
                print("  -> 新窗口已打开，等待加载...")
                video_page.wait_for_load_state("domcontentloaded")
                video_page.wait_for_timeout(500)  # 等待0.5秒
            except:
                # 如果没有新标签页，说明是当前页面跳转
                print("  -> 在当前页面跳转...")
                video_page = page
                page.wait_for_timeout(500)  # 等待0.5秒

            # 检测并关闭可能的引导提示框
            print("  -> 检测页面引导提示...")
            close_intro_modal(video_page)

            # 创建截图目录
            screenshot_dir = "screenshots"
            os.makedirs(screenshot_dir, exist_ok=True)

            # 2. 循环采集视频，直到筛选出足够数量的博主
            video_count = 0  # 已处理的视频数量
            success_count = 0  # 成功筛选出的博主数量
            max_attempts = max_videos * 10  # 最多尝试的视频数量（防止无限循环）
            
            while success_count < max_videos and video_count < max_attempts:
                video_count += 1
                print(f"\n[视频 {video_count}] [已筛选 {success_count}/{max_videos}] 正在处理当前视频...")
                
                # 只在第一个视频时暂停（后续视频在切换时已暂停）
                if video_count == 1:
                    print("  -> 暂停视频...")
                    try:
                        # 连续按三次空格键，确保视频暂停
                        for pause_attempt in range(3):
                            video_page.keyboard.press("Space")
                            if pause_attempt < 2:  # 最后一次按完不需要等待
                                video_page.wait_for_timeout(500)
                    except Exception as e:
                        print(f"  -> 暂停失败，继续: {e}")
                    
                    # 暂停后等待界面稳定
                    print("  -> 等待界面稳定...")
                    video_page.wait_for_timeout(random.randint(1500, 2000))
                
                # --- 提取文字描述 ---
                desc_selectors = [
                    "[data-e2e='video-desc']",
                    ".desc-wrapper span",
                    "h1",
                    ".video-info-container",
                    "div[class*='desc']",
                    "span[class*='desc']"
                ]
                
                text_content = ""
                for _ in range(3): 
                    for selector in desc_selectors:
                        try:
                            elements = video_page.query_selector_all(selector)
                            for el in elements:
                                if el.is_visible():
                                    text = el.text_content()
                                    if text and text.strip():
                                        text_content = text.strip()
                                        break
                            if text_content:
                                break
                        except:
                            continue
                    if text_content:
                        break
                    video_page.wait_for_timeout(500)
                
                current_url = video_page.url
                if not text_content:
                    text_content = "未提取到文字"
                
                display_text = text_content[:50].replace('\n', ' ') + "..." if len(text_content) > 50 else text_content.replace('\n', ' ')
                print(f"  -> 提取到的文字: {display_text}")
                
                # 等待界面完全稳定后再截图
                print("  -> 准备截图，等待界面稳定...")
                video_page.wait_for_timeout(random.randint(100, 200))
                
                # --- 截图 ---
                screenshot_path = os.path.join(screenshot_dir, f"video_{video_count}_{int(time.time())}.png")
                try:
                    video_page.screenshot(path=screenshot_path)
                    print(f"  -> 截图已保存: {screenshot_path}")
                except Exception as e:
                    print(f"  -> 截图失败: {e}")
                    screenshot_path = None

                # --- 调用 Qwen 分析 ---
                if screenshot_path:
                    print("  -> 正在调用 Qwen 分析内容...")
                    analysis_result = analyze_with_qwen(text_content, condition, screenshot_path)
                    print(f"  -> AI分析结果: {analysis_result}")
                    
                    # 判断返回值是否为 True（字符串）
                    should_contact = False
                    if isinstance(analysis_result, str):
                        should_contact = analysis_result.strip().lower() == "true"
                    
                    if should_contact:
                        print("  -> [判定] ✅ 需要联系该博主")
                        
                        # 点击头像并提取博主链接
                        user_link = click_avatar_and_get_profile(video_page, current_url)
                        if user_link:
                            # 立即访问博主主页获取名字和IP
                            user_info = get_user_info(video_page, user_link)
                            
                            contact_info = {
                                "user_name": user_info['user_name'],
                                "user_ip": user_info['user_ip'],
                                "user_link": user_link,
                                "video_url": current_url,
                                "video_text": text_content,
                                "screenshot_path": screenshot_path
                            }
                            contact_list.append(contact_info)
                            success_count += 1  # 成功筛选出一个博主
                            print(f"  -> ✅ 已加入待联系列表 (第 {success_count}/{max_videos} 个): {user_info['user_name']} ({user_link})")
                            
                            # 实时保存到CSV，防止程序中断丢失数据
                            save_to_csv(contact_info, filename=csv_filename)
                        else:
                            print(f"  -> ⚠️ 提取博主链接失败，继续下一个视频")
                    else:
                        print("  -> [判定] ❌ 不需联系，继续下一个视频")
                        
                    # 截图已保存，不进行清理
                
                # --- 切换到下一个视频 ---
                # 如果已经达到目标数量，提前结束
                if success_count >= max_videos:
                    print(f"\n✓ 已成功筛选出 {success_count} 个博主，达到目标数量！")
                    break
                
                # 如果还没达到目标，切换到下一个视频
                if success_count < max_videos:
                    # 保存当前URL，用于检测是否成功切换
                    old_url = current_url
                    old_text = text_content
                    
                    print("  -> 按下 ↓ 键切换视频...")
                    video_page.keyboard.press("ArrowDown")
                    
                    # 立刻暂停新视频
                    video_page.wait_for_timeout(100)  # 短暂等待200ms让视频开始播放
                    print("  -> 立即暂停新视频...")
                    # 连续按三次空格键，确保视频暂停
                    for pause_attempt in range(3):
                        video_page.keyboard.press("Space")
                        if pause_attempt < 2:  # 最后一次按完不需要等待
                            video_page.wait_for_timeout(500)
                    
                    # 检测并关闭新视频可能出现的引导提示框
                    print("  -> 检测新视频的引导提示...")
                    close_intro_modal(video_page)
                    
                    # 暂停后等待页面DOM更新
                    print("  -> 等待页面DOM更新...")
                    video_page.wait_for_timeout(random.randint(2000, 3000))
                    
                    # 等待新视频的内容加载，检测文本是否变化
                    print("  -> 等待新视频内容加载...")
                    for content_check in range(5):  # 最多检查5次
                        video_page.wait_for_timeout(800)
                        # 尝试读取当前视频描述，看是否与上一个不同
                        try:
                            test_elem = video_page.query_selector("[data-e2e='video-desc']")
                            if test_elem:
                                test_text = test_elem.text_content()
                                if test_text and test_text.strip() != old_text:
                                    print(f"  -> ✓ 检测到新内容已加载")
                                    break
                        except:
                            pass
                        if content_check == 4:
                            print(f"  -> ⚠️ 内容可能未更新，但继续处理")
                    
                    # 额外等待确保界面完全稳定
                    video_page.wait_for_timeout(1000)
            
            print("\n" + "="*50)
            print(f"视频采集完成")
            print(f"总共处理视频数: {video_count}")
            print(f"成功筛选博主数: {success_count}")
            print("="*50)
            
            # 如果是新窗口，关闭它
            if video_page != page:
                print("关闭视频窗口...")
                video_page.close()
            
        except Exception as e:
            print(f"  -> 点击或处理过程中出错: {e}")
            # 如果是新窗口且未关闭，关闭它
            if video_page and video_page != page:
                try:
                    if not video_page.is_closed():
                        video_page.close()
                except:
                    pass
                
    except Exception as e:
        print(f"搜集数据过程中出错: {e}")
        
    return contact_list

def run_scraper(keyword, condition, max_count=5, csv_filename="douyin_videos.csv"):
    print("正在启动浏览器...")
    with sync_playwright() as playwright:
        browser, context, page = init_browser(playwright)
        
        try:
            if search_douyin(page, keyword):
                contact_list = collect_video_data(page, condition, max_videos=max_count, csv_filename=csv_filename)
                
                print("\n" + "="*50)
                print("最终筛选出的意向博主列表:")
                print("="*50)
                if contact_list:
                    for idx, item in enumerate(contact_list, 1):
                        print(f"[{idx}] 博主名字: {item['user_name']}")
                        print(f"    IP属地: {item['user_ip']}")
                        print(f"    博主链接: {item['user_link']}")
                        print(f"    视频链接: {item['video_url']}")
                        print(f"    视频文案: {item['video_text'][:50]}..." if len(item['video_text']) > 50 else f"    视频文案: {item['video_text']}")
                        print(f"    截图路径: {item['screenshot_path']}")
                        print()
                    print(f"✓ 数据已保存到: {csv_filename}")
                else:
                    print("没有找到符合条件的博主。")
                print(f"✓ 所有视频截图已保存到: screenshots/ 文件夹")
                print("="*50)
            else:
                print("⚠️ 搜索失败，请检查网络连接或登录状态。")
                
        finally:
            # 采集完成
            print("\n✓ 采集完成！")
            # GUI模式下不需要等待用户输入
            # 关闭浏览器（持久化模式下 browser 为 None）
            print("正在关闭浏览器...")
            try:
                if browser:
                    browser.close()
                else:
                    context.close()
            except:
                pass

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='抖音视频爬虫')
    parser.add_argument('keyword', nargs='?', help='搜索关键词')
    parser.add_argument('condition', nargs='?', help='筛选条件')
    parser.add_argument('count', nargs='?', type=int, help='目标筛选出的博主数量（达到此数量后停止）')
    args = parser.parse_args()

    if args.keyword:
        keyword = args.keyword
    else:
        keyword = input("请输入搜索关键词: ")
    
    if args.condition:
        condition = args.condition
    else:
        condition = input("请输入筛选条件 (例如: 视频内容是否与美食相关): ")
    
    if args.count is not None:
        count = args.count
    else:
        try:
            count = int(input("请输入目标筛选出的博主数量 (默认5，程序将持续处理视频直到达到此数量): ") or 5)
        except:
            count = 5
    
    # 生成带日期的文件名
    current_date = datetime.now().strftime("%Y-%m-%d")
    csv_filename = f"douyin_videos_{current_date}.csv"

    run_scraper(keyword, condition, count, csv_filename)
