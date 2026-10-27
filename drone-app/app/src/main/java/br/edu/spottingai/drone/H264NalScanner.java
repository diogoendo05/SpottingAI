package br.edu.spottingai.drone;

import java.io.ByteArrayOutputStream;

/**
 * Leitor minimo de H.264 Annex-B: acha start codes ({@code 00 00 01} /
 * {@code 00 00 00 01}) e o tipo de cada NAL dentro de um pedaco do fluxo.
 *
 * <p>Usado para (1) guardar o ultimo SPS/PPS visto e (2) saber se um pedaco
 * contem um ponto de entrada (SPS ou IDR). Assim, depois de uma reconexao ou
 * de descartar pedacos por fila cheia, o envio so recomeca num keyframe e o PC
 * consegue decodificar na hora, sem receber P-frames orfaos.</p>
 *
 * <p>Nao e thread-safe: e usado apenas pela thread de envio.</p>
 */
final class H264NalScanner {

    static final int NAL_IDR = 5;
    static final int NAL_SPS = 7;
    static final int NAL_PPS = 8;

    /** Resultado da analise de um pedaco. */
    static final class Info {
        boolean hasSps;
        boolean hasIdr;
    }

    private byte[] lastSps;
    private byte[] lastPps;

    /** Analisa o pedaco e atualiza o cache de SPS/PPS (so NALs completas dentro dele). */
    Info scan(byte[] data) {
        Info info = new Info();
        int n = data.length;
        int nalStart = -1;   // indice do primeiro byte apos o start code
        int codeStart = -1;  // indice do start code da NAL atual
        int i = 0;
        while (i + 2 < n) {
            if (data[i] == 0 && data[i + 1] == 0 && data[i + 2] == 1) {
                int thisCode = (i > 0 && data[i - 1] == 0) ? i - 1 : i;
                if (nalStart >= 0) {
                    cacheParameterSet(data, codeStart, thisCode, nalStart);
                }
                nalStart = i + 3;
                codeStart = thisCode;
                if (nalStart < n) {
                    int type = data[nalStart] & 0x1F;
                    if (type == NAL_SPS) info.hasSps = true;
                    else if (type == NAL_IDR) info.hasIdr = true;
                }
                i += 3;
            } else {
                i++;
            }
        }
        // A ultima NAL pode continuar no proximo pedaco: so e guardada se for
        // SPS/PPS e couber inteira (SPS/PPS sao pequenos e chegam juntos do IDR).
        return info;
    }

    private void cacheParameterSet(byte[] data, int codeStart, int end, int nalStart) {
        if (nalStart >= end) return;
        int type = data[nalStart] & 0x1F;
        if (type != NAL_SPS && type != NAL_PPS) return;
        byte[] nal = new byte[end - codeStart];
        System.arraycopy(data, codeStart, nal, 0, nal.length);
        if (type == NAL_SPS) lastSps = nal;
        else lastPps = nal;
    }

    /** SPS + PPS em cache (com start codes), ou {@code null} se ainda nao vistos. */
    byte[] cachedParameterSets() {
        if (lastSps == null || lastPps == null) return null;
        ByteArrayOutputStream out = new ByteArrayOutputStream(lastSps.length + lastPps.length);
        out.write(lastSps, 0, lastSps.length);
        out.write(lastPps, 0, lastPps.length);
        return out.toByteArray();
    }

    void reset() {
        lastSps = null;
        lastPps = null;
    }
}
