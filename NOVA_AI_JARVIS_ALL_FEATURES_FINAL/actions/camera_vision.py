from __future__ import annotations
import base64,io,os
from PIL import Image
from core import config

def camera_vision(parameters:dict, **kwargs):
    import cv2
    cap=cv2.VideoCapture(0,cv2.CAP_DSHOW if os.name=='nt' else 0)
    if not cap.isOpened(): return 'Camera is not available.'
    ok,frame=cap.read(); cap.release()
    if not ok:return 'Camera capture failed.'
    frame=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB); img=Image.fromarray(frame); b=io.BytesIO(); img.save(b,format='JPEG',quality=82)
    data='data:image/jpeg;base64,'+base64.b64encode(b.getvalue()).decode()
    question=str((parameters or {}).get('question') or 'Describe what the camera can see and identify the important visible details.')
    from openai import OpenAI
    client=OpenAI(api_key=config.GROQ_API_KEY,base_url=config.GROQ_BASE_URL,timeout=45)
    r=client.chat.completions.create(model=config.GROQ_VISION_MODEL,messages=[{'role':'user','content':[{'type':'text','text':question},{'type':'image_url','image_url':{'url':data}}]}],max_tokens=1000)
    return r.choices[0].message.content or 'I could not interpret the camera frame.'

TOOL={
 'name':'camera_vision',
 'description':'Captures one webcam frame and analyzes it with NOVA vision. Use when the user asks what the camera sees or asks NOVA to inspect something in front of the webcam.',
 'parameters':{'type':'OBJECT','properties':{'question':{'type':'STRING','description':'What to inspect in the camera frame'}},'required':[]},
 'handler':camera_vision,
}
