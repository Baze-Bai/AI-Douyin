from typing import List, Optional, Union
import os
import base64
import mimetypes
import pathlib
from dotenv import load_dotenv


def Chat_qwen(
    message: str,
    model: str = "qwen3-vl-flash",
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    stream: bool = True,
    api_key: Optional[str] = None,
    images: Optional[List[str]] = None,
    enable_thinking: bool = False,
    thinking_budget: int = 81920,
) -> Optional[str]:
    """
    向阿里云百炼API（OpenAI兼容模式）发送对话请求

    Args:
        message: 消息字符串
        model: 模型名称，默认 "qwen3-vl-flash"
        temperature: 生成温度
        max_tokens: 最大生成token数量
        stream: 是否以流式方式返回
        api_key: 若为None，则从环境变量 Qwen_API_KEY 读取（支持 .env 文件）
        images: 可选的图片路径列表
        enable_thinking: 是否启用模型思考过程（仅支持特定模型），默认 False
        thinking_budget: 最大推理过程 Token 数，默认 81920

    Returns:
        模型回复文本；失败返回 None
    """
    from openai import OpenAI

    # API Key
    if api_key is None:
        # 加载 .env 文件中的环境变量
        load_dotenv()
        api_key = os.getenv("Qwen_API_KEY")
        if not api_key:
            print("错误: 未找到Qwen_API_KEY环境变量")
            print("提示: 请在 .env 文件中设置 Qwen_API_KEY=your-api-key")
            return None

    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1/",
    )

    def _to_image_content_item(url_or_path: str) -> Optional[dict]:
        # http/https 直接用 URL
        if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
            return {"type": "image_url", "image_url": {"url": url_or_path}}
        # 本地文件 -> data URL
        p = pathlib.Path(url_or_path)
        if p.exists() and p.is_file():
            try:
                mime, _ = mimetypes.guess_type(str(p))
                mime = mime or "application/octet-stream"
                b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
                data_url = f"data:{mime};base64,{b64}"
                return {"type": "image_url", "image_url": {"url": data_url}}
            except Exception:
                return None
        return None

    print(f"\n{'='*60}")
    print(f"开始处理请求...")
    print(f"{'='*60}")
    
    # 打印最终输入的 Prompt
    print(f"\n【输入的 Prompt】:")
    print(f"{'-'*60}")
    # 截断过长的 prompt
    if len(message) > 500:
        print(f"{message[:500]}...")
        print(f"(完整长度: {len(message)} 字符)")
    else:
        print(message)
    print(f"{'-'*60}")

    try:
        # 组装图文多模态 content
        content_items: List[dict] = []
        
        if images:
            print(f"\n【输入的图片】:")
            for idx, im in enumerate(images, 1):
                item = _to_image_content_item(str(im))
                if item:
                    content_items.append(item)
                    print(f"  [{idx}] {im}")
            print(f"{'-'*60}")
        
        # 文本放在最后
        content_items.append({"type": "text", "text": message})

        request_params = {
            "model": model,
            "messages": [{"role": "user", "content": content_items if content_items else message}],
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens is not None:
            request_params["max_tokens"] = max_tokens
        
        # 添加思考模式支持
        if enable_thinking:
            request_params["extra_body"] = {
                "enable_thinking": True,
                "thinking_budget": thinking_budget
            }

        completion = client.chat.completions.create(**request_params)

        full_content = ""
        reasoning_content = ""  # 思考过程
        is_answering = False
        
        if stream:
            # 流式响应处理
            if enable_thinking:
                print(f"\n{'='*60}")
                print(f"【思考过程】:")
                print(f"{'='*60}\n")
            else:
                print(f"\n开始流式输出...\n")
            
            for chunk in completion:
                # 检查是否有usage信息（可能在最后一个chunk）
                if not getattr(chunk, "choices", None) or len(chunk.choices) == 0:
                    if hasattr(chunk, "usage"):
                        print(f"\n{'-'*60}")
                        print(f"Token使用量: {chunk.usage}")
                        print(f"{'-'*60}")
                    continue
                
                delta = chunk.choices[0].delta
                
                # 处理思考过程
                if enable_thinking and hasattr(delta, 'reasoning_content') and delta.reasoning_content is not None:
                    print(delta.reasoning_content, end='', flush=True)
                    reasoning_content += delta.reasoning_content
                # 处理正常回复
                elif delta.content is not None:
                    # 如果刚开始回复，打印分隔线
                    if enable_thinking and not is_answering and delta.content != "":
                        print(f"\n{'='*60}")
                        print(f"【模型回复】:")
                        print(f"{'='*60}\n")
                        is_answering = True
                    
                    content = delta.content
                    full_content += content
                    print(content, end="", flush=True)
            
            print()
        else:
            # 非流式响应处理
            print(f"\n等待模型响应...\n")
            if (
                hasattr(completion, "choices")
                and len(completion.choices) > 0
                and hasattr(completion.choices[0], "message")
            ):
                message_obj = completion.choices[0].message
                
                # 如果启用了思考模式，提取思考内容
                if enable_thinking and hasattr(message_obj, "reasoning_content") and message_obj.reasoning_content:
                    reasoning_content = message_obj.reasoning_content
                    print(f"{'='*60}")
                    print(f"【思考过程】:")
                    print(f"{'='*60}\n")
                    print(reasoning_content)
                    print(f"\n{'='*60}")
                    print(f"【模型回复】:")
                    print(f"{'='*60}\n")
                
                # 提取回复内容
                if message_obj.content is not None:
                    full_content = message_obj.content
                    if len(full_content) > 500:
                        print(f"{full_content[:500]}...")
                        print(f"\n(完整长度: {len(full_content)} 字符)")
                    else:
                        print(full_content)
        
        print(f"\n{'='*60}")
        print(f"✓ 请求处理完成")
        print(f"{'='*60}\n")
        return full_content
        
    except Exception as e:
        error_type = type(e).__name__
        print(f"请求错误 ({error_type}): {e}")
        return None


