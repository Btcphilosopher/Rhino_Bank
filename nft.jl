module RhinoNFT

using SHA
using UUIDs
using Dates
using JSON3

export
    NFT,
    Collection,
    OwnershipRecord,
    NFTMarketplace,
    create_collection,
    mint_nft,
    list_nft!,
    buy_nft!,
    transfer_nft!,
    verify_nft,
    nft_uri,
    nft_summary

# ============================================================
# RHINO NFT / LIGHTNING ASSET ENGINE
# ============================================================

const VERSION = "0.1.0"

# ------------------------------------------------------------
# NFT
# ------------------------------------------------------------

mutable struct NFT

    token_id::UUID

    collection_id::UUID

    name::String

    description::String

    asset_id::String

    genesis_point::String

    metadata_uri::String

    media_hash::Vector{UInt8}

    attributes::Dict{String,String}

    creator::String

    current_owner::String

    created_at::DateTime

    transferable::Bool

    burned::Bool

    proof::Union{
        Nothing,
        String
    }
end

# ------------------------------------------------------------
# COLLECTION
# ------------------------------------------------------------

mutable struct Collection

    collection_id::UUID

    name::String

    symbol::String

    description::String

    issuer::String

    total_supply::UInt64

    minted::UInt64

    metadata_uri::String

    nfts::Dict{UUID,NFT}

    created_at::DateTime
end

# ------------------------------------------------------------
# OWNERSHIP
# ------------------------------------------------------------

struct OwnershipRecord

    token_id::UUID

    owner::String

    acquired_at::DateTime

    transaction_id::String

    previous_owner::Union{
        Nothing,
        String
    }
end

# ------------------------------------------------------------
# LISTING
# ------------------------------------------------------------

mutable struct NFTListing

    listing_id::UUID

    token_id::UUID

    seller::String

    price_msat::UInt64

    created_at::DateTime

    active::Bool
end

# ------------------------------------------------------------
# MARKETPLACE
# ------------------------------------------------------------

mutable struct NFTMarketplace

    collections::Dict{
        UUID,
        Collection
    }

    ownership_history::Vector{
        OwnershipRecord
    }

    listings::Dict{
        UUID,
        NFTListing
    }

    lightning_node_url::String

    fee_bps::UInt64
end

# ============================================================
# MARKETPLACE
# ============================================================

function NFTMarketplace(
    ;
    lightning_node_url="https://127.0.0.1:8089",
    fee_bps=250
)

    NFTMarketplace(
        Dict{UUID,Collection}(),
        OwnershipRecord[],
        Dict{UUID,NFTListing}(),
        lightning_node_url,
        UInt64(fee_bps)
    )
end

# ============================================================
# COLLECTION CREATION
# ============================================================

function create_collection(
    market::NFTMarketplace;
    name::String,
    symbol::String,
    description::String="",
    issuer::String,
    total_supply::Integer,
    metadata_uri::String=""
)

    total_supply > 0 ||
        error("Supply must be positive")

    id = uuid4()

    collection =
        Collection(
            id,
            name,
            symbol,
            description,
            issuer,
            UInt64(total_supply),
            UInt64(0),
            metadata_uri,
            Dict{UUID,NFT}(),
            now()
        )

    market.collections[id] =
        collection

    return collection
end

# ============================================================
# MEDIA HASH
# ============================================================

function hash_media(
    data::Vector{UInt8}
)

    Vector{UInt8}(
        SHA.sha256(data)
    )
end

function hash_media(
    path::String
)

    open(path, "r") do io

        hash_media(
            read(io)
        )
    end
end

# ============================================================
# ASSET ID
# ============================================================

function make_asset_id(
    collection::Collection,
    token_id::UUID,
    media_hash::Vector{UInt8}
)

    payload =
        Vector{UInt8}(
            codeunits(
                string(
                    collection.collection_id,
                    ":",
                    token_id
                )
            )
        )

    append!(
        payload,
        media_hash
    )

    bytes2hex(
        SHA.sha256(
            payload
        )
    )
end

# ============================================================
# MINT NFT
# ============================================================

function mint_nft!(
    market::NFTMarketplace,
    collection_id::UUID;
    name::String,
    description::String="",
    metadata_uri::String="",
    media_hash::Vector{UInt8},
    creator::String,
    attributes=Dict{String,String}(),
    owner::String=creator
)

    haskey(
        market.collections,
        collection_id
    ) ||
        error("Unknown collection")

    collection =
        market.collections[
            collection_id
        ]

    collection.minted <
    collection.total_supply ||
        error(
            "Collection supply exhausted"
        )

    token_id =
        uuid4()

    asset_id =
        make_asset_id(
            collection,
            token_id,
            media_hash
        )

    nft =
        NFT(
            token_id,
            collection_id,
            name,
            description,
            asset_id,

            # Real value should come from
            # tapd after the mint transaction.
            "PENDING",

            metadata_uri,
            media_hash,

            Dict(
                attributes
            ),

            creator,
            owner,

            now(),

            true,
            false,

            nothing
        )

    collection.nfts[token_id] =
        nft

    collection.minted += 1

    market.collections[
        collection_id
    ] = collection

    push!(
        market.ownership_history,
        OwnershipRecord(
            token_id,
            owner,
            now(),
            "MINT",
            nothing
        )
    )

    nft
end

# ============================================================
# METADATA
# ============================================================

function nft_metadata(
    nft::NFT
)

    Dict(
        "name" =>
            nft.name,

        "description" =>
            nft.description,

        "asset_id" =>
            nft.asset_id,

        "genesis_point" =>
            nft.genesis_point,

        "media_hash" =>
            bytes2hex(
                nft.media_hash
            ),

        "creator" =>
            nft.creator,

        "attributes" =>
            nft.attributes,

        "created_at" =>
            string(
                nft.created_at
            )
    )
end

# ============================================================
# NFT URI
# ============================================================

function nft_uri(
    nft::NFT
)

    "rhino://nft/" *
    string(
        nft.collection_id
    ) *
    "/" *
    string(
        nft.token_id
    )
end

# ============================================================
# MARKET LISTING
# ============================================================

function list_nft!(
    market::NFTMarketplace,
    token_id::UUID;
    seller::String,
    price_msat::Integer
)

    price_msat > 0 ||
        error(
            "Price must be positive"
        )

    nft = nothing

    for collection in values(
        market.collections
    )

        if haskey(
            collection.nfts,
            token_id
        )

            nft =
                collection.nfts[
                    token_id
                ]

            break
        end
    end

    nft === nothing &&
        error("NFT not found")

    nft.burned &&
        error("NFT has been burned")

    nft.current_owner == seller ||
        error(
            "Seller does not own NFT"
        )

    listing =
        NFTListing(
            uuid4(),
            token_id,
            seller,
            UInt64(price_msat),
            now(),
            true
        )

    market.listings[
        listing.listing_id
    ] = listing

    listing
end

# ============================================================
# FIND NFT
# ============================================================

function find_nft(
    market::NFTMarketplace,
    token_id::UUID
)

    for collection in values(
        market.collections
    )

        if haskey(
            collection.nfts,
            token_id
        )

            return collection.nfts[
                token_id
            ]
        end
    end

    error("NFT not found")
end

# ============================================================
# LIGHTNING INVOICE
# ============================================================

"""
Application-level representation of a Lightning
payment request.

In production this is obtained from lnd/tapd rather
than fabricated locally.
"""
struct LightningInvoice

    payment_hash::String

    payment_request::String

    amount_msat::UInt64

    expires_at::DateTime
end

# ============================================================
# PAYMENT INTERFACE
# ============================================================

function create_lightning_invoice(
    market::NFTMarketplace,
    amount_msat::UInt64;
    memo::String=""
)

    # Production:
    #
    # POST /v1/invoices
    #
    # or corresponding gRPC call.
    #
    # This simulator creates a placeholder.

    hash =
        bytes2hex(
            SHA.sha256(
                Vector{UInt8}(
                    codeunits(
                        string(
                            uuid4(),
                            amount_msat
                        )
                    )
                )
            )
        )

    LightningInvoice(
        hash,
        "ln-invoice-" *
        hash[1:24],

        amount_msat,

        now() +
        Minute(15)
    )
end

# ============================================================
# BUY NFT
# ============================================================

function buy_nft!(
    market::NFTMarketplace,
    listing_id::UUID;
    buyer::String
)

    haskey(
        market.listings,
        listing_id
    ) ||
        error("Listing not found")

    listing =
        market.listings[
            listing_id
        ]

    listing.active ||
        error("Listing inactive")

    nft =
        find_nft(
            market,
            listing.token_id
        )

    nft.current_owner ==
        listing.seller ||
        error(
            "Ownership changed"
        )

    invoice =
        create_lightning_invoice(
            market,
            listing.price_msat;
            memo =
                "NFT purchase " *
                string(
                    nft.token_id
                )
        )

    println()
    println(
        "Lightning payment required:"
    )
    println(
        invoice.payment_request
    )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Do NOT transfer ownership merely because an invoice
    # was generated.
    #
    # The real implementation waits for node/tapd
    # confirmation.
    # --------------------------------------------------------

    invoice
end

# ============================================================
# COMPLETE TRANSFER
# ============================================================

function transfer_nft!(
    market::NFTMarketplace,
    token_id::UUID;
    from::String,
    to::String,
    transaction_id::String
)

    nft =
        find_nft(
            market,
            token_id
        )

    nft.current_owner == from ||
        error(
            "Transfer rejected: ownership mismatch"
        )

    nft.transferable ||
        error(
            "NFT is non-transferable"
        )

    nft.burned &&
        error(
            "NFT has been burned"
        )

    nft.current_owner =
        to

    push!(
        market.ownership_history,
        OwnershipRecord(
            token_id,
            to,
            now(),
            transaction_id,
            from
        )
    )

    nft
end

# ============================================================
# BURN
# ============================================================

function burn_nft!(
    market::NFTMarketplace,
    token_id::UUID;
    owner::String
)

    nft =
        find_nft(
            market,
            token_id
        )

    nft.current_owner == owner ||
        error(
            "Only owner may burn NFT"
        )

    nft.burned = true

    nft
end

# ============================================================
# VERIFICATION
# ============================================================

function verify_nft(
    market::NFTMarketplace,
    token_id::UUID
)

    nft =
        find_nft(
            market,
            token_id
        )

    expected =
        make_asset_id(
            market.collections[
                nft.collection_id
            ],
            nft.token_id,
            nft.media_hash
        )

    expected ==
    nft.asset_id
end

# ============================================================
# SUMMARY
# ============================================================

function nft_summary(
    market::NFTMarketplace,
    token_id::UUID
)

    nft =
        find_nft(
            market,
            token_id
        )

    collection =
        market.collections[
            nft.collection_id
        ]

    println()
    println(
        "======================================"
    )
    println(
        " RHINO LIGHTNING NFT"
    )
    println(
        "======================================"
    )

    println(
        "Collection: ",
        collection.name
    )

    println(
        "Token ID:   ",
        nft.token_id
    )

    println(
        "Asset ID:   ",
        nft.asset_id
    )

    println(
        "Genesis:    ",
        nft.genesis_point
    )

    println(
        "Owner:      ",
        nft.current_owner
    )

    println(
        "Metadata:   ",
        nft.metadata_uri
    )

    println(
        "Verified:   ",
        verify_nft(
            market,
            token_id
        )
    )

    println(
        "Burned:     ",
        nft.burned
    )

    println(
        "======================================"
    )
end

end # module
