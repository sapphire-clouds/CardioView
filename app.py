import os
import base64
import io
import traceback
import numpy as np
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pydicom
from pydicom import dcmread
from pydicom.uid import UID
from pydicom.sequence import Sequence
from pydicom.multival import MultiValue
import warnings

warnings.filterwarnings("ignore")

app = Flask(__name__, static_folder="static")
CORS(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ─── VALUE SERIALIZATION ──────────────────────────────────────────────────────

def uid_name(uid_str):
    try:
        name = UID(uid_str).name
        if name and name != uid_str:
            return name
    except Exception:
        pass
    return None


def safe_str(val):
    if val is None:
        return ""
    if isinstance(val, bytes):
        try:
            return val.decode("latin-1").strip("\x00").strip()
        except Exception:
            return val.hex()
    if isinstance(val, (MultiValue, list, tuple)):
        return " \\ ".join(safe_str(v) for v in val)
    if isinstance(val, pydicom.valuerep.PersonName):
        return str(val).replace("^", " ").strip()
    if isinstance(val, pydicom.uid.UID):
        s = str(val)
        name = uid_name(s)
        return f"{s}  [{name}]" if name else s
    try:
        return str(val).strip("\x00").strip()
    except Exception:
        return repr(val)


def serialize_element(elem, depth=0):
    MAX_DEPTH = 12
    result = {
        "tag":      str(elem.tag),
        "keyword":  elem.keyword or "",
        "name":     elem.name or str(elem.tag),
        "vr":       elem.VR,
        "value":    "",
        "children": []
    }
    try:
        vr = elem.VR

        if elem.tag == (0x7FE0, 0x0010):
            try:
                result["value"] = f"[Pixel Data — {len(elem.value):,} bytes]"
            except Exception:
                result["value"] = "[Pixel Data]"
            return result

        if vr in ("OB", "OW", "OD", "OF", "OL", "OV", "UN", "OB or OW"):
            try:
                result["value"] = f"[Binary — {len(elem.value):,} bytes]"
            except Exception:
                result["value"] = "[Binary data]"
            return result

        if vr == "SQ":
            seq = elem.value
            result["value"] = f"{len(seq)} item(s)"
            if depth < MAX_DEPTH:
                for i, item in enumerate(seq):
                    item_node = {
                        "tag":      f"Item {i + 1}",
                        "keyword":  "",
                        "name":     f"Item {i + 1}",
                        "vr":       "ITEM",
                        "value":    "",
                        "children": []
                    }
                    for child in item:
                        item_node["children"].append(serialize_element(child, depth + 1))
                    result["children"].append(item_node)
            return result

        if vr == "AT":
            val = elem.value
            if isinstance(val, MultiValue):
                result["value"] = ", ".join(str(v) for v in val)
            else:
                result["value"] = str(val)
            return result

        result["value"] = safe_str(elem.value)

    except Exception as e:
        result["value"] = f"[Error: {e}]"

    return result


# ─── GROUP CLASSIFICATION ─────────────────────────────────────────────────────

GROUP_KEYWORD_MAP = {
    "Patient": [
        "PatientName","PatientID","PatientBirthDate","PatientSex","PatientAge",
        "PatientWeight","PatientSize","PatientAddress","PatientComments",
        "EthnicGroup","Occupation","SmokingStatus","PregnancyStatus",
        "LastMenstrualDate","PatientState","OtherPatientIDs","OtherPatientNames",
        "OtherPatientIDsSequence","ResponsiblePerson","ResponsibleOrganization",
        "MilitaryRank","BranchOfService","MedicalRecordLocator","IssuerOfPatientID",
    ],
    "Study": [
        "StudyInstanceUID","StudyDate","StudyTime","StudyDescription","StudyID",
        "AccessionNumber","ReferringPhysicianName","ConsultingPhysicianName",
        "StudyStatusID","StudyPriorityID","StudyComments","ReasonForStudy",
        "RequestedProcedureDescription","RequestingPhysician","ReasonForTheRequestedProcedure",
        "RequestedProcedureID","PlacerOrderNumberImagingServiceRequest",
        "FillerOrderNumberImagingServiceRequest",
    ],
    "Series": [
        "SeriesInstanceUID","SeriesDate","SeriesTime","SeriesDescription","SeriesNumber",
        "Modality","BodyPartExamined","PatientPosition","ProtocolName","OperatorsName",
        "PerformingPhysicianName","PerformedProcedureStepDescription","Laterality",
        "SmallestImagePixelValue","LargestImagePixelValue","AnatomicRegionSequence",
        "RequestAttributesSequence","PerformedProcedureStepID",
    ],
    "Equipment": [
        "InstitutionName","InstitutionAddress","InstitutionalDepartmentName",
        "Manufacturer","ManufacturerModelName","DeviceSerialNumber","SoftwareVersions",
        "StationName","DetectorID","PlateID","CassetteID","GantryID",
        "InstitutionCodeSequence","DeviceUID","EntityLabelingType",
    ],
    "Image": [
        "Rows","Columns","NumberOfFrames","SamplesPerPixel","PlanarConfiguration",
        "PhotometricInterpretation","BitsAllocated","BitsStored","HighBit",
        "PixelRepresentation","PixelSpacing","ImagerPixelSpacing","NominalScannedPixelSpacing",
        "SliceThickness","SliceLocation","SpacingBetweenSlices",
        "ImageOrientationPatient","ImagePositionPatient","FrameOfReferenceUID",
        "PositionReferenceIndicator","PixelAspectRatio","LossyImageCompression",
        "LossyImageCompressionRatio","LossyImageCompressionMethod",
        "RecommendedDisplayFrameRate","FrameIncrementPointer","PixelDataProviderURL",
    ],
    "LUT & Windowing": [
        "RescaleIntercept","RescaleSlope","RescaleType","WindowCenter","WindowWidth",
        "WindowCenterWidthExplanation","VOILUTFunction","VOILUTSequence",
        "ModalityLUTSequence","PresentationLUTShape","PresentationLUTSequence",
        "PixelIntensityRelationship","PixelIntensityRelationshipSign",
        "RedPaletteColorLookupTableDescriptor","GreenPaletteColorLookupTableDescriptor",
        "BluePaletteColorLookupTableDescriptor","LargestMonochromePixelValue",
        "SmallestMonochromePixelValue",
    ],
    "Acquisition": [
        "AcquisitionDate","AcquisitionTime","AcquisitionNumber","AcquisitionDuration",
        "AcquisitionMatrix","ContentDate","ContentTime","InstanceCreationDate",
        "InstanceCreationTime","InstanceCreatorUID","ImageType","InstanceNumber",
        "TemporalPositionIdentifier","NumberOfTemporalPositions","TemporalResolution",
        "TriggerTime","FrameReferenceTime","FrameTime","FrameTimeVector",
        "ActualFrameDuration","FrameDelay","NumberOfAverages","ImagingFrequency",
        "ImagedNucleus","EchoTime","EchoNumbers","MagneticFieldStrength",
        "NumberOfPhaseEncodingSteps","PercentSampling","PercentPhaseFieldOfView",
        "PixelBandwidth","FlipAngle","VariableFlipAngleFlag","SAR","dBdt",
        "TriggerSourceOrType","TriggerDelayTime",
    ],
    "Cardiac": [
        "HeartRate","NominalInterval","LowRRValue","HighRRValue",
        "IntervalsAcquired","IntervalsRejected","PVCRejection","SkipBeats",
        "HeartRateVariability","CardiacCycleLength","TriggerWindow",
        "NominalCardiacTriggerDelayTime","ActualCardiacTriggerDelayTime",
        "NominalCardiacTriggerTimePriorToRPeak","ActualCardiacTriggerTimePriorToRPeak",
        "RRIntervalTimeNominal","CardiovascularAngiographicSequence",
    ],
    "Contrast": [
        "ContrastBolusAgent","ContrastBolusAgentSequence","ContrastBolusStartTime",
        "ContrastBolusStopTime","ContrastBolusVolume","ContrastBolusTotalDose",
        "ContrastBolusIngredient","ContrastBolusIngredientConcentration",
        "ContrastBolusRoute","ContrastBolusFlowRate","ContrastBolusFlowDuration",
        "ContrastBolusAdministrationRouteSequence",
    ],
    "CT": [
        "KVP","XRayTubeCurrent","Exposure","ExposureTime","FocalSpots",
        "ConvolutionKernel","ReconstructionDiameter","DistanceSourceToDetector",
        "DistanceSourceToPatient","GantryDetectorTilt","TableHeight",
        "RotationDirection","ExposureModulationType","EstimatedDoseSaving",
        "CTDIvol","SingleCollimationWidth","TotalCollimationWidth",
        "TableFeedPerRotation","SpiralPitchFactor","DataCollectionDiameter",
        "FilterType","GeneratorPower","ExposureInuAs",
        "TableSpeed","RevolutionTime","CTDIPhantomTypeCodeSequence",
    ],
    "MR": [
        "ScanningSequence","SequenceVariant","ScanOptions","MRAcquisitionType",
        "SequenceName","RepetitionTime","InversionTime","ReceiveCoilName",
        "TransmitCoilName","InPlanePhaseEncodingDirection","EchoTrainLength",
        "ParallelReductionFactorInPlane","AcquisitionContrast","EffectiveEchoTime",
        "ParallelAcquisitionTechnique","PartialFourierDirection",
        "DiffusionBValue","DiffusionGradientOrientation","VelocityEncodingDirection",
    ],
    "NM / PET": [
        "RadiopharmaceuticalInformationSequence","Radiopharmaceutical",
        "RadionuclideCodeSequence","RadiopharmaceuticalStartTime",
        "RadiopharmaceuticalStopTime","RadionuclideTotalDose","RadiopharmaceuticalVolume",
        "RadiopharmaceuticalRoute","RadiopharmaceuticalCodeSequence",
        "EstimatedRadiographicMagnificationFactor","GateInformationSequence",
        "EnergyWindowInformationSequence","DetectorInformationSequence",
        "RotationInformationSequence","NumberOfSlices","SliceVector",
        "AngularStep","ZoomFactor","ScanArc","ActualFrameDuration",
    ],
    "SOP / Meta": [],
    "Other": [],
}

_KW_TO_GROUP = {}
for _g, _kws in GROUP_KEYWORD_MAP.items():
    for _kw in _kws:
        _KW_TO_GROUP[_kw] = _g

GROUP_ORDER = [
    "Patient","Study","Series","Equipment","Image","LUT & Windowing",
    "Acquisition","Cardiac","Contrast","CT","MR","NM / PET","SOP / Meta","Other"
]


def classify(elem):
    if elem.keyword in _KW_TO_GROUP:
        return _KW_TO_GROUP[elem.keyword]
    g = elem.tag.group
    if g == 0x0002: return "SOP / Meta"
    if g == 0x0008: return "Study"
    if g == 0x0010: return "Patient"
    if g == 0x0018: return "Acquisition"
    if g == 0x0020: return "Image"
    if g == 0x0028: return "LUT & Windowing"
    if g in (0x0032, 0x0040): return "Study"
    if g == 0x0054: return "NM / PET"
    return "Other"


def parse_dataset(ds):
    groups = {g: [] for g in GROUP_ORDER}

    for elem in ds:
        try:
            serialized = serialize_element(elem)
            grp = classify(elem)
            groups[grp].append(serialized)
        except Exception as e:
            groups["Other"].append({
                "tag": str(elem.tag),
                "keyword": getattr(elem, "keyword", ""),
                "name": getattr(elem, "name", str(elem.tag)),
                "vr": getattr(elem, "VR", "??"),
                "value": f"[Error: {e}]",
                "children": []
            })

    result = {}
    for g in GROUP_ORDER:
        if groups[g]:
            result[g] = groups[g]

    total = sum(len(v) for v in result.values())
    return result, total


# ─── IMAGE EXTRACTION ─────────────────────────────────────────────────────────

def normalize_frame(arr, ds=None, apply_window=True):
    """Normalize a 2D or 3D numpy array frame to uint8 PNG base64."""
    img = arr.astype(np.float64)

    # Modality LUT
    if ds is not None:
        slope     = float(getattr(ds, "RescaleSlope", 1) or 1)
        intercept = float(getattr(ds, "RescaleIntercept", 0) or 0)
        img = img * slope + intercept

    # VOI windowing
    applied_window = False
    if apply_window and ds is not None:
        wc_raw = getattr(ds, "WindowCenter", None)
        ww_raw = getattr(ds, "WindowWidth", None)
        if wc_raw is not None and ww_raw is not None:
            try:
                wc = float(wc_raw[0] if isinstance(wc_raw, (list, MultiValue)) else wc_raw)
                ww = float(ww_raw[0] if isinstance(ww_raw, (list, MultiValue)) else ww_raw)
                if ww > 0:
                    lo, hi = wc - ww / 2, wc + ww / 2
                    img = np.clip(img, lo, hi)
                    img = (img - lo) / (hi - lo) * 255.0
                    applied_window = True
            except Exception:
                pass

    if not applied_window:
        mn, mx = img.min(), img.max()
        img = (img - mn) / (mx - mn) * 255.0 if mx > mn else np.zeros_like(img)

    img_u8 = img.astype(np.uint8)

    pi = ""
    if ds is not None:
        pi = str(getattr(ds, "PhotometricInterpretation", "MONOCHROME2")).strip()

    from PIL import Image as PILImage
    if img_u8.ndim == 3 and img_u8.shape[-1] == 3:
        pil = PILImage.fromarray(img_u8, "RGB")
    elif img_u8.ndim == 3 and img_u8.shape[-1] == 4:
        pil = PILImage.fromarray(img_u8, "RGBA").convert("RGB")
    elif pi in ("RGB", "YBR_FULL", "YBR_FULL_422") and img_u8.ndim == 3:
        pil = PILImage.fromarray(img_u8, "RGB")
    else:
        if img_u8.ndim == 3:
            img_u8 = img_u8[..., 0]
        pil = PILImage.fromarray(img_u8, "L").convert("RGB")

    buf = io.BytesIO()
    pil.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def extract_image(ds):
    try:
        pixel_array = ds.pixel_array
    except Exception as e:
        return None, str(e)

    try:
        arr = pixel_array
        if arr.ndim == 4:
            arr = arr[arr.shape[0] // 2]
        elif arr.ndim == 3 and arr.shape[0] > 4:
            arr = arr[arr.shape[0] // 2]

        return normalize_frame(arr, ds), None
    except Exception as e:
        return None, str(e)


def extract_all_frames(ds):
    """Return list of base64 PNG strings for every frame in the dataset."""
    try:
        pixel_array = ds.pixel_array
    except Exception as e:
        return [], str(e)

    try:
        arr = pixel_array
        frames = []

        # Multi-frame: (N, H, W) or (N, H, W, C)
        if arr.ndim == 4 or (arr.ndim == 3 and arr.shape[0] > 4):
            n = arr.shape[0]
            for i in range(n):
                frames.append(normalize_frame(arr[i], ds))
        else:
            # Single frame
            frames.append(normalize_frame(arr, ds))

        return frames, None
    except Exception as e:
        return [], str(e)


# ─── SUMMARY ─────────────────────────────────────────────────────────────────

def ga(ds, *kws):
    for kw in kws:
        try:
            v = getattr(ds, kw, None)
            if v is not None:
                s = safe_str(v)
                if s:
                    return s
        except Exception:
            pass
    return "—"


def fmt_date(d):
    d = d.strip()
    if len(d) == 8 and d.isdigit():
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return d


def build_summary(ds):
    bd = ga(ds, "PatientBirthDate")
    sd = ga(ds, "StudyDate")
    return {
        "patientName":  ga(ds, "PatientName"),
        "patientID":    ga(ds, "PatientID"),
        "patientDOB":   fmt_date(bd) if bd != "—" else "—",
        "patientSex":   ga(ds, "PatientSex"),
        "patientAge":   ga(ds, "PatientAge"),
        "modality":     ga(ds, "Modality"),
        "studyDate":    fmt_date(sd) if sd != "—" else "—",
        "studyDesc":    ga(ds, "StudyDescription"),
        "seriesDesc":   ga(ds, "SeriesDescription"),
        "institution":  ga(ds, "InstitutionName"),
        "rows":         ga(ds, "Rows"),
        "columns":      ga(ds, "Columns"),
        "frames":       ga(ds, "NumberOfFrames"),
        "sliceThick":   ga(ds, "SliceThickness"),
        "bodyPart":     ga(ds, "BodyPartExamined"),
        "manufacturer": ga(ds, "Manufacturer"),
        "model":        ga(ds, "ManufacturerModelName"),
        "heartRate":    ga(ds, "HeartRate"),
        "kvp":          ga(ds, "KVP"),
        "wc":           ga(ds, "WindowCenter"),
        "ww":           ga(ds, "WindowWidth"),
        "transferSyntax": ga(ds, "TransferSyntaxUID"),
    }


# ─── ROUTES ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/parse", methods=["POST"])
def api_parse():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    filepath = os.path.join(UPLOAD_FOLDER, f.filename)
    f.save(filepath)

    try:
        ds = dcmread(filepath, force=True)
    except Exception as e:
        return jsonify({"error": f"Cannot read DICOM: {e}"}), 400

    try:
        summary = build_summary(ds)
        tag_groups, total_tags = parse_dataset(ds)
        img_b64, img_err = extract_image(ds)
        return jsonify({
            "ok": True,
            "filename": f.filename,
            "summary": summary,
            "tagGroups": tag_groups,
            "totalTags": total_tags,
            "image": img_b64,
            "imageError": img_err,
        })
    except Exception as e:
        return jsonify({"error": f"Parse error: {e}\n{traceback.format_exc()}"}), 500


@app.route("/api/parse_series", methods=["POST"])
def api_parse_series():
    """
    Accept multiple DICOM files and return all frames as a flat ordered list.
    Each file contributes one or more frames (if multi-frame DICOM).
    Returns: { ok, totalFrames, frames: [{filename, frameIndex, image}], summary, tagGroups, totalTags }
    """
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files provided"}), 400

    all_frames = []
    first_summary = None
    first_tag_groups = None
    first_total_tags = 0
    errors = []

    for f in files:
        if not f.filename:
            continue
        filepath = os.path.join(UPLOAD_FOLDER, f.filename)
        f.save(filepath)

        try:
            ds = dcmread(filepath, force=True)
        except Exception as e:
            errors.append(f"{f.filename}: Cannot read — {e}")
            continue

        try:
            frames, frame_err = extract_all_frames(ds)
            if frame_err and not frames:
                errors.append(f"{f.filename}: {frame_err}")
                continue

            for idx, img_b64 in enumerate(frames):
                all_frames.append({
                    "filename": f.filename,
                    "frameIndex": idx,
                    "image": img_b64,
                })

            if first_summary is None:
                first_summary = build_summary(ds)
                first_tag_groups, first_total_tags = parse_dataset(ds)

        except Exception as e:
            errors.append(f"{f.filename}: {e}")

    if not all_frames:
        return jsonify({"error": "No frames could be extracted. " + "; ".join(errors)}), 400

    return jsonify({
        "ok": True,
        "totalFrames": len(all_frames),
        "frames": all_frames,
        "summary": first_summary,
        "tagGroups": first_tag_groups,
        "totalTags": first_total_tags,
        "errors": errors,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0")