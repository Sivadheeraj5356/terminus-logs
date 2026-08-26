resource "aws_security_group" "prod_bastion" {
  name        = "prod-bastion"
  description = "Production perimeter access"

  ingress {
    description = "temporary breakglass ssh"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "public customer https"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description      = "postgres maintenance over ipv6"
    from_port        = 5432
    to_port          = 5432
    protocol         = "tcp"
    cidr_ipv6_blocks = ["::/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["10.20.0.0/16"]
  }
}
