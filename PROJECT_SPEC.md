# NYC 311 ETL Pipeline to BigQuery: Lean Project Spec

Version 2.1 | Personal side project | Python transforms, deployed as a Cloud Run Job, BigQuery as the warehouse destination

## 1. Project Context

This is a small ETL pipeline built to practice ETL skills and get hands-on data warehouse exposure while spending close to $0 of the $300 GCP credits. Data is extracted from a public API, transformed in **Python (pandas)**, and loaded into **BigQuery**, which acts only as the storage and serving layer. The pipeline is developed locally, then packaged as a Docker image in **Artifact Registry** and run automatically on GCP as a **Cloud Run Job** triggered by **Cloud Scheduler**.

**Dataset:** NYC 311 Service Requests (NYC Open Data, Socrata SODA API). It is free, updates daily, and is messy enough (inconsistent categories, bad ZIPs, null coordinates, records that change status) to make the transformation work worthwhile. Any other public API can be swapped in; only the extract and clean steps change.

**Learning goals**

- Build an extract, transform, load flow with incremental extraction
- Practice cleaning, deduplication, and dimensional modeling in pandas
- Design a layered warehouse (raw, staging, marts) with partitioned and clustered tables in BigQuery
- Containerize the pipeline and run it unattended on a schedule in GCP
- Add data quality checks and unit tests

## 2. Design Principles

- **Serverless batch.** A Cloud Run Job runs to completion and exits; Cloud Scheduler triggers it daily. No always-on infrastructure, and no Composer, GKE, or VMs.
- **Transform in Python, load to BigQuery.** Transforms read raw files from storage, not from BigQuery, so they use no query quota.
- **One container, two environments.** The same image runs locally and in the cloud; a config setting switches the storage path between a local `data/` folder and a `gs://` bucket.
- **State lives outside the container.** Cloud Run's filesystem is temporary, so all raw files and state are kept in Cloud Storage and BigQuery.
- **Keep data small.** Load roughly the last 6 months (about 1 to 1.5M rows).
- **Use free operations.** BigQuery load jobs are free; storage is free up to 10 GB; queries are free up to 1 TB per month.
- **Full rebuild over clever incremental.** Only the extract is incremental; staging and marts are rebuilt each run.

## 3. Data Source

- **Endpoint:** `https://data.cityofnewyork.us/resource/erm2-nwe9.json` (verify the dataset ID on the portal)
- **Query params:** `$select`, `$where`, `$order`, `$limit`, `$offset`
- **Auth:** free app token in the `X-App-Token` header (optional, avoids throttling)
- **Columns to pull:** `unique_key`, `created_date`, `closed_date`, `agency`, `complaint_type`, `descriptor`, `borough`, `incident_zip`, `latitude`, `longitude`, `status`, `open_data_channel_type`
- **Quirks to handle:** placeholder boroughs, invalid ZIPs, null or zero coordinates, `closed_date` before `created_date`, inconsistent complaint text, status changes after first load

## 4. Architecture

```
Cloud Scheduler (daily)
        |
        v
Cloud Run Job  (image pulled from Artifact Registry)
        |
  extract.py --> gs://<bucket>/raw/<date>.parquet   (immutable)
        |                        |
        |               BigQuery load job --> raw_311.service_requests
        v
  transform.py (pandas, reads raw files from GCS)
  clean, dedupe, model
        |
  gs://<bucket>/staging/stg.parquet
        |
  BigQuery load jobs --> stg_311.service_requests
                         mart_311.dim_* + fact_service_request + agg_*
```

**Deployment flow:** `docker build` the image, push it to Artifact Registry, deploy or update the Cloud Run Job to use it, and let Cloud Scheduler trigger it.

## 5. Technology Stack

| Concern | Choice |
|---|---|
| Language | Python 3.11+ |
| Libraries | `requests`, `pandas`, `pyarrow`, `google-cloud-bigquery`, `google-cloud-storage`, `pytest` |
| Warehouse | BigQuery with 3 datasets: `raw_311`, `stg_311`, `mart_311` |
| File storage | Cloud Storage bucket (`raw/`, `staging/`); local `data/` folder during development |
| Packaging | Docker image on a slim Python base |
| Image registry | Artifact Registry (Docker repository) |
| Compute | Cloud Run Job |
| Scheduling | Cloud Scheduler (one daily job) |
| Auth | Dedicated service account attached to the job; no key file in the cloud |
| Secrets | Secret Manager, or an environment variable at first, for the Socrata app token |
| Logging | Structured JSON logs to stdout (Cloud Logging) |

## 6. Functional Requirements

**Extract**

- FR-1: Fetch records for a date range with paginated requests and a stable `$order`.
- FR-2: Incremental mode pulls from the latest stored `created_date` minus a 14-day lookback to catch status changes. The latest stored date is read from the files in the bucket.
- FR-3: Retry failed requests with exponential backoff.
- FR-4: Save each pull to a dated Parquet file in the bucket (local folder in development) that is never modified afterward.

**Load raw**

- FR-5: Load each raw file into `raw_311.service_requests` with a load job, adding `_ingested_at` and `_batch_id` columns.

**Transform (Python)**

- FR-6: Clean: cast types, trim and standardize text, set invalid ZIPs and out-of-range coordinates to null.
- FR-7: Deduplicate: combine all raw files and keep the latest version of each `unique_key`.
- FR-8: Derive `resolution_hours`, `is_closed`, `date_key`, and a `dq_flags` column. Flag bad rows; do not drop them.
- FR-9: Build dimensions `dim_date`, `dim_agency`, `dim_complaint_type`, and `dim_location` (borough, ZIP) with integer surrogate keys.
- FR-10: Build `fact_service_request` by joining staging to the dimensions.
- FR-11: Build one aggregate table: daily request counts by borough and complaint type.

**Load warehouse**

- FR-12: Load staging, dimensions, fact, and aggregate into BigQuery with `WRITE_TRUNCATE`. The fact table is partitioned by `created_at` date and clustered by `agency_key`.
- FR-13: Reruns must leave identical row counts, since the same raw files always produce the same tables.

**Deployment and automation**

- FR-14: Package the pipeline as one Docker image whose entrypoint runs the full flow (`cli.py all`).
- FR-15: Push the image to Artifact Registry in the same region as the job.
- FR-16: Run the Cloud Run Job under a dedicated service account with least-privilege roles (BigQuery Data Editor, BigQuery Job User, and object access on the bucket only).
- FR-17: Set a low max-retries count and a task timeout on the job so a stuck run cannot keep billing.
- FR-18: Trigger the job once a day with Cloud Scheduler at an off-peak time.
- FR-19: Exit with a non-zero code on any critical failure so Cloud Run marks the execution as failed, and write structured logs with a run ID.

## 7. Data Model

`fact_service_request` is partitioned by `DATE(created_at)` and clustered by `agency_key`.

| Column | Type |
|---|---|
| `request_id` | STRING |
| `created_at`, `closed_at` | TIMESTAMP |
| `date_key`, `agency_key`, `complaint_type_key`, `location_key` | INT64 |
| `status` | STRING |
| `resolution_hours` | FLOAT64 |
| `dq_flags` | STRING (comma-joined) |

Dimensions use integer surrogate keys. Because dimensions and fact are rebuilt together each run, keys stay consistent without extra bookkeeping.

## 8. Data Quality Checks

Checks run in pandas before the warehouse load. Critical failures stop the run before anything is loaded.

| Check | Severity |
|---|---|
| `unique_key` is unique in staging | Critical |
| `unique_key` and `created_date` are not null | Critical |
| Every fact foreign key exists in its dimension | Critical |
| `closed_date >= created_date` where both exist | Warning (flag row) |
| Latest `created_date` is within 2 days of today | Warning |
| BigQuery table row counts match the DataFrames after load | Critical |

## 9. Cost Guardrails

1. Create a **budget alert** at $10 and $25 in the GCP console before anything else.
2. Set `maximum_bytes_billed` (for example 1 GB) on every query job run from Python.
3. Partition the fact table and set `require_partition_filter = true`.
4. Never run `SELECT *` on wide tables; check the dry-run estimate first.
5. Put the bucket, Cloud Run Job, Artifact Registry repo, and BigQuery datasets in one region. Use a US region such as us-central1 so the bucket qualifies for the Cloud Storage free tier.
6. Keep the job small (1 vCPU, 1 GiB memory or less), with a timeout and 1 to 2 retries at most.
7. Keep the Docker image slim, and delete old image versions in Artifact Registry to stay near its free storage allowance.
8. Add a lifecycle rule on the bucket and drop test tables when done.
9. Read raw files from the bucket for transforms; do not pull large tables back out of BigQuery.

## 10. Repository Structure

```
nyc311-etl/
  README.md
  requirements.txt
  Dockerfile
  .dockerignore
  config.yaml          # project id, region, dataset names, bucket, lookback days
  etl/
    extract.py         # Socrata client, pagination, retries
    storage.py         # local folder or gs:// read/write helpers
    load.py            # BigQuery load helpers
    transform.py       # clean, dedupe, derive
    model.py           # build dims, fact, aggregate
    quality.py         # pandas data quality checks
    cli.py             # extract | load-raw | transform | load-dw | all
  deploy/
    deploy.sh          # build, push, deploy job, create scheduler trigger
  tests/
    test_transform.py
    test_model.py
    test_quality.py
    fixtures/          # small sample API payload
  data/                # gitignored: local raw/ and staging/ for development
```

## 11. Milestones

| # | Milestone | Done when |
|---|---|---|
| 1 | GCP setup | Project, budget alerts, service account, bucket, Artifact Registry repo, 3 datasets exist |
| 2 | Extract | One month of data saved from the API (local folder first) |
| 3 | Raw load | `raw_311` populated via load job |
| 4 | Transform | Cleaning, dedupe, dims, fact, aggregate built in pandas with unit tests |
| 5 | Warehouse load and checks | Tables loaded to BigQuery locally, checks pass |
| 6 | Containerize | Image builds, runs locally, and is pushed to Artifact Registry |
| 7 | Deploy | Cloud Run Job runs end to end when started manually, reading and writing the bucket |
| 8 | Automate | Cloud Scheduler triggers the job daily; README written |

## 12. Acceptance Criteria

1. 6 months of data are loaded into all three layers.
2. Rerunning the pipeline leaves BigQuery row counts unchanged.
3. All critical checks pass, and unit tests pass for the transform, model, and quality modules.
4. The scheduled Cloud Run Job runs unattended for 7 consecutive days with successful executions and no duplicate rows.
5. At least 3 analytical SQL queries run on the marts (top complaint types per borough, median resolution time by agency, weekly trend).
6. Total GCP spend stays under about $5.

## 13. Optional Later

- Alert on failed job executions with Cloud Monitoring
- Add CI/CD that builds and pushes the image on every merge (Cloud Build or GitHub Actions)
- Learn `MERGE` by loading changed rows to a temp table and upserting into staging
- Add a Looker Studio dashboard on the marts
- Add a second source (for example weather) and join it to 311 volume

## 14. Out of Scope

Streaming, orchestration platforms (Airflow, Composer), GKE or VM hosting, multi-environment setup, and slowly changing dimensions.