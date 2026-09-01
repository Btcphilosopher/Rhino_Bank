/*
RHINOBANK // CYPHERPUNK TERMINAL
Frontend visual layer only.

Financial authority remains server-side.
Never trust client-side balances, prices, permissions,
settlement status or risk calculations.
*/

class RhinoTerminal {

    constructor(root) {

        this.root = root;

        this.state = {

            connection: "SECURE",
            node: "RHINO-LON-01",

            market: {
                symbol: "RHINO-GBP",
                price: 1.12042,
                target: 1.12000
            },

            account: {
                equity: 12481291.42,
                buyingPower: 4218920.15,
                exposure: 8262371.27,
                drawdown: -0.0831
            }

        };

        this.render();

    }


    render() {

        this.root.innerHTML = `

            <div class="rhino-terminal">

                ${this.header()}

                <div class="rhino-body">

                    ${this.sidebar()}

                    <main class="rhino-main">

                        ${this.commandBar()}

                        ${this.metrics()}

                        <section class="chart-panel">

                            <div class="panel-header">

                                <span>
                                    RHINO-STAT //
                                    EQUITY TELEMETRY
                                </span>

                                <span class="live">
                                    ● LIVE
                                </span>

                            </div>

                            <canvas
                                id="equityChart">
                            </canvas>

                        </section>

                        <div class="lower-grid">

                            ${this.orderBook()}

                            ${this.riskPanel()}

                            ${this.eventsPanel()}

                        </div>

                    </main>

                </div>

                ${this.footer()}

            </div>

        `;

        this.drawChart();

    }


    header() {

        return `

            <header class="rhino-header">

                <div class="rhino-logo">
                    RHINOBANK
                </div>

                <div class="rhino-classification">
                    INSTITUTIONAL DIGITAL ASSET TERMINAL
                </div>

                <div class="header-right">

                    <span class="secure">
                        ● CRYPTOGRAPHIC SESSION
                    </span>

                    <span id="clock">
                        UTC --:--:--
                    </span>

                </div>

            </header>

        `;

    }


    sidebar() {

        const items = [

            "OVERVIEW",
            "MARKET",
            "ORDERS",
            "POSITIONS",
            "ESCROW",
            "SETTLEMENT",
            "RISK",
            "ANALYTICS",
            "AUDIT",
            "NODE"

        ];

        return `

            <aside class="rhino-sidebar">

                <div class="sidebar-title">
                    RHINO // CONTROL
                </div>

                ${items.map(
                    item => `
                        <button
                            class="nav-button"
                            data-view="${item}">
                            ${item}
                        </button>
                    `
                ).join("")}

                <div class="sidebar-spacer"></div>

                <div class="node-status">

                    <div>
                        NODE
                    </div>

                    <strong>
                        ${this.state.node}
                    </strong>

                    <span class="status-online">
                        ● ONLINE
                    </span>

                </div>

            </aside>

        `;

    }


    commandBar() {

        return `

            <div class="command-bar">

                <span class="prompt">
                    RHINO:
                </span>

                <input
                    id="commandInput"
                    autocomplete="off"
                    spellcheck="false"
                    placeholder="enter command..."
                />

                <span class="command-help">
                    CTRL+K COMMAND
                </span>

            </div>

        `;

    }


    metrics() {

        return `

            <section class="metrics">

                ${this.metric(
                    "NET ASSET VALUE",
                    "$12,481,291.42",
                    "+8.41%"
                )}

                ${this.metric(
                    "BUYING POWER",
                    "$4,218,920.15",
                    "AVAILABLE"
                )}

                ${this.metric(
                    "EXPOSURE",
                    "$8,262,371.27",
                    "66.20%"
                )}

                ${this.metric(
                    "MAX DRAW DOWN",
                    "-8.31%",
                    "WITHIN LIMIT"
                )}

            </section>

        `;

    }


    metric(label, value, secondary) {

        return `

            <article class="metric">

                <div class="metric-label">
                    ${label}
                </div>

                <div class="metric-value">
                    ${value}
                </div>

                <div class="metric-secondary">
                    ${secondary}
                </div>

            </article>

        `;

    }


    orderBook() {

        return `

            <section class="panel">

                <div class="panel-header">

                    ORDER BOOK

                    <span>
                        ${this.state.market.symbol}
                    </span>

                </div>

                <div class="book">

                    <div class="book-row ask">
                        <span>1.12071</span>
                        <span>82,400</span>
                    </div>

                    <div class="book-row ask">
                        <span>1.12060</span>
                        <span>41,220</span>
                    </div>

                    <div class="book-row ask">
                        <span>1.12055</span>
                        <span>27,881</span>
                    </div>

                    <div class="spread">
                        1.12042
                    </div>

                    <div class="book-row bid">
                        <span>1.12040</span>
                        <span>38,910</span>
                    </div>

                    <div class="book-row bid">
                        <span>1.12031</span>
                        <span>51,220</span>
                    </div>

                    <div class="book-row bid">
                        <span>1.12020</span>
                        <span>73,900</span>
                    </div>

                </div>

            </section>

        `;

    }


    riskPanel() {

        return `

            <section class="panel">

                <div class="panel-header">
                    RISK TELEMETRY
                </div>

                <div class="risk">

                    ${this.risk(
                        "CREDIT",
                        18.7
                    )}

                    ${this.risk(
                        "MARKET",
                        31.2
                    )}

                    ${this.risk(
                        "LIQUIDITY",
                        12.8
                    )}

                    ${this.risk(
                        "ASSET",
                        42.1
                    )}

                </div>

            </section>

        `;

    }


    risk(label, value) {

        return `

            <div class="risk-row">

                <div class="risk-title">

                    <span>${label}</span>

                    <span>
                        ${value.toFixed(1)}%
                    </span>

                </div>

                <div class="risk-track">

                    <div
                        class="risk-fill"
                        style="width:${value}%">
                    </div>

                </div>

            </div>

        `;

    }


    eventsPanel() {

        return `

            <section class="panel">

                <div class="panel-header">
                    SYSTEM EVENTS
                </div>

                <div class="events">

                    ${this.event(
                        "16:42:17.184",
                        "ORDER",
                        "BUY RHINO-GBP"
                    )}

                    ${this.event(
                        "16:42:13.007",
                        "ESCROW",
                        "FUNDS LOCKED"
                    )}

                    ${this.event(
                        "16:41:58.391",
                        "RISK",
                        "LIMIT CHECK PASS"
                    )}

                    ${this.event(
                        "16:41:52.183",
                        "SETTLEMENT",
                        "COMPLETE"
                    )}

                    ${this.event(
                        "16:41:40.028",
                        "ORACLE",
                        "CPI DATA ACCEPTED"
                    )}

                </div>

            </section>

        `;

    }


    event(time, type, message) {

        return `

            <div class="event">

                <span class="event-time">
                    ${time}
                </span>

                <span class="event-type">
                    ${type}
                </span>

                <span>
                    ${message}
                </span>

            </div>

        `;

    }


    footer() {

        return `

            <footer class="rhino-footer">

                <span>
                    NODE ${this.state.node}
                </span>

                <span>
                    API ● CONNECTED
                </span>

                <span>
                    DATABASE ● HEALTHY
                </span>

                <span>
                    ORACLE ● VERIFIED
                </span>

                <span>
                    AUDIT ● ACTIVE
                </span>

                <span class="footer-spacer"></span>

                <span>
                    RHINO TERMINAL v0.1
                </span>

            </footer>

        `;

    }


    drawChart() {

        const canvas =
            document.getElementById(
                "equityChart"
            );

        if (!canvas) return;

        const ctx =
            canvas.getContext("2d");

        const rect =
            canvas.getBoundingClientRect();

        const dpr =
            window.devicePixelRatio || 1;

        canvas.width =
            rect.width * dpr;

        canvas.height =
            rect.height * dpr;

        ctx.scale(
            dpr,
            dpr
        );

        const width =
            rect.width;

        const height =
            rect.height;

        ctx.clearRect(
            0,
            0,
            width,
            height
        );


        /*
         * Grid
         */

        ctx.lineWidth = 1;

        for (
            let x = 0;
            x < width;
            x += 80
        ) {

            ctx.strokeStyle =
                "rgba(80,120,95,0.12)";

            ctx.beginPath();

            ctx.moveTo(x, 0);
            ctx.lineTo(x, height);

            ctx.stroke();

        }


        for (
            let y = 0;
            y < height;
            y += 50
        ) {

            ctx.beginPath();

            ctx.moveTo(0, y);
            ctx.lineTo(width, y);

            ctx.stroke();

        }


        /*
         * Synthetic demonstration
         * telemetry.
         *
         * Production data should come
         * from the Rhino API.
         */

        const points = [];

        let value = 0.45;

        for (
            let i = 0;
            i < 220;
            i++
        ) {

            value +=
                (Math.random() - 0.46)
                * 0.035;

            value =
                Math.max(
                    0.12,
                    Math.min(
                        0.88,
                        value
                    )
                );

            points.push(
                value
            );

        }


        /*
         * Equity line
         */

        ctx.beginPath();

        points.forEach(
            (value, i) => {

                const x =
                    (i /
                    (points.length - 1))
                    * width;

                const y =
                    height -
                    value * height;

                if (i === 0)
                    ctx.moveTo(x, y);
                else
                    ctx.lineTo(x, y);

            }
        );

        ctx.strokeStyle =
            "#39ff88";

        ctx.lineWidth = 1.5;

        ctx.shadowColor =
            "#39ff88";

        ctx.shadowBlur = 8;

        ctx.stroke();

        ctx.shadowBlur = 0;


        /*
         * Current price marker
         */

        const finalValue =
            points[
                points.length - 1
            ];

        const finalY =
            height -
            finalValue * height;

        ctx.fillStyle =
            "#39ff88";

        ctx.beginPath();

        ctx.arc(
            width - 2,
            finalY,
            3,
            0,
            Math.PI * 2
        );

        ctx.fill();

    }

}


/*
 * Boot
 */

document.addEventListener(
    "DOMContentLoaded",
    () => {

        const root =
            document.getElementById(
                "rhino"
            );

        if (root) {

            window.rhino =
                new RhinoTerminal(
                    root
                );

        }

    }
);
