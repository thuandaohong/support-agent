# ============================================================
# module data — 3 kho có DỮ LIỆU: bảng đơn (Day 53), bucket chính sách (Day 51), repo image (Day 58).
# prevent_destroy: plan nào định xoá / tạo lại chúng sẽ LỖI ngay, kể cả khi ai đó lỡ xoá code.
# Nội dung (50 đơn, 5 file, image) KHÔNG do Terraform quản — xem infra/terraform/README.md.
# ============================================================

# ---------- DynamoDB: 50 đơn mẫu (scripts/load_orders.py) ----------
resource "aws_dynamodb_table" "orders" {
  name         = var.orders_table
  billing_mode = "PAY_PER_REQUEST" # trả theo request, không phải đặt trước capacity
  hash_key     = "order_id"

  attribute {
    name = "order_id"
    type = "S"
  }

  lifecycle {
    prevent_destroy = true
  }
}

# ---------- S3: 5 file chính sách — nguồn của Knowledge Base ----------
resource "aws_s3_bucket" "policies" {
  bucket = var.policies_bucket

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_public_access_block" "policies" {
  bucket                  = aws_s3_bucket.policies.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ---------- ECR: image agent, tag = git SHA, không ghi đè ----------
resource "aws_ecr_repository" "agent" {
  name                 = var.ecr_repo
  image_tag_mutability = "IMMUTABLE" # tag đã push không đổi nội dung được → Runtime chạy đúng image đã duyệt

  image_scanning_configuration {
    scan_on_push = true
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_ecr_lifecycle_policy" "agent" {
  repository = aws_ecr_repository.agent.name
  # Mô tả giữ không dấu như lúc tạo (Day 58) — đổi chữ là plan hiện thay đổi
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Xoa image khong tag sau 1 ngay"
        selection    = { tagStatus = "untagged", countType = "sinceImagePushed", countUnit = "days", countNumber = 1 }
        action       = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Chi giu 10 image gan nhat"
        selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 10 }
        action       = { type = "expire" }
      },
    ]
  })
}
