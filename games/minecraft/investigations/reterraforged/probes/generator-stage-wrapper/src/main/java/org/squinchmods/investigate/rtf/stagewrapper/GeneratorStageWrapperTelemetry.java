package org.squinchmods.investigate.rtf.stagewrapper;

import java.util.concurrent.atomic.AtomicLong;

/** Process-local observation owned by this development probe pack. */
public final class GeneratorStageWrapperTelemetry {
    private static final AtomicLong FTF_SURFACE_WRAPPER_CALLS = new AtomicLong();

    private GeneratorStageWrapperTelemetry() {
    }

    public static void observeFtfSurfaceWrapper() {
        FTF_SURFACE_WRAPPER_CALLS.incrementAndGet();
    }

    public static long ftfSurfaceWrapperCalls() {
        return FTF_SURFACE_WRAPPER_CALLS.get();
    }
}
