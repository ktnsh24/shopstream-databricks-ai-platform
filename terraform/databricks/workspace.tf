resource "databricks_repo" "platform" {
  url    = "https://github.com/ktnsh24/shopstream-databricks-ai-platform"
  path   = "/Repos/helix/shopstream-databricks-ai-platform"
  branch = "main"
}
