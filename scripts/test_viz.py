import json
import os, sys

# Garante que a raiz do projeto (pasta acima de tests) esteja no sys.path para imports relativos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pathlib import Path

from tools.custom_tools import VisualizationTool
import plotly.io as pio


def ensure_dir(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)


def main():
    analysis = {
        'count_by_category': {'Categoria A': 12, 'Categoria B': 7, 'Categoria C': 3},
        'count_by_year': {'2019': 2, '2020': 5, '2021': 9}
    }

    tool = VisualizationTool()
    out_dir = Path('static/temp_images')
    out_dir.mkdir(parents=True, exist_ok=True)

    for plot_type in ('bar', 'pie', 'line'):
        print(f"-- Generating {plot_type} --")
        result_json = tool._run(json.dumps(analysis, ensure_ascii=False), plot_type)

        # Se retornar um JSON com erro, imprime e segue
        try:
            parsed = json.loads(result_json)
        except Exception:
            parsed = None

        if isinstance(parsed, dict) and parsed.get('error'):
            print('ERROR from VisualizationTool:', parsed)
            continue

        # converte JSON do fig em objeto e grava imagem
        try:
            fig = pio.from_json(result_json)
            out_path = out_dir / f'viz_{plot_type}.png'
            fig.write_image(str(out_path))
            print('WROTE', out_path, out_path.exists())
        except Exception as e:
            print('FAILED to write image for', plot_type, e)


if __name__ == '__main__':
    main()
