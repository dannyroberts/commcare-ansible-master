// DO NOT EDIT THIS FILE
// This file is autogenerated, terraform 0.12
// which will introduce "count" on module calls

locals {
  rds_instances = [
    "${merge(local.default_rds, var.rds_instances[0 < length(var.rds_instances) ? 0 : 0])}",
    "${merge(local.default_rds, var.rds_instances[1 < length(var.rds_instances) ? 1 : 0])}",
    "${merge(local.default_rds, var.rds_instances[2 < length(var.rds_instances) ? 2 : 0])}",
    "${merge(local.default_rds, var.rds_instances[3 < length(var.rds_instances) ? 3 : 0])}",
    "${merge(local.default_rds, var.rds_instances[4 < length(var.rds_instances) ? 4 : 0])}",
  ]
}


module "postgresql-0" {
  source = "../postgresql"
  rds_instance = "${local.rds_instances[0]}"
  subnet_ids = "${local.rds_subnet_ids}"
  vpc_security_group_ids = "${local.rds_vpc_security_group_ids}"
  create = "${ 0 < length(var.rds_instances) ? 1 : 0 }"
}
module "postgresql-1" {
  source = "../postgresql"
  rds_instance = "${local.rds_instances[1]}"
  subnet_ids = "${local.rds_subnet_ids}"
  vpc_security_group_ids = "${local.rds_vpc_security_group_ids}"
  create = "${ 1 < length(var.rds_instances) ? 1 : 0 }"
}
module "postgresql-2" {
  source = "../postgresql"
  rds_instance = "${local.rds_instances[2]}"
  subnet_ids = "${local.rds_subnet_ids}"
  vpc_security_group_ids = "${local.rds_vpc_security_group_ids}"
  create = "${ 2 < length(var.rds_instances) ? 1 : 0 }"
}
module "postgresql-3" {
  source = "../postgresql"
  rds_instance = "${local.rds_instances[3]}"
  subnet_ids = "${local.rds_subnet_ids}"
  vpc_security_group_ids = "${local.rds_vpc_security_group_ids}"
  create = "${ 3 < length(var.rds_instances) ? 1 : 0 }"
}
module "postgresql-4" {
  source = "../postgresql"
  rds_instance = "${local.rds_instances[4]}"
  subnet_ids = "${local.rds_subnet_ids}"
  vpc_security_group_ids = "${local.rds_vpc_security_group_ids}"
  create = "${ 4 < length(var.rds_instances) ? 1 : 0 }"
}
