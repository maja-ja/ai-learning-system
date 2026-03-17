import google.generativeai as genai
import json

genai.configure(api_key="YOUR_API_KEY")

def decode_text(text):

    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""
    將以下內容轉成知識卡 JSON：

    {text}

    格式：

    {{
        "word": "",
        "definition": "",
        "meaning": "",
        "example": ""
    }}
    """

    response = model.generate_content(prompt)

    try:
        return json.loads(response.text)
    except:
        return {
            "word": text,
            "definition": response.text,
            "meaning": "",
            "example": ""
        }