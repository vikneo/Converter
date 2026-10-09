# Dec → Hex конвертер

GUI-утилита для пакетной конвертации десятичных чисел из CSV в HEX-формат.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![CI](https://github.com/vikneo/Converter/actions/workflows/ci.yml/badge.svg)
![Build](https://github.com/vikneo/Converter/actions/workflows/build.yml/badge.svg)

## Возможности

- **Построчная обработка CSV** — память не зависит от размера файла.
- **Прогресс-бар с процентами** и возможностью отмены.
- **Настраиваемый префикс** (`0x`, `2`, `$`, `#` и т.п.).
- **Пропуск нечисловых и отрицательных значений** с логированием и номером строки.
- **Атомарная запись** результата (`.tmp` + `os.replace`) — файл не побьётся при сбое.
- **Сохранение настроек** в `~/.dec_to_hex.json`.
- **Кнопка «Открыть папку с результатом»** — кроссплатформенно.
- Работа в **отдельном потоке** — UI не «залипает» на больших файлах.

## Требования

- Python 3.10+ (используются аннотации `X | None`, `tuple[int, int]`)
- Tkinter — обычно идёт в комплекте с Python.
  - Linux: `sudo apt install python3-tk` (Debian/Ubuntu)

## Запуск из исходников

```bash
git clone <repo-url>
cd dec_to_hex
python dec_to_hex_gui.py
```

## Формат входного файла

CSV, обрабатывается только первая колонка:

```csv
value
42
255
1000
-5
abc
```

Результат (при префиксе `0x`):

```csv
0x2A
0xFF
0x3E8
```

Строки `-5` и `abc` пропускаются с сообщением в логе:

```
⚠ Строка 5: «-5» — отрицательное, пропуск
⚠ Строка 6: «abc» — не число, пропуск
```

## Сборка `.exe` (Windows)

```bash
pip install -r requirements-dev.txt
python build/build_exe.py
```

Артефакт появится в `dist/dec_to_hex.exe`.

## Где хранятся настройки

`~/.dec_to_hex.json`:

```json
{
  "input_path": "/home/user/data.csv",
  "output_path": "/home/user/data_to_hex.csv",
  "prefix": "2",
  "add_header": false,
  "last_dir": "/home/user"
}
```

Удаление файла сбрасывает настройки к значениям по умолчанию.

## Лицензия

MIT (см. `LICENSE`).