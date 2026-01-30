# Top-level Makefile to streamline common development and demo tasks for the
# Lab 3 distributed systems project.  Each target encapsulates a standard
# workflow (build, run, replay, etc.) so that you don't have to remember
# individual docker‑compose commands.  All commands are run relative to the
# project root.

# Base docker compose command.  Docker Desktop on Windows/WSL and Linux
# automatically picks up the compose file in the current directory.
COMPOSE = docker compose

## Primary targets

# Build all service images. This does not run the containers.
.PHONY: build
build:
	$(COMPOSE) build

# Bring up the full stack in detached mode.  Does not rebuild images;
# use `make build` beforehand if you've changed code.
.PHONY: up
up:
	$(COMPOSE) up -d

# Stop all running containers but leave volumes intact.
.PHONY: down
down:
	$(COMPOSE) down

# Stop and remove all containers, networks and volumes for a clean slate.
.PHONY: clean
clean:
	$(COMPOSE) down -v

## Convenience targets for different run modes

# Launch the system in normal mode (1 event/second).  This will rebuild
# containers and set the appropriate environment variables for the
# publisher.  All previous containers/volumes are removed.
.PHONY: load
load: clean
	@echo "[make] Starting system in normal mode (EVENT_RATE=1.0, no bursts)"
	EVENT_RATE=1.0 ENABLE_BURST=false $(COMPOSE) up -d --build

# Launch the system in burst mode for backpressure testing (50 events/second).
.PHONY: burst
burst: clean
	@echo "[make] Starting system in burst mode (EVENT_RATE=50.0, ENABLE_BURST=true)"
	EVENT_RATE=50.0 ENABLE_BURST=true $(COMPOSE) up -d --build

# Run the chaos test script to simulate consumer and broker failures.  This
# target assumes that the scripts have executable permissions and that
# Docker is installed.  The script will start the stack, kill and revive
# the validator and the broker, and follow the logs at the end.
.PHONY: chaos
chaos:
	@bash run_chaos.sh

# Replay all previously persisted events from the audit log.  This target
# requires the stack to be running (e.g. via `make load` or `make burst`).
.PHONY: replay
replay:
	@bash replay.sh

# Run the full demonstration (load→burst→chaos→verify).  Refer to
# run_demo.sh for details; this target is just a wrapper.
.PHONY: demo
demo:
	@bash run_demo.sh

# Follow logs of all services.  Change the tail count to see more history.
.PHONY: logs
logs:
	$(COMPOSE) logs -f --tail=100

## Testing

# Run all unit tests.  Requires Python and pytest installed in the container
# or host environment.
.PHONY: test
test:
	python3 tests/run_tests.py