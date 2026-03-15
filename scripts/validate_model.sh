#!/usr/bin/env bash
set -euo pipefail

api_url="${API_URL:-http://localhost:8000/generate}"
max_tokens="${MAX_TOKENS:-8}"
temperature="${TEMPERATURE:-0.1}"
top_p="${TOP_P:-0.95}"
stop_one="${STOP_ONE:-<|im_sep|>}"
stop_two="${STOP_TWO:-Response:}"

prompts=(
  "Is the sky blue when there are no clouds? Please answer yes or no only."
  "Is Paris the capital of France? Please answer yes or no only."
  "Does water freeze at 0 degrees Celsius at standard atmospheric pressure? Please answer yes or no only."
  "Is the Sun a planet? Please answer yes or no only."
  "Can humans naturally breathe underwater without equipment? Please answer yes or no only."
  "Is 2 greater than 10? Please answer yes or no only."
)

expected=(
  "yes"
  "yes"
  "yes"
  "no"
  "no"
  "no"
)

passed=0
failed=0

normalize_answer() {
  local text
  text="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  printf '%s' "$text" | grep -Eo '\b(yes|no)\b' | head -n 1 || true
}

uppercase_answer() {
  printf '%s' "$1" | tr '[:lower:]' '[:upper:]'
}

printf 'Running validation against %s\n\n' "$api_url"

for i in "${!prompts[@]}"; do
  prompt="${prompts[$i]}"
  expected_answer="${expected[$i]}"

  payload="$(jq -nc \
    --arg prompt "$prompt" \
    --arg stop_one "$stop_one" \
    --arg stop_two "$stop_two" \
    --argjson max_tokens "$max_tokens" \
    --argjson temperature "$temperature" \
    --argjson top_p "$top_p" \
    '{prompt: $prompt, max_tokens: $max_tokens, temperature: $temperature, top_p: $top_p, stop: [$stop_one, $stop_two]}')"

  if ! response="$(curl -sS "$api_url" -H 'Content-Type: application/json' -d "$payload")"; then
    failed=$((failed + 1))
    printf 'Case %d: FAIL\n' "$((i + 1))"
    printf '  Prompt: %s\n' "$prompt"
    printf '  Expected: %s\n' "$(uppercase_answer "$expected_answer")"
    printf '  Error: request failed\n\n'
    continue
  fi

  content="$(printf '%s' "$response" | jq -r '.content // empty' 2>/dev/null || true)"
  latency_ms="$(printf '%s' "$response" | jq -r '.latency_ms // empty' 2>/dev/null || true)"
  actual_answer="$(normalize_answer "$content")"

  if [[ "$actual_answer" == "$expected_answer" ]]; then
    passed=$((passed + 1))
    status="PASS"
  else
    failed=$((failed + 1))
    status="FAIL"
  fi

  printf 'Case %d: %s\n' "$((i + 1))" "$status"
  printf '  Prompt: %s\n' "$prompt"
  printf '  Expected: %s\n' "$(uppercase_answer "$expected_answer")"
  printf '  Response: %s\n' "${content:-<empty>}"
  printf '  Parsed: %s\n' "${actual_answer:-<unrecognized>}"
  if [[ -n "$latency_ms" ]]; then
    printf '  Latency: %s ms\n' "$latency_ms"
  fi
  printf '\n'
done

printf 'Validation summary\n'
printf '  Passed: %d\n' "$passed"
printf '  Failed: %d\n' "$failed"
printf '  Total: %d\n' "${#prompts[@]}"

if [[ "$failed" -gt 0 ]]; then
  exit 1
fi
