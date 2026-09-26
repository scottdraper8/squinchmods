package org.squinchmods.investigate;

import java.util.ArrayList;
import java.util.List;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import net.minecraft.server.level.FullChunkStatus;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.chunk.LevelChunk;

/** Shared bounded parser/poller for probes whose authority starts at a real LevelChunk. */
public final class FinishedChunkSelection {
    private final List<Coordinate> coordinates;
    private final int maxWaitTicks;
    private final int exampleLimit;
    private int ticks;

    public FinishedChunkSelection(JsonObject config, String probeName) {
        if (!config.has("bounds") || !config.get("bounds").isJsonArray()) {
            throw new IllegalArgumentException(probeName + " requires config.bounds");
        }
        JsonArray bounds = config.getAsJsonArray("bounds");
        if (bounds.size() != 4) {
            throw new IllegalArgumentException(probeName + " bounds must have four integers");
        }
        String unit = config.has("unit") ? config.get("unit").getAsString() : "chunk";
        int minX = bounds.get(0).getAsInt();
        int minZ = bounds.get(1).getAsInt();
        int maxX = bounds.get(2).getAsInt();
        int maxZ = bounds.get(3).getAsInt();
        if ("block".equals(unit)) {
            minX = Math.floorDiv(minX, 16);
            minZ = Math.floorDiv(minZ, 16);
            maxX = Math.floorDiv(maxX, 16);
            maxZ = Math.floorDiv(maxZ, 16);
        } else if (!"chunk".equals(unit)) {
            throw new IllegalArgumentException(probeName + " unit must be block or chunk");
        }
        if (minX > maxX || minZ > maxZ) {
            throw new IllegalArgumentException(probeName + " bounds are inverted");
        }
        int maximum = config.has("max_chunks") ? config.get("max_chunks").getAsInt() : 65_536;
        if (maximum < 1 || maximum > 65_536) {
            throw new IllegalArgumentException("max_chunks must be 1..65536");
        }
        long widthX = (long) maxX - minX + 1L;
        long widthZ = (long) maxZ - minZ + 1L;
        if (widthX > maximum || widthZ > maximum || widthX * widthZ > maximum) {
            throw new IllegalArgumentException(
                probeName + " request exceeds the maximum of " + maximum + " chunks"
            );
        }
        long requested = widthX * widthZ;
        List<Coordinate> values = new ArrayList<>((int) requested);
        for (long x = minX; x <= maxX; x++) {
            for (long z = minZ; z <= maxZ; z++) {
                values.add(new Coordinate((int) x, (int) z));
            }
        }
        this.coordinates = List.copyOf(values);
        this.maxWaitTicks = config.has("max_wait_ticks")
            ? config.get("max_wait_ticks").getAsInt()
            : 1200;
        this.exampleLimit = config.has("not_ready_example_limit")
            ? config.get("not_ready_example_limit").getAsInt()
            : 32;
        if (this.maxWaitTicks < 1 || this.exampleLimit < 0 || this.exampleLimit > 1024) {
            throw new IllegalArgumentException(
                "max_wait_ticks must be positive and not_ready_example_limit must be 0..1024"
            );
        }
    }

    /** Returns null while bounded polling may continue, otherwise a terminal snapshot. */
    public Snapshot poll(ServerLevel level) {
        this.ticks++;
        List<ReadyChunk> ready = new ArrayList<>();
        JsonArray notReady = new JsonArray();
        for (Coordinate coordinate : this.coordinates) {
            LevelChunk chunk = level.getChunkSource().getChunkNow(coordinate.x(), coordinate.z());
            if (chunk != null && chunk.getFullStatus().isOrAfter(FullChunkStatus.FULL)) {
                ready.add(new ReadyChunk(coordinate, chunk));
            } else if (notReady.size() < this.exampleLimit) {
                JsonArray pair = new JsonArray();
                pair.add(coordinate.x());
                pair.add(coordinate.z());
                notReady.add(pair);
            }
        }
        boolean complete = ready.size() == this.coordinates.size();
        if (!complete && this.ticks < this.maxWaitTicks) {
            return null;
        }
        return new Snapshot(
            List.copyOf(ready), notReady, this.coordinates.size(), this.ticks, complete
        );
    }

    public ProbeResult result(Snapshot snapshot, JsonObject data) {
        data.addProperty("requested_chunks", snapshot.requested());
        data.addProperty("ready_chunks", snapshot.ready().size());
        data.addProperty("poll_ticks", snapshot.pollTicks());
        data.add("not_ready_examples", snapshot.notReadyExamples().deepCopy());
        if (snapshot.complete()) {
            return ProbeResult.complete(
                TerminalState.PASS, ProbePhase.FINISHED_CHUNK, data, snapshot.ready().size()
            );
        }
        return ProbeResult.partial(
            ProbePhase.FINISHED_CHUNK,
            data,
            snapshot.ready().size(),
            snapshot.requested() - snapshot.ready().size(),
            "bounded-poll-expired"
        );
    }

    public record Coordinate(int x, int z) {
    }

    public record ReadyChunk(Coordinate coordinate, LevelChunk chunk) {
    }

    public record Snapshot(
        List<ReadyChunk> ready,
        JsonArray notReadyExamples,
        int requested,
        int pollTicks,
        boolean complete
    ) {
    }
}
