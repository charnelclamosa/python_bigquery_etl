# ---- Configuration ----
PROJECT_NAME 			?= python_etl
CONTAINER_NAME    ?= $(PROJECT_NAME)
API_PORT     			?= 8080
MOUNT_DIR					:= -v "$(PWD):/app" $(PROJECT_NAME)

.PHONY: all build run logs deploy test bash stop

all: build run

build:
	docker build -t $(PROJECT_NAME) .

run:
	docker run -d --name $(CONTAINER_NAME) \
		-p $(API_PORT):8080 \
		-u "$(shell id -u):$(shell id -g)" \
		$(MOUNT_DIR)

stop:
	docker stop $(CONTAINER_NAME)
	docker rm $(CONTAINER_NAME)

logs:
	docker logs -f $(CONTAINER_NAME)

test:
	docker run --rm $(MOUNT_DIR) pytest -v -s --disable-pytest-warnings tests/$(TEST)

bash:
	docker exec -it $(CONTAINER_NAME) bash

deploy: build
	@echo "Deployment target not configured yet."

