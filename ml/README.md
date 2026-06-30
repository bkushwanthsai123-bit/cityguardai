# ML Pipeline - Illegal Garbage Dumping Detector (YOLOv8)

Trains a 5-class YOLOv8 detector. Class order is **fixed** and shared across the
project (`dataset.yaml`, `app/detector.py`, `CONTRACT.md`):

| idx | class | covers |
|---|---|---|
| 0 | `Glass` | glass bottles, jars, broken glass |
| 1 | `Metal` | cans, scrap metal, foil |
| 2 | `Paper` | paper, cardboard, wrappers |
| 3 | `Plastic` | plastic bottles, bags, packaging |
| 4 | `Waste` | mixed/general waste, dumped piles |

The active model is a pretrained YOLOv8m-seg trash detector
(`ml/weights/best.pt`, ~0.43 mAP@0.5 on TACO); retraining via the Colab notebook
(below) yields higher accuracy.

No API keys are used. All dataset downloads are **manual**.

---

## 1. Download datasets (manual, no API key)

Place every export under `ml/data/raw/`. You can mix multiple exports; each
unzipped folder becomes its own source and is merged + remapped automatically.

### A. Roboflow Universe (recommended, free)

1. Go to <https://universe.roboflow.com> and search for, e.g.:
   - "garbage detection", "illegal dumping", "waste detection",
     "overflowing garbage bin", "trash detection".
   - Good starting points: TACO-derived sets, "Garbage Classification/Detection"
     object-detection projects, "Waste/Trash" detection projects.
2. Open a dataset -> **Download Dataset** -> Format = **YOLOv8** ->
   choose **"Download zip to computer"** (no API key needed).
3. Unzip into its own subfolder, e.g.:
   ```
   ml/data/raw/roboflow_garbage_v1/
       data.yaml
       train/images/*.jpg   train/labels/*.txt
       valid/images/...      valid/labels/...
       test/...
   ```
   The `data.yaml` inside the export carries the source `names:` list, which
   `prepare_data.py` uses to remap classes. If it is missing, the script assumes
   the export already uses the canonical index order.

### B. TACO (Trash Annotations in Context)

1. Repo: <https://github.com/pedropro/TACO> (CC BY 4.0). Images + COCO
   annotations (`data/annotations.json`).
2. Convert COCO -> YOLOv8 format. Easiest path: upload the TACO COCO export to a
   Roboflow project and re-export as YOLOv8 (Option A), **or** run any
   COCO->YOLO converter, producing `images/` + `labels/` dirs.
3. Drop the converted export under `ml/data/raw/taco/` with the same
   `images/ labels/` layout.

### Class remapping

Source label vocabularies differ. Edit the `CLASS_NAME_MAP` dict at the top of
`ml/prepare_data.py` so every source class name maps to one of the 5 canonical
classes. Unmapped classes are **dropped** (logged with counts). TACO's ~60 fine
categories typically map to `Plastic`, `Paper`, `Glass`, or `Metal`, with mixed
or unidentifiable trash -> `Waste`.

---

## 2. Prepare the split

From the project root, inside the venv:

```bash
pip install pillow pyyaml numpy            # prepare_data.py deps (stdlib otherwise)
python ml/prepare_data.py                  # reads ml/data/raw/, writes the split
# useful flags:
#   --dry-run        analyse only, no files written
#   --keep-empty     keep label-less images as background negatives
#   -v               verbose / debug logging
```

This:
- discovers all `(image, label)` pairs under `ml/data/raw/`,
- remaps classes to the canonical 5 (fail-loud on malformed labels),
- drops near-duplicate images (average-hash),
- writes an **80/10/10** split into `ml/data/{train,val,test}/{images,labels}`,
- refreshes `ml/dataset.yaml`.

Verify the printed per-class object counts look balanced before training.

---

## 3. Train on Google Colab

1. Zip the prepared split (the folder containing `train/ val/ test/`):
   ```bash
   cd ml && zip -r data.zip data/train data/val data/test
   ```
2. Open `ml/train_colab.ipynb` in Google Colab. Set Runtime -> **GPU (T4)**.
3. Run the cells top to bottom: install -> upload `data.zip` (or mount Drive) ->
   write `dataset.yaml` -> train **YOLOv8s** (toggle to **YOLOv8m** in cell 4)
   for ~100-150 epochs, imgsz 640, mosaic/HSV/flip aug, cosine LR, `patience=25`
   -> validate on the test split -> download `best.pt` and `garbage_runs.zip`.

**Target:** mAP@0.5 >= 0.85 on the test split. If below, add more data, train
longer, or switch to YOLOv8m.

---

## 4. Install weights & evaluate locally

1. Copy the downloaded weights to:
   ```
   ml/weights/best.pt
   ```
2. Evaluate on the local test split (writes `docs/metrics.md` + plots):
   ```bash
   pip install ultralytics
   python ml/evaluate.py --weights ml/weights/best.pt --data ml/dataset.yaml
   ```
   Outputs the metrics table (mAP@0.5, mAP@0.5:0.95, P, R, F1, per-class AP) and
   mean CPU inference latency, and copies the confusion matrix + PR/F1 curves
   into `docs/`.

The app loads `ml/weights/best.pt` by default (`MODEL_PATH` in `app/config.py`).
If the file is absent, `app/detector.py` falls back to `yolov8n.pt` so the API
still boots.

---

## Files

| file | purpose |
|---|---|
| `dataset.yaml` | YOLO data config; canonical class names (fixed order) |
| `prepare_data.py` | ingest raw exports -> remap -> dedup -> 80/10/10 split |
| `evaluate.py` | run `ultralytics val` on test split -> metrics + plots |
| `train_colab.ipynb` | Colab training notebook (YOLOv8s/m) |
| `data/raw/` | drop manually-downloaded YOLOv8 exports here |
| `weights/best.pt` | trained weights (you place this after training) |
