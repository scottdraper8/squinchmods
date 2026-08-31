package org.squinchmods.investigate.rtf.flowstorage.mixin;

import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.chunk.ChunkAccess;
import net.minecraft.world.level.chunk.storage.ChunkSerializer;
import org.squinchmods.investigate.rtf.flowstorage.FlowStorageNetworkTelemetry;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(ChunkSerializer.class)
public abstract class MixinChunkSerializerStorageNetwork {
	@Inject(method = "write", at = @At("RETURN"))
	private static void squinch$captureSerializedChunk(
		ServerLevel level,
		ChunkAccess chunk,
		CallbackInfoReturnable<CompoundTag> callback
	) {
		FlowStorageNetworkTelemetry.observe(level, chunk, callback.getReturnValue());
	}
}
