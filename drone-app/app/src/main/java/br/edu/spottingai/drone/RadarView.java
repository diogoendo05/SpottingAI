package br.edu.spottingai.drone;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;
import android.util.AttributeSet;
import android.view.View;

import java.util.Locale;

/**
 * Radar no lugar do mapa do DJI Fly: a casa (H) no centro, norte para cima,
 * o drone como uma seta apontando para onde o nariz esta virado. A escala se
 * ajusta a distancia; o anel externo mostra o raio em metros.
 */
public final class RadarView extends View {

    private final Paint ring = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint home = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint aircraft = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint text = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path arrow = new Path();
    private final float density;

    private boolean hasPosition;
    private double north;
    private double east;
    private double heading;

    public RadarView(Context context, AttributeSet attrs) {
        super(context, attrs);
        density = getResources().getDisplayMetrics().density;
        fill.setColor(0x99000000);
        ring.setStyle(Paint.Style.STROKE);
        ring.setStrokeWidth(density);
        ring.setColor(0x88FFFFFF);
        home.setColor(0xFFFFC107);
        home.setTextAlign(Paint.Align.CENTER);
        home.setTextSize(12 * density);
        home.setFakeBoldText(true);
        aircraft.setColor(0xFF00F0FF);
        text.setColor(0xCCFFFFFF);
        text.setTextSize(10 * density);
    }

    /** Atualiza a posicao (metros em relacao a casa) e o rumo (graus). */
    void update(boolean hasPosition, double north, double east, double heading) {
        this.hasPosition = hasPosition;
        this.north = north;
        this.east = east;
        this.heading = heading;
        invalidate();
    }

    @Override
    protected void onDraw(Canvas canvas) {
        float cx = getWidth() / 2f;
        float cy = getHeight() / 2f;
        float radius = Math.min(cx, cy) - 2 * density;
        canvas.drawCircle(cx, cy, radius, fill);
        canvas.drawCircle(cx, cy, radius, ring);
        canvas.drawCircle(cx, cy, radius / 2, ring);
        canvas.drawText("N", cx - 3 * density, cy - radius + 11 * density, text);

        double distance = Math.hypot(north, east);
        double range = niceRange(Math.max(20, distance * 1.25));
        canvas.drawText(String.format(Locale.ROOT, "%.0f m", range), cx + 4 * density, cy + radius - 4 * density, text);

        // Casa no centro.
        canvas.drawText("H", cx, cy + 4 * density, home);

        // Drone: com GPS fica na posicao relativa; sem GPS fica no centro, so com o rumo.
        float scale = (float) (radius / range);
        float ax = hasPosition ? cx + (float) east * scale : cx;
        float ay = hasPosition ? cy - (float) north * scale : cy;
        float size = 9 * density;
        arrow.reset();
        arrow.moveTo(0, -size);
        arrow.lineTo(size * 0.7f, size);
        arrow.lineTo(0, size * 0.45f);
        arrow.lineTo(-size * 0.7f, size);
        arrow.close();
        canvas.save();
        canvas.translate(ax, ay);
        canvas.rotate((float) heading);
        canvas.drawPath(arrow, aircraft);
        canvas.restore();
    }

    /** Arredonda o raio para 20, 50, 100, 200, 500 m... */
    private static double niceRange(double meters) {
        double[] steps = {20, 50, 100, 200, 500, 1000, 2000, 5000, 10000};
        for (double step : steps) if (meters <= step) return step;
        return steps[steps.length - 1];
    }
}
