# CardioView

**A clean, web-based DICOM viewer built for cardiovascular imaging.**  
Self-hosted. No accounts. No cloud. Just drop a file and go.

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask)
![pydicom](https://img.shields.io/badge/pydicom-2.4%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Overview

CardioView is a lightweight, self-hosted web application that lets you open and inspect any DICOM file directly in your browser. It was built specifically for cardiovascular imaging workflows — CT angiography, cardiac MRI, echocardiography, nuclear medicine — but works with any valid DICOM file.

**No proprietary software. No install wizard. No internet required after setup.**

### What it does

- Renders the **scan image** with automatic windowing, invert toggle, and window-level presets
- Extracts and displays **every DICOM tag** — including nested sequences — organised into logical groups
- Handles **multi-frame files** (picks the middle frame for preview)
- Applies correct **Modality LUT** (RescaleSlope / Intercept) and **VOI LUT** (WindowCenter / WindowWidth) automatically
- Shows a **patient & study summary** banner at a glance
- **Live search** across all tags, names, keywords, and values
- **Dark mode and Light mode** — toggle with one click

---

## Screenshots

> _Drop a `.dcm` file on the landing page — results appear instantly._

| Dark Mode | Light Mode |
|-----------|------------|
| Patient banner, scan image, grouped tags | Same layout, inverted palette |

---

## Quick Start

### Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.9 or later |
| pip | Any recent version |

No Node.js. No Docker. No database.

---

### Installation

**1. Clone the repository**

```bash
git clone https://github.com/yourname/cardioview.git
cd cardioview
```

**2. Create a virtual environment**

```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate

# Windows (Command Prompt)
python -m venv venv
venv\Scripts\activate.bat

# Windows (PowerShell)
python -m venv venv
venv\Scripts\Activate.ps1
```

You should see `(venv)` at the beginning of your shell prompt.

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Start the server**

```bash
python app.py
```

**5. Open in your browser**

```
http://localhost:5000
```

---

## Usage

1. **Upload** — Drag and drop a `.dcm` file onto the upload area, or click to browse.
2. **View** — The scan image renders immediately on the left panel.
3. **Inspect** — All DICOM tags appear on the right, grouped by category.
4. **Search** — Type anything in the search bar to filter across all tags.
5. **Adjust** — Use the window-level preset buttons (Soft Tissue, Lung, Bone, Brain) to adjust image rendering.
6. **Invert** — Click the Invert button to flip image contrast (useful for X-ray viewing).
7. **Export** — Click "Save PNG" to download the rendered image.
8. **Theme** — Use the sun/moon button in the top-right corner to switch between dark and light mode.

---

## Tag Groups

Tags are automatically classified into the following groups:

| Group | Contents |
|-------|----------|
| **Patient** | Name, ID, DOB, sex, age, weight, comments |
| **Study** | UID, date, time, description, accession number, referring physician |
| **Series** | UID, modality, body part, protocol, operators |
| **Equipment** | Institution, manufacturer, model, device serial, software version |
| **Image** | Rows, columns, frames, pixel spacing, orientation, position |
| **LUT & Windowing** | Rescale slope/intercept, window center/width, VOI LUT |
| **Acquisition** | Dates, times, image type, flip angle, TR, TE, SAR |
| **Cardiac** | Heart rate, RR interval, trigger times, PVC rejection |
| **Contrast** | Agent, route, volume, flow rate, timing |
| **CT** | KVP, tube current, pitch, collimation, CTDIvol, convolution kernel |
| **MR** | Scanning sequence, MR acquisition type, echo train length |
| **NM / PET** | Radiopharmaceutical, energy windows, decay correction |
| **SOP / Meta** | SOP class/instance UIDs, transfer syntax, character set |
| **Other** | Any tag not matched by the above classification |

Sequence elements (VR = SQ) are expanded inline — you can see every nested item.

---

## Project Structure

```
cardioview/
├── app.py              # Flask backend — DICOM parsing, image extraction, API
├── requirements.txt    # Python dependencies
├── README.md           # This file
├── uploads/            # Temporary upload folder (auto-created, not tracked)
└── static/
    └── index.html      # Complete frontend — HTML, CSS, JS in one file
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| [Flask](https://flask.palletsprojects.com/) | Lightweight web server and routing |
| [flask-cors](https://flask-cors.readthedocs.io/) | CORS headers for API |
| [pydicom](https://pydicom.github.io/) | DICOM file reading and tag extraction |
| [NumPy](https://numpy.org/) | Pixel array manipulation and windowing |
| [Pillow](https://pillow.readthedocs.io/) | Image conversion from array to PNG |

---

## Troubleshooting

**Port 5000 already in use (common on macOS)**

macOS Monterey and later uses port 5000 for AirPlay Receiver. Either disable it in *System Preferences → General → AirDrop & Handoff* or change the port:

```python
# In app.py, change the last line to:
app.run(debug=True, port=5001, host="0.0.0.0")
# Then open http://localhost:5001
```

**"No pixel data in this file"**

Some DICOM files contain only metadata — DICOMDIR files, structured reports, and some secondary capture objects have no image. All tags will still be displayed correctly.

**Image appears very dark or featureless**

The server applies the file's WindowCenter / WindowWidth values automatically. If those are absent or unusual, try the window preset buttons. The "Default" preset uses full-range normalisation.

**"Cannot read DICOM file"**

The parser uses `force=True` which handles many non-standard files. If parsing still fails, the file may be:
- Corrupted or incomplete
- A proprietary vendor format without standard DICOM headers
- A DICOMDIR index file (not a single image)

**Windows: `python` not found**

Use `py` instead of `python`, or ensure Python was added to PATH during installation.

---

## Sample DICOM Files

If you need test files:

- **pydicom built-in test files** — `python -c "import pydicom; print(pydicom.data.get_testfiles_name('CT_small.dcm'))"`
- **DICOM Library** — [dicomlibrary.com](https://www.dicomlibrary.com) (free account)
- **OsiriX sample datasets** — [osirix-viewer.com/resources/dicom-image-library](https://www.osirix-viewer.com/resources/dicom-image-library/)

---

## Security Notice

CardioView is designed for **local desktop use only**.

- Files are saved temporarily to the `uploads/` folder and are not automatically deleted
- There is no authentication or access control
- Do not expose this application to the internet without adding proper authentication middleware

---

## Roadmap

- [ ] Multi-file series support
- [ ] DICOMDIR browsing
- [ ] Actual client-side windowing slider
- [ ] Side-by-side frame comparison
- [ ] Export full tag report as CSV

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

---

## License

MIT — free to use, modify, and distribute. See `LICENSE` for details.

---

<p align="center">Built with pydicom · Flask · and a need for a clean DICOM viewer that just works</p>