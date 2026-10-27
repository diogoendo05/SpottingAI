package br.edu.spottingai.drone;

import android.os.SystemClock;
import android.util.Log;

import java.util.ArrayList;
import java.util.List;

import dji.common.airlink.FrequencyInterference;
import dji.common.airlink.OcuSyncWarningMessage;
import dji.common.airlink.SignalQualityCallback;
import dji.sdk.airlink.AirLink;
import dji.sdk.airlink.OcuSyncLink;
import dji.sdk.base.BaseProduct;

/**
 * Estado do radio drone <-> controle (OcuSync): qualidade do sinal de subida e
 * descida, taxa de video do link, avisos de interferencia e o espectro de
 * interferencia por frequencia (o grafico da aba Transmissao do DJI Fly).
 *
 * <p>Os callbacks so gravam valores; a UI le periodicamente. No Air 2S os
 * callbacks do {@code AirLink} podem nunca disparar, entao a inscricao e feita
 * direto no {@link OcuSyncLink} e refeita se as atualizacoes pararem.</p>
 */
final class LinkMonitor {

    private static final String TAG = "LinkMonitor";
    /** Sem atualizacao por este tempo => o SDK trocou o objeto do link; reinscreve. */
    private static final long STALE_MS = 5000;

    /** Qualidade 0-100 do video drone -> controle; -1 = desconhecida. */
    volatile int downlink = -1;
    /** Qualidade 0-100 dos comandos controle -> drone; -1 = desconhecida. */
    volatile int uplink = -1;
    /** Taxa de video atual do link em Mbps; -1 = desconhecida. */
    volatile float rateMbps = -1;
    volatile OcuSyncWarningMessage[] warnings = new OcuSyncWarningMessage[0];
    volatile FrequencyInterference[] interference = new FrequencyInterference[0];

    private AirLink airLink;
    private OcuSyncLink ocuSyncLink;
    private volatile long lastUpdateAt;
    private long lastAttachAt;

    /** OcuSyncLink atual, ou {@code null} se o drone nao tiver (ou ainda nao expuser) um. */
    OcuSyncLink link() {
        return ocuSyncLink;
    }

    /** Chamado a cada segundo: inscreve na primeira vez e reinscreve se ficou mudo. */
    void ensure(BaseProduct product) {
        long now = SystemClock.elapsedRealtime();
        boolean stale = now - lastUpdateAt > STALE_MS;
        if ((ocuSyncLink == null && airLink == null) || (stale && now - lastAttachAt > STALE_MS)) {
            attach(product);
        }
    }

    private void attach(BaseProduct product) {
        lastAttachAt = SystemClock.elapsedRealtime();
        detach();
        try {
            airLink = product != null ? product.getAirLink() : null;
            if (airLink == null) return;
            ocuSyncLink = airLink.isOcuSyncLinkSupported() ? airLink.getOcuSyncLink() : null;
            if (ocuSyncLink != null) {
                ocuSyncLink.setDownlinkSignalQualityCallback(downlinkCallback);
                ocuSyncLink.setUplinkSignalQualityCallback(uplinkCallback);
                ocuSyncLink.setVideoDataRateCallback(rate -> {
                    rateMbps = rate;
                    touch();
                });
                ocuSyncLink.setWarningMessagesCallback(messages -> {
                    warnings = messages != null ? messages : new OcuSyncWarningMessage[0];
                    touch();
                });
                ocuSyncLink.setChannelInterferenceCallback(values -> {
                    if (values != null) interference = values;
                    touch();
                });
            } else {
                airLink.setDownlinkSignalQualityCallback(downlinkCallback);
                airLink.setUplinkSignalQualityCallback(uplinkCallback);
            }
            Log.i(TAG, "Inscrito no link de radio (OcuSync=" + (ocuSyncLink != null) + ")");
        } catch (Exception e) {
            Log.w(TAG, "Link de radio sem telemetria", e);
        }
    }

    void detach() {
        try {
            if (ocuSyncLink != null) {
                ocuSyncLink.setDownlinkSignalQualityCallback(null);
                ocuSyncLink.setUplinkSignalQualityCallback(null);
                ocuSyncLink.setVideoDataRateCallback(null);
                ocuSyncLink.setWarningMessagesCallback(null);
                ocuSyncLink.setChannelInterferenceCallback(null);
            } else if (airLink != null) {
                airLink.setDownlinkSignalQualityCallback(null);
                airLink.setUplinkSignalQualityCallback(null);
            }
        } catch (Exception ignored) {
        }
        airLink = null;
        ocuSyncLink = null;
    }

    /** Drone desconectou: zera tudo para a UI nao mostrar valores velhos. */
    void reset() {
        detach();
        downlink = -1;
        uplink = -1;
        rateMbps = -1;
        warnings = new OcuSyncWarningMessage[0];
        interference = new FrequencyInterference[0];
        lastUpdateAt = 0;
    }

    private final SignalQualityCallback downlinkCallback = percent -> {
        downlink = percent;
        touch();
    };

    private final SignalQualityCallback uplinkCallback = percent -> {
        uplink = percent;
        touch();
    };

    private void touch() {
        lastUpdateAt = SystemClock.elapsedRealtime();
    }

    /** Avisos do radio em portugues (os que o DJI Fly tambem mostra). */
    List<String> warningTexts() {
        List<String> out = new ArrayList<>();
        for (OcuSyncWarningMessage message : warnings) {
            String text = describe(message);
            if (text != null && !out.contains(text)) out.add(text);
        }
        return out;
    }

    private static String describe(OcuSyncWarningMessage message) {
        if (message == null) return null;
        switch (message) {
            case STRONG_TAKE_OFF_INTERFERENCE:
                return "Interferência forte no local de decolagem";
            case STRONG_DOWN_LINK_INTERFERENCE:
                return "Interferência forte no vídeo (descida)";
            case STRONG_UP_LINK_INTERFERENCE:
                return "Interferência forte nos comandos (subida)";
            case WEAK_SIGNAL:
                return "Sinal fraco - aproxime o drone / aponte as antenas";
            case STRONG_INTERFERENCE_WITH_MANUAL_SETTING:
                return "Canal manual com interferência - use canal automático";
            case UP_LINK_BROKEN:
                return "Link de comandos perdido";
            case DOWN_LINK_BROKEN:
                return "Link de vídeo perdido";
            case LINK_UNUSABLE:
                return "Link de rádio inutilizável";
            case AIRCRAFT_LINK_REBOOT:
                return "Rádio do drone reiniciando";
            default:
                return null;  // DEBUG e avisos de oculos (Goggles) nao se aplicam
        }
    }
}
