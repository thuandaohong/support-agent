# ============================================================
# Day 65 — nhận resource ĐANG CHẠY (tạo bằng CLI/console các ngày trước) vào state, KHÔNG tạo lại.
# Import chỉ thành thật khi CI apply (sau Approve). Id ngẫu nhiên lấy từ var.import_ids (import-ids.sh).
# XOÁ file này (và import-ids.sh, var.import_ids) sau khi apply xong và plan = No changes.
# ============================================================

# ---------- module.data ----------
import {
  to = module.data.aws_dynamodb_table.orders
  id = var.orders_table
}

import {
  to = module.data.aws_s3_bucket.policies
  id = local.policies_bucket
}

import {
  to = module.data.aws_s3_bucket_public_access_block.policies
  id = local.policies_bucket
}

import {
  to = module.data.aws_ecr_repository.agent
  id = var.ecr_repo
}

import {
  to = module.data.aws_ecr_lifecycle_policy.agent
  id = var.ecr_repo
}
