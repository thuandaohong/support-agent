#!/usr/bin/env bash
# Bước 2 (Day 61, kiểm): gọi thẳng Lambda search_policy, giả lập context Gateway gửi.
#   ./06-test-policy-lambda.sh "Gói Premium đổi trả bao nhiêu ngày?"
# Không có đối số: chạy 3 ca chuẩn. In TÊN FILE nguồn + điểm + độ dài đoạn (không in nguyên văn).
source "$(dirname "$0")/_env.sh"

CLIENT_CONTEXT="$(lambda_tool_context "${POLICY_TARGET_NAME}___search_policy")"

call() {
  local payload
  payload="$(Q="$1" python3 -c 'import json,os;print(json.dumps({"query":os.environ["Q"]},ensure_ascii=False))')"
  aws lambda invoke --function-name "$POLICY_LAMBDA_NAME" --client-context "$CLIENT_CONTEXT" \
    --payload "$payload" --cli-binary-format raw-in-base64-out \
    --query FunctionError --output text "$TMP_DIR/out.json" > "$TMP_DIR/err.txt"
  [[ "$(cat "$TMP_DIR/err.txt")" == "None" ]] || echo "  (FunctionError: $(cat "$TMP_DIR/err.txt"))" >&2
  printf '"%s" → ' "$1"
  python3 - "$TMP_DIR/out.json" <<'PY'
import json, os, sys
out = json.load(open(sys.argv[1]))
size = os.path.getsize(sys.argv[1])
if "hits" in out:
    hits = ", ".join(f"{h['source'].rsplit('/', 1)[-1]} ({h['score']:.2f}, {len(h['text'])} ký tự)" for h in out["hits"])
    print(f"{len(out['hits'])} đoạn, {size} byte: {hits}")
else:
    print(out)
PY
}

if [[ $# -ge 1 ]]; then
  call "$1"
else
  call "Gói Premium được đổi trả trong bao nhiêu ngày?"   # phải có 01-return-policy.md đứng đầu
  call "Thủ đô của Pháp là gì?"                           # lạc đề: vẫn có đoạn nhưng điểm thấp
  call "   "                                              # rỗng → invalid_input, KB không bị gọi
fi
