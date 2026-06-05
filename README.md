Machine translating systems

Languages: EN + member countries (Russia, Mongolia, Vietnam, Cuba) + former member countries (Hungary, Romania, Bulgaria, Czech, Slovakia ). Other languages also may be available.

System works TOTALLY on-premises, no cloud services.

Система многопользовательская, web. 

Делается на двух серверах. Третий сервер внутри сетевого периметра - к нему только подключаемся, out of project scope/.

|              | pc001           | pc002                                | pc003                          |
| ------------ | --------------- | ------------------------------------ |------------------------------- |
| Назначение   | Backend,        |                                      | LLAMA.cpp with LLMs 
|              | NLLB Inference  | пользовательский интерфейс, frontend | 
| machine type | dedicated PC    | HyperV VM                            |
| hostname     | pc001           | pc002                                |
| ip           | 195.168.33.129  | 195.168.33.45                        |
| CPU          | Core i5 8 cores | 4 virtual processor                  |
| RAM          | 8G              | 4G                                   |
| Videocard    | Nvidia 3070     | -                                    |
| OS           | Debian 13.4     | Debian 13.4                          |

На pc001 установлен Docker. Для взаимодействия с python используем uv, even inside Docker containers.

## Архитектура:
### pc001
Backend.
There should be options:
	- NLLB inference right on pc001
	- Interaction with LLM on LLAMA.c
Стек:
- Python 3.12
- Менеджер пакетов `uv`
- API `FastAPI`
- Библиотеки: see in file nllb-server/pyproject.toml

Для перевода будем модель `facebook/nllb-200-distilled-600M`. Когда RAM будет больше, поменяем модель на `facebook/nllb-200-distilled-1.3B` или другую.
Следует предусмотреть возможность осуществления перевода на третьей машине с llama.cpp - на следующих этапах

ВАЖНО: нужно иметь возможность сохранять форматирование исходного текста. Формат - только Markdown, этого достаточно. IN NEXT RELEASES: should be a possibility to convert input file to MD -> translate. Maybe using of `pandoc` or `microsoft/markdown` makes sense to convert to MD and back.

**Сервер**
Сервер пишем на на python. Используем FastAPI. Прод работает внутри контейнера. Отладка напрямую

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
