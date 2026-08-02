package org.squinchmods.investigate;

import com.google.gson.JsonObject;

public record GenerationEvent(ProbePhase phase, JsonObject data) {
    public GenerationEvent {
        data = data.deepCopy();
    }
}
