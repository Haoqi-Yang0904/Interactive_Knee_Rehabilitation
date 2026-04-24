import base64
import os
import requests

# ==========================================
# VLM 提示词工程初探 (模拟调用视觉大模型 API)
# ==========================================

# 配置您想使用的多模态大模型 API
# 请将 'sk-...' 替换为您刚刚复制的完整 API Key
API_KEY = os.getenv("API_KEY", "sk-9723f0b014434404b1aa20f4b4e3d30a") 
# 如果用阿里通义千问VL，修改下方 URL 即可
API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions" 

def encode_image(image_path):
    """将本地图片转换为可用于发送的 Base64 编码"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def get_therapist_feedback(image_path, current_angle):
    # 1. 把图片转为 base64
    base64_image = encode_image(image_path)
    
    # 2. 核心：精心设计的理疗师 Prompt
    system_prompt = """
    你现在是一位资深、温和且充满耐心的康复理疗师。患者正在进行家中膝关节康复训练。
    由于患者侧身躺着或专心做动作无法时刻盯着屏幕，你需要根据我提供的【患者康复动作照片】和系统给出的【实时膝关节角度】，给出简单、口语化、可以直接转为语音播报(TTS)的指导。

    ### 核心要求：
    1. 语气：温和、鼓励、专业，像一位贴心的教练。绝对不要使用严厉或纯医学术语。
    2. 长度：控制在一到两句话，越简短越好，适合实时语音播报。
    3. 观察重点：
       - 结合当前的角度数据赞美进度。
       - 观察照片中的动作是否变形（如骨盆向后翻转/代偿、腰部借力等）。
    4. 句式结构：[肯定/鼓励] + [具体的身体调整建议]。

    ### 输出要求：
    直接输出你对患者说的“原话”，不要包含分析过程，也不要加引号等符号。
    """
    
    user_prompt = f"当前动作类型：膝关节屈伸\n实时膝关节（小腿与大腿延长线）夹角：{current_angle}度。\n请看图片，给出你的语音指导建议。"

    # 3. 构造请求 Payload (标准的 OpenAI Vision 格式，很多国产大模型也兼容此格式)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    payload = {
        "model": "qwen-vl-plus", # 已经修改为阿里的 qwen-vl-plus
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 150
    }

    print(f"正在分析照片并请求康复大脑指导（当前假定角度: {current_angle}度）...\n")
    response = requests.post(API_URL, headers=headers, json=payload)
    
    if response.status_code == 200:
        result = response.json()["choices"][0]["message"]["content"]
        print("🤖 理疗师语音播报内容：")
        print("-" * 40)
        print(f"🔊 「{result}」")
        print("-" * 40)
    else:
        print("API 请求失败:", response.text)

if __name__ == "__main__":
    # 测试前，请准备一张测试照片命名为 'test_pose.jpg' 放在同级目录下
    test_image_path = "test_pose.jpg" 
    simulated_angle = 45 # 假设我们刚才算出来的角度是 45 度

    if not os.path.exists(test_image_path):
        print(f"❌ 找不到图片 {test_image_path}，请准备一张做动作时的测试照片放到该目录下。")
    else:
        # 注意：你需要先填入真实的 API_KEY
        if API_KEY == "your_api_key_here":
            print("⚠️ 提示: 你还没有填入真实的 API_KEY！代码将抛出鉴权错误。请在代码中填写或者设置环境变量。\n")
            
        get_therapist_feedback(test_image_path, simulated_angle)
