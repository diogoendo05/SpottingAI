package br.edu.spottingai.drone;

import java.util.ArrayList;
import java.util.List;

import dji.common.battery.BatteryState;
import dji.common.flightcontroller.Attitude;
import dji.common.flightcontroller.FlightControllerState;
import dji.common.flightcontroller.FlightMode;
import dji.common.flightcontroller.GoHomeAssessment;
import dji.common.flightcontroller.LocationCoordinate3D;
import dji.common.model.LocationCoordinate2D;
import dji.sdk.base.BaseProduct;
import dji.sdk.battery.Battery;
import dji.sdk.flightcontroller.FlightController;
import dji.sdk.products.Aircraft;

/**
 * Telemetria de voo para o HUD: bateria, altitude, distancia e posicao em
 * relacao a casa, velocidades, rumo, GPS, modo de voo, tempo de voo restante
 * e alertas.
 *
 * <p>Os callbacks do SDK ({@code FlightController.setStateCallback} ~10 Hz e
 * {@code Battery.setStateCallback}) so gravam os valores (campos volateis);
 * a tela le periodicamente.</p>
 */
final class TelemetryMonitor {

    volatile boolean hasFlightData;
    volatile int batteryPercent = -1;
    /** Altura em metros relativa ao ponto de decolagem. */
    volatile float altitude;
    /** Distancia horizontal ate a casa em metros; -1 = sem casa/GPS. */
    volatile double distanceHome = -1;
    /** Posicao do drone em relacao a casa, em metros (norte / leste). */
    volatile double offsetNorth;
    volatile double offsetEast;
    volatile float horizontalSpeed;
    /** Velocidade vertical em m/s, positiva subindo. */
    volatile float verticalSpeed;
    /** Rumo do nariz do drone em graus (0 = norte, sentido horario). */
    volatile double heading;
    volatile int satellites;
    volatile String gpsLevel = "";
    volatile String flightModeText = "";
    volatile FlightMode flightMode;
    volatile boolean flying;
    volatile boolean motorsOn;
    volatile boolean homeSet;
    volatile boolean goingHome;
    volatile boolean landingConfirmationNeeded;
    volatile boolean lowBattery;
    volatile boolean seriousLowBattery;
    /** Tempo de voo restante estimado pelo drone, em segundos; -1 = desconhecido. */
    volatile int remainingFlightTime = -1;
    volatile int flightTimeSeconds;

    /** Sinal e avisos do radio (inscrito pela MainActivity). */
    private final LinkMonitor link;

    private FlightController flightController;
    private Battery battery;

    TelemetryMonitor(LinkMonitor link) {
        this.link = link;
    }

    FlightController flightController() {
        return flightController;
    }

    void attach(BaseProduct product) {
        detach();
        if (product instanceof Aircraft) {
            flightController = ((Aircraft) product).getFlightController();
            if (flightController != null) {
                flightController.setStateCallback(new FlightControllerState.Callback() {
                    @Override
                    public void onUpdate(FlightControllerState state) {
                        onFlightState(state);
                    }
                });
            }
        }
        battery = product.getBattery();
        if (battery != null) {
            battery.setStateCallback(new BatteryState.Callback() {
                @Override
                public void onUpdate(BatteryState state) {
                    batteryPercent = state.getChargeRemainingInPercent();
                }
            });
        }
    }

    void detach() {
        try {
            if (flightController != null) flightController.setStateCallback(null);
            if (battery != null) battery.setStateCallback(null);
        } catch (Exception ignored) {
        }
        flightController = null;
        battery = null;
        hasFlightData = false;
        batteryPercent = -1;
        remainingFlightTime = -1;
    }

    private void onFlightState(FlightControllerState state) {
        LocationCoordinate3D aircraft = state.getAircraftLocation();
        LocationCoordinate2D home = state.getHomeLocation();
        if (aircraft != null) {
            altitude = aircraft.getAltitude();
            homeSet = state.isHomeLocationSet();
            if (homeSet && home != null && isValid(aircraft.getLatitude(), aircraft.getLongitude())
                    && isValid(home.getLatitude(), home.getLongitude())) {
                distanceHome = haversine(aircraft.getLatitude(), aircraft.getLongitude(),
                        home.getLatitude(), home.getLongitude());
                double metersPerDegree = 111_320.0;
                offsetNorth = (aircraft.getLatitude() - home.getLatitude()) * metersPerDegree;
                offsetEast = (aircraft.getLongitude() - home.getLongitude()) * metersPerDegree
                        * Math.cos(Math.toRadians(home.getLatitude()));
            } else {
                distanceHome = -1;
            }
        }
        float vx = state.getVelocityX();
        float vy = state.getVelocityY();
        horizontalSpeed = (float) Math.sqrt(vx * vx + vy * vy);
        verticalSpeed = -state.getVelocityZ();  // NED: Z positivo e para baixo
        Attitude attitude = state.getAttitude();
        if (attitude != null) heading = (attitude.yaw + 360.0) % 360.0;
        satellites = state.getSatelliteCount();
        gpsLevel = String.valueOf(state.getGPSSignalLevel());
        flightMode = state.getFlightMode();
        String modeText = state.getFlightModeString();
        flightModeText = modeText != null ? modeText : String.valueOf(flightMode);
        flying = state.isFlying();
        motorsOn = state.areMotorsOn();
        goingHome = state.isGoingHome();
        landingConfirmationNeeded = state.isLandingConfirmationNeeded();
        lowBattery = state.isLowerThanBatteryWarningThreshold();
        seriousLowBattery = state.isLowerThanSeriousBatteryWarningThreshold();
        flightTimeSeconds = state.getFlightTimeInSeconds();
        GoHomeAssessment assessment = state.getGoHomeAssessment();
        remainingFlightTime = assessment != null ? assessment.getRemainingFlightTime() : -1;
        hasFlightData = true;
    }

    /** Situacao do voo em uma palavra, como no topo do DJI Fly. */
    String statusText() {
        if (!hasFlightData) return "SEM DRONE";
        String mode = flightMode != null ? flightMode.name() : "";
        if (goingHome || mode.contains("GO_HOME")) return "RETORNANDO";
        if (mode.contains("LANDING")) return "POUSANDO";
        if (mode.contains("TAKEOFF")) return "DECOLANDO";
        if (flying) return "EM VOO";
        if (motorsOn) return "MOTORES ON";
        return homeSet && !isWeakGps() ? "PRONTO (GPS)" : "NO SOLO";
    }

    boolean isLanding() {
        return flightMode != null && flightMode.name().contains("LANDING");
    }

    boolean isWeakGps() {
        String level = gpsLevel;
        return level.isEmpty() || level.equals("NONE") || level.endsWith("_0")
                || level.endsWith("_1") || level.endsWith("_2") || satellites < 8;
    }

    /** Alertas de seguranca em ordem de gravidade. */
    List<String> warnings() {
        List<String> warnings = new ArrayList<>();
        if (!hasFlightData) return warnings;
        if (seriousLowBattery) warnings.add("BATERIA CRITICA - POUSE AGORA");
        else if (lowBattery || (batteryPercent >= 0 && batteryPercent <= 30)) warnings.add("Bateria baixa - volte");
        if (landingConfirmationNeeded) warnings.add("Pouso pausado a 0,5 m: confirme o pouso");
        if (!homeSet) warnings.add("Home point NAO gravado - aguarde GPS antes de decolar");
        if (isWeakGps()) warnings.add("GPS fraco");
        if (goingHome) warnings.add("Retorno para casa (RTH) em andamento");
        int down = link.downlink;
        if (down >= 0 && down < 30) warnings.add("Sinal de video fraco - aproxime o drone");
        int up = link.uplink;
        if (up >= 0 && up < 30) warnings.add("Sinal do CONTROLE fraco (" + up + "%) - comandos podem nao chegar ao drone");
        for (String text : link.warningTexts()) {
            if (!warnings.contains(text)) warnings.add(text);
        }
        return warnings;
    }

    private static boolean isValid(double lat, double lon) {
        return !Double.isNaN(lat) && !Double.isNaN(lon) && Math.abs(lat) <= 90 && Math.abs(lon) <= 180
                && !(lat == 0 && lon == 0);
    }

    private static double haversine(double lat1, double lon1, double lat2, double lon2) {
        double r = 6371000.0;
        double dLat = Math.toRadians(lat2 - lat1);
        double dLon = Math.toRadians(lon2 - lon1);
        double a = Math.sin(dLat / 2) * Math.sin(dLat / 2)
                + Math.cos(Math.toRadians(lat1)) * Math.cos(Math.toRadians(lat2))
                * Math.sin(dLon / 2) * Math.sin(dLon / 2);
        return 2 * r * Math.asin(Math.sqrt(a));
    }
}
