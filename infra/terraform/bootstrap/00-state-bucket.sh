#!/usr/bin/env bash
# Day 65 — bucket S3 chứa Terraform state (gà – trứng: backend phải có TRƯỚC khi `terraform init`).
# Chạy 1 lần, chạy lại không sao (mỗi lệnh đều idempotent).
#   - versioning: lỡ ghi hỏng state → lấy lại bản trước
#   - SSE-S3 + chặn public + chỉ cho HTTPS: state chứa ARN, id, cấu hình của mọi resource
#   - khoá state bằng file .tflock (use_lockfile, Terraform >= 1.10) → không cần bảng DynamoDB
set -euo pipefail
export AWS_PAGER=""

REGION="${AWS_REGION:-us-east-1}"
# Tên bucket toàn cầu, KHÔNG chứa account id (repo public). Khớp backend "s3" trong bootstrap/ và live/
BUCKET="support-agent-tfstate-thuan-20261118"

if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "Bucket $BUCKET đã có — chỉ đảm bảo cấu hình"
else
  # us-east-1 KHÔNG nhận LocationConstraint
  aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" >/dev/null
  echo "Đã tạo bucket $BUCKET"
fi

aws s3api put-bucket-versioning --bucket "$BUCKET" --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption --bucket "$BUCKET" --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"},"BucketKeyEnabled":true}]}'
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-ownership-controls --bucket "$BUCKET" \
  --ownership-controls 'Rules=[{ObjectOwnership=BucketOwnerEnforced}]'
aws s3api put-bucket-policy --bucket "$BUCKET" --policy "$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "DenyInsecureTransport",
    "Effect": "Deny",
    "Principal": "*",
    "Action": "s3:*",
    "Resource": ["arn:aws:s3:::$BUCKET", "arn:aws:s3:::$BUCKET/*"],
    "Condition": {"Bool": {"aws:SecureTransport": "false"}}
  }]
}
EOF
)"
aws s3api put-bucket-tagging --bucket "$BUCKET" --tagging 'TagSet=[{Key=project,Value=support-agent}]'
echo "✅ $BUCKET: versioning · SSE-S3 · chặn public · chỉ HTTPS"
