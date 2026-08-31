package org.squinchmods.investigate.rtf.lithostitched.mixin;

import dev.worldgen.lithostitched.api.event.AddBiomeInjectorsEvent;
import dev.worldgen.lithostitched.api.registry.LithostitchedBuiltInRegistries;
import net.minecraft.core.Registry;
import net.minecraft.resources.ResourceLocation;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.squinchmods.investigate.rtf.lithostitched.UnknownBiomeInjector;

@Pseudo
@Mixin(targets = "dev.worldgen.lithostitched.Lithostitched", remap = false)
public abstract class MixinLithostitched {
	private static final ResourceLocation TYPE = ResourceLocation.fromNamespaceAndPath(
		"squinch", "unknown_injector"
	);
	private static final ResourceLocation ENTRY = ResourceLocation.fromNamespaceAndPath(
		"squinch", "unknown_injector_entry"
	);

	@Inject(method = "init", at = @At("TAIL"), remap = false)
	private static void squinch$registerUnknownInjector(CallbackInfo callback) {
		Registry.register(
			LithostitchedBuiltInRegistries.BIOME_INJECTOR_TYPE,
			TYPE,
			UnknownBiomeInjector.CODEC
		);
		AddBiomeInjectorsEvent.EVENT.register(
			(registries, consumer) -> consumer.accept(ENTRY, UnknownBiomeInjector.INSTANCE)
		);
	}
}
