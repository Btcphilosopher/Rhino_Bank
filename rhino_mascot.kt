RhinoMascot.kt
package com.rhinobank.ui

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.RoundRect
import androidx.compose.ui.graphics.*
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.dp
import kotlin.math.sin


enum class RhinoState {

    IDLE,

    PROCESSING,

    SUCCESS,

    WARNING,

    ERROR_404,

    OFFLINE,

    SECURITY_ALERT
}


@Composable
fun RhinoMascot(
    state: RhinoState = RhinoState.IDLE,
    modifier: Modifier = Modifier
) {

    val infinite =
        rememberInfiniteTransition(
            label = "rhino"
        )

    /*
     * Slow breathing animation.
     */

    val breathing by infinite.animateFloat(
        initialValue = 0f,
        targetValue = 1f,

        animationSpec =
            infiniteRepeatable(
                animation =
                    tween(
                        durationMillis = 2400,
                        easing =
                            FastOutSlowInEasing
                    ),
                repeatMode =
                    RepeatMode.Reverse
            ),

        label = "breathing"
    )


    /*
     * Ear movement.
     */

    val earMovement by infinite.animateFloat(
        initialValue = -1f,
        targetValue = 1f,

        animationSpec =
            infiniteRepeatable(
                animation =
                    tween(
                        durationMillis = 1700,
                        easing =
                            EaseInOut
                    ),
                repeatMode =
                    RepeatMode.Reverse
            ),

        label = "ears"
    )


    /*
     * Eye / system pulse.
     */

    val pulse by infinite.animateFloat(
        initialValue = 0.35f,
        targetValue = 1f,

        animationSpec =
            infiniteRepeatable(
                animation =
                    tween(
                        durationMillis = 1100
                    ),
                repeatMode =
                    RepeatMode.Reverse
            ),

        label = "pulse"
    )


    /*
     * Error animation.
     */

    val errorShake by animateFloatAsState(

        targetValue =
            if (
                state == RhinoState.ERROR_404 ||
                state == RhinoState.SECURITY_ALERT
            )
                1f
            else
                0f,

        animationSpec =
            tween(
                durationMillis = 250
            ),

        label = "error-shake"
    )


    val offsetX =
        if (errorShake > 0f)
            sin(
                breathing * 25f
            ) * 4f
        else
            0f


    Box(
        modifier =
            modifier,

        contentAlignment =
            Alignment.Center
    ) {

        Canvas(
            modifier =
                Modifier
                    .fillMaxSize()
        ) {

            drawRhino(

                state = state,

                breathing =
                    breathing,

                earMovement =
                    earMovement,

                pulse =
                    pulse,

                offsetX =
                    offsetX

            )
        }
    }
}
Rhino renderer
private fun DrawScope.drawRhino(
    state: RhinoState,
    breathing: Float,
    earMovement: Float,
    pulse: Float,
    offsetX: Float
) {

    val cx =
        size.width / 2f + offsetX

    val cy =
        size.height / 2f

    /*
     * Responsive scale.
     */

    val scale =
        minOf(
            size.width,
            size.height
        ) / 260f


    /*
     * State colours.
     */

    val accent =
        when (state) {

            RhinoState.ERROR_404 ->
                Color(0xFFFF5068)

            RhinoState.OFFLINE ->
                Color(0xFFFFB84D)

            RhinoState.WARNING ->
                Color(0xFFFFB84D)

            RhinoState.SECURITY_ALERT ->
                Color(0xFFFF5068)

            RhinoState.SUCCESS ->
                Color(0xFF39FF88)

            RhinoState.PROCESSING ->
                Color(0xFF49DFFF)

            RhinoState.IDLE ->
                Color(0xFF39FF88)
        }


    /*
     * Breathing.
     */

    val breathingOffset =
        sin(
            breathing * Math.PI
        ).toFloat() * 2f


    /*
     * Shadow.
     */

    drawOval(

        color =
            Color.Black.copy(
                alpha = 0.55f
            ),

        topLeft =
            Offset(
                cx - 70f * scale,
                cy + 70f * scale
            ),

        size =
            androidx.compose.ui.geometry.Size(
                140f * scale,
                18f * scale
            )

    )


    /*
     * BODY
     */

    val body =
        Path().apply {

            moveTo(
                cx - 70f * scale,
                cy + 35f * scale
            )

            cubicTo(
                cx - 82f * scale,
                cy - 5f * scale,
                cx - 45f * scale,
                cy - 62f * scale,
                cx + 15f * scale,
                cy - 48f * scale
            )

            cubicTo(
                cx + 68f * scale,
                cy - 35f * scale,
                cx + 82f * scale,
                cy + 18f * scale,
                cx + 62f * scale,
                cy + 48f * scale
            )

            cubicTo(
                cx + 35f * scale,
                cy + 72f * scale,
                cx - 45f * scale,
                cy + 70f * scale,
                cx - 70f * scale,
                cy + 35f * scale
            )

            close()

        }


    drawPath(

        path = body,

        color =
            Color(0xFF111714)

    )


    drawPath(

        path = body,

        color =
            accent.copy(
                alpha = 0.65f
            ),

        style =
            Stroke(
                width =
                    1.5f * scale
            )

    )


    /*
     * HEAD
     */

    val head =
        Path().apply {

            moveTo(
                cx - 45f * scale,
                cy - 45f * scale
            )

            cubicTo(
                cx - 40f * scale,
                cy - 83f * scale,
                cx + 2f * scale,
                cy - 92f * scale,
                cx + 43f * scale,
                cy - 67f * scale
            )

            cubicTo(
                cx + 68f * scale,
                cy - 51f * scale,
                cx + 76f * scale,
                cy - 23f * scale,
                cx + 61f * scale,
                cy + 3f * scale
            )

            cubicTo(
                cx + 42f * scale,
                cy + 28f * scale,
                cx - 12f * scale,
                cy + 23f * scale,
                cx - 40f * scale,
                cy + 4f * scale
            )

            close()

        }


    drawPath(

        path = head,

        color =
            Color(0xFF151D18)

    )


    drawPath(

        path = head,

        color =
            accent.copy(
                alpha = 0.75f
            ),

        style =
            Stroke(
                width =
                    1.5f * scale
            )

    )


    /*
     * MAIN HORN
     */

    val horn =
        Path().apply {

            moveTo(
                cx + 42f * scale,
                cy - 51f * scale
            )

            lineTo(
                cx + 75f * scale,
                cy - 96f * scale
            )

            lineTo(
                cx + 67f * scale,
                cy - 45f * scale
            )

            close()

        }


    drawPath(

        path = horn,

        color =
            accent.copy(
                alpha = 0.85f
            )

    )


    /*
     * SECONDARY HORN
     */

    val horn2 =
        Path().apply {

            moveTo(
                cx + 28f * scale,
                cy - 52f * scale
            )

            lineTo(
                cx + 42f * scale,
                cy - 78f * scale
            )

            lineTo(
                cx + 45f * scale,
                cy - 47f * scale
            )

            close()

        }


    drawPath(

        path = horn2,

        color =
            Color(0xFF29342D)

    )


    /*
     * EARS
     */

    drawOval(

        color =
            Color(0xFF151D18),

        topLeft =
            Offset(
                cx - 32f * scale,
                cy - 83f * scale +
                    earMovement * scale
            ),

        size =
            androidx.compose.ui.geometry.Size(
                25f * scale,
                18f * scale
            )

    )


    drawOval(

        color =
            Color(0xFF151D18),

        topLeft =
            Offset(
                cx + 22f * scale,
                cy - 78f * scale -
                    earMovement * scale
            ),

        size =
            androidx.compose.ui.geometry.Size(
                25f * scale,
                18f * scale
            )

    )


    /*
     * EYE GLOW
     */

    drawCircle(

        color =
            accent.copy(
                alpha =
                    0.12f * pulse
            ),

        radius =
            13f * scale,

        center =
            Offset(
                cx + 29f * scale,
                cy - 32f * scale
            )

    )


    drawCircle(

        color =
            accent,

        radius =
            2.8f * scale,

        center =
            Offset(
                cx + 29f * scale,
                cy - 32f * scale
            )

    )


    /*
     * NOSTRIL
     */

    drawCircle(

        color =
            accent.copy(
                alpha = .7f
            ),

        radius =
            2f * scale,

        center =
            Offset(
                cx + 58f * scale,
                cy - 5f * scale
            )

    )


    /*
     * CYBERPUNK SCAN LINE
     */

    if (
        state == RhinoState.PROCESSING ||
        state == RhinoState.SECURITY_ALERT
    ) {

        val scanY =
            cy -
                70f * scale +
                breathing * 140f * scale


        drawLine(

            color =
                accent.copy(
                    alpha = .45f
                ),

            start =
                Offset(
                    cx - 90f * scale,
                    scanY
                ),

            end =
                Offset(
                    cx + 90f * scale,
                    scanY
                ),

            strokeWidth =
                1f * scale

        )

    }


    /*
     * 404 SIGNAL GLITCH
     */

    if (
        state == RhinoState.ERROR_404
    ) {

        repeat(5) { i ->

            val y =
                cy -
                    55f * scale +
                    i * 24f * scale

            drawLine(

                color =
                    accent.copy(
                        alpha = .35f
                    ),

                start =
                    Offset(
                        cx - 85f * scale,
                        y
                    ),

                end =
                    Offset(
                        cx +
                            (30f + i * 12f)
                                * scale,
                        y
                    ),

                strokeWidth =
                    1f * scale

            )
        }
    }
}
404 screen

Then make the rhino the actual personality of the error system:

@Composable
fun Rhino404Screen(
    onReturn: () -> Unit
) {

    Column(

        modifier =
            Modifier
                .fillMaxSize()
                .padding(32.dp),

        horizontalAlignment =
            Alignment.CenterHorizontally,

        verticalArrangement =
            Arrangement.Center

    ) {

        RhinoMascot(

            state =
                RhinoState.ERROR_404,

            modifier =
                Modifier.size(260.dp)

        )


        Spacer(
            Modifier.height(18.dp)
        )


        Text(
            text =
                "404 // ROUTE NOT FOUND"
        )


        Spacer(
            Modifier.height(8.dp)
        )


        Text(
            text =
                "THE RHINO COULD NOT LOCATE THIS RESOURCE."
        )


        Spacer(
            Modifier.height(20.dp)
        )


        Text(
            text =
                "[ RETURN TO TERMINAL ]"
        )
    }
}
And I'd give the Rhino several personalities
RhinoState.IDLE

Normal state:

        RHINO
     breathing
    subtle eye glow
      ear movement
RhinoState.PROCESSING

The horn gets a scanning line:

             /\
            /  \
       ────────╱────
          RHINO
       PROCESSING
RhinoState.SUCCESS

Small upward head movement + green pulse.

RhinoState.WARNING

Amber eyes + ears move slightly backward.

RhinoState.ERROR_404

Brief shake + scan-line glitches:

     RHINO // 404
       ╱╲
   ───╱  ╲──
      ░░░
    ROUTE LOST
RhinoState.OFFLINE

Slowly desaturates and the eye fades.

RhinoState.SECURITY_ALERT

This one could be particularly good for the RhinoBank aesthetic:

       ┌─────────────────┐
       │ SECURITY ALERT  │
       └─────────────────┘

             /\ 
            /  \     ← horn scanning
        ___/____\___
       /            \
      |      ●       |
       \____________/

       AUTHORIZATION
       REQUIRED

The really nice part is that the same Rhino component can be used throughout the entire application:

LOGIN
  ↓
RhinoSecurity

DASHBOARD
  ↓
RhinoIdle

ORDER SUBMISSION
  ↓
RhinoProcessing

TRADE EXECUTED
  ↓
RhinoSuccess

ESCROW WAITING
  ↓
RhinoProcessing

SETTLEMENT
  ↓
RhinoSuccess

404
  ↓
Rhino404

NODE OFFLINE
  ↓
RhinoOffline

SECURITY FAILURE
  ↓
RhinoSecurityAlert
