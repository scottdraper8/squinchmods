package org.squinchmods.investigate.mixin;

import java.util.function.BooleanSupplier;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

import net.minecraft.server.MinecraftServer;
import org.squinchmods.investigate.RuntimeDispatcher;

@Mixin(MinecraftServer.class)
public abstract class MixinMinecraftServer {
    @Inject(method = "tickServer", at = @At("TAIL"))
    private void squinch$dispatch(BooleanSupplier hasTimeLeft, CallbackInfo callback) {
        RuntimeDispatcher.tick((MinecraftServer) (Object) this);
    }

    @Inject(method = "stopServer", at = @At("HEAD"))
    private void squinch$flush(CallbackInfo callback) {
        RuntimeDispatcher.stop((MinecraftServer) (Object) this);
    }
}
