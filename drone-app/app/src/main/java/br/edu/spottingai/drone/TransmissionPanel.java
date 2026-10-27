package br.edu.spottingai.drone;

import android.app.Activity;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;
import android.view.View;
import android.widget.Button;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.TextView;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;

import dji.common.airlink.ChannelSelectionMode;
import dji.common.airlink.FrequencyInterference;
import dji.common.airlink.OcuSyncBandwidth;
import dji.common.airlink.OcuSyncFrequencyBand;
import dji.common.error.DJIError;
import dji.common.util.CommonCallbacks;
import dji.sdk.airlink.OcuSyncLink;

/**
 * Configuracoes de transmissao do radio, equivalentes a aba Transmissao do
 * DJI Fly: frequencia (2,4 / 5,8 / dupla), modo de canal (automatico ou
 * manual), canal e largura de banda (10/20/40 MHz), grafico de interferencia
 * e estado do link.
 *
 * <p>Comportamento medido no Air 2S com o MSDK 4.18, que guia este codigo:</p>
 * <ul>
 *   <li>{@code setFrequencyBand} funciona, mas o radio reinicia e por ~15 s
 *       toda chamada volta "Invalid key for component": o painel fica
 *       bloqueado nesse intervalo em vez de disparar erros;</li>
 *   <li>{@code getFrequencyBand} nunca responde: a banda atual e deduzida da
 *       faixa de canais (MHz) e do grafico de interferencia;</li>
 *   <li>modo de canal, canal e largura de banda dao "tempo esgotado": apos
 *       {@link #CHANNEL_TIMEOUT_LIMIT} falhas o modo manual e desativado com
 *       uma explicacao, sem novas tentativas.</li>
 * </ul>
 * <p>So envia ao drone o que o usuario escolher no painel.</p>
 */
final class TransmissionPanel {

    private static final String TAG = "TransmissionPanel";
    private static final String PREF_BAND = "link_band";
    private static final String PREF_MODE = "link_mode";
    private static final String PREF_BW = "link_bw";
    private static final String PREF_CHANNEL = "link_channel";
    /** Espera depois de tocar em +/- no canal antes de enviar ao drone. */
    private static final long CHANNEL_DEBOUNCE_MS = 800;
    /** Tempo que o radio leva para voltar a aceitar comandos depois de trocar a banda. */
    private static final long BAND_SETTLE_MS = 15_000;
    /** Limite de seguranca enquanto o drone nao confirma a troca. */
    private static final long BAND_COMMAND_MS = 25_000;
    /** Prazo, apos o reinicio do radio, para a leitura confirmar a nova banda. */
    private static final long VERIFY_MS = 10_000;
    /** Tempos esgotados seguidos ate considerar canal/banda manual indisponiveis. */
    private static final int CHANNEL_TIMEOUT_LIMIT = 2;

    private interface Ok<T> {
        void on(T value);
    }

    private final Activity activity;
    private final SharedPreferences prefs;
    private final LinkMonitor monitor;
    private final TelemetryMonitor telemetry;
    private final View presetBox;
    private final TextView presetNote;

    // Configuracao fixa: Manual · 1080p (HD Live View) · 2,4 GHz · 20 MHz.
    private static final String PREF_FIXED_AUTO = "fixed_preset_auto";
    private static final OcuSyncFrequencyBand FIXED_BAND = OcuSyncFrequencyBand.FREQUENCY_BAND_2_DOT_4_GHZ;
    private static final int FIXED_BW_MHZ = 20;
    /** Prazo para cada etapa (troca de banda, grafico em 2,4 GHz) antes de desistir. */
    private static final long FIXED_STAGE_MS = 40_000;

    private enum FixedStage { IDLE, WAIT_BAND, WAIT_SPECTRUM }

    private final Runnable applyLiveDefinition;
    private final TextView fixedStatus;
    private final android.widget.CheckBox fixedAuto;
    private FixedStage fixedStage = FixedStage.IDLE;
    private long fixedDeadline;
    /** Ja aplicada (ou tentada) automaticamente nesta conexao. */
    private boolean fixedAutoDone;
    private final Handler ui = new Handler(Looper.getMainLooper());

    private final RadioGroup bandGroup;
    private final RadioButton band24;
    private final RadioButton band58;
    private final RadioButton bandDual;
    private final TextView bandNote;
    private final RadioButton modeAuto;
    private final RadioButton modeManual;
    private final TextView modeNote;
    private final View manualBox;
    private final TextView channelValue;
    private final Button channelMinus;
    private final Button channelPlus;
    private final RadioButton bw10;
    private final RadioButton bw20;
    private final RadioButton bw40;
    private final InterferenceView interferenceView;
    private final TextView linkStatus;
    private final Button resetButton;

    /** Evita reenviar ao drone quando o proprio app marca um radio. */
    private boolean updatingUi;
    private boolean connected;
    private List<OcuSyncFrequencyBand> supportedBands = new ArrayList<>();
    /** Banda confirmada pelo drone (set OK) ou escolhida pelo usuario; null = desconhecida. */
    private OcuSyncFrequencyBand chosenBand;
    /** Banda em uso deduzida do grafico de interferencia ou da faixa de canais (2,4 ou 5,8). */
    private OcuSyncFrequencyBand activeBand;
    private OcuSyncFrequencyBand spectrumBand;
    private OcuSyncFrequencyBand rangeBand;
    /** Troca pedida aguardando confirmacao pela leitura da banda. */
    private OcuSyncFrequencyBand requestedBand;
    private long verifyDeadline;
    /** Radio reiniciando (troca de banda): nada e enviado ate este instante. */
    private long busyUntil;
    private boolean bandCommandPending;

    private ChannelSelectionMode mode;
    private OcuSyncBandwidth bandwidth;
    private int channel = -1;
    private final List<Integer> channels = new ArrayList<>();
    /** null = ainda verificando; true/false = o drone responde ao modo de canal. */
    private Boolean channelControlSupported;
    private int channelTimeouts;
    private boolean channelQueryInFlight;
    private long lastRefreshAt;

    private final Runnable sendChannel = this::applyPendingChannel;
    private int pendingChannel = -1;

    TransmissionPanel(Activity activity, SharedPreferences prefs, LinkMonitor monitor, TelemetryMonitor telemetry,
                      Runnable applyLiveDefinition) {
        this.activity = activity;
        this.prefs = prefs;
        this.monitor = monitor;
        this.telemetry = telemetry;
        this.applyLiveDefinition = applyLiveDefinition;
        fixedStatus = activity.findViewById(R.id.fixed_preset_status);
        fixedAuto = activity.findViewById(R.id.chk_fixed_preset_auto);
        fixedAuto.setChecked(prefs.getBoolean(PREF_FIXED_AUTO, true));
        fixedAuto.setOnCheckedChangeListener((b, checked) -> prefs.edit().putBoolean(PREF_FIXED_AUTO, checked).apply());
        activity.findViewById(R.id.btn_fixed_preset).setOnClickListener(v -> startFixedPreset(true));
        presetBox = activity.findViewById(R.id.preset_box);
        presetNote = activity.findViewById(R.id.preset_note);
        activity.findViewById(R.id.btn_preset_range).setOnClickListener(
                v -> applyPreset("Alcance máximo", OcuSyncBandwidth.Bandwidth10MHz, 10));
        activity.findViewById(R.id.btn_preset_balanced).setOnClickListener(
                v -> applyPreset("Equilibrado", OcuSyncBandwidth.Bandwidth20MHz, 20));
        activity.findViewById(R.id.btn_preset_quality).setOnClickListener(
                v -> applyPreset("Qualidade máxima", OcuSyncBandwidth.Bandwidth40MHZ, 40));
        activity.findViewById(R.id.btn_preset_auto).setOnClickListener(v -> presetAuto());

        bandGroup = activity.findViewById(R.id.band_group);
        band24 = activity.findViewById(R.id.band_24);
        band58 = activity.findViewById(R.id.band_58);
        bandDual = activity.findViewById(R.id.band_dual);
        bandNote = activity.findViewById(R.id.band_note);
        modeAuto = activity.findViewById(R.id.mode_auto);
        modeManual = activity.findViewById(R.id.mode_manual);
        modeNote = activity.findViewById(R.id.mode_note);
        manualBox = activity.findViewById(R.id.manual_box);
        channelValue = activity.findViewById(R.id.channel_value);
        channelMinus = activity.findViewById(R.id.btn_channel_minus);
        channelPlus = activity.findViewById(R.id.btn_channel_plus);
        bw10 = activity.findViewById(R.id.bw_10);
        bw20 = activity.findViewById(R.id.bw_20);
        bw40 = activity.findViewById(R.id.bw_40);
        interferenceView = activity.findViewById(R.id.interference_view);
        linkStatus = activity.findViewById(R.id.link_status);
        resetButton = activity.findViewById(R.id.btn_link_reset);

        bandGroup.setOnCheckedChangeListener((g, id) -> {
            if (updatingUi || id == -1) return;
            OcuSyncFrequencyBand chosen = id == R.id.band_24 ? OcuSyncFrequencyBand.FREQUENCY_BAND_2_DOT_4_GHZ
                    : id == R.id.band_58 ? OcuSyncFrequencyBand.FREQUENCY_BAND_5_DOT_8_GHZ
                    : OcuSyncFrequencyBand.FREQUENCY_BAND_DUAL;
            changeBand(chosen, true);
        });
        ((RadioGroup) activity.findViewById(R.id.mode_group)).setOnCheckedChangeListener((g, id) -> {
            if (updatingUi || id == -1) return;
            ChannelSelectionMode chosen = id == R.id.mode_manual ? ChannelSelectionMode.MANUAL : ChannelSelectionMode.AUTO;
            prefs.edit().putString(PREF_MODE, chosen.name()).apply();
            manualBox.setVisibility(chosen == ChannelSelectionMode.MANUAL ? View.VISIBLE : View.GONE);
            send("Modo de canal", link -> link.setChannelSelectionMode(chosen, result("Modo de canal", () -> {
                mode = chosen;
                queryChannelSettings();
            })));
        });
        ((RadioGroup) activity.findViewById(R.id.bw_group)).setOnCheckedChangeListener((g, id) -> {
            if (updatingUi || id == -1) return;
            OcuSyncBandwidth chosen = id == R.id.bw_10 ? OcuSyncBandwidth.Bandwidth10MHz
                    : id == R.id.bw_40 ? OcuSyncBandwidth.Bandwidth40MHZ
                    : OcuSyncBandwidth.Bandwidth20MHz;
            prefs.edit().putString(PREF_BW, chosen.name()).apply();
            send("Largura de banda", link -> link.setChannelBandwidth(chosen,
                    result("Largura de banda", () -> bandwidth = chosen)));
        });
        channelMinus.setOnClickListener(v -> stepChannel(-1));
        channelPlus.setOnClickListener(v -> stepChannel(1));
        resetButton.setOnClickListener(v -> resetToAuto());

        onProductDisconnected();
    }

    // -- ciclo de vida ------------------------------------------------------ //

    /**
     * Drone conectado: le o radio. A frequencia nao e reaplicada (o drone a
     * guarda sozinho e cada troca reinicia o radio por ~15 s); a escolha salva
     * so serve para mostrar "Dupla", que nao da para deduzir do espectro.
     */
    void onProductConnected() {
        if (monitor.link() == null) {
            // O radio costuma aparecer alguns segundos depois do produto.
            ui.postDelayed(this::onProductConnected, 2000);
            return;
        }
        connected = true;
        chosenBand = saved(PREF_BAND, OcuSyncFrequencyBand.class);
        refresh();
    }

    void onProductDisconnected() {
        ui.removeCallbacksAndMessages(null);
        connected = false;
        busyUntil = 0;
        bandCommandPending = false;
        activeBand = null;
        spectrumBand = null;
        rangeBand = null;
        requestedBand = null;
        channelControlSupported = null;
        channelTimeouts = 0;
        channelQueryInFlight = false;
        setBandRadiosEnabled(false);
        setChannelControlsEnabled(false);
        resetButton.setEnabled(false);
        bandNote.setText(R.string.band_waiting);
        modeNote.setVisibility(View.GONE);
        presetBox.setVisibility(View.GONE);
        fixedStage = FixedStage.IDLE;
        fixedAutoDone = false;
    }

    /** Chamado 1x por segundo: sinal, grafico, fim do bloqueio pos-troca e releituras. */
    void tick() {
        long now = SystemClock.elapsedRealtime();
        FrequencyInterference[] spectrum = monitor.interference;
        interferenceView.setValues(spectrum);
        inferBandFrom(spectrum);

        String down = monitor.downlink >= 0 ? monitor.downlink + "%" : "--";
        String up = monitor.uplink >= 0 ? monitor.uplink + "%" : "--";
        linkStatus.setText(String.format(Locale.ROOT, "Sinal de vídeo %s · comandos %s\n%s · %s",
                down, up, bandSummary(), channelSummary()));

        if (!connected) return;
        if (isBusy(now)) {
            long seconds = (busyUntil - now + 999) / 1000;
            bandNote.setText(bandCommandPending
                    ? "Enviando a troca de frequência ao drone…"
                    : "Rádio reiniciando na nova frequência… aguarde " + seconds + " s (o vídeo pode piscar).");
            return;
        }
        if (busyUntil != 0) {
            busyUntil = 0;  // acabou o bloqueio: rele o estado e libera os controles
            verifyDeadline = now + VERIFY_MS;
            refresh();
        } else if (requestedBand != null) {
            bandNote.setText("Confirmando a nova frequência com o rádio…");
            verifyBandChange(now);
            if (requestedBand == null) bandNote.setText(bandHint());
        } else if (supportedBands.isEmpty() && now - lastRefreshAt > 10_000) {
            refresh();  // o radio nao respondeu antes: tenta de novo com calma
        }
        if (!isBusy(now) && requestedBand == null) advanceFixedPreset(now);
    }

    // -- leitura do drone --------------------------------------------------- //

    private void refresh() {
        lastRefreshAt = SystemClock.elapsedRealtime();
        OcuSyncLink link = monitor.link();
        if (link == null || isBusy(lastRefreshAt)) return;

        link.getSupportedFrequencyBands(got("getSupportedFrequencyBands", bands -> {
            supportedBands = Arrays.asList(bands);
            setBandRadiosEnabled(true);
            resetButton.setEnabled(true);
            showBand();
            bandNote.setText(bandHint());
        }, error -> {
            if (supportedBands.isEmpty()) {
                bandNote.setText("O rádio ainda não respondeu (" + friendly(error) + "). Tentando de novo…");
            }
        }));
        link.getChannelNumberValidRange(got("getChannelNumberValidRange", range -> {
            channels.clear();
            channels.addAll(expandRange(range));
            // A faixa vem em MHz (ex.: 5735-5839): indica a banda quando ainda nao ha grafico.
            if (!channels.isEmpty()) {
                rangeBand = channels.get(0) >= 5000
                        ? OcuSyncFrequencyBand.FREQUENCY_BAND_5_DOT_8_GHZ
                        : OcuSyncFrequencyBand.FREQUENCY_BAND_2_DOT_4_GHZ;
                updateActiveBand();
            }
            showChannel();
        }, null));
        queryChannelSettings();
    }

    /**
     * Modo de canal, banda e canal. No Air 2S o drone nao responde a essas
     * chaves: depois de {@link #CHANNEL_TIMEOUT_LIMIT} tempos esgotados o
     * modo manual e marcado como indisponivel e nao e mais consultado.
     */
    private void queryChannelSettings() {
        OcuSyncLink link = monitor.link();
        if (link == null || Boolean.FALSE.equals(channelControlSupported) || channelQueryInFlight) return;
        channelQueryInFlight = true;
        if (channelControlSupported == null) {
            modeNote.setText("Verificando se o drone aceita canal manual…");
            modeNote.setVisibility(View.VISIBLE);
        }
        link.getChannelSelectionMode(got("getChannelSelectionMode", value -> {
            channelQueryInFlight = false;
            channelControlSupported = true;
            channelTimeouts = 0;
            mode = value;
            modeNote.setVisibility(View.GONE);
            setChannelControlsEnabled(true);
            updatingUi = true;
            modeAuto.setChecked(value == ChannelSelectionMode.AUTO);
            modeManual.setChecked(value == ChannelSelectionMode.MANUAL);
            updatingUi = false;
            manualBox.setVisibility(value == ChannelSelectionMode.MANUAL ? View.VISIBLE : View.GONE);
            if (value == ChannelSelectionMode.MANUAL) queryManualDetails(link);
        }, error -> {
            channelQueryInFlight = false;
            // Ja respondeu antes nesta conexao: o timeout e do link (sinal do controle), nao falta de suporte.
            if (Boolean.TRUE.equals(channelControlSupported)) {
                ui.postDelayed(this::queryChannelSettings, 4000);
                return;
            }
            if (error.toLowerCase(Locale.ROOT).contains("timed out") && ++channelTimeouts >= CHANNEL_TIMEOUT_LIMIT) {
                channelControlSupported = false;
                setChannelControlsEnabled(false);
                manualBox.setVisibility(View.GONE);
                modeNote.setText("O drone não responde às leituras de modo de canal, canal e largura de banda "
                        + "(DJI SDK v4), então os controles normais ficam desligados. Use as predefinições "
                        + "abaixo: elas enviam a configuração mesmo sem resposta.");
                modeNote.setVisibility(View.VISIBLE);
                presetBox.setVisibility(View.VISIBLE);
            } else {
                ui.postDelayed(this::queryChannelSettings, 4000);
            }
        }));
    }

    private void queryManualDetails(OcuSyncLink link) {
        link.getChannelBandwidth(got("getChannelBandwidth", value -> {
            bandwidth = value;
            updatingUi = true;
            bw10.setChecked(value == OcuSyncBandwidth.Bandwidth10MHz);
            bw20.setChecked(value == OcuSyncBandwidth.Bandwidth20MHz);
            bw40.setChecked(value == OcuSyncBandwidth.Bandwidth40MHZ);
            updatingUi = false;
        }, null));
        link.getChannelNumber(got("getChannelNumber", value -> {
            channel = value;
            if (pendingChannel < 0) showChannel();
        }, null));
    }

    /** A faixa valida vem como {@code [minimo, maximo]}; uma lista maior ja e a lista de canais. */
    private static List<Integer> expandRange(Integer[] range) {
        List<Integer> out = new ArrayList<>();
        if (range == null) return out;
        if (range.length == 2 && range[0] != null && range[1] != null && range[1] >= range[0]) {
            for (int c = range[0]; c <= range[1]; c++) out.add(c);
        } else {
            for (Integer c : range) if (c != null) out.add(c);
        }
        return out;
    }

    /**
     * Banda coberta pelo grafico de interferencia. ATENCAO: no Air 2S o grafico
     * mostra 2,4 GHz mesmo com o radio em 5,8 GHz (medido: grafico 2,4 com faixa
     * de canais 5735-5839 e "Param Illegal" ao pedir canal 2472). Por isso so
     * serve para escolher o canal mais limpo, nunca para dizer a banda em uso.
     */
    private void inferBandFrom(FrequencyInterference[] spectrum) {
        if (spectrum == null || spectrum.length == 0) return;
        spectrumBand = spectrum[0].frequencyFrom >= 5000
                ? OcuSyncFrequencyBand.FREQUENCY_BAND_5_DOT_8_GHZ
                : OcuSyncFrequencyBand.FREQUENCY_BAND_2_DOT_4_GHZ;
    }

    /** A banda em uso vem da faixa valida de canais informada pelo drone (em MHz). */
    private void updateActiveBand() {
        OcuSyncFrequencyBand value = rangeBand;
        if (value == activeBand) return;
        activeBand = value;
        showBand();
    }

    /** Marca a banda real do radio (a escolha salva so vale para mostrar "Dupla"). */
    private void showBand() {
        OcuSyncFrequencyBand shown = chosenBand == OcuSyncFrequencyBand.FREQUENCY_BAND_DUAL
                ? chosenBand : activeBand != null ? activeBand : chosenBand;
        updatingUi = true;
        if (shown == null) bandGroup.clearCheck();
        else if (shown == OcuSyncFrequencyBand.FREQUENCY_BAND_2_DOT_4_GHZ) band24.setChecked(true);
        else if (shown == OcuSyncFrequencyBand.FREQUENCY_BAND_5_DOT_8_GHZ) band58.setChecked(true);
        else if (shown == OcuSyncFrequencyBand.FREQUENCY_BAND_DUAL) bandDual.setChecked(true);
        updatingUi = false;
    }

    private void showChannel() {
        int shown = pendingChannel >= 0 ? pendingChannel : channel;
        String range = channels.isEmpty() ? ""
                : " (" + channels.get(0) + "–" + channels.get(channels.size() - 1) + " MHz)";
        channelValue.setText((shown >= 0 ? shown + " MHz" : "Canal ?") + range);
    }

    // -- escrita no drone ---------------------------------------------------- //

    /** Troca a banda e bloqueia o painel ate o radio reiniciar. */
    private void changeBand(OcuSyncFrequencyBand value, boolean userAction) {
        OcuSyncLink link = monitor.link();
        long now = SystemClock.elapsedRealtime();
        if (link == null) {
            if (userAction) toast("Drone não conectado.");
            showBand();
            return;
        }
        if (isBusy(now) || requestedBand != null) {
            toast("Aguarde: o rádio ainda está aplicando a troca anterior.");
            showBand();
            return;
        }
        if (value != OcuSyncFrequencyBand.FREQUENCY_BAND_DUAL && value == activeBand
                && chosenBand != OcuSyncFrequencyBand.FREQUENCY_BAND_DUAL) {
            toast("O rádio já está em " + bandLabel(value) + ".");
            showBand();
            return;
        }
        bandCommandPending = true;
        busyUntil = now + BAND_COMMAND_MS;
        setBandRadiosEnabled(false);
        setChannelControlsEnabled(false);
        resetButton.setEnabled(false);
        // Esquece a banda vista antes: so a leitura depois da troca vale como confirmacao.
        monitor.interference = new FrequencyInterference[0];
        spectrumBand = null;
        rangeBand = null;
        Log.i(TAG, "Trocando banda para " + value);
        link.setFrequencyBand(value, error -> ui.post(() -> {
            bandCommandPending = false;
            Log.i(TAG, "setFrequencyBand(" + value + "): " + (error == null ? "OK" : error.getDescription()));
            String description = error == null ? "" : error.getDescription().toLowerCase(Locale.ROOT);
            // "Tempo esgotado" e normal aqui: o radio troca de banda na hora e a
            // resposta se perde no meio da troca. A confirmacao vem da leitura
            // da banda depois que o radio volta (veja verifyBandChange).
            if (error == null || description.contains("timed out")) {
                requestedBand = value;
                busyUntil = SystemClock.elapsedRealtime() + BAND_SETTLE_MS;
                channelTimeouts = 0;
                if (userAction) toast("Trocando para " + bandLabel(value) + "… aguarde ~15 s.");
                return;
            }
            boolean restarting = description.contains("invalid key");
            // "Invalid key" = radio ainda reiniciando de outra troca: espera mais um pouco.
            busyUntil = restarting ? SystemClock.elapsedRealtime() + BAND_SETTLE_MS : 0;
            showBand();
            if (userAction) toast("Frequência não alterada: " + friendly(error.getDescription()));
            if (fixedStage == FixedStage.WAIT_BAND && !restarting) {
                failFixed("o drone recusou 2,4 GHz (" + friendly(error.getDescription()) + ")");
            }
            if (!restarting) refresh();
        }));
    }

    /**
     * Depois do reinicio do radio, confere pela banda lida se a troca pedida
     * aconteceu, e so entao a registra como escolhida.
     */
    private void verifyBandChange(long now) {
        OcuSyncFrequencyBand wanted = requestedBand;
        if (wanted == null) return;
        boolean confirmed = wanted == OcuSyncFrequencyBand.FREQUENCY_BAND_DUAL
                ? activeBand != null
                : activeBand == wanted;
        if (confirmed) {
            requestedBand = null;
            chosenBand = wanted;
            prefs.edit().putString(PREF_BAND, wanted.name()).apply();
            showBand();
            if (fixedStage == FixedStage.WAIT_BAND && wanted == FIXED_BAND) {
                fixedStage = FixedStage.WAIT_SPECTRUM;
                fixedDeadline = now + FIXED_STAGE_MS;
                fixedStatus.setText("1/3 1080p ✓ · 2/3 2,4 GHz ✓ · 3/3 escolhendo o canal…");
            }
            toast("✓ Frequência: " + bandLabel(wanted)
                    + (wanted == OcuSyncFrequencyBand.FREQUENCY_BAND_DUAL ? " (agora em " + bandLabel(activeBand) + ")" : ""));
        } else if (now <= verifyDeadline) {
            if (now - lastRefreshAt > 3000) refresh();  // faixa de canais ainda nao lida: tenta de novo
        } else {
            requestedBand = null;
            showBand();
            if (fixedStage == FixedStage.WAIT_BAND) failFixed("o drone não confirmou a troca para 2,4 GHz");
            toast(activeBand != null
                    ? "O drone não trocou: continua em " + bandLabel(activeBand) + ". Tente de novo."
                    : "Não deu para confirmar a frequência; veja o gráfico de interferência.");
        }
    }

    /** Envia um comando de canal/banda, se o radio estiver livre e conectado. */
    private void send(String what, Ok<OcuSyncLink> command) {
        OcuSyncLink link = monitor.link();
        if (link == null) {
            toast("Drone não conectado.");
            return;
        }
        if (isBusy(SystemClock.elapsedRealtime())) {
            toast("Aguarde: o rádio está reiniciando na nova frequência.");
            return;
        }
        Log.i(TAG, "Enviando: " + what);
        command.on(link);
    }

    private void stepChannel(int delta) {
        if (channels.isEmpty()) {
            toast("Faixa de canais ainda desconhecida; aguarde o drone responder.");
            return;
        }
        int current = pendingChannel >= 0 ? pendingChannel : channel;
        int index = channels.indexOf(current);
        index = index < 0 ? 0 : Math.max(0, Math.min(channels.size() - 1, index + delta));
        pendingChannel = channels.get(index);
        showChannel();
        ui.removeCallbacks(sendChannel);
        ui.postDelayed(sendChannel, CHANNEL_DEBOUNCE_MS);
    }

    private void applyPendingChannel() {
        int value = pendingChannel;
        if (value < 0) return;
        prefs.edit().putInt(PREF_CHANNEL, value).apply();
        send("Canal", link -> link.setChannelNumber(value, result("Canal", () -> channel = value)));
        pendingChannel = -1;
    }

    // -- configuracao fixa: Manual · 1080p · 2,4 GHz · 20 MHz ---------------- //

    /**
     * Aplica a configuracao fixa em etapas: video ao vivo em 1080p, banda
     * 2,4 GHz (espera o radio reiniciar e confirma pela leitura) e, por fim,
     * canal manual de 20 MHz no canal mais limpo de 2,4 GHz.
     */
    private void startFixedPreset(boolean userAction) {
        if (fixedStage != FixedStage.IDLE) {
            if (userAction) toast("A configuração fixa já está sendo aplicada.");
            return;
        }
        if (!presetAllowed()) return;
        applyLiveDefinition.run();
        fixedStatus.setVisibility(View.VISIBLE);
        long now = SystemClock.elapsedRealtime();
        fixedDeadline = now + FIXED_STAGE_MS;
        if (activeBand == FIXED_BAND && chosenBand != OcuSyncFrequencyBand.FREQUENCY_BAND_DUAL) {
            fixedStage = FixedStage.WAIT_SPECTRUM;
            fixedStatus.setText("1/3 1080p ✓ · 2/3 já em 2,4 GHz ✓ · 3/3 escolhendo o canal…");
        } else if (activeBand == null) {
            // Banda ainda desconhecida: espera a faixa de canais (o tick decide se precisa trocar).
            fixedStage = FixedStage.WAIT_SPECTRUM;
            fixedStatus.setText("1/3 1080p ✓ · 2/3 verificando a banda do rádio…");
            refresh();
        } else {
            fixedStage = FixedStage.WAIT_BAND;
            fixedStatus.setText("1/3 1080p ✓ · 2/3 trocando para 2,4 GHz (~15 s)…");
            changeBand(FIXED_BAND, true);
        }
        Log.i(TAG, "Configuracao fixa iniciada (" + (userAction ? "toque" : "automatica") + "), etapa " + fixedStage);
    }

    /** Avanca as etapas da configuracao fixa (chamado no tick, com o radio livre). */
    private void advanceFixedPreset(long now) {
        // Aplicacao automatica: uma vez por conexao, com o drone no chao e o radio respondendo.
        if (fixedStage == FixedStage.IDLE && !fixedAutoDone && fixedAuto.isChecked() && telemetry.hasFlightData
                && !telemetry.flying && !supportedBands.isEmpty() && monitor.interference.length > 0) {
            fixedAutoDone = true;
            startFixedPreset(false);
            return;
        }
        if (fixedStage == FixedStage.WAIT_SPECTRUM) {
            if (activeBand == FIXED_BAND) {
                fixedStage = FixedStage.IDLE;
                fixedStatus.setText("1/3 1080p ✓ · 2/3 2,4 GHz ✓ · 3/3 enviando canal manual de 20 MHz…");
                applyPreset("Configuração fixa", OcuSyncBandwidth.Bandwidth20MHz, FIXED_BW_MHZ);
            } else if (activeBand != null) {
                // O radio nao esta em 2,4 GHz (a faixa de canais diz outra banda): troca primeiro.
                fixedStage = FixedStage.WAIT_BAND;
                fixedDeadline = now + FIXED_STAGE_MS;
                fixedStatus.setText("1/3 1080p ✓ · 2/3 trocando para 2,4 GHz (~15 s)…");
                changeBand(FIXED_BAND, true);
            } else if (now > fixedDeadline) {
                failFixed("o drone não informou a banda em uso");
            }
        } else if (fixedStage == FixedStage.WAIT_BAND && requestedBand == null && now > fixedDeadline) {
            failFixed("o drone não confirmou a troca para 2,4 GHz");
        }
    }

    private void failFixed(String reason) {
        fixedStage = FixedStage.IDLE;
        fixedStatus.setVisibility(View.VISIBLE);
        fixedStatus.setText("Configuração fixa interrompida: " + reason + ". Toque no botão para tentar de novo.");
        toast("Configuração fixa: " + reason + ".");
    }

    // -- predefinicoes de canal manual ---------------------------------------- //

    /** Pausa entre os comandos de radio: em sequencia imediata o drone recusa ("could not be executed"). */
    private static final long STEP_GAP_MS = 1500;
    private static final int STEP_ATTEMPTS = 3;

    /** Texto de progresso da predefinicao (nas predefinicoes e, se visivel, na configuracao fixa). */
    private void presetProgress(String text) {
        presetNote.setText(text);
        if (fixedStatus.getVisibility() == View.VISIBLE) fixedStatus.setText(text);
    }

    /**
     * Liga o modo manual com a largura de banda pedida e o canal mais limpo:
     * <ol>
     *   <li>modo MANUAL;</li>
     *   <li>largura de banda;</li>
     *   <li>rele a faixa valida de canais (ela depende da banda e da largura)
     *       e escolhe dentro dela o canal com menos interferencia;</li>
     *   <li>canal;</li>
     *   <li>le de volta modo, largura e canal para confirmar.</li>
     * </ol>
     * Cada comando tem pausa antes e ate {@link #STEP_ATTEMPTS} tentativas.
     */
    private void applyPreset(String name, OcuSyncBandwidth bw, int bwMhz) {
        if (!presetAllowed()) return;
        OcuSyncLink link = monitor.link();
        busyUntil = SystemClock.elapsedRealtime() + 60_000;  // libera ao terminar (sucesso ou erro)
        Log.i(TAG, "Predefinicao " + name + ": manual, " + bwMhz + " MHz");
        presetProgress(name + ": 1/4 ligando o modo manual…");
        attempt("Modo manual", 1, cb -> link.setChannelSelectionMode(ChannelSelectionMode.MANUAL, cb), () -> {
            presetProgress(name + ": 2/4 largura de banda " + bwMhz + " MHz…");
            attempt("Largura de banda", 1, cb -> link.setChannelBandwidth(bw, cb), () -> {
                presetProgress(name + ": 3/4 escolhendo o canal…");
                readRangeThen(link, 1, () -> {
                    int target = cleanestChannel(monitor.interference, channels, bwMhz);
                    if (target < 0) {
                        presetFailed(name, "o drone não informou a faixa de canais");
                        return;
                    }
                    presetProgress(name + ": 4/4 canal " + target + " MHz…");
                    attempt("Canal", 1, cb -> link.setChannelNumber(target, cb),
                            () -> verifyManual(link, name, bw, bwMhz, target));
                });
            });
        });
    }

    /** Envia um comando apos a pausa; repete em "tempo esgotado"/"could not be executed". */
    private void attempt(String what, int n, Ok<CommonCallbacks.CompletionCallback<DJIError>> command, Runnable next) {
        ui.postDelayed(() -> command.on(error -> ui.post(() -> {
            String description = error == null ? "OK" : error.getDescription();
            Log.i(TAG, "Predefinicao/" + what + " (tentativa " + n + "): " + description);
            if (error == null) {
                next.run();
                return;
            }
            String lower = description.toLowerCase(Locale.ROOT);
            boolean transient_ = lower.contains("timed out") || lower.contains("could not be executed");
            if (transient_ && n < STEP_ATTEMPTS) {
                attempt(what, n + 1, command, next);
            } else if (lower.contains("timed out") && !what.equals("Canal")) {
                next.run();  // sem resposta, mas pode ter sido aplicado: a leitura final confere
            } else {
                presetFailed(what, friendly(description));
            }
        })), STEP_GAP_MS);
    }

    /** Rele a faixa valida de canais (depende da banda e da largura atuais). */
    private void readRangeThen(OcuSyncLink link, int n, Runnable next) {
        ui.postDelayed(() -> link.getChannelNumberValidRange(got("faixa de canais", range -> {
            channels.clear();
            channels.addAll(expandRange(range));
            if (!channels.isEmpty()) {
                rangeBand = channels.get(0) >= 5000
                        ? OcuSyncFrequencyBand.FREQUENCY_BAND_5_DOT_8_GHZ
                        : OcuSyncFrequencyBand.FREQUENCY_BAND_2_DOT_4_GHZ;
                updateActiveBand();
            }
            next.run();
        }, error -> {
            if (n < STEP_ATTEMPTS) readRangeThen(link, n + 1, next);
            else next.run();  // segue com a ultima faixa conhecida
        })), STEP_GAP_MS);
    }

    /** Le do drone modo, largura e canal e mostra se bate com o que foi pedido. */
    private void verifyManual(OcuSyncLink link, String name, OcuSyncBandwidth bw, int bwMhz, int target) {
        prefs.edit().putString(PREF_MODE, ChannelSelectionMode.MANUAL.name())
                .putString(PREF_BW, bw.name()).putInt(PREF_CHANNEL, target).apply();
        final ChannelSelectionMode[] readMode = {null};
        final OcuSyncBandwidth[] readBw = {null};
        final Integer[] readChannel = {null};
        Runnable report = () -> {
            busyUntil = 0;
            boolean ok = readMode[0] == ChannelSelectionMode.MANUAL && readBw[0] == bw
                    && readChannel[0] != null && readChannel[0] == target;
            String what = "Manual · canal " + target + " MHz · " + bwMhz + " MHz";
            String text;
            if (ok) {
                text = "✓ Confirmado pelo drone: " + what
                        + (activeBand != null ? " · " + bandLabel(activeBand) : "");
            } else if (readMode[0] == null && readBw[0] == null && readChannel[0] == null) {
                text = "Enviado: " + what + ". O drone não respondeu à leitura de confirmação; "
                        + "observe o vídeo e o sinal.";
            } else {
                text = "Drone informou: modo " + (readMode[0] != null ? readMode[0].name().toLowerCase(Locale.ROOT) : "?")
                        + ", " + bandwidthLabel(readBw[0]) + ", canal "
                        + (readChannel[0] != null ? readChannel[0] + " MHz" : "?") + " (pedido: " + what + ").";
            }
            if (ok && fixedStatus.getVisibility() == View.VISIBLE) {
                text = "✓ 1080p · " + text.substring(2);
            }
            presetProgress(text);
            toast(ok ? "Modo manual confirmado pelo drone." : text);
            if (readMode[0] != null) {
                mode = readMode[0];
                bandwidth = readBw[0];
                if (readChannel[0] != null) channel = readChannel[0];
            }
        };
        ui.postDelayed(() -> link.getChannelSelectionMode(got("confirma modo", m -> {
            readMode[0] = m;
            link.getChannelBandwidth(got("confirma largura", b -> {
                readBw[0] = b;
                link.getChannelNumber(got("confirma canal", c -> {
                    readChannel[0] = c;
                    report.run();
                }, e -> report.run()));
            }, e -> report.run()));
        }, e -> report.run())), STEP_GAP_MS);
    }

    private void presetFailed(String what, String reason) {
        busyUntil = 0;
        String text = what + " recusado: " + reason;
        presetProgress(text);
        toast(text);
    }

    private void presetAuto() {
        if (!presetAllowed()) return;
        OcuSyncLink link = monitor.link();
        busyUntil = SystemClock.elapsedRealtime() + BAND_SETTLE_MS;
        link.setChannelSelectionMode(ChannelSelectionMode.AUTO, step("Canal automático", () -> {
            prefs.edit().remove(PREF_MODE).remove(PREF_BW).remove(PREF_CHANNEL).apply();
            presetNote.setText("Enviado: canal automático (padrão DJI).");
            toast("Canal automático enviado.");
        }));
    }

    private boolean presetAllowed() {
        if (monitor.link() == null) {
            toast("Drone não conectado.");
            return false;
        }
        if (telemetry.flying) {
            // Um canal ruim aplicado sem confirmacao em pleno voo pode derrubar o link.
            toast("Por segurança, troque o canal com o drone no chão.");
            return false;
        }
        if (monitor.uplink >= 0 && monitor.uplink < 30) {
            toast("Sinal do controle para o drone em " + monitor.uplink + "%: os comandos não chegariam. "
                    + "Aproxime o controle do drone e afaste-se de Wi-Fi/celulares.");
            return false;
        }
        if (isBusy(SystemClock.elapsedRealtime()) || requestedBand != null) {
            toast("Aguarde: o rádio ainda está aplicando a troca anterior.");
            return false;
        }
        return true;
    }

    /** Passo da predefinicao: OK ou "tempo esgotado" seguem para o proximo; outro erro para. */
    private CommonCallbacks.CompletionCallback<DJIError> step(String what, Runnable next) {
        return error -> ui.post(() -> {
            Log.i(TAG, "Predefinicao/" + what + ": " + (error == null ? "OK" : error.getDescription()));
            if (error == null || error.getDescription().toLowerCase(Locale.ROOT).contains("timed out")) {
                next.run();
            } else {
                busyUntil = 0;
                presetNote.setText(what + " recusado: " + friendly(error.getDescription()));
                toast(what + " recusado: " + friendly(error.getDescription()));
            }
        });
    }

    /**
     * Centro de canal (MHz) com menor interferencia media numa janela da
     * largura de banda, usando o grafico do radio. Respeita a faixa valida
     * informada pelo drone, se houver. -1 se ainda nao ha grafico.
     */
    static int cleanestChannel(FrequencyInterference[] spectrum, List<Integer> valid, int bwMhz) {
        // A faixa valida do drone manda: canal fora dela da "Param Illegal".
        int fallback = valid.isEmpty() ? -1 : valid.get(valid.size() / 2);
        if (spectrum == null || spectrum.length == 0) return fallback;
        float lo = Float.MAX_VALUE;
        float hi = -Float.MAX_VALUE;
        for (FrequencyInterference f : spectrum) {
            lo = Math.min(lo, f.frequencyFrom);
            hi = Math.max(hi, f.frequencyTo);
        }
        float half = bwMhz / 2f;
        int best = -1;
        double bestScore = Double.MAX_VALUE;
        for (int c = (int) Math.ceil(lo + half); c <= (int) Math.floor(hi - half); c++) {
            if (!valid.isEmpty() && !valid.contains(c)) continue;
            double weighted = 0;
            double total = 0;
            for (FrequencyInterference f : spectrum) {
                double overlap = Math.min(f.frequencyTo, c + half) - Math.max(f.frequencyFrom, c - half);
                if (overlap <= 0) continue;
                weighted += overlap * f.rssi;
                total += overlap;
            }
            if (total <= 0) continue;
            double score = weighted / total;
            if (score < bestScore) {
                bestScore = score;
                best = c;
            }
        }
        // Grafico de outra banda (nenhum canal valido dentro dele): usa o centro da faixa valida.
        return best >= 0 ? best : fallback;
    }

    /** Volta ao padrao do DJI Fly: banda dupla (se houver) e canal automatico. */
    private void resetToAuto() {
        prefs.edit().remove(PREF_BAND).remove(PREF_MODE).remove(PREF_BW).remove(PREF_CHANNEL).apply();
        pendingChannel = -1;
        if (Boolean.TRUE.equals(channelControlSupported) && mode == ChannelSelectionMode.MANUAL) {
            send("Modo de canal", link -> link.setChannelSelectionMode(ChannelSelectionMode.AUTO,
                    result("Modo de canal", () -> mode = ChannelSelectionMode.AUTO)));
        }
        if (supportedBands.contains(OcuSyncFrequencyBand.FREQUENCY_BAND_DUAL)) {
            changeBand(OcuSyncFrequencyBand.FREQUENCY_BAND_DUAL, true);
        } else {
            toast("Transmissão no automático.");
        }
    }

    // -- auxiliares ---------------------------------------------------------- //

    private boolean isBusy(long now) {
        return busyUntil != 0 && now < busyUntil;
    }

    private CommonCallbacks.CompletionCallback<DJIError> result(String what, Runnable onOk) {
        return error -> ui.post(() -> {
            Log.i(TAG, what + ": " + (error == null ? "OK" : error.getDescription()));
            if (error == null) {
                onOk.run();
                toast(what + " alterado.");
            } else {
                toast(what + " não alterado: " + friendly(error.getDescription()));
            }
        });
    }

    private <T> CommonCallbacks.CompletionCallbackWith<T> got(String what, Ok<T> ok, Ok<String> failed) {
        return new CommonCallbacks.CompletionCallbackWith<T>() {
            @Override
            public void onSuccess(T value) {
                Log.i(TAG, what + " = " + (value instanceof Object[] ? Arrays.toString((Object[]) value) : value));
                ui.post(() -> ok.on(value));
            }

            @Override
            public void onFailure(DJIError error) {
                Log.i(TAG, what + " falhou: " + error.getDescription());
                if (failed != null) ui.post(() -> failed.on(error.getDescription()));
            }
        };
    }

    /** Traduz os erros do SDK para o que o usuario pode fazer. */
    private static String friendly(String description) {
        String text = description == null ? "" : description.toLowerCase(Locale.ROOT);
        if (text.contains("timed out")) return "o drone não respondeu (tempo esgotado)";
        if (text.contains("could not be executed")) return "rádio ocupado, tente de novo em alguns segundos";
        if (text.contains("invalid key")) return "o rádio está reiniciando; aguarde ~15 s e tente de novo";
        return description;
    }

    private <E extends Enum<E>> E saved(String key, Class<E> type) {
        String name = prefs.getString(key, null);
        if (name == null) return null;
        try {
            return Enum.valueOf(type, name);
        } catch (IllegalArgumentException e) {
            return null;
        }
    }

    private void setBandRadiosEnabled(boolean enabled) {
        band24.setEnabled(enabled && supportedBands.contains(OcuSyncFrequencyBand.FREQUENCY_BAND_2_DOT_4_GHZ));
        band58.setEnabled(enabled && supportedBands.contains(OcuSyncFrequencyBand.FREQUENCY_BAND_5_DOT_8_GHZ));
        bandDual.setEnabled(enabled && supportedBands.contains(OcuSyncFrequencyBand.FREQUENCY_BAND_DUAL));
    }

    private void setChannelControlsEnabled(boolean enabled) {
        boolean on = enabled && Boolean.TRUE.equals(channelControlSupported);
        modeAuto.setEnabled(on);
        modeManual.setEnabled(on);
        channelMinus.setEnabled(on);
        channelPlus.setEnabled(on);
        bw10.setEnabled(on);
        bw20.setEnabled(on);
        bw40.setEnabled(on);
    }

    private String bandHint() {
        return "2,4 GHz: mais alcance e atravessa obstáculos. 5,8 GHz: menos interferência de Wi-Fi, "
                + "alcance menor. Dupla: o drone alterna sozinho (padrão do DJI Fly). "
                + "A troca leva ~15 s e o vídeo pisca.";
    }

    private String bandSummary() {
        if (chosenBand == OcuSyncFrequencyBand.FREQUENCY_BAND_DUAL) {
            return activeBand != null ? "dupla (agora em " + bandLabel(activeBand) + ")" : "dupla";
        }
        if (activeBand != null) return bandLabel(activeBand);
        return chosenBand != null ? bandLabel(chosenBand) : "frequência ?";
    }

    private String channelSummary() {
        if (Boolean.FALSE.equals(channelControlSupported)) return "canal automático";
        if (mode == ChannelSelectionMode.MANUAL) {
            return "canal " + (channel >= 0 ? channel + " MHz" : "?") + " · " + bandwidthLabel(bandwidth);
        }
        return mode == ChannelSelectionMode.AUTO ? "canal automático" : "canal ?";
    }

    private void toast(String message) {
        Toast.makeText(activity, message, Toast.LENGTH_LONG).show();
    }

    private static String bandLabel(OcuSyncFrequencyBand value) {
        switch (value) {
            case FREQUENCY_BAND_2_DOT_4_GHZ:
                return "2,4 GHz";
            case FREQUENCY_BAND_5_DOT_8_GHZ:
                return "5,8 GHz";
            case FREQUENCY_BAND_DUAL:
                return "dupla 2,4/5,8 GHz";
            default:
                return value.name();
        }
    }

    private static String bandwidthLabel(OcuSyncBandwidth value) {
        if (value == OcuSyncBandwidth.Bandwidth10MHz) return "10 MHz";
        if (value == OcuSyncBandwidth.Bandwidth20MHz) return "20 MHz";
        if (value == OcuSyncBandwidth.Bandwidth40MHZ) return "40 MHz";
        return "banda ?";
    }
}
