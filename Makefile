# ---- Configuration ----
PROJECT_NAME 			?= python_etl
CONTAINER_NAME    ?= $(PROJECT_NAME)
API_PORT     			?= 8080
MOUNT_DIR					:= -v "$(PWD):/app"

.PHONY: all build run logs deploy test bash stop

all: build run

build:
	docker build -t $(PROJECT_NAME) .

run:
	docker run -d --name $(CONTAINER_NAME) \
		--env-file .env \
		-p $(API_PORT):8080 \
		-u "$(shell id -u):$(shell id -g)" \
		$(MOUNT_DIR) \
		--mount "type=bind,source=$(HOME)/.config/gcloud/application_default_credentials.json,target=/tmp/gcp-adc.json,readonly" \
		-e GOOGLE_APPLICATION_CREDENTIALS=/tmp/gcp-adc.json \
		$(PROJECT_NAME)

stop:
	docker stop $(CONTAINER_NAME)
	docker rm $(CONTAINER_NAME)

logs:
	docker logs -f $(CONTAINER_NAME)

test:
	docker run --rm \
		$(MOUNT_DIR) \
		$(PROJECT_NAME) \
		pytest -v -s --disable-pytest-warnings tests/$(TEST)

bash:
	docker exec -it $(CONTAINER_NAME) bash

deploy: build
	@echo "Deployment target not configured yet."

