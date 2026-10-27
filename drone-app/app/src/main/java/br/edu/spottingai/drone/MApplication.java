package br.edu.spottingai.drone;

import android.app.Application;
import android.content.Context;

import androidx.multidex.MultiDex;

/**
 * Application exigida pelo DJI SDK v4: o Helper descompacta/carrega as classes
 * protegidas do SDK antes de qualquer uso.
 *
 * No MSDK 4.18 o Helper mudou de pacote: {@code com.cySdkyc.clx.Helper}
 * (ate a 4.17 era {@code com.secneo.sdk.Helper}). Igual ao
 * DJISampleApplication do sample oficial.
 */
public class MApplication extends Application {

    @Override
    protected void attachBaseContext(Context base) {
        super.attachBaseContext(base);
        MultiDex.install(this);
        com.cySdkyc.clx.Helper.install(this);
    }
}
