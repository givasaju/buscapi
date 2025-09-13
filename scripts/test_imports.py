import importlib
import sys
print('PYTHON', sys.version)
for m in ('tools.custom_tools','agents.ip_agents','app_st3'):
    try:
        importlib.import_module(m)
        print(m, 'OK')
    except Exception as e:
        print(m, 'ERROR', e)
        raise
print('DONE')
