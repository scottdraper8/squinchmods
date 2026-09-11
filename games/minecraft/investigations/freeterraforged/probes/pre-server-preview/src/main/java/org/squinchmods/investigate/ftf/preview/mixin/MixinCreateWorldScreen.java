package org.squinchmods.investigate.ftf.preview.mixin;

import java.io.IOException;
import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationTargetException;
import java.util.concurrent.atomic.AtomicBoolean;

import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.screens.worldselection.CreateWorldScreen;
import net.minecraft.network.chat.Component;
import net.minecraft.world.level.levelgen.presets.WorldPresets;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.squinchmods.investigate.ftf.preview.LifecycleProbe;
import etcodehome.freeterraforged.client.gui.screen.presetconfig.PresetConfigScreen;
import etcodehome.freeterraforged.data.worldgen.preset.settings.Preset;
import etcodehome.freeterraforged.data.worldgen.preset.settings.Presets;

@Mixin(CreateWorldScreen.class)
public abstract class MixinCreateWorldScreen {
	private static final AtomicBoolean SQUINCH_CREATED = new AtomicBoolean();

	@Inject(method = "init", at = @At("TAIL"))
	private void squinch$createWorldAfterPreview(CallbackInfo callback) {
		if (System.getenv("SQUINCH_PRE_SERVER_CREATE_WORLD_RESULT") == null
			|| !SQUINCH_CREATED.compareAndSet(false, true)) {
			return;
		}
		CreateWorldScreen screen = (CreateWorldScreen) (Object) this;
		screen.getUiState().setName("squinch-pre-server-lifecycle-" + ProcessHandle.current().pid());
		String configuredSeed = System.getenv("SQUINCH_PREVIEW_SEED");
		if (configuredSeed != null && !configuredSeed.isBlank()) {
			screen.getUiState().setSeed(configuredSeed);
		}
		if (System.getenv("SQUINCH_VANILLA_WORLD_CONTROL") != null) {
			var normal = screen.getUiState().getNormalPresetList().stream()
				.filter(entry -> entry.preset().unwrapKey().filter(WorldPresets.NORMAL::equals).isPresent())
				.findFirst()
				.orElseThrow(() -> new IllegalStateException("vanilla normal world preset is unavailable"));
			screen.getUiState().setWorldType(normal);
			LifecycleProbe.stagingStarted(screen);
			LifecycleProbe.settingsReloaded();
			return;
		}
		PresetConfigScreen presetScreen = new PresetConfigScreen(screen);
		LifecycleProbe.stagingStarted(screen);
		try {
			Object preset = squinch$defaultPreset();
			if (LifecycleProbe.uiLifecycleEnabled()) {
				LifecycleProbe.beginUiLifecycle(screen, preset);
				return;
			}
			squinch$applyPreset(presetScreen, preset);
		} catch (ReflectiveOperationException | IOException failure) {
			throw new IllegalStateException("failed staging the FTF preset datapack", failure);
		}
	}

	private static Object squinch$defaultPreset() throws ReflectiveOperationException {
		Class<?> entryClass = Class.forName(
			"etcodehome.freeterraforged.client.gui.screen.presetconfig.PresetListPage$PresetEntry"
		);
		Constructor<?> constructor = entryClass.getDeclaredConstructor(
			String.class, Component.class, Preset.class, boolean.class, Button.OnPress.class
		);
		constructor.setAccessible(true);
		return constructor.newInstance(
			"squinch-default",
			Component.literal("squinch-default"),
			Presets.modernDefaultWithRivers(),
			true,
			(Button.OnPress) button -> {
			}
		);
	}

	private static void squinch$applyPreset(PresetConfigScreen screen, Object entry)
		throws ReflectiveOperationException, IOException {
		try {
			screen.getClass().getMethod("applyPreset", entry.getClass()).invoke(screen, entry);
		} catch (InvocationTargetException failure) {
			if (failure.getCause() instanceof IOException ioFailure) {
				throw ioFailure;
			}
			throw failure;
		}
	}
}
