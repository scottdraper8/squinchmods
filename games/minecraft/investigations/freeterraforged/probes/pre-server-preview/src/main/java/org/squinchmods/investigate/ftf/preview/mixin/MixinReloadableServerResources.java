package org.squinchmods.investigate.ftf.preview.mixin;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;

import net.minecraft.commands.Commands;
import net.minecraft.core.LayeredRegistryAccess;
import net.minecraft.server.RegistryLayer;
import net.minecraft.server.ReloadableServerResources;
import net.minecraft.server.packs.resources.ResourceManager;
import net.minecraft.world.flag.FeatureFlagSet;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(ReloadableServerResources.class)
public abstract class MixinReloadableServerResources {
	@Inject(method = "loadResources", at = @At("HEAD"))
	private static void squinch$reportLoadResources(
		ResourceManager resources,
		LayeredRegistryAccess<RegistryLayer> registries,
		FeatureFlagSet features,
		Commands.CommandSelection commandSelection,
		int functionCompilationLevel,
		Executor backgroundExecutor,
		Executor gameExecutor,
		CallbackInfoReturnable<CompletableFuture<ReloadableServerResources>> callback
	) {
		System.err.println("SQUINCH ReloadableServerResources.loadResources invoked");
	}

	@Inject(method = "updateRegistryTags", at = @At("HEAD"))
	private void squinch$reportUpdateRegistryTags(CallbackInfo callback) {
		System.err.println("SQUINCH ReloadableServerResources.updateRegistryTags invoked");
	}
}
