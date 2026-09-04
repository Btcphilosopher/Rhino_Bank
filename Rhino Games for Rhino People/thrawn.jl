# ============================================================
# THRAWN.jl
# Grand Admiral Thrawn Strategic AI
#
# Fictional game AI / simulation
# ============================================================

using Random
using Statistics

# ------------------------------------------------------------
# ENUMERATIONS
# ------------------------------------------------------------

@enum Faction
    IMPERIAL
    REBEL
    REPUBLIC
    NEUTRAL
end

@enum TacticalAction
    ATTACK
    DEFEND
    RETREAT
    FLANK
    AMBUSH
    REINFORCE
    DECEIVE
    WAIT
end

# ------------------------------------------------------------
# UNIT
# ------------------------------------------------------------

mutable struct Unit

    name::String
    faction::Faction

    strength::Float64
    speed::Float64
    armor::Float64
    morale::Float64

    position::Tuple{Float64,Float64}

end


# ------------------------------------------------------------
# ENEMY PROFILE
# ------------------------------------------------------------

mutable struct EnemyProfile

    name::String

    aggression::Float64
    discipline::Float64
    mobility::Float64
    patience::Float64

    preferred_action::TacticalAction

    observed_patterns::Vector{String}

    confidence::Float64

end


# ------------------------------------------------------------
# BATTLEFIELD
# ------------------------------------------------------------

mutable struct Battlefield

    width::Float64
    height::Float64

    terrain::Matrix{Float64}

    imperial_units::Vector{Unit}
    enemy_units::Vector{Unit}

end


# ------------------------------------------------------------
# THRAWN AI
# ------------------------------------------------------------

mutable struct ThrawnAI

    name::String

    strategic_intelligence::Float64
    tactical_intelligence::Float64

    patience::Float64
    deception_skill::Float64

    enemy_profiles::Dict{String,EnemyProfile}

    known_patterns::Vector{String}

end


# ------------------------------------------------------------
# CONSTRUCTOR
# ------------------------------------------------------------

function create_thrawn()

    return ThrawnAI(

        "Grand Admiral Thrawn",

        0.99,
        0.98,

        0.98,
        0.95,

        Dict{String,EnemyProfile}(),

        String[]
    )

end


# ============================================================
# CULTURAL ANALYSIS
# ============================================================

function analyze_culture(
    ai::ThrawnAI,
    culture::String
)

    println("\n[THRAWN] Studying culture: ", culture)

    patterns = Dict(

        "militaristic" => (
            aggression = 0.85,
            discipline = 0.90,
            patience = 0.35
        ),

        "merchant" => (
            aggression = 0.35,
            discipline = 0.60,
            patience = 0.80
        ),

        "revolutionary" => (
            aggression = 0.75,
            discipline = 0.45,
            patience = 0.40
        ),

        "isolationist" => (
            aggression = 0.25,
            discipline = 0.80,
            patience = 0.95
        )
    )

    if haskey(patterns, culture)

        p = patterns[culture]

        println(
            "[THRAWN] Behavioural model generated."
        )

        return p

    end

    println(
        "[THRAWN] Insufficient cultural information."
    )

    return (
        aggression = 0.50,
        discipline = 0.50,
        patience = 0.50
    )

end


# ============================================================
# OBSERVE ENEMY
# ============================================================

function observe_enemy(
    ai::ThrawnAI,
    enemy::EnemyProfile,
    action::TacticalAction
)

    push!(
        enemy.observed_patterns,
        string(action)
    )

    # Bayesian-like confidence increase.
    enemy.confidence = min(
        1.0,
        enemy.confidence + 0.05
    )

    println(
        "[THRAWN] Observed ",
        enemy.name,
        " → ",
        action
    )

end


# ============================================================
# PATTERN DETECTION
# ============================================================

function detect_pattern(
    ai::ThrawnAI,
    enemy::EnemyProfile
)

    actions = enemy.observed_patterns

    if length(actions) < 3

        return nothing

    end

    counts = Dict{String,Int}()

    for action in actions

        counts[action] =
            get(counts, action, 0) + 1

    end

    dominant =
        argmax(counts)

    push!(
        ai.known_patterns,
        dominant
    )

    println(
        "[THRAWN] Pattern identified: ",
        dominant
    )

    return dominant

end


# ============================================================
# PREDICT NEXT MOVE
# ============================================================

function predict_enemy_move(
    ai::ThrawnAI,
    enemy::EnemyProfile
)

    aggression = enemy.aggression
    patience = enemy.patience
    mobility = enemy.mobility

    scores = Dict(

        ATTACK =>
            aggression * 0.55 +
            (1 - patience) * 0.20,

        DEFEND =>
            (1 - aggression) * 0.35 +
            patience * 0.35,

        FLANK =>
            mobility * 0.50 +
            aggression * 0.20,

        RETREAT =>
            (1 - morale_factor(enemy)) * 0.5,

        AMBUSH =>
            patience * 0.45 +
            mobility * 0.25,

        WAIT =>
            patience * 0.40,

        REINFORCE =>
            0.25,

        DECEIVE =>
            0.20
    )

    prediction =
        argmax(scores)

    println(
        "[THRAWN] Predicted enemy action: ",
        prediction
    )

    return prediction

end


# ------------------------------------------------------------
# MORALE FACTOR
# ------------------------------------------------------------

function morale_factor(
    enemy::EnemyProfile
)

    return (
        enemy.discipline * 0.6 +
        enemy.patience * 0.4
    )

end


# ============================================================
# BATTLEFIELD EVALUATION
# ============================================================

function evaluate_battlefield(
    ai::ThrawnAI,
    battlefield::Battlefield
)

    imperial_power = sum(
        u.strength * u.morale
        for u in battlefield.imperial_units
    )

    enemy_power = sum(
        u.strength * u.morale
        for u in battlefield.enemy_units
    )

    power_ratio =
        imperial_power /
        max(enemy_power, 1.0)

    println(
        "\n[THRAWN] Battlefield analysis"
    )

    println(
        "Imperial combat power: ",
        round(imperial_power, digits=2)
    )

    println(
        "Enemy combat power: ",
        round(enemy_power, digits=2)
    )

    println(
        "Power ratio: ",
        round(power_ratio, digits=2)
    )

    return power_ratio

end


# ============================================================
# TACTICAL DECISION
# ============================================================

function choose_action(
    ai::ThrawnAI,
    battlefield::Battlefield,
    predicted_enemy_action::TacticalAction
)

    ratio =
        evaluate_battlefield(
            ai,
            battlefield
        )

    if predicted_enemy_action == ATTACK

        if ratio > 1.5

            return AMBUSH

        elseif ratio > 0.9

            return DEFEND

        else

            return RETREAT

        end

    elseif predicted_enemy_action == DEFEND

        if ratio > 1.2

            return FLANK

        else

            return WAIT

        end

    elseif predicted_enemy_action == FLANK

        return REINFORCE

    elseif predicted_enemy_action == RETREAT

        return ATTACK

    else

        return DECEIVE

    end

end


# ============================================================
# DECEPTION ENGINE
# ============================================================

function create_deception(
    ai::ThrawnAI,
    actual_action::TacticalAction
)

    println(
        "\n[THRAWN] Creating deception strategy."
    )

    deception = Dict(

        "visible_action" => DEFEND,

        "actual_action" => actual_action,

        "decoy_strength" => 0.65,

        "communications_noise" => 0.35,

        "false_retreat" => true

    )

    return deception

end


# ============================================================
# FLEET DEPLOYMENT
# ============================================================

function deploy_fleet(
    ai::ThrawnAI,
    battlefield::Battlefield,
    action::TacticalAction
)

    println(
        "\n[THRAWN] Fleet order: ",
        action
    )

    if action == ATTACK

        for unit in battlefield.imperial_units

            unit.position = (
                unit.position[1] + 10,
                unit.position[2]
            )

        end

    elseif action == RETREAT

        for unit in battlefield.imperial_units

            unit.position = (
                unit.position[1] - 10,
                unit.position[2]
            )

        end

    elseif action == FLANK

        for (i, unit) in
            enumerate(battlefield.imperial_units)

            unit.position = (
                unit.position[1],
                unit.position[2] +
                15 * i
            )

        end

    elseif action == AMBUSH

        println(
            "[THRAWN] Fleet concealed."
        )

    elseif action == DECEIVE

        println(
            "[THRAWN] Executing deception."
        )

    end

end


# ============================================================
# COMPLETE THRAWN DECISION CYCLE
# ============================================================

function strategic_cycle(
    ai::ThrawnAI,
    battlefield::Battlefield,
    enemy::EnemyProfile
)

    println(
        "\n=========================================="
    )

    println(
        "        THRAWN STRATEGIC CYCLE"
    )

    println(
        "=========================================="
    )

    # 1. Observe
    predicted =
        predict_enemy_move(
            ai,
            enemy
        )

    # 2. Evaluate battlefield
    ratio =
        evaluate_battlefield(
            ai,
            battlefield
        )

    # 3. Select response
    action =
        choose_action(
            ai,
            battlefield,
            predicted
        )

    # 4. Deception when appropriate
    if action == DECEIVE

        deception =
            create_deception(
                ai,
                ATTACK
            )

        println(
            "[THRAWN] Deception parameters: ",
            deception
        )

    end

    # 5. Deploy
    deploy_fleet(
        ai,
        battlefield,
        action
    )

    println(
        "\n[THRAWN] Strategic cycle complete."
    )

    return action

end


# ============================================================
# DEMONSTRATION
# ============================================================

function demo()

    thrawn =
        create_thrawn()

    enemy =
        EnemyProfile(

            "Rebel Commander",

            0.75,   # aggression
            0.55,   # discipline
            0.85,   # mobility
            0.40,   # patience

            ATTACK,

            String[],

            0.30
        )

    thrawn.enemy_profiles[
        enemy.name
    ] = enemy

    imperial = [

        Unit(
            "Imperial Star Destroyer",
            IMPERIAL,
            100.0,
            0.50,
            0.90,
            0.95,
            (20.0, 50.0)
        ),

        Unit(
            "TIE Defender Squadron",
            IMPERIAL,
            35.0,
            0.95,
            0.40,
            0.90,
            (25.0, 50.0)
        ),

        Unit(
            "Interdictor",
            IMPERIAL,
            70.0,
            0.30,
            0.85,
            0.90,
            (15.0, 45.0)
        )
    ]

    rebels = [

        Unit(
            "Rebel Cruiser",
            REBEL,
            80.0,
            0.70,
            0.60,
            0.75,
            (80.0, 50.0)
        ),

        Unit(
            "X-Wing Squadron",
            REBEL,
            30.0,
            0.95,
            0.35,
            0.80,
            (75.0, 55.0)
        )
    ]

    battlefield =
        Battlefield(

            100.0,
            100.0,

            rand(20,20),

            imperial,
            rebels
        )

    # Observe several enemy movements.

    observe_enemy(
        thrawn,
        enemy,
        ATTACK
    )

    observe_enemy(
        thrawn,
        enemy,
        FLANK
    )

    observe_enemy(
        thrawn,
        enemy,
        ATTACK
    )

    detect_pattern(
        thrawn,
        enemy
    )

    action =
        strategic_cycle(
            thrawn,
            battlefield,
            enemy
        )

    println(
        "\nFINAL THRAWN DECISION: ",
        action
    )

end


demo()
