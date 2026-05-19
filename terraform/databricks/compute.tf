resource "databricks_sql_endpoint" "main" {
  name             = "helix-sql-warehouse"
  cluster_size     = "2X-Small"
  max_num_clusters = 1
  auto_stop_mins   = 10
  warehouse_type   = "PRO"
  enable_serverless_compute = true

  tags {
    custom_tags {
      key   = "project"
      value = "helix"
    }
  }
}