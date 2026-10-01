from actions.background_monitor import add_monitor, remove_monitor, list_monitors, check_all

def background_monitor_control(parameters:dict, **kwargs):
    p=parameters or {}; a=str(p.get('action','list')).lower(); topic=str(p.get('topic','')).strip()
    if a=='add': return add_monitor(topic)
    if a=='remove': return remove_monitor(topic)
    if a=='check': return '\n'.join(check_all()) or 'No new monitored updates.'
    return '\n'.join(list_monitors()) or 'No background monitors configured.'
TOOL={'name':'background_monitor_control','description':'Manages NOVA background topic monitoring: add, remove, list or check monitored topics.', 'parameters':{'type':'OBJECT','properties':{'action':{'type':'STRING','description':'add | remove | list | check'},'topic':{'type':'STRING','description':'Topic to monitor'}},'required':['action']},'handler':background_monitor_control}
