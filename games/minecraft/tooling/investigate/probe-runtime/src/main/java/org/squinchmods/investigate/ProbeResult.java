package org.squinchmods.investigate;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

public final class ProbeResult {
    private static final java.util.Set<String> RESERVED = java.util.Set.of(
            "protocol_version",
            "run_id",
            "request_id",
            "probe_id",
            "probe_version",
            "type",
            "timestamp",
            "state",
            "phase",
            "completeness");
    private final TerminalState state;
    private final ProbePhase phase;
    private final JsonObject data;
    private final long inspected;
    private final long skipped;
    private final boolean complete;
    private final String completenessReason;

    private ProbeResult(
            TerminalState state,
            ProbePhase phase,
            JsonObject data,
            long inspected,
            long skipped,
            boolean complete,
            String completenessReason) {
        this.state = state;
        this.phase = phase;
        this.data = data.deepCopy();
        this.inspected = inspected;
        this.skipped = skipped;
        this.complete = complete;
        this.completenessReason = completenessReason;
        if (inspected < 0 || skipped < 0) {
            throw new IllegalArgumentException("completeness counts must not be negative");
        }
        for (String key : data.keySet()) {
            if (RESERVED.contains(key)) {
                throw new IllegalArgumentException("probe data uses reserved result key: " + key);
            }
        }
    }

    public static ProbeResult complete(TerminalState state, ProbePhase phase, JsonObject data, long inspected) {
        return new ProbeResult(state, phase, data, inspected, 0, true, null);
    }

    public static ProbeResult partial(
            ProbePhase phase, JsonObject data, long inspected, long skipped, String reason) {
        return new ProbeResult(TerminalState.INCONCLUSIVE, phase, data, inspected, skipped, false, reason);
    }

    public JsonObject toJson() {
        JsonObject result = new JsonObject();
        result.addProperty("state", this.state.wireName());
        result.addProperty("phase", this.phase.wireName());
        JsonObject completeness = new JsonObject();
        completeness.addProperty("inspected", this.inspected);
        completeness.addProperty("skipped", this.skipped);
        completeness.addProperty("complete", this.complete);
        if (this.completenessReason != null) {
            completeness.addProperty("reason", this.completenessReason);
        }
        result.add("completeness", completeness);
        for (var entry : this.data.entrySet()) {
            JsonElement value = entry.getValue();
            result.add(entry.getKey(), value == null ? null : value.deepCopy());
        }
        return result;
    }
}
