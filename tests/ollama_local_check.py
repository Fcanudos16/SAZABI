"""Read-only local service check. Does not download models or send evidence."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.ai_provider import list_models, OllamaError

if __name__ == '__main__':
    reconfigure = getattr(sys.stdout, 'reconfigure', None)
    if callable(reconfigure):
        reconfigure(encoding='utf-8')
    try:
        models = list_models()
        print('Modelos locais: ' + ', '.join(models) if models else 'Ollama ativo, sem modelos locais instalados.')
    except OllamaError as error:
        print(str(error))
        raise SystemExit(1)
