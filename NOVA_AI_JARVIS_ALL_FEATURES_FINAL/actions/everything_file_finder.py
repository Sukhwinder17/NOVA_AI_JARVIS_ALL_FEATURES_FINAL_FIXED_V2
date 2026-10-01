from __future__ import annotations
from tools.everything_file_finder import search, open_result

def everything_file_finder(parameters: dict, player=None, **kwargs) -> str:
    p=parameters or {}; action=str(p.get('action','search')).lower().strip()
    if action in ('open','open_result'):
        result=open_result(str(p.get('ref','')).strip())
        if player and hasattr(player,'write_log'): player.write_log('[files] '+result)
        return result
    query=str(p.get('query','')).strip()
    limit=max(5,min(100,int(p.get('limit',40) or 40)))
    rows, cleaned=search(query,limit)
    if not rows: return f'No relevant files found for: {cleaned}'
    lines=[f'Found {len(rows)} relevant file(s) for: {cleaned}']
    lines += [f'{i:02d}. {p}' for i,p in enumerate(rows,1)]
    lines.append("Say 'open N' or 'open <filename>' to open one of these results.")
    result='\n'.join(lines)
    if player and hasattr(player,'write_log'): player.write_log('[files] '+result)
    return result

TOOL={'name':'everything_file_finder','description':'Searches the entire Windows PC with Everything and returns a clean numbered list. Use for natural-language requests to find files/projects/PDFs/documents. Then use action=open with the recent result number or filename to open one.', 'parameters':{'type':'OBJECT','properties':{'action':{'type':'STRING','description':'search | open'},'query':{'type':'STRING','description':'What to find anywhere on the PC'},'limit':{'type':'INTEGER','description':'Maximum results 5-100'},'ref':{'type':'STRING','description':'Recent result number or filename for open'}},'required':['action']},'handler':everything_file_finder}
