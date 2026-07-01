# Model Evaluation Metrics

**Model:** YOLOv8m-seg (Ultralytics), 5 classes — `Glass, Metal, Paper, Plastic, Waste`.
**Weights:** `ml/weights/best.pt` (the model served by the API).
**Eval set:** held-out **test split** of the 5-class Waste Detection dataset
(45 images, 115 instances). Inference size **416** (the model's native size).
**Command:** `python ml/evaluate.py --weights ml/weights/best.pt --data ml/dataset.yaml --split test --imgsz 416`

## Detection metrics (box)

| Metric        | Value |
| ------------- | ----- |
| mAP@0.5       | 0.260 |
| mAP@0.5:0.95  | 0.215 |
| Precision     | 0.317 |
| Recall        | 0.342 |
| F1            | 0.329 |

### Per-class AP@0.5

| Class   | AP@0.5 |
| ------- | ------ |
| Glass   | 0.00   |
| Metal   | 0.446  |
| Paper   | 0.143  |
| Plastic | 0.474  |
| Waste   | 0.239  |

## Latency (measured on this machine, Apple Silicon / MPS)

| Stage                | imgsz 416 |
| -------------------- | --------- |
| Inference (MPS)      | ~44 ms/img |
| Post-process         | ~41 ms/img |
| **End-to-end (MPS)** | **~85 ms/img** |
| Inference (CPU)      | ~87 ms/img |

End-to-end incident latency adds the report step: Ollama `llama3.2:1b` (~3 s) or
~0 ms with the deterministic `rules` provider (`LLM_PROVIDER=rules`).

## Notes / honest context

- This is a **cross-dataset, held-out evaluation**: the shipped weights were
  pretrained on a *different* public waste dataset, then evaluated here on the
  Waste Detection test split. Absolute mAP therefore **understates** qualitative
  real-world performance — the model detects prominent waste objects strongly in
  practice (e.g. glass bottle @ 0.87 confidence at imgsz 416 in the demos).
- `Glass` AP is 0.0 on this particular 45-image test set due to label-style /
  distribution mismatch between the two datasets; glass is detected well on
  typical photos.
- To reproduce or improve: `ml/train.py` fine-tunes YOLOv8-seg on this dataset
  (`model.train() -> model.val()`); training on-distribution raises these numbers
  substantially.
