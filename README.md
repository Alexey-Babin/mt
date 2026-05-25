Собираем систему машинного перевода. 

Languages: EN + member countries (Russia, Mongolia, Vietnam, Cuba) + former member countries (Hungary, Romania, Bulgaria, Czech, Slovakia ). Other languages also may be available.

Система развернута полностью on-premises, без использования облачных сервисов.

Система многопользовательская, web. 

Делается на двух серверах.

|            | pc001           | pc002                                |
| ---------- | --------------- | ------------------------------------ |
| Назначение | LLM Inference   | пользовательский интерфейс, frontend |
|            | dedicated PC    | HyperV VM                            |
| hostname   | pc001           | pc002                                |
| ip         | 195.168.33.129  | 195.168.33.45                        |
| CPU        | Core i5 8 cores | 4 virtual processor                  |
| RAM        | 8G              | 4G                                   |
| Videocard  | Nvidia 3070     | -                                    |
| OS         | Debian 13.4     | Debian 13.4                          |
На обоих машинах установлен Docker. Для взаимодействия с python используем uv.

## Архитектура:
### pc001
NLLB inference сервер, в своём контейнере. Взаимодействие с ним через API (реализация на FastAPI)
Стек:
- Python 3.12
- Менеджер пакетов `uv`
- API `FastAPI`
- Библиотеки: see in file nllb-server/pyproject.toml

Для перевода будем модель `facebook/nllb-200-distilled-600M`. Когда RAM будет больше, поменяем модель на `facebook/nllb-200-distilled-1.3B`

ВАЖНО: нужно иметь возможность сохранять форматирование исходного текста. Формат - только Markdown, этого достаточно. IN NEXT RELEASES: should be a possibility to convert input file to MD -> translate. Maybe using of `pandoc` or `microsoft/markdown` makes sense to convert to MD and back.

**Сервер**
Сервер пишем на на python. Используем FastAPI. Прод работает внутри контейнера.

Endpoints:
1. POST /translate 
Input:
	- text to be translated,
	- source language,
	- target language,
	- preserve format (MD) - optional. System detects wether MD or raw text
	- response in stream or in single chunk - IN NEXT RELEASES
Output:
	- translated text
	- stats (words, paragraphs, tokens...) - IN NEXT RELEASES

2. GET /health
Output:
	- Is server up and running
	- Use GPU
	- Model

3. GET /languages
Input:
	- Which languages we are using: 
		* member countries + EN (ENG, RUS, MNG, VIE, CUB), 
		* member and former member countries (+ HUN, ROM, CZK, SK, ...)
		* all
Output:
	List of languages in EN, RU, ISO, NLLB code.

### pc002
- Nginx, FastApi, что-то ещё - NEXT STAGES

## Этапы работы:

1. **Этап 1 (базовый):**
    - настроить среду разработки (done)
	- настроить среду тестирования (done, но надо добавить работу с плагином vs code)
    - написать сервер (базовый api):
	    - GET /health (состояние сервера, доступность gpu)
	    - GET /languages (список языков в формате nllb / человеческом. Приоритетные - наверху)
	    - POST /translate (plain text, no http stream, no statistics) - done
	На первом этапе система без оптимизаций.

2. **Этап 2 (Chunking):**
	- Разбивка текста на чанки (строки/абзацы/предложения/слова). Выбор оптимального чанка для передачи в модель (done)

3. **Этап 3 (Поддержка форматирования):**
	- добавляем параметр к методу POST /translate (preserve format)
	- Работа с исходным текстом:
	  * запомнить структуру
	  * Выделить **ТОЛЬКО ТЕКСТ, ПОДЛЕЖАЩИЙ ПЕРЕВОДУ**, 
	  * Перевести все куски текста _с максимальным сохранением контекста_, с учетом разбивки на части как в предыдущем этапе
	  * Собрать структуру обратно
	  * преобразовать опять в md
	  * отправить потребителю

	Допускается использование как библиотек, так и стороннего ПО (предложи)

4. **Этап 4 (Оптимизация):**
	- Доработка 2 этапа Сделать markdown-aware chunk splitting. Проверить тесты.
	- Добавляем Batch translation
	- В ответе метода /translate - помимо перевода - статистика (строк, предложений, абзацев) 

5. **Этап 5 (расширение функционала)**
	- Автоматическое определение исходного языка
	- использование словаря синонимов (возможно, не для всех языков)

6. **Подбор архитектуры Frontend**
	- После реализации предыдущих этапов

7. **Этап 3 Дальнейшие работы:** 
    - Оптимизации, мониторинг - только после предыдущих этапов
	

## Структура проекта:
```
/opt/mt/
├── cache/
├── data/														# Сюда кладём файлы с тест-кейсами
├── docker-compose.dev.yml
├── docker-compose.yml
├── models/														# веса (загружаем вручную)
│   └── nllb-200-distilled-600M
├── nllb-server/
│   ├── Dockerfile
│   ├── Dockerfile.dev
│   ├── languages.json											# Список языков
│   ├── pyproject.toml
│   ├── src/
│   │   ├── mt_server/
│   │       ├── __init__.py
│   │       ├── config.py
│   │       ├── engine.py
│   │       ├── format_detection.py
│   │       ├── languages.py
│   │       ├── main.py											# !!! точка входа
│   │       ├── markdown/                                       # Модуль работы с форматированием
│   │       │   ├── __init__.py
│   │       │   ├── extractor.py
│   │       │   ├── placeholders.py
│   │       │   ├── translator.py
│   │       │   └── units.py
│   │       ├── translation_service.py
│   │       └── utils.py
│   └── uv.lock
└── README.md
```