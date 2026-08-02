package org.squinchmods.investigate;

import com.google.gson.JsonObject;

public record ProbeRequest(
        String runId,
        String requestId,
        String probeId,
        String probeVersion,
        JsonObject config) {
}
