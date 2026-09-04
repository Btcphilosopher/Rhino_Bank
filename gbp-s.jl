A sensible design for a Rhino-style GBP stablecoin wallet would be:

┌──────────────────────────────────────────────┐
│              CHROME EXTENSION                │
│                                              │
│  Popup / Side Panel                          │
│  ├── £GBPX Balance                           │
│  ├── Send / Receive                          │
│  ├── Transaction history                     │
│  ├── Network selector                        │
│  └── Wallet lock                             │
│                 │                            │
│          JavaScript wallet core              │
│                 │                            │
│       ┌─────────┴─────────┐                  │
│       │                   │                  │
│   EVM Provider        Julia API              │
│   / RPC Layer         Engine                 │
│                           │                  │
│                  ┌────────┴────────┐         │
│                  │                 │         │
│              Risk Engine       Price/FX      │
│              Limits           Engine         │
│                  │                 │         │
│                  └────────┬────────┘         │
│                           │                  │
│                    Blockchain RPC            │
└──────────────────────────────────────────────┘

Below is a working prototype architecture, deliberately using a configurable ERC-20 contract rather than pretending that a particular GBP stablecoin contract exists.

1. Project structure
gbp-wallet/
│
├── extension/
│   ├── manifest.json
│   ├── popup.html
│   ├── popup.css
│   ├── popup.js
│   ├── background.js
│   ├── wallet.js
│   ├── crypto.js
│   ├── rpc.js
│   └── icons/
│
├── julia/
│   ├── Project.toml
│   ├── server.jl
│   ├── wallet_engine.jl
│   ├── risk_engine.jl
│   ├── pricing.jl
│   └── models.jl
│
└── README.md
2. Chrome manifest.json
{
  "manifest_version": 3,
  "name": "GBP Stablecoin Wallet",
  "version": "0.1.0",
  "description": "A non-custodial GBP stablecoin wallet.",
  "permissions": [
    "storage"
  ],
  "action": {
    "default_title": "GBP Wallet",
    "default_popup": "popup.html"
  },
  "background": {
    "service_worker": "background.js",
    "type": "module"
  },
  "side_panel": {
    "default_path": "popup.html"
  },
  "host_permissions": [
    "https://*.infura.io/*",
    "https://*.alchemy.com/*"
  ]
}

Manifest V3 is the appropriate foundation for a modern Chrome extension.

3. Wallet cryptography — crypto.js

For a production wallet, don't invent cryptography. Use audited libraries such as ethers or equivalent and isolate private-key operations.

Prototype:

export class WalletVault {

    constructor() {
        this.storageKey = "gbp_wallet_vault";
    }

    async initialise() {

        const existing =
            await chrome.storage.local.get(this.storageKey);

        if (existing[this.storageKey]) {
            return JSON.parse(existing[this.storageKey]);
        }

        return null;
    }

    async saveEncryptedVault(vault) {

        await chrome.storage.local.set({
            [this.storageKey]: JSON.stringify(vault)
        });
    }

    async deleteVault() {

        await chrome.storage.local.remove(this.storageKey);
    }

    async lock() {

        sessionStorage.removeItem("unlocked_wallet");
    }

    async unlock(wallet) {

        sessionStorage.setItem(
            "unlocked_wallet",
            JSON.stringify(wallet)
        );

        return wallet;
    }

    getUnlockedWallet() {

        const raw =
            sessionStorage.getItem("unlocked_wallet");

        if (!raw)
            return null;

        return JSON.parse(raw);
    }
}

Important: this is deliberately not production-grade key storage. A real wallet should encrypt key material using a user-derived secret, avoid keeping raw private keys in persistent Chrome storage, use secure memory handling where possible, and undergo an independent security audit.

Chrome provides extension storage APIs, but chrome.storage should not be treated as a hardware-wallet equivalent.

4. Blockchain RPC layer — rpc.js
export class EthereumRPC {

    constructor(rpcUrl) {
        this.rpcUrl = rpcUrl;
        this.id = 1;
    }

    async call(method, params = []) {

        const response = await fetch(this.rpcUrl, {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                jsonrpc: "2.0",
                id: this.id++,
                method,
                params
            })
        });

        if (!response.ok) {
            throw new Error(
                `RPC HTTP error ${response.status}`
            );
        }

        const result = await response.json();

        if (result.error) {
            throw new Error(result.error.message);
        }

        return result.result;
    }

    async getBalance(address) {

        return await this.call(
            "eth_getBalance",
            [address, "latest"]
        );
    }

    async getBlockNumber() {

        return await this.call(
            "eth_blockNumber"
        );
    }

    async sendRawTransaction(rawTx) {

        return await this.call(
            "eth_sendRawTransaction",
            [rawTx]
        );
    }
}
5. GBP stablecoin interface

Suppose the stablecoin is an ERC-20 token:

Symbol: GBPX
Decimals: 18

1 GBPX ≈ £1.00

The extension should not hard-code the token contract.

export const GBP_STABLECOIN = {

    symbol: "GBPX",

    decimals: 18,

    contract: "0xYOUR_CONTRACT_ADDRESS",

    chainId: 1,

    name: "GBP Stablecoin"
};

That makes the wallet usable with a legitimate GBP stablecoin contract later.

6. ERC-20 ABI
export const ERC20_ABI = [

    {
        name: "balanceOf",
        type: "function",
        stateMutability: "view",
        inputs: [
            {
                name: "account",
                type: "address"
            }
        ],
        outputs: [
            {
                name: "",
                type: "uint256"
            }
        ]
    },

    {
        name: "transfer",
        type: "function",
        stateMutability: "nonpayable",
        inputs: [
            {
                name: "recipient",
                type: "address"
            },
            {
                name: "amount",
                type: "uint256"
            }
        ],
        outputs: [
            {
                name: "",
                type: "bool"
            }
        ]
    },

    {
        name: "decimals",
        type: "function",
        stateMutability: "view",
        inputs: [],
        outputs: [
            {
                name: "",
                type: "uint8"
            }
        ]
    },

    {
        name: "symbol",
        type: "function",
        stateMutability: "view",
        inputs: [],
        outputs: [
            {
                name: "",
                type: "string"
            }
        ]
    }
];
7. Julia financial engine

This is where Julia becomes particularly useful.

models.jl
struct Wallet
    address::String
    network::String
end

struct Transaction
    id::String
    from::String
    to::String
    asset::String
    amount::Float64
    fee_gbp::Float64
    timestamp::DateTime
    status::String
end

struct RiskResult
    approved::Bool
    reason::String
    risk_score::Float64
end
8. Julia risk engine
module RiskEngine

export assess_transaction

function assess_transaction(
    amount_gbp::Float64,
    daily_volume::Float64,
    destination::String
)

    if amount_gbp <= 0
        return (
            approved = false,
            reason = "Invalid amount",
            risk_score = 1.0
        )
    end

    if amount_gbp > 10000
        return (
            approved = false,
            reason = "Transaction exceeds prototype limit",
            risk_score = 0.90
        )
    end

    if daily_volume + amount_gbp > 25000
        return (
            approved = false,
            reason = "Daily volume limit exceeded",
            risk_score = 0.80
        )
    end

    if !startswith(lowercase(destination), "0x")
        return (
            approved = false,
            reason = "Invalid EVM address",
            risk_score = 1.0
        )
    end

    return (
        approved = true,
        reason = "Approved",
        risk_score = 0.01
    )
end

end

This gives you a place to eventually implement:

transaction limits
velocity monitoring
address reputation
sanctions screening
AML integration
fraud scoring
gas estimation
institutional limits
treasury rules
multi-signature policies
9. Julia GBP pricing engine
module PricingEngine

export gbp_value

function gbp_value(
    token_amount::Float64,
    gbp_reference_price::Float64
)

    return token_amount * gbp_reference_price
end

function deviation(
    market_price::Float64,
    target_price::Float64 = 1.0
)

    return abs(market_price - target_price) /
           target_price
end

end

For a stablecoin:

gbp_value(1250.50, 1.0)

returns approximately:

£1,250.50
10. Julia API

Using HTTP + JSON:

server.jl
using HTTP
using JSON3

include("wallet_engine.jl")
include("risk_engine.jl")
include("pricing.jl")

const PORT = 8080

function json_response(data, status=200)

    return HTTP.Response(
        status,
        [
            "Content-Type" => "application/json",
            "Access-Control-Allow-Origin" => "*"
        ],
        JSON3.write(data)
    )
end

function router(req)

    path = String(req.target)

    if path == "/health"

        return json_response(Dict(
            "status" => "ok",
            "service" => "GBP Wallet Engine",
            "version" => "0.1.0"
        ))

    elseif path == "/risk"

        body = JSON3.read(String(req.body))

        amount =
            Float64(body.amount)

        daily =
            Float64(body.daily_volume)

        destination =
            String(body.destination)

        result =
            RiskEngine.assess_transaction(
                amount,
                daily,
                destination
            )

        return json_response(result)

    elseif path == "/price"

        body = JSON3.read(String(req.body))

        amount =
            Float64(body.amount)

        price =
            Float64(body.price)

        value =
            PricingEngine.gbp_value(
                amount,
                price
            )

        return json_response(Dict(
            "token_amount" => amount,
            "gbp_price" => price,
            "gbp_value" => value
        ))

    end

    return json_response(
        Dict("error" => "Not found"),
        404
    )
end

HTTP.serve(router, "127.0.0.1", PORT)
11. Popup UI
popup.html
<!DOCTYPE html>

<html>

<head>

    <meta charset="UTF-8">

    <title>GBP Wallet</title>

    <link rel="stylesheet" href="popup.css">

</head>

<body>

<div class="wallet">

    <header>

        <div>
            <h1>GBP Wallet</h1>
            <span id="network">Ethereum</span>
        </div>

        <button id="settings">
            ⚙
        </button>

    </header>


    <section class="balance">

        <span class="label">
            GBP Stablecoin
        </span>

        <div id="balance">
            £0.00
        </div>

        <span id="tokenBalance">
            0 GBPX
        </span>

    </section>


    <section class="address">

        <span>Your wallet</span>

        <code id="address">
            Not connected
        </code>

        <button id="copyAddress">
            Copy
        </button>

    </section>


    <div class="actions">

        <button id="send">
            Send
        </button>

        <button id="receive">
            Receive
        </button>

    </div>


    <section class="transactions">

        <h2>Activity</h2>

        <div id="transactionList">

            <div class="empty">
                No transactions
            </div>

        </div>

    </section>

</div>

<script type="module" src="popup.js"></script>

</body>

</html>
12. Popup JavaScript
import { WalletVault } from "./crypto.js";

const vault = new WalletVault();

const balanceElement =
    document.getElementById("balance");

const tokenElement =
    document.getElementById("tokenBalance");

const addressElement =
    document.getElementById("address");


async function initialise() {

    const wallet =
        await vault.initialise();

    if (!wallet) {

        balanceElement.textContent =
            "£0.00";

        tokenElement.textContent =
            "0 GBPX";

        addressElement.textContent =
            "Create wallet";

        return;
    }

    addressElement.textContent =
        shortenAddress(wallet.address);

    await refreshBalance(wallet.address);
}


function shortenAddress(address) {

    if (!address)
        return "";

    return (
        address.substring(0, 6) +
        "..." +
        address.substring(address.length - 4)
    );
}


async function refreshBalance(address) {

    try {

        const response =
            await chrome.runtime.sendMessage({

                type: "GET_GBP_BALANCE",

                address

            });

        const amount =
            Number(response.balance);

        balanceElement.textContent =
            `£${amount.toFixed(2)}`;

        tokenElement.textContent =
            `${amount.toFixed(2)} GBPX`;

    } catch (error) {

        console.error(error);

        balanceElement.textContent =
            "Unable to load";

    }
}


document
    .getElementById("copyAddress")
    .addEventListener(
        "click",
        async () => {

            const address =
                addressElement.textContent;

            await navigator.clipboard.writeText(
                address
            );
        }
    );


initialise();
13. Background service worker
background.js
import { EthereumRPC } from "./rpc.js";

const RPC_URL =
    "https://YOUR_RPC_ENDPOINT";

const rpc =
    new EthereumRPC(RPC_URL);


chrome.runtime.onMessage.addListener(
    (message, sender, sendResponse) => {

        if (
            message.type ===
            "GET_ETH_BALANCE"
        ) {

            rpc.getBalance(
                message.address
            )
            .then(balance => {

                sendResponse({
                    balance
                });

            })
            .catch(error => {

                sendResponse({
                    error: error.message
                });

            });

            return true;
        }

        if (
            message.type ===
            "GET_GBP_BALANCE"
        ) {

            getGBPBalance(
                message.address
            )
            .then(balance => {

                sendResponse({
                    balance
                });

            })
            .catch(error => {

                sendResponse({
                    error: error.message
                });

            });

            return true;
        }
    }
);


async function getGBPBalance(address) {

    /*
       Production implementation:

       eth_call(
           GBP_TOKEN.balanceOf(address)
       )
    */

    return 0;
}
14. Send workflow

The important thing is that the Julia engine should approve the transaction before the blockchain transaction is signed.

User enters:

Recipient:
0xABCD...

Amount:
£250.00

        ↓

JavaScript validates address

        ↓

Julia risk engine

        ↓

Transaction policy

        ↓

Gas estimation

        ↓

Display:

Send £250.00 GBPX
Network fee: £0.XX
Recipient: 0xABCD...

        ↓

USER CONFIRMS

        ↓

Wallet signs transaction

        ↓

RPC broadcast

        ↓

Transaction hash

        ↓

Julia transaction ledger

        ↓

Chrome wallet activity

A Julia risk request could look like:

async function checkTransaction(
    amount,
    destination,
    dailyVolume
) {

    const response = await fetch(
        "http://127.0.0.1:8080/risk",
        {
            method: "POST",

            headers: {
                "Content-Type":
                    "application/json"
            },

            body: JSON.stringify({
                amount,
                destination,
                daily_volume: dailyVolume
            })
        }
    );

    return await response.json();
}
15. The wallet should ultimately have these screens
┌─────────────────────────┐
│ GBP WALLET              │
│                         │
│ £12,482.76              │
│ 12,482.76 GBPX          │
│                         │
│ [ SEND ] [ RECEIVE ]    │
│                         │
│ Ethereum Mainnet        │
│                         │
│ ─────────────────────── │
│ Recent                  │
│                         │
│ + £500.00               │
│    Today                │
│                         │
│ - £125.50               │
│    Yesterday            │
│                         │
│ - £40.00                │
│    02 Sep               │
└─────────────────────────┘

Then a full side-panel version could have:

GBP WALLET

£125,420.72
GBP Stablecoin

┌────────────┐ ┌────────────┐
│   SEND     │ │  RECEIVE   │
└────────────┘ └────────────┘

Portfolio
────────────
GBPX          £125,420
ETH               £842
USDC              £210

Activity
────────────
Received       +£10,000
Sent            -£2,500
Received        +£1,250

Network
────────────
Ethereum
Arbitrum
Base
Optimism

Security
────────────
● Wallet unlocked

[Lock wallet]
16. One important architectural change I'd make

For a serious GBP stablecoin/RhinoBank-style wallet, I wouldn't make Julia responsible for actually holding private keys.

I'd use:

JavaScript

wallet UI
browser integration
signing
blockchain provider
token contracts
hardware-wallet integration

Julia

transaction policy
pricing
FX
risk
portfolio analytics
liquidity analysis
fee optimisation
transaction monitoring
treasury analytics
institutional limits

Smart contracts

GBP stablecoin
mint/burn
reserve controls
pausing
role management
redemption

That gives you a much more interesting platform than simply putting a Julia server behind a wallet.

For example, the Julia engine could eventually calculate:

struct TransactionDecision

    approved::Bool

    amount_gbp::Float64

    estimated_fee_gbp::Float64

    stablecoin_deviation::Float64

    risk_score::Float64

    daily_volume::Float64

    liquidity_score::Float64

    recommended_network::String

end

and select between Ethereum, Base, Arbitrum, etc. based on cost, liquidity, confirmation time and risk, while the Chrome wallet remains the signing authority.

One caution: this is a prototype architecture, not a wallet I'd put real funds into yet. A production wallet needs audited cryptography, secure key derivation/storage, transaction simulation, phishing/domain protections, nonce management, chain-ID validation, EIP-712 handling where applicable, hardware-wallet support, RPC failover, contract verification and independent security review.
