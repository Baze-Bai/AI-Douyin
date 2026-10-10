import os
import sys
import platform
import shutil
from playwright.sync_api import sync_playwright

def get_playwright_launch_args(headless=False):
    """获取Playwright启动参数"""
    return {
        "headless": headless,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--window-position=0,0",
            "--ignore-certificate-errors",
            "--ignore-ssl-errors",
            "--disable-gpu",
            "--no-first-run",
            "--no-service-autorun",
            "--password-store=basic"
        ]
    }

def get_chrome_path():
    """检测系统 Chrome 路径"""
    if platform.system() == "Windows":
        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
        ]
        for p in paths:
            if os.path.exists(p): return p
    # MacOS/Linux detection could be added here
    return None

def get_edge_path():
    """检测系统 Edge 路径"""
    if platform.system() == "Windows":
        paths = [
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        ]
        for p in paths:
            if os.path.exists(p): return p
    return None

def get_firefox_path():
    """检测系统 Firefox 路径"""
    if platform.system() == "Windows":
        paths = [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Mozilla Firefox\firefox.exe")
        ]
        for p in paths:
            if os.path.exists(p): return p
    return None

def get_safari_path():
    """检测系统 Safari 路径 (主要针对 macOS)"""
    if platform.system() == "Darwin":
        return "/Applications/Safari.app/Contents/MacOS/Safari"
    return None

def configure_bundled_browsers():
    """配置打包环境下的浏览器路径"""
    if getattr(sys, 'frozen', False):
        bundled_browsers_path = os.path.join(sys._MEIPASS, "ms-playwright")
        if os.path.exists(bundled_browsers_path):
            print(f"  -> 检测到打包环境，设置 PLAYWRIGHT_BROWSERS_PATH: {bundled_browsers_path}")
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = bundled_browsers_path
        else:
            print(f"  -> ⚠️打包环境未找到预期的浏览器路径: {bundled_browsers_path}")

def detect_browser_config(playwright):
    """
    检测可用浏览器配置
    返回: (browser_type_obj, launch_kwargs, browser_name)
    """
    # 1. 检测 Chrome
    if get_chrome_path():
        print("✓ 检测到系统 Chrome")
        return playwright.chromium, {"channel": "chrome"}, "Chrome"
    
    # 2. 检测 Edge
    if get_edge_path():
        print("✓ 检测到系统 Edge")
        return playwright.chromium, {"channel": "msedge"}, "Edge"
        
    # 3. 检测 Firefox
    firefox_path = get_firefox_path()
    if firefox_path:
        print("✓ 检测到系统 Firefox")
        return playwright.firefox, {"executable_path": firefox_path}, "Firefox"
        
    # 4. 检测 Safari (Webkit)
    # 注意: Playwright 在 Windows 上不直接支持系统 Safari，但在 Mac 上可以使用 webkit
    if platform.system() == "Darwin":
        print("✓ 检测到系统 Safari (使用 WebKit)")
        return playwright.webkit, {}, "Safari"
        
    # 5. Fallback: 使用 Playwright 内置 Chromium
    print("⚠️ 未检测到系统浏览器，使用 Playwright 内置 Chromium")
    configure_bundled_browsers()
    return playwright.chromium, {}, "Built-in Chromium"

def launch_browser_with_fallback(playwright, headless=False, launch_args=None):
    """
    启动浏览器，自动选择最佳可用浏览器
    """
    if launch_args is None:
        launch_args = get_playwright_launch_args(headless)["args"]
        
    browser_type, specific_kwargs, name = detect_browser_config(playwright)
    
    print(f"正在启动 {name}...")
    try:
        browser = browser_type.launch(
            headless=headless,
            args=launch_args,
            **specific_kwargs
        )
        print(f"✓ 成功启动 {name}")
        return browser
    except Exception as e:
        print(f"❌ {name} 启动失败: {e}")
        # 如果是系统浏览器失败，尝试降级到内置 Chromium
        if name != "Built-in Chromium":
            print("尝试降级到内置 Chromium...")
            configure_bundled_browsers()
            try:
                browser = playwright.chromium.launch(
                    headless=headless,
                    args=launch_args
                )
                print("✓ 成功启动内置 Chromium")
                return browser
            except Exception as e2:
                print(f"❌ 内置 Chromium 启动失败: {e2}")
                raise e2
        raise e
