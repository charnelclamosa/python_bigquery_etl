# NYC 311 to BigQuery: Lean Requirements (Python Transforms, Cloud Run Job)

A small ETL side project. Main goal: **hands-on data warehouse exposure** (layered tables, partitioning, clustering, dimensional modeling) while spending close to $0 of the $300 GCP credits. Transformations are written in **Python (pandas)**; BigQuery is the storage and serving layer. The pipeline is containerized, stored in Artifact Registry, and runs daily as a **Cloud Run Job** triggered by **Cloud Scheduler**.

## 1. Design Principles

- **Serverless batch.** A Cloud Run Job runs to completion and exits; Cloud Scheduler triggers it daily. No always-on infrastructure, and no Composer, GKE, or VMs.
- **Transform in Python, load to BigQuery.** Transforms read raw files from storage, not from BigQuery, so they use no query quota.
- **One container, two environments.** The same image runs locally and in the cloud; a config setting switches storage between a local `data/` folder and a `gs://` bucket.
- **State lives outside the container.** Cloud Run's filesystem is temporary, so raw files and state are kept in Cloud Storage and BigQuery.
- **Keep data small.** Load roughly the last 6 months (about 1 to 1.5M rows).
- **Use free operations.** Load jobs are free; BigQuery storage is free up to 10 GB; queries are free up to 1 TB/month.
- **Full rebuild over clever incremental.** Only the extract is incremental.

## 2. Source

- **Dataset:** NYC 311 Service Requests (NYC Open Data, Socrata SODA API)
- **Endpoint:** `https://data.cityofnewyork.us/resource/erm2-nwe9.json` (verify the dataset ID on the portal)
- **Query params:** `$select`, `$where`, `$order`, `$limit`, `$offset`
- **Auth:** free app token in the `X-App-Token` header (optional but avoids throttling)
- **Columns to pull (keep it narrow):** `unique_key`, `created_date`, `closed_date`, `agency`, `complaint_type`, `descriptor`, `borough`, `incident_zip`, `latitude`, `longitude`, `status`, `open_data_channel_type`

## 3. Architecture

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
        |
  gs://<bucket>/staging/stg.parquet
        |
  BigQuery load jobs --> stg_311.service_requests
                         mart_311.dim_* + fact_service_request + agg_*
```

Deployment flow: build the Docker image, push it to Artifact Registry, deploy or update the Cloud Run Job, and let Cloud Scheduler trigger it.

## 4. Tech Stack

| Concern | Choice |
|---|---|
| Language | Python 3.11+ |
| Libraries | `requests`, `pandas`, `pyarrow`, `google-cloud-bigquery`, `google-cloud-storage`, `pytest` |
| Warehouse | BigQuery (3 datasets: `raw_311`, `stg_311`, `mart_311`) |
| File storage | Cloud Storage bucket (`raw/`, `staging/`); local `data/` folder in development |
| Packaging | Docker image on a slim Python base |
| Image registry | Artifact Registry |
| Compute | Cloud Run Job |
| Scheduling | Cloud Scheduler (one daily job) |
| Auth | Dedicated service account attached to the job; no key file in the cloud |
| Secrets | Secret Manager, or an environment variable at first, for the Socrata token |
| Logging | Structured JSON logs to stdout (Cloud Logging) |

## 5. Functional Requirements

**Extract**
- FR-1: Fetch records for a date range using paginated requests with a stable `$order`.
- FR-2: Incremental mode: pull from the latest stored `created_date` (read from the files in the bucket) minus a 14-day lookback (catches status changes).
- FR-3: Retry failed requests with simple exponential backoff.
- FR-4: Save each pull to a dated Parquet file in the bucket (local folder in development), for example `raw/2026-10-29.parquet`, never modified afterward.

**Load raw**
- FR-5: Load each raw file into `raw_311.service_requests` with a load job; add `_ingested_at` and `_batch_id` columns.

**Transform (Python)**
- FR-6: **Clean:** cast types (timestamps, floats), trim and standardize text (borough, complaint type, agency), set invalid ZIPs and out-of-range coordinates to null.
- FR-7: **Deduplicate:** combine all raw files and keep the latest version of each `unique_key` (by file/ingest time). Write the result to `data/staging/`.
- FR-8: **Derive:** `resolution_hours`, `is_closed`, `date_key`, and a `dq_flags` column listing issues found (flag, do not drop).
- FR-9: **Dimensions:** build `dim_date`, `dim_agency`, `dim_complaint_type`, `dim_location` (borough, ZIP) as DataFrames with integer surrogate keys.
- FR-10: **Fact:** build `fact_service_request` by joining staging to the dimensions.
- FR-11: **Aggregate:** build one table, daily request counts by borough and complaint type.

**Load warehouse**
- FR-12: Load staging, dimensions, fact, and aggregate into BigQuery with `WRITE_TRUNCATE` (full replace). Fact table is partitioned by `created_at` date and clustered by `agency_key`.
- FR-13: Reruns must leave identical row counts (idempotent by construction: same raw files in, same tables out).

**Deployment and automation**
- FR-14: Package the pipeline as one Docker image whose entrypoint runs the full flow (`cli.py all`).
- FR-15: Push the image to Artifact Registry in the same region as the job.
- FR-16: Run the Cloud Run Job under a dedicated service account with least-privilege roles (BigQuery Data Editor, BigQuery Job User, object access on the bucket only).
- FR-17: Set a low max-retries count and a task timeout so a stuck run cannot keep billing.
- FR-18: Trigger the job once a day with Cloud Scheduler at an off-peak time.
- FR-19: Exit non-zero on any critical failure so Cloud Run marks the execution as failed; write structured logs with a run ID.

**Quality (pandas checks run before the warehouse load)**
- `unique_key` is unique in staging
- `unique_key` and `created_date` are not null
- Every fact foreign key exists in its dimension
- `closed_date >= created_date` where both exist (warn and flag only)
- Latest `created_date` is within 2 days of today (warn only)
- After load: row counts in BigQuery match the DataFrames (one cheap `COUNT(*)` per table, or read `table.num_rows` from metadata at zero cost)

Critical failures stop the run before anything is loaded.

## 6. Data Model

**`fact_service_request`**: partitioned by `DATE(created_at)`, clustered by `agency_key`.

| Column | Type |
|---|---|
| `request_id` | STRING |
| `created_at`, `closed_at` | TIMESTAMP |
| `date_key`, `agency_key`, `complaint_type_key`, `location_key` | INT64 |
| `status` | STRING |
| `resolution_hours` | FLOAT64 |
| `dq_flags` | ARRAY<STRING> (or comma-joined STRING) |

Dimensions use integer surrogate keys. Because dims and fact are rebuilt together every run, keys stay consistent without extra bookkeeping.

## 7. Cost Guardrails (do these first)

1. Create a **budget alert** at $10 and $25 in the GCP console.
2. Set `maximum_bytes_billed` (for example 1 GB) on every query job you run from Python.
3. Partition the fact table and set `require_partition_filter = true`.
4. Never run `SELECT *` on wide tables; check the dry-run estimate before new analytical queries.
5. Put the bucket, Cloud Run Job, Artifact Registry repo, and BigQuery datasets in one region. Use a US region such as us-central1 so the bucket qualifies for the Cloud Storage free tier.
6. Keep the job small (1 vCPU, 1 GiB memory or less), with a timeout and 1 to 2 retries at most.
7. Keep the Docker image slim and delete old image versions in Artifact Registry.
8. Add a lifecycle rule on the bucket and drop test tables when done.
9. Read raw files from the bucket for transforms; do not pull large tables back out of BigQuery.

## 8. Repo Structure

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

## 9. Milestones

| # | Milestone | Done when |
|---|---|---|
| 1 | GCP setup | Project, budget alerts, service account, bucket, Artifact Registry repo, 3 datasets exist |
| 2 | Extract | One month of data saved from the API (local folder first) |
| 3 | Raw load | `raw_311` populated via load job |
| 4 | Transform | Cleaning, dedupe, dims, fact, aggregate built in pandas with unit tests |
| 5 | Warehouse load + checks | Tables loaded to BigQuery locally, checks pass |
| 6 | Containerize | Image builds, runs locally, and is pushed to Artifact Registry |
| 7 | Deploy | Cloud Run Job runs end to end when started manually, reading and writing the bucket |
| 8 | Automate | Cloud Scheduler triggers the job daily; README written |

## 10. Acceptance Criteria

- 6 months of data loaded into all three layers
- Rerunning the pipeline leaves BigQuery row counts unchanged
- All critical checks pass; unit tests pass for transform, model, and quality modules
- The scheduled Cloud Run Job runs unattended for 7 consecutive days with successful executions and no duplicate rows
- At least 3 analytical SQL queries run on the marts (top complaint types per borough, median resolution time by agency, weekly trend)
- Total GCP spend stays under about $5

## 11. Optional Later

- Alert on failed job executions with Cloud Monitoring
- Add CI/CD that builds and pushes the image on every merge (Cloud Build or GitHub Actions)
- Learn `MERGE`: load changed rows to a temp table and upsert into staging instead of full replace
- Add a Looker Studio dashboard on the marts
- Add a second source (for example weather) and join it to 311 volume

## 12. Out of Scope

Streaming, orchestration platforms (Airflow/Composer), GKE or VM hosting, multi-environment setup, slowly changing dimensions.