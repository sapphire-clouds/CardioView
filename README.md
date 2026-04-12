# CardioView — DICOM Viewer

A lightweight, browser-based DICOM viewer built with Flask and vanilla JavaScript. Drag-and-drop DICOM files, inspect pixel data with windowing/brightness controls, explore all DICOM tags in a searchable tree, and play back entire image series as smooth animations.

![Dark mode screenshot placeholder](https://placehold.co/900x480/080B10/0FBFA0?text=CardioView+DICOM+Viewer)

---

## Features

- **DICOM parsing** — reads `.dcm` / `.dicom` and extension-less files using pydicom
- **Image viewer** — zoom (scroll wheel), pan (drag), brightness & contrast sliders, invert, and PNG export
- **Multi-frame playback** — load a single multi-frame DICOM *or* a folder of individual slices and play them back as a video/animation
- **Series filmstrip** — thumbnail strip with click-to-seek; keyboard `←` `→` to step, `Space` to play/pause
- **Adjustable FPS** — 1 – 60 fps slider to control animation speed
- **DICOM tag tree** — all tags grouped by category (Patient, Study, Series, Equipment, Image, CT, MR, Cardiac, …) with full-text search and nested sequence expansion
- **Patient/study banner** — key metadata shown at a glance (modality, dimensions, institution, equipment)
- **Dark / light theme** toggle
- **Responsive layout** — usable on tablets and smaller screens

---

## Tech Stack

| Layer    | Technology |
|----------|-----------|
| Backend  | Python 3 · Flask · pydicom · NumPy · Pillow |
| Frontend | Vanilla JS · Canvas API · HTML5 / CSS3 |
| Fonts    | JetBrains Mono · Inter (Google Fonts) |
| Icons    | Font Awesome 6 |

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/cardioview.git
cd cardioview
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Place the frontend

The Flask app serves `static/index.html`. Copy or move the frontend file:

```bash
mkdir -p static
cp index.html static/index.html
```

### 5. Run the server

```bash
python app.py
```

Open your browser at **http://localhost:5000**.

---

## Usage

### Single file

Drag a `.dcm` file onto the drop zone (or click to browse). The image renders immediately with DICOM windowing applied. Use the **Brightness** and **Contrast** sliders to adjust, **⬛ Invert** to flip polarity, and **⬇ Save PNG** to download the current view.

### Series / animation playback

1. Open a single DICOM file first (or skip straight to step 2).
2. In the **Series Playback** panel below the sliders, drop multiple DICOM files (or click **+ Add DICOM files**). You can also use the **Load Series** button in the top-right header.
3. Each file is parsed server-side; all frames are extracted (including multi-frame DICOMs) and returned as a flat ordered sequence.
4. A filmstrip of thumbnails appears. Click any thumbnail to jump to that frame.
5. Use the transport controls: **⏮ ⏴ ▶ ⏵ ⏭** or the scrubber to navigate.
6. Adjust **FPS** (1 – 60) to change animation speed.
7. Keyboard shortcuts: `←` / `→` to step frames, `Space` to play/pause.

> **Tip — CT series:** Select all `.dcm` files for a CT study at once (Ctrl+A in the file browser). CardioView will sort them by upload order and play them as a stack flythrough.

### DICOM tag explorer

The right panel shows every tag in the file, grouped into categories. Use the search box to filter by tag address, keyword, name, or value. Nested sequences (SQ) are expandable.

---

## API Endpoints

### `POST /api/parse`

Parse a single DICOM file and return image + all tags.

**Request:** `multipart/form-data` with field `file`.

**Response:**
```json
{
  "ok": true,
  "filename": "scan.dcm",
  "summary": { "patientName": "...", "modality": "CT", ... },
  "tagGroups": { "Patient": [...], "Study": [...], ... },
  "totalTags": 142,
  "image": "<base64 PNG>",
  "imageError": null
}
```

---

### `POST /api/parse_series`

Parse multiple DICOM files and extract all frames as a series.

**Request:** `multipart/form-data` with one or more fields named `files`.

**Response:**
```json
{
  "ok": true,
  "totalFrames": 64,
  "frames": [
    { "filename": "slice_001.dcm", "frameIndex": 0, "image": "<base64 PNG>" },
    ...
  ],
  "summary": { ... },
  "tagGroups": { ... },
  "totalTags": 142,
  "errors": []
}
```

---

## Project Structure

```
cardioview/
├── app.py              # Flask backend — parsing, windowing, series API
├── requirements.txt    # Python dependencies
├── static/
│   └── index.html      # Single-file frontend (CSS + JS inline)
├── uploads/            # Temporary upload directory (auto-created)
└── README.md
```

---

## Requirements

```
flask>=3.0.0
flask-cors>=4.0.0
pydicom>=2.4.0
numpy>=1.24.0
Pillow>=10.0.0
```

Python 3.9+ recommended.

---

## Supported DICOM Types

| Type | Notes |
|------|-------|
| CT | Full windowing (WC/WW) applied |
| MR | Auto-normalized if no window tags |
| X-Ray / CR / DX | Monochrome & RGB |
| NM / PET | Frame extraction supported |
| Multi-frame DICOM | All frames extracted from a single file |
| Uncompressed & JPEG/RLE | pydicom handles decompression |

---

## Limitations

- No DICOMDIR or WADO-RS support (plain file upload only)
- Series ordering follows upload order — rename files with zero-padded numbers for correct slice order (e.g. `slice_001.dcm`, `slice_002.dcm`, …)
- Uploaded files are stored temporarily on disk in `uploads/`; no auto-cleanup is implemented
- Not intended for clinical diagnostic use

---

## License

MIT — see `LICENSE` for details.

---

## Contributing

Pull requests are welcome. For major changes please open an issue first to discuss what you would like to change.