from core.undo import undo_last, history, can_undo

def undo_action(parameters:dict, **kwargs):
    if can_undo(): return undo_last()
    return 'There is nothing for NOVA to undo.'
TOOL={'name':'undo_action','description':'Undo NOVA’s most recent reversible file or setting change. Use when the user says undo, revert, put it back, cancel that, or says NOVA got it wrong.', 'parameters':{'type':'OBJECT','properties':{}},'handler':undo_action}
