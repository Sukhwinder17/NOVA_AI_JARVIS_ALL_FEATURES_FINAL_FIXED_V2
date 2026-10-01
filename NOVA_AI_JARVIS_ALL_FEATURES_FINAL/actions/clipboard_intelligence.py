from __future__ import annotations
import base64,io
from PIL import ImageGrab
from core import config

def clipboard_intelligence(parameters:dict, **kwargs):
    import pyperclip
    text=pyperclip.paste() or ''
    if not text.strip(): return 'The clipboard is empty.'
    q=str((parameters or {}).get('action') or 'explain').lower(); prompts={'explain':'Explain this clipboard text clearly.','summarize':'Summarize this clipboard text.','translate':'Translate this clipboard text to English.','fix':'Fix the clipboard text while preserving its meaning.','analyze':'Analyze this clipboard text.'}
    from openai import OpenAI
    client=OpenAI(api_key=config.GROQ_API_KEY,base_url=config.GROQ_BASE_URL,timeout=45)
    r=client.chat.completions.create(model=config.GROQ_MODEL,messages=[{'role':'system','content':prompts.get(q,prompts['explain'])},{'role':'user','content':text}],max_tokens=1200)
    return r.choices[0].message.content or 'No result.'
TOOL={'name':'clipboard_intelligence','description':'Reads current clipboard text and can explain, summarize, translate, analyze or fix it using NOVA.', 'parameters':{'type':'OBJECT','properties':{'action':{'type':'STRING','description':'explain | summarize | translate | fix | analyze'}},'required':['action']},'handler':clipboard_intelligence}
