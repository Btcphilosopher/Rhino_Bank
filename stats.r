# RHINOBANK ANALYTICS ENGINE — HARD R

## Architecture

```text
                         RHINOBANK
                             │
                ┌────────────┴────────────┐
                │                         │
          TRADE BLOTTER               LEDGER
                │                         │
          POSITIONS / ORDERS        CASH FLOWS
                │                         │
                └────────────┬────────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │ RHINO ANALYTICS R   │
                  │                     │
                  │ data.table         │
                  │ xts                │
                  │ PerformanceAnalytics│
                  │ R6                 │
                  └──────────┬──────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
      PERFORMANCE        EXECUTION           RISK
      ───────────        ─────────           ────
      P&L                fill rate           volatility
      returns            slippage            drawdown
      Sharpe             turnover            VaR
      Sortino            commissions         exposure
      CAGR               win rate             concentration
          │                  │                  │
          └──────────────────┼──────────────────┘
                             ▼
                     USER DASHBOARD API
```

---

# 1. Install the R stack

```r
install.packages(c(
    "data.table",
    "R6",
    "xts",
    "PerformanceAnalytics",
    "jsonlite",
    "lubridate"
))
```

---

# 2. `rhino_analytics.R`

```r
library(data.table)
library(R6)
library(xts)
library(PerformanceAnalytics)
library(jsonlite)
library(lubridate)


# ============================================================
# RHINOBANK ANALYTICS
# ============================================================

RhinoAnalytics <- R6Class(

    "RhinoAnalytics",

    public = list(

        trades = NULL,
        equity = NULL,
        positions = NULL,
        orders = NULL,

        initialize = function(
            trades = NULL,
            equity = NULL,
            positions = NULL,
            orders = NULL
        ) {

            self$trades <- as.data.table(
                trades
            )

            self$equity <- as.data.table(
                equity
            )

            self$positions <- as.data.table(
                positions
            )

            self$orders <- as.data.table(
                orders
            )

            private$validate()
        },


        # ====================================================
        # PERFORMANCE
        # ====================================================

        performance = function() {

            if (
                nrow(self$equity) < 2
            ) {

                return(
                    list(
                        status = "INSUFFICIENT_DATA"
                    )
                )
            }

            setorder(
                self$equity,
                timestamp
            )

            values <- self$equity$value

            returns <- values[
                -1
            ] / values[
                -length(values)
            ] - 1

            returns <- returns[
                is.finite(returns)
            ]

            if (
                length(returns) == 0
            ) {

                return(
                    list(
                        status =
                            "INSUFFICIENT_RETURNS"
                    )
                )
            }

            r <- xts(
                returns,
                order.by =
                    as.POSIXct(
                        self$equity$timestamp[-1]
                    )
            )

            annual_return <- tryCatch(
                Return.annualized(
                    r,
                    scale = 252
                )[1],
                error = function(e) NA_real_
            )

            annual_vol <- tryCatch(
                StdDev.annualized(
                    r,
                    scale = 252
                )[1],
                error = function(e) NA_real_
            )

            sharpe <- tryCatch(
                SharpeRatio.annualized(
                    r,
                    scale = 252
                )[1],
                error = function(e) NA_real_
            )

            sortino <- tryCatch(
                SortinoRatio(
                    r,
                    MAR = 0,
                    scale = 252
                )[1],
                error = function(e) NA_real_
            )

            drawdown <- tryCatch(
                maxDrawdown(r),
                error = function(e) NA_real_
            )

            list(

                total_return =
                    as.numeric(
                        prod(
                            1 + returns
                        ) - 1
                    ),

                annualized_return =
                    as.numeric(
                        annual_return
                    ),

                annualized_volatility =
                    as.numeric(
                        annual_vol
                    ),

                sharpe_ratio =
                    as.numeric(
                        sharpe
                    ),

                sortino_ratio =
                    as.numeric(
                        sortino
                    ),

                maximum_drawdown =
                    as.numeric(
                        drawdown
                    ),

                observations =
                    length(returns)
            )
        },


        # ====================================================
        # P&L
        # ====================================================

        pnl = function() {

            if (
                nrow(self$trades) == 0
            ) {

                return(
                    list(
                        realized = 0,
                        gross = 0,
                        fees = 0,
                        net = 0
                    )
                )
            }

            if (
                !"realized_pnl"
                %in%
                names(self$trades)
            ) {

                realized <- 0

            } else {

                realized <- sum(
                    self$trades$realized_pnl,
                    na.rm = TRUE
                )
            }

            fees <- if (
                "fees"
                %in%
                names(self$trades)
            ) {

                sum(
                    self$trades$fees,
                    na.rm = TRUE
                )

            } else {

                0
            }

            gross <- realized

            net <- gross - fees

            list(

                gross_realized_pnl =
                    gross,

                fees =
                    fees,

                net_realized_pnl =
                    net
            )
        },


        # ====================================================
        # TRADE STATISTICS
        # ====================================================

        trade_statistics = function() {

            if (
                nrow(self$trades) == 0
            ) {

                return(
                    list(
                        trades = 0
                    )
                )
            }

            pnl <- self$trades$realized_pnl

            pnl <- pnl[
                is.finite(pnl)
            ]

            winners <- pnl[
                pnl > 0
            ]

            losers <- pnl[
                pnl < 0
            ]

            gross_profit <- sum(
                winners,
                na.rm = TRUE
            )

            gross_loss <- abs(
                sum(
                    losers,
                    na.rm = TRUE
                )
            )

            profit_factor <- if (
                gross_loss > 0
            ) {

                gross_profit /
                    gross_loss

            } else {

                Inf
            }

            expectancy <- if (
                length(pnl) > 0
            ) {

                mean(
                    pnl,
                    na.rm = TRUE
                )

            } else {

                0
            }

            list(

                total_trades =
                    length(pnl),

                winning_trades =
                    length(winners),

                losing_trades =
                    length(losers),

                win_rate =
                    length(winners) /
                    max(
                        length(pnl),
                        1
                    ),

                gross_profit =
                    gross_profit,

                gross_loss =
                    gross_loss,

                profit_factor =
                    profit_factor,

                average_trade =
                    mean(
                        pnl,
                        na.rm = TRUE
                    ),

                median_trade =
                    median(
                        pnl,
                        na.rm = TRUE
                    ),

                best_trade =
                    max(
                        pnl,
                        na.rm = TRUE
                    ),

                worst_trade =
                    min(
                        pnl,
                        na.rm = TRUE
                    ),

                expectancy =
                    expectancy
            )
        },


        # ====================================================
        # EXECUTION
        # ====================================================

        execution = function() {

            if (
                nrow(self$orders) == 0
            ) {

                return(
                    list(
                        orders = 0
                    )
                )
            }

            orders <- self$orders

            total <- nrow(
                orders
            )

            filled <- if (
                "filled_quantity"
                %in%
                names(orders)
            ) {

                sum(
                    orders$filled_quantity,
                    na.rm = TRUE
                )

            } else {

                0
            }

            requested <- if (
                "quantity"
                %in%
                names(orders)
            ) {

                sum(
                    orders$quantity,
                    na.rm = TRUE
                )

            } else {

                0
            }

            fill_rate <- if (
                requested > 0
            ) {

                filled /
                    requested

            } else {

                0
            }

            list(

                total_orders =
                    total,

                filled_quantity =
                    filled,

                requested_quantity =
                    requested,

                fill_rate =
                    fill_rate
            )
        },


        # ====================================================
        # TURNOVER
        # ====================================================

        turnover = function() {

            if (
                nrow(self$trades) == 0
            ) {

                return(0)
            }

            if (
                !"notional"
                %in%
                names(self$trades)
            ) {

                return(NA_real_)
            }

            sum(
                abs(
                    self$trades$notional
                ),
                na.rm = TRUE
            )
        },


        # ====================================================
        # POSITION EXPOSURE
        # ====================================================

        exposure = function() {

            if (
                nrow(self$positions) == 0
            ) {

                return(
                    data.table()
                )
            }

            p <- copy(
                self$positions
            )

            if (
                all(
                    c(
                        "quantity",
                        "mark_price"
                    )
                    %in%
                    names(p)
                )
            ) {

                p[
                    ,
                    market_value :=
                        quantity *
                        mark_price
                ]

                total <- sum(
                    abs(
                        p$market_value
                    ),
                    na.rm = TRUE
                )

                p[
                    ,
                    weight :=
                        ifelse(
                            total > 0,
                            abs(
                                market_value
                            ) / total,
                            0
                        )
                ]
            }

            p[]
        },


        # ====================================================
        # CONCENTRATION
        # ====================================================

        concentration = function() {

            exposure <- self$exposure()

            if (
                nrow(exposure) == 0
            ) {

                return(
                    list()
                )
            }

            setorder(
                exposure,
                -weight
            )

            top <- head(
                exposure,
                10
            )

            list(

                largest_position =
                    top[1]$symbol,

                largest_weight =
                    top[1]$weight,

                top_5_weight =
                    sum(
                        head(
                            exposure$weight,
                            5
                        )
                    ),

                top_10_weight =
                    sum(
                        head(
                            exposure$weight,
                            10
                        )
                    )
            )
        },


        # ====================================================
        # RISK
        # ====================================================

        risk = function(
            confidence = 0.99
        ) {

            if (
                nrow(self$equity) < 3
            ) {

                return(
                    list(
                        status =
                            "INSUFFICIENT_DATA"
                    )
                )
            }

            setorder(
                self$equity,
                timestamp
            )

            values <- self$equity$value

            returns <- values[
                -1
            ] /
            values[
                -length(values)
            ] - 1

            returns <- returns[
                is.finite(returns)
            ]

            var <- quantile(
                returns,
                probs =
                    1 - confidence,
                na.rm = TRUE
            )

            es <- mean(
                returns[
                    returns <= var
                ],
                na.rm = TRUE
            )

            list(

                confidence =
                    confidence,

                historical_var =
                    as.numeric(var),

                expected_shortfall =
                    as.numeric(es),

                volatility =
                    sd(
                        returns,
                        na.rm = TRUE
                    )
            )
        },


        # ====================================================
        # DAILY PERFORMANCE
        # ====================================================

        daily_performance = function() {

            if (
                nrow(self$equity) == 0
            ) {

                return(
                    data.table()
                )
            }

            e <- copy(
                self$equity
            )

            e[
                ,
                date :=
                    as.Date(timestamp)
            ]

            daily <- e[
                ,
                .(
                    opening =
                        first(value),

                    closing =
                        last(value),

                    high =
                        max(value),

                    low =
                        min(value)
                ),
                by = date
            ]

            daily[
                ,
                return :=
                    closing /
                    shift(closing) - 1
            ]

            daily[]
        },


        # ====================================================
        # FULL USER REPORT
        # ====================================================

        report = function() {

            list(

                generated_at =
                    format(
                        Sys.time(),
                        tz = "UTC"
                    ),

                performance =
                    self$performance(),

                pnl =
                    self$pnl(),

                trading =
                    self$trade_statistics(),

                execution =
                    self$execution(),

                turnover =
                    self$turnover(),

                concentration =
                    self$concentration(),

                risk =
                    self$risk(),

                positions =
                    self$exposure()
            )
        },


        # ====================================================
        # JSON API OUTPUT
        # ====================================================

        report_json = function() {

            jsonlite::toJSON(
                self$report(),
                auto_unbox = TRUE,
                pretty = TRUE,
                na = "null"
            )
        }
    ),


    private = list(

        validate = function() {

            if (
                nrow(self$equity) > 0
                &&
                !"timestamp"
                %in%
                names(self$equity)
            ) {

                stop(
                    "Equity requires timestamp."
                )
            }

            if (
                nrow(self$equity) > 0
                &&
                !"value"
                %in%
                names(self$equity)
            ) {

                stop(
                    "Equity requires value."
                )
            }

            if (
                nrow(self$trades) > 0
                &&
                !"realized_pnl"
                %in%
                names(self$trades)
            ) {

                warning(
                    "Trades do not contain realized_pnl."
                )
            }
        }
    )
)
```

---

# 3. User data model

The RhinoBank API can provide the R engine with records such as:

```r
trades <- data.table(

    timestamp = as.POSIXct(
        c(
            "2026-08-01 09:30:00",
            "2026-08-03 14:10:00",
            "2026-08-07 11:20:00"
        ),
        tz = "UTC"
    ),

    symbol = c(
        "BTC/USDT",
        "ETH/USDT",
        "BTC/USDT"
    ),

    side = c(
        "BUY",
        "SELL",
        "SELL"
    ),

    quantity = c(
        1,
        10,
        0.5
    ),

    price = c(
        60000,
        3200,
        64000
    ),

    notional = c(
        60000,
        32000,
        32000
    ),

    realized_pnl = c(
        0,
        2500,
        2000
    ),

    fees = c(
        30,
        16,
        16
    )
)
```

---

# 4. Equity history

```r
equity <- data.table(

    timestamp = seq(
        as.POSIXct(
            "2026-08-01",
            tz = "UTC"
        ),

        as.POSIXct(
            "2026-08-31",
            tz = "UTC"
        ),

        by = "day"
    ),

    value = c(
        1000000,
        1005000,
        1002000,
        1015000,
        1020000,
        1017000,
        1030000,
        1042000,
        1038000,
        1050000,
        1065000,
        1060000,
        1072000,
        1080000,
        1075000,
        1090000,
        1105000,
        1098000,
        1110000,
        1125000,
        1130000,
        1127000,
        1140000,
        1155000,
        1160000,
        1170000,
        1185000,
        1190000,
        1205000,
        1210000,
        1220000
    )
)
```

---

# 5. Positions

```r
positions <- data.table(

    symbol = c(
        "BTC/USDT",
        "ETH/USDT",
        "SOL/USDT"
    ),

    quantity = c(
        5,
        100,
        1000
    ),

    mark_price = c(
        62000,
        3300,
        180
    )
)
```

---

# 6. Orders

```r
orders <- data.table(

    order_id = sprintf(
        "ORD-%05d",
        1:5
    ),

    symbol = c(
        "BTC/USDT",
        "BTC/USDT",
        "ETH/USDT",
        "ETH/USDT",
        "SOL/USDT"
    ),

    quantity = c(
        5,
        2,
        100,
        50,
        1000
    ),

    filled_quantity = c(
        5,
        2,
        100,
        25,
        1000
    )
)
```

---

# 7. Create the analytics engine

```r
analytics <- RhinoAnalytics$new(

    trades = trades,

    equity = equity,

    positions = positions,

    orders = orders
)
```

---

# 8. Performance

```r
analytics$performance()
```

Example output:

```text
$total_return
[1] 0.22

$annualized_return
[1] ...

$annualized_volatility
[1] ...

$sharpe_ratio
[1] ...

$sortino_ratio
[1] ...

$maximum_drawdown
[1] ...

$observations
[1] 30
```

---

# 9. Trading statistics

```r
analytics$trade_statistics()
```

The user can see:

```text
Total Trades
Winning Trades
Losing Trades
Win Rate
Gross Profit
Gross Loss
Profit Factor
Average Trade
Median Trade
Best Trade
Worst Trade
Expectancy
```

---

# 10. Risk dashboard

```r
analytics$risk(
    confidence = 0.99
)
```

Produces:

```text
99% Historical VaR
Expected Shortfall
Realized Volatility
```

---

# 11. Exposure

```r
analytics$exposure()
```

Produces a table such as:

```text
SYMBOL       QUANTITY      MARK       MARKET VALUE       WEIGHT
BTC/USDT     5             62000      310000             0.62
ETH/USDT     100           3300       330000             0.66
SOL/USDT     1000          180        180000             0.36
```

The dashboard can therefore display:

```text
PORTFOLIO EXPOSURE

BTC/USDT          ████████████████ 62%
ETH/USDT          █████████████████ 66%
SOL/USDT          █████████ 36%

TOP 5 CONCENTRATION     91%
```

---

# 12. Full report

```r
report <- analytics$report()

print(report)
```

Or produce API-ready JSON:

```r
json <- analytics$report_json()

cat(json)
```

---

# 13. User-specific isolation

The analytics service should **never accept an arbitrary account ID from the browser and then query everything**.

Instead:

```text
AUTHENTICATED SESSION
        │
        ▼
IDENTITY
        │
        ▼
ACCOUNT AUTHORIZATION
        │
        ▼
ACCOUNT-SCOPED DATA QUERY
        │
        ▼
R ANALYTICS
```

For example, the API layer should establish:

```r
user_context <- list(
    account_id = "RHINO-INST-001",
    permissions = c(
        "VIEW_PERFORMANCE",
        "VIEW_POSITIONS",
        "VIEW_TRADES"
    )
)
```

Then only retrieve:

```r
account_trades <- trades[
    account_id ==
        user_context$account_id
]
```

The R process should receive **only the authorized user's dataset**.

---

# 14. Analytics API

A lightweight R HTTP endpoint can be added using `plumber`.

Install:

```r
install.packages("plumber")
```

`api.R`:

```r
library(plumber)
library(jsonlite)

#* RhinoBank user analytics
#* @param account_id Institutional account identifier
#* @get /analytics
function(account_id) {

    # IMPORTANT:
    # account authorization must happen upstream.
    #
    # This example assumes the API gateway has
    # already authenticated the caller.

    user_trades <- load_user_trades(
        account_id
    )

    user_equity <- load_user_equity(
        account_id
    )

    user_positions <- load_user_positions(
        account_id
    )

    user_orders <- load_user_orders(
        account_id
    )

    analytics <- RhinoAnalytics$new(

        trades =
            user_trades,

        equity =
            user_equity,

        positions =
            user_positions,

        orders =
            user_orders
    )

    analytics$report_json()
}
```

Start it with:

```bash
Rscript -e \
'pr <- plumber::plumb("api.R"); pr$run(host="0.0.0.0", port=8001)'
```

---

# 15. Dashboard data structure

The front end can consume the report as:

```json
{
  "performance": {
    "total_return": 0.22,
    "annualized_return": 0.19,
    "annualized_volatility": 0.24,
    "sharpe_ratio": 1.31,
    "sortino_ratio": 1.84,
    "maximum_drawdown": -0.083
  },

  "pnl": {
    "gross_realized_pnl": 45000,
    "fees": 1250,
    "net_realized_pnl": 43750
  },

  "trading": {
    "total_trades": 142,
    "winning_trades": 86,
    "losing_trades": 56,
    "win_rate": 0.606,
    "profit_factor": 1.72,
    "average_trade": 308.1
  },

  "risk": {
    "confidence": 0.99,
    "historical_var": -0.034,
    "expected_shortfall": -0.051,
    "volatility": 0.024
  }
}
```

This lets the RhinoBank interface have a dedicated:

```text
┌─────────────────────────────────────────────────────────┐
│ RHINOBANK ANALYTICS                         01 SEP 2026 │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  PORTFOLIO VALUE       NET P&L        RETURN            │
│  $1,220,000             $43,750        +22.0%            │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  PERFORMANCE                                             │
│                                                         │
│  Equity ────────────────────────────────╮               │
│                                         ╰───────         │
│                                                         │
├──────────────────────┬──────────────────────────────────┤
│ SHARPE               │ MAX DRAWDOWN                     │
│ 1.31                 │ -8.3%                            │
├──────────────────────┼──────────────────────────────────┤
│ WIN RATE             │ PROFIT FACTOR                    │
│ 60.6%                │ 1.72                             │
├──────────────────────┴──────────────────────────────────┤
│                                                         │
│ EXPOSURE                                                │
│                                                         │
│ BTC/USDT       ████████████████████                     │
│ ETH/USDT       █████████████████                       │
│ SOL/USDT       █████████                              │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ EXECUTION                                               │
│                                                         │
│ ORDERS       142          FILL RATE       91.7%         │
│ TURNOVER     $4.82m       FEES            $1,250        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

The key architectural principle is **R is an analytics/read-only service**. It should never have trading, withdrawal, custody, or signing privileges. The Python RhinoBank core remains authoritative for balances, orders and settlement; R calculates statistics from an authorized snapshot of that data.

