"""
抖音自动化工具 - 统一GUI界面
包含三大功能：视频采集(Scraper)、评论采集(Comment)、私信发送(Messenger)
"""
import os
import sys
import threading
import queue
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
from datetime import datetime

# 确保工作目录正确
if getattr(sys, 'frozen', False):
    # 打包后的exe运行
    application_path = os.path.dirname(sys.executable)
else:
    # 开发环境运行
    application_path = os.path.dirname(os.path.abspath(__file__))

os.chdir(application_path)

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 创建必要的文件夹
def create_required_folders():
    folders = ['screenshots', 'Chrome_data']
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"✓ 创建文件夹: {folder}")

create_required_folders()

# 导入功能模块
from douyin_scraper import run_scraper
from douyin_comment import run_comment
from douyin_messenger import run_messenger


class OutputRedirector:
    """重定向stdout到GUI文本框"""
    def __init__(self, text_widget, output_queue):
        self.text_widget = text_widget
        self.output_queue = output_queue
        
    def write(self, text):
        self.output_queue.put(text)
        
    def flush(self):
        pass


class DouyinToolGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("抖音自动化工具 v1.0")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        # 设置主题颜色
        self.colors = {
            'bg': '#1a1a2e',
            'fg': '#eaeaea',
            'accent': '#e94560',
            'secondary': '#16213e',
            'success': '#00d26a',
            'warning': '#ffc107',
            'input_bg': '#0f3460',
            'button_hover': '#ff6b6b'
        }
        
        self.root.configure(bg=self.colors['bg'])
        
        # 配置样式
        self.setup_styles()
        
        # 输出队列
        self.output_queue = queue.Queue()
        
        # 运行状态
        self.is_running = False
        self.current_thread = None
        
        # 创建界面
        self.create_widgets()
        
        # 启动输出更新
        self.update_output()
        
    def setup_styles(self):
        """配置ttk样式"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # 配置Notebook样式
        style.configure('TNotebook', background=self.colors['bg'])
        style.configure('TNotebook.Tab', 
                       background=self.colors['secondary'],
                       foreground=self.colors['fg'],
                       padding=[20, 10],
                       font=('Microsoft YaHei UI', 11, 'bold'))
        style.map('TNotebook.Tab',
                 background=[('selected', self.colors['accent'])],
                 foreground=[('selected', '#ffffff')])
        
        # 配置Frame样式
        style.configure('TFrame', background=self.colors['bg'])
        style.configure('Card.TFrame', background=self.colors['secondary'])
        
        # 配置Label样式
        style.configure('TLabel', 
                       background=self.colors['bg'],
                       foreground=self.colors['fg'],
                       font=('Microsoft YaHei UI', 10))
        style.configure('Header.TLabel',
                       font=('Microsoft YaHei UI', 12, 'bold'))
        
        # 配置Entry样式
        style.configure('TEntry',
                       fieldbackground=self.colors['input_bg'],
                       foreground=self.colors['fg'],
                       insertcolor=self.colors['fg'])
        
        # 配置Button样式
        style.configure('Accent.TButton',
                       background=self.colors['accent'],
                       foreground='#ffffff',
                       font=('Microsoft YaHei UI', 11, 'bold'),
                       padding=[20, 10])
        style.map('Accent.TButton',
                 background=[('active', self.colors['button_hover'])])
        
    def create_widgets(self):
        """创建界面组件"""
        # 顶部标题
        title_frame = tk.Frame(self.root, bg=self.colors['bg'])
        title_frame.pack(fill=tk.X, padx=20, pady=15)
        
        title_label = tk.Label(title_frame, 
                               text="🎬 抖音自动化工具",
                               font=('Microsoft YaHei UI', 20, 'bold'),
                               fg=self.colors['accent'],
                               bg=self.colors['bg'])
        title_label.pack(side=tk.LEFT)
        
        # 状态指示器
        self.status_label = tk.Label(title_frame,
                                     text="● 就绪",
                                     font=('Microsoft YaHei UI', 10),
                                     fg=self.colors['success'],
                                     bg=self.colors['bg'])
        self.status_label.pack(side=tk.RIGHT)
        
        # 创建Notebook（标签页）
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 创建三个功能页面
        self.create_scraper_tab()
        self.create_comment_tab()
        self.create_messenger_tab()
        
        # 输出日志区域
        log_frame = tk.Frame(self.root, bg=self.colors['secondary'])
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        log_header = tk.Frame(log_frame, bg=self.colors['secondary'])
        log_header.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        log_title = tk.Label(log_header,
                             text="📋 运行日志",
                             font=('Microsoft YaHei UI', 11, 'bold'),
                             fg=self.colors['fg'],
                             bg=self.colors['secondary'])
        log_title.pack(side=tk.LEFT)
        
        clear_btn = tk.Button(log_header,
                              text="清空",
                              font=('Microsoft YaHei UI', 9),
                              fg=self.colors['fg'],
                              bg=self.colors['accent'],
                              relief=tk.FLAT,
                              cursor='hand2',
                              command=self.clear_log)
        clear_btn.pack(side=tk.RIGHT)
        
        self.log_text = scrolledtext.ScrolledText(log_frame,
                                                   font=('Consolas', 10),
                                                   bg='#0a0a15',
                                                   fg='#00ff00',
                                                   insertbackground='#00ff00',
                                                   relief=tk.FLAT,
                                                   height=12)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
    def create_input_row(self, parent, label_text, default_value="", row=0):
        """创建输入行"""
        frame = tk.Frame(parent, bg=self.colors['secondary'])
        frame.pack(fill=tk.X, pady=8)
        
        label = tk.Label(frame,
                         text=label_text,
                         font=('Microsoft YaHei UI', 10),
                         fg=self.colors['fg'],
                         bg=self.colors['secondary'],
                         width=15,
                         anchor='e')
        label.pack(side=tk.LEFT, padx=(0, 10))
        
        entry = tk.Entry(frame,
                         font=('Microsoft YaHei UI', 10),
                         bg=self.colors['input_bg'],
                         fg=self.colors['fg'],
                         insertbackground=self.colors['fg'],
                         relief=tk.FLAT)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)
        entry.insert(0, default_value)
        
        return entry
        
    def create_scraper_tab(self):
        """创建视频采集标签页"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📹 视频采集")
        
        # 内容区域
        content = tk.Frame(tab, bg=self.colors['secondary'])
        content.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # 说明
        desc = tk.Label(content,
                        text="采集抖音视频博主信息，根据关键词搜索并筛选符合条件的博主",
                        font=('Microsoft YaHei UI', 10),
                        fg='#888888',
                        bg=self.colors['secondary'])
        desc.pack(anchor='w', pady=(0, 15))
        
        # 输入区域
        self.scraper_keyword = self.create_input_row(content, "搜索关键词:", "成都找工作")
        self.scraper_condition = self.create_input_row(content, "筛选条件:", "视频内容是否与找工作相关")
        self.scraper_count = self.create_input_row(content, "目标数量:", "5")
        
        # 运行按钮
        btn_frame = tk.Frame(content, bg=self.colors['secondary'])
        btn_frame.pack(fill=tk.X, pady=20)
        
        run_btn = tk.Button(btn_frame,
                            text="▶ 开始采集",
                            font=('Microsoft YaHei UI', 12, 'bold'),
                            fg='#ffffff',
                            bg=self.colors['accent'],
                            activebackground=self.colors['button_hover'],
                            activeforeground='#ffffff',
                            relief=tk.FLAT,
                            cursor='hand2',
                            padx=30,
                            pady=10,
                            command=self.run_scraper)
        run_btn.pack()
        
    def create_comment_tab(self):
        """创建评论采集标签页"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="💬 评论采集")
        
        content = tk.Frame(tab, bg=self.colors['secondary'])
        content.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        desc = tk.Label(content,
                        text="采集抖音视频评论区用户信息，根据关键词搜索视频并收集评论用户",
                        font=('Microsoft YaHei UI', 10),
                        fg='#888888',
                        bg=self.colors['secondary'])
        desc.pack(anchor='w', pady=(0, 15))
        
        self.comment_keyword = self.create_input_row(content, "搜索关键词:", "成都找工作")
        self.comment_condition = self.create_input_row(content, "筛选条件:", "视频内容是否与找工作相关")
        self.comment_count = self.create_input_row(content, "目标视频数:", "5")
        
        btn_frame = tk.Frame(content, bg=self.colors['secondary'])
        btn_frame.pack(fill=tk.X, pady=20)
        
        run_btn = tk.Button(btn_frame,
                            text="▶ 开始采集",
                            font=('Microsoft YaHei UI', 12, 'bold'),
                            fg='#ffffff',
                            bg=self.colors['accent'],
                            activebackground=self.colors['button_hover'],
                            activeforeground='#ffffff',
                            relief=tk.FLAT,
                            cursor='hand2',
                            padx=30,
                            pady=10,
                            command=self.run_comment)
        run_btn.pack()
        
    def create_messenger_tab(self):
        """创建私信发送标签页"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="✉️ 私信发送")
        
        content = tk.Frame(tab, bg=self.colors['secondary'])
        content.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        desc = tk.Label(content,
                        text="根据CSV文件中的用户列表，使用AI生成个性化私信并自动发送",
                        font=('Microsoft YaHei UI', 10),
                        fg='#888888',
                        bg=self.colors['secondary'])
        desc.pack(anchor='w', pady=(0, 15))
        
        # CSV文件选择
        file_frame = tk.Frame(content, bg=self.colors['secondary'])
        file_frame.pack(fill=tk.X, pady=8)
        
        file_label = tk.Label(file_frame,
                              text="CSV文件:",
                              font=('Microsoft YaHei UI', 10),
                              fg=self.colors['fg'],
                              bg=self.colors['secondary'],
                              width=15,
                              anchor='e')
        file_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.messenger_csv = tk.Entry(file_frame,
                                      font=('Microsoft YaHei UI', 10),
                                      bg=self.colors['input_bg'],
                                      fg=self.colors['fg'],
                                      insertbackground=self.colors['fg'],
                                      relief=tk.FLAT)
        self.messenger_csv.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)
        
        browse_btn = tk.Button(file_frame,
                               text="浏览...",
                               font=('Microsoft YaHei UI', 9),
                               fg=self.colors['fg'],
                               bg=self.colors['input_bg'],
                               relief=tk.FLAT,
                               cursor='hand2',
                               command=self.browse_csv)
        browse_btn.pack(side=tk.RIGHT, padx=(10, 0))
        
        self.messenger_requirement = self.create_input_row(content, "私信要求:", "邀请对方加入我们的招聘群，提供兼职机会")
        
        btn_frame = tk.Frame(content, bg=self.colors['secondary'])
        btn_frame.pack(fill=tk.X, pady=20)
        
        run_btn = tk.Button(btn_frame,
                            text="▶ 开始发送",
                            font=('Microsoft YaHei UI', 12, 'bold'),
                            fg='#ffffff',
                            bg=self.colors['accent'],
                            activebackground=self.colors['button_hover'],
                            activeforeground='#ffffff',
                            relief=tk.FLAT,
                            cursor='hand2',
                            padx=30,
                            pady=10,
                            command=self.run_messenger)
        run_btn.pack()
        
    def browse_csv(self):
        """浏览选择CSV文件"""
        filename = filedialog.askopenfilename(
            title="选择CSV文件",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            self.messenger_csv.delete(0, tk.END)
            self.messenger_csv.insert(0, filename)
            
    def clear_log(self):
        """清空日志"""
        self.log_text.delete(1.0, tk.END)
        
    def update_output(self):
        """更新输出日志"""
        try:
            while True:
                text = self.output_queue.get_nowait()
                self.log_text.insert(tk.END, text)
                self.log_text.see(tk.END)
        except queue.Empty:
            pass
        self.root.after(100, self.update_output)
        
    def set_running(self, running):
        """设置运行状态"""
        self.is_running = running
        if running:
            self.status_label.config(text="● 运行中", fg=self.colors['warning'])
        else:
            self.status_label.config(text="● 就绪", fg=self.colors['success'])
            
    def run_in_thread(self, func, *args):
        """在线程中运行函数"""
        if self.is_running:
            messagebox.showwarning("提示", "当前有任务正在运行，请等待完成后再试")
            return
            
        def wrapper():
            self.set_running(True)
            # 重定向输出
            old_stdout = sys.stdout
            sys.stdout = OutputRedirector(self.log_text, self.output_queue)
            try:
                func(*args)
            except Exception as e:
                print(f"\n❌ 错误: {e}")
                import traceback
                traceback.print_exc()
            finally:
                sys.stdout = old_stdout
                self.set_running(False)
                
        self.current_thread = threading.Thread(target=wrapper, daemon=True)
        self.current_thread.start()
        
    def run_scraper(self):
        """运行视频采集"""
        keyword = self.scraper_keyword.get().strip()
        condition = self.scraper_condition.get().strip()
        try:
            count = int(self.scraper_count.get().strip())
        except:
            count = 5
            
        if not keyword:
            messagebox.showwarning("提示", "请输入搜索关键词")
            return
        if not condition:
            messagebox.showwarning("提示", "请输入筛选条件")
            return
            
        current_date = datetime.now().strftime("%Y-%m-%d")
        csv_filename = f"douyin_videos_{current_date}.csv"
        
        self.run_in_thread(run_scraper, keyword, condition, count, csv_filename)
        
    def run_comment(self):
        """运行评论采集"""
        keyword = self.comment_keyword.get().strip()
        condition = self.comment_condition.get().strip()
        try:
            count = int(self.comment_count.get().strip())
        except:
            count = 5
            
        if not keyword:
            messagebox.showwarning("提示", "请输入搜索关键词")
            return
        if not condition:
            messagebox.showwarning("提示", "请输入筛选条件")
            return
            
        current_date = datetime.now().strftime("%Y-%m-%d")
        csv_filename = f"douyin_comments_{current_date}.csv"
        
        self.run_in_thread(run_comment, keyword, condition, count, csv_filename)
        
    def run_messenger(self):
        """运行私信发送"""
        csv_file = self.messenger_csv.get().strip()
        requirement = self.messenger_requirement.get().strip()
        
        if not csv_file:
            messagebox.showwarning("提示", "请选择CSV文件")
            return
        if not os.path.exists(csv_file):
            messagebox.showerror("错误", f"文件不存在: {csv_file}")
            return
        if not requirement:
            messagebox.showwarning("提示", "请输入私信要求")
            return
            
        self.run_in_thread(run_messenger, csv_file, requirement)


def main():
    root = tk.Tk()
    app = DouyinToolGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

