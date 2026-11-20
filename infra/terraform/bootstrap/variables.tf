variable "project" {
  description = "Tiền tố tên role của pipeline"
  type        = string
  default     = "support-agent"
}

variable "github_repo" {
  description = "owner/repo trên GitHub"
  type        = string
}

variable "github_owner_id" {
  description = "ID số (bất biến) của owner — api.github.com/repos/<owner>/<repo> → owner.id"
  type        = string
}

variable "github_repo_id" {
  description = "ID số (bất biến) của repo — api.github.com/repos/<owner>/<repo> → id"
  type        = string
}

variable "state_bucket" {
  description = "Bucket state (khớp backend của live/)"
  type        = string
  default     = "support-agent-tfstate-thuan-20261118"
}

variable "live_state_key" {
  description = "Key state của live/ — role plan chỉ được ghi file khoá của đúng key này"
  type        = string
  default     = "support-agent/live.tfstate"
}

variable "kb_role_suffix" {
  description = "Hậu tố ngẫu nhiên console gán cho role + policy của KB support-policy-kb (Day 51)"
  type        = string
  default     = "1uz0d"
}
