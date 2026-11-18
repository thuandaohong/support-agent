# OIDC provider của GitHub ĐÃ CÓ trong account (Project 1 rag-chatbot tạo). Mỗi account chỉ được 1
# provider cho mỗi URL → ở đây chỉ ĐỌC, không tạo/sở hữu. Xoá Project 1 thì phải chuyển provider sang đây.
data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

data "aws_caller_identity" "current" {}

locals {
  account_id   = data.aws_caller_identity.current.account_id
  github_owner = split("/", var.github_repo)[0]
  github_name  = split("/", var.github_repo)[1]

  # Phần đầu claim `sub`, 2 định dạng:
  #  - có ID bất biến: repo:owner@ownerId/repo@repoId — repo bị xoá rồi người khác tạo lại cùng tên KHÔNG khớp
  #  - chỉ tên:        repo:owner/repo
  github_sub_prefixes = [
    "repo:${local.github_owner}@${var.github_owner_id}/${local.github_name}@${var.github_repo_id}",
    "repo:${var.github_repo}",
  ]
}
