output "aws_region" {
  description = "AWS region of the cluster."
  value       = var.aws_region
}

output "cluster_certificate_authority_data" {
  description = "Base64 encoded cluster CA."
  value       = module.eks.cluster_certificate_authority_data
  sensitive   = true
}

output "cluster_endpoint" {
  description = "EKS API endpoint."
  value       = module.eks.cluster_endpoint
}

output "cluster_name" {
  description = "EKS cluster name."
  value       = module.eks.cluster_name
}

output "cluster_security_group_id" {
  description = "Primary EKS security group id."
  value       = module.eks.cluster_primary_security_group_id
}

output "cloudtrail_bucket_name" {
  description = "S3 bucket receiving CloudTrail management events."
  value       = aws_s3_bucket.cloudtrail.id
}

output "mcp_image_repository" {
  description = "ECR repository URI used by the GitOps Bridge chart."
  value       = aws_ecr_repository.mcp_server.repository_url
}

output "router_security_group_id" {
  description = "Security group assigned to the sandbox router pods."
  value       = aws_security_group.router.id
}

output "sandbox_role_arn" {
  description = "IRSA role for the demo sandbox service account."
  value       = aws_iam_role.sandbox.arn
}

output "sandbox_security_group_id" {
  description = "Security group assigned to sandbox pods."
  value       = aws_security_group.sandbox.id
}

output "vpc_id" {
  description = "VPC identifier."
  value       = module.vpc.vpc_id
}
