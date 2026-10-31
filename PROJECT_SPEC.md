from pathlib import Path
import pypandoc

markdown = r"""# NYC 311 ETL Pipeline to BigQuery — Project Specification

> **Status:** Work in progress  
> **Purpose:** Personal portfolio project for practicing Python-based ETL, dimensional modeling, and loading data into Google BigQuery.

## 1. Project Overview

This project builds a batch ETL pipeline using the NYC 311 Service Requests dataset from NYC Open Data.

The pipeline will:

1. **Extract** service-request records from the Socrata API using Python and `sodapy`.
2. **Transform** the extracted records using Python and Pandas.
3. **Load** the transformed data into Google BigQuery for analytical querying.

Parquet will be used as the intermediate file format. Google Cloud Storage (GCS) will provide cloud-based file staging.

The project is being developed locally first, then will be containerized with Docker and deployed as a Google Cloud Run Job triggered by Cloud Scheduler.

## 2. Learning Objectives

- Build a paginated, incremental data extraction process.
- Implement data cleaning, validation, deduplication, and transformation with Pandas.
- Design and populate a dimensional model using a star schema.
- Write transformed data to Parquet.
- Stage files in Google Cloud Storage and load them into BigQuery.
- Containerize the pipeline and run it as a scheduled batch job.
- Add logging, retry handling, data quality checks, and tests.

## 3. Data Source

| Item | Details |
|---|---|
| Dataset | NYC 311 Service Requests |
| Provider | NYC Open Data / Socrata |
| Dataset ID | `erm2-nwe9` |
| SODA 2 endpoint | `https://data.cityofnewyork.us/resource/erm2-nwe9.json` |
| Python client | `sodapy.Socrata` |
| Authentication | Socrata app token; credentials supplied through environment variables |

The extraction implementation currently uses the Socrata SODA 2 interface through `sodapy`. It uses `select`, `where`, `order`, `limit`, and `offset` parameters.

### Source fields

The extraction currently requests fields needed for the fact table and dimensions:

| Source field | Intended use |
|---|---|
| `unique_key` | Source-system complaint identifier |
| `agency`, `agency_name` | `dim_agency` |
| `complaint_type`, `descriptor` | `dim_complaint_type` |
| `incident_zip`, `incident_address`, `street_name`, `address_type`, `landmark`, `city`, `police_precinct`, `borough`, `latitude`, `longitude` | `dim_location` |
| `status` | `dim_status` |
| `resolution_description` | `dim_resolution` |
| `created_date` | Complaint creation timestamp and creation-date dimension reference |
| `resolution_action_updated_date` | Resolution/action timestamp and resolution-date dimension reference |

**Scope decision:** Facility attributes (`facility_type`, `park_facility_name`, and `park_borough`) are excluded from the current dimensional model because they are frequently null or not applicable. They should also be removed from the extraction column list unless the project scope changes.

`resolution_action_updated_date` represents the date/time of the latest resolution-related action update. It should not automatically be interpreted as a definitive closure timestamp. The project will retain this source meaning in its documentation and analysis.

## 4. Architecture

### Planned end-to-end flow

```text
                 NYC 311 Socrata API
                          |
                          v
                 Extract (sodapy)
                          |
                          v
               Raw records / Pandas
                          |
                          v
             Transform and validate
                       (Pandas)
                          |
                          v
                    Parquet files
                          |
                          v
               Google Cloud Storage
                          |
                          v
                BigQuery load jobs
                          |
                          v
              BigQuery warehouse tables
                 (star schema)
```

### Planned GCP execution flow

```text
Cloud Scheduler
      |
      v
Cloud Run Job
      |
      v
Docker image from Artifact Registry
      |
      v
Run the Python ETL pipeline
      |
      +--> Socrata API
      |
      +--> Google Cloud Storage
      |
      +--> BigQuery
```

BigQuery is the warehouse and analytical serving layer. Data cleaning and dimensional transformations are performed in Python/Pandas rather than relying on BigQuery SQL for the primary transformation process.

## 5. Technology Stack

| Area | Technology |
|---|---|
| Language | Python |
| API client | `sodapy` |
| Data processing | Pandas |
| Intermediate format | Parquet / PyArrow |
| HTTP retry support | `requests`, `urllib3` |
| Local API / development interface | FastAPI |
| Containerization | Docker |
| Cloud file storage | Google Cloud Storage |
| Data warehouse | Google BigQuery |
| Container registry | Artifact Registry |
| Batch execution | Cloud Run Jobs |
| Scheduling | Cloud Scheduler |
| Logging | Python `logging`, Cloud Logging |
| Testing | pytest (planned) |

## 6. Extraction Design

### Current implementation

The extraction module is `src/extract.py`.

It currently includes:

- A `sodapy.Socrata` client configured with credentials from environment variables.
- HTTP request retries for selected transient HTTP errors, with a maximum of five retries and exponential backoff.
- A request timeout of 30 seconds.
- A configurable page size, currently set to 10,000 records.
- A date-window query using `created_date >= start AND created_date < end`.
- Deterministic ordering by `created_date ASC, unique_key ASC`.
- Offset-based pagination.
- Duplicate removal using `unique_key`.
- Conversion of extracted rows to records with missing values represented as `None`.
- A watermark returned by the extraction function for the caller to persist after a successful load.

### Incremental extraction

The extraction window is defined as:

- `start`: inclusive lower bound, defaulting to the saved watermark.
- `end`: exclusive upper bound, defaulting to the current timestamp.

The extraction function returns both the extracted records and the proposed new watermark. The watermark must only be committed after the corresponding data has been successfully written to durable storage and loaded as required by the pipeline.

The current approach uses `created_date` as the extraction watermark. This captures newly created complaints, but it does not by itself detect changes to older complaints. A future enhancement may use a lookback window and deduplication/upsert logic to re-fetch recent records. The limitations of `created_date` as a change-tracking field should be documented.

### Pagination

The implementation uses SODA 2 offset pagination:

- `limit`: maximum number of records per request.
- `offset`: number of records to skip.

Pages are ordered by `created_date` and `unique_key` to provide deterministic ordering. The extraction loop stops when a page contains fewer records than the configured page size.

The current implementation collects all pages into memory before returning the result. If the extraction volume becomes too large, consider processing and writing each page as a separate Parquet batch rather than accumulating the entire extraction window in memory.

### Current extraction progress

| Capability | Status |
|---|---|
| Socrata client initialization | Implemented |
| Environment-based credentials | Implemented |
| Retry configuration and request timeout | Implemented |
| Date-window filtering | Implemented |
| Ordered, offset-based pagination | Implemented |
| Duplicate removal by `unique_key` | Implemented |
| Missing-value conversion | Implemented through utility function |
| Watermark retrieval and return | Implemented through utility functions |
| Durable raw Parquet output | Planned |
| GCS upload | Planned |
| BigQuery loading | Planned |

## 7. Dimensional Data Model

The warehouse will use a **star schema** with one fact table and the following dimensions:

- `dim_agency`
- `dim_complaint_type`
- `dim_location`
- `dim_status`
- `dim_resolution`
- `dim_date`

`dim_facility` is intentionally excluded from the current model.

### Fact table: `fact_complaints`

**Grain:** One row per unique NYC 311 complaint.

| Column | Description |
|---|---|
| `complaint_key` | Warehouse-generated surrogate primary key |
| `complaint_id` | Source `unique_key`; natural/business identifier |
| `agency_key` | FK to `dim_agency` |
| `complaint_type_key` | FK to `dim_complaint_type` |
| `location_key` | FK to `dim_location` |
| `status_key` | FK to `dim_status` |
| `resolution_key` | FK to `dim_resolution` |
| `date_key` | FK to `dim_date` for the complaint creation date |
| `resolution_date_key` | FK to `dim_date` for the resolution/action update date |
| `created_date` | Original source creation timestamp |
| `resolution_action_updated_date` | Original source resolution/action update timestamp |
| `complaint_count` | Additive measure, set to `1` for each complaint |

The two date foreign keys reference the same `dim_date` table in different roles: creation date and resolution/action update date.

### Dimension tables

#### `dim_agency`

| Column | Description |
|---|---|
| `agency_key` | Surrogate primary key |
| `agency_id` | Source agency identifier (`agency`) |
| `agency_name` | Agency name |

#### `dim_complaint_type`

| Column | Description |
|---|---|
| `complaint_type_key` | Surrogate primary key |
| `complaint_type` | Complaint category |
| `descriptor` | More specific complaint description |

#### `dim_location`

| Column | Description |
|---|---|
| `location_key` | Surrogate primary key |
| `incident_zip` | Incident ZIP code |
| `incident_address` | Incident address |
| `street_name` | Street name |
| `address_type` | Address type |
| `landmark` | Nearby landmark |
| `city` | City |
| `police_precinct` | Police precinct |
| `borough` | NYC borough |
| `latitude` | Latitude |
| `longitude` | Longitude |

#### `dim_status`

| Column | Description |
|---|---|
| `status_key` | Surrogate primary key |
| `status` | Current complaint status in the source record |

#### `dim_resolution`

| Column | Description |
|---|---|
| `resolution_key` | Surrogate primary key |
| `resolution_description` | Source resolution/action description |

The resolution description may contain verbose or high-cardinality text. During transformation, assess its distinct-value count and consistency. If it does not form a useful reusable dimension, consider retaining it as a descriptive fact attribute or grouping it into meaningful categories.

#### `dim_date`

| Column | Description |
|---|---|
| `date_key` | Date key, preferably integer `YYYYMMDD` |
| `full_date` | Calendar date |
| `day` | Day of month |
| `month` | Month number |
| `month_name` | Month name |
| `quarter` | Calendar quarter |
| `year` | Calendar year |
| `day_of_week` | Day of week |

The date dimension contains calendar attributes, not hour/minute-level rows. Original source timestamps remain in the fact table so time-of-day analysis remains possible.

### Modeling notes

- Dimension keys are warehouse-generated surrogate keys.
- `complaint_id` preserves the source `unique_key` and identifies the complaint across pipeline runs.
- `complaint_count` is a derived measure equal to `1` per fact row.
- The current fact design represents the complaint's latest available state, not a full history of every status change.
- If status history becomes a requirement, add a separate status-event or periodic-snapshot fact rather than treating the current fact as historical status tracking.
- Since the current design rebuilds dimensions and facts together, surrogate keys can be regenerated consistently within each full rebuild. If incremental dimension maintenance is introduced, key persistence and change handling must be designed explicitly.

## 8. Transformation Requirements

Transformations will be implemented in Python/Pandas.

Planned processing includes:

1. Normalize column names and text values.
2. Convert source fields to appropriate data types.
3. Handle missing values consistently.
4. Validate ZIP codes and geographic coordinates.
5. Deduplicate records using `unique_key`.
6. Parse source timestamps and derive calendar dates.
7. Build unique dimension datasets.
8. Generate surrogate keys for dimensions.
9. Map dimension keys back to complaint records.
10. Build the fact table at one row per complaint.
11. Run data quality checks before loading.

The original timestamp values should be retained in the fact table even when date keys are derived for dimensional analysis.

## 9. Loading Design

The planned load flow is:

1. Write extracted or transformed batches to Parquet.
2. Upload Parquet files to a Google Cloud Storage bucket.
3. Load the transformed datasets into BigQuery using BigQuery load jobs.
4. Populate the dimension and fact tables.

A possible GCS layout:

```text
gs://<bucket>/
    raw/
        service_requests_<batch-id>.parquet
    transformed/
        dim_agency.parquet
        dim_complaint_type.parquet
        dim_location.parquet
        dim_status.parquet
        dim_resolution.parquet
        dim_date.parquet
        fact_complaints.parquet
```

A possible BigQuery layout:

```text
BigQuery project
└── nyc_311
    ├── staging
    │   └── stg_service_requests
    └── warehouse
        ├── dim_agency
        ├── dim_complaint_type
        ├── dim_location
        ├── dim_status
        ├── dim_resolution
        ├── dim_date
        └── fact_complaints
```

The exact dataset and table names may be adjusted during implementation. Staging and warehouse tables should remain logically separated.

## 10. Data Quality and Reliability

Planned checks include:

| Check | Expected behavior |
|---|---|
| `unique_key` is not null | Critical failure if violated |
| `unique_key` is unique in the final fact | Critical failure if violated |
| Required timestamps parse correctly | Invalid values are flagged or rejected according to policy |
| Latitude and longitude are within valid ranges | Invalid values are set to null and flagged |
| Dimension natural attributes are deduplicated | No duplicate dimension members |
| Every fact foreign key resolves to a dimension row | Critical failure if violated |
| Resolution/action update timestamp is not earlier than creation timestamp | Flag suspicious records for review |
| Loaded row counts match transformed row counts | Critical failure if violated |

Failures should be logged with enough context to diagnose the affected batch. The pipeline should not advance its watermark when extraction, transformation, or loading fails.

## 11. API and Local Development Interface

The current `src/server.py` exposes a small FastAPI interface:

| Route | Purpose |
|---|---|
| `GET /api/healthz` | Health check |
| `GET /api/etl/extract` | Development endpoint that invokes extraction |

FastAPI is currently used as a local development/testing interface. It is not the ETL execution mechanism planned for Cloud Run Jobs. The deployed job should execute the pipeline as a process, run to completion, and exit with an appropriate status code.

**Important implementation requirement:** The current extraction endpoint saves the watermark after extraction and returns a `loaded` count, but it does not yet perform a durable file or BigQuery load. Before using this endpoint in the complete pipeline, move watermark persistence until after successful loading, and report `loaded` only when records have actually been loaded.

## 12. Deployment and Scheduling

Planned GCP deployment:

- Build the ETL Docker image.
- Push the image to Artifact Registry.
- Configure a Cloud Run Job to execute the ETL entry point.
- Configure Cloud Scheduler to trigger the job on a daily schedule.
- Use a dedicated service account with least-privilege access to GCS and BigQuery.
- Store API credentials in environment configuration or Secret Manager.
- Write logs to stdout/stderr so Cloud Logging can collect them.
- Return a non-zero process exit code for critical failures.

Cloud Run Jobs are intended for the scheduled batch pipeline. The FastAPI development server should not be required for the job to execute.

## 13. Cost Considerations

The project aims to stay within the available GCP credits and keep ongoing costs low.

Cost-conscious practices:

- Use batch processing rather than streaming.
- Use Parquet to reduce intermediate storage size.
- Keep the initial extraction window limited while developing.
- Use BigQuery load jobs rather than repeatedly inserting rows individually.
- Avoid unnecessary full-table scans and `SELECT *` queries.
- Consider partitioning the fact table by complaint creation date.
- Keep Cloud Run Job CPU, memory, timeout, and retry settings modest.
- Configure a GCP budget alert before running the cloud pipeline regularly.

Exact free-tier eligibility and pricing depend on current GCP terms, region, and usage; verify costs in the Google Cloud console.

## 14. Repository Structure

The repository is evolving. The current code includes `src/extract.py`, `src/server.py`, `src/logging_config.py`, and utility functions. The following is a target structure, not a statement that every module already exists.

```text
nyc-311-etl/
├── README.md
├── PROJECT_SPEC.md
├── requirements.txt
├── Dockerfile
├── Makefile
├── src/
│   ├── __init__.py
│   ├── extract.py
│   ├── transform.py
│   ├── model.py
│   ├── load.py
│   ├── storage.py
│   ├── quality.py
│   ├── server.py
│   ├── logging_config.py
│   └── utils.py
├── tests/
│   ├── test_extract.py
│   ├── test_transform.py
│   ├── test_model.py
│   └── test_quality.py
├── docs/
│   └── data_model.puml
└── data/                  # Local development data; gitignored
```

## 15. Milestones

| # | Milestone | Completion criteria | Status |
|---|---|---|---|
| 1 | Project and data model design | Source, grain, dimensions, and fact table defined | In progress |
| 2 | API extraction | Paginated extraction, retries, date filtering, and watermark handling | Partially implemented |
| 3 | Local Parquet output | Extracted batches saved locally as Parquet | Planned |
| 4 | Data transformation | Cleaning, validation, deduplication, and dimensional model built with Pandas | Planned |
| 5 | GCS staging | Parquet files uploaded to Cloud Storage | Planned |
| 6 | BigQuery loading | Staging, dimension, and fact tables loaded successfully | Planned |
| 7 | Testing and data quality | Unit tests and pipeline checks pass | Planned |
| 8 | Containerization | ETL image builds and runs locally | Planned |
| 9 | GCP deployment | Cloud Run Job completes successfully | Planned |
| 10 | Scheduling | Cloud Scheduler triggers the job successfully | Planned |

## 16. Acceptance Criteria

The project will be considered complete when:

1. The pipeline extracts records from the NYC 311 API using paginated requests.
2. Incremental extraction and watermark handling work without skipping records after a failed run.
3. Extracted data is transformed with Python/Pandas and written to Parquet.
4. Parquet files are staged in Google Cloud Storage.
5. BigQuery contains the agreed dimensions and `fact_complaints` star schema.
6. Fact rows have valid dimension foreign keys and one row per source complaint.
7. Rerunning the pipeline does not create duplicate complaints.
8. Automated tests and data quality checks pass.
9. The Dockerized pipeline runs successfully as a Cloud Run Job.
10. Cloud Scheduler can trigger the job without manual intervention.

## 17. Out of Scope for the Initial Version

- Streaming ingestion.
- Apache Airflow / Cloud Composer.
- Kubernetes / GKE or VM-based orchestration.
- Full historical tracking of every complaint status change.
- Slowly changing dimensions (SCD Type 2).
- A separate facility dimension.
- Dashboard development (may be considered later).
"""

output_path = "/mnt/data/PROJECT_SPEC.md"
pypandoc.convert_text(
    markdown,
    "md",
    format="md",
    outputfile=output_path,
    extra_args=["--standalone"],
)
print(f"Created: {output_path}")
