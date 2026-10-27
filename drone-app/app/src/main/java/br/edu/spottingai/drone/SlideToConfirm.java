package br.edu.spottingai.drone;

import android.app.Activity;
import android.app.AlertDialog;
import android.widget.LinearLayout;
import android.widget.SeekBar;
import android.widget.TextView;

/**
 * Confirmacao por deslize para comandos de voo (decolar, pousar, RTH, formatar
 * o cartao), como o DJI Fly faz: um toque acidental nao basta.
 */
final class SlideToConfirm {

    private SlideToConfirm() {
    }

    static void show(Activity activity, String title, String message, Runnable onConfirm) {
        float density = activity.getResources().getDisplayMetrics().density;
        int pad = (int) (20 * density);

        LinearLayout box = new LinearLayout(activity);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(pad, pad / 2, pad, pad / 2);

        TextView text = new TextView(activity);
        text.setText(message);
        text.setTextSize(15);
        box.addView(text);

        TextView hint = new TextView(activity);
        hint.setText("Deslize até o fim para confirmar  →");
        hint.setTextSize(13);
        hint.setPadding(0, pad, 0, pad / 4);
        box.addView(hint);

        SeekBar slider = new SeekBar(activity);
        slider.setMax(100);
        box.addView(slider);

        AlertDialog dialog = new AlertDialog.Builder(activity)
                .setTitle(title)
                .setView(box)
                .setNegativeButton("Cancelar", null)
                .create();

        slider.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
            }

            @Override
            public void onStartTrackingTouch(SeekBar seekBar) {
            }

            @Override
            public void onStopTrackingTouch(SeekBar seekBar) {
                if (seekBar.getProgress() >= 95) {
                    dialog.dismiss();
                    onConfirm.run();
                } else {
                    seekBar.setProgress(0);  // soltou antes do fim: volta ao inicio
                }
            }
        });
        dialog.show();
    }
}
