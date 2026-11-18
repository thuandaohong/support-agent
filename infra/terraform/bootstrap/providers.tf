# ============================================================
# bootstrap/ — 2 role cho pipeline Terraform của live/.
# Apply Ở MÁY đúng 1 lần (pipeline không tự tạo quyền cho chính nó); sửa sau này cũng ở máy, có review.
# State cùng bucket với live/ nhưng KEY khác → 2 root độc lập.
# ============================================================
terraform {
  required_version = ">= 1.10" # use_lockfile

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.73"
    }
  }

  backend "s3" {
    bucket       = "support-agent-tfstate-thuan-20261118" # tạo bởi 00-state-bucket.sh
    key          = "support-agent/bootstrap.tfstate"
    region       = "us-east-1"
    use_lockfile = true
    encrypt      = true
  }
}

provider "aws" {
  region = "us-east-1"
  default_tags {
    tags = { project = "support-agent", managed-by = "terraform-bootstrap" }
  }
}
