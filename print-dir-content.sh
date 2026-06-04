#!/bin/sh

# Проверка аргументов
if [ $# -ne 1 ]; then
    echo "Usage: $0 <directory>"
    exit 1
fi

TARGET_DIR="$1"

# Проверка существования директории
if [ ! -d "$TARGET_DIR" ]; then
    echo "Error: Directory '$TARGET_DIR' not found"
    exit 1
fi

# Рекурсивный обход файлов, исключая скрытые и служебные директории
find "$TARGET_DIR" -type f \
    -not -path "*/.*/*" \
    -not -path "*/__pycache__/*" \
    -not -path "*/node_modules/*" \
    -not -path "*/.git/*" \
    -not -path "*/.svn/*" \
    -not -path "*/.hg/*" \
    -not -path "*/venv/*" \
    -not -path "*/env/*" \
    -not -path "*/dist/*" \
    -not -path "*/build/*" \
    -not -path "*/.idea/*" \
    -not -path "*/.vscode/*" \
    -not -path "*/target/*" \
    -not -path "*/.next/*" \
    -not -path "*/vendor/*" \
    -not -path "*/.cache/*" \
    -not -path "*/tmp/*" \
    -not -path "*/temp/*" \
    -not -path "*/*.egg-info/*" \
    2>/dev/null | while read -r file; do
    
    # Пропускаем скрытые файлы (начинающиеся с точки)
    basename_file=$(basename "$file")
    case "$basename_file" in
        .*) continue ;;
    esac
    
    # Пропускаем конкретные служебные файлы
    case "$basename_file" in
        uv.lock|package-lock.json|yarn.lock|pnpm-lock.yaml|Cargo.lock|Gemfile.lock|composer.lock|poetry.lock|languages.json)
            continue ;;
    esac
    
    # Выводим разделитель и путь к файлу
    echo "---------------------------------------"
    echo "$file"
    echo "---------------------------------------"

    # Определяем расширение файла для указания языка в маркере
    extension="${file##*.}"
    
    # Определяем язык для подсветки синтаксиса
    case "$extension" in
        py|python) lang="python" ;;
        js|javascript) lang="javascript" ;;
        sh|bash|zsh) lang="bash" ;;
        md|markdown) lang="markdown" ;;
        json) lang="json" ;;
        xml) lang="xml" ;;
        html|htm) lang="html" ;;
        css) lang="css" ;;
        c) lang="c" ;;
        cpp|cc|cxx) lang="cpp" ;;
        java) lang="java" ;;
        go) lang="go" ;;
        rs) lang="rust" ;;
        rb) lang="ruby" ;;
        php) lang="php" ;;
        sql) lang="sql" ;;
        yml|yaml) lang="yaml" ;;
        txt) lang="text" ;;
        *) lang="" ;;
    esac
    
    # Выводим содержимое с маркерами
    if [ -n "$lang" ]; then
        echo "\`\`\`$lang"
    else
        echo "\`\`\`"
    fi
    
    cat "$file"
    echo "\`\`\`"
done

# Финальный разделитель
echo "---------------------------------------"