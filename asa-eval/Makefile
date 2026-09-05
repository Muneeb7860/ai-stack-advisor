.PHONY: smoke eval classifier ci
smoke:      ; python -m evalkit.runner --adapter mock
eval:       ; python -m evalkit.runner --adapter $(ADAPTER) --judge $(JUDGE) --out runs/latest.json
classifier: ; python tools/eval_classifier.py --backend $(BACKEND)
ci:         ; python -m evalkit.runner --adapter $(ADAPTER) --baseline runs/last-good.json --fail-on-regression --fail-under 0.65
ADAPTER ?= http
JUDGE   ?= none
BACKEND ?= anthropic
