package br.edu.spottingai.drone;

import android.app.Activity;
import android.app.AlertDialog;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.widget.Toast;

import java.util.Locale;

import dji.common.error.DJIError;
import dji.common.util.CommonCallbacks;

/**
 * Atalhos para chamadas do DJI SDK feitas pelo HUD: resultado sempre na
 * thread de UI, erro mostrado em portugues e registrado no log.
 */
final class Sdk {

    private static final String TAG = "Hud";
    private static final Handler UI = new Handler(Looper.getMainLooper());

    interface Value<T> {
        void on(T value);
    }

    private Sdk() {
    }

    /** Callback de comando: {@code onOk} na UI se deu certo; toast com o erro se nao. */
    static CommonCallbacks.CompletionCallback<DJIError> done(Activity activity, String what, Runnable onOk) {
        return error -> UI.post(() -> {
            Log.i(TAG, what + ": " + (error == null ? "OK" : error.getDescription()));
            if (error == null) {
                if (onOk != null) onOk.run();
            } else {
                toast(activity, what + ": " + friendly(error.getDescription()));
            }
        });
    }

    /** Callback de leitura: valor na UI; falha so vai para o log (o HUD mostra "--"). */
    static <T> CommonCallbacks.CompletionCallbackWith<T> got(String what, Value<T> onValue) {
        return new CommonCallbacks.CompletionCallbackWith<T>() {
            @Override
            public void onSuccess(T value) {
                UI.post(() -> onValue.on(value));
            }

            @Override
            public void onFailure(DJIError error) {
                Log.i(TAG, what + " falhou: " + error.getDescription());
            }
        };
    }

    static void toast(Activity activity, String message) {
        Toast.makeText(activity, message, Toast.LENGTH_LONG).show();
    }

    /** Lista de opcoes com a atual marcada; {@code onPick} recebe o indice escolhido. */
    static void choose(Activity activity, String title, String[] labels, int selected, Value<Integer> onPick) {
        new AlertDialog.Builder(activity)
                .setTitle(title)
                .setSingleChoiceItems(labels, selected, (dialog, which) -> {
                    dialog.dismiss();
                    if (which != selected) onPick.on(which);
                })
                .setNegativeButton("Cancelar", null)
                .show();
    }

    /** Traduz os erros mais comuns do SDK para o que o piloto pode fazer. */
    static String friendly(String description) {
        String text = description == null ? "" : description.toLowerCase(Locale.ROOT);
        if (text.contains("timed out")) return "o drone não respondeu (tempo esgotado)";
        if (text.contains("could not be executed")) return "o drone recusou agora; tente de novo em instantes";
        if (text.contains("invalid key") || text.contains("not supported")) return "não suportado por este drone";
        if (text.contains("motor")) return description + " (verifique os motores/hélices)";
        return description;
    }
}
