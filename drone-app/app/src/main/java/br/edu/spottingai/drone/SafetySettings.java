package br.edu.spottingai.drone;

import android.app.Activity;
import android.os.Handler;
import android.os.Looper;
import android.widget.Button;
import android.widget.TextView;

import java.util.Locale;

import dji.common.flightcontroller.ConnectionFailSafeBehavior;
import dji.common.flightcontroller.flightassistant.ObstacleActionMode;
import dji.sdk.flightcontroller.FlightAssistant;
import dji.sdk.flightcontroller.FlightController;

/**
 * Aba "Seguranca" do painel ⚙, equivalente a do DJI Fly: altitude de RTH,
 * altitude maxima, distancia maxima, acao ao desviar de obstaculos, acao ao
 * perder o sinal, desvio de obstaculos durante o RTH e atualizar o ponto
 * de casa. Cada valor e lido do drone ao conectar.
 */
final class SafetySettings {

    private static final long APPLY_DELAY_MS = 900;

    private final Activity activity;
    private final TelemetryMonitor telemetry;
    private final Handler ui = new Handler(Looper.getMainLooper());

    private final TextView rthHeight;
    private final TextView maxHeight;
    private final TextView maxDistance;
    private final Button distanceLimit;
    private final Button obstacleMode;
    private final Button signalLoss;
    private final Button rthObstacle;

    private int rthValue = -1;
    private int maxHeightValue = -1;
    private int maxDistanceValue = -1;
    private Boolean distanceLimited;
    private ObstacleActionMode obstacle;
    private ConnectionFailSafeBehavior failSafe;
    private Boolean rthAvoidance;

    SafetySettings(Activity activity, TelemetryMonitor telemetry) {
        this.activity = activity;
        this.telemetry = telemetry;
        rthHeight = activity.findViewById(R.id.rth_height_value);
        maxHeight = activity.findViewById(R.id.max_height_value);
        maxDistance = activity.findViewById(R.id.max_distance_value);
        distanceLimit = activity.findViewById(R.id.btn_distance_limit);
        obstacleMode = activity.findViewById(R.id.btn_obstacle_mode);
        signalLoss = activity.findViewById(R.id.btn_signal_loss);
        rthObstacle = activity.findViewById(R.id.btn_rth_obstacle);

        activity.findViewById(R.id.btn_rth_minus).setOnClickListener(v -> stepRth(-10));
        activity.findViewById(R.id.btn_rth_plus).setOnClickListener(v -> stepRth(10));
        activity.findViewById(R.id.btn_max_height_minus).setOnClickListener(v -> stepMaxHeight(-10));
        activity.findViewById(R.id.btn_max_height_plus).setOnClickListener(v -> stepMaxHeight(10));
        activity.findViewById(R.id.btn_max_distance_minus).setOnClickListener(v -> stepMaxDistance(-100));
        activity.findViewById(R.id.btn_max_distance_plus).setOnClickListener(v -> stepMaxDistance(100));
        distanceLimit.setOnClickListener(v -> toggleDistanceLimit());
        obstacleMode.setOnClickListener(v -> chooseObstacleMode());
        signalLoss.setOnClickListener(v -> chooseSignalLoss());
        rthObstacle.setOnClickListener(v -> toggleRthAvoidance());
        activity.findViewById(R.id.btn_update_home).setOnClickListener(v -> updateHome());
        render();
    }

    /**
     * Le todos os valores do drone. Logo apos conectar o drone costuma nao
     * responder ("tempo esgotado"), entao repete a cada 10 s ate ter todos.
     */
    void refresh() {
        ui.removeCallbacks(retry);
        FlightController fc = telemetry.flightController();
        if (fc == null) return;
        ui.postDelayed(retry, 10_000);
        fc.getGoHomeHeightInMeters(Sdk.got("getGoHomeHeight", v -> { rthValue = v; render(); }));
        fc.getMaxFlightHeight(Sdk.got("getMaxFlightHeight", v -> { maxHeightValue = v; render(); }));
        fc.getMaxFlightRadius(Sdk.got("getMaxFlightRadius", v -> { maxDistanceValue = v; render(); }));
        fc.getMaxFlightRadiusLimitationEnabled(Sdk.got("getMaxFlightRadiusLimitationEnabled",
                v -> { distanceLimited = v; render(); }));
        fc.getConnectionFailSafeBehavior(Sdk.got("getConnectionFailSafeBehavior",
                v -> { failSafe = v; render(); }));
        FlightAssistant assistant = fc.getFlightAssistant();
        if (assistant != null) {
            assistant.getObstacleAvoidanceMode(Sdk.got("getObstacleAvoidanceMode", v -> { obstacle = v; render(); }));
            assistant.getRTHObstacleAvoidanceEnabled(Sdk.got("getRTHObstacleAvoidanceEnabled",
                    v -> { rthAvoidance = v; render(); }));
        }
    }

    private final Runnable retry = this::retryIfMissing;

    private void retryIfMissing() {
        boolean missing = rthValue <= 0 || maxHeightValue <= 0 || maxDistanceValue <= 0 || distanceLimited == null
                || failSafe == null || obstacle == null || rthAvoidance == null;
        if (missing && telemetry.hasFlightData) refresh();
    }

    /** Drone desconectou: para de tentar ler. */
    void stop() {
        ui.removeCallbacks(retry);
    }

    private void render() {
        rthHeight.setText(rthValue > 0 ? rthValue + " m" : "--");
        maxHeight.setText(maxHeightValue > 0 ? maxHeightValue + " m" : "--");
        boolean limited = !Boolean.FALSE.equals(distanceLimited);
        maxDistance.setText(!limited ? "sem limite" : maxDistanceValue > 0 ? maxDistanceValue + " m" : "--");
        distanceLimit.setText(distanceLimited == null ? "--" : distanceLimited ? "Limite ligado" : "Limite desligado");
        obstacleMode.setText(obstacle == null ? "--" : obstacleLabel(obstacle));
        signalLoss.setText(failSafe == null ? "--" : failSafeLabel(failSafe));
        rthObstacle.setText(rthAvoidance == null ? "--" : rthAvoidance ? "Ligado" : "Desligado");
    }

    // -- ajustes numericos (aplicados apos uma pausa nos toques) -------------- //

    private final Runnable applyRth = this::sendRth;
    private final Runnable applyMaxHeight = this::sendMaxHeight;
    private final Runnable applyMaxDistance = this::sendMaxDistance;

    private void sendRth() {
        withController(fc -> fc.setGoHomeHeightInMeters(rthValue, Sdk.done(activity, "Altitude de RTH", null)));
    }

    private void sendMaxHeight() {
        withController(fc -> fc.setMaxFlightHeight(maxHeightValue, Sdk.done(activity, "Altitude máxima", null)));
    }

    private void sendMaxDistance() {
        withController(fc -> fc.setMaxFlightRadius(maxDistanceValue, Sdk.done(activity, "Distância máxima", null)));
    }

    private void stepRth(int delta) {
        if (rthValue <= 0) return;
        rthValue = clamp(rthValue + delta, 20, Math.max(20, maxHeightValue > 0 ? maxHeightValue : 500));
        render();
        schedule(applyRth);
    }

    private void stepMaxHeight(int delta) {
        if (maxHeightValue <= 0) return;
        maxHeightValue = clamp(maxHeightValue + delta, 20, 500);
        if (maxHeightValue > 120) {
            Sdk.toast(activity, "Atenção: acima de 120 m exige autorização da ANAC/DECEA.");
        }
        render();
        schedule(applyMaxHeight);
    }

    private void stepMaxDistance(int delta) {
        if (maxDistanceValue <= 0) return;
        maxDistanceValue = clamp(maxDistanceValue + delta, 15, 8000);
        render();
        schedule(applyMaxDistance);
    }

    private void schedule(Runnable apply) {
        ui.removeCallbacks(apply);
        ui.postDelayed(apply, APPLY_DELAY_MS);
    }

    // -- opcoes ----------------------------------------------------------------- //

    private void toggleDistanceLimit() {
        if (distanceLimited == null) return;
        boolean enable = !distanceLimited;
        withController(fc -> fc.setMaxFlightRadiusLimitationEnabled(enable,
                Sdk.done(activity, "Limite de distância", () -> { distanceLimited = enable; render(); })));
    }

    private void chooseObstacleMode() {
        ObstacleActionMode[] modes = {ObstacleActionMode.APAS, ObstacleActionMode.STOP, ObstacleActionMode.CLOSE};
        String[] labels = new String[modes.length];
        for (int i = 0; i < modes.length; i++) labels[i] = obstacleLabel(modes[i]);
        Sdk.choose(activity, "Ação ao detectar obstáculo", labels, java.util.Arrays.asList(modes).indexOf(obstacle),
                i -> withController(fc -> {
                    FlightAssistant assistant = fc.getFlightAssistant();
                    if (assistant == null) {
                        Sdk.toast(activity, "Assistente de voo indisponível.");
                        return;
                    }
                    assistant.setObstacleAvoidanceMode(modes[i], Sdk.done(activity, "Desvio de obstáculos",
                            () -> { obstacle = modes[i]; render(); }));
                }));
    }

    private void chooseSignalLoss() {
        ConnectionFailSafeBehavior[] options = {ConnectionFailSafeBehavior.GO_HOME,
                ConnectionFailSafeBehavior.LANDING, ConnectionFailSafeBehavior.HOVER};
        String[] labels = new String[options.length];
        for (int i = 0; i < options.length; i++) labels[i] = failSafeLabel(options[i]);
        Sdk.choose(activity, "Ao perder o sinal do controle", labels,
                java.util.Arrays.asList(options).indexOf(failSafe),
                i -> withController(fc -> fc.setConnectionFailSafeBehavior(options[i],
                        Sdk.done(activity, "Perda de sinal", () -> { failSafe = options[i]; render(); }))));
    }

    private void toggleRthAvoidance() {
        if (rthAvoidance == null) return;
        boolean enable = !rthAvoidance;
        withController(fc -> {
            FlightAssistant assistant = fc.getFlightAssistant();
            if (assistant != null) assistant.setRTHObstacleAvoidanceEnabled(enable,
                    Sdk.done(activity, "Desvio no RTH", () -> { rthAvoidance = enable; render(); }));
        });
    }

    private void updateHome() {
        SlideToConfirm.show(activity, "Atualizar ponto de casa",
                "O RTH passa a voltar para onde o drone está agora.",
                () -> withController(fc -> fc.setHomeLocationUsingAircraftCurrentLocation(
                        Sdk.done(activity, "Ponto de casa", () -> Sdk.toast(activity, "Ponto de casa atualizado.")))));
    }

    private void withController(Sdk.Value<FlightController> action) {
        FlightController fc = telemetry.flightController();
        if (fc == null) {
            Sdk.toast(activity, "Drone não conectado.");
            return;
        }
        action.on(fc);
    }

    private static int clamp(int value, int min, int max) {
        return Math.max(min, Math.min(max, value));
    }

    private static String obstacleLabel(ObstacleActionMode mode) {
        switch (mode) {
            case APAS:
                return "Desviar (APAS)";
            case STOP:
                return "Frear";
            case CLOSE:
                return "Desligado";
            default:
                return mode.name().toLowerCase(Locale.ROOT);
        }
    }

    private static String failSafeLabel(ConnectionFailSafeBehavior behavior) {
        switch (behavior) {
            case GO_HOME:
                return "Retornar para casa (RTH)";
            case LANDING:
                return "Pousar";
            case HOVER:
                return "Pairar";
            default:
                return behavior.name().toLowerCase(Locale.ROOT);
        }
    }
}
