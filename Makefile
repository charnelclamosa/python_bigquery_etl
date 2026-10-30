# ---- Configuration ----
PROJECT_NAME 			?= python_etl
CONTAINER_NAME    ?= $(PROJECT_NAME)
API_PORT     			?= 8080

.PHONY: all build run logs deploy bash stop

all: build run

build:
	docker build -t $(PROJECT_NAME) .

run:
	docker run -d --name $(CONTAINER_NAME) \
		-p $(API_PORT):8080 \
		-u "$(shell id -u):$(shell id -g)" \
		-v "$(PWD):/app" $(PROJECT_NAME)

stop:
	docker stop $(CONTAINER_NAME)
	docker rm $(CONTAINER_NAME)

logs:
	docker logs -f $(CONTAINER_NAME)

bash:
	docker exec -it $(CONTAINER_NAME) bash

deploy: build
	@echo "Deployment target not configured yet."

