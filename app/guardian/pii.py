import re
from dataclasses import asdict, dataclass
from typing import Any

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_RE = re.compile(r"(?:\+33|0)[1-9](?:[\s.-]?\d{2}){4}")
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
NIR_RE = re.compile(r"\b[12]\d{2}(?:0[1-9]|1[0-2])\d{2}\d{3}\d{3}\d{2}\b")

SENSITIVE_COLUMN_NAMES = frozenset(
    {
        "email",
        "e_mail",
        "mail",
        "telephone",
        "phone",
        "mobile",
        "iban",
        "account_number",
        "numero_compte",
        "nom",
        "prenom",
        "firstname",
        "lastname",
        "name",
        "adresse",
        "address",
        "ssn",
        "nir",
        "date_naissance",
        "birth_date",
    }
)

PII_TYPE_LABELS = {
    "email": "Adresse e-mail",
    "phone": "Numéro de téléphone",
    "iban": "IBAN",
    "card": "Numéro de carte bancaire",
    "nir": "Identifiant national (NIR)",
    "sensitive_column": "Colonne sensible",
}


@dataclass
class PIIFinding:
    pii_type: str
    path: str
    sample: str
    masked_sample: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _mask_value(value: str, pii_type: str) -> str:
    if len(value) <= 4:
        return "****"
    if pii_type == "email" and "@" in value:
        local, domain = value.split("@", 1)
        return f"{local[:2]}***@{domain[:2]}***"
    return value[:2] + "*" * min(8, len(value) - 4) + value[-2:]


def scan_text(text: str, path: str = "$") -> list[PIIFinding]:
    findings: list[PIIFinding] = []
    patterns = [
        ("email", EMAIL_RE),
        ("phone", PHONE_RE),
        ("iban", IBAN_RE),
        ("card", CARD_RE),
        ("nir", NIR_RE),
    ]
    for pii_type, pattern in patterns:
        for match in pattern.finditer(text):
            sample = match.group(0)
            findings.append(
                PIIFinding(
                    pii_type=pii_type,
                    path=path,
                    sample=sample,
                    masked_sample=_mask_value(sample, pii_type),
                )
            )
    return findings


def scan_structure(obj: Any, path: str = "$") -> list[PIIFinding]:
    findings: list[PIIFinding] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            child_path = f"{path}.{key}"
            if str(key).lower() in SENSITIVE_COLUMN_NAMES and isinstance(value, str) and value.strip():
                findings.append(
                    PIIFinding(
                        pii_type="sensitive_column",
                        path=child_path,
                        sample=value[:80],
                        masked_sample=_mask_value(value, "sensitive_column"),
                    )
                )
            findings.extend(scan_structure(value, child_path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            findings.extend(scan_structure(item, f"{path}[{i}]"))
    elif isinstance(obj, str) and obj.strip():
        findings.extend(scan_text(obj, path))
    return findings


def mask_structure(obj: Any) -> tuple[Any, list[dict[str, str]]]:
    findings = scan_structure(obj)
    if not findings:
        return obj, []

    def _mask(obj: Any, current_path: str = "$") -> Any:
        if isinstance(obj, dict):
            return {k: _mask(v, f"{current_path}.{k}") for k, v in obj.items()}
        if isinstance(obj, list):
            return [_mask(item, f"{current_path}[{i}]") for i, item in enumerate(obj)]
        if isinstance(obj, str):
            masked = obj
            for f in findings:
                if f.path == current_path or (f.path.startswith(current_path) and f.sample in masked):
                    masked = masked.replace(f.sample, f.masked_sample)
            for pii_type, pattern in [
                ("email", EMAIL_RE),
                ("phone", PHONE_RE),
                ("iban", IBAN_RE),
                ("card", CARD_RE),
                ("nir", NIR_RE),
            ]:
                masked = pattern.sub(lambda m, t=pii_type: _mask_value(m.group(0), t), masked)
            return masked
        return obj

    return _mask(obj), [f.to_dict() for f in findings]


def findings_summary(findings: list[dict[str, str]]) -> str:
    if not findings:
        return "Aucune donnée personnelle détectée."
    by_type: dict[str, int] = {}
    for f in findings:
        label = PII_TYPE_LABELS.get(f.get("pii_type", ""), f.get("pii_type", "PII"))
        by_type[label] = by_type.get(label, 0) + 1
    parts = [f"- **{label}** : {count} occurrence(s)" for label, count in by_type.items()]
    return "Données personnelles détectées (RGPD) :\n" + "\n".join(parts)
