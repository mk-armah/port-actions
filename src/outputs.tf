output "instance_state" {
  description = "The state of the EC2 instance."
  value       = aws_instance.app_server.instance_state
}

output "instance_public_ip" {
  description = "The public IP address of the EC2 instance."
  value       = aws_instance.app_server.public_ip
}

output "instance_private_ip" {
  description = "The private IP address of the EC2 instance."
  value       = aws_instance.app_server.private_ip
}

output "subnet_id" {
  description = "The ID of the subnet to which the instance is attached."
  value       = aws_instance.app_server.subnet_id
}

output "tags" {
  description = "A map of tags assigned to the resource."
  value       = aws_instance.app_server.tags
}

output "security_groups" {
  description = "The names of the security groups for the instance."
  value       = [for sg in aws_instance.app_server.security_groups : sg]
}

output "instance_id" {
  description = "The ID of the EC2 instance."
  value       = aws_instance.app_server.id
}
