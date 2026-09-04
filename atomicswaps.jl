module RhinoAtomicSwap

using SHA
using UUIDs
using Dates
using Random

export
    Swap,
    SwapLeg,
    SwapState,
    create_swap,
    generate_secret!,
    verify_preimage,
    lock_lightning!,
    lock_onchain!,
    reveal_preimage!,
    claim_lightning!,
    claim_onchain!,
    refund_swap!,
    swap_status

# ============================================================
# ATOMIC SWAP STATE MACHINE
# ============================================================

@enum SwapState begin
    CREATED
    QUOTED
    SECRET_GENERATED
    LIGHTNING_LOCKED
    ONCHAIN_LOCKED
    READY_TO_SETTLE
    PREIMAGE_REVEALED
    LIGHTNING_CLAIMED
    ONCHAIN_CLAIMED
    COMPLETED
    EXPIRED
    REFUNDED
    FAILED
end

@enum LegState begin
    UNLOCKED
    LOCKED
    CLAIMED
    REFUNDED
end

@enum AssetType begin
    BTC_LIGHTNING
    BTC_ONCHAIN
    TAPROOT_ASSET
    OTHER
end

# ============================================================
# SWAP LEG
# ============================================================

mutable struct SwapLeg

    asset::AssetType

    amount::UInt64

    owner::String

    hashlock::Vector{UInt8}

    timelock::DateTime

    state::LegState

    contract_id::String

    transaction_id::Union{
        Nothing,
        String
    }
end

# ============================================================
# SWAP
# ============================================================

mutable struct Swap

    id::UUID

    initiator::String

    counterparty::String

    send_asset::AssetType

    receive_asset::AssetType

    send_amount::UInt64

    receive_amount::UInt64

    secret::Union{
        Nothing,
        Vector{UInt8}
    }

    payment_hash::Vector{UInt8}

    lightning_leg::Union{
        Nothing,
        SwapLeg
    }

    onchain_leg::Union{
        Nothing,
        SwapLeg
    }

    created_at::DateTime

    expires_at::DateTime

    state::SwapState

    fee_msat::UInt64
end

# ============================================================
# RANDOM SECRET
# ============================================================

function random_secret()

    rand(
        UInt8,
        32
    )
end

# ============================================================
# HASHLOCK
# ============================================================

function hash_secret(
    secret::Vector{UInt8}
)

    Vector{UInt8}(
        SHA.sha256(secret)
    )
end

# ============================================================
# CREATE SWAP
# ============================================================

function create_swap(
    ;
    initiator::String,
    counterparty::String,

    send_asset::AssetType,
    receive_asset::AssetType,

    send_amount::Integer,
    receive_amount::Integer,

    timeout_minutes::Integer=60,

    fee_msat::Integer=0
)

    secret =
        random_secret()

    hashlock =
        hash_secret(secret)

    now_time =
        now()

    Swap(
        uuid4(),

        initiator,
        counterparty,

        send_asset,
        receive_asset,

        UInt64(send_amount),
        UInt64(receive_amount),

        secret,

        hashlock,

        nothing,
        nothing,

        now_time,

        now_time +
        Minute(timeout_minutes),

        CREATED,

        UInt64(fee_msat)
    )
end

# ============================================================
# SECRET
# ============================================================

function generate_secret!(
    swap::Swap
)

    swap.state ==
    CREATED ||
        error(
            "Secret can only be generated from CREATED"
        )

    swap.secret =
        random_secret()

    swap.payment_hash =
        hash_secret(
            swap.secret
        )

    swap.state =
        SECRET_GENERATED

    swap
end

# ============================================================
# PREIMAGE VERIFICATION
# ============================================================

function verify_preimage(
    swap::Swap,
    preimage::Vector{UInt8}
)

    hash_secret(
        preimage
    ) ==
    swap.payment_hash
end

# ============================================================
# LIGHTNING CONTRACT
# ============================================================

function lock_lightning!(
    swap::Swap;
    contract_id::String,
    transaction_id::Union{
        Nothing,
        String
    }=nothing
)

    swap.state in
        (
            SECRET_GENERATED,
            ONCHAIN_LOCKED
        ) ||
        error(
            "Invalid state for Lightning lock"
        )

    swap.lightning_leg =
        SwapLeg(
            swap.send_asset ==
                BTC_LIGHTNING ?
                BTC_LIGHTNING :
                swap.receive_asset,

            swap.send_amount,

            swap.initiator,

            swap.payment_hash,

            swap.expires_at,

            LOCKED,

            contract_id,

            transaction_id
        )

    if swap.onchain_leg !== nothing

        swap.state =
            READY_TO_SETTLE
    else

        swap.state =
            LIGHTNING_LOCKED
    end

    swap
end

# ============================================================
# ON-CHAIN CONTRACT
# ============================================================

function lock_onchain!(
    swap::Swap;
    contract_id::String,
    transaction_id::Union{
        Nothing,
        String
    }=nothing
)

    swap.state in
        (
            SECRET_GENERATED,
            LIGHTNING_LOCKED
        ) ||
        error(
            "Invalid state for on-chain lock"
        )

    swap.onchain_leg =
        SwapLeg(
            BTC_ONCHAIN,

            swap.receive_amount,

            swap.counterparty,

            swap.payment_hash,

            swap.expires_at,

            LOCKED,

            contract_id,

            transaction_id
        )

    if swap.lightning_leg !== nothing

        swap.state =
            READY_TO_SETTLE
    else

        swap.state =
            ONCHAIN_LOCKED
    end

    swap
end

# ============================================================
# REVEAL PREIMAGE
# ============================================================

function reveal_preimage!(
    swap::Swap,
    preimage::Vector{UInt8}
)

    verify_preimage(
        swap,
        preimage
    ) ||
        error(
            "Invalid preimage"
        )

    swap.secret =
        copy(preimage)

    swap.state =
        PREIMAGE_REVEALED

    swap
end

# ============================================================
# CLAIM LIGHTNING
# ============================================================

function claim_lightning!(
    swap::Swap;
    transaction_id::String
)

    swap.state ==
    PREIMAGE_REVEALED ||
        error(
            "Preimage has not been revealed"
        )

    swap.lightning_leg === nothing &&
        error(
            "No Lightning leg"
        )

    verify_preimage(
        swap,
        swap.secret
    ) ||
        error(
            "Preimage verification failed"
        )

    swap.lightning_leg.state =
        CLAIMED

    swap.lightning_leg.transaction_id =
        transaction_id

    if swap.onchain_leg !== nothing &&
       swap.onchain_leg.state == CLAIMED

        swap.state =
            COMPLETED
    end

    swap
end

# ============================================================
# CLAIM ON-CHAIN
# ============================================================

function claim_onchain!(
    swap::Swap;
    transaction_id::String
)

    swap.state ==
    PREIMAGE_REVEALED ||
        error(
            "Preimage has not been revealed"
        )

    swap.onchain_leg === nothing &&
        error(
            "No on-chain leg"
        )

    verify_preimage(
        swap,
        swap.secret
    ) ||
        error(
            "Invalid preimage"
        )

    swap.onchain_leg.state =
        CLAIMED

    swap.onchain_leg.transaction_id =
        transaction_id

    if swap.lightning_leg !== nothing &&
       swap.lightning_leg.state == CLAIMED

        swap.state =
            COMPLETED
    end

    swap
end

# ============================================================
# REFUND
# ============================================================

function refund_swap!(
    swap::Swap
)

    now() >=
    swap.expires_at ||
        error(
            "Swap has not expired"
        )

    if swap.lightning_leg !== nothing

        if swap.lightning_leg.state ==
           LOCKED

            swap.lightning_leg.state =
                REFUNDED
        end
    end

    if swap.onchain_leg !== nothing

        if swap.onchain_leg.state ==
           LOCKED

            swap.onchain_leg.state =
                REFUNDED
        end
    end

    swap.state =
        REFUNDED

    swap
end

# ============================================================
# STATUS
# ============================================================

function swap_status(
    swap::Swap
)

    println()
    println(
        "=========================================="
    )
    println(
        " RHINO ATOMIC SWAP"
    )
    println(
        "=========================================="
    )

    println(
        "Swap ID: ",
        swap.id
    )

    println(
        "State: ",
        swap.state
    )

    println(
        "Send: ",
        swap.send_amount,
        " ",
        swap.send_asset
    )

    println(
        "Receive: ",
        swap.receive_amount,
        " ",
        swap.receive_asset
    )

    println(
        "Hashlock: ",
        bytes2hex(
            swap.payment_hash
        )
    )

    println(
        "Expires: ",
        swap.expires_at
    )

    if swap.lightning_leg !== nothing

        println(
            "Lightning: ",
            swap.lightning_leg.state
        )
    end

    if swap.onchain_leg !== nothing

        println(
            "On-chain: ",
            swap.onchain_leg.state
        )
    end

    println(
        "=========================================="
    )
end

end
