package org.squinchmods.investigate.rtf.client.mixin;

import java.io.IOException;
import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationTargetException;
import java.util.concurrent.atomic.AtomicBoolean;

import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.screens.worldselection.CreateWorldScreen;
import net.minecraft.network.chat.Component;
import org.squinchmods.investigate.rtf.client.WorldLifecycleProbe;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import raccoonman.reterraforged.client.gui.screen.presetconfig.PresetConfigScreen;
import raccoonman.reterraforged.data.worldgen.preset.settings.Preset;
import raccoonman.reterraforged.data.worldgen.preset.settings.Presets;

@Mixin(CreateWorldScreen.class)
public abstract class MixinCreateWorldScreen {
	private static final AtomicBoolean SQUINCH_CREATED = new AtomicBoolean();

	@Inject(method = "init", at = @At("TAIL"))
	private void squinch$stagePreset(CallbackInfo callback) {
		if (System.getenv("SQUINCH_CLIENT_WORLD_RESULT") == null
			|| !SQUINCH_CREATED.compareAndSet(false, true)) {
			return;
		}
		CreateWorldScreen screen = (CreateWorldScreen) (Object) this;
		screen.getUiState().setName("squinch-client-world-" + ProcessHandle.current().pid());
		String configuredSeed = System.getenv("SQUINCH_PREVIEW_SEED");
		if (configuredSeed != null && !configuredSeed.isBlank()) {
			screen.getUiState().setSeed(configuredSeed);
		}
		WorldLifecycleProbe.stagingStarted(screen);
		try {
			PresetConfigScreen presetScreen = new PresetConfigScreen(screen);
			Object preset = squinch$defaultPreset();
			try {
				presetScreen.getClass().getMethod("applyPreset", preset.getClass()).invoke(presetScreen, preset);
			} catch (InvocationTargetException failure) {
				if (failure.getCause() instanceof IOException ioFailure) {
					throw ioFailure;
				}
				throw failure;
			}
		} catch (ReflectiveOperationException | IOException failure) {
			throw new IllegalStateException("failed staging the FTF preset datapack", failure);
		}
	}

	private static Object squinch$defaultPreset() throws ReflectiveOperationException {
		Class<?> entryClass = Class.forName(
			"raccoonman.reterraforged.client.gui.screen.presetconfig.PresetListPage$PresetEntry"
		);
		Constructor<?> constructor = entryClass.getDeclaredConstructor(
			String.class, Component.class, Preset.class, boolean.class, Button.OnPress.class
		);
		constructor.setAccessible(true);
		return constructor.newInstance(
			"squinch-default", Component.literal("squinch-default"),
			Presets.modernDefaultWithRivers(), true, (Button.OnPress) button -> { }
		);
	}
}
