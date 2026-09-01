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










/*
RHINOBANK CYPHERPUNK UI
*/

:root {

    --black:
        #020403;

    --panel:
        #050806;

    --panel-2:
        #080d0a;

    --border:
        #17241b;

    --border-bright:
        #25402d;

    --text:
        #c8d3ca;

    --muted:
        #56645b;

    --green:
        #39ff88;

    --green-dark:
        #0e2c19;

    --cyan:
        #43d9ff;

    --amber:
        #ffc857;

    --red:
        #ff4d61;

}


* {

    box-sizing:
        border-box;

}


html,
body {

    margin: 0;

    width: 100%;

    height: 100%;

    overflow: hidden;

    background:
        var(--black);

}


body {

    font-family:
        "JetBrains Mono",
        "IBM Plex Mono",
        "SFMono-Regular",
        Consolas,
        monospace;

    color:
        var(--text);

}


button,
input {

    font:
        inherit;

}


.rhino-terminal {

    display:
        flex;

    flex-direction:
        column;

    width: 100vw;

    height: 100vh;

    background:
        radial-gradient(
            circle at 70% 20%,
            rgba(25,80,45,.08),
            transparent 35%
        ),
        var(--black);

}


/* HEADER */

.rhino-header {

    height:
        54px;

    display:
        flex;

    align-items:
        center;

    padding:
        0 18px;

    border-bottom:
        1px solid var(--border);

    background:
        rgba(3,7,5,.96);

}


.rhino-logo {

    color:
        var(--green);

    font-size:
        19px;

    font-weight:
        900;

    letter-spacing:
        4px;

    text-shadow:
        0 0 12px
        rgba(57,255,136,.35);

}


.rhino-classification {

    margin-left:
        18px;

    color:
        var(--muted);

    font-size:
        9px;

    letter-spacing:
        2px;

}


.header-right {

    margin-left:
        auto;

    display:
        flex;

    gap:
        25px;

    align-items:
        center;

    font-size:
        9px;

}


.secure {

    color:
        var(--green);

}


#clock {

    color:
        var(--muted);

}


/* BODY */

.rhino-body {

    display:
        flex;

    flex: 1;

    min-height:
        0;

}


/* SIDEBAR */

.rhino-sidebar {

    width:
        170px;

    flex-shrink:
        0;

    display:
        flex;

    flex-direction:
        column;

    background:
        #040705;

    border-right:
        1px solid var(--border);

}


.sidebar-title {

    padding:
        17px 14px;

    color:
        #405047;

    font-size:
        9px;

    letter-spacing:
        2px;

}


.nav-button {

    appearance:
        none;

    border:
        0;

    border-left:
        2px solid transparent;

    background:
        transparent;

    color:
        #647169;

    padding:
        12px 14px;

    text-align:
        left;

    font-size:
        9px;

    letter-spacing:
        1.4px;

    cursor:
        pointer;

    transition:
        .12s ease;

}


.nav-button:hover {

    color:
        var(--green);

    background:
        #09110c;

    border-left-color:
        var(--green);

}


.nav-button:active {

    background:
        #0c1710;

}


.sidebar-spacer {

    flex: 1;

}


.node-status {

    margin:
        10px;

    padding:
        12px;

    border:
        1px solid var(--border);

    background:
        #070c08;

    font-size:
        8px;

    color:
        var(--muted);

}


.node-status strong {

    display:
        block;

    margin:
        6px 0;

    color:
        var(--text);

}


.status-online {

    color:
        var(--green);

}


/* MAIN */

.rhino-main {

    flex:
        1;

    min-width:
        0;

    min-height:
        0;

    overflow:
        auto;

    padding:
        15px;

}


/* COMMAND */

.command-bar {

    height:
        38px;

    display:
        flex;

    align-items:
        center;

    padding:
        0 12px;

    margin-bottom:
        12px;

    border:
        1px solid var(--border);

    background:
        #050906;

}


.prompt {

    color:
        var(--green);

    margin-right:
        9px;

}


.command-bar input {

    flex:
        1;

    background:
        transparent;

    border:
        0;

    outline:
        none;

    color:
        var(--text);

    font-size:
        10px;

}


.command-bar input::placeholder {

    color:
        #344138;

}


.command-help {

    color:
        #354138;

    font-size:
        8px;

}


/* METRICS */

.metrics {

    display:
        grid;

    grid-template-columns:
        repeat(4, 1fr);

    gap:
        10px;

    margin-bottom:
        10px;

}


.metric {

    padding:
        14px;

    border:
        1px solid var(--border);

    background:
        linear-gradient(
            135deg,
            #070c08,
            #050806
        );

}


.metric-label {

    color:
        var(--muted);

    font-size:
        8px;

    letter-spacing:
        1.5px;

}


.metric-value {

    margin-top:
        9px;

    color:
        #e7eee9;

    font-size:
        21px;

    font-weight:
        700;

}


.metric-secondary {

    margin-top:
        6px;

    color:
        var(--green);

    font-size:
        9px;

}


/* PANELS */

.panel,
.chart-panel {

    border:
        1px solid var(--border);

    background:
        var(--panel);

}


.panel-header {

    height:
        35px;

    display:
        flex;

    align-items:
        center;

    justify-content:
        space-between;

    padding:
        0 12px;

    border-bottom:
        1px solid var(--border);

    color:
        #708077;

    font-size:
        8px;

    letter-spacing:
        1.5px;

}


.live {

    color:
        var(--green);

}


/* CHART */

.chart-panel {

    height:
        480px;

    margin-bottom:
        10px;

}


#equityChart {

    display:
        block;

    width:
        100%;

    height:
        calc(100% - 35px);

}


/* LOWER PANELS */

.lower-grid {

    display:
        grid;

    grid-template-columns:
        1fr 1fr 1.3fr;

    gap:
        10px;

}


.panel {

    min-height:
        260px;

}


/* ORDER BOOK */

.book {

    padding:
        10px;

}


.book-row {

    display:
        flex;

    justify-content:
        space-between;

    padding:
        7px 4px;

    font-size:
        9px;

}


.ask {

    color:
        #d87d88;

}


.bid {

    color:
        var(--green);

}


.spread {

    margin:
        7px 0;

    padding:
        8px;

    text-align:
        center;

    color:
        var(--cyan);

    border-top:
        1px solid var(--border);

    border-bottom:
        1px solid var(--border);

}


/* RISK */

.risk {

    padding:
        14px;

}


.risk-row {

    margin-bottom:
        16px;

}


.risk-title {

    display:
        flex;

    justify-content:
        space-between;

    margin-bottom:
        6px;

    color:
        #77847b;

    font-size:
        8px;

}


.risk-track {

    height:
        4px;

    background:
        #101812;

}


.risk-fill {

    height:
        100%;

    background:
        var(--green);

    box-shadow:
        0 0 8px
        rgba(57,255,136,.35);

}


/* EVENTS */

.events {

    padding:
        7px 10px;

}


.event {

    display:
        grid;

    grid-template-columns:
        105px 90px 1fr;

    gap:
        8px;

    padding:
        8px 3px;

    border-bottom:
        1px solid
        rgba(40,60,47,.4);

    font-size:
        8px;

}


.event-time {

    color:
        #4d5c52;

}


.event-type {

    color:
        var(--cyan);

}


/* FOOTER */

.rhino-footer {

    height:
        29px;

    display:
        flex;

    align-items:
        center;

    gap:
        22px;

    padding:
        0 12px;

    border-top:
        1px solid var(--border);

    background:
        #040705;

    color:
        #4b584f;

    font-size:
        7px;

    letter-spacing:
        .7px;

}


.footer-spacer {

    flex:
        1;

}


/* SCROLLBAR */

::-webkit-scrollbar {

    width:
        7px;

}


::-webkit-scrollbar-track {

    background:
        #030504;

}


::-webkit-scrollbar-thumb {

    background:
        #1b2c20;

}


::-webkit-scrollbar-thumb:hover {

    background:
        #315039;

}


/* CRT / TERMINAL EFFECT */

.rhino-terminal::after {

    content: "";

    pointer-events:
        none;

    position:
        fixed;

    inset:
        0;

    background:
        repeating-linear-gradient(
            to bottom,
            rgba(255,255,255,.012),
            rgba(255,255,255,.012) 1px,
            transparent 1px,
            transparent 4px
        );

    opacity:
        .25;

}






function updateRhinoClock() {

    const element =
        document.getElementById("clock");

    if (!element)
        return;

    const now =
        new Date();

    const time =
        now.toISOString()
           .split("T")[1]
           .replace("Z", "");

    element.textContent =
        `UTC ${time}`;

}

setInterval(
    updateRhinoClock,
    100
);

updateRhinoClock();





document.addEventListener(
    "keydown",
    event => {

        if (
            event.ctrlKey &&
            event.key.toLowerCase() === "k"
        ) {

            event.preventDefault();

            const input =
                document.getElementById(
                    "commandInput"
                );

            if (input) {

                input.focus();

            }

        }

    }
);


document.addEventListener(
    "keydown",
    event => {

        const input =
            document.getElementById(
                "commandInput"
            );

        if (
            !input ||
            document.activeElement !== input
        ) {

            return;

        }

        if (
            event.key === "Enter"
        ) {

            executeRhinoCommand(
                input.value
            );

            input.value = "";

        }

    }
);


function executeRhinoCommand(
    command
) {

    const cmd =
        command
            .trim()
            .toLowerCase();


    switch (cmd) {

        case "status":

            console.log(
                "RHINO NODE: ONLINE"
            );

            break;


        case "risk":

            console.log(
                "RISK ENGINE: NOMINAL"
            );

            break;


        case "oracle":

            console.log(
                "CPI ORACLE: VERIFIED"
            );

            break;


        case "clear":

            console.clear();

            break;


        default:

            console.log(
                `RHINO: unknown command '${command}'`
            );

    }

}



