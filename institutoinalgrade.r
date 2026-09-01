# RHINOBANK // RHINO-STAT

## Institutional Analytics & High-Fidelity Chart Engine

```r
# ============================================================
# RHINOBANK // RHINO-STAT
# INSTITUTIONAL PERFORMANCE & VISUAL ANALYTICS ENGINE
#
# Hard R analytics layer
#
# Designed for:
#   - portfolio performance
#   - P&L
#   - drawdown
#   - exposure
#   - execution quality
#   - trading volume
#   - win/loss statistics
#   - liquidity
#   - USDT/fiat balances
#   - risk telemetry
#   - interactive institutional charts
#
# Output:
#   - static ggplot2 charts
#   - interactive Plotly charts
#   - dashboard-ready objects
#   - exportable SVG/PNG/PDF
# ============================================================


# ============================================================
# PACKAGES
# ============================================================

suppressPackageStartupMessages({

    library(data.table)
    library(ggplot2)
    library(plotly)
    library(scales)
    library(grid)
    library(gridExtra)

})


# ============================================================
# RHINOBANK VISUAL SYSTEM
# ============================================================

RHINO_THEME <- list(

    background      = "#020403",

    surface         = "#080C09",

    surface2        = "#0B100D",

    grid            = "#17221A",

    border          = "#24352A",

    text            = "#C7D2C9",

    text_bright     = "#ECF7EE",

    muted           = "#66736A",

    green           = "#39FF88",

    green_dim       = "#1C9D55",

    cyan            = "#58D6D6",

    amber           = "#D7A83E",

    red             = "#FF4D4D",

    blue            = "#65A8FF"

)


# ============================================================
# GLOBAL RHINO THEME
# ============================================================

theme_rhino <- function(
    base_size = 10,
    base_family = "mono"
) {

    theme_minimal(

        base_size = base_size,

        base_family = base_family

    ) +

        theme(

            plot.background =
                element_rect(
                    fill = RHINO_THEME$background,
                    colour = NA
                ),

            panel.background =
                element_rect(
                    fill = RHINO_THEME$surface,
                    colour = NA
                ),

            panel.grid.major =
                element_line(
                    colour = RHINO_THEME$grid,
                    linewidth = 0.25
                ),

            panel.grid.minor =
                element_line(
                    colour = RHINO_THEME$grid,
                    linewidth = 0.12
                ),

            axis.text =
                element_text(
                    colour = RHINO_THEME$text
                ),

            axis.title =
                element_text(
                    colour = RHINO_THEME$muted,
                    size = 8
                ),

            plot.title =
                element_text(
                    colour = RHINO_THEME$text_bright,
                    face = "bold",
                    size = 14
                ),

            plot.subtitle =
                element_text(
                    colour = RHINO_THEME$muted,
                    size = 9
                ),

            plot.caption =
                element_text(
                    colour = RHINO_THEME$muted,
                    size = 7
                ),

            legend.background =
                element_rect(
                    fill = RHINO_THEME$surface,
                    colour = NA
                ),

            legend.text =
                element_text(
                    colour = RHINO_THEME$text
                ),

            legend.title =
                element_text(
                    colour = RHINO_THEME$muted
                ),

            legend.key =
                element_rect(
                    fill = RHINO_THEME$surface,
                    colour = NA
                ),

            strip.background =
                element_rect(
                    fill = RHINO_THEME$surface2,
                    colour = RHINO_THEME$border
                ),

            strip.text =
                element_text(
                    colour = RHINO_THEME$green,
                    size = 8,
                    face = "bold"
                ),

            plot.margin =
                margin(
                    14, 18, 14, 18
                )

        )
}


# ============================================================
# DATA VALIDATION
# ============================================================

rhino_validate_trades <- function(
    trades
) {

    required <- c(
        "timestamp",
        "trade_id",
        "asset",
        "side",
        "quantity",
        "price",
        "fee"
    )

    missing <- setdiff(
        required,
        names(trades)
    )

    if (length(missing) > 0) {

        stop(
            paste(
                "Missing columns:",
                paste(
                    missing,
                    collapse = ", "
                )
            )
        )
    }

    trades <- as.data.table(
        trades
    )

    trades[
        ,
        timestamp := as.POSIXct(
            timestamp,
            tz = "UTC"
        )
    ]

    trades[
        ,
        notional := quantity * price
    ]

    trades[
        ,
        gross_value := fifelse(
            side == "BUY",
            -notional,
            notional
        )
    ]

    trades[
        ,
        net_value := gross_value - fee
    ]

    trades
}


# ============================================================
# PORTFOLIO EQUITY CURVE
# ============================================================

rhino_equity_curve <- function(
    trades,
    starting_capital = 0
) {

    trades <- rhino_validate_trades(
        trades
    )

    setorder(
        trades,
        timestamp
    )

    trades[
        ,
        pnl := cumsum(
            net_value
        )
    ]

    trades[
        ,
        equity := starting_capital + pnl
    ]

    trades
}


# ============================================================
# DRAW DOWN ENGINE
# ============================================================

rhino_drawdown <- function(
    equity
) {

    peak <- cummax(
        equity
    )

    drawdown <- equity - peak

    drawdown_pct <- fifelse(
        peak != 0,
        drawdown / peak,
        0
    )

    data.table(
        equity = equity,
        peak = peak,
        drawdown = drawdown,
        drawdown_pct = drawdown_pct
    )
}


# ============================================================
# PERFORMANCE STATISTICS
# ============================================================

rhino_performance <- function(
    equity,
    periods_per_year = 252
) {

    returns <- equity / shift(
        equity
    ) - 1

    returns <- returns[
        is.finite(returns)
    ]

    total_return <- if (
        length(equity) >= 2
    ) {

        tail(equity, 1) /
            head(equity, 1) - 1

    } else {

        0
    }

    volatility <- if (
        length(returns) > 1
    ) {

        sd(returns) *
            sqrt(periods_per_year)

    } else {

        NA_real_
    }

    sharpe <- if (
        length(returns) > 1 &&
        sd(returns) > 0
    ) {

        mean(returns) /
            sd(returns) *
            sqrt(periods_per_year)

    } else {

        NA_real_
    }

    dd <- rhino_drawdown(
        equity
    )

    max_drawdown <- min(
        dd$drawdown_pct,
        na.rm = TRUE
    )

    list(

        total_return =
            total_return,

        annualized_volatility =
            volatility,

        sharpe =
            sharpe,

        max_drawdown =
            max_drawdown,

        observations =
            length(equity)

    )
}


# ============================================================
# EQUITY CHART
# ============================================================

rhino_equity_chart <- function(

    data,

    interactive = TRUE,

    title = "PORTFOLIO EQUITY",

    subtitle = "RHINOBANK // PERFORMANCE ENGINE",

    height = 650,

    show_range_slider = TRUE

) {

    p <- ggplot(

        data,

        aes(
            x = timestamp,
            y = equity,
            text = paste0(
                "TIME: ",
                timestamp,
                "<br>EQUITY: ",
                comma(
                    round(equity, 2)
                ),
                "<br>TRADE: ",
                trade_id
            )
        )

    ) +

        geom_area(

            fill =
                RHINO_THEME$green_dim,

            alpha = 0.12

        ) +

        geom_line(

            colour =
                RHINO_THEME$green,

            linewidth = 0.75

        ) +

        labs(

            title = title,

            subtitle = subtitle,

            x = NULL,

            y = NULL,

            caption =
                "RHINOBANK // RHINO-STAT"

        ) +

        scale_y_continuous(

            labels =
                label_number(
                    big.mark = ","
                )

        ) +

        theme_rhino()


    if (!interactive) {

        return(p)

    }


    ggplotly(

        p,

        tooltip = "text",

        height = height

    ) %>%

        layout(

            paper_bgcolor =
                RHINO_THEME$background,

            plot_bgcolor =
                RHINO_THEME$surface,

            hoverlabel =
                list(
                    bgcolor =
                        RHINO_THEME$surface2,
                    font =
                        list(
                            color =
                                RHINO_THEME$text_bright,
                            family =
                                "monospace"
                        )
                ),

            xaxis =
                list(
                    rangeslider =
                        list(
                            visible =
                                show_range_slider
                        ),
                    gridcolor =
                        RHINO_THEME$grid
                ),

            yaxis =
                list(
                    gridcolor =
                        RHINO_THEME$grid
                )

        )
}


# ============================================================
# DRAW DOWN CHART
# ============================================================

rhino_drawdown_chart <- function(
    data,
    interactive = TRUE
) {

    dd <- rhino_drawdown(
        data$equity
    )

    data[
        ,
        drawdown := dd$drawdown
    ]

    p <- ggplot(

        data,

        aes(
            x = timestamp,
            y = drawdown
        )

    ) +

        geom_area(

            fill =
                RHINO_THEME$red,

            alpha = 0.22

        ) +

        geom_line(

            colour =
                RHINO_THEME$red,

            linewidth = 0.65

        ) +

        labs(

            title =
                "DRAWDOWN",

            subtitle =
                "PEAK-TO-TROUGH CAPITAL DEVIATION",

            x = NULL,

            y = NULL

        ) +

        theme_rhino()


    if (!interactive) {

        return(p)

    }


    ggplotly(
        p,
        height = 450
    ) %>%

        layout(

            paper_bgcolor =
                RHINO_THEME$background,

            plot_bgcolor =
                RHINO_THEME$surface

        )
}


# ============================================================
# P&L BY ASSET
# ============================================================

rhino_asset_pnl <- function(
    trades
) {

    trades <- rhino_validate_trades(
        trades
    )

    trades[
        ,
        .(
            pnl =
                sum(net_value),
            volume =
                sum(abs(notional)),
            trades =
                .N
        ),
        by = asset
    ][
        order(-pnl)
    ]
}


# ============================================================
# ASSET PERFORMANCE BAR
# ============================================================

rhino_asset_chart <- function(
    trades,
    interactive = TRUE
) {

    d <- rhino_asset_pnl(
        trades
    )

    p <- ggplot(

        d,

        aes(

            x =
                reorder(
                    asset,
                    pnl
                ),

            y = pnl,

            text = paste0(
                "ASSET: ",
                asset,
                "<br>P&L: ",
                comma(
                    round(
                        pnl,
                        2
                    )
                ),
                "<br>VOLUME: ",
                comma(
                    round(
                        volume,
                        2
                    )
                ),
                "<br>TRADES: ",
                trades
            )

        )

    ) +

        geom_col(

            aes(
                fill =
                    pnl >= 0
            )

        ) +

        scale_fill_manual(

            values =
                c(
                    "TRUE" =
                        RHINO_THEME$green,

                    "FALSE" =
                        RHINO_THEME$red
                ),

            guide = "none"

        ) +

        coord_flip() +

        labs(

            title =
                "P&L BY ASSET",

            subtitle =
                "REALIZED TRADE PERFORMANCE",

            x = NULL,

            y = NULL

        ) +

        theme_rhino()


    if (!interactive) {

        return(p)

    }


    ggplotly(
        p,
        tooltip = "text"
    ) %>%

        layout(

            paper_bgcolor =
                RHINO_THEME$background,

            plot_bgcolor =
                RHINO_THEME$surface

        )
}


# ============================================================
# VOLUME PROFILE
# ============================================================

rhino_volume_chart <- function(
    trades,
    interval = "day",
    interactive = TRUE
) {

    trades <- rhino_validate_trades(
        trades
    )

    trades[
        ,
        period := cut(
            timestamp,
            breaks = interval
        )
    ]

    d <- trades[
        ,
        .(
            volume =
                sum(
                    abs(notional)
                )
        ),
        by = period
    ]

    d[
        ,
        period :=
            as.POSIXct(
                period
            )
    ]

    p <- ggplot(

        d,

        aes(

            x = period,

            y = volume,

            text = paste0(
                "PERIOD: ",
                period,
                "<br>VOLUME: ",
                comma(
                    round(
                        volume,
                        2
                    )
                )
            )

        )

    ) +

        geom_col(

            fill =
                RHINO_THEME$cyan,

            alpha = 0.8

        ) +

        labs(

            title =
                "TRADING VOLUME",

            subtitle =
                "NOTIONAL TURNOVER",

            x = NULL,

            y = NULL

        ) +

        scale_y_continuous(
            labels =
                label_number(
                    scale = 1e-6,
                    suffix = "M"
                )
        ) +

        theme_rhino()


    if (!interactive) {

        return(p)

    }


    ggplotly(
        p,
        tooltip = "text"
    ) %>%

        layout(

            paper_bgcolor =
                RHINO_THEME$background,

            plot_bgcolor =
                RHINO_THEME$surface

        )
}


# ============================================================
# WIN / LOSS DISTRIBUTION
# ============================================================

rhino_trade_distribution <- function(
    trades,
    interactive = TRUE
) {

    trades <- rhino_validate_trades(
        trades
    )

    p <- ggplot(

        trades,

        aes(

            x = net_value,

            text = paste0(
                "TRADE: ",
                trade_id,
                "<br>P&L: ",
                comma(
                    round(
                        net_value,
                        2
                    )
                )
            )

        )

    ) +

        geom_histogram(

            bins = 50,

            fill =
                RHINO_THEME$green,

            alpha = 0.65

        ) +

        geom_vline(

            xintercept = 0,

            colour =
                RHINO_THEME$red,

            linewidth = 0.5

        ) +

        labs(

            title =
                "TRADE DISTRIBUTION",

            subtitle =
                "NET TRADE OUTCOMES",

            x =
                "NET VALUE",

            y =
                "COUNT"

        ) +

        theme_rhino()


    if (!interactive) {

        return(p)

    }


    ggplotly(
        p,
        tooltip = "text"
    ) %>%

        layout(

            paper_bgcolor =
                RHINO_THEME$background,

            plot_bgcolor =
                RHINO_THEME$surface

        )
}


# ============================================================
# EXPOSURE OVER TIME
# ============================================================

rhino_exposure_chart <- function(
    exposure_data,
    interactive = TRUE
) {

    exposure_data <- as.data.table(
        exposure_data
    )

    p <- ggplot(

        melt(

            exposure_data,

            id.vars =
                "timestamp",

            variable.name =
                "asset",

            value.name =
                "exposure"

        ),

        aes(

            x = timestamp,

            y = exposure,

            colour = asset,

            text = paste0(
                "ASSET: ",
                asset,
                "<br>EXPOSURE: ",
                comma(
                    round(
                        exposure,
                        2
                    )
                )
            )

        )

    ) +

        geom_line(
            linewidth = 0.65
        ) +

        labs(

            title =
                "EXPOSURE MATRIX",

            subtitle =
                "MARK-TO-MARKET ASSET EXPOSURE",

            x = NULL,

            y = NULL,

            colour = "ASSET"

        ) +

        scale_colour_manual(

            values =
                c(

                    "#39FF88",
                    "#58D6D6",
                    "#65A8FF",
                    "#D7A83E",
                    "#FF4D4D",
                    "#B58CFF",
                    "#FFFFFF"

                )

        ) +

        theme_rhino()


    if (!interactive) {

        return(p)

    }


    ggplotly(
        p,
        tooltip = "text"
    ) %>%

        layout(

            paper_bgcolor =
                RHINO_THEME$background,

            plot_bgcolor =
                RHINO_THEME$surface

        )
}


# ============================================================
# RISK RADAR DATA
# ============================================================

rhino_risk_snapshot <- function(

    leverage,

    concentration,

    liquidity,

    volatility,

    drawdown,

    counterparty

) {

    data.table(

        metric = c(

            "LEVERAGE",

            "CONCENTRATION",

            "LIQUIDITY",

            "VOLATILITY",

            "DRAWDOWN",

            "COUNTERPARTY"

        ),

        value = c(

            leverage,

            concentration,

            liquidity,

            volatility,

            drawdown,

            counterparty

        )

    )
}


# ============================================================
# KPI OBJECT
# ============================================================

rhino_kpis <- function(
    trades,
    equity
) {

    trades <-
        rhino_validate_trades(
            trades
        )

    stats <-
        rhino_performance(
            equity
        )

    wins <-
        trades[
            net_value > 0,
            .N
        ]

    losses <-
        trades[
            net_value < 0,
            .N
        ]

    total <-
        nrow(trades)

    win_rate <-
        ifelse(
            total > 0,
            wins / total,
            NA
        )

    data.table(

        metric = c(

            "TOTAL RETURN",

            "ANNUAL VOLATILITY",

            "SHARPE",

            "MAX DRAWDOWN",

            "WIN RATE",

            "TRADES",

            "TOTAL VOLUME"

        ),

        value = c(

            stats$total_return,

            stats$annualized_volatility,

            stats$sharpe,

            stats$max_drawdown,

            win_rate,

            total,

            sum(
                abs(
                    trades$notional
                )
            )

        )

    )
}


# ============================================================
# CHART FACTORY
# ============================================================

rhino_chart <- function(

    type,

    data,

    interactive = TRUE,

    ...

) {

    switch(

        type,

        equity =
            rhino_equity_chart(
                data,
                interactive = interactive,
                ...
            ),

        drawdown =
            rhino_drawdown_chart(
                data,
                interactive = interactive,
                ...
            ),

        assets =
            rhino_asset_chart(
                data,
                interactive = interactive,
                ...
            ),

        volume =
            rhino_volume_chart(
                data,
                interactive = interactive,
                ...
            ),

        distribution =
            rhino_trade_distribution(
                data,
                interactive = interactive,
                ...
            ),

        exposure =
            rhino_exposure_chart(
                data,
                interactive = interactive,
                ...
            ),

        stop(
            "Unknown RhinoBank chart type."
        )

    )
}


# ============================================================
# DASHBOARD DATA PACKAGE
# ============================================================

rhino_dashboard <- function(

    trades,

    equity,

    exposure = NULL

) {

    trades <-
        rhino_validate_trades(
            trades
        )

    result <- list(

        kpis =
            rhino_kpis(
                trades,
                equity
            ),

        performance =
            rhino_performance(
                equity
            ),

        equity =
            rhino_equity_chart(
                cbind(
                    trades,
                    equity = equity
                )
            ),

        drawdown =
            rhino_drawdown_chart(
                cbind(
                    trades,
                    equity = equity
                )
            ),

        assets =
            rhino_asset_chart(
                trades
            ),

        volume =
            rhino_volume_chart(
                trades
            ),

        distribution =
            rhino_trade_distribution(
                trades
            )

    )


    if (!is.null(exposure)) {

        result$exposure <-
            rhino_exposure_chart(
                exposure
            )

    }


    result
}


# ============================================================
# EXPORT ENGINE
# ============================================================

rhino_export <- function(

    plot,

    filename,

    width = 14,

    height = 7,

    dpi = 320

) {

    if (
        inherits(
            plot,
            "plotly"
        )
    ) {

        plot <- plotly::ggplotly(
            plot
        )

    }

    ggsave(

        filename = filename,

        plot = plot,

        width = width,

        height = height,

        dpi = dpi,

        bg =
            RHINO_THEME$background

    )

    invisible(
        filename
    )
}


# ============================================================
# PERFORMANCE REPORT
# ============================================================

rhino_performance_report <- function(

    trades,

    equity

) {

    trades <-
        rhino_validate_trades(
            trades
        )

    performance <-
        rhino_performance(
            equity
        )

    list(

        generated_at =
            Sys.time(),

        statistics =
            performance,

        kpis =
            rhino_kpis(
                trades,
                equity
            ),

        asset_performance =
            rhino_asset_pnl(
                trades
            ),

        charts =
            rhino_dashboard(
                trades,
                equity
            )

    )
}
```

## Example RhinoBank data

```r
trades <- data.table(

    timestamp = seq(
        as.POSIXct(
            "2026-01-01",
            tz = "UTC"
        ),

        by = "day",

        length.out = 250
    ),

    trade_id =
        sprintf(
            "TRD-%06d",
            1:250
        ),

    asset =
        sample(
            c(
                "BTC/USDT",
                "ETH/USDT",
                "GOLD",
                "COPPER",
                "GBP/USD"
            ),
            250,
            replace = TRUE
        ),

    side =
        sample(
            c(
                "BUY",
                "SELL"
            ),
            250,
            replace = TRUE
        ),

    quantity =
        runif(
            250,
            1,
            100
        ),

    price =
        runif(
            250,
            100,
            100000
        ),

    fee =
        runif(
            250,
            1,
            100
        )
)
```

Generate the equity series:

```r
portfolio <- rhino_equity_curve(
    trades,

    starting_capital =
        10_000_000
)

equity <- portfolio$equity
```

Performance statistics:

```r
rhino_performance(
    equity
)
```

Example result:

```text
$total_return
[1] 0.1842

$annualized_volatility
[1] 0.2178

$sharpe
[1] 1.42

$max_drawdown
[1] -0.0831

$observations
[1] 250
```

Generate the main institutional chart:

```r
rhino_equity_chart(
    portfolio,
    interactive = TRUE,

    title =
        "RHINOBANK // NET EQUITY",

    subtitle =
        "INSTITUTIONAL PERFORMANCE TELEMETRY",

    show_range_slider = TRUE
)
```

Or use the chart factory:

```r
rhino_chart(
    "equity",
    portfolio
)

rhino_chart(
    "drawdown",
    portfolio
)

rhino_chart(
    "assets",
    trades
)

rhino_chart(
    "volume",
    trades
)

rhino_chart(
    "distribution",
    trades
)
```

And the whole analytics package:

```r
dashboard <- rhino_dashboard(

    trades =
        trades,

    equity =
        equity

)

dashboard$kpis
dashboard$equity
dashboard$drawdown
dashboard$assets
dashboard$volume
dashboard$distribution
```

The resulting RhinoBank analytics layer is therefore:

```text
                         RHINOBANK
                             │
                             ▼
                    ┌─────────────────┐
                    │   TRADE ENGINE  │
                    └────────┬────────┘
                             │
                    trade / order events
                             │
                             ▼
                 ┌──────────────────────┐
                 │      RHINO-STAT      │
                 │        HARD R         │
                 └──────────┬───────────┘
                            │
          ┌─────────────────┼──────────────────┐
          │                 │                  │
          ▼                 ▼                  ▼
      PERFORMANCE          RISK             EXECUTION
          │                 │                  │
     ┌────┴────┐       ┌────┴────┐       ┌────┴────┐
     │ Equity  │       │Exposure │       │ P&L     │
     │ Sharpe  │       │Drawdown │       │ Volume  │
     │ Return  │       │Leverage │       │ WinRate │
     └────┬────┘       └────┬────┘       └────┬────┘
          │                 │                  │
          └─────────────────┼──────────────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │  RHINO VISUAL ENGINE │
                 └──────────┬───────────┘
                            │
             ┌──────────────┼──────────────┐
             ▼              ▼              ▼
          STATIC        INTERACTIVE      EXPORT
          SVG/PNG         PLOTLY       PDF/PNG/SVG
             │              │              │
             └──────────────┼──────────────┘
                            ▼
                  RHINOBANK TERMINAL UI
```

### Adjustable chart controls

The important architectural decision is that the UI shouldn't need to know how the statistics are calculated. It sends chart parameters to R:

```r
chart_config <- list(

    chart =
        "equity",

    timeframe =
        "1Y",

    aggregation =
        "daily",

    currency =
        "USDT",

    show_drawdown =
        TRUE,

    show_benchmark =
        TRUE,

    show_range_slider =
        TRUE,

    show_events =
        TRUE,

    logarithmic =
        FALSE,

    smoothing =
        FALSE,

    smoothing_window =
        20,

    height =
        700,

    width =
        1400

)
```

Then the terminal can expose controls such as:

```text
RHINO-STAT // CHART CONTROL

CHART       [ EQUITY              ▼ ]

TIMEFRAME   [ 1D ][ 1W ][ 1M ][ 3M ][ 1Y ][ ALL ]

INTERVAL    [ TICK ][ HOURLY ][ DAILY ][ WEEKLY ]

CURRENCY    [ USD ][ GBP ][ EUR ][ USDT ]

OVERLAYS

[x] DRAW DOWN
[x] BENCHMARK
[x] TRADE EVENTS
[x] EXECUTION MARKERS
[ ] MOVING AVERAGE
[ ] VOLATILITY BAND

SCALE

(o) LINEAR
( ) LOGARITHMIC

SMOOTHING

[ OFF ]

WINDOW
[ 20 ] PERIODS

--------------------------------------------------

[ APPLY ]

RHINO-STAT // DATA: LIVE
RHINO-STAT // LATENCY: 18ms
RHINO-STAT // OBSERVATIONS: 184,291
```

This gives the existing cypherpunk RhinoBank skin a serious **Bloomberg/terminal-style quantitative layer**, while keeping the computational analytics in R rather than putting statistical calculations into the browser.

