import importlib

mods = ['tasks.pdf_worker', 'flows.ip_flow']

for m in mods:
    try:
        importlib.import_module(m)
        print(f'OK: {m}')
    except Exception as e:
        print(f'ERR: {m} -> {e}')
