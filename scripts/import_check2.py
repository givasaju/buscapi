import importlib
mods=['app_st3','flows.ip_flow','tasks.pdf_worker']
for m in mods:
    try:
        importlib.import_module(m)
        print('OK:', m)
    except Exception as e:
        print('ERR:', m, e)
