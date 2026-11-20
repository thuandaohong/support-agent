# ============================================================
# live/ — toàn bộ hạ tầng support-agent. CHỈ GitHub Actions apply (terraform.yml, sau Approve).
# Ở máy chỉ chạy `terraform plan` (đọc). Role pipeline do ../bootstrap quản.
# ============================================================
terraform {
  required_version = ">= 1.10" # use_lockfile; import {} với id là biểu thức cần >= 1.6

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.73" # >= 6.56 cho KB MANAGED; 6.73 có aws_bedrockagentcore_* (đã probe schema)
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.7" # zip code Lambda
    }
  }

  backend "s3" {
    bucket       = "support-agent-tfstate-thuan-20261118" # ../bootstrap/00-state-bucket.sh
    key          = "support-agent/live.tfstate"
    region       = "us-east-1"
    use_lockfile = true
    encrypt      = true
  }
}

provider "aws" {
  region = var.aws_region
  # Mọi resource hỗ trợ tag đều có tag này (giống tag các script cũ gắn) → lọc chi phí theo project
  default_tags {
    tags = { project = "support-agent" }
  }
}
