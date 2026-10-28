"""Check pip's bundled CA file for two relevant eMudhra trust anchors."""

from __future__ import annotations

import hashlib
import ssl
from pathlib import Path

# https://emudhra.we-have-a-problem.com/roots.json (emSign ECC Root CA - G3)
BLOCKED_ROOT_SHA256 = "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b"
# The AAA root can anchor cross-signed paths; its presence alone is not proof of compromise.
AAA_ROOT_SHA256 = "d7a7a0fb5d7e2731d771e9484ebcdef71d5f0c3e0a2948782bc83ee0ea699ef4"


def check_bundle(path: Path) -> int:
    """Return the number of roots or fail if the named bundle is unusable or affected."""
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cafile=str(path))
        certs = context.get_ca_certs(binary_form=True)
    except (OSError, ssl.SSLError) as exc:
        raise ValueError(f"Unable to load CA bundle {path}: {exc}") from exc
    if not certs:
        raise ValueError(f"CA bundle {path} contains no usable CA certificates")
    fingerprints = {hashlib.sha256(cert).hexdigest() for cert in certs}
    if BLOCKED_ROOT_SHA256 in fingerprints:
        raise ValueError(f"CA bundle {path} contains emSign ECC Root CA - G3")
    if AAA_ROOT_SHA256 in fingerprints:
        raise ValueError(
            f"CA bundle {path} contains AAA Certificate Services; "
            "cross-signed paths require separate verification"
        )
    return len(certs)


def main() -> None:
    from pip._vendor import certifi

    path = Path(certifi.where())
    count = check_bundle(path)
    print(
        f"pip bundled certifi {certifi.__version__}: {path} ({count} CA certificates)"
    )
    print("emSign ECC Root CA - G3: absent from this bundle")
    print("AAA Certificate Services: absent from this bundle")
    print("Other trust stores and certificate chains were not checked")


if __name__ == "__main__":
    main()
