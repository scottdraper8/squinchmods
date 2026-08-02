package org.squinchmods.investigate;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import net.minecraft.server.MinecraftServer;

public final class RuntimeDispatcher {
    public static final String PROTOCOL_VERSION = "1";
    private static final Gson GSON = new GsonBuilder().disableHtmlEscaping().create();
    private static final Path ROOT = Path.of(".squinch-investigate").toAbsolutePath().normalize();
    private static final Path REQUESTS = ROOT.resolve("requests");
    private static final Path PROCESSING = ROOT.resolve("processing");
    private static final Path RESULTS = ROOT.resolve("results");
    private static final Map<String, ActiveRequest> ACTIVE = new ConcurrentHashMap<>();
    private static Thread serverThread;
    private static boolean initialized;

    static {
        BuiltinProbes.register();
    }

    private RuntimeDispatcher() {
    }

    public static void tick(MinecraftServer server) {
        try {
            requireServerThread();
            initialize();
            claimRequests();
            for (ActiveRequest active : List.copyOf(ACTIVE.values())) {
                active.drainGenerationEvents();
                try {
                    ProbeResult result = active.execution.tick(server);
                    if (result != null) {
                        publish(active, result.toJson());
                    }
                } catch (Throwable thrown) {
                    publishException(active, thrown, "probe tick threw");
                }
            }
        } catch (Throwable thrown) {
            System.err.println("[squinch-investigate] dispatcher tick failed: " + thrown);
            thrown.printStackTrace(System.err);
        }
    }

    public static void stop(MinecraftServer server) {
        try {
            requireServerThread();
            initialize();
            claimRequests();
            for (ActiveRequest active : List.copyOf(ACTIVE.values())) {
                active.drainGenerationEvents();
                try {
                    ProbeResult result = active.execution.flush(server);
                    if (result == null) {
                        JsonObject data = new JsonObject();
                        data.addProperty("message", "server stopped before probe completed");
                        result = ProbeResult.partial(
                                ProbePhase.RELOAD, data, 0, 1, "server-stop");
                    }
                    publish(active, result.toJson());
                } catch (Throwable thrown) {
                    publishException(active, thrown, "probe stop-time flush threw");
                }
            }
        } catch (Throwable thrown) {
            System.err.println("[squinch-investigate] dispatcher stop flush failed: " + thrown);
            thrown.printStackTrace(System.err);
        }
    }

    public static void collect(String probeId, GenerationEvent event) {
        for (ActiveRequest active : ACTIVE.values()) {
            if (active.request.probeId().equals(probeId)) {
                active.generationEvents.add(new GenerationEvent(event.phase(), event.data()));
            }
        }
    }

    private static void requireServerThread() {
        Thread current = Thread.currentThread();
        if (serverThread == null) {
            serverThread = current;
        } else if (serverThread != current) {
            throw new IllegalStateException("probe dispatcher invoked outside the Minecraft server thread");
        }
    }

    private static void initialize() throws IOException {
        if (initialized) {
            return;
        }
        Files.createDirectories(REQUESTS);
        Files.createDirectories(PROCESSING);
        Files.createDirectories(RESULTS);
        initialized = true;
        System.out.println("[squinch-investigate] protocol ready at " + ROOT);
    }

    private static void claimRequests() throws IOException {
        List<Path> pending = new ArrayList<>();
        try (DirectoryStream<Path> stream = Files.newDirectoryStream(REQUESTS, "*.json")) {
            for (Path path : stream) {
                if (Files.isRegularFile(path)) {
                    pending.add(path);
                }
            }
        }
        pending.sort(Comparator.comparing(path -> path.getFileName().toString()));
        for (Path requestPath : pending) {
            Path claimed = PROCESSING.resolve(requestPath.getFileName());
            try {
                atomicMove(requestPath, claimed, false);
            } catch (IOException race) {
                if (Files.exists(requestPath)) {
                    throw race;
                }
                continue;
            }
            try {
                ProbeRequest request = parseRequest(claimed);
                if (ACTIVE.containsKey(request.requestId())) {
                    throw new IllegalArgumentException("request ID is already active");
                }
                Path result = RESULTS.resolve(request.requestId() + ".jsonl");
                if (Files.exists(result)) {
                    throw new IllegalArgumentException("terminal result already exists for request ID");
                }
                ProbeRegistry.RegisteredProbe registered = ProbeRegistry.find(request.probeId());
                if (registered == null) {
                    throw new IllegalArgumentException("unknown probe ID: " + request.probeId());
                }
                if (!registered.version().equals(request.probeVersion())) {
                    throw new IllegalArgumentException(
                            "probe version mismatch: runtime has " + registered.version()
                                    + ", request asked for " + request.probeVersion());
                }
                ProbeExecution execution = registered.factory().create(request);
                ACTIVE.put(request.requestId(), new ActiveRequest(request, claimed, result, execution));
            } catch (Throwable thrown) {
                ProbeRequest fallback = fallbackRequest(claimed);
                ActiveRequest active = new ActiveRequest(
                        fallback,
                        claimed,
                        RESULTS.resolve(fallback.requestId() + ".jsonl"),
                        server -> null);
                publishException(active, thrown, "request could not be started");
            }
        }
    }

    private static ProbeRequest parseRequest(Path path) throws IOException {
        JsonObject value = JsonParser.parseString(Files.readString(path, StandardCharsets.UTF_8))
                .getAsJsonObject();
        String protocol = requiredString(value, "protocol_version");
        if (!PROTOCOL_VERSION.equals(protocol)) {
            throw new IllegalArgumentException("unsupported protocol version: " + protocol);
        }
        JsonObject config = value.has("config") && value.get("config").isJsonObject()
                ? value.getAsJsonObject("config").deepCopy()
                : new JsonObject();
        return new ProbeRequest(
                requiredString(value, "run_id"),
                requiredString(value, "request_id"),
                requiredString(value, "probe_id"),
                requiredString(value, "probe_version"),
                config);
    }

    private static ProbeRequest fallbackRequest(Path path) {
        String requestId = path.getFileName().toString().replaceFirst("\\.json$", "");
        String runId = "unknown";
        String probeId = "unknown";
        String probeVersion = "unknown";
        try {
            JsonObject value = JsonParser.parseString(Files.readString(path, StandardCharsets.UTF_8))
                    .getAsJsonObject();
            runId = optionalString(value, "run_id", runId);
            requestId = optionalString(value, "request_id", requestId);
            probeId = optionalString(value, "probe_id", probeId);
            probeVersion = optionalString(value, "probe_version", probeVersion);
        } catch (Throwable ignored) {
        }
        return new ProbeRequest(runId, requestId, probeId, probeVersion, new JsonObject());
    }

    private static String requiredString(JsonObject value, String key) {
        String result = optionalString(value, key, null);
        if (result == null || result.isBlank()) {
            throw new IllegalArgumentException("missing nonempty string: " + key);
        }
        return result;
    }

    private static String optionalString(JsonObject value, String key, String fallback) {
        JsonElement element = value.get(key);
        return element != null && element.isJsonPrimitive() && element.getAsJsonPrimitive().isString()
                ? element.getAsString()
                : fallback;
    }

    private static void publishException(ActiveRequest active, Throwable thrown, String message) {
        JsonObject result = new JsonObject();
        result.addProperty("state", TerminalState.ERROR.wireName());
        result.addProperty("phase", ProbePhase.RELOAD.wireName());
        result.addProperty("message", message);
        result.add("exception", serializeException(thrown));
        JsonObject completeness = new JsonObject();
        completeness.addProperty("inspected", 0);
        completeness.addProperty("skipped", 1);
        completeness.addProperty("complete", false);
        completeness.addProperty("reason", "exception");
        result.add("completeness", completeness);
        try {
            publish(active, result);
        } catch (Throwable publishingFailure) {
            System.err.println("[squinch-investigate] could not publish probe error: " + publishingFailure);
            publishingFailure.printStackTrace(System.err);
        }
    }

    private static JsonObject serializeException(Throwable thrown) {
        JsonObject exception = new JsonObject();
        exception.addProperty("type", thrown.getClass().getName());
        exception.addProperty("message", String.valueOf(thrown.getMessage()));
        JsonArray frames = new JsonArray();
        StackTraceElement[] stack = thrown.getStackTrace();
        for (int index = 0; index < Math.min(stack.length, 24); index++) {
            frames.add(stack[index].toString());
        }
        exception.add("stack", frames);
        if (thrown.getCause() != null && thrown.getCause() != thrown) {
            JsonObject cause = new JsonObject();
            cause.addProperty("type", thrown.getCause().getClass().getName());
            cause.addProperty("message", String.valueOf(thrown.getCause().getMessage()));
            exception.add("cause", cause);
        }
        return exception;
    }

    private static void publish(ActiveRequest active, JsonObject body) throws IOException {
        JsonObject accepted = identity(active.request);
        accepted.addProperty("type", "progress");
        accepted.addProperty("event", "accepted");
        accepted.addProperty("timestamp", Instant.now().toString());

        JsonObject terminal = identity(active.request);
        terminal.addProperty("type", "terminal");
        terminal.addProperty("timestamp", Instant.now().toString());
        for (var entry : body.entrySet()) {
            terminal.add(entry.getKey(), entry.getValue().deepCopy());
        }
        Path temporary = active.resultPath.resolveSibling(active.resultPath.getFileName() + ".tmp");
        String transcript = GSON.toJson(accepted) + "\n" + GSON.toJson(terminal) + "\n";
        Files.writeString(
                temporary,
                transcript,
                StandardCharsets.UTF_8,
                StandardOpenOption.CREATE_NEW,
                StandardOpenOption.WRITE);
        atomicMove(temporary, active.resultPath, false);
        Files.deleteIfExists(active.claimedPath);
        ACTIVE.remove(active.request.requestId());
        System.out.println(
                "[squinch-investigate] " + active.request.requestId() + " -> "
                        + terminal.get("state").getAsString());
    }

    private static JsonObject identity(ProbeRequest request) {
        JsonObject identity = new JsonObject();
        identity.addProperty("protocol_version", PROTOCOL_VERSION);
        identity.addProperty("run_id", request.runId());
        identity.addProperty("request_id", request.requestId());
        identity.addProperty("probe_id", request.probeId());
        identity.addProperty("probe_version", request.probeVersion());
        return identity;
    }

    private static void atomicMove(Path source, Path target, boolean replace) throws IOException {
        List<StandardCopyOption> options = new ArrayList<>();
        options.add(StandardCopyOption.ATOMIC_MOVE);
        if (replace) {
            options.add(StandardCopyOption.REPLACE_EXISTING);
        }
        try {
            Files.move(source, target, options.toArray(StandardCopyOption[]::new));
        } catch (AtomicMoveNotSupportedException unsupported) {
            options.remove(StandardCopyOption.ATOMIC_MOVE);
            Files.move(source, target, options.toArray(StandardCopyOption[]::new));
        }
    }

    private static final class ActiveRequest {
        private final ProbeRequest request;
        private final Path claimedPath;
        private final Path resultPath;
        private final ProbeExecution execution;
        private final ConcurrentLinkedQueue<GenerationEvent> generationEvents =
                new ConcurrentLinkedQueue<>();

        private ActiveRequest(
                ProbeRequest request, Path claimedPath, Path resultPath, ProbeExecution execution) {
            this.request = request;
            this.claimedPath = claimedPath;
            this.resultPath = resultPath;
            this.execution = execution;
        }

        private void drainGenerationEvents() {
            GenerationEvent event;
            while ((event = this.generationEvents.poll()) != null) {
                this.execution.acceptGenerationEvent(event);
            }
        }
    }
}
