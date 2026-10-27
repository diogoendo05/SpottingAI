package br.edu.spottingai.drone;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.util.AttributeSet;
import android.view.View;

import java.util.Locale;

import dji.common.airlink.FrequencyInterference;

/**
 * Grafico de interferencia por frequencia, como o da aba Transmissao do DJI
 * Fly: uma barra por faixa, mais alta e mais vermelha quanto mais ruido
 * (RSSI maior). Barras baixas e verdes = canal limpo.
 */
public final class InterferenceView extends View {

    /** RSSI (dBm) tratado como "sem ruido" e como "saturado". */
    private static final float RSSI_FLOOR = -110f;
    private static final float RSSI_CEIL = -60f;

    private final Paint bar = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint text = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint grid = new Paint();
    private FrequencyInterference[] values = new FrequencyInterference[0];

    public InterferenceView(Context context, AttributeSet attrs) {
        super(context, attrs);
        float density = getResources().getDisplayMetrics().density;
        text.setColor(0xFF8B949E);
        text.setTextSize(11 * density);
        grid.setColor(0xFF30363D);
        grid.setStrokeWidth(density);
    }

    void setValues(FrequencyInterference[] newValues) {
        values = newValues != null ? newValues : new FrequencyInterference[0];
        invalidate();
    }

    @Override
    protected void onDraw(Canvas canvas) {
        int w = getWidth();
        int h = getHeight();
        float labelH = text.getTextSize() + 4;
        float chartH = h - labelH;
        canvas.drawLine(0, chartH, w, chartH, grid);

        if (values.length == 0) {
            canvas.drawText("Sem dados de interferência (conecte o drone)", 0, chartH / 2, text);
            return;
        }

        float minF = Float.MAX_VALUE;
        float maxF = -Float.MAX_VALUE;
        for (FrequencyInterference v : values) {
            minF = Math.min(minF, v.frequencyFrom);
            maxF = Math.max(maxF, v.frequencyTo);
        }
        float span = Math.max(1f, maxF - minF);
        float gap = Math.max(1f, w / 400f);

        for (FrequencyInterference v : values) {
            float level = (v.rssi - RSSI_FLOOR) / (RSSI_CEIL - RSSI_FLOOR);
            level = Math.max(0.03f, Math.min(1f, level));
            bar.setColor(colorFor(level));
            float left = (v.frequencyFrom - minF) / span * w;
            float right = (v.frequencyTo - minF) / span * w;
            canvas.drawRect(left, chartH - level * chartH, Math.max(left + 1, right - gap), chartH, bar);
        }

        canvas.drawText(format(minF), 0, h - 2, text);
        String end = format(maxF);
        canvas.drawText(end, w - text.measureText(end), h - 2, text);
    }

    private static int colorFor(float level) {
        if (level < 0.35f) return Color.rgb(46, 160, 67);    // limpo
        if (level < 0.6f) return Color.rgb(210, 153, 34);    // moderado
        return Color.rgb(218, 54, 51);                       // ruim
    }

    /** O SDK informa a frequencia em MHz; mostra em GHz. */
    private static String format(float mhz) {
        return mhz > 100 ? String.format(Locale.ROOT, "%.3f GHz", mhz / 1000f)
                : String.format(Locale.ROOT, "%.1f", mhz);
    }
}
