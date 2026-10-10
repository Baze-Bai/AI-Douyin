import time
import random
import os
import csv
from datetime import datetime
from playwright.sync_api import sync_playwright
from browser_utils import launch_browser_with_fallback, get_playwright_launch_args, detect_browser_config, configure_bundled_browsers

from qwen_analyzer import analyze_with_qwen

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
                viewport={'width': 1500, 'height': 700},
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

def search_douyin(page, keyword):
    """搜索抖音关键词"""
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

def click_comment_button(page):
    """点击评论按钮，展开评论区"""
    try:
        print("  -> 正在查找评论按钮...")
        
        # 使用精确的评论按钮选择器
        selector = "[data-e2e='feed-comment-icon']"
        
        try:
            elements = page.query_selector_all(selector)
            for element in elements:
                if element.is_visible():
                    print(f"  -> 找到评论按钮")
                    # 尝试滚动到元素可见
                    try:
                        element.scroll_into_view_if_needed(timeout=2000)
                        page.wait_for_timeout(300)
                    except:
                        pass
                    
                    element.click(timeout=5000)
                    page.wait_for_timeout(2000)  # 等待评论区展开
                    print("  -> ✅ 评论按钮点击成功")
                    return True
        except Exception as e:
            print(f"  -> 查找评论按钮时出错: {e}")
        
        print("  -> ⚠️ 未找到评论按钮")
        return False
        
    except Exception as e:
        print(f"  -> 点击评论按钮失败: {e}")
        return False

def expand_all_buttons_in_view(page, show_summary=True):
    """检测并点击当前视图内所有"展开n条回复"和"展开更多"按钮
    
    参数:
        page: 页面对象
        show_summary: 是否显示统计信息
    
    返回:
        (reply_count, more_count): 回复按钮数量和展开更多按钮数量
    """
    try:
        # 根据源码结构，按钮选择器
        # 同时匹配"展开n条回复"和"展开更多"
        expand_selectors = [
            "button.AlC_XilC",  # 精确class（两种按钮共用）
            "button:has-text('展开')",  # 包含"展开"文本的按钮
            "button[class*='AlC_']",  # 模糊匹配
            "div.bgzSRRCZ",  # 按钮内部容器
        ]
        
        reply_count = 0  # "展开n条回复"按钮数量
        more_count = 0   # "展开更多"按钮数量
        
        # 限制每次只点击一个按钮，然后立即返回，以便程序能继续滚动
        # 尝试多次查找，直到找到一个可点击的按钮
        
        # 打印进度点
        if not show_summary:
            print('.', end='', flush=True)

        for selector in expand_selectors:
            try:
                # 查找所有匹配的按钮
                buttons = page.query_selector_all(selector)
                
                for button in buttons:
                    try:
                        # 检查按钮是否可见
                        if button.is_visible():
                            button_text = button.text_content().strip()
                            
                            # 判断按钮类型：
                            # 1. "展开更多" 或 "展开更多▽"（优先判断）
                            # 2. "展开n条回复"
                            is_more_button = "展开" in button_text and "更多" in button_text
                            is_reply_button = "展开" in button_text and "回复" in button_text
                            
                            if is_more_button or is_reply_button:
                                # 直接点击展开按钮（不滚动）
                                button.click(force=True, timeout=3000)
                                
                                if is_more_button:
                                    more_count += 1
                                    if show_summary:
                                        print(f"  -> ✅ 展开更多评论: {button_text}")
                                elif is_reply_button:
                                    reply_count += 1
                                    if show_summary:
                                        print(f"  -> ✅ 展开回复: {button_text}")
                                
                                # 等待展开动画完成
                                page.wait_for_timeout(800)
                                
                                # ✅ 点击一个后立即返回
                                if not show_summary:
                                    print("", end='\r')
                                return reply_count, more_count
                    except Exception as e:
                        continue
                
            except Exception as e:
                continue
        
        # 如果没有找到任何按钮
        if not show_summary:
            print("", end='\r')
        
        return 0, 0
        
    except Exception as e:
        if show_summary:
            print(f"  -> 展开按钮时出错: {e}")
        return 0, 0

def scroll_and_expand_comments(page):
    """滚动评论区到底部，并在过程中持续展开所有按钮
    采用三轮扫描策略确保所有按钮都被点击：
    1. 第一轮：从顶部到底部
    2. 第二轮：返回顶部，再从顶部到底部
    3. 第三轮：最后再扫描一次确保完全展开
    """
    try:
        print("  -> 开始三轮扫描评论区并展开所有内容...")
        
        # 尝试查找评论区容器
        comment_area_selectors = [
            "[data-e2e='comment-list']",
            "div[class*='comment-list']",
            "div[class*='CommentList']",
            "div[id*='comment']"
        ]
        
        comment_area = None
        comment_selector = None
        for selector in comment_area_selectors:
            try:
                element = page.query_selector(selector)
                if element and element.is_visible():
                    comment_area = element
                    comment_selector = selector
                    print(f"  -> 找到评论区容器: {selector}")
                    break
            except:
                continue
        
        if comment_area:
            # 总计数器
            total_reply_count_all = 0
            total_more_count_all = 0
            
            # 滚动距离配置（像素）
            scroll_distance_min = 100  # 最小滚动距离
            scroll_distance_max = 150  # 最大滚动距离
            
            # 进行单轮扫描（只遍历一遍）
            print(f"\n{'='*60}")
            print(f"  -> 🔄 开始扫描评论区（从上往下）")
            print(f"{'='*60}")
            
            # 计数器
            scroll_count = 0
            max_scrolls = 3  # 增加最大滚动次数
            no_change_count = 0  # 连续没有变化的次数
            last_height = 0
        
            while scroll_count < max_scrolls:
                # 1. 先完全展开当前视图的所有按钮（滚动前）
                print(f"  -> 检查展开按钮...", end='', flush=True)
                reply_count, more_count = expand_all_buttons_in_view(page, show_summary=False)
                
                if reply_count > 0 or more_count > 0:
                    total_reply_count_all += reply_count
                    total_more_count_all += more_count
                    msg = []
                    if reply_count > 0:
                        msg.append(f"{reply_count}个回复")
                    if more_count > 0:
                        msg.append(f"{more_count}个'展开更多'")
                    print(f"  -> ✅ 展开: {', '.join(msg)}")
                else:
                    print(f"  -> 当前视图无需展开的按钮")
            
                # 2. 获取当前滚动位置和总高度
                scroll_info = page.evaluate("""
                    (selector) => {
                        const element = document.querySelector(selector);
                        if (element) {
                            return {
                                scrollTop: element.scrollTop,
                                scrollHeight: element.scrollHeight,
                                clientHeight: element.clientHeight
                            };
                        }
                        return null;
                    }
                """, comment_selector)
                
                # 3. 每次滚动随机距离，避免固定步长遗漏按钮
                current_scroll_distance = random.randint(scroll_distance_min, scroll_distance_max)
                page.evaluate("""
                    ([selector, distance]) => {
                        const element = document.querySelector(selector);
                        if (element) {
                            element.scrollTop += distance;  // 向下滚动随机距离
                        }
                    }
                """, [comment_selector, current_scroll_distance])
                
                scroll_count += 1
                print(f"  -> 滚动评论区 ({scroll_count}，距离: {current_scroll_distance}px)")
                
                # 4. 等待内容加载（缩短等待时间以加快速度）
                page.wait_for_timeout(random.randint(800, 1200))
            
                # 5. 获取新的滚动信息，检查是否到底
                new_scroll_info = page.evaluate("""
                    (selector) => {
                        const element = document.querySelector(selector);
                        if (element) {
                            return {
                                scrollTop: element.scrollTop,
                                scrollHeight: element.scrollHeight,
                                clientHeight: element.clientHeight
                            };
                        }
                        return null;
                    }
                """, comment_selector)
                
                # 检查是否到达底部
                if new_scroll_info:
                    is_at_bottom = (new_scroll_info['scrollTop'] + new_scroll_info['clientHeight']) >= (new_scroll_info['scrollHeight'] - 50)
                    new_height = new_scroll_info['scrollHeight']
                    
                    if is_at_bottom or new_height == last_height:
                        no_change_count += 1
                        if no_change_count >= 5:  # 连续5次确认到底（增加判定次数，防止误判）
                            # 最后再检查一次是否有按钮
                            print(f"  -> 到达底部，最后检查一次按钮...")
                            reply_count, more_count = expand_all_buttons_in_view(page, show_summary=False)
                            if reply_count > 0 or more_count > 0:
                                total_reply_count_all += reply_count
                                total_more_count_all += more_count
                                msg = []
                                if reply_count > 0:
                                    msg.append(f"{reply_count}个回复")
                                if more_count > 0:
                                    msg.append(f"{more_count}个'展开更多'")
                                print(f"  -> ✅ 最后展开: {', '.join(msg)}")
                            
                            print(f"  -> ✅ 扫描完成（共滚动 {scroll_count} 次）")
                            break
                    else:
                        no_change_count = 0  # 重置计数器
                    
                    last_height = new_height
            
            # 扫描完成，显示最终统计
            print(f"\n{'='*60}")
            print(f"  -> ✅ 评论区扫描结束")
            print(f"  -> ✅ 总共展开: {total_reply_count_all} 个回复按钮, {total_more_count_all} 个'展开更多'按钮")
            print(f"{'='*60}\n")
        else:
            # 如果找不到评论区，尝试滚动整个页面
            print("  -> 未找到评论区容器，尝试滚动整个页面")
            for i in range(5):
                page.mouse.wheel(0, 500)
                page.wait_for_timeout(random.randint(1000, 2000))
                print(f"  -> 滚动页面 ({i+1}/5)")
        
        return True
        
    except Exception as e:
        print(f"  -> 滚动评论区失败: {e}")
        return False

def extract_node_text_with_alt(element):
    """提取节点内容，将img标签转换为alt文本"""
    try:
        return element.evaluate("""element => {
            let text = "";
            element.childNodes.forEach(node => {
                if (node.nodeType === Node.TEXT_NODE) {
                    text += node.textContent;
                } else if (node.nodeType === Node.ELEMENT_NODE) {
                    if (node.tagName === "IMG") {
                        text += node.getAttribute("alt") || "";
                    } else {
                        text += node.innerText;
                    }
                }
            });
            return text;
        }""").strip()
    except:
        return element.text_content().strip()

def process_single_comment(comment_node):
    """
    提取单个评论节点的信息 (div.UuCzPLbi)
    严格遵循用户提供的结构:
    1. Avatar: div.ElTDPJYl -> div.obhJm_Xz -> a
    2. Info Wrap: div.EpsntdUI -> div.Vrj4Q3zT
    3. Name: span.arnSiSbK (inside Info Wrap)
    4. IP: div.fJhvAqos (inside Info Wrap)
    """
    try:
        # 1. 提取博主主页链接
        user_link = "未提取到"
        # 策略A (原逻辑): div.ElTDPJYl -> div.obhJm_Xz -> a
        try:
            avatar_container = comment_node.query_selector("div.ElTDPJYl")
            if avatar_container:
                link_wrapper = avatar_container.query_selector("div.obhJm_Xz")
                if link_wrapper:
                    link_node = link_wrapper.query_selector("a")
                    if link_node:
                        href = link_node.get_attribute("href")
                        if href:
                             user_link = href
        except:
            pass

        # 策略B (新逻辑 - 用户提供): 
        # Path: div.EpsntdUI -> div.Vrj4Q3zT -> div.jzhUi9rG (info-wrap) -> div._uYOTNYZ -> div.BT7MlqJC -> a
        if user_link == "未提取到":
            try:
                # 尝试从 info_wrap 中提取
                # 注意：此时我们还没有 info_wrap 变量，需要先获取 content_container
                content_container = comment_node.query_selector("div.EpsntdUI, div[class*='Epsntd']")
                if content_container:
                    info_wrap_node = content_container.query_selector("div.Vrj4Q3zT, div[class*='Vrj4Q3zT']")
                    if info_wrap_node:
                        # 查找包含链接的特定容器 div.BT7MlqJC
                        link_container = info_wrap_node.query_selector("div.BT7MlqJC")
                        if link_container:
                            link_node = link_container.query_selector("a")
                            if link_node:
                                href = link_node.get_attribute("href")
                                if href:
                                    user_link = href
            except:
                pass
        
        # 统一处理链接格式
        if user_link != "未提取到":
             if user_link.startswith("//"):
                user_link = "https:" + user_link
             elif user_link.startswith("/"):
                user_link = "https://www.douyin.com" + user_link

        # 进入主要内容容器 div.EpsntdUI
        # User: Epsntdul (typo corrected to EpsntdUI based on context/OCR)
        content_container = comment_node.query_selector("div.EpsntdUI")
        if not content_container:
            # 尝试模糊匹配，兼容性
            content_container = comment_node.query_selector("div[class*='Epsntd']")
            
        if not content_container:
            return None

        # 进入信息区域 div.Vrj4Q3zT (User: vri4Q3zT)
        # Class usually: Vrj4Q3zT fiDvPS80
        info_wrap = content_container.query_selector("div.Vrj4Q3zT")
        if not info_wrap:
             info_wrap = content_container.query_selector("div[class*='Vrj4Q3zT'], div[class*='vri4Q3zT']")

        user_name = "未提取到"
        ip_location = "未知"
        comment_text = ""
        
        if info_wrap:
            # 2. 提取博主名字 (span.arnSiSbK)
            try:
                # User: arnsisbK (typo corrected to arnSiSbK)
                name_node = info_wrap.query_selector("span.arnSiSbK")
                if not name_node:
                     name_node = info_wrap.query_selector("span[class*='arnSiSbK'], span[class*='arnsisbK']")
                
                if name_node:
                    # 处理名字中的图标 (alt属性拼接)
                    user_name = extract_node_text_with_alt(name_node)
            except:
                pass
            
            # 3. 提取IP地址 (div.fJhvAqos)
            try:
                # User: fThv4gos (typo corrected to fJhvAqos)
                ip_node = info_wrap.query_selector("div.fJhvAqos")
                if not ip_node:
                    ip_node = info_wrap.query_selector("div[class*='fJhvAqos'], div[class*='fThv4gos']")
                
                if ip_node:
                    ip_text = ip_node.text_content().strip()
                    # 分割 "4小时前 · 四川" -> 取后半部分
                    separator = None
                    if '·' in ip_text: separator = '·'
                    elif '•' in ip_text: separator = '•'
                    
                    if separator:
                        parts = ip_text.split(separator)
                        if len(parts) > 1:
                            ip_location = parts[-1].strip()
                    else:
                        # 兜底：如果没找到分隔符，可能是纯时间或纯IP，这里按用户要求"取划分后的后半部分"，如果无法划分则保留原样或提取最后一段
                        if " " in ip_text:
                            ip_location = ip_text.split()[-1]
                        else:
                            ip_location = ip_text
            except:
                pass

            # 4. 提取评论内容
            # 用户提供的新结构:
            # Path: info_wrap (Vrj4Q3zT) -> div.C7LroK_h -> span.WFJiGxr7 -> span -> span.arnSiSbK
            try:
                # 定位内容容器 div.C7LroK_h
                content_div = info_wrap.query_selector("div.C7LroK_h")
                if content_div:
                    # 定位具体的span结构 span.WFJiGxr7
                    content_span = content_div.query_selector("span.WFJiGxr7")
                    if content_span:
                        # 尝试深入查找 span.arnSiSbK，这是包含文本的最内层关键节点（如图所示）
                        inner_text_node = content_span.query_selector("span.arnSiSbK")
                        if inner_text_node:
                            comment_text = extract_node_text_with_alt(inner_text_node)
                        else:
                            # 如果没找到 arnSiSbK，则直接读取 WFJiGxr7 下的文本
                            comment_text = extract_node_text_with_alt(content_span)
            except:
                pass
            
            # 如果上面的路径没找到，尝试直接查找 C7LroK_h 下的文本
            if not comment_text:
                try:
                    content_div = info_wrap.query_selector("div.C7LroK_h")
                    if content_div:
                         comment_text = extract_node_text_with_alt(content_div)
                except:
                    pass

            # 兼容旧逻辑（如果新结构没找到）
            if not comment_text:
                try:
                    text_node = info_wrap.query_selector("span.sU2yAQQU, div.LvAtvU_f, span[class*='sU2y'], div[class*='LvAtv']")
                    if text_node:
                        comment_text = text_node.text_content().strip()
                except:
                    pass
                
        # 校验
        if not comment_text and not user_name:
            return None

        return {
            "user_name": user_name,
            "user_link": user_link,
            "comment": comment_text,
            "ip_location": ip_location
        }
    except Exception as e:
        # print(f"提取单条评论失败: {e}")
        return None

def scrape_comments(page):
    """
    爬取评论区的所有评论
    策略：
    1. 调用 scroll_and_expand_comments 滚动到底部并展开所有按钮 (预处理)
    2. 快速回到顶部
    3. 缓慢向下滚动，边滚边采，去重
    """
    all_comments_data = []
    seen_keys = set()
    
    try:
        print("  -> 正在爬取评论(基于新策略: 预处理+回滚采集)...")
        
        # 1. 预处理：滚动到底部并展开所有按钮
        # (保留用户要求的原有逻辑，这一步非常重要，确保所有折叠内容都被展开)
        scroll_and_expand_comments(page)
        
        # 2. 准备采集阶段
        print(f"\n{'='*60}")
        print("  -> 🔄 准备开始采集数据...")
        
        # 定位评论列表容器 (为了控制滚动)
        comment_list = None
        list_selectors = [
            "[data-e2e='comment-list']",
            ".Rwb9ssMc", ".Rwb9ssHc", 
            "div[class*='Rwb9ss']",
            "div[class*='comment-list']"
        ]
        
        for sel in list_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    comment_list = el
                    print(f"  -> 找到评论列表容器: {sel}")
                    break
            except:
                continue
                
        # 3. 快速回到顶部
        print("  -> ⬆️ 快速回到评论区顶部...")
        if comment_list:
            comment_list.evaluate("el => el.scrollTop = 0")
        else:
            page.evaluate("window.scrollTo(0, 0)")
        
        page.wait_for_timeout(1500) # 等待页面渲染
        
        # 4. 缓慢下滑并采集
        print("  -> ⬇️ 开始下滑并采集数据...")
        
        # 滚动参数
        scroll_step = 600  # 每次滚动步长
        last_scroll_top = -1
        no_change_count = 0
        max_no_change = 3
        
        # 临时测试限制
        test_scroll_count = 0
        max_test_scrolls = 3
        
        while True:
            # 测试限制
            if test_scroll_count >= max_test_scrolls:
                print("\n  -> [测试模式] 达到最大滚动次数 10 次，停止采集")
                break
            test_scroll_count += 1
            # --- 采集当前视口数据 ---
            # 获取当前所有可见的一级评论块
            # 注意：在虚拟滚动中，DOM中可能只有当前视口附近的元素
            current_batch_items = []
            if comment_list:
                current_batch_items = comment_list.query_selector_all(":scope > div")
            else:
                current_batch_items = page.query_selector_all(".UuCzPLbi")

            new_in_batch = 0
            
            for item in current_batch_items:
                try:
                    # 尝试提取主评论
                    main_comment_node = None
                    classes = item.get_attribute("class") or ""
                    
                    if "UuCzPLbi" in classes:
                        main_comment_node = item
                    else:
                        main_comment_node = item.query_selector(".UuCzPLbi")
                    
                    if main_comment_node:
                        # 提取主评论数据
                        main_data = process_single_comment(main_comment_node)
                        if main_data:
                            # 生成去重键 (名字+内容+IP)
                            key = f"{main_data['user_name']}|{main_data['comment']}|{main_data['ip_location']}"
                            if key not in seen_keys:
                                seen_keys.add(key)
                                all_comments_data.append(main_data)
                                new_in_batch += 1
                        
                        # 提取回复数据
                        try:
                            # 查找回复容器
                            content_container = main_comment_node.query_selector("div.EpsntdUI, div[class*='Epsntd']")
                            if content_container:
                                reply_container = content_container.query_selector(".CCbmLKh0.replyContainer, div[class*='replyContainer']")
                                if reply_container:
                                    # 查找回复容器内的所有评论项
                                    replies = reply_container.query_selector_all(".UuCzPLbi")
                                    for reply in replies:
                                        reply_data = process_single_comment(reply)
                                        if reply_data:
                                            r_key = f"{reply_data['user_name']}|{reply_data['comment']}|{reply_data['ip_location']}"
                                            if r_key not in seen_keys:
                                                seen_keys.add(r_key)
                                                all_comments_data.append(reply_data)
                                                new_in_batch += 1
                        except:
                            pass
                except:
                    continue
            
            # --- 滚动逻辑 ---
            if comment_list:
                # 获取当前滚动状态
                scroll_info = comment_list.evaluate("""el => {
                    return {scrollTop: el.scrollTop, scrollHeight: el.scrollHeight, clientHeight: el.clientHeight}
                }""")
                scrollTop = scroll_info['scrollTop']
                scrollHeight = scroll_info['scrollHeight']
                clientHeight = scroll_info['clientHeight']
                
                # 打印进度
                print(f"  -> 采集进度: 已收集 {len(all_comments_data)} 条 (本批新增 {new_in_batch}) [Pos: {int(scrollTop)}/{int(scrollHeight)}]", end='\r')
                
                # 检查是否到底
                if scrollTop + clientHeight >= scrollHeight - 100:
                    print("\n  -> 到达底部")
                    break
                
                # 检查是否卡住
                if scrollTop == last_scroll_top:
                    no_change_count += 1
                    if no_change_count >= max_no_change:
                        print("\n  -> 滚动未发生变化，停止采集")
                        break
                else:
                    no_change_count = 0
                    last_scroll_top = scrollTop
                
                # 执行向下滚动
                comment_list.evaluate(f"el => el.scrollTop += {scroll_step}")
                
            else:
                # 页面级滚动备用逻辑
                prev_scroll_y = page.evaluate("window.scrollY")
                page.evaluate(f"window.scrollBy(0, {scroll_step})")
                page.wait_for_timeout(500)
                new_scroll_y = page.evaluate("window.scrollY")
                
                print(f"  -> 采集进度: 已收集 {len(all_comments_data)} 条 (本批新增 {new_in_batch})", end='\r')
                
                if new_scroll_y == prev_scroll_y:
                     print("\n  -> 页面滚动到底部或未变化")
                     break
            
            # 每次滚动后短暂等待，确保内容渲染
            page.wait_for_timeout(random.randint(600, 1000))

        print(f"\n  -> ✅ 采集完成，共收集 {len(all_comments_data)} 条评论")
        return all_comments_data
        
    except Exception as e:
        print(f"  -> 爬取评论失败: {e}")
        import traceback
        traceback.print_exc()
        return all_comments_data

def save_comments_to_csv(comments, video_url, video_text, screenshot_path, filename="douyin_comments.csv"):
    """保存评论数据到CSV文件"""
    file_exists = os.path.isfile(filename)
    
    try:
        # 检查文件是否为空（不仅仅是存在）
        should_write_header = not file_exists or os.path.getsize(filename) == 0
        
        with open(filename, mode='a', newline='', encoding='utf-8-sig') as f:
            # 字段名（与 douyin_scraper.py 保持一致，comment 列放在最后）
            fieldnames = ['user_name', 'user_ip', 'user_link', 'video_url', 'video_text', 'screenshot_path', 'comment']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            if should_write_header:
                writer.writeheader()
            
            for comment in comments:
                writer.writerow({
                    'user_name': comment.get('user_name', '未提取到'),
                    'user_ip': comment.get('ip_location', '未知'),
                    'user_link': comment.get('user_link', '未提取到'),
                    'video_url': video_url,
                    'video_text': video_text,
                    'screenshot_path': screenshot_path,
                    'comment': comment.get('comment', '')
                })
        
        print(f"  -> ✅ 评论数据已保存到 {filename}")
        return True
        
    except Exception as e:
        print(f"  -> ❌ 保存CSV失败: {e}")
        return False

def analyze_current_video(page, current_url, condition):
    """
    截图并分析当前视频内容
    
    Args:
        page: 页面对象
        current_url: 视频URL
        condition: 筛选条件
    
    Returns:
        (should_process, text_content, screenshot_path): 是否处理、视频文案和截图路径
    """
    screenshot_path = None
    text_content = ""
    
    try:
        # 创建截图目录
        screenshot_dir = "screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)
        
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
                    elements = page.query_selector_all(selector)
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
            page.wait_for_timeout(500)
        
        if not text_content:
            text_content = "未提取到文字"
        
        display_text = text_content[:50].replace('\n', ' ') + "..." if len(text_content) > 50 else text_content.replace('\n', ' ')
        print(f"  -> 提取到的文字: {display_text}")
        
        # --- 截图 ---
        screenshot_path = os.path.join(screenshot_dir, f"video_analysis_{int(time.time())}.png")
        try:
            page.screenshot(path=screenshot_path)
            print(f"  -> 截图已保存: {screenshot_path}")
        except Exception as e:
            print(f"  -> 截图失败: {e}")
            screenshot_path = None
            return False, text_content, screenshot_path

        # --- 调用 Qwen 分析 ---
        print("  -> 正在调用 Qwen 分析内容...")
        # 使用与 douyin_scraper.py 相同的调用方式
        analysis_result = analyze_with_qwen(text_content, condition, screenshot_path)
        
        print(f"  -> AI分析结果: {analysis_result}")
        
        # 处理 AI 返回的原始文本结果 (True/False)
        should_process = False
        if isinstance(analysis_result, str):
            # 清理结果文本，移除可能的空格或标点
            clean_result = analysis_result.strip().lower()
            should_process = clean_result == "true"
            
        if should_process:
            print("  -> [判定] ✅ 内容符合要求，开始采集评论")
        else:
            print("  -> [判定] ❌ 内容不符合要求，跳过评论采集")
            
        return should_process, text_content, screenshot_path
        
    except Exception as e:
        print(f"  -> 视频内容分析失败: {e}")
        return False, text_content, screenshot_path # 默认不处理，避免因分析失败导致意外采集


def collect_video_comments(page, condition, max_videos=5, csv_filename="douyin_comments.csv"):
    """收集视频评论的主函数"""
    all_comments = []
    
    try:
        print("正在识别视频卡片...")
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
                    print(f"✓ 使用选择器 '{selector}' 识别到 {len(valid_cards)} 个卡片")
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
            print("❌ 未能识别到视频卡片")
            return []

        print(f"准备处理视频评论，目标筛选出 {max_videos} 个符合条件的视频...")
        
        card = valid_cards[0]
        video_page = None
        
        try:
            # 1. 点击第一个视频
            print("\n正在点击第一个视频卡片...")
            card.evaluate("el => el.scrollIntoView({block: 'center', inline: 'nearest'})")
            page.wait_for_timeout(250)
            
            # 尝试检测是否会打开新标签页
            try:
                # 设置短超时，快速检测是否有新页面
                with page.context.expect_page(timeout=500) as new_page_info:
                    card.click(force=True)
                
                video_page = new_page_info.value
                print("  -> 新窗口已打开，等待加载...")
                video_page.wait_for_load_state("domcontentloaded")
                video_page.wait_for_timeout(250)
            except:
                # 如果没有新标签页，说明是当前页面跳转
                print("  -> 在当前页面跳转...")
                video_page = page
                page.wait_for_timeout(2000)

            # 检测并关闭可能的引导提示框
            print("  -> 检测页面引导提示...")
            close_intro_modal(video_page)

            # 2. 循环处理视频，直到筛选出足够数量的视频
            video_count = 0  # 已处理的视频数量
            success_count = 0  # 成功筛选出的视频数量
            max_attempts = max_videos * 10  # 最多尝试的视频数量（防止无限循环）
            
            while success_count < max_videos and video_count < max_attempts:
                video_count += 1
                print(f"\n{'='*60}")
                print(f"[视频 {video_count}] [已筛选 {success_count}/{max_videos}] 正在处理当前视频的评论...")
                print(f"{'='*60}")
                
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
                        print(f"  -> 暂停失败: {e}")
                
                # 获取当前视频URL
                current_url = video_page.url
                print(f"  -> 视频链接: {current_url}")

                # AI 分析视频内容
                should_process, video_text, screenshot_path = analyze_current_video(video_page, current_url, condition)
                
                if should_process:
                    # 只有当 AI 返回 True 时才采集评论
                    
                    # 第一次点击评论按钮
                    comment_opened = False
                    if success_count == 0:  # 第一个成功的视频
                        comment_opened = click_comment_button(video_page)
                    else:
                         # 后续视频，评论区通常默认展开（如果上一个视频展开了）
                         # 但为了保险，还是检查一下，如果没展开再点击
                         # 这里的逻辑可能需要根据实际情况微调，通常抖音网页版切换视频后评论区状态会保持
                         # 或者我们可以简单地再次调用 click_comment_button，让它内部判断是否可见
                         # 但根据用户要求"之后打开新视频不需要"，这里默认已展开
                         comment_opened = True
                         print("  -> [后续视频] 默认评论区已展开")

                    if comment_opened:
                        # 爬取评论
                        comments = scrape_comments(video_page)
                        
                        if comments:
                            # 保存评论到CSV（包含视频文案和截图路径）
                            save_comments_to_csv(comments, current_url, video_text, screenshot_path, csv_filename)
                            all_comments.extend(comments)
                            success_count += 1  # 成功筛选出一个视频
                            print(f"  -> ✅ 成功采集评论 (第 {success_count}/{max_videos} 个符合条件的视频)")
                        else:
                            print("  -> ⚠️ 该视频没有评论或爬取失败，继续下一个视频")
                    else:
                        print("  -> ⚠️ 无法打开评论区，继续下一个视频")
                else:
                     print("  -> [判定] ❌ 不符合条件，继续下一个视频")
                
                # 切换到下一个视频
                # 如果已经达到目标数量，提前结束
                if success_count >= max_videos:
                    print(f"\n✓ 已成功筛选出 {success_count} 个视频，达到目标数量！")
                    break
                
                # 如果还没达到目标，切换到下一个视频
                if success_count < max_videos:
                    print("\n  -> 按下 ↓ 键切换到下一个视频...")
                    video_page.keyboard.press("ArrowDown")
                    
                    # 立刻暂停新视频
                    video_page.wait_for_timeout(100)
                    print("  -> 立即暂停新视频...")
                    # 连续按三次空格键，确保视频暂停
                    for pause_attempt in range(3):
                        video_page.keyboard.press("Space")
                        if pause_attempt < 2:
                            video_page.wait_for_timeout(500)
                    
                    # 等待页面加载
                    wait_time = random.randint(200, 300)
                    video_page.wait_for_timeout(wait_time)
                    
                    # 检测并关闭新视频可能出现的引导提示框
                    close_intro_modal(video_page)
            
            print("\n" + "="*60)
            print("✅ 评论采集完成")
            print(f"总共处理视频数: {video_count}")
            print(f"成功筛选视频数: {success_count}")
            print("="*60)
            
            # 如果是新窗口，关闭它
            if video_page != page:
                print("关闭视频窗口...")
                video_page.close()
            
        except Exception as e:
            print(f"❌ 点击或处理过程中出错: {e}")
            import traceback
            traceback.print_exc()
            # 如果是新窗口且未关闭，关闭它
            if video_page and video_page != page:
                try:
                    if not video_page.is_closed():
                        video_page.close()
                except:
                    pass
                
    except Exception as e:
        print(f"❌ 搜集评论过程中出错: {e}")
        import traceback
        traceback.print_exc()
        
    return all_comments

def run_comment(keyword, condition, max_videos=5, csv_filename=None):
    """
    运行评论爬虫的主入口函数
    
    参数:
        keyword: 搜索关键词
        condition: 筛选条件
        max_videos: 目标筛选出的视频数量
        csv_filename: 输出CSV文件名（如果为None则自动生成）
    """
    print(f"\n开始爬取抖音评论...")
    print(f"搜索关键词: {keyword}")
    print(f"筛选条件: {condition}")
    print(f"目标视频数量: {max_videos}")
    print("="*60)
    
    # 生成带日期的文件名
    if csv_filename is None:
        current_date = datetime.now().strftime("%Y-%m-%d")
        csv_filename = f"douyin_comments_{current_date}.csv"
    
    with sync_playwright() as playwright:
        browser, context, page = init_browser(playwright)
        
        try:
            if search_douyin(page, keyword):
                all_comments = collect_video_comments(page, condition, max_videos, csv_filename)
                
                print("\n" + "="*60)
                print("评论爬取汇总")
                print("="*60)
                if all_comments:
                    print(f"✓ 总共爬取到 {len(all_comments)} 条评论")
                    print(f"✓ 数据已保存到: {csv_filename}")
                else:
                    print("❌ 没有爬取到任何评论")
                print("="*60)
                
        except Exception as e:
            print(f"❌ 程序执行出错: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # GUI模式下不需要等待用户输入
            # 关闭浏览器（持久化模式下 browser 为 None）
            try:
                if browser:
                    browser.close()
                else:
                    context.close()
            except:
                pass

def main():
    import argparse
    parser = argparse.ArgumentParser(description='抖音评论爬虫')
    parser.add_argument('keyword', nargs='?', help='搜索关键词')
    parser.add_argument('condition', nargs='?', help='筛选条件')
    parser.add_argument('max_videos', nargs='?', type=int, help='目标筛选出的视频数量（达到此数量后停止）')
    args = parser.parse_args()

    if args.keyword:
        keyword = args.keyword
    else:
        keyword = input("请输入搜索关键词: ")
    
    if args.condition:
        condition = args.condition
    else:
        condition = input("请输入筛选条件 (例如: 视频内容是否与找工作相关): ")
    
    if args.max_videos is not None:
        max_videos = args.max_videos
    else:
        max_videos_input = input("请输入目标筛选出的视频数量 (默认5，程序将持续处理视频直到达到此数量): ")
        try:
            max_videos = int(max_videos_input) if max_videos_input else 5
        except:
            max_videos = 5
    
    print(f"\n开始爬取抖音评论...")
    print(f"搜索关键词: {keyword}")
    print(f"筛选条件: {condition}")
    print(f"目标视频数量: {max_videos}")
    print("="*60)
    
    # 生成带日期的文件名
    current_date = datetime.now().strftime("%Y-%m-%d")
    csv_filename = f"douyin_comments_{current_date}.csv"
    
    with sync_playwright() as playwright:
        browser, context, page = init_browser(playwright)
        
        try:
            if search_douyin(page, keyword):
                all_comments = collect_video_comments(page, condition, max_videos, csv_filename)
                
                print("\n" + "="*60)
                print("评论爬取汇总")
                print("="*60)
                if all_comments:
                    print(f"✓ 总共爬取到 {len(all_comments)} 条评论")
                    print(f"✓ 数据已保存到: {csv_filename}")
                else:
                    print("❌ 没有爬取到任何评论")
                print("="*60)
                
        except Exception as e:
            print(f"❌ 程序执行出错: {e}")
            import traceback
            traceback.print_exc()
        finally:
            input("\n按回车键关闭浏览器...")
            # 关闭浏览器（持久化模式下 browser 为 None）
            try:
                if browser:
                    browser.close()
                else:
                    context.close()
            except:
                pass

if __name__ == "__main__":
    main()

