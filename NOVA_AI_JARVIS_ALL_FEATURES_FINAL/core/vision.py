from __future__ import annotations
import base64, io
from PIL import ImageGrab
from . import config

def capture_screen():
    return ImageGrab.grab(all_screens=True)

def analyze_screen(question: str = 'Explain what is visible on my screen and what I should do next.') -> str:
    if not config.GROQ_API_KEY: return 'Groq vision is not configured.'
    img=capture_screen().convert('RGB')
    buf=io.BytesIO(); img.save(buf,format='JPEG',quality=82)
    data='data:image/jpeg;base64,'+base64.b64encode(buf.getvalue()).decode()
    from openai import OpenAI
    client=OpenAI(api_key=config.GROQ_API_KEY,base_url=config.GROQ_BASE_URL,timeout=45)
    r=client.chat.completions.create(model=config.GROQ_VISION_MODEL,messages=[{'role':'user','content':[{'type':'text','text':question},{'type':'image_url','image_url':{'url':data}}]}],max_tokens=1200)
    return r.choices[0].message.content or 'I could not read the screen.'
