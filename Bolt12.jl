module Bolt12

using SHA
using Random

export
    TLV,
    Offer,
    InvoiceRequest,
    Bolt12Invoice,
    add_tlv!,
    encode_offer,
    decode_offer,
    create_offer,
    create_invoice_request

# ============================================================
# BOLT 12 TLV ENGINE
# ============================================================

struct TLV
    typ::UInt64
    value::Vector{UInt8}
end

mutable struct Offer
    node_id::Vector{UInt8}

    amount_msat::Union{Nothing,UInt64}

    description::Union{
        Nothing,
        String
    }

    issuer::Union{
        Nothing,
        String
    }

    quantity_max::Union{
        Nothing,
        UInt64
    }

    absolute_expiry::Union{
        Nothing,
        UInt64
    }

    features::Vector{UInt8}

    signing_key::Vector{UInt8}

    blinded_paths::Vector{Any}

    tlvs::Vector{TLV}

    signature::Union{
        Nothing,
        Vector{UInt8}
    }
end

mutable struct InvoiceRequest

    offer::Offer

    quantity::Union{
        Nothing,
        UInt64
    }

    amount_msat::Union{
        Nothing,
        UInt64
    }

    payer_id::Vector{UInt8}

    payer_note::Union{
        Nothing,
        String
    }

    blinded_paths::Vector{Any}

    tlvs::Vector{TLV}

    signature::Union{
        Nothing,
        Vector{UInt8}
    }
end

mutable struct Bolt12Invoice

    node_id::Vector{UInt8}

    amount_msat::UInt64

    payment_hash::Vector{UInt8}

    payment_secret::Union{
        Nothing,
        Vector{UInt8}
    }

    created_at::UInt64

    relative_expiry::UInt64

    invoice_request::InvoiceRequest

    blinded_paths::Vector{Any}

    tlvs::Vector{TLV}

    signature::Union{
        Nothing,
        Vector{UInt8}
    }
end

# ============================================================
# BIG-ENDIAN INTEGER
# ============================================================

function encode_uint(x::UInt64)

    bytes = UInt8[]

    started = false

    for shift in 56:-8:0

        b =
            UInt8(
                (x >> shift) & 0xff
            )

        if b != 0 || started || shift == 0

            push!(bytes, b)
            started = true
        end
    end

    bytes
end

# ============================================================
# BIGSIZE
# ============================================================

function encode_bigsize(x::UInt64)

    if x < 0xfd

        return UInt8[
            UInt8(x)
        ]

    elseif x <= 0xffff

        return vcat(
            UInt8[0xfd],
            UInt8[
                (x >> 8) & 0xff,
                x & 0xff
            ]
        )

    elseif x <= 0xffffffff

        return vcat(
            UInt8[0xfe],
            [
                UInt8((x >> shift) & 0xff)
                for shift in 24:-8:0
            ]
        )

    else

        return vcat(
            UInt8[0xff],
            [
                UInt8((x >> shift) & 0xff)
                for shift in 56:-8:0
            ]
        )
    end
end

# ============================================================
# TLV
# ============================================================

function encode_tlv(t::TLV)

    vcat(
        encode_bigsize(t.typ),
        encode_bigsize(UInt64(length(t.value))),
        t.value
    )
end

function encode_tlvs(tlvs)

    result = UInt8[]

    # BOLT12 TLVs must be ordered numerically.
    sorted =
        sort(
            tlvs,
            by = x -> x.typ
        )

    for tlv in sorted

        append!(
            result,
            encode_tlv(tlv)
        )
    end

    result
end

function add_tlv!(
    obj,
    typ::UInt64,
    value::Vector{UInt8}
)

    push!(
        obj.tlvs,
        TLV(
            typ,
            value
        )
    )

    obj
end

# ============================================================
# RANDOM IDENTIFIERS
# ============================================================

random32() =
    rand(UInt8, 32)

# ============================================================
# OFFER
# ============================================================

function create_offer(
    node_id::Vector{UInt8};
    amount_msat=nothing,
    description=nothing,
    issuer=nothing
)

    Offer(
        node_id,
        amount_msat === nothing ?
            nothing :
            UInt64(amount_msat),

        description,
        issuer,

        nothing,
        nothing,

        UInt8[],

        random32(),

        Any[],

        TLV[],

        nothing
    )
end

# ============================================================
# OFFER TLVs
# ============================================================

function build_offer_tlvs(
    offer::Offer
)

    tlvs = TLV[]

    # The actual BOLT12 type assignments should be kept
    # in a dedicated specification table so that updates
    # can be incorporated without rewriting the encoder.

    # Example application-level fields:

    if offer.amount_msat !== nothing

        push!(
            tlvs,
            TLV(
                UInt64(2),
                encode_uint(
                    offer.amount_msat
                )
            )
        )
    end

    if offer.description !== nothing

        push!(
            tlvs,
            TLV(
                UInt64(10),
                Vector{UInt8}(
                    codeunits(
                        offer.description
                    )
                )
            )
        )
    end

    if offer.issuer !== nothing

        push!(
            tlvs,
            TLV(
                UInt64(12),
                Vector{UInt8}(
                    codeunits(
                        offer.issuer
                    )
                )
            )
        )
    end

    append!(
        tlvs,
        offer.tlvs
    )

    sort!(
        tlvs,
        by=x -> x.typ
    )

    tlvs
end

# ============================================================
# OFFER SIGNING DIGEST
# ============================================================

function offer_signing_digest(
    offer::Offer
)

    payload =
        encode_tlvs(
            build_offer_tlvs(
                offer
            )
        )

    SHA.sha256(payload)
end

# ============================================================
# BOLT12 BECH32
# ============================================================

function bech32_encode_bolt12(
    payload::Vector{UInt8}
)

    # Placeholder for the shared Bech32/TLV codec.
    #
    # Production implementation:
    #
    #   TLV bytes
    #       ↓
    #   BOLT12 Bech32 encoding
    #       ↓
    #   lno1...
    #
    error(
        "Connect to shared BOLT12 Bech32 codec"
    )
end

function encode_offer(
    offer::Offer;
    signature::Union{
        Nothing,
        Vector{UInt8}
    }=nothing
)

    signature === nothing &&
        error(
            "BOLT12 Offer requires cryptographic signature"
        )

    offer.signature =
        signature

    tlvs =
        build_offer_tlvs(
            offer
        )

    payload =
        encode_tlvs(
            tlvs
        )

    bech32_encode_bolt12(
        payload
    )
end

# ============================================================
# INVOICE REQUEST
# ============================================================

function create_invoice_request(
    offer::Offer;
    quantity=nothing,
    amount_msat=nothing,
    payer_note=nothing
)

    InvoiceRequest(
        offer,

        quantity === nothing ?
            nothing :
            UInt64(quantity),

        amount_msat === nothing ?
            nothing :
            UInt64(amount_msat),

        random32(),

        payer_note,

        Any[],

        TLV[],

        nothing
    )
end

# ============================================================
# REQUEST DIGEST
# ============================================================

function invoice_request_digest(
    request::InvoiceRequest
)

    payload =
        encode_tlvs(
            request.tlvs
        )

    SHA.sha256(payload)
end

# ============================================================
# DEBUG DISPLAY
# ============================================================

function show_offer(
    offer::Offer
)

    println()
    println("====================================")
    println(" BOLT 12 OFFER")
    println("====================================")

    println(
        "Node ID: ",
        bytes2hex(
            offer.node_id
        )
    )

    println(
        "Amount: ",
        offer.amount_msat === nothing ?
        "variable" :
        string(
            offer.amount_msat,
            " msat"
        )
    )

    println(
        "Description: ",
        offer.description
    )

    println(
        "Issuer: ",
        offer.issuer
    )

    println(
        "TLVs: ",
        length(
            build_offer_tlvs(
                offer
            )
        )
    )

    println("====================================")
end

end
