# Script de diagnóstico rápido para o app Streamlit
import importlib
import traceback

print('DEBUG: importando app_st3')
try:
    m = importlib.import_module('app_st3')
    App = getattr(m, 'StreamlitIPApp', None)
    if not App:
        print('ERROR: StreamlitIPApp não encontrada em app_st3')
    else:
        try:
            app = App()
            print('OK: StreamlitIPApp instanciada')
            ip_agents = getattr(app, 'ip_agents', None)
            print('ip_agents:', type(ip_agents), ip_agents is not None)
            try:
                # Testa conexão com o DB
                from database.persist_dados import BuscapiDB
                db = BuscapiDB()
                qs = db.get_all_search_queries()
                print('DB OK: total de buscas =', len(qs) if qs is not None else 'None')
                db.close()
            except Exception as e:
                print('DB ERRO:', e)
        except Exception as e:
            print('ERRO ao instanciar StreamlitIPApp')
            traceback.print_exc()
except Exception as e:
    print('ERRO ao importar app_st3:')
    traceback.print_exc()
