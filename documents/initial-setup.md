Установлены и настроены драйверы видеокарты, nvidia-container-toolkit, проброс видеокарты в контейнер.
```sh
sudo nvidia-ctk runtime configure --runtime=docker 
sudo systemctl restart docker
```

Проект размещаем в `/opt/mt`. Пользователь - localadmin имеет права 755 на эту директорию.
Структура проекта:
```
/opt/mt/
├── docker-compose.yml
├── data/
│   └── ?                         # Сюда кладём файлы с тест-кейсами
├── nllb-server/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── main.py (или server.py)   # точка входа
│   ├── engine.py                 # Работа с моделью только в части перевода
│   ├── schemas.py                # Pydantic Request/Response
│   ├── utils.py                  # Всё прочее (маппинг языков, разбивка текста...)
│   └── ?
├── models/                       # веса (загружаем вручную)
├── cache/                        # кэщ трансформеров
```

Создаём проект и инициализируем репозиторий:
```sh
sudo mkdir /opt/mt
sudo chown localadmin:localadmin /opt/mt
cd /opt/mt
mkdir ./nllb-server
mkdir ./models
mkdir ./cache

git init

cat <<EOF >.gitignore
# Python-generated files
__pycache__/
*.py[oc]
build/
dist/
wheels/
*.egg-info

# Virtual environments
.venv
# Huge size models
models
```

Загружаем модели с hugging face (через uvx). Директорию с моделями - в .gitignore.
```sh
MODEL_NAME=facebook/nllb-200-distilled-600M
TOKEN=hf_secret_token
uvx --from huggingface-hub hf download "${MODEL_NAME}" --local-dir "./models/${MODEL_NAME}" --type=model --token="${TOKEN}
echo "models/" >> .gitignore
```

На время разработки сервер можно запускать напрямую, не в контейнере. Тем не менее, приложение контейнеризуем (через docker compose).

Инициализируем проект в директории `nllb-server`:
```sh
cd /opt/mt/nllb-server
uv python pin 3.12
uv init --app --name "nllb-server" --description "NLLB Server for Machine Translation"
uv add accelerate fastapi uvicorn torch transformers
uv venv
uv sync
```

Проверяем доступность cuda (должно быть `true`):
```sh
uv run python -c "import torch; print(torch.cuda.is_available())"
```

### Запуск проекта:
Во время разработки проект можно запускать локально, так:
```sh
cd nllb-server
uv run main/py
```
или так:
```sh
cd nllb-server
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

А также можно побилдить образ и запустить в контейнере:
```
docker-compose up --build -d
```