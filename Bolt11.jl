module Bolt11

using SHA
using Random
using Dates

export Invoice,
       TaggedField,
       create_invoice,
       encode_invoice,
       decode_invoice,
       validate_invoice,
       invoice_summary,
       add_tag!

# ============================================================
# BOLT 11
# ============================================================

const CHARSET =
    "qpzry9x8gf2tvdw0s3jn54khce6mua7l"

const CHARSET_REV = Dict(c => i - 1 for (i, c) in enumerate(CHARSET))

const BECH32_CONST = UInt32(1)

# ------------------------------------------------------------
# Data structures
# ------------------------------------------------------------

struct TaggedField
    tag::Char
    data::Vector{UInt8}
end

mutable struct Invoice
    network::Symbol
    amount_msat::Union{Nothing,UInt64}
    timestamp::UInt64

    payment_hash::Vector{UInt8}
    payment_secret::Union{Nothing,Vector{UInt8}}

    description::Union{Nothing,String}
    description_hash::Union{Nothing,Vector{UInt8}}

    destination::Union{Nothing,Vector{UInt8}}
    expiry::UInt64

    min_final_cltv::UInt64

    fallback_address::Union{Nothing,String}

    routing_hints::Vector{Any}
    feature_bits::Vector{UInt8}

    tags::Vector{TaggedField}

    signature::Union{Nothing,Vector{UInt8}}
end

# ------------------------------------------------------------
# Network
# ------------------------------------------------------------

function network_hrp(network::Symbol)

    network == :bitcoin && return "lnbc"
    network == :testnet && return "lntb"
    network == :regtest && return "lnbcrt"
    network == :signet && return "lntbs"

    error("Unsupported Lightning network: $network")
end

# ------------------------------------------------------------
# Cryptographic random bytes
# ------------------------------------------------------------

random_bytes(n::Int) = rand(UInt8, n)

function random_32()
    random_bytes(32)
end

# ------------------------------------------------------------
# SHA256
# ------------------------------------------------------------

sha256_bytes(x::Vector{UInt8}) =
    Vector{UInt8}(SHA.sha256(x))

# ------------------------------------------------------------
# Bech32 primitives
# ------------------------------------------------------------

function polymod(values)

    generator = UInt32[
        0x3b6a57b2,
        0x26508e6d,
        0x1ea119fa,
        0x3d4233dd,
        0x2a1462b3
    ]

    chk = UInt32(1)

    for v in values

        top = chk >> 25

        chk = ((chk & 0x1ffffff) << 5) ⊻ UInt32(v)

        for i in 0:4
            if ((top >> i) & 1) == 1
                chk ⊻= generator[i + 1]
            end
        end
    end

    return chk
end

function hrp_expand(hrp)

    result = UInt8[]

    for c in codeunits(hrp)
        push!(result, UInt8(c >> 5))
    end

    push!(result, 0)

    for c in codeunits(hrp)
        push!(result, UInt8(c & 31))
    end

    result
end

function convertbits(
    data::Vector{UInt8},
    frombits::Int,
    tobits::Int;
    pad::Bool=true
)

    acc = 0
    bits = 0
    ret = UInt8[]

    maxv = (1 << tobits) - 1
    max_acc = (1 << (frombits + tobits - 1)) - 1

    for value in data

        if (value >> frombits) != 0
            error("Invalid value for convertbits")
        end

        acc = ((acc << frombits) | Int(value)) & max_acc
        bits += frombits

        while bits >= tobits

            bits -= tobits

            push!(
                ret,
                UInt8((acc >> bits) & maxv)
            )
        end
    end

    if pad

        if bits > 0
            push!(
                ret,
                UInt8((acc << (tobits - bits)) & maxv)
            )
        end

    else

        if bits >= frombits
            error("Excess padding")
        end

        if ((acc << (tobits - bits)) & maxv) != 0
            error("Non-zero padding")
        end
    end

    ret
end

function bech32_checksum(hrp, data)

    values =
        vcat(
            hrp_expand(hrp),
            data,
            zeros(UInt8, 6)
        )

    mod = polymod(values) ⊻ BECH32_CONST

    [
        UInt8((mod >> 5 * (5 - i)) & 31)
        for i in 0:5
    ]
end

function bech32_encode(hrp, data)

    checksum =
        bech32_checksum(hrp, data)

    combined =
        vcat(data, checksum)

    chars = String[
        string(CHARSET[Int(x) + 1])
        for x in combined
    ]

    lowercase(hrp * "1" * join(chars))
end

function bech32_decode(s)

    s = lowercase(strip(s))

    pos = findlast(==('1'), s)

    pos === nothing &&
        error("Invalid Bech32 string")

    hrp = s[1:pos-1]
    payload = s[pos+1:end]

    length(payload) >= 6 ||
        error("Bech32 payload too short")

    values = UInt8[]

    for c in payload

        haskey(CHARSET_REV, c) ||
            error("Invalid Bech32 character")

        push!(values, UInt8(CHARSET_REV[c]))
    end

    polymod(
        vcat(
            hrp_expand(hrp),
            values
        )
    ) == BECH32_CONST ||
        error("Invalid Bech32 checksum")

    return (
        hrp,
        values[1:end-6]
    )
end

# ------------------------------------------------------------
# Integer encoding
# ------------------------------------------------------------

function uint_to_bytes(x::UInt64, n::Int)

    result = zeros(UInt8, n)

    for i in n:-1:1

        result[i] =
            UInt8(x & 0xff)

        x >>= 8
    end

    result
end

function bytes_to_uint(v)

    result = UInt64(0)

    for b in v
        result = (result << 8) | UInt64(b)
    end

    result
end

# ------------------------------------------------------------
# Amount → BOLT11 HRP
# ------------------------------------------------------------

function encode_amount_msat(msat::UInt64)

    # BOLT11 supports:
    #
    # m = milli-bitcoin
    # u = micro-bitcoin
    # n = nano-bitcoin
    # p = pico-bitcoin

    # Convert msat → bitcoin pico units.
    pico =
        BigInt(msat) * BigInt(10)^9

    units = [
        ('m', BigInt(10)^12),
        ('u', BigInt(10)^9),
        ('n', BigInt(10)^6),
        ('p', BigInt(10)^3)
    ]

    for (suffix, divisor) in units

        if pico % divisor == 0

            amount = pico ÷ divisor

            return string(amount) * suffix
        end
    end

    error(
        "Amount cannot be represented exactly in BOLT11 HRP"
    )
end

# ------------------------------------------------------------
# Tagged fields
# ------------------------------------------------------------

function tag_to_words(data::Vector{UInt8})

    convertbits(
        data,
        8,
        5,
        pad=true
    )
end

function words_to_bytes(words)

    convertbits(
        Vector{UInt8}(words),
        5,
        8,
        pad=false
    )
end

function add_tag!(
    invoice::Invoice,
    tag::Char,
    data::Vector{UInt8}
)

    push!(
        invoice.tags,
        TaggedField(tag, data)
    )

    invoice
end

# ------------------------------------------------------------
# Standard tags
# ------------------------------------------------------------

function add_payment_hash!(invoice)

    add_tag!(
        invoice,
        'p',
        invoice.payment_hash
    )
end

function add_payment_secret!(invoice)

    invoice.payment_secret === nothing &&
        return

    add_tag!(
        invoice,
        's',
        invoice.payment_secret
    )
end

function add_description!(invoice)

    invoice.description === nothing &&
        return

    add_tag!(
        invoice,
        'd',
        Vector{UInt8}(
            codeunits(invoice.description)
        )
    )
end

function add_description_hash!(invoice)

    invoice.description_hash === nothing &&
        return

    add_tag!(
        invoice,
        'h',
        invoice.description_hash
    )
end

function add_expiry!(invoice)

    invoice.expiry == 3600 &&
        return

    add_tag!(
        invoice,
        'x',
        uint_to_bytes(
            invoice.expiry,
            8
        )
    )
end

function add_cltv!(invoice)

    invoice.min_final_cltv == 18 &&
        return

    add_tag!(
        invoice,
        'c',
        uint_to_bytes(
            invoice.min_final_cltv,
            4
        )
    )
end

# ------------------------------------------------------------
# Invoice constructor
# ------------------------------------------------------------

function create_invoice(
    ;
    network::Symbol=:bitcoin,
    amount_msat::Union{Nothing,Integer}=nothing,
    description::Union{Nothing,String}=nothing,
    expiry::Integer=3600,
    min_final_cltv::Integer=18,
    payment_hash::Union{Nothing,Vector{UInt8}}=nothing,
    payment_secret::Union{Nothing,Vector{UInt8}}=nothing
)

    ph =
        payment_hash === nothing ?
        random_32() :
        payment_hash

    length(ph) == 32 ||
        error("payment_hash must be 32 bytes")

    ps =
        payment_secret === nothing ?
        random_32() :
        payment_secret

    length(ps) == 32 ||
        error("payment_secret must be 32 bytes")

    Invoice(
        network,
        amount_msat === nothing ?
            nothing :
            UInt64(amount_msat),

        UInt64(Dates.datetime2unix(now(Dates.UTC))),

        ph,
        ps,

        description,
        nothing,

        nothing,

        UInt64(expiry),
        UInt64(min_final_cltv),

        nothing,

        Any[],
        UInt8[],

        TaggedField[],

        nothing
    )
end

# ------------------------------------------------------------
# Build BOLT11 data
# ------------------------------------------------------------

function build_data(invoice::Invoice)

    invoice.tags = TaggedField[]

    add_payment_hash!(invoice)
    add_payment_secret!(invoice)
    add_description!(invoice)
    add_description_hash!(invoice)
    add_expiry!(invoice)
    add_cltv!(invoice)

    data = UInt8[]

    # timestamp = 35-bit unsigned integer
    timestamp =
        invoice.timestamp

    timestamp_words =
        UInt8[
            UInt8(
                (timestamp >> (5 * i)) & 31
            )
            for i in reverse(0:6)
        ]

    append!(
        data,
        timestamp_words
    )

    # Tagged fields:
    #
    # 5-bit tag
    # 10-bit length
    # payload

    for field in invoice.tags

        tag_index =
            get(
                CHARSET_REV,
                field.tag,
                -1
            )

        tag_index >= 0 ||
            error("Unsupported BOLT11 tag")

        words =
            tag_to_words(field.data)

        length(words) <= 1023 ||
            error("BOLT11 tagged field too large")

        push!(
            data,
            UInt8(tag_index)
        )

        push!(
            data,
            UInt8(length(words) >> 5)
        )

        push!(
            data,
            UInt8(length(words) & 31)
        )

        append!(
            data,
            words
        )
    end

    data
end

# ------------------------------------------------------------
# Signing interface
# ------------------------------------------------------------

"""
Create the exact message which must be signed.

The actual BOLT11 implementation must use a secp256k1
ECDSA signer and append the recovery ID.

This function deliberately exposes the digest so that the
signer can live in a hardened cryptographic component.
"""
function signing_digest(invoice::Invoice)

    hrp =
        network_hrp(invoice.network)

    if invoice.amount_msat !== nothing

        hrp *=
            encode_amount_msat(
                invoice.amount_msat
            )
    end

    data =
        build_data(invoice)

    data_bytes =
        convertbits(
            data,
            5,
            8,
            pad=true
        )

    sha256_bytes(
        vcat(
            Vector{UInt8}(
                codeunits(hrp)
            ),
            data_bytes
        )
    )
end

# ------------------------------------------------------------
# Encoding
# ------------------------------------------------------------

function encode_invoice(
    invoice::Invoice;
    signature::Union{
        Nothing,
        Vector{UInt8}
    }=nothing
)

    hrp =
        network_hrp(invoice.network)

    if invoice.amount_msat !== nothing

        hrp *=
            encode_amount_msat(
                invoice.amount_msat
            )
    end

    data =
        build_data(invoice)

    # A valid BOLT11 signature is:
    #
    # 64-byte compact ECDSA signature
    # + 1-byte recovery ID
    #
    # The signer is external in this implementation.

    signature === nothing &&
        error(
            "A real secp256k1 signature is required"
        )

    length(signature) == 65 ||
        error(
            "BOLT11 signature must be 65 bytes"
        )

    sig_words =
        convertbits(
            signature,
            8,
            5,
            pad=true
        )

    bech32_encode(
        hrp,
        vcat(data, sig_words)
    )
end

# ------------------------------------------------------------
# Decoder
# ------------------------------------------------------------

function decode_invoice(payment_request::String)

    hrp, data =
        bech32_decode(
            payment_request
        )

    startswith(hrp, "ln") ||
        error("Not a Lightning invoice")

    timestamp =
        bytes_to_uint(
            words_to_bytes(
                data[1:7]
            )
        )

    fields = TaggedField[]

    # After timestamp:
    #
    # tag + length(2 words) + payload

    pos = 8

    while pos <= length(data)

        remaining =
            length(data) - pos + 1

        # Last 104 words represent
        # the 65-byte signature.
        #
        # 65 bytes → 104 five-bit words.
        if remaining <= 104
            break
        end

        tag_index =
            Int(data[pos])

        tag_index < 32 ||
            error("Invalid tag")

        tag =
            CHARSET[tag_index + 1]

        length_words =
            (Int(data[pos + 1]) << 5) |
            Int(data[pos + 2])

        start =
            pos + 3

        stop =
            start + length_words - 1

        stop < length(data) ||
            error("Invalid tagged field")

        words =
            data[start:stop]

        bytes =
            words_to_bytes(words)

        push!(
            fields,
            TaggedField(
                tag,
                bytes
            )
        )

        pos = stop + 1
    end

    signature_words =
        data[pos:end]

    signature =
        words_to_bytes(
            signature_words
        )

    (
        hrp=hrp,
        timestamp=timestamp,
        tags=fields,
        signature=signature
    )
end

# ------------------------------------------------------------
# Validation
# ------------------------------------------------------------

function validate_invoice(
    payment_request::String
)

    decoded =
        decode_invoice(
            payment_request
        )

    length(decoded.signature) == 65 ||
        return false

    for field in decoded.tags

        if field.tag == 'p'

            length(field.data) == 32 ||
                return false

        elseif field.tag == 's'

            length(field.data) == 32 ||
                return false

        elseif field.tag == 'x'

            length(field.data) <= 8 ||
                return false

        end
    end

    true
end

# ------------------------------------------------------------
# Human-readable inspection
# ------------------------------------------------------------

function invoice_summary(
    payment_request::String
)

    d =
        decode_invoice(
            payment_request
        )

    println("================================")
    println(" BOLT 11 INVOICE")
    println("================================")

    println("HRP:       ", d.hrp)
    println("Timestamp: ", d.timestamp)

    for field in d.tags

        println(
            "Tag ",
            field.tag,
            ": ",
            bytes2hex(field.data)
        )
    end

    println(
        "Signature: ",
        bytes2hex(d.signature)
    )

    println(
        "Valid structure: ",
        validate_invoice(
            payment_request
        )
    )

    println("================================")
end

end # module
