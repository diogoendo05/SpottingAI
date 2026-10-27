package br.edu.spottingai.drone;

import android.util.Log;

import java.io.BufferedOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.util.Arrays;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Envia o H.264 do drone para o PC por TCP, sem bloquear o callback do SDK.
 *
 * <ul>
 *   <li>{@link #offer} (chamado no {@code VideoDataListener.onReceive}) so copia
 *       os bytes e tenta enfileirar - nunca bloqueia nem faz I/O.</li>
 *   <li>Uma thread propria conecta, escreve e reconecta sozinha
 *       (espera de 1 s, 2 s, 4 s ... ate 5 s) enquanto o envio estiver ativo.</li>
 *   <li>Fila cheia (rede lenta) => a fila e esvaziada em vez de acumular
 *       atraso, e o app forca um keyframe novo para limpar a imagem.</li>
 * </ul>
 */
final class VideoStreamSender {

    private static final String TAG = "VideoStreamSender";

    /** ~4 s de video a 30 fps; acima disso a latencia ja nao vale a pena. */
    private static final int QUEUE_CAPACITY = 120;
    private static final int CONNECT_TIMEOUT_MS = 3000;
    private static final int MAX_BACKOFF_MS = 5000;

    enum State { STOPPED, CONNECTING, CONNECTED, RETRY_WAIT }

    interface Listener {
        /** Chamado na thread de envio; quem atualiza a UI deve usar runOnUiThread. */
        void onStateChanged(State state, String detail);
    }

    private final ArrayBlockingQueue<byte[]> queue = new ArrayBlockingQueue<>(QUEUE_CAPACITY);
    private final AtomicBoolean resyncRequested = new AtomicBoolean(true);
    private final AtomicLong bytesSent = new AtomicLong();
    private final AtomicLong chunksDropped = new AtomicLong();
    private final H264NalScanner scanner = new H264NalScanner();
    private final Listener listener;

    private volatile boolean running;
    private volatile boolean waitForKeyframe = true;
    private volatile boolean connected;
    /** Quando comecou a espera por SPS/IDR (0 = nao esta esperando). */
    private volatile long resyncSince;
    private volatile Socket socket;
    /** SPS/PPS ja enviados nesta conexao (so a thread de envio usa). */
    private boolean paramsSent;
    private Thread thread;
    private String host;
    private int port;

    VideoStreamSender(Listener listener) {
        this.listener = listener;
    }

    /**
     * Inicia o envio para {@code host:port}.
     *
     * @param waitForKeyframe {@code true} para o feed transcodificado (H.264
     *     padrao): so envia a partir de SPS/IDR. {@code false} para o feed
     *     primario, que nao traz SPS/PPS e seria descartado para sempre.
     */
    synchronized void start(String host, int port, boolean waitForKeyframe) {
        stop();
        this.host = host;
        this.port = port;
        this.waitForKeyframe = waitForKeyframe;
        queue.clear();
        scanner.reset();
        resyncRequested.set(false);
        requestResync();
        running = true;
        thread = new Thread(this::runLoop, "h264-sender");
        thread.start();
    }

    synchronized void stop() {
        running = false;
        closeSocket();
        Thread t = thread;
        thread = null;
        if (t != null) {
            t.interrupt();
            try {
                t.join(2000);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
        }
        queue.clear();
        notifyState(State.STOPPED, "");
    }

    boolean isRunning() {
        return running;
    }

    /** Chamado no callback de video do SDK: copia e enfileira, sem bloquear. */
    void offer(byte[] videoBuffer, int size) {
        if (!running || videoBuffer == null || size <= 0) return;
        byte[] copy = Arrays.copyOf(videoBuffer, size);
        if (!queue.offer(copy)) {
            // Rede nao acompanha: descarta o atraso acumulado e pede um keyframe
            // (ate ele chegar o PC mostra a imagem com alguns borroes).
            int dropped = queue.size() + 1;
            queue.clear();
            chunksDropped.addAndGet(dropped);
            requestResync();
        }
    }

    private void requestResync() {
        if (!resyncRequested.getAndSet(true)) resyncSince = System.currentTimeMillis();
    }

    /**
     * Ha quanto tempo (ms) o envio esta conectado mas parado esperando um
     * keyframe; 0 se nao esta esperando. O transcodificador da DJI quase nao
     * gera IDR, entao quem chama deve reiniciar o feed se isso crescer.
     */
    long keyframeWaitMs() {
        if (!connected || !waitForKeyframe || !resyncRequested.get() || resyncSince == 0) return 0;
        return System.currentTimeMillis() - resyncSince;
    }

    long bytesSent() {
        return bytesSent.get();
    }

    long chunksDropped() {
        return chunksDropped.get();
    }

    int queueSize() {
        return queue.size();
    }

    // -- thread de envio --------------------------------------------------- //

    private void runLoop() {
        int backoffMs = 1000;
        while (running) {
            notifyState(State.CONNECTING, host + ":" + port);
            Socket s = new Socket();
            socket = s;
            try {
                s.setTcpNoDelay(true);
                s.setSendBufferSize(512 * 1024);
                s.connect(new InetSocketAddress(host, port), CONNECT_TIMEOUT_MS);
                OutputStream out = new BufferedOutputStream(s.getOutputStream(), 64 * 1024);

                // Conexao nova: o PC precisa de SPS/PPS (e, para imagem limpa, um IDR).
                queue.clear();
                paramsSent = false;
                resyncRequested.set(false);
                requestResync();
                connected = true;
                backoffMs = 1000;
                notifyState(State.CONNECTED, host + ":" + port);
                Log.i(TAG, "Conectado a " + host + ":" + port);

                while (running) {
                    byte[] chunk = queue.poll(500, TimeUnit.MILLISECONDS);
                    if (chunk == null) {
                        out.flush();
                        continue;
                    }
                    writeChunk(out, chunk);
                    if (queue.isEmpty()) out.flush();
                }
            } catch (IOException e) {
                if (running) {
                    Log.w(TAG, "Conexao com o PC falhou: " + e.getMessage());
                    notifyState(State.RETRY_WAIT,
                            "Sem conexao (" + e.getMessage() + "). Nova tentativa em " + backoffMs / 1000 + " s");
                }
            } catch (InterruptedException e) {
                break;
            } finally {
                connected = false;
                closeSocket();
            }

            if (!running) break;
            try {
                Thread.sleep(backoffMs);
            } catch (InterruptedException e) {
                break;
            }
            backoffMs = Math.min(backoffMs * 2, MAX_BACKOFF_MS);
        }
    }

    private void writeChunk(OutputStream out, byte[] chunk) throws IOException {
        H264NalScanner.Info info = scanner.scan(chunk);

        if (waitForKeyframe && resyncRequested.get()) {
            if (info.hasSps || info.hasIdr) {
                if (resyncSince != 0) {
                    Log.i(TAG, "Keyframe apos " + (System.currentTimeMillis() - resyncSince) + " ms");
                }
                resyncRequested.set(false);
                resyncSince = 0;
            }
            if (!info.hasSps && !paramsSent) {
                byte[] params = scanner.cachedParameterSets();
                if (params == null) {
                    chunksDropped.incrementAndGet();
                    return;  // sem SPS/PPS o PC nao decodifica nada: espera o primeiro
                }
                // O transcodificador da DJI quase nao gera IDR: em vez de segurar
                // o envio (e o PC derrubar a conexao por inatividade), manda os
                // SPS/PPS em cache e segue. O PC exibe na hora (show_all) e a
                // imagem fica limpa no proximo IDR, que o app forca reiniciando
                // o transcodificador (veja keyframeWaitMs).
                out.write(params);
                bytesSent.addAndGet(params.length);
            }
            paramsSent = true;
        }

        out.write(chunk);
        bytesSent.addAndGet(chunk.length);
    }

    private void closeSocket() {
        Socket s = socket;
        socket = null;
        if (s != null) {
            try {
                s.close();  // tambem desbloqueia um write() parado
            } catch (IOException ignored) {
            }
        }
    }

    private void notifyState(State state, String detail) {
        if (listener != null) listener.onStateChanged(state, detail);
    }
}
