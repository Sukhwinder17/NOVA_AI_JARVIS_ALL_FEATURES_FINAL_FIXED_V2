from actions.system_monitor import get_system_status

def system_status(parameters:dict, **kwargs):
    s=get_system_status(); return 'System status: '+', '.join(f'{k}={v}' for k,v in s.items())
TOOL={'name':'system_status','description':'Returns real current CPU, memory, GPU and temperature telemetry when available. Use only when asked for system status.', 'parameters':{'type':'OBJECT','properties':{}},'handler':system_status}
