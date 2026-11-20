# NYC 311 Data Pipeline

> **Development paused.** The current pipeline extracts NYC 311 records, transforms them, and writes CSV and Parquet files. The BigQuery load, star schema population, and scheduled deployment are unfinished.

This Python project uses FastAPI to run an incremental batch pipeline against the [NYC 311 Service Requests dataset](https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2020-to-Present/erm2-nwe9). It demonstrates a paginated API integration, data cleaning and validation, and configurable output to the local filesystem or Google Cloud Storage.

## How it works

1. Fetch records from the Socrata API in pages, with retries and backoff for transient HTTP errors. The extraction starts from the saved `created_date` watermark or looks back 14 days on the first run.
2. Deduplicate records by `unique_key`, then clean and validate the data with pandas.
3. Save extracted records as CSV and transformed records as Parquet. Update the local watermark in `data/state.json` after both files have been written.

## Run locally

Run these commands from the repository root. You’ll need Docker, Make, and a `.env` file containing `APP_ENV=local`.

`make run` also mounts the Google Application Default Credentials file, including in local mode. If the file is missing at `$HOME/.config/gcloud/application_default_credentials.json`, run `gcloud auth application-default login` first.

```bash
make build  # Build the Docker image
make run    # Start the container in the background
make logs   # Follow the container logs
```

In a second terminal, check the service and trigger the pipeline. The pipeline endpoint waits for the run to finish before responding.

```bash
curl -fsS http://localhost:8080/api/healthz
curl -fsS -X POST http://localhost:8080/api/etl/run
```

A successful run with records returns a summary like this:

```json
{
  "extracted": 120,
  "transformed": 120,
  "watermark": "2026-11-18T18:30:00.000",
  "run date": "2026-11-19",
  "run ID": "a9c2f6950bca417bbf06ae85433557ad",
  "outputs": {
    "raw": "data/2026-11-19/raw_a9c2f6950bca417bbf06ae85433557ad.csv",
    "cleaned": "data/2026-11-19/cleaned_a9c2f6950bca417bbf06ae85433557ad.parquet"
  }
}
```

When you’re done, press `Ctrl+C` to exit the log stream and run `make stop` to stop and remove the container. Output files and the watermark remain under `data/` on the host.

FastAPI serves interactive API docs at [localhost:8080/docs](http://localhost:8080/docs). The pipeline currently has a known issue when Socrata returns zero rows. The extractor returns a list in that case, and the endpoint expects a DataFrame.

## Configuration

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | Defaults to `local`, which writes outputs under `data/`. Set to `uat` to upload outputs to Google Cloud Storage. |
| `GCS_BUCKET` | Required in `uat`. Use the bucket name without the `gs://` prefix. |
| `NYC_OPEN_DATA_TOKEN` | Optional Socrata app token. Add it to `.env` if you use one. |

Cloud Storage mode requires Google Application Default Credentials with permission to upload objects to the bucket. The watermark stays in `data/state.json` in both modes.

## Run unit tests

After running `make build`, use `make test` to run the transformation unit tests with pytest in a separate Docker container. The API container can be stopped.

```bash
make test
```

## Design

The [project specification](PROJECT_SPEC.md) and [data model diagram](docs/311_service_requests_data_model.puml) describe the planned BigQuery warehouse.
