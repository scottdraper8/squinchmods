package org.squinchmods.investigate.rtf.enclosure;

import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.util.HashSet;
import java.util.Set;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.ChunkPos;
import org.squinchmods.investigate.FinishedChunkSelection;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbePhase;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;
import org.squinchmods.investigate.TerminalState;
import raccoonman.reterraforged.world.worldgen.GeneratorContext;
import raccoonman.reterraforged.world.worldgen.RTFRandomState;
import raccoonman.reterraforged.world.worldgen.biome.UndergroundBiomeSurfaceProtection;
import raccoonman.reterraforged.world.worldgen.cell.Cell;

public final class RtfUndergroundFeatureEnclosureProbePack implements ProbePack {
    private static final int BUFFER_BLOCKS = UndergroundBiomeSurfaceProtection.HARD_SHELL_BLOCKS;

    @Override
    public void register() {
        ProbeRegistry.register(
            "squinch:rtf-underground-feature-enclosure",
            "1",
            UndergroundFeatureEnclosureProbe::new
        );
    }

    private static final class UndergroundFeatureEnclosureProbe implements ProbeExecution {
        private final FinishedChunkSelection selection;
        private final boolean requireActualChecks;

        private UndergroundFeatureEnclosureProbe(ProbeRequest request) {
            this.selection = new FinishedChunkSelection(request.config(), "rtf-underground-feature-enclosure");
            this.requireActualChecks = !request.config().has("require_actual_checks")
                || request.config().get("require_actual_checks").getAsBoolean();
        }

        @Override
        public ProbeResult tick(net.minecraft.server.MinecraftServer server) throws Exception {
            ServerLevel level = server.overworld();
            FinishedChunkSelection.Snapshot snapshot = this.selection.poll(level);
            if (snapshot == null) {
                return null;
            }

            Set<Long> selectedChunks = new HashSet<>();
            snapshot.ready().forEach(ready -> selectedChunks.add(
                ChunkPos.asLong(ready.coordinate().x(), ready.coordinate().z())
            ));
            long actualChecks = 0;
            long actualAccepted = 0;
            long actualRejected = 0;
            JsonArray actualExamples = new JsonArray();
            for (var entry : UndergroundFeatureEnclosureTelemetry.stats().entrySet()) {
                if (!selectedChunks.contains(entry.getKey())) {
                    continue;
                }
                var stats = entry.getValue();
                actualChecks += stats.checked.sum();
                actualAccepted += stats.accepted.sum();
                actualRejected += stats.rejected.sum();
                synchronized (stats.examples) {
                    for (var example : stats.examples) {
                        if (actualExamples.size() >= 32) {
                            break;
                        }
                        JsonObject value = new JsonObject();
                        value.addProperty("x", example.position().getX());
                        value.addProperty("y", example.position().getY());
                        value.addProperty("z", example.position().getZ());
                        value.addProperty("accepted", example.accepted());
                        actualExamples.add(value);
                    }
                }
            }

            RTFRandomState randomState = (RTFRandomState)(Object)level.getChunkSource().randomState();
            GeneratorContext context = randomState.generatorContext();
            if (context == null) {
                throw new IllegalStateException("FTF GeneratorContext unavailable");
            }
            Class<?> guardClass = Class.forName(
                "raccoonman.reterraforged.world.worldgen.feature.placement.UndergroundFeatureEnclosure$Guard"
            );
            Constructor<?> constructor = guardClass.getDeclaredConstructor(GeneratorContext.class);
            constructor.setAccessible(true);
            Object guard = constructor.newInstance(context);
            Method isProtected = guardClass.getDeclaredMethod("isProtected", BlockPos.class);
            isProtected.setAccessible(true);

            Cell cell = new Cell();
            long syntheticChecks = 0;
            long syntheticMismatches = 0;
            JsonArray syntheticExamples = new JsonArray();
            for (FinishedChunkSelection.ReadyChunk ready : snapshot.ready()) {
                int x = ready.coordinate().x() * 16 + 8;
                int z = ready.coordinate().z() * 16 + 8;
                int minimumSurfaceY = Integer.MAX_VALUE;
                for (int sampleZ = z - BUFFER_BLOCKS; sampleZ <= z + BUFFER_BLOCKS; sampleZ++) {
                    for (int sampleX = x - BUFFER_BLOCKS; sampleX <= x + BUFFER_BLOCKS; sampleX++) {
                        minimumSurfaceY = Math.min(
                            minimumSurfaceY,
                            UndergroundBiomeSurfaceProtection.sampleSurfaceY(context, cell, sampleX, sampleZ)
                        );
                    }
                }
                int rejectedY = minimumSurfaceY - BUFFER_BLOCKS;
                int acceptedY = rejectedY - 1;
                boolean rejectedResult = (Boolean)isProtected.invoke(guard, new BlockPos(x, rejectedY, z));
                boolean acceptedResult = (Boolean)isProtected.invoke(guard, new BlockPos(x, acceptedY, z));
                syntheticChecks += 2;
                if (rejectedResult || !acceptedResult) {
                    syntheticMismatches++;
                }
                if (syntheticExamples.size() < 16) {
                    JsonObject example = new JsonObject();
                    example.addProperty("x", x);
                    example.addProperty("z", z);
                    example.addProperty("minimum_surface_y", minimumSurfaceY);
                    example.addProperty("rejected_y", rejectedY);
                    example.addProperty("rejected_result", rejectedResult);
                    example.addProperty("accepted_y", acceptedY);
                    example.addProperty("accepted_result", acceptedResult);
                    syntheticExamples.add(example);
                }
            }

            JsonObject data = new JsonObject();
            data.addProperty("authority", "placement-hook-and-runtime-terrain-context");
            data.addProperty("buffer_blocks", BUFFER_BLOCKS);
            data.addProperty("actual_checks", actualChecks);
            data.addProperty("actual_accepted", actualAccepted);
            data.addProperty("actual_rejected", actualRejected);
            data.addProperty("require_actual_checks", this.requireActualChecks);
            data.add("actual_examples", actualExamples);
            data.addProperty("synthetic_boundary_checks", syntheticChecks);
            data.addProperty("synthetic_boundary_mismatches", syntheticMismatches);
            data.add("synthetic_examples", syntheticExamples);
            data.addProperty("requested_chunks", snapshot.requested());
            data.addProperty("ready_chunks", snapshot.ready().size());
            return ProbeResult.complete(
                (!this.requireActualChecks || actualChecks > 0) && syntheticMismatches == 0
                    ? TerminalState.PASS
                    : TerminalState.FAIL,
                ProbePhase.FINISHED_CHUNK,
                data,
                snapshot.ready().size()
            );
        }
    }
}
