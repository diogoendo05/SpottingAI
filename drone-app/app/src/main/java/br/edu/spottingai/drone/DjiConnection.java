package br.edu.spottingai.drone;

import android.content.Context;
import android.util.Log;

import java.util.concurrent.atomic.AtomicBoolean;

import dji.common.error.DJIError;
import dji.common.error.DJISDKError;
import dji.sdk.base.BaseComponent;
import dji.sdk.base.BaseProduct;
import dji.sdk.sdkmanager.DJISDKInitEvent;
import dji.sdk.sdkmanager.DJISDKManager;

/**
 * Registro do DJI SDK v4 e conexao com o produto (drone via RC-N1).
 *
 * <p>Segue o fluxo do sample oficial (MainContent.java): {@code registerApp}
 * numa thread de fundo e, com {@code REGISTRATION_SUCCESS},
 * {@code startConnectionToProduct()}. Os callbacks do SDK chegam fora da
 * thread de UI.</p>
 */
final class DjiConnection {

    private static final String TAG = "DjiConnection";

    interface Listener {
        void onStatus(String message);
        void onRegistered();
        void onProductConnected(BaseProduct product);
        void onProductDisconnected();
    }

    private final Context context;
    private final Listener listener;
    private final AtomicBoolean registering = new AtomicBoolean(false);

    DjiConnection(Context context, Listener listener) {
        this.context = context.getApplicationContext();
        this.listener = listener;
    }

    void register() {
        if (DJISDKManager.getInstance().hasSDKRegistered()) {
            listener.onRegistered();
            DJISDKManager.getInstance().startConnectionToProduct();
            return;
        }
        if (!registering.compareAndSet(false, true)) return;

        listener.onStatus("Registrando o DJI SDK (precisa de internet na 1a vez)...");
        new Thread(() -> DJISDKManager.getInstance().registerApp(context, new DJISDKManager.SDKManagerCallback() {
            @Override
            public void onRegister(DJIError djiError) {
                registering.set(false);
                if (djiError == DJISDKError.REGISTRATION_SUCCESS) {
                    Log.i(TAG, "Registro OK");
                    listener.onRegistered();
                    DJISDKManager.getInstance().startConnectionToProduct();
                } else {
                    String why = djiError != null ? djiError.getDescription() : "erro desconhecido";
                    Log.e(TAG, "Registro falhou: " + why);
                    listener.onStatus("Falha no registro do SDK: " + why
                            + " (confira o App Key no AndroidManifest e a internet)");
                }
            }

            @Override
            public void onProductDisconnect() {
                Log.i(TAG, "Produto desconectado");
                listener.onProductDisconnected();
            }

            @Override
            public void onProductConnect(BaseProduct baseProduct) {
                Log.i(TAG, "Produto conectado: " + baseProduct);
                listener.onProductConnected(baseProduct);
            }

            @Override
            public void onProductChanged(BaseProduct baseProduct) {
                if (baseProduct != null) listener.onProductConnected(baseProduct);
            }

            @Override
            public void onComponentChange(BaseProduct.ComponentKey componentKey,
                                          BaseComponent oldComponent,
                                          BaseComponent newComponent) {
                // A camera do drone so fica disponivel depois que o link sobe:
                // reavalia o produto para (re)ligar o feed de video.
                if (componentKey == BaseProduct.ComponentKey.CAMERA && newComponent != null) {
                    BaseProduct product = DJISDKManager.getInstance().getProduct();
                    if (product != null) listener.onProductConnected(product);
                }
            }

            @Override
            public void onInitProcess(DJISDKInitEvent djisdkInitEvent, int totalProcess) {
                Log.d(TAG, "Init: " + djisdkInitEvent + " " + totalProcess);
            }

            @Override
            public void onDatabaseDownloadProgress(long current, long total) {
                if (total > 0) {
                    listener.onStatus("Baixando base de dados do SDK: " + (100 * current / total) + "%");
                }
            }
        }), "dji-register").start();
    }
}
