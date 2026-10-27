package br.edu.spottingai.drone;

import android.app.Activity;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;

import dji.common.camera.ResolutionAndFrameRate;
import dji.common.camera.SettingsDefinitions.CameraMode;
import dji.common.camera.SettingsDefinitions.ExposureCompensation;
import dji.common.camera.SettingsDefinitions.ExposureMode;
import dji.common.camera.SettingsDefinitions.FlatCameraMode;
import dji.common.camera.SettingsDefinitions.ISO;
import dji.common.camera.SettingsDefinitions.PhotoAspectRatio;
import dji.common.camera.SettingsDefinitions.ShutterSpeed;
import dji.common.camera.SettingsDefinitions.VideoFileFormat;
import dji.common.camera.SettingsDefinitions.WhiteBalancePreset;
import dji.common.camera.WhiteBalance;
import dji.common.gimbal.Rotation;
import dji.common.gimbal.RotationMode;
import dji.sdk.base.BaseProduct;
import dji.sdk.camera.Camera;
import dji.sdk.camera.Capabilities;
import dji.sdk.gimbal.Gimbal;

/**
 * Parte de camera do HUD, no estilo do DJI Fly:
 * <ul>
 *   <li>coluna direita: foto/video, obturador/gravar com cronometro, modo de
 *       captura, exposicao AUTO/PRO, zoom digital e gimbal;</li>
 *   <li>painel de exposicao: modo, ISO, obturador, EV, balanco de branco e
 *       trava de exposicao (AE lock);</li>
 *   <li>aba "Camera" do painel ⚙: resolucao/FPS do video, proporcao da foto,
 *       formato do video e formatacao do cartao SD;</li>
 *   <li>barra superior: espaco no cartao SD.</li>
 * </ul>
 * As listas de opcoes vem de {@link Capabilities}: so aparece o que a camera
 * deste drone informa aceitar.
 */
final class CameraHud {

    /** Fatores oferecidos pelo botao de zoom (cada toque passa para o proximo). */
    private static final float[] ZOOM_STEPS = {1f, 2f, 4f, 8f};

    /** Qual API de zoom a camera informa suportar. */
    private enum ZoomKind { NONE, DIGITAL, HYBRID, OPTICAL }

    private final Activity activity;

    // HUD
    private final TextView sd;
    private final TextView resolutionLabel;
    private final Button photoVideo;
    private final Button shutter;
    private final TextView recTime;
    private final Button captureMode;
    private final Button exposureButton;
    private final Button zoom;
    private final GimbalSlider gimbalSlider;
    private final View exposurePanel;
    private final Button expMode;
    private final TextView isoValue;
    private final TextView shutterValue;
    private final TextView evValue;
    private final Button wbButton;
    private final Button aeLockButton;
    // Aba Camera
    private final Button resolutionButton;
    private final Button ratioButton;
    private final Button formatButton;

    private Camera camera;
    private Gimbal gimbal;

    // Estado vindo dos callbacks (thread do SDK) e lido pelo tick().
    private volatile boolean recording;
    private volatile int recordingSeconds;
    private volatile boolean shootingContinuous;
    private volatile FlatCameraMode flatMode;
    private volatile CameraMode cameraMode;
    private volatile String storageText = "SD --";
    private volatile int liveIso = -1;
    private volatile ShutterSpeed liveShutter;
    private volatile ExposureCompensation liveEv;
    private volatile float gimbalPitch = Float.NaN;

    // Estado lido sob demanda.
    private boolean flat;
    private ExposureMode exposureMode;
    private ISO iso;
    private ShutterSpeed shutterSpeed;
    private ExposureCompensation ev;
    private WhiteBalancePreset whiteBalance;
    private boolean aeLock;
    private float zoomFactor = 1f;
    private ZoomKind zoomKind = ZoomKind.NONE;
    /** Distancias focais (hibrido/optico): minima = 1x. */
    private int minFocal;
    private int maxFocal;
    private int focalStep = 1;
    private ResolutionAndFrameRate resolution;
    private List<FlatCameraMode> flatModes = new ArrayList<>();
    private List<ExposureMode> exposureModes = new ArrayList<>();
    private List<ISO> isoRange = new ArrayList<>();
    private List<ShutterSpeed> shutterRange = new ArrayList<>();
    private List<ExposureCompensation> evRange = new ArrayList<>();
    private List<ResolutionAndFrameRate> resolutions = new ArrayList<>();

    CameraHud(Activity activity) {
        this.activity = activity;
        sd = activity.findViewById(R.id.hud_sd);
        resolutionLabel = activity.findViewById(R.id.hud_resolution);
        photoVideo = activity.findViewById(R.id.btn_photo_video);
        shutter = activity.findViewById(R.id.btn_shutter);
        recTime = activity.findViewById(R.id.hud_rec_time);
        captureMode = activity.findViewById(R.id.btn_capture_mode);
        exposureButton = activity.findViewById(R.id.btn_exposure);
        zoom = activity.findViewById(R.id.btn_zoom);
        gimbalSlider = activity.findViewById(R.id.gimbal_slider);
        exposurePanel = activity.findViewById(R.id.exposure_panel);
        expMode = activity.findViewById(R.id.btn_exp_mode);
        isoValue = activity.findViewById(R.id.iso_value);
        shutterValue = activity.findViewById(R.id.shutter_value);
        evValue = activity.findViewById(R.id.ev_value);
        wbButton = activity.findViewById(R.id.btn_wb);
        aeLockButton = activity.findViewById(R.id.btn_ae_lock);
        resolutionButton = activity.findViewById(R.id.btn_video_resolution);
        ratioButton = activity.findViewById(R.id.btn_photo_ratio);
        formatButton = activity.findViewById(R.id.btn_video_format);

        photoVideo.setOnClickListener(v -> togglePhotoVideo());
        shutter.setOnClickListener(v -> onShutter());
        captureMode.setOnClickListener(v -> chooseCaptureMode());
        exposureButton.setOnClickListener(v -> exposurePanel.setVisibility(
                exposurePanel.getVisibility() == View.VISIBLE ? View.GONE : View.VISIBLE));
        activity.findViewById(R.id.btn_exp_close).setOnClickListener(v -> exposurePanel.setVisibility(View.GONE));
        zoom.setOnClickListener(v -> nextZoom());
        expMode.setOnClickListener(v -> chooseExposureMode());
        activity.findViewById(R.id.btn_iso_minus).setOnClickListener(v -> stepIso(-1));
        activity.findViewById(R.id.btn_iso_plus).setOnClickListener(v -> stepIso(1));
        activity.findViewById(R.id.btn_shutter_minus).setOnClickListener(v -> stepShutter(-1));
        activity.findViewById(R.id.btn_shutter_plus).setOnClickListener(v -> stepShutter(1));
        activity.findViewById(R.id.btn_ev_minus).setOnClickListener(v -> stepEv(-1));
        activity.findViewById(R.id.btn_ev_plus).setOnClickListener(v -> stepEv(1));
        wbButton.setOnClickListener(v -> chooseWhiteBalance());
        aeLockButton.setOnClickListener(v -> withCamera(c -> c.setAELock(!aeLock,
                Sdk.done(activity, "Trava de exposição", () -> aeLock = !aeLock))));
        gimbalSlider.setListener(this::rotateGimbal);
        activity.findViewById(R.id.btn_gimbal_center).setOnClickListener(v -> rotateGimbal(0f));
        activity.findViewById(R.id.btn_gimbal_down).setOnClickListener(v -> rotateGimbal(-90f));
        resolutionButton.setOnClickListener(v -> chooseResolution());
        ratioButton.setOnClickListener(v -> choosePhotoRatio());
        formatButton.setOnClickListener(v -> chooseVideoFormat());
        activity.findViewById(R.id.btn_format_sd).setOnClickListener(v -> formatSd());

        setEnabled(false);
    }

    // -- conexao -------------------------------------------------------------- //

    void attach(BaseProduct product) {
        detach();
        camera = product.getCamera();
        gimbal = product.getGimbal();
        if (camera != null) {
            flat = camera.isFlatCameraModeSupported();
            camera.setSystemStateCallback(state -> {
                recording = state.isRecording();
                recordingSeconds = state.getCurrentVideoRecordingTimeInSeconds();
                shootingContinuous = state.isShootingIntervalPhoto() || state.isShootingBurstPhoto();
                flatMode = state.getFlatMode();
                cameraMode = state.getMode();
            });
            camera.setStorageStateCallBack(state -> storageText = describeStorage(state));
            camera.setExposureSettingsCallback(settings -> {
                liveIso = settings.getISO();
                liveShutter = settings.getShutterSpeed();
                liveEv = settings.getExposureCompensation();
            });
            readCapabilities();
            refresh();
            setupZoom(camera);
        }
        if (gimbal != null) {
            gimbal.setStateCallback(state -> {
                if (state.getAttitudeInDegrees() != null) gimbalPitch = state.getAttitudeInDegrees().getPitch();
            });
        }
        setEnabled(camera != null);
    }

    void detach() {
        try {
            if (camera != null) {
                camera.setSystemStateCallback(null);
                camera.setStorageStateCallBack(null);
                camera.setExposureSettingsCallback(null);
            }
            if (gimbal != null) gimbal.setStateCallback(null);
        } catch (Exception ignored) {
        }
        camera = null;
        gimbal = null;
        storageText = "SD --";
        setEnabled(false);
    }

    private void readCapabilities() {
        Capabilities caps = camera.getCapabilities();
        if (caps == null) return;
        flatModes = list(caps.FlatCameraModeRange());
        exposureModes = list(caps.exposureModeRange());
        isoRange = without(list(caps.ISORange()), ISO.AUTO, ISO.FIXED, ISO.UNKNOWN);
        shutterRange = without(list(caps.shutterSpeedRange()), ShutterSpeed.AUTO, ShutterSpeed.UNKNOWN);
        evRange = without(list(caps.exposureCompensationRange()), ExposureCompensation.FIXED,
                ExposureCompensation.UNKNOWN);
        resolutions = list(caps.videoResolutionAndFrameRateRange());
    }

    /** Le do drone os valores atuais mostrados nos botoes. */
    private void refresh() {
        Camera c = camera;
        if (c == null) return;
        c.getExposureMode(Sdk.got("getExposureMode", value -> exposureMode = value));
        c.getISO(Sdk.got("getISO", value -> iso = value));
        c.getShutterSpeed(Sdk.got("getShutterSpeed", value -> shutterSpeed = value));
        c.getExposureCompensation(Sdk.got("getExposureCompensation", value -> ev = value));
        c.getWhiteBalance(Sdk.got("getWhiteBalance", value -> whiteBalance = value.getWhiteBalancePreset()));
        c.getAELock(Sdk.got("getAELock", value -> aeLock = value));
        c.getVideoResolutionAndFrameRate(Sdk.got("getVideoResolutionAndFrameRate", value -> resolution = value));
        c.getPhotoAspectRatio(Sdk.got("getPhotoAspectRatio", value -> ratioButton.setText(ratioLabel(value))));
        c.getVideoFileFormat(Sdk.got("getVideoFileFormat", value -> formatButton.setText(value.name())));
        readZoom();
    }

    /**
     * O SDK tem tres APIs de zoom (digital, hibrido e optico); usa a que a
     * camera deste drone informa suportar, nessa ordem de preferencia.
     */
    private void setupZoom(Camera c) {
        boolean digital = c.isDigitalZoomSupported();
        boolean hybrid = c.isHybridZoomSupported();
        boolean optical = c.isOpticalZoomSupported();
        android.util.Log.i("Hud", "Zoom suportado: digital=" + digital + " hibrido=" + hybrid + " optico=" + optical);
        zoomKind = hybrid ? ZoomKind.HYBRID : optical ? ZoomKind.OPTICAL : digital ? ZoomKind.DIGITAL : ZoomKind.NONE;
        zoom.setVisibility(zoomKind == ZoomKind.NONE ? View.GONE : View.VISIBLE);
        zoom.setOnLongClickListener(v -> {
            applyZoom(1f);
            return true;
        });
        if (zoomKind == ZoomKind.HYBRID) {
            c.getHybridZoomSpec(Sdk.got("getHybridZoomSpec", spec -> {
                minFocal = spec.getMinHybridFocalLength();
                maxFocal = spec.getMaxHybridFocalLength();
                focalStep = Math.max(1, spec.getFocalLengthStep());
                readZoom();
            }));
        } else if (zoomKind == ZoomKind.OPTICAL) {
            c.getOpticalZoomSpec(Sdk.got("getOpticalZoomSpec", spec -> {
                minFocal = spec.getMinFocalLength();
                maxFocal = spec.getMaxFocalLength();
                focalStep = Math.max(1, spec.getFocalLengthStep());
                readZoom();
            }));
        }
    }

    /** Le o zoom atual da camera (mostra o valor real, nao o pedido). */
    private void readZoom() {
        Camera c = camera;
        if (c == null) return;
        switch (zoomKind) {
            case DIGITAL:
                c.getDigitalZoomFactor(Sdk.got("getDigitalZoomFactor", value -> zoomFactor = value));
                break;
            case HYBRID:
                c.getHybridZoomFocalLength(Sdk.got("getHybridZoomFocalLength",
                        value -> zoomFactor = minFocal > 0 ? value / (float) minFocal : 1f));
                break;
            case OPTICAL:
                c.getOpticalZoomFocalLength(Sdk.got("getOpticalZoomFocalLength",
                        value -> zoomFactor = minFocal > 0 ? value / (float) minFocal : 1f));
                break;
            default:
                break;
        }
    }

    // -- tela ------------------------------------------------------------------ //

    void tick() {
        sd.setText(storageText);
        boolean video = isVideoMode();
        photoVideo.setText(video ? "🎥 Vídeo" : "📷 Foto");
        shutter.setBackgroundResource(recording || shootingContinuous ? R.drawable.shutter_recording
                : video ? R.drawable.shutter_video : R.drawable.shutter_photo);
        recTime.setText(recording ? String.format(Locale.ROOT, "● %d:%02d", recordingSeconds / 60, recordingSeconds % 60)
                : "");
        recTime.setVisibility(recording ? View.VISIBLE : View.GONE);
        captureMode.setText(flatMode != null ? modeLabel(flatMode) : video ? "Normal" : "Simples");
        resolutionLabel.setText(resolution != null ? resolutionText(resolution) : "");
        resolutionButton.setText(resolution != null ? resolutionText(resolution) : "--");

        boolean manual = exposureMode == ExposureMode.MANUAL;
        exposureButton.setText(manual ? "PRO" : "AUTO");
        expMode.setText(manual ? "Manual (PRO)" : "Automático");
        isoValue.setText(liveIso > 0 ? "ISO " + liveIso : iso != null ? "ISO " + isoLabel(iso) : "ISO --");
        ShutterSpeed shownShutter = liveShutter != null ? liveShutter : shutterSpeed;
        shutterValue.setText(shownShutter != null ? shutterLabel(shownShutter) : "--");
        ExposureCompensation shownEv = liveEv != null ? liveEv : ev;
        evValue.setText(shownEv != null ? "EV " + evLabel(shownEv) : "EV --");
        wbButton.setText(whiteBalance != null ? wbLabel(whiteBalance) : "--");
        aeLockButton.setText(aeLock ? "AE 🔒 travada" : "AE 🔓 livre");
        zoom.setText(Math.abs(zoomFactor - Math.round(zoomFactor)) < 0.05f
                ? String.format(Locale.ROOT, "%.0fx", zoomFactor)
                : String.format(Locale.ROOT, "%.1fx", zoomFactor));
        if (!Float.isNaN(gimbalPitch)) gimbalSlider.setActualPitch(gimbalPitch);
    }

    private void setEnabled(boolean enabled) {
        for (View v : new View[]{photoVideo, shutter, captureMode, exposureButton, zoom, resolutionButton,
                ratioButton, formatButton}) {
            v.setEnabled(enabled);
            v.setAlpha(enabled ? 1f : 0.4f);
        }
    }

    // -- acoes ----------------------------------------------------------------- //

    private boolean isVideoMode() {
        FlatCameraMode f = flatMode;
        if (f != null && f != FlatCameraMode.UNKNOWN) return f.name().startsWith("VIDEO") || f == FlatCameraMode.SLOW_MOTION;
        return cameraMode == CameraMode.RECORD_VIDEO;
    }

    private void togglePhotoVideo() {
        if (recording) {
            Sdk.toast(activity, "Pare a gravação antes de trocar para foto.");
            return;
        }
        boolean toVideo = !isVideoMode();
        withCamera(c -> {
            if (flat) {
                c.setFlatMode(toVideo ? FlatCameraMode.VIDEO_NORMAL : FlatCameraMode.PHOTO_SINGLE,
                        Sdk.done(activity, toVideo ? "Modo vídeo" : "Modo foto", this::refresh));
            } else {
                c.setMode(toVideo ? CameraMode.RECORD_VIDEO : CameraMode.SHOOT_PHOTO,
                        Sdk.done(activity, toVideo ? "Modo vídeo" : "Modo foto", this::refresh));
            }
        });
    }

    private void onShutter() {
        withCamera(c -> {
            if (isVideoMode()) {
                if (recording) c.stopRecordVideo(Sdk.done(activity, "Parar gravação", null));
                else c.startRecordVideo(Sdk.done(activity, "Gravar", null));
            } else if (shootingContinuous) {
                c.stopShootPhoto(Sdk.done(activity, "Parar fotos", null));
            } else {
                c.startShootPhoto(Sdk.done(activity, "Foto", () -> Sdk.toast(activity, "📷 Foto tirada")));
            }
        });
    }

    /** Modos da camera (simples, AEB, intervalo, camera lenta, HDR...) que o drone informa. */
    private void chooseCaptureMode() {
        boolean video = isVideoMode();
        List<FlatCameraMode> options = new ArrayList<>();
        for (FlatCameraMode m : flatModes) {
            boolean isVideo = m.name().startsWith("VIDEO") || m == FlatCameraMode.SLOW_MOTION;
            // Modos de voo automatico (QuickShots/MasterShots) nao sao liberados ao SDK v4 no Air 2S.
            boolean autoFlight = m.name().matches("VIDEO_(ASTEROID|ROCKET|DRONIE|CIRCLE|HELIX|BOOMERANG|DOLLY_ZOOM)");
            if (isVideo == video && !autoFlight && m != FlatCameraMode.UNKNOWN
                    && m != FlatCameraMode.INTERNAL_AI_SPOT_CHECKING) {
                options.add(m);
            }
        }
        if (!flat || options.isEmpty()) {
            Sdk.toast(activity, "A câmera não informou outros modos de " + (video ? "vídeo" : "foto") + ".");
            return;
        }
        String[] labels = new String[options.size()];
        for (int i = 0; i < labels.length; i++) labels[i] = modeLabel(options.get(i));
        Sdk.choose(activity, video ? "Modo de vídeo" : "Modo de foto", labels, options.indexOf(flatMode),
                i -> withCamera(c -> c.setFlatMode(options.get(i), Sdk.done(activity, "Modo", null))));
    }

    private void chooseExposureMode() {
        List<ExposureMode> options = new ArrayList<>();
        for (ExposureMode m : exposureModes) {
            if (m == ExposureMode.PROGRAM || m == ExposureMode.MANUAL) options.add(m);
        }
        if (options.isEmpty()) options = Arrays.asList(ExposureMode.PROGRAM, ExposureMode.MANUAL);
        List<ExposureMode> finalOptions = options;
        String[] labels = new String[options.size()];
        for (int i = 0; i < labels.length; i++) {
            labels[i] = options.get(i) == ExposureMode.MANUAL ? "Manual (PRO): ISO e obturador" : "Automático (+ EV)";
        }
        Sdk.choose(activity, "Exposição", labels, options.indexOf(exposureMode),
                i -> withCamera(c -> c.setExposureMode(finalOptions.get(i),
                        Sdk.done(activity, "Exposição", () -> {
                            exposureMode = finalOptions.get(i);
                            refresh();
                        }))));
    }

    private void stepIso(int delta) {
        if (exposureMode != ExposureMode.MANUAL) {
            Sdk.toast(activity, "ISO só é ajustável no modo Manual (PRO).");
            return;
        }
        ISO next = step(isoRange, iso, delta);
        if (next != null) withCamera(c -> c.setISO(next, Sdk.done(activity, "ISO", () -> iso = next)));
    }

    private void stepShutter(int delta) {
        if (exposureMode != ExposureMode.MANUAL) {
            Sdk.toast(activity, "O obturador só é ajustável no modo Manual (PRO).");
            return;
        }
        ShutterSpeed next = step(shutterRange, shutterSpeed, delta);
        if (next != null) withCamera(c -> c.setShutterSpeed(next,
                Sdk.done(activity, "Obturador", () -> shutterSpeed = next)));
    }

    private void stepEv(int delta) {
        if (exposureMode == ExposureMode.MANUAL) {
            Sdk.toast(activity, "EV só vale no modo Automático.");
            return;
        }
        ExposureCompensation next = step(evRange, ev, delta);
        if (next != null) withCamera(c -> c.setExposureCompensation(next,
                Sdk.done(activity, "EV", () -> ev = next)));
    }

    private void chooseWhiteBalance() {
        WhiteBalancePreset[] presets = {WhiteBalancePreset.AUTO, WhiteBalancePreset.SUNNY,
                WhiteBalancePreset.CLOUDY, WhiteBalancePreset.WATER_SURFACE,
                WhiteBalancePreset.INDOOR_INCANDESCENT, WhiteBalancePreset.INDOOR_FLUORESCENT};
        String[] labels = new String[presets.length];
        for (int i = 0; i < presets.length; i++) labels[i] = wbLabel(presets[i]);
        Sdk.choose(activity, "Balanço de branco", labels, Arrays.asList(presets).indexOf(whiteBalance),
                i -> withCamera(c -> c.setWhiteBalance(new WhiteBalance(presets[i]),
                        Sdk.done(activity, "Balanço de branco", () -> whiteBalance = presets[i]))));
    }

    /** Toque: proximo fator (1x → 2x → 4x → 8x → 1x). Toque longo: volta a 1x. */
    private void nextZoom() {
        int index = 0;
        for (int i = 0; i < ZOOM_STEPS.length; i++) if (zoomFactor >= ZOOM_STEPS[i] - 0.05f) index = i;
        float next = ZOOM_STEPS[(index + 1) % ZOOM_STEPS.length];
        // Optico/hibrido: nao passa do maximo da lente; ao chegar no fim, volta para 1x.
        if ((zoomKind == ZoomKind.HYBRID || zoomKind == ZoomKind.OPTICAL) && minFocal > 0
                && next * minFocal > maxFocal) {
            next = zoomFactor < maxFocal / (float) minFocal - 0.05f ? maxFocal / (float) minFocal : 1f;
        }
        applyZoom(next);
    }

    private void applyZoom(float factor) {
        Camera c = camera;
        if (c == null) {
            Sdk.toast(activity, "Câmera não conectada.");
            return;
        }
        // Erro (fator fora da faixa do modo atual): mostra o motivo e rele o zoom real.
        dji.common.util.CommonCallbacks.CompletionCallback<dji.common.error.DJIError> result = error -> zoom.post(() -> {
            android.util.Log.i("Hud", "Zoom " + factor + "x (" + zoomKind + "): "
                    + (error == null ? "OK" : error.getDescription()));
            if (error == null) {
                zoomFactor = factor;
            } else {
                Sdk.toast(activity, "Zoom " + Math.round(factor) + "x: " + Sdk.friendly(error.getDescription())
                        + ". O alcance do zoom depende da resolução (em 5.4K e em foto pode não haver zoom).");
            }
            readZoom();
        });
        switch (zoomKind) {
            case DIGITAL:
                c.setDigitalZoomFactor(factor, result);
                break;
            case HYBRID:
            case OPTICAL:
                int focal = Math.round(minFocal * factor / focalStep) * focalStep;
                focal = Math.max(minFocal, Math.min(maxFocal, focal));
                if (zoomKind == ZoomKind.HYBRID) c.setHybridZoomFocalLength(focal, result);
                else c.setOpticalZoomFocalLength(focal, result);
                break;
            default:
                Sdk.toast(activity, "Esta câmera não informa suporte a zoom pelo SDK.");
        }
    }

    private void rotateGimbal(float pitch) {
        Gimbal g = gimbal;
        if (g == null) {
            Sdk.toast(activity, "Gimbal não conectado.");
            return;
        }
        Rotation rotation = new Rotation.Builder()
                .mode(RotationMode.ABSOLUTE_ANGLE)
                .pitch(pitch)
                .time(1.0)
                .build();
        g.rotate(rotation, Sdk.done(activity, "Gimbal", null));
    }

    // -- preparo para video ao vivo em 1080p ---------------------------------- //

    /**
     * O HD Live View (video ao vivo em 1080p) so funciona com a camera em modo
     * video gravando em 1080p ou 2.7K. Coloca a camera nesse estado (modo
     * video; se a gravacao estiver em 4K/5.4K, muda para 1080p 30fps) e depois
     * chama {@code then}, mesmo se alguma etapa falhar.
     */
    void prepareForHdLiveView(Runnable then) {
        Camera c = camera;
        if (c == null) {
            then.run();
            return;
        }
        Runnable resolutionStep = () -> {
            ResolutionAndFrameRate target = resolution != null && isAbove27k(resolution) ? find1080p30() : null;
            if (target == null) {
                then.run();
                return;
            }
            c.setVideoResolutionAndFrameRate(target, result("Resolução 1080p 30fps", () -> {
                resolution = target;
                Sdk.toast(activity, "Gravação ajustada para 1080p 30fps (necessário para o vídeo ao vivo em 1080p).");
            }, then));
        };
        if (isVideoMode()) {
            resolutionStep.run();
        } else if (flat) {
            c.setFlatMode(FlatCameraMode.VIDEO_NORMAL, result("Modo vídeo", this::refresh, resolutionStep));
        } else {
            c.setMode(CameraMode.RECORD_VIDEO, result("Modo vídeo", this::refresh, resolutionStep));
        }
    }

    /** Callback que mostra erro (se houver) e segue para {@code next} de qualquer jeito. */
    private dji.common.util.CommonCallbacks.CompletionCallback<dji.common.error.DJIError> result(
            String what, Runnable onOk, Runnable next) {
        return error -> zoom.post(() -> {
            android.util.Log.i("Hud", what + ": " + (error == null ? "OK" : error.getDescription()));
            if (error == null) onOk.run();
            else Sdk.toast(activity, what + ": " + Sdk.friendly(error.getDescription()));
            next.run();
        });
    }

    private static boolean isAbove27k(ResolutionAndFrameRate value) {
        String res = value.getResolution().name().replace("RESOLUTION_", "").toLowerCase(Locale.ROOT);
        String[] parts = res.split("x");
        try {
            return parts.length == 2 && Integer.parseInt(parts[0]) > 2720;
        } catch (NumberFormatException e) {
            return false;  // RESOLUTION_MAX etc.: nao mexe
        }
    }

    /** 1080p a 30fps (ou 29.97) da lista que a camera informa; senao, qualquer 1080p. */
    private ResolutionAndFrameRate find1080p30() {
        ResolutionAndFrameRate any1080 = null;
        for (ResolutionAndFrameRate r : resolutions) {
            if (r.getResolution().name().equals("RESOLUTION_1920x1080")) {
                String fps = r.getFrameRate().name();
                if (fps.equals("FRAME_RATE_30_FPS") || fps.equals("FRAME_RATE_29_DOT_970_FPS")) return r;
                if (any1080 == null) any1080 = r;
            }
        }
        return any1080;
    }

    // -- aba Camera ------------------------------------------------------------ //

    private void chooseResolution() {
        if (resolutions.isEmpty()) {
            Sdk.toast(activity, "A câmera não informou as resoluções disponíveis.");
            return;
        }
        String[] labels = new String[resolutions.size()];
        int selected = -1;
        for (int i = 0; i < labels.length; i++) {
            labels[i] = resolutionText(resolutions.get(i));
            if (resolution != null && labels[i].equals(resolutionText(resolution))) selected = i;
        }
        Sdk.choose(activity, "Resolução e FPS do vídeo", labels, selected,
                i -> withCamera(c -> c.setVideoResolutionAndFrameRate(resolutions.get(i),
                        Sdk.done(activity, "Resolução", () -> resolution = resolutions.get(i)))));
    }

    private void choosePhotoRatio() {
        PhotoAspectRatio[] ratios = {PhotoAspectRatio.RATIO_4_3, PhotoAspectRatio.RATIO_16_9,
                PhotoAspectRatio.RATIO_3_2};
        String[] labels = new String[ratios.length];
        for (int i = 0; i < ratios.length; i++) labels[i] = ratioLabel(ratios[i]);
        Sdk.choose(activity, "Proporção da foto", labels, -1,
                i -> withCamera(c -> c.setPhotoAspectRatio(ratios[i],
                        Sdk.done(activity, "Proporção", () -> ratioButton.setText(labels[i])))));
    }

    private void chooseVideoFormat() {
        VideoFileFormat[] formats = {VideoFileFormat.MP4, VideoFileFormat.MOV};
        String[] labels = {"MP4", "MOV"};
        Sdk.choose(activity, "Formato do vídeo", labels, -1,
                i -> withCamera(c -> c.setVideoFileFormat(formats[i],
                        Sdk.done(activity, "Formato", () -> formatButton.setText(labels[i])))));
    }

    private void formatSd() {
        SlideToConfirm.show(activity, "Formatar cartão SD",
                "APAGA todas as fotos e vídeos do cartão do drone. Não dá para desfazer.",
                () -> withCamera(c -> c.formatSDCard(Sdk.done(activity, "Formatar SD",
                        () -> Sdk.toast(activity, "Cartão SD formatado.")))));
    }

    // -- auxiliares ------------------------------------------------------------ //

    private void withCamera(Sdk.Value<Camera> action) {
        Camera c = camera;
        if (c == null) {
            Sdk.toast(activity, "Câmera não conectada.");
            return;
        }
        action.on(c);
    }

    private static <T> List<T> list(T[] values) {
        return values == null ? new ArrayList<>() : new ArrayList<>(Arrays.asList(values));
    }

    @SafeVarargs
    private static <T> List<T> without(List<T> values, T... removed) {
        values.removeAll(Arrays.asList(removed));
        return values;
    }

    /** Proximo valor da lista; se o atual nao estiver nela, comeca do meio. */
    private <T> T step(List<T> range, T current, int delta) {
        if (range.isEmpty()) {
            Sdk.toast(activity, "A câmera não informou a faixa de valores.");
            return null;
        }
        int index = range.indexOf(current);
        if (index < 0) return range.get(range.size() / 2);
        int next = Math.max(0, Math.min(range.size() - 1, index + delta));
        return next == index ? null : range.get(next);
    }

    private static String describeStorage(dji.common.camera.StorageState state) {
        if (!state.isInserted()) return "SEM SD";
        if (state.isFull()) return "SD CHEIO";
        if (state.hasError() || state.isInvalidFormat()) return "SD ERRO";
        int mb = state.getRemainingSpaceInMB();
        return mb >= 1024 ? String.format(Locale.ROOT, "SD %.1f GB", mb / 1024f) : "SD " + mb + " MB";
    }

    static String resolutionText(ResolutionAndFrameRate value) {
        String res = value.getResolution().name().replace("RESOLUTION_", "").toLowerCase(Locale.ROOT);
        switch (res) {
            case "3840x2160":
                res = "4K";
                break;
            case "5472x3078":
                res = "5.4K";
                break;
            case "2688x1512":
            case "2704x1520":
            case "2720x1530":
                res = "2.7K";
                break;
            case "1920x1080":
                res = "1080p";
                break;
            case "1280x720":
                res = "720p";
                break;
            default:
                break;
        }
        String fps = value.getFrameRate().name().replace("FRAME_RATE_", "").replace("_FPS", "")
                .replace("_DOT_", ".");
        return res + " " + fps + "fps";
    }

    private static String modeLabel(FlatCameraMode mode) {
        switch (mode) {
            case PHOTO_SINGLE:
                return "Simples";
            case PHOTO_AEB:
                return "AEB";
            case PHOTO_BURST:
                return "Rajada";
            case PHOTO_INTERVAL:
                return "Intervalo";
            case PHOTO_HDR:
            case PHOTO_EHDR:
                return "HDR";
            case PHOTO_SMART:
                return "Smart";
            case PHOTO_HIGH_RESOLUTION:
                return "Alta resolução";
            case PHOTO_SUPER_RESOLUTION:
                return "Super resolução";
            case PHOTO_TIME_LAPSE:
                return "Time-lapse";
            case PHOTO_HYPER_LAPSE:
                return "Hyperlapse";
            case PHOTO_PANORAMA:
                return "Panorama";
            case PHOTO_COUNTDOWN:
                return "Temporizador";
            case PHOTO_HYPER_LIGHT:
                return "Hyperlight";
            case VIDEO_NORMAL:
                return "Normal";
            case VIDEO_HDR:
                return "HDR";
            case SLOW_MOTION:
                return "Câmera lenta";
            default:
                return mode.name();
        }
    }

    private static String isoLabel(ISO value) {
        return value.name().replace("ISO_", "");
    }

    static String shutterLabel(ShutterSpeed value) {
        String name = value.name().replace("SHUTTER_SPEED_", "").replace("_DOT_", ".");
        if (name.startsWith("1_")) return "1/" + name.substring(2);
        return name + "\"";
    }

    private static String evLabel(ExposureCompensation value) {
        String name = value.name();
        if (name.equals("N_0_0")) return "0.0";
        return (name.startsWith("N") ? "-" : "+") + name.substring(2).replace('_', '.');
    }

    private static String wbLabel(WhiteBalancePreset value) {
        switch (value) {
            case AUTO:
                return "Auto";
            case SUNNY:
                return "Sol";
            case CLOUDY:
                return "Nublado";
            case WATER_SURFACE:
                return "Água";
            case INDOOR_INCANDESCENT:
                return "Incandescente";
            case INDOOR_FLUORESCENT:
                return "Fluorescente";
            default:
                return value.name();
        }
    }

    private static String ratioLabel(PhotoAspectRatio value) {
        return value.name().replace("RATIO_", "").replace('_', ':');
    }
}
