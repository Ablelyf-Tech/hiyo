terraform {

  required_version = ">= 1.7.0"
  required_providers {

    google = {
      source = "hashicorp/google", version = "~> 6.0"
    }


  }


}

provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "image" {
  type        = string
  description = "Reviewed Artifact Registry container image, preferably pinned by digest"
}

variable "db_password" {
  type        = string
  sensitive   = true
  description = "Set through a secure Terraform input use encrypted remote state"
}

variable "billing_account" {
  type = string
}

variable "alert_project_number" {
  type        = string
  description = "Numeric project identifier for budget scoping"
}

variable "service_url" {
  type        = string
  default     = ""
  description = "Set to the deployed HTTPS service URI before enabling enrollment and maintenance"
}

variable "monthly_budget_usd" {
  type    = number
  default = 100
}

locals {
  services = toset(["run.googleapis.com", "sqladmin.googleapis.com", "secretmanager.googleapis.com", "artifactregistry.googleapis.com", "cloudscheduler.googleapis.com", "billingbudgets.googleapis.com", "identitytoolkit.googleapis.com"])
}

resource "google_project_service" "api" {
  for_each           = local.services
  service            = each.value
  disable_on_destroy = false
}

resource "google_service_account" "api" {
  account_id   = "hiyo-coordinator"
  display_name = "Hiyo Cloud coordination"
}

resource "google_service_account" "maintenance" {
  account_id   = "hiyo-maintenance"
  display_name = "Hiyo retention scheduler"
}

resource "google_project_iam_member" "sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_artifact_registry_repository" "images" {
  location      = var.region
  repository_id = "hiyo"
  format        = "DOCKER"
  depends_on    = [google_project_service.api]
}

resource "google_sql_database_instance" "db" {

  name                = "hiyo-production"
  database_version    = "POSTGRES_16"
  deletion_protection = true
  depends_on          = [google_project_service.api]
  settings {

    tier                  = "db-custom-4-15360"
    availability_type     = "REGIONAL"
    disk_type             = "PD_SSD"
    disk_size             = 50
    disk_autoresize       = true
    disk_autoresize_limit = 1500
    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7
    }

    ip_configuration {
      ipv4_enabled = true
      ssl_mode     = "ENCRYPTED_ONLY"
    }

    database_flags {
      name  = "max_connections"
      value = "200"
    }

    insights_config {
      query_insights_enabled  = true
      record_application_tags = true
    }


  }


}

resource "google_sql_database" "hiyo" {
  name     = "hiyo"
  instance = google_sql_database_instance.db.name
}

resource "google_sql_user" "app" {
  name     = "hiyo_app"
  instance = google_sql_database_instance.db.name
  password = var.db_password
}

resource "google_secret_manager_secret" "database_url" {

  secret_id = "hiyo-database-url"
  replication {
    auto {

    }

  }

  depends_on = [google_project_service.api]

}

# Add the URL as a Secret Manager version through the secure operator flow. No value is embedded here.
resource "google_secret_manager_secret_iam_member" "database_reader" {
  secret_id = google_secret_manager_secret.database_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_cloud_run_v2_service" "api" {

  name                = "hiyo-cloud"
  location            = var.region
  deletion_protection = true
  depends_on          = [google_project_service.api, google_project_iam_member.sql_client, google_secret_manager_secret_iam_member.database_reader]
  template {

    service_account                  = google_service_account.api.email
    max_instance_request_concurrency = 40
    timeout                          = "60s"
    scaling {
      min_instance_count = 0
      max_instance_count = 20
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.db.connection_name]
      }

    }

    containers {

      image = var.image
      resources {
        limits = {
          cpu = "1", memory = "1Gi"
        }

        cpu_idle = true
      }

      ports {
        container_port = 8080
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      env {
        name = "HIYO_DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }

        }

      }

      env {
        name  = "HIYO_FIREBASE_PROJECT"
        value = var.project_id
      }

      env {
        name  = "HIYO_SERVICE_URL"
        value = var.service_url
      }

      env {
        name  = "HIYO_MAINTENANCE_ACCOUNT"
        value = google_service_account.maintenance.email
      }

      env {
        name  = "HIYO_DASHBOARD_DIR"
        value = "/app/dashboard/dist"
      }

      startup_probe {
        http_get {
          path = "/api/health"
          port = 8080
        }

        initial_delay_seconds = 2
        period_seconds        = 5
        failure_threshold     = 10
      }


    }


  }


}

resource "google_cloud_run_v2_service_iam_member" "public_transport" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_scheduler_job" "retention" {

  name       = "hiyo-retention"
  region     = var.region
  schedule   = "17 * * * *"
  time_zone  = "Etc/UTC"
  depends_on = [google_project_service.api]
  http_target {

    uri         = "${google_cloud_run_v2_service.api.uri}/internal/retention"
    http_method = "POST"
    oidc_token {
      service_account_email = google_service_account.maintenance.email
      audience              = google_cloud_run_v2_service.api.uri
    }


  }


}

resource "google_billing_budget" "pilot" {

  billing_account = var.billing_account
  display_name    = "Hiyo pilot budget alerts"
  budget_filter {
    projects = ["projects/${var.alert_project_number}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.monthly_budget_usd)
    }

  }

  threshold_rules {
    threshold_percent = 0.5
  }

  threshold_rules {
    threshold_percent = 0.8
  }

  threshold_rules {
    threshold_percent = 1.0
  }


}

output "service_uri" {
  value = google_cloud_run_v2_service.api.uri
}

output "sql_connection" {
  value = google_sql_database_instance.db.connection_name
}

