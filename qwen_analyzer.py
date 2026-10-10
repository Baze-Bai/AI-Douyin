import os
import sys
import time
import json
import traceback
from typing import Optional
from dotenv import load_dotenv
from qwen_client import Chat_qwen

# 尝试加载环境变量
try:
    load_dotenv()
except Exception:
    pass

DEFAULT_PROMPT_TEMPLATE = (
"""
你是一个抖音运营助手。我会发给你视频或评论的相关信息。
你需要判断我发给你的内容是否符合以下条件：{condition}.
以下为视频相关文案或评论内容：{content}。
如果符合，则返回True，否则返回False。不要包含其他文字。
"""
)

_api_key_status_printed = False

def get_exe_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def load_qwen_config_from_file():
    """从 qwen_config.json 文件加载配置"""
    exe_dir = get_exe_dir()
    config_file = os.path.join(exe_dir, 'qwen_config.json')
    
    if not os.path.exists(config_file):
        config_file = 'qwen_config.json'
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                if 'api_key' in config and config['api_key']:
                    if not os.getenv("Qwen_API_KEY"):
                        os.environ["Qwen_API_KEY"] = config['api_key']
                if 'model' in config and config['model']:
                    if not os.getenv("QWEN_MODEL"):
                        os.environ["QWEN_MODEL"] = config['model']
        except Exception:
            pass

load_qwen_config_from_file()

def analyze_with_qwen(text_content: str, condition: str, image_path: Optional[str] = None) -> str:
    """调用 Qwen 分析视频内容
    
    Args:
        text_content: 视频文案或评论内容
        condition: 判断条件
        image_path: 可选的图片路径
    
    Returns:
        分析结果（返回 str，通常为 "True" 或 "False"）
    """
    global _api_key_status_printed
    
    load_qwen_config_from_file()
    
    api_key = os.getenv("Qwen_API_KEY")
    model = os.getenv("QWEN_MODEL", "qwen3-vl-plus")  # 使用支持思考模式的模型
    
    if not _api_key_status_printed:
        if api_key:
            masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
            print(f"✓ Qwen API Key 获取成功: {masked_key}")
        else:
            print("⚠️ Qwen API Key 未获取到，无法进行AI分析")
        _api_key_status_printed = True

    if not api_key:
        return "False"

    # 使用 DEFAULT_PROMPT_TEMPLATE 拼接完整消息
    full_message = DEFAULT_PROMPT_TEMPLATE.format(
        condition=condition,
        content=text_content
    )

    try:
        output = Chat_qwen(
            message=full_message,
            model=model,
            temperature=0.7,
            max_tokens=None,
            stream=False,
            api_key=api_key,
            images=[image_path] if image_path else None,
            enable_thinking=True,  # 启用思考模式
        )
        
        if output:
            response_text = output.strip()
            return response_text
        else:
            print("⚠️ Qwen API 返回空结果")
            return "False"
            
    except Exception as e:
        print(f"⚠️ Qwen API 调用失败: {e}")
        traceback.print_exc()
        return "False"


