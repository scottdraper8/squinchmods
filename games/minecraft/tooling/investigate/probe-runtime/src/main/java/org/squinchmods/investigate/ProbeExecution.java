package org.squinchmods.investigate;

import net.minecraft.server.MinecraftServer;

public interface ProbeExecution {
    ProbeResult tick(MinecraftServer server) throws Exception;

    default void acceptGenerationEvent(GenerationEvent event) {
    }

    default ProbeResult flush(MinecraftServer server) throws Exception {
        return null;
    }
}
