package org.squinchmods.investigate;

import java.util.ArrayList;
import java.util.List;
import java.util.ServiceLoader;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.FullChunkStatus;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.chunk.LevelChunk;

final class BuiltinProbes {
    private BuiltinProbes() {
    }

    static void register() {
        ProbeRegistry.register("squinch:runtime-smoke", "1", request -> server -> {
            JsonObject data = new JsonObject();
            data.addProperty("server_thread", Thread.currentThread().getName());
            data.addProperty("levels", count(server.getAllLevels()));
            return ProbeResult.complete(TerminalState.PASS, ProbePhase.FINISHED_CHUNK, data, 1);
        });
        ProbeRegistry.register("squinch:partial-control", "1", request -> server -> {
            JsonObject data = new JsonObject();
            data.addProperty("control", "deliberately-partial");
            return ProbeResult.partial(
                    ProbePhase.FINISHED_CHUNK,
                    data,
                    1,
                    1,
                    "negative-control-intentionally-skipped-one-item");
        });
        ProbeRegistry.register("squinch:exception-control", "1", request -> server -> {
            throw new IllegalStateException("deliberate probe exception control");
        });
        ProbeRegistry.register("squinch:isolation-control", "1", request -> {
            String token = request.config().has("token")
                    ? request.config().get("token").getAsString()
                    : request.requestId();
            int waitTicks = request.config().has("wait_ticks")
                    ? request.config().get("wait_ticks").getAsInt()
                    : 5;
            return new ProbeExecution() {
                private int ticks;

                @Override
                public ProbeResult tick(MinecraftServer server) {
                    this.ticks++;
                    if (this.ticks < waitTicks) {
                        return null;
                    }
                    JsonObject data = new JsonObject();
                    data.addProperty("token", token);
                    data.addProperty("ticks", this.ticks);
                    return ProbeResult.complete(
                            TerminalState.PASS, ProbePhase.FINISHED_CHUNK, data, 1);
                }
            };
        });
        ProbeRegistry.register("squinch:stop-flush-control", "1", request -> server -> null);
        ProbeRegistry.register("squinch:finished-chunks", "1", FinishedChunks::new);
        ProbeRegistry.register("squinch:finished-chunk-palette", "1", FinishedChunkPalette::new);
        ServiceLoader.load(ProbePack.class, ProbePack.class.getClassLoader())
                .forEach(ProbePack::register);
    }

    private static int count(Iterable<?> values) {
        int count = 0;
        for (Object ignored : values) {
            count++;
        }
        return count;
    }

    private static final class FinishedChunks implements ProbeExecution {
        private final FinishedChunkSelection selection;

        private FinishedChunks(ProbeRequest request) {
            this.selection = new FinishedChunkSelection(request.config(), "finished-chunks");
        }

        @Override
        public ProbeResult tick(MinecraftServer server) {
            FinishedChunkSelection.Snapshot snapshot = this.selection.poll(server.overworld());
            if (snapshot == null) {
                return null;
            }
            JsonObject data = new JsonObject();
            data.add("missing_examples", snapshot.notReadyExamples().deepCopy());
            return this.selection.result(snapshot, data);
        }
    }
}
