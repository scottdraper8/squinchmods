package org.squinchmods.investigate;

import java.util.Objects;
import java.util.concurrent.CompletableFuture;
import java.util.function.Function;

import net.minecraft.server.MinecraftServer;

public final class AsyncProbe implements ProbeExecution {
    private final CompletableFuture<?> future;
    private final Function<Object, ProbeResult> finish;

    @SuppressWarnings("unchecked")
    public <T> AsyncProbe(CompletableFuture<T> future, Function<T, ProbeResult> finish) {
        this.future = Objects.requireNonNull(future);
        this.finish = value -> finish.apply((T) value);
    }

    @Override
    public ProbeResult tick(MinecraftServer server) {
        if (!this.future.isDone()) {
            return null;
        }
        return this.finish.apply(this.future.join());
    }
}
