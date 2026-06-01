#!/usr/bin/env bash
set -euo pipefail

FAILED=0

pass() {
    echo "PASS: $1"
}

fail() {
    echo "FAIL: $1: $2"
    FAILED=1
}

check_gitignore_entries() {
    local missing=()
    local required_entries=(".env" "data/" "__pycache__/" ".venv/")

    for entry in "${required_entries[@]}"; do
        if ! grep -qxF "$entry" .gitignore; then
            missing+=("$entry")
        fi
    done

    if [ "${#missing[@]}" -eq 0 ]; then
        pass ".gitignore includes core entries"
    else
        fail ".gitignore includes core entries" "missing ${missing[*]}"
    fi
}

check_env_example_fields() {
    local missing=()
    local required_fields=(
        "DEEPSEEK_API_KEY"
        "DB_PATH"
        "UPLOAD_DIR"
        "MAX_UPLOAD_SIZE_MB"
        "FREE_QUESTION_PER_PROJECT"
        "MONTHLY_QUOTA"
        "LOG_LEVEL"
    )

    for field in "${required_fields[@]}"; do
        if ! grep -q "^${field}=" .env.example; then
            missing+=("$field")
        fi
    done

    if [ "${#missing[@]}" -eq 0 ]; then
        pass ".env.example includes required fields"
    else
        fail ".env.example includes required fields" "missing ${missing[*]}"
    fi
}

check_no_key_leaks() {
    local pattern="your-api-key\|sk-real\|sk-prod\|sk-live"

    if hits=$(grep -rn "$pattern" --include="*.example" --include="*.toml" \
        --exclude-dir=".venv" --exclude-dir=".git" . 2>/dev/null); then
        fail "no leaked real-looking API keys" "$hits"
    else
        pass "no leaked real-looking API keys"
    fi
}

check_no_todos() {
    local pattern="TODO\|FIXME\|XXX"

    if hits=$(grep -rn "$pattern" --include="*.py" \
        --exclude-dir=".venv" --exclude-dir=".git" . 2>/dev/null); then
        fail "no TODO/FIXME/XXX in .py files" "$hits"
    else
        pass "no TODO/FIXME/XXX in .py files"
    fi
}

check_no_print_calls() {
    if hits=$(grep -rn "print(" --include="*.py" --exclude-dir=".venv" \
        --exclude-dir=".git" --exclude-dir="tests" . 2>/dev/null); then
        fail "no print calls in non-test .py files" "$hits"
    else
        pass "no print calls in non-test .py files"
    fi
}

check_no_bare_except() {
    if hits=$(grep -rn "^[[:space:]]*except:" --include="*.py" \
        --exclude-dir=".venv" --exclude-dir=".git" . 2>/dev/null); then
        fail "no bare except in .py files" "$hits"
    else
        pass "no bare except in .py files"
    fi
}

check_gitignore_entries
check_env_example_fields
check_no_key_leaks
check_no_todos
check_no_print_calls
check_no_bare_except

if [ "$FAILED" -eq 0 ]; then
    echo "All hygiene checks passed!"
    exit 0
else
    echo "Hygiene check FAILED."
    exit 1
fi
