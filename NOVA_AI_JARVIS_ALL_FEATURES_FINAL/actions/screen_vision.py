from core.vision import analyze_screen

def screen_vision(parameters:dict, **kwargs):
    p=parameters or {}
    return analyze_screen(str(p.get('question') or 'Explain what is visible on my screen, including errors and the next useful step.'))

TOOL={
 'name':'screen_vision',
 'description':'Captures the current Windows screen and analyzes it with NOVA vision. Use for explain this screen, what is happening, read visible errors, explain SQL/code shown on screen.',
 'parameters':{'type':'OBJECT','properties':{'question':{'type':'STRING','description':'What to inspect or explain'}},'required':[]},
 'handler':screen_vision,
}
