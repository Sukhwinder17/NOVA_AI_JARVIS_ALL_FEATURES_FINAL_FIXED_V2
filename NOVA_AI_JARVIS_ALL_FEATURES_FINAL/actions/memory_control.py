from __future__ import annotations
from memory.memory_manager import load_memory, update_memory, search_memory, save_memory, remember, forget_memory

def memory_control(parameters:dict, **kwargs):
    p=parameters or {}; action=str(p.get('action','recall')).lower(); query=str(p.get('query','')).strip(); category=str(p.get('category','notes')).strip() or 'notes'; key=str(p.get('key','')).strip(); value=str(p.get('value','')).strip()
    if action in ('save','remember'):
        return remember(key, value, category)
    if action in ('recall','search'):
        return search_memory(query or key)
    if action in ('all','list'): return str(load_memory())
    return 'Unknown memory action.'
TOOL={'name':'memory_control','description':'Persistent local memory: save, remember, recall, search and list stored facts. Use when the user asks NOVA to remember or recall personal/project context.', 'parameters':{'type':'OBJECT','properties':{'action':{'type':'STRING','description':'save | recall | search | list'},'category':{'type':'STRING','description':'identity | preferences | projects | relationships | wishes | notes'},'key':{'type':'STRING'},'value':{'type':'STRING'},'query':{'type':'STRING'}},'required':['action']},'handler':memory_control}
