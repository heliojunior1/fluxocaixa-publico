import sys
import os

# Adicionar src ao PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


if __name__ == '__main__':
    import uvicorn

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # O watcher precisa ignorar `.venv/`: sem isso, mexer em dependência dispara
    # restart, e como a SECRET_KEY é aleatória por processo quando não vem do
    # ambiente, cada restart derruba as sessões abertas.
    #
    # `reload_excludes` é quem faz esse trabalho, e exige caminho ABSOLUTO — o
    # filtro compara `exclude_dir in path.parents` e os eventos chegam absolutos.
    # `reload_dirs` sozinho não bastaria: o uvicorn descarta os diretórios que
    # estão sob o diretório de trabalho e observa a raiz inteira no lugar deles
    # (ver `supervisors/watchfilesreload.py`). Ele fica porque continua valendo
    # quando o processo é iniciado de fora da raiz do projeto.
    uvicorn.run(
        "fluxocaixa.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[os.path.join(BASE_DIR, "src"), os.path.join(BASE_DIR, "templates")],
        reload_excludes=[os.path.join(BASE_DIR, ".venv")],
    )
