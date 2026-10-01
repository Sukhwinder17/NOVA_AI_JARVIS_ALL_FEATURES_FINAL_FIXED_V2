from __future__ import annotations
from pathlib import Path
import os

def invoice_generator(parameters:dict, **kwargs):
    p=parameters or {}; template=Path(str(p.get('template',''))).expanduser(); output=Path(str(p.get('output','invoice.txt'))).expanduser()
    if not template.exists(): return 'Invoice template is missing. Provide a real template containing the company registration number, bank details and address placeholders; NOVA will not invent those fields.'
    text=template.read_text(encoding='utf-8',errors='replace')
    for key,val in (p.get('fields') or {}).items(): text=text.replace('{{'+str(key)+'}}',str(val))
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(text,encoding='utf-8'); os.startfile(str(output)) if os.name=='nt' else None
    return f'Invoice rendered and opened: {output}'
TOOL={'name':'invoice_generator','description':'Renders an invoice from the user’s real template and opens it. Never invent company registration, bank or address fields.', 'parameters':{'type':'OBJECT','properties':{'template':{'type':'STRING'},'output':{'type':'STRING'},'fields':{'type':'OBJECT'}},'required':['template']},'handler':invoice_generator}
