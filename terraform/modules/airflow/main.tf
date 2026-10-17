# Keep this module free of managed Airflow resources.
#
# Cloud Composer and any other hosted Airflow service incur significant cost.
# Do not add those resources here, do not call this module from
# terraform/envs/*, and do not apply it from .github/workflows/deploy.yml.
# scripts/no-managed-airflow.sh rejects Composer resources in *.tf files.
#
# Run Airflow locally when a scheduler is needed. Airflow uses a SQLite
# metadata database unless AIRFLOW__DATABASE__SQL_ALCHEMY_CONN is set.
# Local Airflow is not part of continuous deployment.
