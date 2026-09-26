package org.squinchmods.investigate;

import com.google.gson.JsonObject;

public final class RuntimeHooks {
    private RuntimeHooks() {
    }

    public static void generation(String probeId, ProbePhase phase, JsonObject data) {
        RuntimeDispatcher.collect(probeId, new GenerationEvent(phase, data));
    }
}
