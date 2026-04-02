import os
import json
import base64
import io
import numpy as np
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pydicom
from pydicom.uid import UID
import warnings

warnings.filterwarnings("ignore")

app = Flask(__name__, static_folder="static")
CORS(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def get_tag_name(tag):
    try:
        return pydicom.datadict.keyword_for_tag(tag)
    except Exception:
        return str(tag)


def clean_value(element):
    vr = element.VR
    val = element.value

    try:
        if vr == "SQ":
            return f"[Sequence with {len(val)} item(s)]"
        elif vr in ("OB", "OW", "OD", "OF", "UN"):
            return f"[Binary data, {len(val)} bytes]"
        elif vr == "UI":
            uid_val = str(val)
            try:
                name = UID(uid_val).name
                if name and name != uid_val:
                    return f"{uid_val} ({name})"
            except Exception:
                pass
            return uid_val
        elif vr in ("DS", "IS"):
            if isinstance(val, pydicom.multival.MultiValue):
                return " / ".join(str(v) for v in val)
            return str(val)
        elif isinstance(val, pydicom.multival.MultiValue):
            return " / ".join(str(v) for v in val)
        elif isinstance(val, bytes):
            return f"[Binary data, {len(val)} bytes]"
        else:
            s = str(val).strip()
            return s if s else "(empty)"
    except Exception:
        return "(unreadable)"


def build_tag_groups(ds):
    groups = {}
    group_order = [
        ("Patient", [
            "PatientName", "PatientID", "PatientBirthDate", "PatientSex",
            "PatientAge", "PatientWeight", "PatientSize", "PatientComments",
            "EthnicGroup", "OtherPatientIDs"
        ]),
        ("Study", [
            "StudyInstanceUID", "StudyDate", "StudyTime", "StudyDescription",
            "AccessionNumber", "ReferringPhysicianName", "StudyID",
            "InstitutionName", "InstitutionalDepartmentName"
        ]),
        ("Series", [
            "SeriesInstanceUID", "SeriesDate", "SeriesTime", "SeriesDescription",
            "Modality", "SeriesNumber", "BodyPartExamined", "PatientPosition",
            "ProtocolName", "OperatorsName", "PerformingPhysicianName"
        ]),
        ("Image", [
            "SOPInstanceUID", "SOPClassUID", "InstanceNumber", "ImageType",
            "AcquisitionDate", "AcquisitionTime", "ContentDate", "ContentTime",
            "SamplesPerPixel", "PhotometricInterpretation", "Rows", "Columns",
            "BitsAllocated", "BitsStored", "HighBit", "PixelRepresentation",
            "PixelSpacing", "SliceThickness", "SliceLocation", "ImageOrientationPatient",
            "ImagePositionPatient", "WindowCenter", "WindowWidth", "RescaleIntercept",
            "RescaleSlope", "LossyImageCompression"
        ]),
        ("Equipment", [
            "Manufacturer", "ManufacturerModelName", "DeviceSerialNumber",
            "SoftwareVersions", "StationName", "InstitutionAddress",
            "DistanceSourceToDetector", "DistanceSourceToPatient"
        ]),
        ("Cardiac / Acquisition", [
            "HeartRate", "NominalInterval", "LowRRValue", "HighRRValue",
            "IntervalsAcquired", "IntervalsRejected", "PVCRejection",
            "SkipBeats", "HeartRateVariability", "CardiacCycleLength",
            "TriggerWindow", "R-RIntervalTimeNominal", "FrameReferenceTime",
            "TriggerTime", "FrameTime", "FrameTimeVector", "ActualFrameDuration",
            "NumberOfFrames", "FrameDelay", "RadiopharmaceuticalInformationSequence"
        ]),
        ("Contrast / Agent", [
            "ContrastBolusAgent", "ContrastBolusStartTime", "ContrastBolusStopTime",
            "ContrastBolusVolume", "ContrastBolusIngredientConcentration",
            "ContrastBolusTotalDose"
        ]),
    ]

    found_keywords = set()

    for group_name, keywords in group_order:
        entries = []
        for kw in keywords:
            try:
                if hasattr(ds, kw):
                    elem = ds[pydicom.datadict.tag_for_keyword(kw)]
                    entries.append({
                        "tag": str(elem.tag),
                        "keyword": kw,
                        "vr": elem.VR,
                        "name": elem.name,
                        "value": clean_value(elem)
                    })
                    found_keywords.add(kw)
            except Exception:
                pass
        if entries:
            groups[group_name] = entries

    # All other tags
    other = []
    for elem in ds:
        if elem.keyword in found_keywords:
            continue
        if elem.tag.group == 0x7FE0:  # pixel data
            continue
        try:
            other.append({
                "tag": str(elem.tag),
                "keyword": elem.keyword or get_tag_name(elem.tag),
                "vr": elem.VR,
                "name": elem.name,
                "value": clean_value(elem)
            })
        except Exception:
            pass

    if other:
        groups["Other Tags"] = other

    return groups


def extract_image(ds):
    try:
        pixel_array = ds.pixel_array
    except Exception as e:
        return None, str(e)

    try:
        # Handle multi-frame: pick middle frame
        if pixel_array.ndim == 3 and pixel_array.shape[0] > 1:
            frame_idx = pixel_array.shape[0] // 2
            img_data = pixel_array[frame_idx]
        elif pixel_array.ndim == 3:
            img_data = pixel_array[0]
        else:
            img_data = pixel_array

        # Apply modality LUT (rescale)
        slope = float(getattr(ds, "RescaleSlope", 1))
        intercept = float(getattr(ds, "RescaleIntercept", 0))
        img_data = img_data.astype(np.float64) * slope + intercept

        # Apply VOI LUT / windowing
        try:
            wc_raw = ds.WindowCenter
            ww_raw = ds.WindowWidth
            wc = float(wc_raw[0] if hasattr(wc_raw, "__iter__") else wc_raw)
            ww = float(ww_raw[0] if hasattr(ww_raw, "__iter__") else ww_raw)
            low = wc - ww / 2
            high = wc + ww / 2
            img_data = np.clip(img_data, low, high)
            img_data = (img_data - low) / (high - low) * 255
        except Exception:
            min_v, max_v = img_data.min(), img_data.max()
            if max_v > min_v:
                img_data = (img_data - min_v) / (max_v - min_v) * 255
            else:
                img_data = np.zeros_like(img_data)

        img_uint8 = img_data.astype(np.uint8)

        # Color images
        try:
            pi = ds.PhotometricInterpretation
        except Exception:
            pi = "MONOCHROME2"

        if pi in ("RGB", "YBR_FULL", "YBR_FULL_422") and img_uint8.ndim == 3:
            from PIL import Image as PILImage
            pil_img = PILImage.fromarray(img_uint8, mode="RGB")
        else:
            from PIL import Image as PILImage
            pil_img = PILImage.fromarray(img_uint8, mode="L").convert("RGB")

        buf = io.BytesIO()
        pil_img.save(buf, format="PNG", optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return b64, None
    except Exception as e:
        return None, str(e)


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/parse", methods=["POST"])
def parse_dicom():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    f = request.files["file"]
    filename = f.filename or "upload.dcm"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    f.save(filepath)

    try:
        ds = pydicom.dcmread(filepath, force=True)
    except Exception as e:
        return jsonify({"error": f"Failed to read DICOM file: {e}"}), 400

    tag_groups = build_tag_groups(ds)
    img_b64, img_err = extract_image(ds)

    # Quick summary
    summary = {
        "patientName": str(getattr(ds, "PatientName", "—")).replace("^", " ").strip(),
        "modality": str(getattr(ds, "Modality", "—")),
        "studyDate": str(getattr(ds, "StudyDate", "—")),
        "studyDescription": str(getattr(ds, "StudyDescription", "—")),
        "institution": str(getattr(ds, "InstitutionName", "—")),
        "rows": str(getattr(ds, "Rows", "—")),
        "columns": str(getattr(ds, "Columns", "—")),
        "frames": str(getattr(ds, "NumberOfFrames", "1")),
    }

    return jsonify({
        "summary": summary,
        "tagGroups": tag_groups,
        "image": img_b64,
        "imageError": img_err,
        "filename": filename
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
