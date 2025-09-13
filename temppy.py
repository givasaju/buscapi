import os, sys
import importlib


# Garante que a raiz do projeto (pasta acima de tests) esteja no sys.path para imports relativos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))



try:
    m = importlib.import_module('app_st3')
    App = getattr(m, 'StreamlitIPApp', None)
    if App:
        a = App()
        print('OK: StreamlitIPApp instantiated')
    else:
        print('ERROR: StreamlitIPApp not found')
except Exception as e:
    import traceback
    traceback.print_exc()
    print('IMPORT ERROR:', e)