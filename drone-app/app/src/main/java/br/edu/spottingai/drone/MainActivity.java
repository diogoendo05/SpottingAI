package br.edu.spottingai.drone;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.SurfaceTexture;
import android.hardware.usb.UsbManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;
import android.view.TextureView;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.TextView;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

import dji.common.error.DJIError;
import dji.common.util.CommonCallbacks;
import dji.sdk.base.BaseProduct;
import dji.sdk.camera.VideoFeeder;
import dji.sdk.codec.DJICodecManager;
import dji.sdk.sdkmanager.DJISDKManager;

/**
 * Tela unica do app: registra o SDK, mostra o preview do drone e envia o
 * H.264 para o PC do SpottingAI.
 *
 * <p>Fluxo do video:</p>
 * <pre>
 * feed primario --(onReceive)--> DJICodecManager --> preview na tela
 * feed transcodificado --(onReceive)--> VideoStreamSender --TCP--> PC (PyAV)
 * </pre>
 * <p>O feed primario da DJI vem em formato proprietario, sem SPS/PPS (DJI,
 * issue #1076 do Mobile-SDK-Android); por isso o padrao e o feed
 * transcodificado ({@code provideTranscodedVideoFeed()}), que e H.264 Annex-B
 * padrao. O primario fica como opcao experimental.</p>
 */
public class MainActivity extends Activity implements DjiConnection.Listener, VideoStreamSender.Listener {

    private static final String TAG = "MainActivity";
    private static final int REQ_PERMISSIONS = 1;
    private static final String PREFS = "spottingai_drone";
    private static final float DEFAULT_BITRATE_MBPS = 8f;

    private final Handler ui = new Handler(Looper.getMainLooper());

    private TextureView preview;
    private TextView previewHint;
    private TextView statusSdk;
    private TextView statusProduct;
    private TextView statusSocket;
    private TextView statusStats;
    private EditText inputIp;
    private EditText inputPort;
    private EditText inputBitrate;
    private RadioButton feedTranscoded;
    private RadioButton feedPrimary;
    private RadioButton defSd;
    private RadioButton defHd;
    private Button btnToggle;

    private TextView statusChip;
    private View settingsPanel;
    /** Estado do socket mostrado no indicador do canto (atualizado pela thread de envio). */
    private volatile VideoStreamSender.State senderState = VideoStreamSender.State.STOPPED;

    private DjiConnection dji;
    private VideoStreamSender sender;
    private final LinkMonitor linkMonitor = new LinkMonitor();
    private final TelemetryMonitor telemetry = new TelemetryMonitor(linkMonitor);
    private TransmissionPanel transmission;
    private FlightHud flightHud;
    private CameraHud cameraHud;
    private SafetySettings safety;

    private volatile DJICodecManager codecManager;
    /** Envia o feed primario em vez do transcodificado (modo experimental). */
    private volatile boolean sendPrimary;
    private volatile long lastVideoAt;
    private volatile long lastTranscodedAt;
    private long lastPrimaryReattachAt;
    /** HD Live View ja reaplicado nesta conexao com o drone. */
    private boolean hdApplied;
    private long lastTranscodedRestartAt;
    private VideoFeeder.VideoFeed transcodedFeed;

    private long lastStatsBytes;
    private long lastStatsAt;

    /** Feed primario: alimenta o preview e, no modo experimental, o envio. */
    private final VideoFeeder.VideoDataListener primaryListener = new VideoFeeder.VideoDataListener() {
        @Override
        public void onReceive(byte[] videoBuffer, int size) {
            lastVideoAt = SystemClock.elapsedRealtime();
            DJICodecManager manager = codecManager;
            if (manager != null) {
                manager.sendDataToDecoder(videoBuffer, size);
            }
            if (sendPrimary) {
                sender.offer(videoBuffer, size);
            }
        }
    };

    /** Feed transcodificado (H.264 padrao): vai direto para a fila de envio. */
    private final VideoFeeder.VideoDataListener transcodedListener = new VideoFeeder.VideoDataListener() {
        @Override
        public void onReceive(byte[] videoBuffer, int size) {
            lastTranscodedAt = SystemClock.elapsedRealtime();
            sender.offer(videoBuffer, size);
        }
    };

    // -- ciclo de vida ------------------------------------------------------ //

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        preview = findViewById(R.id.video_preview);
        previewHint = findViewById(R.id.preview_hint);
        statusSdk = findViewById(R.id.status_sdk);
        statusProduct = findViewById(R.id.status_product);
        statusSocket = findViewById(R.id.status_socket);
        statusStats = findViewById(R.id.status_stats);
        inputIp = findViewById(R.id.input_ip);
        inputPort = findViewById(R.id.input_port);
        inputBitrate = findViewById(R.id.input_bitrate);
        feedTranscoded = findViewById(R.id.feed_transcoded);
        feedPrimary = findViewById(R.id.feed_primary);
        defSd = findViewById(R.id.def_sd);
        defHd = findViewById(R.id.def_hd);
        btnToggle = findViewById(R.id.btn_toggle);
        statusChip = findViewById(R.id.status_chip);
        settingsPanel = findViewById(R.id.settings_panel);

        loadPreferences();
        fitPreview16x9();
        preview.setSurfaceTextureListener(surfaceListener);

        findViewById(R.id.btn_settings).setOnClickListener(v -> setSettingsVisible(
                settingsPanel.getVisibility() != View.VISIBLE));
        findViewById(R.id.btn_close_settings).setOnClickListener(v -> setSettingsVisible(false));
        setupTabs();
        // Primeira vez (sem IP salvo): abre o painel na aba PC para configurar.
        if (inputIp.getText().toString().trim().isEmpty()) {
            showTab(R.id.section_pc);
            setSettingsVisible(true);
        } else {
            setSettingsVisible(false);
        }

        sender = new VideoStreamSender(this);
        dji = new DjiConnection(this, this);

        btnToggle.setOnClickListener(v -> {
            if (sender.isRunning()) stopStreaming();
            else startStreaming();
        });
        ((RadioGroup) findViewById(R.id.definition_group)).setOnCheckedChangeListener((group, id) -> {
            boolean hd = id == R.id.def_hd;
            getSharedPreferences(PREFS, MODE_PRIVATE).edit().putBoolean("hd", hd).apply();
            applyHdLiveView(hd);
        });
        // Configuracao fixa em 1080p: prepara a camera (modo video, gravacao ate 2.7K) e liga o HD Live View.
        transmission = new TransmissionPanel(this, getSharedPreferences(PREFS, MODE_PRIVATE), linkMonitor, telemetry,
                () -> cameraHud.prepareForHdLiveView(() -> {
                    if (defHd.isChecked()) applyHdLiveView(true);
                    else defHd.setChecked(true);  // o listener salva a escolha e aplica no drone
                }));
        flightHud = new FlightHud(this, telemetry, linkMonitor);
        cameraHud = new CameraHud(this);
        safety = new SafetySettings(this, telemetry);

        ui.post(statsTicker);
        ui.post(telemetryTicker);
        requestPermissionsThenRegister();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        // Igual ao sample oficial: repassa ao SDK o evento de RC conectado por USB.
        if (UsbManager.ACTION_USB_ACCESSORY_ATTACHED.equals(intent.getAction())) {
            Intent attached = new Intent();
            attached.setAction(DJISDKManager.USB_ACCESSORY_ATTACHED);
            sendBroadcast(attached);
        }
        super.onNewIntent(intent);
    }

    @Override
    protected void onDestroy() {
        ui.removeCallbacksAndMessages(null);
        transmission.onProductDisconnected();
        cameraHud.detach();
        telemetry.detach();
        linkMonitor.detach();
        sender.stop();
        stopTranscodedFeed();
        try {
            VideoFeeder.getInstance().getPrimaryVideoFeed().removeVideoDataListener(primaryListener);
        } catch (Exception ignored) {
        }
        releaseCodec();
        super.onDestroy();
    }

    // -- permissoes e registro --------------------------------------------- //

    private void requestPermissionsThenRegister() {
        List<String> wanted = new ArrayList<>();
        wanted.add(Manifest.permission.ACCESS_FINE_LOCATION);
        wanted.add(Manifest.permission.ACCESS_COARSE_LOCATION);
        wanted.add(Manifest.permission.READ_PHONE_STATE);
        wanted.add(Manifest.permission.RECORD_AUDIO);
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
            wanted.add(Manifest.permission.READ_EXTERNAL_STORAGE);
            wanted.add(Manifest.permission.WRITE_EXTERNAL_STORAGE);
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            wanted.add(Manifest.permission.BLUETOOTH_CONNECT);
            wanted.add(Manifest.permission.BLUETOOTH_SCAN);
        }

        List<String> missing = new ArrayList<>();
        for (String permission : wanted) {
            if (checkSelfPermission(permission) != PackageManager.PERMISSION_GRANTED) missing.add(permission);
        }
        if (missing.isEmpty()) {
            dji.register();
        } else {
            requestPermissions(missing.toArray(new String[0]), REQ_PERMISSIONS);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != REQ_PERMISSIONS) return;
        for (int i = 0; i < permissions.length; i++) {
            if (grantResults[i] != PackageManager.PERMISSION_GRANTED
                    && permissions[i].equals(Manifest.permission.ACCESS_FINE_LOCATION)) {
                Toast.makeText(this, "Sem localização o DJI SDK pode recusar o registro.", Toast.LENGTH_LONG).show();
            }
        }
        // Registra mesmo com alguma negada: o SDK informa o erro se faltar algo essencial.
        dji.register();
    }

    // -- DjiConnection.Listener --------------------------------------------- //

    @Override
    public void onStatus(String message) {
        runOnUiThread(() -> statusSdk.setText("SDK: " + message));
    }

    @Override
    public void onRegistered() {
        runOnUiThread(() -> statusSdk.setText("SDK: registrado " + DJISDKManager.getInstance().getSDKVersion()
                + " — conectando ao produto…"));
    }

    @Override
    public void onProductConnected(BaseProduct product) {
        if (product == null) return;
        runOnUiThread(() -> {
            statusProduct.setText("Drone: " + product.getModel() + diagnostics());
            telemetry.attach(product);
            attachPrimaryFeed();
            if (sender.isRunning() && !sendPrimary) startTranscodedFeed(currentBitrate());
            // HD Live View e frequencia sao reaplicados uma vez por conexao no videoWatchdog.
        });
    }

    @Override
    public void onProductDisconnected() {
        runOnUiThread(() -> {
            hdApplied = false;
            telemetry.detach();
            linkMonitor.reset();
            transmission.onProductDisconnected();
            cameraHud.detach();
            safety.stop();
            statusProduct.setText(R.string.status_product_none);
            previewHint.setVisibility(View.VISIBLE);
        });
    }

    /** Indica se a DJI recomenda o feed transcodificado para este produto. */
    private String diagnostics() {
        try {
            VideoFeeder feeder = VideoFeeder.getInstance();
            boolean keyFrame = feeder.isFetchKeyFrameNeeded();
            boolean distortion = feeder.isLensDistortionCalibrationNeeded();
            if (keyFrame || distortion) {
                return "\n(feed primário exige " + (keyFrame ? "keyframe do SDK" : "")
                        + (keyFrame && distortion ? " e " : "")
                        + (distortion ? "anti-distorção" : "") + ": use o transcodificado)";
            }
        } catch (Exception ignored) {
        }
        return "";
    }

    // -- VideoStreamSender.Listener ----------------------------------------- //

    @Override
    public void onStateChanged(VideoStreamSender.State state, String detail) {
        senderState = state;
        runOnUiThread(() -> {
            switch (state) {
                case CONNECTING:
                    statusSocket.setText("PC: conectando a " + detail + "…");
                    break;
                case CONNECTED:
                    statusSocket.setText("PC: conectado a " + detail + " — enviando");
                    break;
                case RETRY_WAIT:
                    statusSocket.setText("PC: " + detail);
                    break;
                default:
                    statusSocket.setText(R.string.status_socket_stopped);
            }
        });
    }

    // -- video ---------------------------------------------------------------- //

    private final TextureView.SurfaceTextureListener surfaceListener = new TextureView.SurfaceTextureListener() {
        @Override
        public void onSurfaceTextureAvailable(SurfaceTexture surface, int width, int height) {
            if (codecManager == null) {
                codecManager = new DJICodecManager(MainActivity.this, surface, width, height);
            }
        }

        @Override
        public void onSurfaceTextureSizeChanged(SurfaceTexture surface, int width, int height) {
        }

        @Override
        public boolean onSurfaceTextureDestroyed(SurfaceTexture surface) {
            releaseCodec();
            return false;
        }

        @Override
        public void onSurfaceTextureUpdated(SurfaceTexture surface) {
            if (previewHint.getVisibility() == View.VISIBLE) previewHint.setVisibility(View.GONE);
        }
    };

    private void attachPrimaryFeed() {
        try {
            VideoFeeder.VideoFeed feed = VideoFeeder.getInstance().getPrimaryVideoFeed();
            if (feed != null && !feed.getListeners().contains(primaryListener)) {
                feed.addVideoDataListener(primaryListener);
            }
        } catch (Exception e) {
            statusProduct.setText("Drone: erro ao abrir o feed de vídeo: " + e.getMessage());
        }
    }

    private void startTranscodedFeed(float rateMbps) {
        try {
            VideoFeeder feeder = VideoFeeder.getInstance();
            feeder.setTranscodingDataRate(rateMbps);
            if (transcodedFeed == null) transcodedFeed = feeder.provideTranscodedVideoFeed();
            if (transcodedFeed != null && !transcodedFeed.getListeners().contains(transcodedListener)) {
                transcodedFeed.addVideoDataListener(transcodedListener);
            }
        } catch (Exception e) {
            statusSocket.setText("PC: feed transcodificado indisponível: " + e.getMessage());
        }
    }

    private void stopTranscodedFeed() {
        VideoFeeder.VideoFeed feed = transcodedFeed;
        transcodedFeed = null;
        if (feed == null) return;
        try {
            // Sem listener o SDK para de transcodificar (economiza CPU/bateria).
            feed.removeVideoDataListener(transcodedListener);
            feed.destroy();
        } catch (Exception ignored) {
        }
    }

    private void releaseCodec() {
        DJICodecManager manager = codecManager;
        codecManager = null;
        if (manager != null) {
            manager.cleanSurface();
            manager.destroyCodec();
        }
    }

    private void applyHdLiveView(boolean enabled) {
        applyHdLiveView(enabled, 1);
    }

    /**
     * Logo apos conectar o drone costuma nao responder ("tempo esgotado"):
     * tenta de novo algumas vezes antes de mostrar o erro.
     */
    private void applyHdLiveView(boolean enabled, int attempt) {
        BaseProduct product = DJISDKManager.getInstance().getProduct();
        if (product == null || product.getCamera() == null) return;  // reaplicado ao conectar
        product.getCamera().setHDLiveViewEnabled(enabled, new CommonCallbacks.CompletionCallback() {
            @Override
            public void onResult(DJIError djiError) {
                Log.i(TAG, "setHDLiveViewEnabled(" + enabled + ") tentativa " + attempt + ": "
                        + (djiError == null ? "OK" : djiError.getDescription()));
                boolean retry = djiError != null && attempt < 4
                        && Sdk.friendly(djiError.getDescription()).startsWith("o drone não respondeu");
                runOnUiThread(() -> {
                    if (retry) {
                        ui.postDelayed(() -> applyHdLiveView(defHd.isChecked(), attempt + 1), 3000);
                        return;
                    }
                    Toast.makeText(MainActivity.this,
                            djiError == null
                                    ? (enabled ? "Vídeo ao vivo em HD (1080p)" : "Vídeo ao vivo em 720p")
                                    : "Definição do vídeo: " + Sdk.friendly(djiError.getDescription()),
                            Toast.LENGTH_SHORT).show();
                });
            }
        });
    }

    // -- envio -------------------------------------------------------------- //

    private void startStreaming() {
        String ip = inputIp.getText().toString().trim();
        int port;
        try {
            port = Integer.parseInt(inputPort.getText().toString().trim());
        } catch (NumberFormatException e) {
            port = -1;
        }
        if (ip.isEmpty() || port < 1 || port > 65535) {
            Toast.makeText(this, "Informe o IP do PC e uma porta válida (ex.: 9000).", Toast.LENGTH_LONG).show();
            return;
        }
        float rate = currentBitrate();
        boolean transcoded = feedTranscoded.isChecked();
        savePreferences(ip, port, rate);

        sendPrimary = !transcoded;
        if (transcoded) {
            startTranscodedFeed(rate);
        } else {
            stopTranscodedFeed();
        }
        // Transcodificado: espera SPS/IDR antes de enviar. Primario: envia tudo.
        sender.start(ip, port, transcoded);
        lastStatsBytes = sender.bytesSent();
        lastStatsAt = SystemClock.elapsedRealtime();
        setInputsEnabled(false);
        btnToggle.setText(R.string.btn_stop);
        setSettingsVisible(false);  // libera a tela para o voo
    }

    private void stopStreaming() {
        sendPrimary = false;
        sender.stop();
        stopTranscodedFeed();
        setInputsEnabled(true);
        btnToggle.setText(R.string.btn_start);
    }

    private void setInputsEnabled(boolean enabled) {
        inputIp.setEnabled(enabled);
        inputPort.setEnabled(enabled);
        inputBitrate.setEnabled(enabled);
        feedTranscoded.setEnabled(enabled);
        feedPrimary.setEnabled(enabled);
    }

    private float currentBitrate() {
        try {
            float rate = Float.parseFloat(inputBitrate.getText().toString().trim().replace(',', '.'));
            return Math.max(0.3f, Math.min(20f, rate));
        } catch (NumberFormatException e) {
            return DEFAULT_BITRATE_MBPS;
        }
    }

    /** Atualiza taxa enviada, fila, descartes e sinal de video a cada segundo. */
    private final Runnable statsTicker = new Runnable() {
        @Override
        public void run() {
            long now = SystemClock.elapsedRealtime();
            long bytes = sender.bytesSent();
            double seconds = Math.max(0.001, (now - lastStatsAt) / 1000.0);
            double mbps = (bytes - lastStatsBytes) * 8 / seconds / 1_000_000.0;
            lastStatsBytes = bytes;
            lastStatsAt = now;

            String video = lastVideoAt == 0 ? "sem vídeo do drone"
                    : (now - lastVideoAt > 2000 ? "vídeo do drone parado" : "vídeo do drone OK");
            statusStats.setText(sender.isRunning()
                    ? String.format(Locale.ROOT, "%s · enviando %.1f Mbps · fila %d · descartados %d",
                            video, mbps, sender.queueSize(), sender.chunksDropped())
                    : video);
            statusChip.setText(chipText(mbps));
            transmission.tick();
            videoWatchdog(now);
            ui.postDelayed(this, 1000);
        }
    };

    /**
     * Religa os feeds de video quando o drone (re)conecta depois do app.
     *
     * <p>Se o app abre com o drone desligado, ele se inscreve em feeds que o SDK
     * substitui quando a aeronave sobe o link; sem isto o preview e o envio
     * ficariam mudos ate reabrir o app.</p>
     */
    private void videoWatchdog(long now) {
        BaseProduct product = DJISDKManager.getInstance().getProduct();
        // getModel() pode vir nulo por um tempo mesmo com o Air 2S ja conectado.
        if (product == null || !product.isConnected()) return;

        // Sinal/avisos do radio: inscreve e reinscreve se as atualizacoes pararem.
        linkMonitor.ensure(product);

        // O HD Live View fica gravado no drone; reaplica o estado do switch uma vez
        // por conexao (desligado volta o live view ao modo padrao de 720p).
        if (!hdApplied && product.getCamera() != null) {
            hdApplied = true;
            Log.i(TAG, "Produto: model=" + product.getModel() + " camera=" + product.getCamera().getDisplayName()
                    + " -> HD Live View " + (defHd.isChecked() ? "ON" : "OFF"));
            applyHdLiveView(defHd.isChecked());
            transmission.onProductConnected();
            cameraHud.attach(product);
            // O controlador de voo e inscrito pela telemetria; le os limites logo depois.
            ui.postDelayed(safety::refresh, 1500);
        }

        if (product.getModel() != null) {
            String label = "Drone: " + product.getModel();
            if (!statusProduct.getText().toString().startsWith(label)) {
                statusProduct.setText(label + diagnostics());
                telemetry.attach(product);
            }
        }

        // Feed primario parado ha 3 s (ex.: HD Live View reiniciou o stream):
        // reinscreve no feed atual do SDK.
        if (now - lastVideoAt > 3000 && now - lastPrimaryReattachAt > 3000) {
            lastPrimaryReattachAt = now;
            try {
                VideoFeeder.VideoFeed feed = VideoFeeder.getInstance().getPrimaryVideoFeed();
                if (feed != null) {
                    feed.removeVideoDataListener(primaryListener);
                    boolean added = feed.addVideoDataListener(primaryListener);
                    Log.i(TAG, "Watchdog: feed primario mudo; reinscrito (ok=" + added + ")");
                }
            } catch (Exception e) {
                Log.w(TAG, "Watchdog: falha ao reinscrever feed primario", e);
            }
        }

        // Video do drone chegando, mas o transcodificado mudo: recria o transcodificador.
        boolean primaryOk = now - lastVideoAt < 2000;
        if (sender.isRunning() && !sendPrimary && primaryOk
                && now - lastTranscodedAt > 4000 && now - lastTranscodedRestartAt > 6000) {
            lastTranscodedRestartAt = now;
            Log.i(TAG, "Watchdog: feed transcodificado mudo; recriando");
            stopTranscodedFeed();
            startTranscodedFeed(currentBitrate());
        }

        // Conectado ao PC mas preso esperando keyframe: o transcodificador da DJI
        // quase nao gera IDR, entao reinicia-lo forca SPS/PPS + IDR na hora.
        if (sender.isRunning() && !sendPrimary && sender.keyframeWaitMs() > 2000
                && now - lastTranscodedRestartAt > 5000) {
            lastTranscodedRestartAt = now;
            Log.i(TAG, "Watchdog: sem keyframe ha " + sender.keyframeWaitMs() + " ms; reiniciando transcodificador");
            stopTranscodedFeed();
            startTranscodedFeed(currentBitrate());
        }
    }

    /** Texto curto do indicador do canto: o video esta chegando no PC? */
    private String chipText(double mbps) {
        switch (senderState) {
            case CONNECTED:
                return String.format(Locale.ROOT, "PC ✓ %.1f Mbps", mbps);
            case CONNECTING:
                return "PC: conectando…";
            case RETRY_WAIT:
                return "PC ✗ reconectando";
            default:
                return getString(R.string.chip_stopped);
        }
    }

    /** Atualiza o HUD (voo, camera, alertas) 4x por segundo. */
    private final Runnable telemetryTicker = new Runnable() {
        @Override
        public void run() {
            flightHud.tick();
            cameraHud.tick();
            ui.postDelayed(this, 250);
        }
    };

    // -- abas do painel ⚙ ---------------------------------------------------- //

    private static final int[] TAB_BUTTONS = {R.id.tab_safety, R.id.tab_camera, R.id.tab_transmission, R.id.tab_pc};
    private static final int[] TAB_SECTIONS = {R.id.section_safety, R.id.section_camera,
            R.id.section_transmission, R.id.section_pc};

    private void setupTabs() {
        for (int i = 0; i < TAB_BUTTONS.length; i++) {
            int section = TAB_SECTIONS[i];
            findViewById(TAB_BUTTONS[i]).setOnClickListener(v -> showTab(section));
        }
        showTab(R.id.section_safety);
    }

    private void showTab(int sectionId) {
        for (int i = 0; i < TAB_SECTIONS.length; i++) {
            boolean selected = TAB_SECTIONS[i] == sectionId;
            findViewById(TAB_SECTIONS[i]).setVisibility(selected ? View.VISIBLE : View.GONE);
            findViewById(TAB_BUTTONS[i]).setAlpha(selected ? 1f : 0.55f);
        }
    }

    // -- preferencias e layout ---------------------------------------------- //

    private void loadPreferences() {
        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        inputIp.setText(prefs.getString("ip", ""));
        inputPort.setText(String.valueOf(prefs.getInt("port", 9000)));
        inputBitrate.setText(String.valueOf(prefs.getFloat("bitrate", DEFAULT_BITRATE_MBPS)));
        boolean primary = prefs.getBoolean("primary", false);
        feedPrimary.setChecked(primary);
        feedTranscoded.setChecked(!primary);
        boolean hd = prefs.getBoolean("hd", false);
        defHd.setChecked(hd);
        defSd.setChecked(!hd);
    }

    private void savePreferences(String ip, int port, float rate) {
        getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                .putString("ip", ip)
                .putInt("port", port)
                .putFloat("bitrate", rate)
                .putBoolean("primary", feedPrimary.isChecked())
                .putBoolean("hd", defHd.isChecked())
                .apply();
    }

    /** Ajusta o preview ao maior retangulo 16:9 que cabe na tela (faixas pretas nas sobras). */
    private void fitPreview16x9() {
        View root = findViewById(R.id.root);
        root.addOnLayoutChangeListener((v, left, top, right, bottom, oldLeft, oldTop, oldRight, oldBottom) -> {
            int w = right - left;
            int h = bottom - top;
            if (w == 0 || h == 0) return;
            int targetW = Math.min(w, h * 16 / 9);
            int targetH = targetW * 9 / 16;
            ViewGroup.LayoutParams params = preview.getLayoutParams();
            if (params.width != targetW || params.height != targetH) {
                params.width = targetW;
                params.height = targetH;
                preview.post(() -> preview.setLayoutParams(params));
            }
        });
    }

    private void setSettingsVisible(boolean visible) {
        settingsPanel.setVisibility(visible ? View.VISIBLE : View.GONE);
        if (!visible) enterImmersive();
    }

    /** Tela cheia: esconde barra de status e de navegacao (voltam com um deslize). */
    @SuppressWarnings("deprecation")
    private void enterImmersive() {
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                        | View.SYSTEM_UI_FLAG_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN);
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus && settingsPanel.getVisibility() != View.VISIBLE) enterImmersive();
    }
}
