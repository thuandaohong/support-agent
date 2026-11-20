data "aws_caller_identity" "current" {}

locals {
  # Account id tra lúc chạy — không bao giờ viết literal vào repo public
  account_id = data.aws_caller_identity.current.account_id
  region     = var.aws_region

  # Bucket chính sách (Day 51) có account id trong tên → ghép ở đây thay vì ghi vào tfvars
  policies_bucket = "${var.policies_bucket_prefix}-${local.account_id}"
}
