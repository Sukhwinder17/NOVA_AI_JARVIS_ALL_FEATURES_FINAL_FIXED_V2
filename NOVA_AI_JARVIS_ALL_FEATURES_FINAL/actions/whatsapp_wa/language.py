from __future__ import annotations
from core import config
from core.llm_router import _client,_model
def translate(text,target_language):
    text=(text or "").strip()
    if not text: raise ValueError("Enter text to translate.")
    prompt=f"Translate the following text into {target_language}. Preserve meaning, names, tone and script. Return only the translation.\n\n{text[:5000]}"
    errors=[]
    for provider,key in (("gemini",config.GEMINI_API_KEY),("groq",config.GROQ_API_KEY),("xkiro",config.XKIRO_API_KEY)):
        if not key: continue
        try:
            r=_client(provider).chat.completions.create(model=_model(provider),messages=[{"role":"user","content":prompt}],temperature=0.1)
            return r.choices[0].message.content.strip()
        except Exception as exc: errors.append(type(exc).__name__)
    raise RuntimeError("No configured NOVA AI provider could translate this text. "+", ".join(errors))
