package br.edu.spottingai.drone;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.util.AttributeSet;
import android.view.MotionEvent;
import android.view.View;

import java.util.Locale;

/**
 * Controle vertical da inclinacao do gimbal, como a barra lateral do DJI Fly:
 * topo = 0° (horizonte), base = -90° (camera para baixo). Arrastar move o
 * marcador; ao soltar, o angulo escolhido e enviado. A marca fina mostra o
 * angulo real informado pelo gimbal.
 */
public final class GimbalSlider extends View {

    interface Listener {
        void onPitchChosen(float pitch);
    }

    static final float MIN_PITCH = -90f;
    static final float MAX_PITCH = 0f;

    private final Paint track = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint thumb = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint actual = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint text = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final float density;

    private Listener listener;
    private float actualPitch = 0f;
    private float dragPitch = Float.NaN;

    public GimbalSlider(Context context, AttributeSet attrs) {
        super(context, attrs);
        density = getResources().getDisplayMetrics().density;
        track.setColor(0x99FFFFFF);
        track.setStrokeWidth(3 * density);
        track.setStrokeCap(Paint.Cap.ROUND);
        thumb.setColor(0xFF00F0FF);
        actual.setColor(0xFFFFC107);
        actual.setStrokeWidth(2 * density);
        text.setColor(0xFFFFFFFF);
        text.setTextSize(11 * density);
        text.setTextAlign(Paint.Align.CENTER);
        text.setShadowLayer(3, 0, 0, 0xFF000000);
    }

    void setListener(Listener listener) {
        this.listener = listener;
    }

    /** Angulo real do gimbal (callback do SDK). */
    void setActualPitch(float pitch) {
        actualPitch = clamp(pitch);
        invalidate();
    }

    @Override
    protected void onDraw(Canvas canvas) {
        float cx = getWidth() / 2f;
        float top = 16 * density;
        float bottom = getHeight() - 8 * density;
        canvas.drawLine(cx, top, cx, bottom, track);

        float ay = yFor(actualPitch, top, bottom);
        canvas.drawLine(cx - 8 * density, ay, cx + 8 * density, ay, actual);

        float shown = Float.isNaN(dragPitch) ? actualPitch : dragPitch;
        float ty = yFor(shown, top, bottom);
        canvas.drawCircle(cx, ty, 7 * density, thumb);
        canvas.drawText(String.format(Locale.ROOT, "%.0f°", shown), cx, top - 4 * density, text);
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        float top = 16 * density;
        float bottom = getHeight() - 8 * density;
        float fraction = (event.getY() - top) / Math.max(1f, bottom - top);
        float pitch = clamp(MAX_PITCH + (MIN_PITCH - MAX_PITCH) * fraction);
        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                getParent().requestDisallowInterceptTouchEvent(true);
                // fall through
            case MotionEvent.ACTION_MOVE:
                dragPitch = pitch;
                invalidate();
                return true;
            case MotionEvent.ACTION_UP:
                dragPitch = Float.NaN;
                invalidate();
                if (listener != null) listener.onPitchChosen(Math.round(pitch));
                return true;
            case MotionEvent.ACTION_CANCEL:
                dragPitch = Float.NaN;
                invalidate();
                return true;
            default:
                return super.onTouchEvent(event);
        }
    }

    private static float yFor(float pitch, float top, float bottom) {
        return top + (pitch - MAX_PITCH) / (MIN_PITCH - MAX_PITCH) * (bottom - top);
    }

    private static float clamp(float pitch) {
        return Math.max(MIN_PITCH, Math.min(MAX_PITCH, pitch));
    }
}
