Собираем систему машинного перевода. Основной язык - английский. Перевод на русский, английский, вьетнамский, монгольский - в приоритете. Остальные языки не лишние.
Система развернута полностью on-premises, без использования облачных сервисов.

Система многопользовательская, web. 
Делается на двух серверах.

|            | pc001           | pc002                                |
| ---------- | --------------- | ------------------------------------ |
| Назначение | Инференс модели | пользовательский интерфейс, frontend |
|            | dedicated PC    | HyperV VM                            |
| hostname   | pc001           | pc002                                |
| ip         | 195.168.33.129  | 195.168.33.45                        |
| CPU        | Core i5 8 cores | 4 virtual processor                  |
| RAM        | 8G              | 4G                                   |
| Videocard  | Nvidia 3070     | -                                    |
| OS         | Debian 13.4     | Debian 13.4                          |
На обоих машинах установлен Docker. Если на хосте используем Python, то через uv.

## Архитектура:
### pc001
NLLB inference сервер, в своём контейнере. Взаимодействие с ним через API (реализация на FastAPI)
Стек:
- Python 3.12
- Менеджер пакетов `uv`
- API `FastAPI`
- Библиотеки: `PyTorch`, `transformers`, `accelerate`

Для перевода будем модель `facebook/nllb-200-distilled-600M`. Когда RAM будет больше, поменяем модель на `facebook/nllb-200-distilled-1.3B`

**Сервер**
Сервер самописный на python, работает внутри контейнера. Endpoints:
- POST /translate
- GET /health
- GET /languages

### pc002
- Nginx, FastApi, что-то ещё - на следующих этапах

### Этапы работы:

1. **Этап 1 (базовый):**
    - настроить среду разработки
    - написать сервер (базовый api):
	    - GET /health (состояние сервера, доступность gpu)
	    - GET /languages (список языков в формате nllb / человеческом. Приоритетные - наверху)
	    - POST /translate (что переводим, с какого, на какой)
2. **Этап 2 (оптимизация перевода):**
	- Разбивка текста на чанки (строки/абзацы/предложения/слова). Выбор оптимального чанка для передачи в модель
	- В ответе метода /translate - помимо перевода - статистика (строк, предложений, абзацев)
	- Автоматическое определение исходного языка
	- рассмотреть использование словаря синонимов (возможно, не для всех языков)
3. **Подбор архитектуры Frontend
	- После реализации предыдущих этапов
4. **Этап 3 Дальнейшие работы:** 
    - Оптимизации, мониторинг - только после предыдущих этапов

## Реализация:
### PC001 (inference engine, NLLB)

**1 этап**
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

Загружены библиотеки `accelerate`, `fastapi`, `uvicorn`, `torch`, `transformers`

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


**2 этап**
Разделяем конвеер:
```
raw text      - при вызове эндпоинта /translate
↓
normalize
↓
paragraph split
↓
sentence split (pySBD)
↓
smart chunk merge
↓
translate chunks
↓
reassemble
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