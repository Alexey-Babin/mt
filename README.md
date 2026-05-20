## Nachine Translation

Собираем систему машинного перевода. Основной язык - русский. Перевод на русский, английский, вьетнамский, монгольский.
Система развернута полностью on-premises, без использования облачных сервисов.
Система многопользовательская, web. Аутентификация - ?? (для начала - username/password или jwt, на следующих этапах - ldap)
Делается на двух серверах.


|            | pc001           | pc002                      |
| ---------- | --------------- | -------------------------- |
| Назначение | Инференс модели | пользовательский интерфейс |
|            | dedicated PC    | HyperV VM                  |
| hostname   | pc001           | pc002                      |
| ip         | 195.168.33.129  | 195.168.33.45              |
| CPU        | Core i5 8 cores | 4 virtual processor        |
| RAM        | 8G              | 4G                         |
| Videocard  | Nvidia 3070     | -                          |
| OS         | Debian 13.4     | Debian 13.4                |
На обоих машинах установлен Docker. Если на хосте используем Python, то через uv.

## Архитектура:
### pc001
NLLB inference сервер, в своём контейнере. Взаимодействие с ним через API (реализация на FastAPI)
Стек:
- Python 3.12
- Менеджер пакетов `uv`
- API `FastAPI`
- Библиотеки: `PyTorch`, `transformers`, `accelerate`

Для перевода будем модель `facebook/nllb-200-distilled-300M`. Когда RAM будет больше, поменяем модель на `facebook/nllb-200-distilled-600M` или `facebook/nllb-200-distilled-1.3B`

**Сервер**
Сервер самописный на python или typescript, внутри контейнера. Endpoints:
- POST /translate
- GET /health
- GET /languages

**Оптимизации:**
- `batch_size=1` (интерактив), `torch.inference_mode()`
*  Использовать `torch.compile` (PyTorch 2.0+)
- При необходимости добавить `bitsandbytes` 8-bit (снизит качество на 1-2 BLEU, но сэкономит память)

### pc002
- Nginx, FastApi, что-то ещё - на следующих этапах
