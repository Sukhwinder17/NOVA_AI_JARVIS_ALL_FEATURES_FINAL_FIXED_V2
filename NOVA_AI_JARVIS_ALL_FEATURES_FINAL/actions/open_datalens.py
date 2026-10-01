from tools.datalens import open_datalens

def handler(parameters:dict, **kwargs): return open_datalens()
TOOL={'name':'open_datalens','description':'Opens the deployed NOVA DataLens app directly in the user browser. Use for open/start/launch DataLens.', 'parameters':{'type':'OBJECT','properties':{}},'handler':handler}
