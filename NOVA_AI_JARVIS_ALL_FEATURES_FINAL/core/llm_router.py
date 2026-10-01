from __future__ import annotations
import json
import time
from typing import Any
from openai import OpenAI
from . import config

SYSTEM_PROMPT = '''You are NOVA AI, a capable native desktop operator and conversational assistant.

Core rule: if the user asks you to do something on the computer, DO it with the provided tools. Never merely describe how to do it and never claim an action succeeded unless the tool result says it did.

You can control applications, browsers, files, the desktop, settings, YouTube, messages, reminders, weather, flights, code, documents, screenshots, vision, monitoring and other local actions through tools. Use the narrowest direct tool that can complete the request.

For multi-step requests, execute the steps in the order the user gave them. Do not invent steps. If an action reaches outside the machine (sending a message, posting, uploading, purchasing, etc.), make sure the user explicitly asked for that action before doing it. Destructive file deletion and shutdown/restart/WiFi changes require confirmation through the app's confirmation gate.

Conversation style: concise, calm, technically competent, lightly dry when appropriate. No fake enthusiasm. No bullet lists in spoken TTS output. For the desktop chat UI, normal readable formatting is allowed.

NOVA is the assistant name. Do not call yourself JARVIS or Mark. The JARVIS/Mark-LV codebase is an internal capability source, not the assistant identity.

If the user says 'open YouTube', open YouTube. If they say 'open WhatsApp', open WhatsApp Web in Chrome. If they say 'send a message to X saying Y', use the messaging tool and report the actual result. If they say 'find files related to X', use the whole-PC file finder. If they say 'open 3', use the most recent file-finder result #3.
'''

def _client(provider: str) -> OpenAI:
    if provider == 'groq':
        if not config.GROQ_API_KEY: raise RuntimeError('Groq API key is not configured.')
        return OpenAI(api_key=config.GROQ_API_KEY, base_url=config.GROQ_BASE_URL, timeout=45.0)
    if provider == 'xkiro':
        if not config.XKIRO_API_KEY: raise RuntimeError('xKiro API key is not configured.')
        return OpenAI(api_key=config.XKIRO_API_KEY, base_url=config.XKIRO_BASE_URL, timeout=45.0)
    if provider == 'gemini':
        if not config.GEMINI_API_KEY: raise RuntimeError('Gemini API key is not configured.')
        return OpenAI(api_key=config.GEMINI_API_KEY, base_url=config.GEMINI_BASE_URL, timeout=45.0)
    raise ValueError(provider)

def _model(provider: str) -> str:
    return {'groq': config.GROQ_MODEL, 'xkiro': config.XKIRO_MODEL, 'gemini': config.GEMINI_MODEL}[provider]

def _convert_schema(schema: dict | None) -> dict:
    if not isinstance(schema, dict): return {'type':'object','properties':{}}
    def cv(v):
        if isinstance(v, dict):
            out={}
            for k,val in v.items():
                if k == 'type':
                    t=str(val).lower()
                    out[k]={'object':'object','string':'string','integer':'integer','number':'number','boolean':'boolean','array':'array'}.get(t,t)
                elif k == 'properties': out[k]={pk:cv(pv) for pk,pv in val.items()}
                elif k == 'items': out[k]=cv(val)
                else: out[k]=cv(val) if isinstance(val,(dict,list)) else val
            return out
        if isinstance(v,list): return [cv(x) for x in v]
        return v
    return cv(schema)

def build_tools(registry) -> list[dict]:
    tools=[]
    for rec in registry._actions.values():
        tools.append({'type':'function','function':{
            'name':rec.name,
            'description':rec.description,
            'parameters':_convert_schema(rec.parameters),
        }})
    return tools

def _text(msg) -> str:
    content = getattr(msg, 'content', None)
    if content is None: return ''
    if isinstance(content, str): return content
    return str(content)

def ask(provider: str, messages: list[dict], tools: list[dict], temperature: float = 0.2):
    client=_client(provider)
    resp=client.chat.completions.create(
        model=_model(provider), messages=messages, tools=tools or None,
        tool_choice='auto' if tools else None, temperature=temperature,
    )
    return resp

class LLMRouter:
    def __init__(self, registry):
        self.registry=registry
        self.tools=build_tools(registry)

    def provider_order(self, requested: str | None = None):
        p=(requested or config.AI_PROVIDER or 'auto').lower()
        if p in ('groq','gemini','xkiro'): return [p]
        return [x for x in ('groq','xkiro','gemini') if {'groq':config.GROQ_API_KEY,'xkiro':config.XKIRO_API_KEY,'gemini':config.GEMINI_API_KEY}[x]]

    def run(self, user_text: str, history: list[dict], context: dict | None = None, requested_provider: str | None = None):
        base=[{'role':'system','content':SYSTEM_PROMPT}]
        if context:
            base[0]['content'] += '\n\nLIVE MEMORY:\n' + str(context.get('memory',''))
            base[0]['content'] += '\n\nCAPABILITIES:\n' + ', '.join(sorted(self.registry.names()))
        base.extend(history[-20:])
        base.append({'role':'user','content':user_text})
        last_err=''
        for provider in self.provider_order(requested_provider):
            try:
                messages=list(base)
                for _round in range(6):
                    resp=ask(provider,messages,self.tools)
                    choice=resp.choices[0].message
                    tool_calls=getattr(choice,'tool_calls',None) or []
                    text=_text(choice)
                    if not tool_calls:
                        return text, provider
                    messages.append({'role':'assistant','content':text or None,'tool_calls':[
                        {'id':tc.id,'type':'function','function':{'name':tc.function.name,'arguments':tc.function.arguments}} for tc in tool_calls
                    ]})
                    for tc in tool_calls:
                        try: args=json.loads(tc.function.arguments or '{}')
                        except Exception: args={}
                        result=self.registry.run(tc.function.name,args,context or {})
                        messages.append({'role':'tool','tool_call_id':tc.id,'name':tc.function.name,'content':str(result)})
                return 'I reached the tool-call limit before the task was complete.', provider
            except Exception as e:
                last_err=f'{provider}: {e}'
                if provider != self.provider_order(requested_provider)[-1]:
                    continue
        return f'NOVA could not complete that request. {last_err}', 'error'
