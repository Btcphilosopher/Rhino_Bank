using Dates
using UUIDs
using SHA
using JSON3
using HTTP
using Random

# ============================================================
# RHINO LIGHTNING RAILS
#
# Bitcoin Lightning payment processing layer
#
# Julia 1.10+
#
# SIMULATION / APPLICATION LAYER
#
# In production:
#   Julia <-> Lightning node API
#   Julia <-> Database
#   Julia <-> Merchant systems
# ============================================================


# ============================================================
# CONFIGURATION
# ============================================================

const SATOSHIS_PER_BTC = 100_000_000

const DEFAULT_INVOICE_EXPIRY = 3600

const MAX_PAYMENT_RETRIES = 3

const API_TIMEOUT = 10


# ============================================================
# PAYMENT STATES
# ============================================================

const CREATED   = :CREATED
const PENDING   = :PENDING
const SUCCEEDED = :SUCCEEDED
const FAILED    = :FAILED
const EXPIRED   = :EXPIRED
const CANCELLED = :CANCELLED


# ============================================================
# INVOICE
# ============================================================

mutable struct Invoice

    id::String

    payment_hash::String

    amount_msat::Int64

    description::String

    created_at::DateTime

    expires_at::DateTime

    status::Symbol

    payment_request::String

    paid_at::Union{Nothing,DateTime}

    preimage::Union{Nothing,String}

end


# ============================================================
# PAYMENT
# ============================================================

mutable struct Payment

    id::String

    invoice_id::String

    amount_msat::Int64

    fee_msat::Int64

    total_msat::Int64

    status::Symbol

    created_at::DateTime

    completed_at::Union{Nothing,DateTime}

    failure_reason::Union{Nothing,String}

    attempts::Int

end


# ============================================================
# MERCHANT ACCOUNT
# ============================================================

mutable struct Merchant

    id::String

    name::String

    balance_msat::Int64

    total_received_msat::Int64

    total_sent_msat::Int64

    transaction_count::Int

end


# ============================================================
# LIGHTNING CHANNEL
# ============================================================

mutable struct Channel

    id::String

    local_node::String

    remote_node::String

    capacity_msat::Int64

    local_balance_msat::Int64

    remote_balance_msat::Int64

    active::Bool

    fee_base_msat::Int64

    fee_rate_ppm::Int64

end


# ============================================================
# PAYMENT RAIL
# ============================================================

mutable struct LightningRail

    node_id::String

    network::Symbol

    invoices::Dict{String,Invoice}

    payments::Dict{String,Payment}

    merchants::Dict{String,Merchant}

    channels::Dict{String,Channel}

    ledger::Vector{Dict{String,Any}}

    total_volume_msat::Int64

    total_fees_msat::Int64

end


# ============================================================
# CONSTRUCTOR
# ============================================================

function create_rail(

    node_id::String = "rhino-julia-node";

    network::Symbol = :regtest

)

    return LightningRail(

        node_id,

        network,

        Dict{String,Invoice}(),

        Dict{String,Payment}(),

        Dict{String,Merchant}(),

        Dict{String,Channel}(),

        Vector{Dict{String,Any}}(),

        0,

        0
    )
end


# ============================================================
# UTILITY
# ============================================================

function sats_to_msat(sats::Integer)

    return Int64(sats * 1000)
end


function msat_to_sats(msat::Integer)

    return msat ÷ 1000
end


function btc_to_msat(btc::Real)

    return Int64(round(
        btc * SATOSHIS_PER_BTC * 1000
    ))
end


function msat_to_btc(msat::Integer)

    return msat /
           (SATOSHIS_PER_BTC * 1000)
end


# ============================================================
# PAYMENT HASH
# ============================================================

function create_payment_secret()

    raw =
        string(
            uuid4(),
            "-",
            time_ns(),
            "-",
            rand(UInt64)
        )

    return bytes2hex(
        sha256(
            Vector{UInt8}(
                codeunits(raw)
            )
        )
    )
end


# ============================================================
# MERCHANT CREATION
# ============================================================

function register_merchant!(

    rail::LightningRail,

    name::String

)

    id =
        "merchant-" *
        string(uuid4())

    merchant =
        Merchant(

            id,

            name,

            0,

            0,

            0,

            0
        )

    rail.merchants[id] =
        merchant

    println(
        "Merchant registered: ",
        id
    )

    return id
end


# ============================================================
# INVOICE CREATION
# ============================================================

function create_invoice!(

    rail::LightningRail,

    merchant_id::String,

    amount_msat::Int64,

    description::String;

    expiry::Int = DEFAULT_INVOICE_EXPIRY

)

    if !haskey(
        rail.merchants,
        merchant_id
    )

        error("Unknown merchant")
    end


    invoice_id =
        "inv-" *
        string(uuid4())


    payment_hash =
        create_payment_secret()


    created =
        now()


    expires =
        created +
        Second(expiry)


    # --------------------------------------------------------
    # IMPORTANT:
    #
    # This is an application-level representation.
    #
    # A real BOLT-11 invoice must be generated and signed
    # by the Lightning node.
    # --------------------------------------------------------

    payment_request =
        "ln-" *
        string(rail.network) *
        "-" *
        string(amount_msat) *
        "-" *
        payment_hash


    invoice =
        Invoice(

            invoice_id,

            payment_hash,

            amount_msat,

            description,

            created,

            expires,

            CREATED,

            payment_request,

            nothing,

            nothing
        )


    rail.invoices[invoice_id] =
        invoice


    println()
    println(
        "Invoice created: ",
        invoice_id
    )

    println(
        "Amount: ",
        amount_msat,
        " msat"
    )

    println(
        "Payment request: ",
        payment_request
    )


    return invoice_id
end


# ============================================================
# INVOICE STATUS
# ============================================================

function invoice_expired(

    invoice::Invoice

)

    return now() >=
           invoice.expires_at
end


function get_invoice(

    rail::LightningRail,

    invoice_id::String

)

    if !haskey(
        rail.invoices,
        invoice_id
    )

        return nothing
    end

    invoice =
        rail.invoices[
            invoice_id
        ]


    if invoice.status == CREATED &&
       invoice_expired(invoice)

        invoice.status =
            EXPIRED
    end


    return invoice
end


# ============================================================
# CHANNEL MANAGEMENT
# ============================================================

function add_channel!(

    rail::LightningRail,

    remote_node::String,

    capacity_msat::Int64,

    local_balance_msat::Int64;

    fee_base_msat::Int64 = 1000,

    fee_rate_ppm::Int64 = 100

)

    if local_balance_msat >
       capacity_msat

        error(
            "Local balance exceeds capacity"
        )
    end


    id =
        "chan-" *
        string(uuid4())


    remote_balance =
        capacity_msat -
        local_balance_msat


    channel =
        Channel(

            id,

            rail.node_id,

            remote_node,

            capacity_msat,

            local_balance_msat,

            remote_balance,

            true,

            fee_base_msat,

            fee_rate_ppm
        )


    rail.channels[id] =
        channel


    println(
        "Channel added: ",
        id
    )


    return id
end


# ============================================================
# ROUTING FEE
# ============================================================

function calculate_fee(

    channel::Channel,

    amount_msat::Int64

)

    proportional =
        (
            amount_msat *
            channel.fee_rate_ppm
        ) ÷ 1_000_000


    return channel.fee_base_msat +
           proportional
end


# ============================================================
# SELECT ROUTE
# ============================================================

function select_route(

    rail::LightningRail,

    amount_msat::Int64

)

    candidates =
        Channel[]


    for channel in
        values(rail.channels)

        if !channel.active
            continue
        end

        if channel.local_balance_msat <
           amount_msat

            continue
        end

        push!(
            candidates,
            channel
        )
    end


    if isempty(candidates)

        return nothing
    end


    # Choose lowest estimated fee.

    sort!(
        candidates,
        by = c ->
            calculate_fee(
                c,
                amount_msat
            )
    )


    return candidates[1]
end


# ============================================================
# PAYMENT ATTEMPT
# ============================================================

function attempt_payment!(

    rail::LightningRail,

    payment::Payment,

    invoice::Invoice

)

    payment.attempts += 1


    channel =
        select_route(
            rail,
            invoice.amount_msat
        )


    if channel === nothing

        payment.status =
            FAILED

        payment.failure_reason =
            "NO_ROUTE"

        return false
    end


    fee =
        calculate_fee(
            channel,
            invoice.amount_msat
        )


    total =
        invoice.amount_msat +
        fee


    if channel.local_balance_msat <
       total

        payment.status =
            FAILED

        payment.failure_reason =
            "INSUFFICIENT_CHANNEL_BALANCE"

        return false
    end


    # --------------------------------------------------------
    # SIMULATED ROUTING
    # --------------------------------------------------------

    println()
    println(
        "Routing payment..."
    )

    println(
        "Channel: ",
        channel.id
    )

    println(
        "Amount: ",
        invoice.amount_msat,
        " msat"
    )

    println(
        "Fee: ",
        fee,
        " msat"
    )


    # In a real Lightning network, this is where the actual
    # node implementation performs the payment protocol.
    #
    # We deliberately don't implement cryptographic HTLC/
    # onion-routing machinery here.


    channel.local_balance_msat -=
        total


    channel.remote_balance_msat +=
        total


    payment.fee_msat =
        fee


    payment.total_msat =
        total


    return true
end


# ============================================================
# SETTLE INVOICE
# ============================================================

function settle_invoice!(

    rail::LightningRail,

    invoice::Invoice,

    payment::Payment

)

    merchant =
        find_merchant_for_invoice(
            rail,
            invoice.id
        )


    if merchant === nothing

        payment.status =
            FAILED

        payment.failure_reason =
            "MERCHANT_NOT_FOUND"

        return false
    end


    # --------------------------------------------------------
    # Settlement
    # --------------------------------------------------------

    merchant.balance_msat +=
        invoice.amount_msat


    merchant.total_received_msat +=
        invoice.amount_msat


    merchant.transaction_count += 1


    invoice.status =
        SUCCEEDED


    invoice.paid_at =
        now()


    invoice.preimage =
        create_payment_secret()


    payment.status =
        SUCCEEDED


    payment.completed_at =
        now()


    rail.total_volume_msat +=
        invoice.amount_msat


    rail.total_fees_msat +=
        payment.fee_msat


    # --------------------------------------------------------
    # Ledger entry
    # --------------------------------------------------------

    push!(
        rail.ledger,

        Dict(

            "id" =>
                string(uuid4()),

            "timestamp" =>
                string(now()),

            "type" =>
                "LIGHTNING_PAYMENT",

            "invoice_id" =>
                invoice.id,

            "payment_id" =>
                payment.id,

            "merchant_id" =>
                merchant.id,

            "amount_msat" =>
                invoice.amount_msat,

            "fee_msat" =>
                payment.fee_msat,

            "status" =>
                "SETTLED"
        )
    )


    return true
end


# ============================================================
# INVOICE -> MERCHANT MAPPING
# ============================================================

const INVOICE_MERCHANT =
    Dict{String,String}()


function assign_invoice_to_merchant!(

    rail::LightningRail,

    invoice_id::String,

    merchant_id::String

)

    INVOICE_MERCHANT[
        invoice_id
    ] = merchant_id
end


function find_merchant_for_invoice(

    rail::LightningRail,

    invoice_id::String

)

    if !haskey(
        INVOICE_MERCHANT,
        invoice_id
    )

        return nothing
    end


    merchant_id =
        INVOICE_MERCHANT[
            invoice_id
        ]


    return get(
        rail.merchants,
        merchant_id,
        nothing
    )
end


# ============================================================
# PAY INVOICE
# ============================================================

function pay_invoice!(

    rail::LightningRail,

    invoice_id::String

)

    invoice =
        get_invoice(
            rail,
            invoice_id
        )


    if invoice === nothing

        error(
            "Invoice not found"
        )
    end


    if invoice.status != CREATED

        println(
            "Invoice cannot be paid. Status: ",
            invoice.status
        )

        return nothing
    end


    if invoice_expired(invoice)

        invoice.status =
            EXPIRED

        return nothing
    end


    payment_id =
        "pay-" *
        string(uuid4())


    payment =
        Payment(

            payment_id,

            invoice.id,

            invoice.amount_msat,

            0,

            0,

            PENDING,

            now(),

            nothing,

            nothing,

            0
        )


    rail.payments[payment_id] =
        payment


    success = false


    for attempt in
        1:MAX_PAYMENT_RETRIES

        success =
            attempt_payment!(
                rail,
                payment,
                invoice
            )


        if success
            break
        end


        println(
            "Payment attempt ",
            attempt,
            " failed."
        )
    end


    if !success

        payment.status =
            FAILED

        return payment_id
    end


    settle_invoice!(
        rail,
        invoice,
        payment
    )


    println()
    println(
        "PAYMENT SETTLED"
    )

    println(
        "Payment ID: ",
        payment.id
    )

    println(
        "Amount: ",
        payment.amount_msat,
        " msat"
    )

    println(
        "Fee: ",
        payment.fee_msat,
        " msat"
    )


    return payment_id
end


# ============================================================
# PAYMENT LOOKUP
# ============================================================

function payment_status(

    rail::LightningRail,

    payment_id::String

)

    if !haskey(
        rail.payments,
        payment_id
    )

        return nothing
    end


    return rail.payments[
        payment_id
    ]
end


# ============================================================
# MERCHANT BALANCE
# ============================================================

function merchant_balance(

    rail::LightningRail,

    merchant_id::String

)

    merchant =
        rail.merchants[
            merchant_id
        ]


    return merchant.balance_msat
end


# ============================================================
# RAIL DASHBOARD
# ============================================================

function dashboard(

    rail::LightningRail

)

    println()
    println(
        "============================================================"
    )

    println(
        "                 RHINO LIGHTNING RAILS"
    )

    println(
        "============================================================"
    )

    println(
        "Node:          ",
        rail.node_id
    )

    println(
        "Network:       ",
        rail.network
    )

    println(
        "Channels:      ",
        length(rail.channels)
    )

    println(
        "Invoices:      ",
        length(rail.invoices)
    )

    println(
        "Payments:      ",
        length(rail.payments)
    )

    println(
        "Merchants:     ",
        length(rail.merchants)
    )

    println(
        "Volume:        ",
        rail.total_volume_msat,
        " msat"
    )

    println(
        "Fees:          ",
        rail.total_fees_msat,
        " msat"
    )

    println(
        "============================================================"
    )

end


# ============================================================
# CHANNEL DASHBOARD
# ============================================================

function channel_dashboard(

    rail::LightningRail

)

    println()
    println(
        "CHANNELS"
    )

    println(
        "------------------------------------------------------------"
    )


    for channel in
        values(rail.channels)

        println(
            channel.id,
            " | ",
            channel.remote_node,
            " | local=",
            channel.local_balance_msat,
            " msat",
            " | remote=",
            channel.remote_balance_msat,
            " msat",
            " | active=",
            channel.active
        )
    end
end


# ============================================================
# MERCHANT DASHBOARD
# ============================================================

function merchant_dashboard(

    rail::LightningRail

)

    println()
    println(
        "MERCHANTS"
    )

    println(
        "------------------------------------------------------------"
    )


    for merchant in
        values(rail.merchants)

        println(
            merchant.id,
            " | ",
            merchant.name,
            " | balance=",
            merchant.balance_msat,
            " msat",
            " | received=",
            merchant.total_received_msat,
            " msat"
        )
    end
end


# ============================================================
# LEDGER
# ============================================================

function print_ledger(

    rail::LightningRail

)

    println()
    println(
        "PAYMENT LEDGER"
    )

    println(
        "------------------------------------------------------------"
    )


    for entry in
        rail.ledger

        println(
            entry["timestamp"],
            " | ",
            entry["type"],
            " | ",
            entry["amount_msat"],
            " msat",
            " | ",
            entry["status"]
        )
    end
end


# ============================================================
# DEMONSTRATION
# ============================================================

function demonstration()

    rail =
        create_rail(
            "rhino-bank-ln-01";
            network = :regtest
        )


    # --------------------------------------------------------
    # MERCHANT
    # --------------------------------------------------------

    merchant =
        register_merchant!(
            rail,
            "Rhino Vending Ltd"
        )


    # --------------------------------------------------------
    # CHANNEL
    # --------------------------------------------------------

    add_channel!(
        rail,
        "routing-node-01",
        sats_to_msat(5_000_000),
        sats_to_msat(2_500_000);

        fee_base_msat = 1000,

        fee_rate_ppm = 100
    )


    # --------------------------------------------------------
    # CREATE INVOICE
    # --------------------------------------------------------

    invoice =
        create_invoice!(
            rail,
            merchant,
            sats_to_msat(25),
            "Coffee vending machine"
        )


    assign_invoice_to_merchant!(
        rail,
        invoice,
        merchant
    )


    # --------------------------------------------------------
    # PAY
    # --------------------------------------------------------

    payment =
        pay_invoice!(
            rail,
            invoice
        )


    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    dashboard(rail)

    channel_dashboard(rail)

    merchant_dashboard(rail)

    print_ledger(rail)


    println()
    println(
        "Merchant balance: ",
        merchant_balance(
            rail,
            merchant
        ),
        " msat"
    )

    println()
    println(
        "Simulation complete."
    )

end


# ============================================================
# START
# ============================================================

demonstration()
