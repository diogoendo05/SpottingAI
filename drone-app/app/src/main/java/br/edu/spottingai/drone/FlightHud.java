package br.edu.spottingai.drone;

import android.app.Activity;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;

import java.util.List;
import java.util.Locale;

import dji.sdk.flightcontroller.FlightController;

/**
 * Parte de voo do HUD, no estilo do DJI Fly:
 * <ul>
 *   <li>barra superior: situacao do voo, modo, GPS, sinal de video e do
 *       controle, bateria com tempo de voo restante;</li>
 *   <li>botoes a esquerda: decolar / pousar / cancelar pouso, retorno para
 *       casa (RTH) e confirmacao de pouso - todos com confirmacao deslizante;</li>
 *   <li>canto inferior esquerdo: radar (casa e drone) com altura (H),
 *       distancia (D) e velocidades horizontal (HS) e vertical (VS).</li>
 * </ul>
 */
final class FlightHud {

    private final Activity activity;
    private final TelemetryMonitor telemetry;
    private final LinkMonitor link;

    private final TextView status;
    private final TextView mode;
    private final TextView gps;
    private final TextView video;
    private final TextView rc;
    private final TextView battery;
    private final TextView warnings;
    private final TextView values;
    private final RadarView radar;
    private final Button takeoffLand;
    private final Button rth;
    private final Button confirmLanding;

    FlightHud(Activity activity, TelemetryMonitor telemetry, LinkMonitor link) {
        this.activity = activity;
        this.telemetry = telemetry;
        this.link = link;
        status = activity.findViewById(R.id.hud_status);
        mode = activity.findViewById(R.id.hud_mode);
        gps = activity.findViewById(R.id.hud_gps);
        video = activity.findViewById(R.id.hud_video);
        rc = activity.findViewById(R.id.hud_rc);
        battery = activity.findViewById(R.id.hud_battery);
        warnings = activity.findViewById(R.id.telemetry_warnings);
        values = activity.findViewById(R.id.hud_values);
        radar = activity.findViewById(R.id.hud_radar);
        takeoffLand = activity.findViewById(R.id.btn_takeoff_land);
        rth = activity.findViewById(R.id.btn_rth);
        confirmLanding = activity.findViewById(R.id.btn_confirm_landing);

        takeoffLand.setOnClickListener(v -> onTakeoffLand());
        rth.setOnClickListener(v -> onRth());
        confirmLanding.setOnClickListener(v -> withController(fc ->
                fc.confirmLanding(Sdk.done(activity, "Confirmar pouso", null))));
    }

    /** Atualiza o HUD (chamado 4x por segundo). */
    void tick() {
        TelemetryMonitor t = telemetry;
        boolean data = t.hasFlightData;

        String state = t.statusText();
        status.setText(state);
        status.setBackgroundColor(state.equals("EM VOO") || state.startsWith("PRONTO") ? 0xCC2EA043
                : state.equals("RETORNANDO") || state.equals("POUSANDO") || state.equals("DECOLANDO") ? 0xCCD29922
                : data ? 0xCC6E7681 : 0xCCB00020);

        mode.setText(data ? shortMode(t.flightModeText) : "--");
        gps.setText(data ? "GPS " + t.satellites : "GPS --");
        gps.setTextColor(data && !t.isWeakGps() ? 0xFFFFFFFF : 0xFFFF6B6B);
        video.setText(signalText("VÍDEO", link.downlink));
        video.setTextColor(signalColor(link.downlink));
        rc.setText(signalText("RC", link.uplink));
        rc.setTextColor(signalColor(link.uplink));

        String bat = t.batteryPercent >= 0 ? t.batteryPercent + "%" : "--";
        String remaining = t.remainingFlightTime > 0
                ? String.format(Locale.ROOT, " · %d:%02d", t.remainingFlightTime / 60, t.remainingFlightTime % 60)
                : "";
        battery.setText("BAT " + bat + remaining);
        battery.setTextColor(t.seriousLowBattery ? 0xFFFF6B6B
                : t.lowBattery || (t.batteryPercent >= 0 && t.batteryPercent <= 30) ? 0xFFFFC107 : 0xFFFFFFFF);

        String distance = t.distanceHome >= 0 ? String.format(Locale.ROOT, "%.0f m", t.distanceHome) : "--";
        values.setText(String.format(Locale.ROOT, "H  %.1f m   D  %s\nHS %.1f m/s  VS %+.1f m/s",
                t.altitude, distance, t.horizontalSpeed, t.verticalSpeed));
        radar.update(t.distanceHome >= 0, t.offsetNorth, t.offsetEast, t.heading);

        // Botao principal: decolar / pousar / cancelar pouso, conforme a situacao.
        takeoffLand.setEnabled(data);
        if (t.isLanding()) takeoffLand.setText("✕ Cancelar pouso");
        else if (t.flying) takeoffLand.setText("⤓ Pousar");
        else takeoffLand.setText("⤒ Decolar");

        rth.setEnabled(data && (t.flying || t.goingHome));
        rth.setText(t.goingHome ? "✕ Cancelar RTH" : "⌂ RTH");
        takeoffLand.setAlpha(takeoffLand.isEnabled() ? 1f : 0.4f);
        rth.setAlpha(rth.isEnabled() ? 1f : 0.4f);
        confirmLanding.setVisibility(t.landingConfirmationNeeded ? View.VISIBLE : View.GONE);

        List<String> list = t.warnings();
        if (list.isEmpty()) {
            warnings.setVisibility(View.GONE);
        } else {
            warnings.setText(String.join("\n", list));
            warnings.setVisibility(View.VISIBLE);
        }
    }

    private void onTakeoffLand() {
        TelemetryMonitor t = telemetry;
        if (t.isLanding()) {
            withController(fc -> fc.cancelLanding(Sdk.done(activity, "Cancelar pouso", null)));
        } else if (t.flying) {
            SlideToConfirm.show(activity, "Pousar", "O drone vai descer e pousar no local atual.",
                    () -> withController(fc -> fc.startLanding(Sdk.done(activity, "Pousar", null))));
        } else {
            // Sem link de comandos o drone nao obedeceria aos sticks depois de subir.
            if (link.uplink >= 0 && link.uplink < 30) {
                Sdk.toast(activity, "Decolagem bloqueada: sinal do controle para o drone em " + link.uplink
                        + "%. Os comandos não estão chegando. Afaste-se de Wi-Fi/celulares, aponte as antenas "
                        + "e aguarde o RC subir acima de 50%.");
                return;
            }
            String warning = "";
            if (t.isWeakGps()) {
                warning = "\n\n⚠ SEM GPS (" + shortMode(t.flightModeText) + "): o drone NÃO segura a posição e "
                        + "vai derivar com o vento ou correntes de ar. Em local fechado e perto de pessoas, NÃO decole.";
            } else if (!t.homeSet) {
                warning = "\n\nAtenção: home point ainda não gravado. Sem ele o RTH não funciona.";
            }
            SlideToConfirm.show(activity, "Decolar",
                    "Os motores ligam e o drone sobe até ~1,2 m e fica parado." + warning,
                    () -> withController(fc -> fc.startTakeoff(Sdk.done(activity, "Decolar", null))));
        }
    }

    private void onRth() {
        if (telemetry.goingHome) {
            withController(fc -> fc.cancelGoHome(Sdk.done(activity, "Cancelar RTH", null)));
            return;
        }
        String distance = telemetry.distanceHome >= 0
                ? String.format(Locale.ROOT, " (%.0f m daqui)", telemetry.distanceHome) : "";
        SlideToConfirm.show(activity, "Retornar para casa",
                "O drone sobe até a altitude de RTH, volta ao ponto de decolagem" + distance
                        + " e pousa. A altitude de RTH fica em ⚙ → Segurança.",
                () -> withController(fc -> fc.startGoHome(Sdk.done(activity, "RTH", null))));
    }

    private void withController(Sdk.Value<FlightController> action) {
        FlightController fc = telemetry.flightController();
        if (fc == null) {
            Sdk.toast(activity, "Drone não conectado.");
            return;
        }
        action.on(fc);
    }

    /** "P-GPS" / "GPS_ATTI" -> texto curto para a barra. */
    private static String shortMode(String text) {
        if (text == null || text.isEmpty()) return "--";
        return text.length() > 10 ? text.substring(0, 10) : text;
    }

    private static String signalText(String label, int percent) {
        return label + " " + (percent >= 0 ? percent + "%" : "--");
    }

    private static int signalColor(int percent) {
        if (percent < 0) return 0xFF8B949E;
        if (percent < 30) return 0xFFFF6B6B;
        if (percent < 60) return 0xFFFFC107;
        return 0xFFFFFFFF;
    }
}
