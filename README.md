# NYC 311 Data Warehouse

> **Work in progress**

A portfolio project focused on practicing the design and implementation of an **ELT pipeline** that extracts public data, stages it in cloud storage, and loads it into a cloud data warehouse for analytical use.

## Project Overview

The pipeline uses the [NYC 311 Service Requests dataset](https://data.cityofnewyork.us/) as its data source. The goal is to retrieve service-request records, store them in an analytics-friendly format, load them into Google BigQuery, and organize the data into a dimensional model using a star schema.

## Planned Technologies

- **Python** — extraction and pipeline orchestration
- **Socrata API (`sodapy`)** — source data access
- **Pandas / PyArrow** — data processing and Parquet files
- **Google Cloud Storage** — data staging
- **Google BigQuery** — data warehouse
- **Docker, Cloud Run Jobs, and Cloud Scheduler** — containerization and scheduled execution

## Project Status

This project is actively being developed. The pipeline design, data model, and implementation may change as the project progresses.