"""M26.19: independently replay a derived CSV against immutable originals.

A derived channel must never be passed off as an original instrument file.
Replays the deterministic conversion, compares every exported byte and the
exact sidecar, and rejects self-declared physical validation fields.
"""
from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
from pathlib import Path

from physics.validation.flight_explicit_csv_conversion import (
    derive_original_vendor_csv_bytes,
)


def _unique_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate provenance JSON key forbidden")
        obj[key] = value
    return obj


def replay_derived_flight_csv(
    root, manifest, *, derived_csv_path: str | Path,
    provenance_json_path: str | Path,
) -> dict:
    """Verify normalized data and sidecar are *exactly* reproducible."""
    base = Path(root).resolve(strict=True)
    csv_path, sidecar = Path(derived_csv_path), Path(provenance_json_path)
    if (csv_path.is_symlink() or sidecar.is_symlink()
            or not csv_path.is_file() or not sidecar.is_file()):
        raise ValueError("derived CSV and provenance must exist as regular non-symlink files")
    output_path, metadata_path = csv_path.resolve(strict=True), sidecar.resolve(strict=True)
    if (output_path == metadata_path or output_path.is_relative_to(base)
            or metadata_path.is_relative_to(base)):
        raise ValueError("derived file and provenance must be separate and outside original root")
    if (output_path.suffix.lower() != ".csv" or metadata_path.suffix.lower() != ".json"
            or output_path.stat().st_size > 8_000_000
            or not 0 < metadata_path.stat().st_size <= 200_000):
        raise ValueError("unsupported or unbounded derived CSV/provenance")
    try:
        sidecar_obj = json.loads(
            metadata_path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_keys,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid source-derived provenance JSON") from exc
    if not isinstance(sidecar_obj, Mapping) or not isinstance(sidecar_obj.get("transformation_spec"), Mapping):
        raise ValueError("exact derived transformation spec and evidence sidecar required")
    original_bytes, expected_provenance = derive_original_vendor_csv_bytes(
        root, manifest, mapping=sidecar_obj["transformation_spec"],
    )
    if sidecar_obj != expected_provenance:
        raise ValueError("derived provenance differs from recomputed original-source transformation")
    observed_bytes = output_path.read_bytes()
    if observed_bytes != original_bytes or sha256(observed_bytes).hexdigest() != expected_provenance["derived_csv_sha256"]:
        raise ValueError("derived CSV byte content is not reproducible from immutable originals")
    return {
        "status": "SOURCE_LINKED_DERIVED_CSV_REPLAY_EXACT_NOT_PHYSICAL_VALIDATION",
        "original_source_sha256": expected_provenance["original_sha256"],
        "derived_csv_sha256": expected_provenance["derived_csv_sha256"],
        "conversion_spec_sha256": expected_provenance["transformation_spec_sha256"],
        "derived_sample_count": expected_provenance["derived_sample_count"],
        "same_original_bytes_and_transformation_reproduced": True,
        "original_instrument_source_custody_authenticated": False,
        "source_units_and_calibration_independently_verified": False,
        "derived_file_may_be_misrepresented_as_original": False,
        "physical_prediction_accuracy_established": False,
        "flight_release_authorized": False,
    }
