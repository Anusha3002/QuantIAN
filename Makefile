# QuantIAN — common dev commands
#
# Defaults assume a POSIX shell and that `python3`, `npm`, and `mosquitto`
# are on PATH. Usage: `make help`

PY      ?= python3
VENV    ?= .venv
PYBIN   := $(VENV)/bin
WEBDIR  := web_dashboard
BROKER  ?= mqtt://localhost:1883

.PHONY: help setup install-py install-web broker stack stack-no-iot dashboard \
        test typecheck build screenshots clean stop status push-ticks \
        docker-build docker-up docker-up-ui docker-down docker-logs

help:  ## list available targets
	@awk 'BEGIN{FS=":.*##"; printf "\n\033[1mQuantIAN\033[0m targets:\n\n"} /^[a-zA-Z_-]+:.*?##/ {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: install-py install-web  ## full first-time setup (python + node deps)

install-py:  ## create .venv and install python deps
	test -d $(VENV) || $(PY) -m venv $(VENV)
	$(PYBIN)/pip install --upgrade pip
	$(PYBIN)/pip install -r requirements.txt

install-web:  ## install node deps for the web dashboard
	cd $(WEBDIR) && npm install

broker:  ## start Mosquitto in the background on :1883 (macOS brew path)
	@pgrep -f "mosquitto -d -p 1883" >/dev/null && echo "mosquitto already running" || mosquitto -d -p 1883

stack: broker  ## start full local stack (all 5 peers + streamlit + broker)
	$(PYBIN)/python scripts/run_local_stack.py --with-iot-bridge --with-dashboard --reset-state

stack-no-iot: ## start the 4 core peers + streamlit (no MQTT broker, no iot-bridge)
	$(PYBIN)/python scripts/run_local_stack.py --with-dashboard --reset-state

dashboard:  ## run the React dashboard (Vite dev server on :5174)
	cd $(WEBDIR) && npm run dev

test:  ## run the pytest suite
	$(PYBIN)/pytest --color=yes

typecheck:  ## typecheck the web dashboard
	cd $(WEBDIR) && npx tsc -b --noEmit

build:  ## production build of the web dashboard
	cd $(WEBDIR) && npm run build

screenshots:  ## capture dashboard screenshots (assumes stack + React dashboard are running)
	@which node >/dev/null 2>&1 || (echo "node required"; exit 1)
	@test -d /tmp/qn-puppeteer/node_modules/puppeteer || (mkdir -p /tmp/qn-puppeteer && cd /tmp/qn-puppeteer && npm init -y >/dev/null && npm install puppeteer --silent --no-audit --no-fund)
	cp scripts/capture_screenshots.mjs /tmp/qn-puppeteer/capture.mjs
	@sed -i.bak 's|resolve(__dirname, "..", "docs", "screenshots")|"$(PWD)/docs/screenshots"|' /tmp/qn-puppeteer/capture.mjs
	cd /tmp/qn-puppeteer && node capture.mjs

push-ticks:  ## publish 10 synthetic MQTT cycles to exercise the pipeline
	PYTHONPATH=$(PWD) $(PYBIN)/python -m simulator.mqtt_publisher.cli \
	  --mqtt --cycles 10 --delay 1 --broker-url $(BROKER)

status:  ## quick health check across all peers
	@for port in 8000 8001 8002 8003 8004; do \
	  printf "  :$$port "; curl -s --max-time 2 "http://127.0.0.1:$$port/health" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('service','?'), d.get('status','?'))" 2>/dev/null || echo "DOWN"; \
	done

stop:  ## kill every QuantIAN listener + broker
	-lsof -ti :8000,8001,8002,8003,8004,8501,5174,1883 2>/dev/null | xargs -r kill -15
	@sleep 1
	-lsof -ti :8000,8001,8002,8003,8004,8501,5174,1883 2>/dev/null | xargs -r kill -9
	@echo "stopped"

docker-build:  ## build the QuantIAN image + web dashboard image
	docker compose build

docker-up:  ## start core stack in docker (mosquitto + 5 peers)
	docker compose up -d

docker-up-ui:  ## start core stack + streamlit + nginx-served web dashboard
	docker compose --profile ui up -d --build

docker-down:  ## stop and remove all containers (keeps volumes)
	docker compose --profile ui down

docker-logs:  ## tail all container logs
	docker compose logs -f --tail=40

clean: stop  ## stop stack and wipe runtime state + caches
	rm -rf data/runtime logs .pytest_cache web_dashboard/dist web_dashboard/.vite
	find . -type d -name __pycache__ -not -path "./.venv/*" -not -path "./web_dashboard/node_modules/*" -exec rm -rf {} + 2>/dev/null || true
	@echo "cleaned"
