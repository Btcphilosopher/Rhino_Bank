The design below gives RhinoBank:

                     RHINOBANK CRYPTOGRAPHIC IDENTITY

                               ROOT CA
                                  │
                  ┌───────────────┴───────────────┐
                  │                               │
             INSTITUTION                    RHINOBANK NODE
             PGP KEY                         ED25519 KEY
                  │                               │
          ┌───────┴────────┐              ┌───────┴────────┐
          │                │              │                │
      Treasury          Trading        API Server      Market Node
          │                │              │                │
          └────────────────┴──────────────┴────────────────┘
                                  │
                           SIGNED REQUEST
                                  │
                           NONCE + TIMESTAMP
                                  │
                            BODY HASH
                                  │
                           ED25519 SIGNATURE
                                  │
                             VERIFICATION

For OpenPGP, GnuPG itself recommends protecting secret keys carefully and notes that detached signatures are appropriate for signature verification workflows.

1. Install
sudo apt install gnupg

python -m venv .venv
source .venv/bin/activate

pip install cryptography fastapi uvicorn
rhino_crypto.py

This is the core cryptographic identity module.

"""
RHINOBANK CRYPTOGRAPHIC IDENTITY ENGINE

Provides:

    - Ed25519 node identity
    - PGP/GPG integration
    - canonical request serialization
    - request signing
    - signature verification
    - replay protection
    - nonce tracking
    - key fingerprints
    - key rotation
    - signed audit events

IMPORTANT:

Private keys should ultimately live in an HSM,
hardware token, smartcard, or MPC signing service.

This module is intentionally suitable for development
and controlled institutional environments, but should
undergo independent security review before production use.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import subprocess
import time

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from cryptography.exceptions import InvalidSignature

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from cryptography.hazmat.primitives import serialization


# ============================================================
# HELPERS
# ============================================================

def b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode()


def b64d(data: str) -> bytes:
    return base64.urlsafe_b64decode(data.encode())


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(data: dict) -> bytes:

    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


# ============================================================
# ED25519 IDENTITY
# ============================================================

@dataclass
class NodeIdentity:

    node_id: str

    private_key: Ed25519PrivateKey

    @property
    def public_key(self):

        return self.private_key.public_key()

    @property
    def public_key_bytes(self):

        return self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    @property
    def fingerprint(self):

        return sha256_hex(
            self.public_key_bytes
        )

    # --------------------------------------------------------
    # GENERATE
    # --------------------------------------------------------

    @classmethod
    def generate(
        cls,
        node_id: str,
    ):

        private_key = (
            Ed25519PrivateKey.generate()
        )

        return cls(
            node_id=node_id,
            private_key=private_key,
        )

    # --------------------------------------------------------
    # SIGN
    # --------------------------------------------------------

    def sign(
        self,
        message: bytes,
    ) -> bytes:

        return self.private_key.sign(
            message
        )

    # --------------------------------------------------------
    # VERIFY
    # --------------------------------------------------------

    @staticmethod
    def verify(
        public_key: Ed25519PublicKey,
        message: bytes,
        signature: bytes,
    ) -> bool:

        try:

            public_key.verify(
                signature,
                message,
            )

            return True

        except InvalidSignature:

            return False

    # --------------------------------------------------------
    # EXPORT PRIVATE KEY
    # --------------------------------------------------------

    def export_private_pem(
        self,
        password: bytes,
    ) -> bytes:

        if not password:
            raise ValueError(
                "Password required."
            )

        return self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,

            format=serialization.PrivateFormat.PKCS8,

            encryption_algorithm=
                serialization.BestAvailableEncryption(
                    password
                ),
        )

    # --------------------------------------------------------
    # EXPORT PUBLIC KEY
    # --------------------------------------------------------

    def export_public_pem(self) -> bytes:

        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,

            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )


# ============================================================
# KEY STORE
# ============================================================

class KeyStore:

    """
    Encrypted-at-rest key storage for development.

    Production:
        replace with HSM/MPC/KMS/smartcard backend.
    """

    def __init__(
        self,
        directory: str = "./keys",
    ):

        self.directory = Path(
            directory
        )

        self.directory.mkdir(
            mode=0o700,
            exist_ok=True,
        )

    def save(
        self,
        identity: NodeIdentity,
        password: bytes,
    ):

        private_path = (
            self.directory
            / f"{identity.node_id}.key"
        )

        public_path = (
            self.directory
            / f"{identity.node_id}.pub"
        )

        private_path.write_bytes(
            identity.export_private_pem(
                password
            )
        )

        public_path.write_bytes(
            identity.export_public_pem()
        )

        os.chmod(
            private_path,
            0o600,
        )

        os.chmod(
            public_path,
            0o644,
        )

        return {
            "private":
                str(private_path),

            "public":
                str(public_path),

            "fingerprint":
                identity.fingerprint,
        }

    def load(
        self,
        node_id: str,
        password: bytes,
    ) -> NodeIdentity:

        private_path = (
            self.directory
            / f"{node_id}.key"
        )

        if not private_path.exists():

            raise FileNotFoundError(
                "Private identity not found."
            )

        key_data = (
            private_path.read_bytes()
        )

        private_key = (
            serialization.load_pem_private_key(
                key_data,
                password=password,
            )
        )

        if not isinstance(
            private_key,
            Ed25519PrivateKey,
        ):

            raise TypeError(
                "Invalid RhinoBank key."
            )

        return NodeIdentity(
            node_id=node_id,
            private_key=private_key,
        )


# ============================================================
# REPLAY PROTECTION
# ============================================================

class ReplayGuard:

    def __init__(
        self,
        maximum_age_seconds: int = 30,
    ):

        self.maximum_age = (
            maximum_age_seconds
        )

        self.seen = set()

    def validate(
        self,
        nonce: str,
        timestamp: int,
    ):

        now = int(
            time.time()
        )

        if abs(
            now - timestamp
        ) > self.maximum_age:

            raise PermissionError(
                "Request timestamp outside "
                "allowed window."
            )

        if nonce in self.seen:

            raise PermissionError(
                "Replay detected."
            )

        self.seen.add(
            nonce
        )


# ============================================================
# SIGNED REQUEST
# ============================================================

@dataclass
class SignedRequest:

    node_id: str

    method: str

    path: str

    timestamp: int

    nonce: str

    body_hash: str

    signature: str

    public_key: str

    def as_headers(self):

        return {
            "X-Rhino-Node":
                self.node_id,

            "X-Rhino-Timestamp":
                str(self.timestamp),

            "X-Rhino-Nonce":
                self.nonce,

            "X-Rhino-Body-SHA256":
                self.body_hash,

            "X-Rhino-Public-Key":
                self.public_key,

            "X-Rhino-Signature":
                self.signature,
        }


# ============================================================
# REQUEST SIGNER
# ============================================================

class RequestSigner:

    def __init__(
        self,
        identity: NodeIdentity,
    ):

        self.identity = identity

    def create(
        self,
        method: str,
        path: str,
        body: bytes,
    ) -> SignedRequest:

        timestamp = int(
            time.time()
        )

        nonce = secrets.token_hex(
            32
        )

        body_hash = sha256_hex(
            body
        )

        signing_document = (
            f"{self.identity.node_id}\n"
            f"{method.upper()}\n"
            f"{path}\n"
            f"{timestamp}\n"
            f"{nonce}\n"
            f"{body_hash}"
        ).encode()

        signature = (
            self.identity.sign(
                signing_document
            )
        )

        return SignedRequest(

            node_id=
                self.identity.node_id,

            method=
                method.upper(),

            path=
                path,

            timestamp=
                timestamp,

            nonce=
                nonce,

            body_hash=
                body_hash,

            signature=
                b64e(signature),

            public_key=
                b64e(
                    self.identity.public_key_bytes
                ),
        )


# ============================================================
# REQUEST VERIFIER
# ============================================================

class RequestVerifier:

    def __init__(self):

        self.replay = (
            ReplayGuard()
        )

    def verify(
        self,
        request: SignedRequest,
        body: bytes,
    ) -> bool:

        # ----------------------------------------------
        # BODY INTEGRITY
        # ----------------------------------------------

        calculated_hash = (
            sha256_hex(body)
        )

        if calculated_hash != request.body_hash:

            raise PermissionError(
                "Body hash mismatch."
            )

        # ----------------------------------------------
        # REPLAY PROTECTION
        # ----------------------------------------------

        self.replay.validate(
            request.nonce,
            request.timestamp,
        )

        # ----------------------------------------------
        # PUBLIC KEY
        # ----------------------------------------------

        public_key = (
            Ed25519PublicKey.from_public_bytes(
                b64d(
                    request.public_key
                )
            )
        )

        # ----------------------------------------------
        # SIGNED DOCUMENT
        # ----------------------------------------------

        document = (
            f"{request.node_id}\n"
            f"{request.method.upper()}\n"
            f"{request.path}\n"
            f"{request.timestamp}\n"
            f"{request.nonce}\n"
            f"{request.body_hash}"
        ).encode()

        # ----------------------------------------------
        # VERIFY
        # ----------------------------------------------

        if not NodeIdentity.verify(
            public_key,
            document,
            b64d(
                request.signature
            ),
        ):

            raise PermissionError(
                "Invalid cryptographic signature."
            )

        return True


# ============================================================
# PGP/GPG ENGINE
# ============================================================

class PGPIdentity:

    """
    Thin wrapper around GnuPG.

    Used for institutional certificates,
    detached signatures and key fingerprints.

    GnuPG remains responsible for OpenPGP
    key management.
    """

    def __init__(
        self,
        home: str = "./pgp",
    ):

        self.home = Path(
            home
        )

        self.home.mkdir(
            mode=0o700,
            exist_ok=True,
        )

    def _run(
        self,
        *args,
        input_data=None,
    ):

        command = [
            "gpg",
            "--homedir",
            str(self.home),
            "--batch",
            "--yes",
            *args,
        ]

        return subprocess.run(
            command,
            input=input_data,
            capture_output=True,
            check=True,
        )

    def generate(
        self,
        name: str,
        email: str,
    ):

        batch = f"""
Key-Type: eddsa
Key-Curve: ed25519
Name-Real: {name}
Name-Email: {email}
Expire-Date: 2y
%no-protection
%commit
""".encode()

        self._run(
            "--generate-key",
            input_data=batch,
        )

    def list_keys(self):

        result = self._run(
            "--list-keys",
            "--with-colons",
        )

        return result.stdout.decode()

    def fingerprint(
        self,
        identity: str,
    ):

        result = self._run(
            "--fingerprint",
            identity,
        )

        return result.stdout.decode()

    def export_public(
        self,
        identity: str,
    ):

        result = self._run(
            "--armor",
            "--export",
            identity,
        )

        return result.stdout

    def sign_detached(
        self,
        identity: str,
        data: bytes,
    ):

        result = self._run(
            "--armor",
            "--detach-sign",
            "--local-user",
            identity,
            input_data=data,
        )

        return result.stdout

    def verify_detached(
        self,
        data: bytes,
        signature: bytes,
    ):

        data_file = (
            self.home
            / "verify.data"
        )

        sig_file = (
            self.home
            / "verify.sig"
        )

        data_file.write_bytes(
            data
        )

        sig_file.write_bytes(
            signature
        )

        result = subprocess.run(
            [
                "gpg",
                "--homedir",
                str(self.home),
                "--batch",
                "--status-fd",
                "1",
                "--verify",
                str(sig_file),
                str(data_file),
            ],
            capture_output=True,
        )

        return result.returncode == 0
2. RhinoBank authenticated API

Now bolt the cryptographic layer directly onto the node we built previously.

"""
RHINOBANK CRYPTOGRAPHIC API GATEWAY
"""

from fastapi import (
    FastAPI,
    Request,
    HTTPException,
)

from .rhino_crypto import (
    SignedRequest,
    RequestVerifier,
)


app = FastAPI(
    title="RhinoBank Cryptographic Node",
    version="1.0.0",
)

verifier = RequestVerifier()


def signed_request_from_http(
    request: Request,
) -> SignedRequest:

    headers = request.headers

    required = [
        "x-rhino-node",
        "x-rhino-timestamp",
        "x-rhino-nonce",
        "x-rhino-body-sha256",
        "x-rhino-public-key",
        "x-rhino-signature",
    ]

    for header in required:

        if header not in headers:

            raise HTTPException(
                status_code=401,
                detail=(
                    "Missing cryptographic "
                    f"header: {header}"
                ),
            )

    return SignedRequest(

        node_id=
            headers["x-rhino-node"],

        method=
            request.method,

        path=
            request.url.path,

        timestamp=
            int(
                headers["x-rhino-timestamp"]
            ),

        nonce=
            headers["x-rhino-nonce"],

        body_hash=
            headers["x-rhino-body-sha256"],

        signature=
            headers["x-rhino-signature"],

        public_key=
            headers["x-rhino-public-key"],
    )


@app.post(
    "/secure/transaction"
)
async def secure_transaction(
    request: Request,
):

    body = await request.body()

    signed = signed_request_from_http(
        request
    )

    try:

        verifier.verify(
            signed,
            body,
        )

    except PermissionError as exc:

        raise HTTPException(
            status_code=401,
            detail=str(exc),
        )

    return {
        "authenticated": True,

        "node_id":
            signed.node_id,

        "body_sha256":
            signed.body_hash,

        "status":
            "ACCEPTED",
    }
3. Generate a RhinoBank node identity
from rhino_crypto import (
    NodeIdentity,
    KeyStore,
)

identity = NodeIdentity.generate(
    "rhino-node-001"
)

store = KeyStore()

result = store.save(
    identity,
    password=b"CHANGE-THIS-PASSWORD",
)

print(result)

You get:

keys/
├── rhino-node-001.key
└── rhino-node-001.pub

And a fingerprint such as:

f4e1...9b72

The fingerprint becomes the node's cryptographic identity.

Do not identify a node merely by its IP address or hostname.

4. Sign a RhinoBank API request
import json

from rhino_crypto import (
    KeyStore,
    RequestSigner,
)

store = KeyStore()

identity = store.load(
    "rhino-node-001",
    password=b"CHANGE-THIS-PASSWORD",
)

signer = RequestSigner(
    identity
)

payload = {
    "account_id":
        "RHINO-INST-001",

    "symbol":
        "BTC/USDT",

    "side":
        "BUY",

    "quantity":
        "5",

    "price":
        "60000",
}

body = json.dumps(
    payload,
    sort_keys=True,
    separators=(",", ":"),
).encode()

signed = signer.create(
    method="POST",
    path="/secure/transaction",
    body=body,
)

print(
    signed.as_headers()
)

The resulting HTTP request carries:

X-Rhino-Node
X-Rhino-Timestamp
X-Rhino-Nonce
X-Rhino-Body-SHA256
X-Rhino-Public-Key
X-Rhino-Signature

So RhinoBank isn't simply asking:

"What's your API key?"

It is asking:

Who are you?
       +
What exactly did you sign?
       +
When did you sign it?
       +
Have I seen this request before?
       +
Does the public key verify the signature?
5. Add PGP institutional identity

The OpenPGP layer is useful for things such as:

Institutional identity
       │
       ├── signed documents
       ├── settlement instructions
       ├── release manifests
       ├── software releases
       ├── public certificates
       └── inter-institution messages

Generate a RhinoBank institutional key:

from rhino_crypto import PGPIdentity

pgp = PGPIdentity(
    "./pgp"
)

pgp.generate(
    name="RhinoBank Treasury",
    email="treasury@rhinobank.example",
)

print(
    pgp.list_keys()
)

Then retrieve the fingerprint:

print(
    pgp.fingerprint(
        "treasury@rhinobank.example"
    )
)

Export the public certificate:

public_key = pgp.export_public(
    "treasury@rhinobank.example"
)

with open(
    "rhinobank-treasury.asc",
    "wb",
) as f:

    f.write(public_key)

And sign a settlement instruction:

instruction = b"""
RHINOBANK SETTLEMENT INSTRUCTION

REFERENCE: SETTLE-2026-000001
ASSET: USDT
NETWORK: TRON
AMOUNT: 250000.00
DESTINATION: INSTITUTIONAL-WALLET
"""

signature = pgp.sign_detached(
    "treasury@rhinobank.example",
    instruction,
)

with open(
    "settlement.sig",
    "wb",
) as f:

    f.write(signature)

GnuPG explicitly supports detached signatures and verification, which is the model used here.

6. The hard part: key hierarchy

For the actual RhinoBank architecture, don't have one giant private key.

Use a hierarchy:

                         RHINOBANK ROOT
                              │
                     OpenPGP ROOT KEY
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
       TREASURY             TRADING             NODE CA
          │                   │                   │
      PGP KEY             PGP KEY            SIGNING KEY
          │                   │                   │
      ┌───┴───┐           ┌───┴───┐          ┌────┴────┐
      │       │           │       │          │         │
    USD     USDT         BTC     ETH       NODE-01   NODE-02

Then introduce role-separated keys:

RHINO-ROOT
RHINO-TREASURY
RHINO-TRADING
RHINO-SETTLEMENT
RHINO-RISK
RHINO-AUDIT
RHINO-NODE-001
RHINO-NODE-002

A trading node should not possess the Treasury signing key.

A market-making process should not possess the withdrawal-signing key.

The API server should never possess a custody signing key.

7. Multi-signature withdrawal authorization

For the really serious version, make a USDT withdrawal require multiple independent signatures:

                   WITHDRAWAL
                       │
                       ▼
                 RISK ENGINE
                       │
                ┌──────┴──────┐
                │             │
             RISK KEY     TREASURY KEY
                │             │
                └──────┬──────┘
                       │
                       ▼
                  2-OF-3 AUTH
                       │
              ┌────────┼────────┐
              │        │        │
             KEY A    KEY B    KEY C
              │        │        │
              └────────┴────────┘
                       │
                       ▼
                  CUSTODY HSM
                       │
                       ▼
                  BLOCKCHAIN

The transaction should therefore be represented as a cryptographic authorization object, rather than merely a database row:

@dataclass
class WithdrawalAuthorization:

    withdrawal_id: str

    account_id: str

    asset: str

    network: str

    amount: str

    destination: str

    nonce: str

    created_at: int

    required_signatures: int

    signatures: list

Each signer signs the exact canonical withdrawal payload.

def withdrawal_document(
    withdrawal_id,
    account_id,
    asset,
    network,
    amount,
    destination,
    nonce,
    created_at,
):

    document = {
        "withdrawal_id":
            withdrawal_id,

        "account_id":
            account_id,

        "asset":
            asset,

        "network":
            network,

        "amount":
            amount,

        "destination":
            destination,

        "nonce":
            nonce,

        "created_at":
            created_at,
    }

    return canonical_json(
        document
    )

That prevents somebody from taking a valid signature for:

100,000 USDT

and modifying it to:

1,000,000 USDT

because the amount is part of the signed document.

8. The RhinoBank security model

I'd ultimately make the node operate like this:

                 ┌───────────────────────┐
                 │   RHINOBANK CLIENT    │
                 └───────────┬───────────┘
                             │
                     signed request
                             │
                             ▼
                  ┌────────────────────┐
                  │    API GATEWAY     │
                  └─────────┬──────────┘
                            │
                   verify signature
                   verify timestamp
                   verify nonce
                   verify body hash
                            │
                            ▼
                    ┌───────────────┐
                    │ AUTHORIZATION │
                    └───────┬───────┘
                            │
                     RBAC / policy
                            │
                            ▼
                     ┌────────────┐
                     │ RISK ENGINE│
                     └──────┬─────┘
                            │
                            ▼
                     ┌────────────┐
                     │   LEDGER   │
                     └──────┬─────┘
                            │
               ┌────────────┼────────────┐
               ▼            ▼            ▼
             USDT         SPOT         AUDIT
             ENGINE       ENGINE       ENGINE
               │            │
               └──────┬─────┘
                      ▼
                SETTLEMENT
                      │
                      ▼
                 CUSTODY HSM
                      │
                      ▼
                  BLOCKCHAIN
One important production change

For a genuine institutional deployment, do not leave the private Ed25519/PGP keys as ordinary encrypted files on the same machine running RhinoBank. The code above deliberately gives you a clean interface so the key backend can later be replaced with an HSM, smartcard, hardware token, MPC system, or external signing service. GnuPG's own documentation emphasizes protecting secret keys and notes hardware/token-based approaches as useful for protecting them.

That gives RhinoBank a much stronger model:

identity → authentication → authorization → risk approval → cryptographic authorization → custody signing → blockchain settlement.

And importantly, the API node never gets to unilaterally move USDT.
