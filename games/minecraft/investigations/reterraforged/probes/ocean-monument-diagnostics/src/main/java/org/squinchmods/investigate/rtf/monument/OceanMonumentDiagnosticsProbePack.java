package org.squinchmods.investigate.rtf.monument;

import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.Map;
import java.util.TreeMap;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Blocks;
import org.squinchmods.investigate.FinishedChunkSelection;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;
import org.squinchmods.investigate.ProbePhase;
import org.squinchmods.investigate.TerminalState;

public final class OceanMonumentDiagnosticsProbePack implements ProbePack {
    public static final ConcurrentLinkedQueue<JsonObject> OBSERVATIONS = new ConcurrentLinkedQueue<>();

    @Override
    public void register() {
        ProbeRegistry.register("squinch:rtf-ocean-monument-diagnostics", "1", Diagnostics::new);
    }

    private static final class Diagnostics implements ProbeExecution {
        private final FinishedChunkSelection selection;
        private final int minimumObservations;

        private Diagnostics(ProbeRequest request) {
            this.selection = new FinishedChunkSelection(request.config(), "rtf-ocean-monument-diagnostics");
            this.minimumObservations = request.config().has("min_observations")
                ? request.config().get("min_observations").getAsInt()
                : 1;
            if (this.minimumObservations < 1) {
                throw new IllegalArgumentException("min_observations must be positive");
            }
        }

        @Override
        public ProbeResult tick(net.minecraft.server.MinecraftServer server) {
            FinishedChunkSelection.Snapshot snapshot = this.selection.poll(server.overworld());
            if (snapshot == null) {
                return null;
            }

            JsonArray observations = new JsonArray();
            JsonObject observation;
            while ((observation = OBSERVATIONS.poll()) != null) {
                observations.add(observation);
            }

            JsonObject data = new JsonObject();
            data.addProperty("authority", "finished-chunk");
            data.addProperty("observation_count", observations.size());
            data.addProperty("minimum_observations", this.minimumObservations);
            data.add("observations", observations);
            if (observations.size() > 0) {
                data.add("footprint_scan", scanFootprint(server.overworld(), observations.get(0).getAsJsonObject()));
            }
            if (snapshot.complete() && observations.size() < this.minimumObservations) {
                data.addProperty("requested_chunks", snapshot.requested());
                data.addProperty("ready_chunks", snapshot.ready().size());
                data.addProperty("poll_ticks", snapshot.pollTicks());
                data.add("not_ready_examples", snapshot.notReadyExamples().deepCopy());
                return ProbeResult.complete(TerminalState.FAIL, ProbePhase.FINISHED_CHUNK, data, snapshot.ready().size());
            }
            return this.selection.result(snapshot, data);
        }

        private static JsonObject scanFootprint(ServerLevel level, JsonObject observation) {
            int minX = observation.get("piece_min_x").getAsInt();
            int maxX = observation.get("piece_max_x").getAsInt();
            int minZ = observation.get("piece_min_z").getAsInt();
            int maxZ = observation.get("piece_max_z").getAsInt();
            int configuredSeaLevel = observation.get("preset_sea_level").getAsInt();
            Map<Integer, Integer> waterByY = new TreeMap<>();
            JsonArray highWaterExamples = new JsonArray();
            int columnsWithWater = 0;
            int columnsWithWaterAtOrAboveConfiguredSea = 0;
            int highestWater = Integer.MIN_VALUE;

            for (int x = minX; x <= maxX; x++) {
                for (int z = minZ; z <= maxZ; z++) {
                    int topWater = Integer.MIN_VALUE;
                    for (int y = level.getMinBuildHeight(); y <= level.getMaxBuildHeight(); y++) {
                        if (level.getBlockState(new BlockPos(x, y, z)).is(Blocks.WATER)) {
                            waterByY.merge(y, 1, Integer::sum);
                            topWater = y;
                            highestWater = Math.max(highestWater, y);
                        }
                    }
                    if (topWater != Integer.MIN_VALUE) {
                        columnsWithWater++;
                        if (topWater >= configuredSeaLevel) {
                            columnsWithWaterAtOrAboveConfiguredSea++;
                            if (highWaterExamples.size() < 32) {
                                JsonObject example = new JsonObject();
                                example.addProperty("x", x);
                                example.addProperty("z", z);
                                example.addProperty("top_water_y", topWater);
                                highWaterExamples.add(example);
                            }
                        }
                    }
                }
            }

            JsonObject result = new JsonObject();
            result.addProperty("min_x", minX);
            result.addProperty("max_x", maxX);
            result.addProperty("min_z", minZ);
            result.addProperty("max_z", maxZ);
            result.addProperty("configured_sea_level", configuredSeaLevel);
            result.addProperty("columns_with_water", columnsWithWater);
            result.addProperty("columns_with_water_at_or_above_configured_sea", columnsWithWaterAtOrAboveConfiguredSea);
            result.addProperty("highest_water_y", highestWater);
            JsonObject waterHistogram = new JsonObject();
            waterByY.forEach((y, count) -> waterHistogram.addProperty(Integer.toString(y), count));
            result.add("water_blocks_by_y", waterHistogram);
            result.add("high_water_examples", highWaterExamples);
            return result;
        }
    }
}
